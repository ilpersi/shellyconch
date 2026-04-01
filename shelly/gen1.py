"""
Shelly Gen1 device interface.

All first-generation Shelly devices share a common HTTP REST API served on
port 80.  Parameters are passed as query-string key-value pairs (both GET and
POST are accepted; this library always uses GET for simplicity).  Every
endpoint that modifies state can be read at the same URL without parameters.

Authentication: HTTP Basic Auth (disabled by default on the device; enable
it via :meth:`set_auth` or through the device web UI).

Reference: https://shelly-api-docs.shelly.cloud/gen1/
"""

from __future__ import annotations

from typing import Any

from requests.auth import HTTPBasicAuth

from .base import BaseShelly
from .models import Gen1RollerDirection, RelayState


class ShellyGen1(BaseShelly):
    """
    Generic interface for all first-generation Shelly devices.

    Parameters
    ----------
    host:
        IP address or hostname of the device.
    port:
        HTTP port (default ``80``).
    timeout:
        Request timeout in seconds (default ``10``).
    username:
        Username for HTTP Basic Auth (default ``"admin"``).
    password:
        Password for HTTP Basic Auth.  Leave ``None`` (default) when auth
        is disabled on the device.
    """

    def __init__(self, host: str, port: int = 80, timeout: float = 10.0, username: str = "admin",
            password: str | None = None, ):
        super().__init__(host, port, timeout)
        self._username = username
        self._password = password
        if password:
            self.session.auth = HTTPBasicAuth(username, password)

    # ------------------------------------------------------------------
    # Device identification & discovery
    # ------------------------------------------------------------------

    def get_info(self) -> dict:
        """
        Return basic device information.

        This endpoint is always accessible even when auth is enabled.

        Returns a dict with keys ``type``, ``mac``, ``auth``, ``fw``,
        ``longid``, ``discoverable``.
        """
        return self._get("/shelly")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """
        Return the current runtime status of the device.

        The response contains WiFi state, cloud/MQTT connectivity, memory
        stats, firmware update availability, and device-specific readings
        (relay states, power measurements, sensor values, etc.).
        """
        return self._get("/status")

    # ------------------------------------------------------------------
    # Settings (device-wide)
    # ------------------------------------------------------------------

    def get_settings(self) -> dict:
        """Return the full device configuration as a dict."""
        return self._get("/settings")

    def set_settings(self, **params: Any) -> dict:
        """
        Update one or more global device settings.

        Common parameters
        -----------------
        name : str
            Human-readable device name.
        timezone : str
            IANA timezone string (e.g. ``"America/New_York"``).
        lat, lng : float
            Geolocation for sunrise/sunset schedules.
        tzautodetect : bool
            Auto-detect timezone from IP address.
        discoverable : bool
            Whether the device announces itself via mDNS.
        mqtt_enable : bool
        mqtt_server : str
            Broker ``"host:port"``.
        mqtt_user, mqtt_pass : str
        mqtt_update_period : int
            Seconds between periodic MQTT status publishes (0 = off).
        coiot_enable : bool
        coiot_update_period : int
            CoIoT broadcast interval in seconds (15–65535).
        coiot_peer : str
            Unicast CoIoT target ``"ip:port"``; empty string = multicast.
        sntp_server : str
        debug_enable : bool
        allow_cross_origin : bool
        reset : int
            Pass ``1`` to perform a factory reset.
        """
        return self._get("/settings", params=_clean(params))

    # ------------------------------------------------------------------
    # WiFi settings
    # ------------------------------------------------------------------

    def get_wifi_ap(self) -> dict:
        """Return the Access-Point WiFi configuration."""
        return self._get("/settings/ap")

    def set_wifi_ap(self, enabled: bool, ssid: str | None = None, key: str | None = None, ) -> dict:
        """Enable or disable the device's WiFi Access Point."""
        p: dict = {"enabled": _bool(enabled)}
        if ssid is not None:
            p["ssid"] = ssid
        if key is not None:
            p["key"] = key
        return self._get("/settings/ap", params=p)

    def get_wifi_sta(self, index: int = 0) -> dict:
        """
        Return WiFi client (STA) configuration.

        ``index=0`` is the primary network; ``index=1`` is the fallback.
        """
        path = "/settings/sta" if index == 0 else "/settings/sta1"
        return self._get(path)

    def set_wifi_sta(self, ssid: str, key: str = "", enabled: bool = True, index: int = 0, ipv4_method: str = "dhcp",
            ip: str | None = None, gw: str | None = None, mask: str | None = None, dns: str | None = None, ) -> dict:
        """
        Configure WiFi client mode.

        Parameters
        ----------
        ssid:
            Network name.
        key:
            WiFi password (empty string for open networks).
        enabled:
            Activate this network profile.
        index:
            ``0`` = primary, ``1`` = fallback.
        ipv4_method:
            ``"dhcp"`` or ``"static"``.
        ip, gw, mask, dns:
            Static IP settings (required when ``ipv4_method="static"``).
        """
        path = "/settings/sta" if index == 0 else "/settings/sta1"
        p: dict = {"ssid": ssid, "key": key, "enabled": _bool(enabled), "ipv4_method": ipv4_method}
        for k, v in [("ip", ip), ("gw", gw), ("mask", mask), ("dns", dns)]:
            if v is not None:
                p[k] = v
        return self._get(path, params=p)

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def get_auth_settings(self) -> dict:
        """Return the current HTTP authentication configuration."""
        return self._get("/settings/login")

    def set_auth(self, enabled: bool, username: str = "admin", password: str | None = None, ) -> dict:
        """
        Enable or disable HTTP Basic Authentication on the device.

        When enabling, provide a ``username`` and ``password``.  The password
        is write-only and will not appear in subsequent GET responses.
        """
        p: dict = {"enabled": _bool(enabled), "username": username}
        if password is not None:
            p["password"] = password
        resp = self._get("/settings/login", params=p)
        if enabled and password:
            self._password = password
            self._username = username
            self.session.auth = HTTPBasicAuth(username, password)
        elif not enabled:
            self._password = None
            self.session.auth = None
        return resp

    # ------------------------------------------------------------------
    # Cloud
    # ------------------------------------------------------------------

    def get_cloud_settings(self) -> dict:
        """Return cloud connectivity settings."""
        return self._get("/settings/cloud")

    def set_cloud(self, enabled: bool) -> dict:
        """Enable or disable Shelly Cloud connectivity."""
        return self._get("/settings/cloud", params={"enabled": _bool(enabled)})

    # ------------------------------------------------------------------
    # Actions (URL callbacks)
    # ------------------------------------------------------------------

    def get_actions(self) -> dict:
        """
        Return all configured URL-triggered actions for this device.

        The response contains an ``actions`` dict keyed by action name
        (e.g. ``out_on_url``, ``out_off_url``), each being a list of
        ``{index, urls, enabled}`` objects.
        """
        return self._get("/settings/actions")

    def set_action(self, name: str, urls: list[str], index: int = 0, enabled: bool = True, ) -> dict:
        """
        Configure a URL callback action.

        Parameters
        ----------
        name:
            Action name, e.g. ``"out_on_url"``, ``"out_off_url"``,
            ``"over_power_url"``, ``"roller_open_url"``, etc.
        urls:
            List of up to 5 URLs to call (max 256 chars each).
        index:
            Channel index (0 for single-channel devices).
        enabled:
            Activate this action.

        Common Gen1 action names
        ------------------------
        Relay: out_on_url, out_off_url, over_power_url, btn_on_url,
               btn_off_url, shortpush_url, longpush_url
        Roller: roller_open_url, roller_close_url, roller_stop_url
        Sensors: flood_detected_url, flood_gone_url, open_url, close_url,
                 over_temp_url, under_temp_url, alarm_url, alarm_off_url
        """
        p: dict = {"index": index, "name": name, "enabled": _bool(enabled), }
        for i, url in enumerate(urls):
            p[f"urls[{i}]"] = url
        return self._get("/settings/actions", params=p)

    # ------------------------------------------------------------------
    # Relay control
    # ------------------------------------------------------------------

    def get_relay(self, index: int = 0) -> dict:
        """
        Return the current state of a relay channel.

        Response keys: ``ison``, ``has_timer``, ``timer_remaining``,
        ``source``.  Power-metered devices also include ``power``,
        ``energy``, ``temperature``.
        """
        return self._get(f"/relay/{index}")

    def set_relay(self, index: int, turn: str | RelayState, timer: float | None = None, ) -> dict:
        """
        Control a relay channel.

        Parameters
        ----------
        index:
            Channel index (0-based).
        turn:
            ``"on"``, ``"off"``, or ``"toggle"`` (see :class:`RelayState`).
        timer:
            Auto-revert timer in seconds.  Pass ``0`` to cancel an active
            timer.
        """
        p: dict = {"turn": str(turn)}
        if timer is not None:
            p["timer"] = timer
        return self._get(f"/relay/{index}", params=p)

    def relay_on(self, index: int = 0, timer: float | None = None) -> dict:
        """Turn a relay channel ON (optionally with an auto-off timer)."""
        return self.set_relay(index, RelayState.ON, timer=timer)

    def relay_off(self, index: int = 0, timer: float | None = None) -> dict:
        """Turn a relay channel OFF (optionally with an auto-on timer)."""
        return self.set_relay(index, RelayState.OFF, timer=timer)

    def relay_toggle(self, index: int = 0) -> dict:
        """Toggle a relay channel."""
        return self.set_relay(index, RelayState.TOGGLE)

    def get_relay_settings(self, index: int = 0) -> dict:
        """Return the persistent configuration for a relay channel."""
        return self._get(f"/settings/relay/{index}")

    def set_relay_settings(self, index: int = 0, **params: Any) -> dict:
        """
        Update the persistent configuration for a relay channel.

        Common parameters
        -----------------
        default_state : str
            Power-on behaviour: ``"off"``, ``"on"``, ``"restore"``,
            ``"switch"``.
        btn_type : str
            Physical button mode (see :class:`Gen1ButtonType`).
        btn_reverse : int
            ``1`` to invert the button logic.
        auto_on : float
            Auto-turn-on delay in seconds (0 = disabled).
        auto_off : float
            Auto-turn-off delay in seconds (0 = disabled).
        max_power : float
            Overpower threshold in Watts.
        name : str
            Human-readable channel label.
        schedule : bool
        schedule_rules : list[str]
        """
        return self._get(f"/settings/relay/{index}", params=_clean(params))

    # ------------------------------------------------------------------
    # Power metering (Shelly1PM, Plug, 4Pro, etc.)
    # ------------------------------------------------------------------

    def get_meter(self, index: int = 0) -> dict:
        """
        Return power meter readings.

        Response keys: ``power`` (W), ``overpower``, ``is_valid``,
        ``timestamp``, ``counters`` (last 3×1-min Watt-minute rolling
        totals), ``total`` (cumulative Watt-minutes).
        """
        return self._get(f"/meter/{index}")

    # ------------------------------------------------------------------
    # Energy metering (Shelly EM / 3EM)
    # ------------------------------------------------------------------

    def get_emeter(self, index: int = 0) -> dict:
        """
        Return energy meter readings (EM / 3EM devices).

        Response keys: ``power`` (W), ``pf``, ``current`` (A),
        ``voltage`` (V), ``is_valid``, ``total`` (Wh),
        ``total_returned`` (Wh), ``reactive`` (VAr).
        """
        return self._get(f"/emeter/{index}")

    def reset_emeter(self, index: int = 0) -> dict:
        """Reset the energy counters (``total`` and ``total_returned``) to zero."""
        return self._get(f"/emeter/{index}", params={"reset_totals": 1})

    def get_emeter_settings(self, index: int = 0) -> dict:
        """Return persistent configuration for an energy meter channel."""
        return self._get(f"/settings/emeter/{index}")

    def set_emeter_settings(self, index: int = 0, **params: Any) -> dict:
        """
        Update configuration for an energy meter channel.

        Parameters
        ----------
        max_power : float
            Overpower protection threshold in Watts.
        over_power_url : str
        over_power_url_threshold : float
        under_power_url : str
        under_power_url_threshold : float
        """
        return self._get(f"/settings/emeter/{index}", params=_clean(params))

    def reset_all_energy_data(self) -> dict:
        """Reset all energy statistics on EM/3EM devices."""
        return self._get("/reset_data")

    # ------------------------------------------------------------------
    # Roller / cover control (Shelly2 / 2.5 in roller mode)
    # ------------------------------------------------------------------

    def get_roller(self, index: int = 0) -> dict:
        """
        Return the current state of a roller/cover channel.

        Response keys: ``state`` (open/close/stop), ``power``, ``energy``,
        ``current_pos`` (0–100), ``target_pos``, ``stop_reason``,
        ``last_direction``, ``positioning``.
        """
        return self._get(f"/roller/{index}")

    def set_roller(self, index: int, go: str | Gen1RollerDirection, pos: int | None = None,
            duration: int | None = None, ) -> dict:
        """
        Command a roller/cover channel.

        Parameters
        ----------
        index:
            Channel index.
        go:
            Direction: ``"open"``, ``"close"``, ``"stop"``, or ``"to_pos"``.
        pos:
            Target position 0–100 (0 = open, 100 = closed).  Required when
            ``go="to_pos"``.  Can also be passed directly as
            ``roller_pos`` for devices with position tracking.
        duration:
            Move for this many milliseconds then stop.
        """
        p: dict = {"go": str(go)}
        if pos is not None:
            p["roller_pos"] = pos
        if duration is not None:
            p["duration"] = duration
        return self._get(f"/roller/{index}", params=p)

    def roller_open(self, index: int = 0, duration: int | None = None) -> dict:
        """Open the roller/cover (move in the open direction)."""
        return self.set_roller(index, Gen1RollerDirection.OPEN, duration=duration)

    def roller_close(self, index: int = 0, duration: int | None = None) -> dict:
        """Close the roller/cover (move in the close direction)."""
        return self.set_roller(index, Gen1RollerDirection.CLOSE, duration=duration)

    def roller_stop(self, index: int = 0) -> dict:
        """Stop the roller/cover motor."""
        return self.set_roller(index, Gen1RollerDirection.STOP)

    def roller_to_position(self, index: int, pos: int) -> dict:
        """
        Move the roller/cover to a specific position.

        Requires calibration (see :meth:`calibrate_roller`).

        Parameters
        ----------
        pos:
            Target position 0–100 (0 = fully open, 100 = fully closed).
        """
        return self.set_roller(index, Gen1RollerDirection.TO_POS, pos=pos)

    def calibrate_roller(self, index: int = 0) -> dict:
        """
        Initiate automatic roller calibration.

        The device will fully open and close the cover to measure travel
        time.  Required before position control can be used.
        """
        return self._get(f"/roller/{index}/calibrate")

    def get_roller_settings(self, index: int = 0) -> dict:
        """Return the persistent configuration for a roller channel."""
        return self._get(f"/settings/roller/{index}")

    def set_roller_settings(self, index: int = 0, **params: Any) -> dict:
        """
        Update roller channel configuration.

        Common parameters
        -----------------
        maxtime_open, maxtime_close : float
            Maximum travel time in seconds.
        default_state : str
            ``"stop"``, ``"open"``, or ``"close"`` on power-on.
        swap : bool
            Swap open/close directions.
        swap_inputs : bool
            Swap input button functions.
        obstacle_mode : str
            ``"reverse"`` or ``"stop"`` on obstacle detection.
        safety_switch : str
            ``"disabled"`` or ``"stop"``/``"reverse"`` on safety input.
        positioning : bool
            Enable position tracking (requires calibration).
        schedule : bool
        schedule_rules : list[str]
        """
        return self._get(f"/settings/roller/{index}", params=_clean(params))

    # ------------------------------------------------------------------
    # Light / dimmer / RGBW control
    # ------------------------------------------------------------------

    def get_light(self, index: int = 0) -> dict:
        """
        Return the current state of a light channel.

        Response keys vary by device: ``ison``, ``brightness``, ``mode``
        (color/white), ``red``, ``green``, ``blue``, ``white``, ``gain``,
        ``temp`` (colour temperature K), ``effect``, ``transition``.
        """
        return self._get(f"/light/{index}")

    def set_light(self, index: int = 0, **params: Any) -> dict:
        """
        Control a light channel (Bulb, Dimmer, Vintage, Duo, RGBW2).

        Parameters
        ----------
        turn : str
            ``"on"``, ``"off"``, ``"toggle"``.
        mode : str
            ``"color"`` or ``"white"`` (RGBW/Bulb only).
        brightness : int
            0–100 % (white mode / dimmers).
        red, green, blue : int
            0–255 channel values (colour mode).
        white : int
            0–255 white channel (colour mode or Duo).
        gain : int
            0–100 overall brightness multiplier (colour mode).
        temp : int
            Colour temperature in Kelvin, e.g. 3000–6500 (white mode).
        effect : int
            Light effect index (0 = none).
        transition : int
            Fade duration in milliseconds (one-shot, resets after move).
        timer : float
            Auto-off/on timer in seconds.
        dim : str
            ``"up"`` or ``"down"`` (Dimmer only, incremental).
        step : int
            Increment for ``dim`` commands (Dimmer only).
        """
        return self._get(f"/light/{index}", params=_clean(params))

    def light_on(self, index: int = 0, **params: Any) -> dict:
        """Turn a light ON (pass additional keyword args as per :meth:`set_light`)."""
        return self.set_light(index, turn="on", **params)

    def light_off(self, index: int = 0) -> dict:
        """Turn a light OFF."""
        return self.set_light(index, turn="off")

    def light_toggle(self, index: int = 0) -> dict:
        """Toggle a light channel."""
        return self.set_light(index, turn="toggle")

    def get_color(self, index: int = 0) -> dict:
        """Return the current state of a colour-mode channel (RGBW / Bulb)."""
        return self._get(f"/color/{index}")

    def set_color(self, index: int = 0, **params: Any) -> dict:
        """
        Control a colour-mode channel.

        Accepted params: ``turn``, ``red``, ``green``, ``blue``, ``white``,
        ``gain``, ``effect``, ``transition``, ``timer``.
        """
        return self._get(f"/color/{index}", params=_clean(params))

    def get_white(self, index: int = 0) -> dict:
        """Return the current state of a white-mode channel (RGBW2 / Bulb / Duo)."""
        return self._get(f"/white/{index}")

    def set_white(self, index: int = 0, **params: Any) -> dict:
        """
        Control a white-mode channel.

        Accepted params: ``turn``, ``brightness``, ``temp``, ``transition``,
        ``timer``.
        """
        return self._get(f"/white/{index}", params=_clean(params))

    def get_light_settings(self, index: int = 0) -> dict:
        """Return the persistent configuration for a light channel."""
        return self._get(f"/settings/light/{index}")

    def set_light_settings(self, index: int = 0, **params: Any) -> dict:
        """
        Update persistent light channel configuration.

        Common parameters
        -----------------
        default_state : str
            ``"off"``, ``"on"``, ``"restore_last"``.
        auto_on, auto_off : float
            Auto-timer seconds (0 = disabled).
        transition : int
            Default fade duration in ms.
        min_brightness : int
            Minimum brightness percent (Dimmer).
        schedule : bool
        schedule_rules : list[str]
        """
        return self._get(f"/settings/light/{index}", params=_clean(params))

    def get_color_settings(self, index: int = 0) -> dict:
        """Return the persistent colour-mode configuration (RGBW2 / Bulb)."""
        return self._get(f"/settings/color/{index}")

    def set_color_settings(self, index: int = 0, **params: Any) -> dict:
        """Update persistent colour-mode configuration."""
        return self._get(f"/settings/color/{index}", params=_clean(params))

    def get_white_settings(self, index: int = 0) -> dict:
        """Return the persistent white-mode configuration."""
        return self._get(f"/settings/white/{index}")

    def set_white_settings(self, index: int = 0, **params: Any) -> dict:
        """Update persistent white-mode configuration."""
        return self._get(f"/settings/white/{index}", params=_clean(params))

    def get_night_mode(self) -> dict:
        """Return night-mode configuration (light devices)."""
        return self._get("/settings/night_mode")

    def set_night_mode(self, enabled: bool, brightness: int | None = None,
            active_between: list[str] | None = None, ) -> dict:
        """
        Configure night mode (light devices).

        Parameters
        ----------
        enabled:
            Activate night mode.
        brightness:
            Brightness percentage to use during night mode.
        active_between:
            Two-element list of ``"HH:MM"`` strings, e.g.
            ``["23:00", "06:00"]``.
        """
        p: dict = {"enabled": _bool(enabled)}
        if brightness is not None:
            p["brightness"] = brightness
        if active_between is not None:
            p["active_between[0]"] = active_between[0]
            p["active_between[1]"] = active_between[1]
        return self._get("/settings/night_mode", params=p)

    # ------------------------------------------------------------------
    # External add-on sensors (Shelly1 / 1PM)
    # ------------------------------------------------------------------

    def get_ext_temperature(self, sensor_index: int = 0) -> dict:
        """Return settings and last reading for an external DS1820 sensor."""
        return self._get(f"/settings/ext_temperature/{sensor_index}")

    def set_ext_temperature(self, sensor_index: int = 0, **params: Any) -> dict:
        """
        Configure an external temperature sensor.

        Parameters
        ----------
        over_temp_threshold, under_temp_threshold : float
            Alert thresholds in °C.
        offset_tC : float
            Calibration offset in °C.
        """
        return self._get(f"/settings/ext_temperature/{sensor_index}", params=_clean(params))

    def get_ext_humidity(self, sensor_index: int = 0) -> dict:
        """Return settings and last reading for an external DHT22 sensor."""
        return self._get(f"/settings/ext_humidity/{sensor_index}")

    def set_ext_humidity(self, sensor_index: int = 0, **params: Any) -> dict:
        """Configure an external humidity sensor."""
        return self._get(f"/settings/ext_humidity/{sensor_index}", params=_clean(params))

    # ------------------------------------------------------------------
    # Input channels (i3, Button1)
    # ------------------------------------------------------------------

    def get_input(self, index: int = 0) -> dict:
        """Return the current state of an input channel."""
        return self._get(f"/input/{index}")

    def get_input_settings(self, index: int = 0) -> dict:
        """Return the persistent configuration for an input channel."""
        return self._get(f"/settings/input/{index}")

    def set_input_settings(self, index: int = 0, **params: Any) -> dict:
        """
        Update input channel configuration.

        Common parameters
        -----------------
        btn_type : str
            ``"toggle"``, ``"momentary"``, ``"edge"``, ``"detached"``.
        btn_reverse : int
            ``1`` to invert button logic.
        longpush_time : int
            Long-press threshold in milliseconds.
        btn_debounce : int
            Debounce interval in milliseconds.
        """
        return self._get(f"/settings/input/{index}", params=_clean(params))

    # ------------------------------------------------------------------
    # Analogue input (Shelly Uni)
    # ------------------------------------------------------------------

    def get_adc(self, index: int = 0) -> dict:
        """Return the current ADC voltage reading (Shelly Uni)."""
        return self._get(f"/adc/{index}")

    def get_adc_settings(self, index: int = 0) -> dict:
        """Return ADC configuration (Shelly Uni)."""
        return self._get(f"/settings/adc/{index}")

    def set_adc_settings(self, index: int = 0, **params: Any) -> dict:
        """Update ADC configuration (Shelly Uni)."""
        return self._get(f"/settings/adc/{index}", params=_clean(params))

    # ------------------------------------------------------------------
    # TRV (thermostatic radiator valve)
    # ------------------------------------------------------------------

    def get_thermostat(self, index: int = 0) -> dict:
        """
        Return current thermostat state (Shelly TRV).

        Response keys: ``pos`` (valve 0–100 %), ``target_t`` (setpoint),
        ``tmp`` (measured temperature), ``schedule``, ``boost_minutes``.
        """
        return self._get(f"/thermostats/{index}")

    def set_thermostat(self, index: int = 0, **params: Any) -> dict:
        """
        Control the TRV setpoint.

        Parameters
        ----------
        target_t_enabled : bool
            Enable thermostat control.
        target_t : float
            Target temperature in °C.
        """
        return self._get(f"/thermostats/{index}", params=_clean(params))

    def get_thermostat_settings(self, index: int = 0) -> dict:
        """Return TRV schedule and profile configuration."""
        return self._get(f"/settings/thermostats/{index}")

    def set_thermostat_settings(self, index: int = 0, **params: Any) -> dict:
        """Update TRV configuration."""
        return self._get(f"/settings/thermostats/{index}", params=_clean(params))

    # ------------------------------------------------------------------
    # Gas detector
    # ------------------------------------------------------------------

    def gas_self_test(self) -> dict:
        """Trigger the gas sensor self-test (Shelly Gas)."""
        return self._get("/self_test")

    def gas_mute(self) -> dict:
        """Silence the active alarm buzzer (Shelly Gas)."""
        return self._get("/mute")

    def gas_unmute(self) -> dict:
        """Restore the alarm buzzer sound (Shelly Gas)."""
        return self._get("/unmute")

    def get_valve(self, index: int = 0) -> dict:
        """Return the current valve state (Shelly Gas)."""
        return self._get(f"/valve/{index}")

    def set_valve(self, index: int, turn: str) -> dict:
        """
        Control the gas valve (Shelly Gas).

        Parameters
        ----------
        turn:
            ``"open"`` or ``"close"``.
        """
        return self._get(f"/valve/{index}", params={"turn": turn})

    # ------------------------------------------------------------------
    # Door/Window sensor calibration
    # ------------------------------------------------------------------

    def calibrate_door_window(self, opened: bool) -> dict:
        """
        Calibrate the Door/Window sensor tilt angle.

        Parameters
        ----------
        opened:
            ``True`` = calibrate the open position; ``False`` is not valid
            (use ``clear`` instead).
        """
        p: dict = {"opened": 1} if opened else {"clear": 1}
        return self._get("/calibrate", params=p)

    # ------------------------------------------------------------------
    # CoIoT device description (all devices, firmware ≥ 1.10)
    # ------------------------------------------------------------------

    def get_coiot_description(self) -> dict:
        """
        Return the CoIoT device description over HTTP.

        Available since firmware v1.10.0.  Describes all sensor IDs and
        their types for interpreting CoAP multicast status packets.
        """
        return self._get("/cit/d")

    # ------------------------------------------------------------------
    # Firmware
    # ------------------------------------------------------------------

    def get_ota_status(self) -> dict:
        """
        Return firmware update status.

        Response keys: ``status`` (idle/pending/updating/unknown),
        ``has_update``, ``new_version``, ``old_version``, ``beta_version``.
        """
        return self._get("/ota")

    def check_update(self) -> dict:
        """
        Ask the device to poll the firmware server for available updates.

        Returns ``{"status": "ok"}`` or ``{"status": "running"}``.
        """
        return self._get("/ota/check")

    def update_firmware(self, url: str | None = None, beta: bool = False, ) -> dict:
        """
        Trigger a firmware update.

        Parameters
        ----------
        url:
            Custom firmware binary URL.  If ``None``, the device downloads
            from the official Shelly update server.
        beta:
            ``True`` to install the latest beta firmware instead of stable.
        """
        if url:
            return self._get("/ota", params={"url": url})
        if beta:
            return self._get("/ota", params={"beta": 1})
        return self._get("/ota", params={"update": 1})

    # ------------------------------------------------------------------
    # Reboot & factory reset
    # ------------------------------------------------------------------

    def reboot(self) -> dict:
        """Reboot the device immediately."""
        return self._get("/reboot")

    def factory_reset(self) -> dict:
        """
        Perform a factory reset via the settings endpoint.

        Equivalent to passing ``reset=1`` to :meth:`set_settings`.
        """
        return self._get("/settings", params={"reset": 1})

    # ------------------------------------------------------------------
    # WiFi scan (available in AP mode only)
    # ------------------------------------------------------------------

    def wifi_scan(self) -> dict:
        """
        Scan for nearby WiFi networks.

        Only available when the device is operating in Access Point mode.
        Returns a list of networks with ``ssid``, ``auth``, ``channel``,
        ``bssid``, and ``rssi``.
        """
        return self._get("/wifiscan")

    # ------------------------------------------------------------------
    # Battery device helpers
    # ------------------------------------------------------------------

    def reset_sta_cache(self) -> dict:
        """
        Reset the STA connection cache on battery-operated devices.

        Applies to Door/Window, H&T, Smoke, Flood, and Button1.
        """
        return self._get("/sta_cache_reset")

    # ------------------------------------------------------------------
    # Debug logs
    # ------------------------------------------------------------------

    def get_debug_log(self, index: int = 0) -> str:
        """
        Retrieve the device debug log as plain text.

        ``index=0`` → ``/debug/log``; ``index=1`` → ``/debug/log1``.
        """
        path = "/debug/log" if index == 0 else "/debug/log1"
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, timeout=self.timeout)
        if not resp.ok:
            raise ShellyHTTPError(resp.status_code, resp.text)  # type: ignore[misc]
        return resp.text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _bool(value: bool) -> str:
    """Encode a Python bool as a Gen1 boolean string (``true``/``false``)."""
    return "true" if value else "false"


def _clean(params: dict) -> dict:
    """Remove None values from a parameter dict."""
    return {k: v for k, v in params.items() if v is not None}
