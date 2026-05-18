"""
Generation-agnostic Shelly device wrapper.

:class:`ShellyDevice` composes either a :class:`~shelly.gen1.ShellyGen1` or a
:class:`~shelly.gen2.ShellyGen2` instance and exposes a unified API that works
identically regardless of device generation.

For generation-specific features (scripts, KVS, webhooks, TRV, gas sensors,
etc.) use the :attr:`ShellyDevice.underlying` property to access the typed
instance directly.
"""

from typing import Any

import requests

from .exceptions import ShellyConnectionError
from .gen1 import ShellyGen1
from .gen2 import ShellyGen2
from .models import GEN1_MODELS


class ShellyDevice:
    """
    Generation-agnostic wrapper for Shelly devices.

    Wraps a :class:`~shelly.gen1.ShellyGen1` or
    :class:`~shelly.gen2.ShellyGen2` instance and provides a unified API
    covering relay/switch, cover, light, firmware, WiFi, cloud, and auth
    operations that are common to all generations.

    Parameters
    ----------
    device:
        An already-constructed typed device instance to wrap.

    Examples
    --------
    Auto-detect generation and connect::

        device = ShellyDevice.connect("192.168.1.100", password="secret")
        device.turn_on(0)

    Wrap a typed instance obtained from discovery::

        for d in discover_devices(timeout=10):
            wrapped = ShellyDevice(d)
            print(wrapped.get_info())
    """

    def __init__(self, device: ShellyGen1 | ShellyGen2, generation: int | None = None) -> None:
        self._device = device
        self._generation: int | None = generation

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def connect(cls, host: str, port: int = 80, password: str | None = None, gen1_password: str | None = None,
            gen1_username: str = "admin", timeout: float = 10.0, ) -> "ShellyDevice":
        """
        Probe a device, detect its generation, and return a
        :class:`ShellyDevice` wrapping the appropriate typed instance.

        Parameters
        ----------
        host:
            IP address or hostname.
        port:
            HTTP port (default ``80``).
        password:
            Password for Gen2+ SHA-256 Digest Auth.
        gen1_password:
            Password for Gen1 HTTP Basic Auth.  Falls back to *password*
            when ``None``.
        gen1_username:
            Gen1 Basic Auth username (default ``"admin"``).
        timeout:
            Request timeout in seconds (default ``10``).

        Raises
        ------
        ShellyConnectionError
            If the device cannot be reached, times out, or does not respond
            as a Shelly device.
        """
        _gen1_pass = gen1_password if gen1_password is not None else password
        url = f"http://{host}:{port}/shelly"
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            info = resp.json()
        except requests.exceptions.ConnectionError as exc:
            raise ShellyConnectionError(f"Cannot connect to {host}:{port}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ShellyConnectionError(f"Probe of {host}:{port} timed out after {timeout}s") from exc
        except Exception as exc:
            raise ShellyConnectionError(f"Probe of {host}:{port} failed: {exc}") from exc

        if "mac" not in info:
            raise ShellyConnectionError(f"{host}:{port} did not respond as a Shelly device "
                                        f"(/shelly response missing 'mac')")

        gen = info.get("gen", 1)

        if gen == 1:
            device: ShellyGen1 | ShellyGen2 = ShellyGen1(host=host, port=port, timeout=timeout, username=gen1_username,
                password=_gen1_pass, )
        else:
            device = ShellyGen2(host=host, port=port, timeout=timeout, password=password, )

        instance = cls(device)
        instance._generation = gen
        return instance

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def underlying(self) -> ShellyGen1 | ShellyGen2:
        """The wrapped typed device instance (``ShellyGen1`` or ``ShellyGen2``)."""
        return self._device

    @property
    def generation(self) -> int:
        """
        The device generation number (``1`` for Gen1; ``2``, ``3``, or ``4``
        for Gen2+).

        For devices obtained via :meth:`connect` this is read from the
        ``/shelly`` probe.  For devices passed directly to the constructor,
        Gen1 is always ``1``; Gen2+ is fetched from the device on the first
        access and then cached.
        """
        if self._generation is not None:
            return self._generation
        if isinstance(self._device, ShellyGen1):
            self._generation = 1
        else:
            dev_info = self._device.get_info()
            self._generation = dev_info.get("gen", 2)
        return self._generation

    def __repr__(self) -> str:
        gen = self._generation if self._generation is not None else "?"
        return f"ShellyDevice(gen={gen}, host={self._device.host!r})"

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP session and release all connections."""
        self._device.close()

    def __enter__(self) -> "ShellyDevice":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def get_info(self) -> dict:
        """
        Return normalized device identification.

        Unlike the raw generation-specific endpoints (which use completely
        different key schemas), this always returns the same shape:

        ``mac``
            Hardware MAC address (no colons).
        ``model``
            Human-readable model name (e.g. ``"Shelly1PM"`` or
            ``"ShellyPlus1PM"``).
        ``firmware``
            Firmware version string.
        ``generation``
            Integer generation number.
        ``auth_enabled``
            Whether HTTP authentication is currently active.
        """
        if isinstance(self._device, ShellyGen1):
            raw = self._device.get_info()
            model_id = raw.get("type", "")
            return {"mac": raw.get("mac", ""), "model": GEN1_MODELS.get(model_id, model_id),
                "firmware": raw.get("fw", ""), "generation": 1, "auth_enabled": bool(raw.get("auth", False)), }
        else:
            raw = self._device.get_info()
            gen = raw.get("gen", 2)
            if self._generation is None:
                self._generation = gen
            return {"mac": raw.get("mac", ""), "model": raw.get("model") or raw.get("app", ""),
                "firmware": raw.get("ver", ""), "generation": gen, "auth_enabled": bool(raw.get("auth_en", False)), }

    def get_name(self) -> str:
        """
        Return the device name.
        """
        if isinstance(self._device, ShellyGen1):
            settings = self._device.get_settings()

            name = settings.get("name", "unknown")
            return name

        else:
            config = self._device.get_config()

            if config.get("sys", False) and config["sys"].get("device", False):
                return config["sys"]["device"].get("name", "unknown")
            else:
                return "unknown"

    def get_status(self) -> dict:
        """
        Return the full device status.

        Delegates directly to the underlying typed instance.  The response
        shape differs between generations — Gen1 returns a flat dict of
        device-wide readings; Gen2 returns a dict keyed by component
        identifier (e.g. ``"switch:0"``, ``"sys"``).
        """
        return self._device.get_status()

    # ------------------------------------------------------------------
    # Switch / relay
    # ------------------------------------------------------------------

    def turn_on(self, channel: int = 0, timer: float | None = None) -> dict:
        """
        Turn a switch/relay channel ON.

        Parameters
        ----------
        channel:
            Channel index (0-based).
        timer:
            Auto-revert delay in seconds: the channel will turn OFF
            automatically after this many seconds.
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.relay_on(channel, timer=timer)
        else:
            return self._device.switch_set(channel, on=True, toggle_after=timer)

    def turn_off(self, channel: int = 0, timer: float | None = None) -> dict:
        """
        Turn a switch/relay channel OFF.

        Parameters
        ----------
        channel:
            Channel index (0-based).
        timer:
            Auto-revert delay in seconds: the channel will turn ON
            automatically after this many seconds.
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.relay_off(channel, timer=timer)
        else:
            return self._device.switch_set(channel, on=False, toggle_after=timer)

    def toggle(self, channel: int = 0) -> dict:
        """Toggle a switch/relay channel."""
        if isinstance(self._device, ShellyGen1):
            return self._device.relay_toggle(channel)
        else:
            return self._device.switch_toggle(channel)

    def get_switch_status(self, channel: int = 0) -> dict:
        """
        Return the current state of a switch/relay channel.

        Gen1 response uses ``ison`` for the output state; Gen2 uses
        ``output``.  Both include power readings when the device supports
        metering.
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.get_relay(channel)
        else:
            return self._device.switch_get_status(channel)

    # ------------------------------------------------------------------
    # Cover / roller
    # ------------------------------------------------------------------

    def cover_open(self, channel: int = 0, duration: float | None = None) -> None:
        """
        Open a cover/roller (move in the open direction).

        Parameters
        ----------
        channel:
            Channel index (0-based).
        duration:
            Move for this many **seconds** then stop.

        .. note::
            Gen1 devices accept duration in milliseconds internally; this
            method accepts seconds and converts automatically.
        """
        if isinstance(self._device, ShellyGen1):
            ms = int(duration * 1000) if duration is not None else None
            self._device.roller_open(channel, duration=ms)
        else:
            self._device.cover_open(channel, duration=duration)

    def cover_close(self, channel: int = 0, duration: float | None = None) -> None:
        """
        Close a cover/roller (move in the close direction).

        Parameters
        ----------
        channel:
            Channel index (0-based).
        duration:
            Move for this many **seconds** then stop.
        """
        if isinstance(self._device, ShellyGen1):
            ms = int(duration * 1000) if duration is not None else None
            self._device.roller_close(channel, duration=ms)
        else:
            self._device.cover_close(channel, duration=duration)

    def cover_stop(self, channel: int = 0) -> None:
        """Stop the cover/roller motor immediately."""
        if isinstance(self._device, ShellyGen1):
            self._device.roller_stop(channel)
        else:
            self._device.cover_stop(channel)

    def cover_goto_position(self, channel: int = 0, pos: int = 0) -> None:
        """
        Move a cover/roller to an absolute position.

        Requires prior calibration (see :meth:`cover_calibrate`).

        Parameters
        ----------
        channel:
            Channel index (0-based).
        pos:
            Target position 0–100 (0 = fully open, 100 = fully closed).
        """
        if isinstance(self._device, ShellyGen1):
            self._device.roller_to_position(channel, pos)
        else:
            self._device.cover_goto_position(channel, pos=pos)

    def cover_calibrate(self, channel: int = 0) -> None:
        """
        Run automatic cover/roller calibration.

        The device will fully open and close to measure travel time.
        Required before :meth:`cover_goto_position` can be used.
        """
        if isinstance(self._device, ShellyGen1):
            self._device.calibrate_roller(channel)
        else:
            self._device.cover_calibrate(channel)

    def get_cover_status(self, channel: int = 0) -> dict:
        """
        Return the current state of a cover/roller channel.

        Both generations include ``state`` and ``current_pos`` (0–100) in
        their response, though surrounding keys differ.
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.get_roller(channel)
        else:
            return self._device.cover_get_status(channel)

    # ------------------------------------------------------------------
    # Light / dimmer
    # ------------------------------------------------------------------

    def light_on(self, channel: int = 0, brightness: int | None = None) -> dict:
        """
        Turn a light channel ON.

        Parameters
        ----------
        channel:
            Channel index (0-based).
        brightness:
            Brightness 0–100 %.  Omit to restore the device's last value.
        """
        if isinstance(self._device, ShellyGen1):
            kwargs: dict = {}
            if brightness is not None:
                kwargs["brightness"] = brightness
            return self._device.light_on(channel, **kwargs)
        else:
            return self._device.light_set(channel, on=True, brightness=brightness)

    def light_off(self, channel: int = 0) -> dict:
        """Turn a light channel OFF."""
        if isinstance(self._device, ShellyGen1):
            return self._device.light_off(channel)
        else:
            return self._device.light_set(channel, on=False)

    def light_toggle(self, channel: int = 0) -> dict:
        """Toggle a light channel."""
        return self._device.light_toggle(channel)

    def get_light_status(self, channel: int = 0) -> dict:
        """
        Return the current state of a light channel.

        Gen1 response uses ``ison`` and may include ``mode``, ``red``,
        ``green``, ``blue``.  Gen2 response uses ``output`` and
        ``brightness``.
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.get_light(channel)
        else:
            return self._device.light_get_status(channel)

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------

    def reboot(self) -> None:
        """Reboot the device."""
        self._device.reboot()

    def factory_reset(self) -> None:
        """Perform a factory reset.  All settings and credentials are erased."""
        self._device.factory_reset()

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    def check_for_update(self) -> dict:
        """
        Ask the device to check the firmware server for available updates.

        The response shape differs between generations:

        * Gen1: ``{"status": "ok"}`` or ``{"status": "running"}``
        * Gen2: ``{"stable": {"version": ..., "build_id": ...}, "beta": {...}}``
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.check_update()
        else:
            return self._device.check_for_update()

    def update_firmware(self, url: str | None = None, beta: bool = False) -> None:
        """
        Trigger a firmware update.

        Parameters
        ----------
        url:
            Custom firmware binary URL.  When ``None`` the device downloads
            from the official Shelly update server.
        beta:
            ``True`` to install the latest beta release instead of stable.
            Ignored when *url* is provided.
        """
        if isinstance(self._device, ShellyGen1):
            self._device.update_firmware(url=url, beta=beta)
        else:
            if url:
                self._device.update_firmware(url=url)
            else:
                self._device.update_firmware(stage="beta" if beta else "stable")

    # ------------------------------------------------------------------
    # WiFi
    # ------------------------------------------------------------------

    def wifi_scan(self) -> dict:
        """
        Scan for nearby WiFi networks.

        Returns a list of access points; the response shape differs between
        generations.
        """
        return self._device.wifi_scan()

    # ------------------------------------------------------------------
    # Cloud
    # ------------------------------------------------------------------

    def get_cloud_status(self) -> dict:
        """
        Return cloud connectivity status.

        Both generations return a dict containing at least
        ``"connected": bool``.
        """
        if isinstance(self._device, ShellyGen1):
            return self._device.get_cloud_settings()
        else:
            return self._device.cloud_get_status()

    def set_cloud_enabled(self, enabled: bool) -> None:
        """Enable or disable Shelly Cloud connectivity."""
        if isinstance(self._device, ShellyGen1):
            self._device.set_cloud(enabled)
        else:
            self._device.cloud_set_config(enable=enabled)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def set_auth(self, password: str | None, username: str = "admin") -> None:
        """
        Set or remove the device password.

        Parameters
        ----------
        password:
            New password string.  Pass ``None`` to disable authentication.
        username:
            Username for Gen1 HTTP Basic Auth (default ``"admin"``).
            Ignored for Gen2+ devices, which always use ``"admin"``.
        """
        if isinstance(self._device, ShellyGen1):
            self._device.set_auth(enabled=password is not None, username=username, password=password, )
        else:
            self._device.set_auth(password)
