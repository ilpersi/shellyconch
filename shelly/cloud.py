"""
Shelly Cloud Control API v2 client.

All control operations go through Shelly's cloud servers, so the target
device does not need to be on the same local network as the caller.  The
device only needs to be online and registered to the account.

Authentication
--------------
Two pieces of information are required, both obtained in the Shelly Cloud
mobile app under **User Settings → Authorization cloud key**:

- **server** — the HOST assigned to your account,
  e.g. ``"shelly-13-eu.shelly.cloud"``.
- **auth_key** — your personal authorization key.
  Keep it secret: anyone with this key can control all your devices.
  It is invalidated whenever you change your account password.

Rate limit
----------
Shelly's servers enforce **1 request per second**.  The library does *not*
throttle automatically; the caller is responsible for observing this limit.
Requests that exceed it will receive HTTP errors from the server.

Device IDs
----------
Device IDs are hex strings (e.g. ``"b48a0a1cd978"``), zero-padded to 6 or
12 characters.  They are case-insensitive.

For group operations the format is ``"<DEVICE_ID>_<CHANNEL>"``
(e.g. ``"b48a0a1cd978_0"``).  The channel suffix may be omitted and
defaults to ``0``.

Scope
-----
This module covers the **v2 HTTP API** only (endpoints under
``/v2/devices/api/``).  The real-time WebSocket + OAuth API (available at
``wss://<server>:6113/shelly/wss/hk_sock``) is not implemented here; it
requires a browser-based OAuth flow and persistent connection management.

Reference: https://shelly-api-docs.shelly.cloud/cloud-control-api/communication-v2
"""

from __future__ import annotations

from typing import Any

import requests

from .exceptions import ShellyAuthError, ShellyCloudError, ShellyConnectionError, ShellyTimeoutError


class ShellyCloud:
    """
    Client for the Shelly Cloud Control API v2.

    Parameters
    ----------
    server:
        Your assigned cloud server hostname, e.g.
        ``"shelly-13-eu.shelly.cloud"``.  Obtain this from the Shelly Cloud
        app under **User Settings → Authorization cloud key**.
    auth_key:
        Your authorization key from the same location.
    timeout:
        HTTP request timeout in seconds (default ``10``).

    Examples
    --------
    ::

        cloud = ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="abc123...")

        # Read state of two devices
        states = cloud.get_devices_state(
            ["b48a0a1cd978", "dc4f2276846a"],
            select=["status"],
        )

        # Control a relay
        cloud.turn_on("b48a0a1cd978")
        cloud.turn_off("b48a0a1cd978", channel=1, toggle_after=60)

        # Control a cover
        cloud.cover_open("dc4f2276846a")
        cloud.cover_goto_position("dc4f2276846a", pos=50)

        # Close the session when done
        cloud.close()

    Use as a context manager to close the session automatically::

        with ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="abc123...") as cloud:
            cloud.turn_on("b48a0a1cd978")
    """

    _BASE_PATH = "/v2/devices/api/"

    def __init__(self, server: str, auth_key: str, timeout: float = 10.0):
        self._server = server.rstrip("/")
        self._auth_key = auth_key
        self._timeout = timeout
        self._session: requests.Session | None = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    @property
    def _base_url(self) -> str:
        return f"https://{self._server}{self._BASE_PATH}"

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def close(self) -> None:
        """Close the underlying HTTP session and release all connections."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "ShellyCloud":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"ShellyCloud(server={self._server!r})"

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _post(self, path: str, body: dict) -> Any:
        """POST *body* as JSON to *path* and return the parsed response."""
        url = f"{self._base_url}{path}"
        params = {"auth_key": self._auth_key}
        try:
            resp = self.session.post(url, json=body, params=params, timeout=self._timeout)
        except requests.exceptions.ConnectionError as exc:
            raise ShellyConnectionError(f"Cannot connect to Shelly Cloud ({self._server}): {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ShellyTimeoutError(f"Request to Shelly Cloud timed out after {self._timeout}s") from exc

        if resp.status_code == 401:
            raise ShellyAuthError("Shelly Cloud authentication failed. Check your auth_key.")

        if not resp.ok:
            # All error responses carry an "error" string and optional messages.
            try:
                payload = resp.json()
                error_str = payload.get("error", str(resp.status_code))
                messages = payload.get("data", {}).get("messages", [])
            except Exception:
                error_str = str(resp.status_code)
                messages = [resp.text]
            raise ShellyCloudError(error_str, messages)

        # 200 with no body (successful control calls)
        if not resp.content:
            return {}

        return resp.json()

    # ------------------------------------------------------------------
    # Device state
    # ------------------------------------------------------------------

    def get_devices_state(self, ids: list[str], select: list[str] | None = None, pick: dict | None = None, ) -> list[
        dict]:
        """
        Fetch the state of up to 10 devices in a single request.

        Parameters
        ----------
        ids:
            List of 1–10 device IDs (hex strings).
        select:
            Which sections to include in the response.  Any combination of
            ``"status"`` and ``"settings"``.  When omitted both sections are
            returned if the device supports them.
        pick:
            Restrict which top-level keys to return within each section,
            e.g. ``{"status": ["sys", "switch:0"], "settings": ["ble"]}``.
            Only the listed keys are returned; absent sections or absent
            keys are silently omitted.

        Returns
        -------
        list
            One dict per device containing at minimum ``id``, ``type``,
            ``code``, ``gen``, and ``online``.  ``status`` and/or
            ``settings`` are included according to *select* / *pick*.

        Raises
        ------
        ValueError
            If *ids* is empty or contains more than 10 entries.

        Examples
        --------
        ::

            # Full status and settings for two devices
            states = cloud.get_devices_state(
                ["b48a0a1cd978", "dc4f2276846a"],
                select=["status", "settings"],
            )

            # Only the sys and switch:0 status sub-keys
            states = cloud.get_devices_state(
                ["b48a0a1cd978"],
                select=["status"],
                pick={"status": ["sys", "switch:0"]},
            )
        """
        if not ids:
            raise ValueError("ids must contain at least one device ID.")
        if len(ids) > 10:
            raise ValueError(f"ids may contain at most 10 device IDs; got {len(ids)}.")

        body: dict = {"ids": ids}
        if select is not None:
            body["select"] = select
        if pick is not None:
            body["pick"] = pick

        result = self._post("get", body)
        # The API returns a JSON array directly (not wrapped in a key).
        if isinstance(result, list):
            return result
        # Defensive: if the server ever wraps it, return as-is.
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Single-device switch/relay control
    # ------------------------------------------------------------------

    def set_switch(self, device_id: str, on: bool, channel: int = 0, toggle_after: float | None = None, ) -> None:
        """
        Set the output state of a switch/relay channel.

        Works for all generations of relays and plugs.

        Parameters
        ----------
        device_id:
            Target device ID (hex string).
        on:
            ``True`` = ON, ``False`` = OFF.
        channel:
            Output channel index (default ``0``).
        toggle_after:
            Seconds after which the output automatically reverts to the
            opposite of *on*.

        Raises
        ------
        ShellyCloudError
            On API-level errors such as ``DEVICE_OFFLINE``,
            ``DEVICE_INVALID_CHANNEL``, etc.
        """
        body: dict = {"id": device_id, "channel": channel, "on": on}
        if toggle_after is not None:
            body["toggle_after"] = toggle_after
        self._post("set/switch", body)

    def turn_on(self, device_id: str, channel: int = 0, toggle_after: float | None = None, ) -> None:
        """
        Turn a switch/relay channel ON.

        Parameters
        ----------
        device_id:
            Target device ID.
        channel:
            Output channel index (default ``0``).
        toggle_after:
            Auto-off delay in seconds.
        """
        self.set_switch(device_id, on=True, channel=channel, toggle_after=toggle_after)

    def turn_off(self, device_id: str, channel: int = 0, toggle_after: float | None = None, ) -> None:
        """
        Turn a switch/relay channel OFF.

        Parameters
        ----------
        device_id:
            Target device ID.
        channel:
            Output channel index (default ``0``).
        toggle_after:
            Auto-on delay in seconds.
        """
        self.set_switch(device_id, on=False, channel=channel, toggle_after=toggle_after)

    # ------------------------------------------------------------------
    # Single-device cover/roller control
    # ------------------------------------------------------------------

    def set_cover(self, device_id: str, channel: int = 0, position: str | int | None = None,
            duration: float | None = None, relative: int | None = None, slat_position: int | None = None,
            slat_relative: int | None = None, ) -> None:
        """
        Control a cover/roller channel.

        Works for all generations of rollers and covers.

        Parameters
        ----------
        device_id:
            Target device ID.
        channel:
            Channel index (default ``0``).
        position:
            Target position.  One of:

            * ``"open"`` — move to fully open
            * ``"close"`` — move to fully closed
            * ``"stop"`` — stop immediately
            * integer 0–100 — move to absolute position (0 = open,
              100 = closed); requires prior calibration

            Cannot be combined with *relative*.
        duration:
            Move for this many seconds then stop.  Only valid when
            *position* is ``"open"``, ``"close"``, or ``"stop"``
            (not with a numeric *position*).
        relative:
            Move by a relative amount −100 to +100.
            Cannot be combined with *position*.
        slat_position:
            Target slat angle 0–100 (devices with slat support only).
            Cannot be combined with *slat_relative*.
        slat_relative:
            Relative slat change −100 to +100.
            Cannot be combined with *slat_position*.

        Raises
        ------
        ValueError
            If mutually exclusive parameters are both provided.
        ShellyCloudError
            On API-level errors such as ``DEVICE_OFFLINE``,
            ``DEVICE_INVALID_MODE``, etc.
        """
        if position is not None and relative is not None:
            raise ValueError("'position' and 'relative' are mutually exclusive.")
        if slat_position is not None and slat_relative is not None:
            raise ValueError("'slat_position' and 'slat_relative' are mutually exclusive.")

        body: dict = {"id": device_id, "channel": channel}
        if position is not None:
            body["position"] = position
        if duration is not None:
            body["duration"] = duration
        if relative is not None:
            body["relative"] = relative
        if slat_position is not None:
            body["slatPosition"] = slat_position
        if slat_relative is not None:
            body["slatRelative"] = slat_relative

        self._post("set/cover", body)

    def cover_open(self, device_id: str, channel: int = 0, duration: float | None = None, ) -> None:
        """Open a cover/roller (move to fully open position)."""
        self.set_cover(device_id, channel=channel, position="open", duration=duration)

    def cover_close(self, device_id: str, channel: int = 0, duration: float | None = None, ) -> None:
        """Close a cover/roller (move to fully closed position)."""
        self.set_cover(device_id, channel=channel, position="close", duration=duration)

    def cover_stop(self, device_id: str, channel: int = 0) -> None:
        """Stop a cover/roller motor immediately."""
        self.set_cover(device_id, channel=channel, position="stop")

    def cover_goto_position(self, device_id: str, pos: int, channel: int = 0, ) -> None:
        """
        Move a cover/roller to an absolute position.

        Requires prior calibration on the device.

        Parameters
        ----------
        device_id:
            Target device ID.
        pos:
            Target position 0–100 (0 = fully open, 100 = fully closed).
        channel:
            Channel index (default ``0``).
        """
        self.set_cover(device_id, channel=channel, position=pos)

    # ------------------------------------------------------------------
    # Single-device light control
    # ------------------------------------------------------------------

    def set_light(self, device_id: str, channel: int = 0, on: bool | None = None, toggle_after: float | None = None,
            mode: str | None = None, brightness: int | None = None, temperature: int | None = None,
            red: int | None = None, green: int | None = None, blue: int | None = None, white: int | None = None,
            gain: int | None = None, effect: int | None = None, ) -> None:
        """
        Control a light channel.

        Works for all generations of lights; unsupported parameters (e.g.
        RGB on a dimmer-only device) are ignored by the device.

        Parameters
        ----------
        device_id:
            Target device ID.
        channel:
            Channel index (default ``0``).
        on:
            Power state.  Required when no other parameters are supplied.
        toggle_after:
            Seconds after which the output reverts to the opposite of *on*.
        mode:
            ``"color"`` or ``"white"`` for devices that support mode
            switching (e.g. ShellyRGBW2, ShellyBulb).
        brightness:
            Brightness 0–100 % (white mode and dimmers).
        temperature:
            Colour temperature 2700–7000 K (white mode).
        red, green, blue:
            RGB channel values 0–255 (colour mode).
        white:
            White channel value 0–255 (colour mode with white channel).
        gain:
            Overall brightness multiplier 0–100 (colour mode).
        effect:
            Animated effect index 0–6 (devices that support effects).

        Raises
        ------
        ShellyCloudError
            On API-level errors such as ``DEVICE_OFFLINE``,
            ``DEVICE_INVALID_MODE``, etc.
        """
        body: dict = {"id": device_id, "channel": channel}
        if on is not None:
            body["on"] = on
        if toggle_after is not None:
            body["toggle_after"] = toggle_after
        if mode is not None:
            body["mode"] = mode
        if brightness is not None:
            body["brightness"] = brightness
        if temperature is not None:
            body["temperature"] = temperature
        if red is not None:
            body["red"] = red
        if green is not None:
            body["green"] = green
        if blue is not None:
            body["blue"] = blue
        if white is not None:
            body["white"] = white
        if gain is not None:
            body["gain"] = gain
        if effect is not None:
            body["effect"] = effect

        self._post("set/light", body)

    def light_on(self, device_id: str, channel: int = 0, brightness: int | None = None,
            toggle_after: float | None = None, ) -> None:
        """
        Turn a light ON.

        Parameters
        ----------
        device_id:
            Target device ID.
        channel:
            Channel index (default ``0``).
        brightness:
            Brightness 0–100 %.
        toggle_after:
            Auto-off delay in seconds.
        """
        self.set_light(device_id, channel=channel, on=True, brightness=brightness, toggle_after=toggle_after, )

    def light_off(self, device_id: str, channel: int = 0) -> None:
        """Turn a light OFF."""
        self.set_light(device_id, channel=channel, on=False)

    # ------------------------------------------------------------------
    # Group control
    # ------------------------------------------------------------------

    def set_groups(self, switch: dict | None = None, cover: dict | None = None, light: dict | None = None, ) -> dict:
        """
        Control multiple devices of different types in a single request.

        Each argument is a dict with:

        - ``ids`` — list of ``"<DEVICE_ID>_<CHANNEL>"`` strings.
          The ``_<CHANNEL>`` suffix may be omitted and defaults to ``0``.
        - ``command`` — the command payload (same parameters as the
          corresponding single-device method).

        At least one of *switch*, *cover*, or *light* must be supplied.

        Parameters
        ----------
        switch:
            Group of switch/relay channels.

            ``command`` keys: ``on`` (bool, **required**),
            ``toggle_after`` (float, optional).

            Example::

                {
                    "ids": ["b48a0a1cd978_0", "dc4f2276846a_0"],
                    "command": {"on": True}
                }

        cover:
            Group of cover/roller channels.

            ``command`` keys: ``position`` (``"open"``/``"close"``/``"stop"``/
            int 0–100), ``duration`` (float), ``relative`` (int −100–100),
            ``slatPosition`` (int 0–100), ``slatRelative`` (int −100–100).

            Example::

                {
                    "ids": ["dc4f2276846a_0"],
                    "command": {"position": "open"}
                }

        light:
            Group of light channels.

            ``command`` keys: ``on`` (bool, **required** if no other params),
            ``toggle_after`` (float), ``mode`` (``"color"``/``"white"``),
            ``brightness`` (int 0–100), ``temperature`` (int 2500–7000),
            ``red``/``green``/``blue``/``white`` (int 0–255), ``gain``
            (int 0–100), ``effect`` (int 0–6).

        Returns
        -------
        dict
            Empty dict on full success.  When individual devices fail the
            server still returns HTTP 200 and includes a ``failedCommands``
            key mapping ``"<ID>_<CHANNEL>"`` to an error string::

                {
                    "failedCommands": {
                        "b48a0a1cd978_0": "DEVICE_OFFLINE"
                    }
                }

        Raises
        ------
        ValueError
            If no group is provided.
        ShellyCloudError
            On validation errors or server-side failures.
        """
        if switch is None and cover is None and light is None:
            raise ValueError("Supply at least one of 'switch', 'cover', or 'light'.")

        body: dict = {}
        if switch is not None:
            body["switch"] = switch
        if cover is not None:
            body["cover"] = cover
        if light is not None:
            body["light"] = light

        return self._post("set/groups", body)
