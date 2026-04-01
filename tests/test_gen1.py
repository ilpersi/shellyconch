"""Tests for shelly/gen1.py — ShellyGen1 endpoints and helpers."""

from unittest.mock import MagicMock

from requests.auth import HTTPBasicAuth
from shelly.gen1 import ShellyGen1, _bool, _clean
from shelly.models import Gen1RollerDirection, RelayState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_gen1(host="192.168.1.100", password=None):
    device = ShellyGen1(host, password=password)
    device._session = MagicMock()
    device._session.request.return_value = _ok({})
    return device


def _ok(data):
    r = MagicMock()
    r.status_code = 200
    r.ok = True
    r.content = b"x"
    r.json.return_value = data
    return r


def last_call(device):
    """Return (method, url, kwargs) from the most recent session.request call."""
    args, kwargs = device._session.request.call_args
    return args[0], args[1], kwargs


# ---------------------------------------------------------------------------
# _bool helper
# ---------------------------------------------------------------------------

class TestBool:
    def test_true(self):
        assert _bool(True) == "true"

    def test_false(self):
        assert _bool(False) == "false"


# ---------------------------------------------------------------------------
# _clean helper
# ---------------------------------------------------------------------------

class TestClean:
    def test_removes_none_values(self):
        assert _clean({"a": 1, "b": None, "c": "x"}) == {"a": 1, "c": "x"}

    def test_empty_dict(self):
        assert _clean({}) == {}

    def test_keeps_zero_and_false(self):
        assert _clean({"a": 0, "b": False}) == {"a": 0, "b": False}


# ---------------------------------------------------------------------------
# Construction / auth setup
# ---------------------------------------------------------------------------

class TestInit:
    def test_no_password_no_auth(self):
        d = ShellyGen1("192.168.1.1")
        # session not yet created — just check internal state
        assert d._password is None

    def test_password_sets_session_auth(self):
        d = ShellyGen1("192.168.1.1", password="secret")
        assert isinstance(d.session.auth, HTTPBasicAuth)


# ---------------------------------------------------------------------------
# Device info
# ---------------------------------------------------------------------------

class TestGetInfo:
    def test_calls_shelly_endpoint(self):
        d = make_gen1()
        d.get_info()
        _, url, _ = last_call(d)
        assert url == "http://192.168.1.100:80/shelly"

    def test_returns_response_json(self):
        d = make_gen1()
        payload = {"type": "SHSW-1", "mac": "AABBCCDD1122", "fw": "1.0"}
        d._session.request.return_value = _ok(payload)
        assert d.get_info() == payload


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_calls_status_endpoint(self):
        d = make_gen1()
        d.get_status()
        _, url, _ = last_call(d)
        assert url.endswith("/status")


# ---------------------------------------------------------------------------
# Relay control
# ---------------------------------------------------------------------------

class TestRelay:
    def test_get_relay_url(self):
        d = make_gen1()
        d.get_relay(1)
        _, url, _ = last_call(d)
        assert url.endswith("/relay/1")

    def test_set_relay_turn_param(self):
        d = make_gen1()
        d.set_relay(0, "on")
        _, url, kwargs = last_call(d)
        assert url.endswith("/relay/0")
        assert kwargs["params"]["turn"] == "on"  # plain string passes through as-is

    def test_set_relay_with_timer(self):
        d = make_gen1()
        d.set_relay(0, "on", timer=30)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["timer"] == 30

    def test_relay_on(self):
        d = make_gen1()
        d.relay_on(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["turn"] == str(RelayState.ON)

    def test_relay_off(self):
        d = make_gen1()
        d.relay_off(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["turn"] == str(RelayState.OFF)

    def test_relay_toggle(self):
        d = make_gen1()
        d.relay_toggle(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["turn"] == str(RelayState.TOGGLE)

    def test_relay_on_with_timer(self):
        d = make_gen1()
        d.relay_on(0, timer=60)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["timer"] == 60

    def test_get_relay_settings(self):
        d = make_gen1()
        d.get_relay_settings(2)
        _, url, _ = last_call(d)
        assert url.endswith("/settings/relay/2")


# ---------------------------------------------------------------------------
# Roller / cover
# ---------------------------------------------------------------------------

class TestRoller:
    def test_get_roller_url(self):
        d = make_gen1()
        d.get_roller(0)
        _, url, _ = last_call(d)
        assert url.endswith("/roller/0")

    def test_set_roller_go_param(self):
        d = make_gen1()
        d.set_roller(0, "open")
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["go"] == "open"  # plain string passes through as-is

    def test_set_roller_with_duration(self):
        d = make_gen1()
        d.set_roller(0, "open", duration=5000)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["duration"] == 5000

    def test_roller_open(self):
        d = make_gen1()
        d.roller_open()
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["go"] == str(Gen1RollerDirection.OPEN)

    def test_roller_close(self):
        d = make_gen1()
        d.roller_close()
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["go"] == str(Gen1RollerDirection.CLOSE)

    def test_roller_stop(self):
        d = make_gen1()
        d.roller_stop()
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["go"] == str(Gen1RollerDirection.STOP)

    def test_roller_to_position(self):
        d = make_gen1()
        d.roller_to_position(0, 50)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["go"] == str(Gen1RollerDirection.TO_POS)
        assert kwargs["params"]["roller_pos"] == 50

    def test_calibrate_roller_url(self):
        d = make_gen1()
        d.calibrate_roller(0)
        _, url, _ = last_call(d)
        assert url.endswith("/roller/0/calibrate")

    def test_roller_open_with_duration(self):
        d = make_gen1()
        d.roller_open(0, duration=3000)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["duration"] == 3000


# ---------------------------------------------------------------------------
# Light
# ---------------------------------------------------------------------------

class TestLight:
    def test_get_light_url(self):
        d = make_gen1()
        d.get_light(0)
        _, url, _ = last_call(d)
        assert url.endswith("/light/0")

    def test_light_on_passes_turn(self):
        d = make_gen1()
        d.light_on(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["turn"] == "on"

    def test_light_off_passes_turn(self):
        d = make_gen1()
        d.light_off(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["turn"] == "off"

    def test_light_toggle_passes_turn(self):
        d = make_gen1()
        d.light_toggle(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["turn"] == "toggle"

    def test_set_light_strips_none(self):
        d = make_gen1()
        d.set_light(0, turn="on", brightness=80, mode=None)
        _, _, kwargs = last_call(d)
        assert "mode" not in kwargs["params"]
        assert kwargs["params"]["brightness"] == 80


# ---------------------------------------------------------------------------
# Meter / emeter
# ---------------------------------------------------------------------------

class TestMeters:
    def test_get_meter_url(self):
        d = make_gen1()
        d.get_meter(0)
        _, url, _ = last_call(d)
        assert url.endswith("/meter/0")

    def test_get_emeter_url(self):
        d = make_gen1()
        d.get_emeter(1)
        _, url, _ = last_call(d)
        assert url.endswith("/emeter/1")

    def test_reset_emeter_passes_param(self):
        d = make_gen1()
        d.reset_emeter(0)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["reset_totals"] == 1


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_get_settings_url(self):
        d = make_gen1()
        d.get_settings()
        _, url, _ = last_call(d)
        assert url.endswith("/settings")

    def test_set_settings_passes_params(self):
        d = make_gen1()
        d.set_settings(name="MyDevice")
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["name"] == "MyDevice"

    def test_set_settings_strips_none(self):
        d = make_gen1()
        d.set_settings(name="X", timezone=None)
        _, _, kwargs = last_call(d)
        assert "timezone" not in kwargs["params"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuth:
    def test_set_auth_enable_updates_session_auth(self):
        d = make_gen1()
        d.set_auth(enabled=True, username="admin", password="newpass")
        assert isinstance(d.session.auth, HTTPBasicAuth)
        assert d._password == "newpass"

    def test_set_auth_disable_clears_session_auth(self):
        d = make_gen1("192.168.1.1", password="old")
        d.set_auth(enabled=False)
        assert d.session.auth is None
        assert d._password is None

    def test_set_auth_calls_login_endpoint(self):
        d = make_gen1()
        d.set_auth(enabled=True, password="p")
        _, url, _ = last_call(d)
        assert url.endswith("/settings/login")


# ---------------------------------------------------------------------------
# Cloud
# ---------------------------------------------------------------------------

class TestCloud:
    def test_get_cloud_settings_url(self):
        d = make_gen1()
        d.get_cloud_settings()
        _, url, _ = last_call(d)
        assert url.endswith("/settings/cloud")

    def test_set_cloud_enabled(self):
        d = make_gen1()
        d.set_cloud(True)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["enabled"] == "true"

    def test_set_cloud_disabled(self):
        d = make_gen1()
        d.set_cloud(False)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["enabled"] == "false"


# ---------------------------------------------------------------------------
# OTA / firmware
# ---------------------------------------------------------------------------

class TestOTA:
    def test_get_ota_url(self):
        d = make_gen1()
        d.get_ota_status()
        _, url, _ = last_call(d)
        assert url.endswith("/ota")

    def test_check_update_url(self):
        d = make_gen1()
        d.check_update()
        _, url, _ = last_call(d)
        assert url.endswith("/ota/check")

    def test_update_firmware_default(self):
        d = make_gen1()
        d.update_firmware()
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["update"] == 1

    def test_update_firmware_beta(self):
        d = make_gen1()
        d.update_firmware(beta=True)
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["beta"] == 1

    def test_update_firmware_custom_url(self):
        d = make_gen1()
        d.update_firmware(url="http://custom/fw.bin")
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["url"] == "http://custom/fw.bin"


# ---------------------------------------------------------------------------
# Reboot / reset
# ---------------------------------------------------------------------------

class TestRebootReset:
    def test_reboot_url(self):
        d = make_gen1()
        d.reboot()
        _, url, _ = last_call(d)
        assert url.endswith("/reboot")

    def test_factory_reset_passes_reset_param(self):
        d = make_gen1()
        d.factory_reset()
        _, _, kwargs = last_call(d)
        assert kwargs["params"]["reset"] == 1


# ---------------------------------------------------------------------------
# Debug log
# ---------------------------------------------------------------------------

class TestDebugLog:
    def test_get_debug_log_index_0(self):
        d = make_gen1()
        resp = MagicMock()
        resp.ok = True
        resp.text = "log text"
        d._session.get.return_value = resp
        result = d.get_debug_log(0)
        call_args = d._session.get.call_args[0]
        assert call_args[0].endswith("/debug/log")
        assert result == "log text"

    def test_get_debug_log_index_1(self):
        d = make_gen1()
        resp = MagicMock()
        resp.ok = True
        resp.text = "log1 text"
        d._session.get.return_value = resp
        d.get_debug_log(1)
        call_args = d._session.get.call_args[0]
        assert call_args[0].endswith("/debug/log1")
