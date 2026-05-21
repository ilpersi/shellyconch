"""
Shelly Gen2+ device interface (Gen2, Gen3, Gen4).

All second-generation and newer Shelly devices expose a **JSON-RPC 2.0** API.
This module communicates exclusively over HTTP using the ``requests`` library.

Authentication: SHA-256 Digest Auth (a subset of RFC 7616).  Supply a
``password`` when creating the instance; authentication is then handled
transparently on every request.

Reference: https://shelly-api-docs.shelly.cloud/gen2/
"""

import itertools
from typing import Any

from .auth import ShellyDigestAuth
from .base import BaseShelly
from .exceptions import ShellyRPCError

# Global counter shared across all instances for request IDs.
_id_counter = itertools.count(1)


class ShellyGen2(BaseShelly):
    """
    Generic interface for all second-generation (and newer) Shelly devices.

    All communication is done through JSON-RPC 2.0 POST requests to the
    ``/rpc`` endpoint.  Convenience wrappers are provided for every
    standard component.

    Parameters
    ----------
    host:
        IP address or hostname of the device.
    port:
        HTTP port (default ``80``).
    timeout:
        Request timeout in seconds (default ``10``).
    password:
        Password for SHA-256 Digest Auth.  Leave ``None`` (default) when
        auth is not enabled on the device.
    """

    def __init__(self, host: str, port: int = 80, timeout: float = 10.0, password: str | None = None, ):
        super().__init__(host, port, timeout)
        self._password = password
        if password:
            self.session.auth = ShellyDigestAuth(password)

    # ------------------------------------------------------------------
    # Core RPC transport
    # ------------------------------------------------------------------

    def call(self, method: str, params: dict | None = None) -> Any:
        """
        Execute a single JSON-RPC 2.0 call and return the ``result`` value.

        Parameters
        ----------
        method:
            Full RPC method name, e.g. ``"Switch.Set"``.
        params:
            Optional parameter dict.

        Raises
        ------
        ShellyRPCError
            If the device returns a JSON-RPC error frame.
        ShellyAuthError
            If authentication fails (HTTP 401).
        ShellyConnectionError
            If the device cannot be reached.
        ShellyTimeoutError
            If the request times out.
        """
        payload: dict = {"id": next(_id_counter), "method": method}
        if params:
            payload["params"] = params
        resp = self._post("/rpc", json=payload)
        if "error" in resp:
            err = resp["error"]
            raise ShellyRPCError(err.get("code", -1), err.get("message", ""))
        return resp.get("result")

    def get_info(self):
        """
        Return basic device information.

        This endpoint is always accessible even when auth is enabled.

        Returns a dict with keys ``name``, ``id``, ``slot``, ``mode``,
        ``gen``, ``fw_id``, ``ver``, ``app``, ``auth_en``, ``auth_domain``,
        ``profile``.
        """
        return self._get("/shelly")

    # ------------------------------------------------------------------
    # Shelly component (device management)
    # ------------------------------------------------------------------

    def get_device_info(self, ident: bool = False) -> dict:
        """
        Return basic device identification.

        This method is always accessible even when auth is enabled because
        the underlying ``/shelly`` HTTP GET is unauthenticated.

        Returns a dict with keys: ``id``, ``mac``, ``model``, ``gen``,
        ``fw_id``, ``ver``, ``app``, ``auth_en``, ``auth_domain``.

        Parameters
        ----------
        ident:
            When ``True``, also returns ``key`` (cloud JWT) and batch info.
        """
        params: dict = {}
        if ident:
            params["ident"] = True
        return self.call("Shelly.GetDeviceInfo", params or None)

    def get_status(self) -> dict:
        """
        Return the live status of all device components.

        The response is a flat dict keyed by component identifiers such as
        ``"switch:0"``, ``"cover:0"``, ``"sys"``, ``"wifi"``, etc.
        """
        return self.call("Shelly.GetStatus")

    def get_config(self) -> dict:
        """Return the full configuration of all device components."""
        return self.call("Shelly.GetConfig")

    def list_methods(self) -> list[str]:
        """Return the list of RPC method names supported by this device."""
        result = self.call("Shelly.ListMethods")
        return result.get("methods", []) if isinstance(result, dict) else result

    def get_components(self, offset: int = 0, include: list[str] | None = None, dynamic_only: bool = False, ) -> dict:
        """
        Return a paginated list of device components.

        Parameters
        ----------
        offset:
            Starting index for pagination.
        include:
            Optional list of component keys to include.
        dynamic_only:
            When ``True``, return only virtual/dynamic components.
        """
        p: dict = {"offset": offset}
        if include:
            p["include"] = include
        if dynamic_only:
            p["dynamic_only"] = True
        return self.call("Shelly.GetComponents", p)

    def reboot(self, delay_ms: int = 500) -> None:
        """
        Reboot the device.

        Parameters
        ----------
        delay_ms:
            Delay in milliseconds before rebooting (minimum 500 ms).
        """
        self.call("Shelly.Reboot", {"delay_ms": max(500, delay_ms)})

    def factory_reset(self) -> None:
        """Perform a factory reset.  All settings are erased."""
        self.call("Shelly.FactoryReset")

    def reset_wifi_config(self) -> None:
        """Erase WiFi credentials and revert to AP mode."""
        self.call("Shelly.ResetWiFiConfig")

    def set_auth(self, password: str | None) -> None:
        """
        Set or remove the device password.

        Parameters
        ----------
        password:
            New password string.  Pass ``None`` to disable authentication.
        """
        import hashlib

        if password is not None:
            device_info = self.get_info()
            realm = device_info.get("auth_domain") or device_info.get("id", "")
            ha1 = hashlib.sha256(f"admin:{realm}:{password}".encode()).hexdigest()
            self.call("Shelly.SetAuth", {"user": "admin", "realm": realm, "ha1": ha1})
            self._password = password
            self.session.auth = ShellyDigestAuth(password)
        else:
            self.call("Shelly.SetAuth", {"user": "admin", "realm": "", "ha1": None})
            self._password = None
            self.session.auth = None

    def check_for_update(self) -> dict:
        """
        Ask the device to query the firmware server for available updates.

        Returns a dict with ``stable`` and ``beta`` sub-dicts containing
        ``version`` and ``build_id``.
        """
        return self.call("Shelly.CheckForUpdate")

    def update_firmware(self, stage: str = "stable", url: str | None = None) -> None:
        """
        Trigger a firmware update.

        Parameters
        ----------
        stage:
            ``"stable"`` (default) or ``"beta"``.
        url:
            Custom firmware URL.  When provided, ``stage`` is ignored.
        """
        if url:
            self.call("Shelly.Update", {"url": url})
        else:
            self.call("Shelly.Update", {"stage": stage})

    def detect_location(self) -> dict:
        """
        Ask the device to auto-detect its location from the public IP.

        Returns ``{"tz": "...", "lat": ..., "lon": ...}``.
        """
        return self.call("Shelly.DetectLocation")

    def list_profiles(self) -> list[str]:
        """Return available profiles (multi-profile devices such as Shelly2PM)."""
        result = self.call("Shelly.ListProfiles")
        return result.get("profiles", []) if isinstance(result, dict) else result

    def set_profile(self, name: str) -> dict:
        """
        Switch the device profile (requires reboot).

        Returns ``{"profile_was": "<previous_profile>"}``.
        """
        return self.call("Shelly.SetProfile", {"name": name})

    # ------------------------------------------------------------------
    # Switch component
    # ------------------------------------------------------------------

    def switch_set(self, switch_id: int, on: bool, toggle_after: float | None = None, ) -> dict:
        """
        Set a switch output.

        Parameters
        ----------
        switch_id:
            Switch instance ID (0-based).
        on:
            ``True`` = ON, ``False`` = OFF.
        toggle_after:
            Auto-revert after this many seconds.

        Returns ``{"was_on": bool}``.
        """
        p: dict = {"id": switch_id, "on": on}
        if toggle_after is not None:
            p["toggle_after"] = toggle_after
        return self.call("Switch.Set", p)

    def switch_toggle(self, switch_id: int) -> dict:
        """Toggle a switch output.  Returns ``{"was_on": bool}``."""
        return self.call("Switch.Toggle", {"id": switch_id})

    def switch_get_status(self, switch_id: int) -> dict:
        """
        Return the live status of a switch.

        Response keys: ``id``, ``source``, ``output`` (bool), ``apower``
        (W), ``voltage`` (V), ``current`` (A), ``aenergy``, ``temperature``.
        """
        return self.call("Switch.GetStatus", {"id": switch_id})

    def switch_get_config(self, switch_id: int) -> dict:
        """Return the persistent configuration of a switch."""
        return self.call("Switch.GetConfig", {"id": switch_id})

    def switch_set_config(self, switch_id: int, config: dict) -> dict:
        """
        Update the persistent configuration of a switch.

        Common config keys
        ------------------
        name : str
        in_mode : str
            ``"momentary"``, ``"follow"``, ``"flip"``, ``"detached"``,
            ``"cycle"``, ``"activate"``.
        initial_state : str
            ``"off"``, ``"on"``, ``"restore_last"``, ``"match_input"``.
        auto_on : bool
        auto_on_delay : float
            Auto-turn-on delay in seconds.
        auto_off : bool
        auto_off_delay : float
            Auto-turn-off delay in seconds.
        power_limit : float
            Overpower threshold in Watts.
        voltage_limit : float
            Overvoltage threshold in Volts.
        current_limit : float
            Overcurrent threshold in Amperes.
        """
        return self.call("Switch.SetConfig", {"id": switch_id, "config": config})

    def switch_reset_counters(self, switch_id: int, counter_types: list[str] | None = None, ) -> dict:
        """
        Reset energy counters for a switch.

        Parameters
        ----------
        counter_types:
            Optional list specifying which counters to reset, e.g.
            ``["aenergy"]``.  Resets all by default.
        """
        p: dict = {"id": switch_id}
        if counter_types:
            p["type"] = counter_types
        return self.call("Switch.ResetCounters", p)

    # ------------------------------------------------------------------
    # Cover component (roller / blind)
    # ------------------------------------------------------------------

    def cover_open(self, cover_id: int, duration: float | None = None) -> None:
        """
        Open a cover (move in the open direction).

        Parameters
        ----------
        cover_id:
            Cover instance ID.
        duration:
            Move for this many seconds then stop (0.1–``maxtime_open``).
        """
        p: dict = {"id": cover_id}
        if duration is not None:
            p["duration"] = duration
        self.call("Cover.Open", p)

    def cover_close(self, cover_id: int, duration: float | None = None) -> None:
        """Close a cover (move in the close direction)."""
        p: dict = {"id": cover_id}
        if duration is not None:
            p["duration"] = duration
        self.call("Cover.Close", p)

    def cover_stop(self, cover_id: int) -> None:
        """Stop the cover motor immediately."""
        self.call("Cover.Stop", {"id": cover_id})

    def cover_goto_position(self, cover_id: int, pos: int | None = None, rel: int | None = None, ) -> None:
        """
        Move the cover to an absolute or relative position.

        Parameters
        ----------
        cover_id:
            Cover instance ID.
        pos:
            Absolute target position 0–100 (0 = open, 100 = closed).
            Mutually exclusive with ``rel``.
        rel:
            Relative position change −100 to +100.
            Mutually exclusive with ``pos``.
        """
        if pos is None and rel is None:
            raise ValueError("Supply either 'pos' or 'rel'.")
        p: dict = {"id": cover_id}
        if pos is not None:
            p["pos"] = pos
        if rel is not None:
            p["rel"] = rel
        self.call("Cover.GoToPosition", p)

    def cover_calibrate(self, cover_id: int) -> None:
        """
        Run the 5-step automatic calibration sequence.

        Required before position control can be used.
        """
        self.call("Cover.Calibrate", {"id": cover_id})

    def cover_get_status(self, cover_id: int) -> dict:
        """
        Return the live status of a cover.

        Response keys: ``id``, ``source``, ``state`` (open/closed/opening/
        closing/stopped/calibrating), ``current_pos``, ``last_direction``,
        ``pos_control``, ``apower``, ``voltage``, ``aenergy``.
        """
        return self.call("Cover.GetStatus", {"id": cover_id})

    def cover_get_config(self, cover_id: int) -> dict:
        """Return the persistent configuration of a cover."""
        return self.call("Cover.GetConfig", {"id": cover_id})

    def cover_set_config(self, cover_id: int, config: dict) -> dict:
        """
        Update the persistent configuration of a cover.

        Common config keys
        ------------------
        name : str
        in_mode : str
            ``"single"``, ``"dual"``, ``"detached"``.
        initial_state : str
            ``"open"``, ``"closed"``, ``"stopped"``.
        power_limit : float
        auto_on, auto_off : bool
        auto_on_delay, auto_off_delay : float
        """
        return self.call("Cover.SetConfig", {"id": cover_id, "config": config})

    def cover_reset_counters(self, cover_id: int, counter_types: list[str] | None = None, ) -> dict:
        """Reset energy counters for a cover channel."""
        p: dict = {"id": cover_id}
        if counter_types:
            p["type"] = counter_types
        return self.call("Cover.ResetCounters", p)

    # ------------------------------------------------------------------
    # Light component (dimmable lights)
    # ------------------------------------------------------------------

    def light_set(self, light_id: int, on: bool | None = None, brightness: int | None = None,
                  transition_duration: float | None = None, toggle_after: float | None = None, ) -> dict:
        """
        Set a light channel state and/or brightness.

        Parameters
        ----------
        light_id:
            Light instance ID.
        on:
            ``True`` = ON, ``False`` = OFF.  Omit to change only brightness.
        brightness:
            Brightness 0–100 %.
        transition_duration:
            Fade duration in seconds.
        toggle_after:
            Auto-revert timer in seconds.

        Returns ``{"was_on": bool}``.
        """
        p: dict = {"id": light_id}
        if on is not None:
            p["on"] = on
        if brightness is not None:
            p["brightness"] = brightness
        if transition_duration is not None:
            p["transition_duration"] = transition_duration
        if toggle_after is not None:
            p["toggle_after"] = toggle_after
        return self.call("Light.Set", p)

    def light_toggle(self, light_id: int) -> dict:
        """Toggle a light channel.  Returns ``{"was_on": bool}``."""
        return self.call("Light.Toggle", {"id": light_id})

    def light_get_status(self, light_id: int) -> dict:
        """
        Return the live status of a light channel.

        Response keys: ``id``, ``source``, ``output``, ``brightness``,
        ``timer_started_at``, ``timer_duration``, ``transition``.
        """
        return self.call("Light.GetStatus", {"id": light_id})

    def light_get_config(self, light_id: int) -> dict:
        """Return the persistent configuration of a light channel."""
        return self.call("Light.GetConfig", {"id": light_id})

    def light_set_config(self, light_id: int, config: dict) -> dict:
        """
        Update the persistent configuration of a light channel.

        Common config keys
        ------------------
        name : str
        initial_state : str
            ``"off"``, ``"on"``, ``"restore_last"``.
        auto_on, auto_off : bool
        auto_on_delay, auto_off_delay : float
        transition_duration : float
            Default transition time in seconds.
        min_brightness_on_toggle : int
        night_mode : dict
            ``{"enable": bool, "brightness": int,
               "active_between": ["HH:MM", "HH:MM"]}``
        """
        return self.call("Light.SetConfig", {"id": light_id, "config": config})

    def light_dim_up(self, light_id: int, rate: int = 3) -> None:
        """
        Start continuously dimming UP.

        Parameters
        ----------
        rate:
            Dimming speed 1–5 (default 3).
        """
        self.call("Light.DimUp", {"id": light_id, "rate": rate})

    def light_dim_down(self, light_id: int, rate: int = 3) -> None:
        """Start continuously dimming DOWN."""
        self.call("Light.DimDown", {"id": light_id, "rate": rate})

    def light_dim_stop(self, light_id: int) -> None:
        """Stop an in-progress continuous dim operation."""
        self.call("Light.DimStop", {"id": light_id})

    def light_reset_counters(self, light_id: int, counter_types: list[str] | None = None, ) -> dict:
        """Reset energy counters for a light channel."""
        p: dict = {"id": light_id}
        if counter_types:
            p["type"] = counter_types
        return self.call("Light.ResetCounters", p)

    # ------------------------------------------------------------------
    # RGBW component
    # ------------------------------------------------------------------

    def rgbw_set(self, rgbw_id: int, on: bool | None = None, brightness: int | None = None,
                 rgb: list[int] | None = None, white: int | None = None, transition_duration: float | None = None,
                 toggle_after: float | None = None, ) -> dict:
        """
        Set the state of an RGBW light.

        Parameters
        ----------
        rgbw_id:
            RGBW instance ID.
        on:
            Power state.
        brightness:
            Overall brightness 0–100 %.
        rgb:
            ``[R, G, B]`` colour values, each 0–255.
        white:
            White channel 0–255.
        transition_duration:
            Fade duration in seconds.
        toggle_after:
            Auto-revert timer in seconds.

        Returns ``{"was_on": bool}``.
        """
        p: dict = {"id": rgbw_id}
        if on is not None:
            p["on"] = on
        if brightness is not None:
            p["brightness"] = brightness
        if rgb is not None:
            p["rgb"] = rgb
        if white is not None:
            p["white"] = white
        if transition_duration is not None:
            p["transition_duration"] = transition_duration
        if toggle_after is not None:
            p["toggle_after"] = toggle_after
        return self.call("RGBW.Set", p)

    def rgbw_toggle(self, rgbw_id: int) -> dict:
        """Toggle an RGBW light.  Returns ``{"was_on": bool}``."""
        return self.call("RGBW.Toggle", {"id": rgbw_id})

    def rgbw_get_status(self, rgbw_id: int) -> dict:
        """Return the live status of an RGBW light."""
        return self.call("RGBW.GetStatus", {"id": rgbw_id})

    def rgbw_get_config(self, rgbw_id: int) -> dict:
        """Return the persistent configuration of an RGBW light."""
        return self.call("RGBW.GetConfig", {"id": rgbw_id})

    def rgbw_set_config(self, rgbw_id: int, config: dict) -> dict:
        """Update the persistent configuration of an RGBW light."""
        return self.call("RGBW.SetConfig", {"id": rgbw_id, "config": config})

    # ------------------------------------------------------------------
    # Input component
    # ------------------------------------------------------------------

    def input_get_status(self, input_id: int) -> dict:
        """
        Return the live status of an input channel.

        Response depends on the configured input type:

        * ``switch`` / ``button``: ``state`` (bool or null)
        * ``analog``: ``percent`` (0–100)
        * ``count``: ``counts.total``, ``counts.by_minute``, ``freq``
        """
        return self.call("Input.GetStatus", {"id": input_id})

    def input_get_config(self, input_id: int) -> dict:
        """Return the persistent configuration of an input channel."""
        return self.call("Input.GetConfig", {"id": input_id})

    def input_set_config(self, input_id: int, config: dict) -> dict:
        """
        Update the persistent configuration of an input channel.

        Common config keys
        ------------------
        name : str
        type : str
            ``"switch"``, ``"button"``, ``"analog"``, ``"count"``.
        enable : bool
        invert : bool
            Invert the logical state of a switch/button input.
        """
        return self.call("Input.SetConfig", {"id": input_id, "config": config})

    def input_trigger(self, input_id: int, event_type: str) -> None:
        """
        Simulate a button event (button-type inputs only).

        Parameters
        ----------
        event_type:
            One of: ``"btn_down"``, ``"btn_up"``, ``"single_push"``,
            ``"double_push"``, ``"triple_push"``, ``"long_push"``.
        """
        self.call("Input.Trigger", {"id": input_id, "event_type": event_type})

    def input_reset_counters(self, input_id: int, counter_types: list[str] | None = None, ) -> dict:
        """Reset pulse counters for a count-type input channel."""
        p: dict = {"id": input_id}
        if counter_types:
            p["type"] = counter_types
        return self.call("Input.ResetCounters", p)

    # ------------------------------------------------------------------
    # Temperature sensor component
    # ------------------------------------------------------------------

    def temperature_get_status(self, sensor_id: int) -> dict:
        """
        Return the live temperature reading.

        Response keys: ``tC``, ``tF`` (both nullable on read error),
        ``errors``.
        """
        return self.call("Temperature.GetStatus", {"id": sensor_id})

    def temperature_get_config(self, sensor_id: int) -> dict:
        """Return the persistent configuration of a temperature sensor."""
        return self.call("Temperature.GetConfig", {"id": sensor_id})

    def temperature_set_config(self, sensor_id: int, config: dict) -> dict:
        """
        Update temperature sensor configuration.

        Config keys: ``name``, ``report_thr_C`` (report threshold),
        ``offset_C`` (calibration offset).
        """
        return self.call("Temperature.SetConfig", {"id": sensor_id, "config": config})

    # ------------------------------------------------------------------
    # Humidity sensor component
    # ------------------------------------------------------------------

    def humidity_get_status(self, sensor_id: int) -> dict:
        """
        Return the live relative-humidity reading.

        Response keys: ``rh`` (nullable), ``errors``.
        """
        return self.call("Humidity.GetStatus", {"id": sensor_id})

    def humidity_get_config(self, sensor_id: int) -> dict:
        """Return the persistent configuration of a humidity sensor."""
        return self.call("Humidity.GetConfig", {"id": sensor_id})

    def humidity_set_config(self, sensor_id: int, config: dict) -> dict:
        """
        Update humidity sensor configuration.

        Config keys: ``name``, ``report_thr`` (%), ``offset`` (%).
        """
        return self.call("Humidity.SetConfig", {"id": sensor_id, "config": config})

    # ------------------------------------------------------------------
    # Voltmeter component
    # ------------------------------------------------------------------

    def voltmeter_get_status(self, voltmeter_id: int) -> dict:
        """Return the live voltage reading (``voltage``, ``xvoltage``)."""
        return self.call("Voltmeter.GetStatus", {"id": voltmeter_id})

    def voltmeter_get_config(self, voltmeter_id: int) -> dict:
        """Return the persistent configuration of a voltmeter."""
        return self.call("Voltmeter.GetConfig", {"id": voltmeter_id})

    def voltmeter_set_config(self, voltmeter_id: int, config: dict) -> dict:
        """Update voltmeter configuration."""
        return self.call("Voltmeter.SetConfig", {"id": voltmeter_id, "config": config})

    # ------------------------------------------------------------------
    # Smoke sensor component
    # ------------------------------------------------------------------

    def smoke_get_status(self, smoke_id: int) -> dict:
        """Return the live smoke sensor state (``alarm``, ``mute``)."""
        return self.call("Smoke.GetStatus", {"id": smoke_id})

    def smoke_mute(self, smoke_id: int) -> None:
        """Silence the active smoke alarm buzzer."""
        self.call("Smoke.Mute", {"id": smoke_id})

    def smoke_get_config(self, smoke_id: int) -> dict:
        """Return the persistent configuration of a smoke sensor."""
        return self.call("Smoke.GetConfig", {"id": smoke_id})

    def smoke_set_config(self, smoke_id: int, config: dict) -> dict:
        """Update smoke sensor configuration."""
        return self.call("Smoke.SetConfig", {"id": smoke_id, "config": config})

    # ------------------------------------------------------------------
    # DevicePower (battery status)
    # ------------------------------------------------------------------

    def device_power_get_status(self, power_id: int = 0) -> dict:
        """
        Return battery and external power status.

        Response keys: ``battery.V``, ``battery.percent``,
        ``external.present``.
        """
        return self.call("DevicePower.GetStatus", {"id": power_id})

    # ------------------------------------------------------------------
    # PM1 component (single-phase power meter)
    # ------------------------------------------------------------------

    def pm1_get_status(self, pm1_id: int) -> dict:
        """
        Return live readings from a single-phase power meter.

        Response keys: ``voltage``, ``current``, ``apower``, ``freq``,
        ``pf``, ``aenergy``, ``ret_aenergy``.
        """
        return self.call("PM1.GetStatus", {"id": pm1_id})

    def pm1_get_config(self, pm1_id: int) -> dict:
        """Return the persistent configuration of a PM1 meter."""
        return self.call("PM1.GetConfig", {"id": pm1_id})

    def pm1_set_config(self, pm1_id: int, config: dict) -> dict:
        """Update PM1 meter configuration."""
        return self.call("PM1.SetConfig", {"id": pm1_id, "config": config})

    def pm1_reset_counters(self, pm1_id: int, counter_types: list[str] | None = None) -> dict:
        """Reset energy counters for a PM1 meter."""
        p: dict = {"id": pm1_id}
        if counter_types:
            p["type"] = counter_types
        return self.call("PM1.ResetCounters", p)

    # ------------------------------------------------------------------
    # EM component (3-phase energy meter — ShellyPro3EM)
    # ------------------------------------------------------------------

    def em_get_status(self, em_id: int = 0) -> dict:
        """Return live three-phase energy meter readings."""
        return self.call("EM.GetStatus", {"id": em_id})

    def em_get_config(self, em_id: int = 0) -> dict:
        """Return the persistent configuration of an EM meter."""
        return self.call("EM.GetConfig", {"id": em_id})

    def em_set_config(self, em_id: int, config: dict) -> dict:
        """Update EM meter configuration."""
        return self.call("EM.SetConfig", {"id": em_id, "config": config})

    # ------------------------------------------------------------------
    # EM1 component (single-phase energy meter — ShellyProEM)
    # ------------------------------------------------------------------

    def em1_get_status(self, em1_id: int) -> dict:
        """Return live single-phase energy meter readings."""
        return self.call("EM1.GetStatus", {"id": em1_id})

    def em1_get_config(self, em1_id: int) -> dict:
        """Return the persistent configuration of an EM1 meter."""
        return self.call("EM1.GetConfig", {"id": em1_id})

    def em1_set_config(self, em1_id: int, config: dict) -> dict:
        """Update EM1 meter configuration."""
        return self.call("EM1.SetConfig", {"id": em1_id, "config": config})

    # ------------------------------------------------------------------
    # EMData component (energy history)
    # ------------------------------------------------------------------

    def emdata_get_data(self, emdata_id: int, ts: int | None = None, end_ts: int | None = None) -> dict:
        """
        Retrieve stored energy records.

        Parameters
        ----------
        emdata_id:
            EMData instance ID.
        ts:
            Start Unix timestamp for the query window.
        end_ts:
            End Unix timestamp for the query window.
        """
        p: dict = {"id": emdata_id}
        if ts is not None:
            p["ts"] = ts
        if end_ts is not None:
            p["end_ts"] = end_ts
        return self.call("EMData.GetData", p)

    def emdata_reset_counters(self, emdata_id: int) -> dict:
        """Reset EMData energy counters."""
        return self.call("EMData.ResetCounters", {"id": emdata_id})

    def emdata_delete_all(self, emdata_id: int) -> None:
        """Delete all stored energy records."""
        self.call("EMData.DeleteAllData", {"id": emdata_id})

    # ------------------------------------------------------------------
    # System component
    # ------------------------------------------------------------------

    def sys_get_status(self) -> dict:
        """
        Return system status.

        Response keys: ``mac``, ``restart_required``, ``time``,
        ``unixtime``, ``uptime``, ``ram_size``, ``ram_free``,
        ``fs_size``, ``fs_free``, ``cfg_rev``, ``available_updates``.
        """
        return self.call("Sys.GetStatus")

    def sys_get_config(self) -> dict:
        """Return system configuration."""
        return self.call("Sys.GetConfig")

    def sys_set_config(self, config: dict) -> dict:
        """
        Update system configuration.

        Common config keys
        ------------------
        device.name : str
        device.eco_mode : bool
        device.discoverable : bool
        location.tz : str
        location.lat, location.lon : float
        sntp.server : str
        """
        return self.call("Sys.SetConfig", {"config": config})

    def sys_set_time(self, unixtime: int) -> None:
        """Manually set the system clock (Unix timestamp)."""
        self.call("Sys.SetTime", {"unixtime": unixtime})

    # ------------------------------------------------------------------
    # WiFi component
    # ------------------------------------------------------------------

    def wifi_get_status(self) -> dict:
        """
        Return WiFi connection status.

        Response keys: ``sta_ip``, ``status``, ``ssid``, ``bssid``,
        ``rssi``, ``ap_client_count``.
        """
        return self.call("Wifi.GetStatus")

    def wifi_get_config(self) -> dict:
        """Return WiFi configuration (AP, STA, STA1, roam settings)."""
        return self.call("Wifi.GetConfig")

    def wifi_set_config(self, config: dict) -> dict:
        """
        Update WiFi configuration.

        Config structure mirrors the result of :meth:`wifi_get_config`.
        Set ``config.sta.ssid`` and ``config.sta.pass`` to configure the
        primary network; ``config.sta1`` for the fallback network.
        """
        return self.call("Wifi.SetConfig", {"config": config})

    def wifi_scan(self) -> dict:
        """
        Scan for available WiFi networks.

        Returns a ``results`` list with ``ssid``, ``bssid``, ``auth``,
        ``channel``, and ``rssi`` for each detected network.
        """
        return self.call("Wifi.Scan")

    def wifi_list_ap_clients(self) -> dict:
        """
        List clients connected to the device's AP (if active).

        Returns ``ts`` and ``ap_clients`` list with ``mac``, ``ip``,
        ``ip_static``, ``mport``, and ``since``.
        """
        return self.call("WiFi.ListAPClients")

    # ------------------------------------------------------------------
    # Cloud component
    # ------------------------------------------------------------------

    def cloud_get_status(self) -> dict:
        """Return ``{"connected": bool}``."""
        return self.call("Cloud.GetStatus")

    def cloud_get_config(self) -> dict:
        """Return cloud connectivity configuration."""
        return self.call("Cloud.GetConfig")

    def cloud_set_config(self, enable: bool, server: str | None = None) -> dict:
        """Enable or disable Shelly Cloud connectivity."""
        cfg: dict = {"enable": enable}
        if server is not None:
            cfg["server"] = server
        return self.call("Cloud.SetConfig", {"config": cfg})

    # ------------------------------------------------------------------
    # MQTT component
    # ------------------------------------------------------------------

    def mqtt_get_status(self) -> dict:
        """Return ``{"connected": bool}``."""
        return self.call("Mqtt.GetStatus")

    def mqtt_get_config(self) -> dict:
        """Return MQTT broker configuration."""
        return self.call("Mqtt.GetConfig")

    def mqtt_set_config(self, config: dict) -> dict:
        """
        Update MQTT configuration.

        Common config keys
        ------------------
        enable : bool
        server : str
            ``"host:port"``.
        client_id : str
        user, pass : str
        topic_prefix : str
        rpc_ntf : bool
            Publish RPC notifications (default ``True``).
        status_ntf : bool
            Publish full status updates (default ``False``).
        ssl_ca : str
            ``null`` (plain), ``"*"`` (no TLS validation), ``"user_ca.pem"``,
            or ``"ca.pem"``.
        enable_control : bool
            Accept control commands via MQTT (default ``True``).
        """
        return self.call("Mqtt.SetConfig", {"config": config})

    # ------------------------------------------------------------------
    # Outbound WebSocket component
    # ------------------------------------------------------------------

    def ws_get_status(self) -> dict:
        """Return ``{"connected": bool}``."""
        return self.call("Ws.GetStatus")

    def ws_get_config(self) -> dict:
        """Return outbound WebSocket configuration."""
        return self.call("Ws.GetConfig")

    def ws_set_config(self, enable: bool, server: str | None = None, ssl_ca: str | None = None) -> dict:
        """
        Configure the outbound WebSocket connection.

        Parameters
        ----------
        enable:
            Activate the connection.
        server:
            WebSocket URL (prefix with ``wss://`` for TLS).
        ssl_ca:
            TLS option (see :meth:`mqtt_set_config`).
        """
        cfg: dict = {"enable": enable}
        if server is not None:
            cfg["server"] = server
        if ssl_ca is not None:
            cfg["ssl_ca"] = ssl_ca
        return self.call("Ws.SetConfig", {"config": cfg})

    # ------------------------------------------------------------------
    # BLE component
    # ------------------------------------------------------------------

    def ble_get_status(self) -> dict:
        """Return BLE status."""
        return self.call("BLE.GetStatus")

    def ble_get_config(self) -> dict:
        """Return BLE configuration."""
        return self.call("BLE.GetConfig")

    def ble_set_config(self, enable: bool, rpc_enable: bool = False, ) -> dict:
        """
        Update BLE configuration.

        Parameters
        ----------
        enable:
            Activate the BLE radio.
        rpc_enable:
            Enable the BLE RPC channel (allows control over Bluetooth).
        """
        return self.call("BLE.SetConfig", {"config": {"enable": enable, "rpc": {"enable": rpc_enable}}}, )

    # ------------------------------------------------------------------
    # Schedule service
    # ------------------------------------------------------------------

    def schedule_list(self) -> list[dict]:
        """
        Return all scheduled jobs.

        Each job has: ``id``, ``enable``, ``timespec`` (cron string),
        ``calls`` (list of RPC call objects).
        """
        result = self.call("Schedule.List")
        return result.get("jobs", []) if isinstance(result, dict) else result

    def schedule_create(self, timespec: str, calls: list[dict], enable: bool = True, ) -> dict:
        """
        Create a new scheduled job.

        Parameters
        ----------
        timespec:
            Cron-style time specification with seconds field:
            ``"<sec> <min> <hour> <dom> <month> <dow>"``.
            Day-of-week uses ``SUN``/``MON``/.../``SAT``.
            Example: ``"0 30 7 * * MON,TUE,WED,THU,FRI"`` (every weekday
            at 07:30:00).
        calls:
            List of up to 5 RPC calls to execute.  Each element is a dict
            with ``method`` and optional ``params`` keys, e.g.:
            ``[{"method": "Switch.Set", "params": {"id": 0, "on": true}}]``.
        enable:
            Activate the schedule immediately (default ``True``).

        Returns ``{"id": <job_id>, "rev": <config_revision>}``.
        """
        return self.call("Schedule.Create", {"enable": enable, "timespec": timespec, "calls": calls}, )

    def schedule_update(self, job_id: int, **fields: Any) -> dict:
        """
        Update an existing scheduled job.

        Pass ``enable``, ``timespec``, and/or ``calls`` as keyword
        arguments.

        Returns ``{"id": <job_id>, "rev": <config_revision>}``.
        """
        return self.call("Schedule.Update", {"id": job_id, **fields})

    def schedule_delete(self, job_id: int) -> dict:
        """Delete a scheduled job by ID."""
        return self.call("Schedule.Delete", {"id": job_id})

    def schedule_delete_all(self) -> dict:
        """Delete all scheduled jobs."""
        return self.call("Schedule.DeleteAll")

    # ------------------------------------------------------------------
    # Webhook service
    # ------------------------------------------------------------------

    def webhook_list(self) -> list[dict]:
        """
        Return all configured webhooks.

        Each webhook has: ``id``, ``cid``, ``enable``, ``event``,
        ``name``, ``urls``, ``condition``, ``repeat_period``,
        ``active_between``.
        """
        result = self.call("Webhook.List")
        return result.get("hooks", []) if isinstance(result, dict) else result

    def webhook_list_supported(self) -> dict:
        """
        Return all events that can trigger a webhook on this device.

        Useful for discovering which event names to use with
        :meth:`webhook_create`.
        """
        return self.call("Webhook.ListSupported")

    def webhook_create(self, event: str, cid: int, urls: list[str], enable: bool = True, name: str | None = None,
                       condition: str | None = None, repeat_period: int | None = None,
                       active_between: list[str] | None = None, ssl_ca: str | None = None, ) -> dict:
        """
        Create a URL callback webhook.

        Parameters
        ----------
        event:
            Trigger event name, e.g. ``"switch.on"``, ``"switch.off"``,
            ``"cover.open"``, ``"input.button_push"``.
        cid:
            Component instance ID (e.g. ``0`` for ``switch:0``).
        urls:
            List of 1–5 URLs to call (max 300 chars each).
            URLs may include ``${status["switch:0"].output}``-style tokens.
        enable:
            Activate immediately (default ``True``).
        name:
            Optional human-readable label.
        condition:
            JavaScript boolean expression evaluated before firing.
        repeat_period:
            Minimum seconds between fires; negative = fire once only.
        active_between:
            Time window ``["HH:MM", "HH:MM"]`` during which the webhook
            is active.
        ssl_ca:
            TLS option for HTTPS targets.

        Returns ``{"id": <webhook_id>, "rev": <config_revision>}``.
        """
        p: dict = {"event": event, "cid": cid, "urls": urls, "enable": enable, }
        if name is not None:
            p["name"] = name
        if condition is not None:
            p["condition"] = condition
        if repeat_period is not None:
            p["repeat_period"] = repeat_period
        if active_between is not None:
            p["active_between"] = active_between
        if ssl_ca is not None:
            p["ssl_ca"] = ssl_ca
        return self.call("Webhook.Create", p)

    def webhook_update(self, webhook_id: int, **fields: Any) -> dict:
        """
        Update an existing webhook.

        Pass any combination of ``event``, ``cid``, ``urls``, ``enable``,
        ``name``, ``condition``, ``repeat_period``, ``active_between`` as
        keyword arguments.

        Returns ``{"id": <webhook_id>, "rev": <config_revision>}``.
        """
        return self.call("Webhook.Update", {"id": webhook_id, **fields})

    def webhook_delete(self, webhook_id: int) -> dict:
        """Delete a webhook by ID."""
        return self.call("Webhook.Delete", {"id": webhook_id})

    def webhook_delete_all(self) -> dict:
        """Delete all webhooks."""
        return self.call("Webhook.DeleteAll")

    # ------------------------------------------------------------------
    # KVS (key-value store)
    # ------------------------------------------------------------------

    def kvs_set(self, key: str, value: Any, etag: str | None = None) -> dict:
        """
        Store a value in the device's key-value store.

        Parameters
        ----------
        key:
            Key name (max 42 chars).
        value:
            Value to store (max 253 chars when serialised to string).
        etag:
            If provided, the operation will fail unless the stored etag
            matches (optimistic concurrency).

        Returns ``{"etag": str, "rev": int}``.
        """
        p: dict = {"key": key, "value": value}
        if etag is not None:
            p["etag"] = etag
        return self.call("KVS.Set", p)

    def kvs_get(self, key: str) -> dict:
        """Retrieve a value by key.  Returns ``{"etag": str, "value": any}``."""
        return self.call("KVS.Get", {"key": key})

    def kvs_get_many(self, match: str = "*", offset: int = 0) -> dict:
        """
        Retrieve multiple values using a glob pattern.

        Parameters
        ----------
        match:
            Glob pattern; ``*`` matches any chars, ``?`` matches one char.
        offset:
            Pagination offset.

        Returns ``{"items": {key: {etag, value}}, "offset": int, "total": int}``.
        """
        return self.call("KVS.GetMany", {"match": match, "offset": offset})

    def kvs_list(self, match: str = "*") -> dict:
        """
        List keys matching a glob pattern.

        Returns ``{"keys": {key: {etag}}, "rev": int}``.
        """
        return self.call("KVS.List", {"match": match})

    def kvs_delete(self, key: str, etag: str | None = None) -> dict:
        """Delete a key from the store.  Returns ``{"rev": int}``."""
        p: dict = {"key": key}
        if etag is not None:
            p["etag"] = etag
        return self.call("KVS.Delete", p)

    # ------------------------------------------------------------------
    # Script component
    # ------------------------------------------------------------------

    def script_list(self) -> list[dict]:
        """
        Return all scripts on the device.

        Each entry has: ``id``, ``name``, ``enable``, ``running``.
        """
        result = self.call("Script.List")
        return result.get("scripts", []) if isinstance(result, dict) else result

    def script_create(self, name: str | None = None) -> dict:
        """Create a new (empty) script slot.  Returns ``{"id": int}``."""
        p: dict = {}
        if name:
            p["name"] = name
        return self.call("Script.Create", p or None)

    def script_delete(self, script_id: int) -> None:
        """Delete a script by ID."""
        self.call("Script.Delete", {"id": script_id})

    def script_put_code(self, script_id: int, code: str, append: bool = False) -> dict:
        """
        Upload JavaScript code to a script slot.

        Parameters
        ----------
        script_id:
            Script instance ID.
        code:
            JavaScript source code.
        append:
            When ``True``, append to existing code; otherwise replace.

        Returns ``{"len": int}`` (total stored bytes).
        """
        return self.call("Script.PutCode", {"id": script_id, "code": code, "append": append})

    def script_get_code(self, script_id: int, offset: int = 0, length: int = 1024) -> dict:
        """
        Download script source code.

        Returns ``{"data": str, "left": int}`` (remaining bytes after the
        returned chunk).
        """
        return self.call("Script.GetCode", {"id": script_id, "offset": offset, "len": length})

    def script_start(self, script_id: int) -> dict:
        """Start a script.  Returns ``{"was_running": bool}``."""
        return self.call("Script.Start", {"id": script_id})

    def script_stop(self, script_id: int) -> dict:
        """Stop a running script.  Returns ``{"was_running": bool}``."""
        return self.call("Script.Stop", {"id": script_id})

    def script_get_status(self, script_id: int) -> dict:
        """
        Return the runtime status of a script.

        Response keys: ``running``, ``mem_used``, ``mem_peak``,
        ``mem_free``, ``errors``.
        """
        return self.call("Script.GetStatus", {"id": script_id})

    def script_get_config(self, script_id: int) -> dict:
        """Return the persistent configuration of a script."""
        return self.call("Script.GetConfig", {"id": script_id})

    def script_set_config(self, script_id: int, config: dict) -> dict:
        """
        Update script configuration.

        Config keys: ``name`` (str), ``enable`` (bool, auto-start on boot).
        """
        return self.call("Script.SetConfig", {"id": script_id, "config": config})

    def script_eval(self, script_id: int, code: str) -> dict:
        """
        Evaluate a JavaScript expression in the context of a running script.

        Returns ``{"result": str}``.
        """
        return self.call("Script.Eval", {"id": script_id, "code": code})

    # ------------------------------------------------------------------
    # HTTP outbound calls (from device)
    # ------------------------------------------------------------------

    def http_get(self, url: str, timeout: float = 15.0, ssl_ca: str | None = None) -> dict:
        """
        Instruct the device to perform an outbound HTTP GET.

        Returns ``{"code": int, "message": str, "headers": dict, "body": str}``.
        """
        p: dict = {"url": url, "timeout": timeout}
        if ssl_ca is not None:
            p["ssl_ca"] = ssl_ca
        return self.call("HTTP.GET", p)

    def http_post(self, url: str, body: str = "", content_type: str = "application/x-www-form-urlencoded",
                  timeout: float = 15.0, ssl_ca: str | None = None, ) -> dict:
        """
        Instruct the device to perform an outbound HTTP POST.

        Returns the same structure as :meth:`http_get`.
        """
        p: dict = {"url": url, "body": body, "content_type": content_type, "timeout": timeout, }
        if ssl_ca is not None:
            p["ssl_ca"] = ssl_ca
        return self.call("HTTP.POST", p)

    # ------------------------------------------------------------------
    # Matter component (Gen4 / Gen3)
    # ------------------------------------------------------------------

    def matter_get_status(self) -> dict:
        """Return Matter commissioning status (``num_fabrics``, ``commissionable``)."""
        return self.call("Matter.GetStatus")

    def matter_get_config(self) -> dict:
        """Return Matter configuration."""
        return self.call("Matter.GetConfig")

    def matter_set_config(self, enable: bool) -> dict:
        """Enable or disable the Matter protocol stack."""
        return self.call("Matter.SetConfig", {"config": {"enable": enable}})

    def matter_get_setup_code(self) -> dict:
        """
        Return the Matter pairing codes.

        Returns ``{"qr_code": str, "manual_code": str}``.
        """
        return self.call("Matter.GetSetupCode")
