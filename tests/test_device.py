"""Tests for shelly/device.py — ShellyDevice unified API and generation dispatch."""

from unittest.mock import MagicMock, patch

import pytest
import requests
from shelly.device import ShellyDevice
from shelly.exceptions import ShellyConnectionError
from shelly.gen1 import ShellyGen1
from shelly.gen2 import ShellyGen2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _gen1_mock():
    d = MagicMock(spec=ShellyGen1)
    d.host = "192.168.1.100"
    return d


def _gen2_mock():
    d = MagicMock(spec=ShellyGen2)
    d.host = "192.168.1.101"
    return d


def _shelly_resp(gen=2, mac="AABBCCDDEE00"):
    r = MagicMock()
    r.status_code = 200
    r.raise_for_status = MagicMock()
    r.json.return_value = {"gen": gen, "mac": mac}
    return r


# ---------------------------------------------------------------------------
# __init__ and underlying property
# ---------------------------------------------------------------------------

class TestInit:
    def test_underlying_returns_wrapped_device(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        assert sd.underlying is d

    def test_generation_is_none_until_accessed(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        assert sd._generation is None


# ---------------------------------------------------------------------------
# connect() classmethod
# ---------------------------------------------------------------------------

class TestConnect:
    @patch("shelly.device.requests.get")
    def test_connect_detects_gen1(self, mock_get):
        mock_get.return_value = _shelly_resp(gen=1)
        sd = ShellyDevice.connect("192.168.1.100")
        assert isinstance(sd.underlying, ShellyGen1)
        assert sd._generation == 1

    @patch("shelly.device.requests.get")
    def test_connect_detects_gen2(self, mock_get):
        mock_get.return_value = _shelly_resp(gen=2)
        sd = ShellyDevice.connect("192.168.1.101")
        assert isinstance(sd.underlying, ShellyGen2)
        assert sd._generation == 2

    @patch("shelly.device.requests.get")
    def test_connect_missing_gen_defaults_to_gen1(self, mock_get):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"mac": "AABB"}  # no 'gen' key
        mock_get.return_value = r
        sd = ShellyDevice.connect("192.168.1.100")
        assert isinstance(sd.underlying, ShellyGen1)

    @patch("shelly.device.requests.get")
    def test_connect_connection_error_raises_shelly_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("refused")
        with pytest.raises(ShellyConnectionError):
            ShellyDevice.connect("192.168.1.1")

    @patch("shelly.device.requests.get")
    def test_connect_timeout_raises_shelly_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("timed out")
        with pytest.raises(ShellyConnectionError):
            ShellyDevice.connect("192.168.1.1")

    @patch("shelly.device.requests.get")
    def test_connect_missing_mac_raises_shelly_connection_error(self, mock_get):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"gen": 2}  # no 'mac' key
        mock_get.return_value = r
        with pytest.raises(ShellyConnectionError):
            ShellyDevice.connect("192.168.1.1")

    @patch("shelly.device.requests.get")
    def test_connect_passes_password_to_gen2(self, mock_get):
        mock_get.return_value = _shelly_resp(gen=2)
        sd = ShellyDevice.connect("host", password="secret")
        assert sd.underlying._password == "secret"

    @patch("shelly.device.requests.get")
    def test_connect_passes_gen1_password(self, mock_get):
        mock_get.return_value = _shelly_resp(gen=1)
        sd = ShellyDevice.connect("host", gen1_password="gen1pass")
        assert sd.underlying._password == "gen1pass"

    @patch("shelly.device.requests.get")
    def test_connect_gen1_falls_back_to_password(self, mock_get):
        mock_get.return_value = _shelly_resp(gen=1)
        sd = ShellyDevice.connect("host", password="fallback")
        # gen1_password is None so it falls back to password
        assert sd.underlying._password == "fallback"


# ---------------------------------------------------------------------------
# generation property (lazy fetch for Gen2)
# ---------------------------------------------------------------------------

class TestGenerationProperty:
    def test_gen1_always_returns_1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        assert sd.generation == 1

    def test_gen2_fetches_from_device_info(self):
        d = _gen2_mock()
        d.get_info.return_value = {"gen": 3, "mac": "AA"}
        sd = ShellyDevice(d)
        assert sd.generation == 3

    def test_gen2_caches_generation_after_first_access(self):
        d = _gen2_mock()
        d.get_info.return_value = {"gen": 2, "mac": "AA"}
        sd = ShellyDevice(d)
        _ = sd.generation
        _ = sd.generation
        d.get_info.assert_called_once()

    def test_gen2_defaults_to_2_when_gen_absent(self):
        d = _gen2_mock()
        d.get_info.return_value = {"mac": "AA"}  # no 'gen' key
        sd = ShellyDevice(d)
        assert sd.generation == 2

    def test_pre_cached_generation_not_refetched(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd._generation = 4
        assert sd.generation == 4
        d.get_info.assert_not_called()


# ---------------------------------------------------------------------------
# get_info() normalization
# ---------------------------------------------------------------------------

class TestGetInfo:
    def test_gen1_normalized_keys(self):
        d = _gen1_mock()
        d.get_info.return_value = {"type": "SHSW-1", "mac": "AABBCC001122", "fw": "1.12.3", "auth": True, }
        sd = ShellyDevice(d)
        info = sd.get_info()
        assert info["mac"] == "AABBCC001122"
        assert info["model"] == "Shelly1"
        assert info["firmware"] == "1.12.3"
        assert info["generation"] == 1
        assert info["auth_enabled"] is True

    def test_gen1_unknown_type_uses_raw_type(self):
        d = _gen1_mock()
        d.get_info.return_value = {"type": "SHUNKNOWN", "mac": "AA", "fw": "1.0", "auth": False}
        sd = ShellyDevice(d)
        info = sd.get_info()
        assert info["model"] == "SHUNKNOWN"

    def test_gen2_normalized_keys(self):
        d = _gen2_mock()
        d.get_info.return_value = {"mac": "AABBCCDDEEFF", "model": "ShellyPlus1PM", "ver": "1.0.5", "gen": 2,
            "auth_en": True, }
        sd = ShellyDevice(d)
        info = sd.get_info()
        assert info["mac"] == "AABBCCDDEEFF"
        assert info["model"] == "ShellyPlus1PM"
        assert info["firmware"] == "1.0.5"
        assert info["generation"] == 2
        assert info["auth_enabled"] is True

    def test_gen2_caches_generation(self):
        d = _gen2_mock()
        d.get_info.return_value = {"mac": "AA", "model": "M", "ver": "1.0", "gen": 3, "auth_en": False}
        sd = ShellyDevice(d)
        sd.get_info()
        assert sd._generation == 3


# ---------------------------------------------------------------------------
# get_status — pass-through
# ---------------------------------------------------------------------------

class TestGetStatus:
    def test_gen1_delegates_to_underlying(self):
        d = _gen1_mock()
        d.get_status.return_value = {"relays": []}
        sd = ShellyDevice(d)
        sd.get_status()
        d.get_status.assert_called_once()

    def test_gen2_delegates_to_underlying(self):
        d = _gen2_mock()
        d.get_status.return_value = {"switch:0": {}}
        sd = ShellyDevice(d)
        sd.get_status()
        d.get_status.assert_called_once()


# ---------------------------------------------------------------------------
# Switch / relay dispatch
# ---------------------------------------------------------------------------

class TestSwitchDispatch:
    def test_turn_on_gen1_calls_relay_on(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.turn_on(0, timer=5)
        d.relay_on.assert_called_once_with(0, timer=5)

    def test_turn_on_gen2_calls_switch_set(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.turn_on(0, timer=5)
        d.switch_set.assert_called_once_with(0, on=True, toggle_after=5)

    def test_turn_off_gen1_calls_relay_off(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.turn_off(1)
        d.relay_off.assert_called_once_with(1, timer=None)

    def test_turn_off_gen2_calls_switch_set(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.turn_off(1)
        d.switch_set.assert_called_once_with(1, on=False, toggle_after=None)

    def test_toggle_gen1_calls_relay_toggle(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.toggle(0)
        d.relay_toggle.assert_called_once_with(0)

    def test_toggle_gen2_calls_switch_toggle(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.toggle(0)
        d.switch_toggle.assert_called_once_with(0)

    def test_get_switch_status_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.get_switch_status(0)
        d.get_relay.assert_called_once_with(0)

    def test_get_switch_status_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.get_switch_status(0)
        d.switch_get_status.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# Cover dispatch — including duration unit conversion
# ---------------------------------------------------------------------------

class TestCoverDispatch:
    def test_cover_open_gen1_converts_seconds_to_ms(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.cover_open(0, duration=2.5)
        d.roller_open.assert_called_once_with(0, duration=2500)

    def test_cover_open_gen1_no_duration(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.cover_open(0)
        d.roller_open.assert_called_once_with(0, duration=None)

    def test_cover_open_gen2_passes_seconds(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.cover_open(0, duration=3.0)
        d.cover_open.assert_called_once_with(0, duration=3.0)

    def test_cover_close_gen1_converts_duration(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.cover_close(0, duration=1.0)
        d.roller_close.assert_called_once_with(0, duration=1000)

    def test_cover_close_gen2_passes_seconds(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.cover_close(0, duration=1.5)
        d.cover_close.assert_called_once_with(0, duration=1.5)

    def test_cover_stop_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.cover_stop(0)
        d.roller_stop.assert_called_once_with(0)

    def test_cover_stop_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.cover_stop(0)
        d.cover_stop.assert_called_once_with(0)

    def test_cover_goto_position_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.cover_goto_position(0, pos=75)
        d.roller_to_position.assert_called_once_with(0, 75)

    def test_cover_goto_position_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.cover_goto_position(0, pos=75)
        d.cover_goto_position.assert_called_once_with(0, pos=75)

    def test_cover_calibrate_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.cover_calibrate(0)
        d.calibrate_roller.assert_called_once_with(0)

    def test_cover_calibrate_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.cover_calibrate(0)
        d.cover_calibrate.assert_called_once_with(0)

    def test_get_cover_status_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.get_cover_status(0)
        d.get_roller.assert_called_once_with(0)

    def test_get_cover_status_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.get_cover_status(0)
        d.cover_get_status.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# Light dispatch
# ---------------------------------------------------------------------------

class TestLightDispatch:
    def test_light_on_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.light_on(0, brightness=80)
        d.light_on.assert_called_once_with(0, brightness=80)

    def test_light_on_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.light_on(0, brightness=80)
        d.light_set.assert_called_once_with(0, on=True, brightness=80)

    def test_light_off_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.light_off(0)
        d.light_off.assert_called_once_with(0)

    def test_light_off_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.light_off(0)
        d.light_set.assert_called_once_with(0, on=False)

    def test_get_light_status_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.get_light_status(0)
        d.get_light.assert_called_once_with(0)

    def test_get_light_status_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.get_light_status(0)
        d.light_get_status.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# Firmware dispatch
# ---------------------------------------------------------------------------

class TestFirmwareDispatch:
    def test_check_for_update_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.check_for_update()
        d.check_update.assert_called_once()

    def test_check_for_update_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.check_for_update()
        d.check_for_update.assert_called_once()

    def test_update_firmware_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.update_firmware(beta=True)
        d.update_firmware.assert_called_once_with(url=None, beta=True)

    def test_update_firmware_gen2_stable(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.update_firmware()
        d.update_firmware.assert_called_once_with(stage="stable")

    def test_update_firmware_gen2_beta(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.update_firmware(beta=True)
        d.update_firmware.assert_called_once_with(stage="beta")

    def test_update_firmware_gen2_custom_url(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.update_firmware(url="http://custom/fw.zip")
        d.update_firmware.assert_called_once_with(url="http://custom/fw.zip")


# ---------------------------------------------------------------------------
# Cloud and auth dispatch
# ---------------------------------------------------------------------------

class TestCloudAuthDispatch:
    def test_get_cloud_status_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.get_cloud_status()
        d.get_cloud_settings.assert_called_once()

    def test_get_cloud_status_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.get_cloud_status()
        d.cloud_get_status.assert_called_once()

    def test_set_cloud_enabled_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.set_cloud_enabled(True)
        d.set_cloud.assert_called_once_with(True)

    def test_set_cloud_enabled_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.set_cloud_enabled(False)
        d.cloud_set_config.assert_called_once_with(enable=False)

    def test_set_auth_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.set_auth("newpass")
        d.set_auth.assert_called_once_with(enabled=True, username="admin", password="newpass")

    def test_set_auth_gen1_disable(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.set_auth(None)
        d.set_auth.assert_called_once_with(enabled=False, username="admin", password=None)

    def test_set_auth_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.set_auth("newpass")
        d.set_auth.assert_called_once_with("newpass")


# ---------------------------------------------------------------------------
# Reboot / reset
# ---------------------------------------------------------------------------

class TestReboot:
    def test_reboot_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.reboot()
        d.reboot.assert_called_once()

    def test_reboot_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.reboot()
        d.reboot.assert_called_once()

    def test_factory_reset_gen1(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd.factory_reset()
        d.factory_reset.assert_called_once()

    def test_factory_reset_gen2(self):
        d = _gen2_mock()
        sd = ShellyDevice(d)
        sd.factory_reset()
        d.factory_reset.assert_called_once()


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_context_manager_calls_close(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        with sd:
            pass
        d.close.assert_called_once()


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr_without_cached_generation(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        assert "ShellyDevice" in repr(sd)

    def test_repr_with_cached_generation(self):
        d = _gen1_mock()
        sd = ShellyDevice(d)
        sd._generation = 1
        assert "gen=1" in repr(sd)
