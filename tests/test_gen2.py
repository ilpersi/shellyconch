"""Tests for shelly/gen2.py — ShellyGen2 JSON-RPC transport and methods."""

import hashlib
from unittest.mock import MagicMock

import pytest
from shelly.auth import ShellyDigestAuth
from shelly.exceptions import ShellyRPCError
from shelly.gen2 import ShellyGen2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_gen2(host="192.168.1.101", password=None):
    device = ShellyGen2(host, password=password)
    device._session = MagicMock()
    return device


def rpc_ok(result):
    """Mock a successful JSON-RPC response frame."""
    r = MagicMock()
    r.status_code = 200
    r.ok = True
    r.content = b"x"
    r.json.return_value = {"id": 1, "result": result}
    return r


def rpc_error(code, message):
    """Mock an error JSON-RPC response frame."""
    r = MagicMock()
    r.status_code = 200
    r.ok = True
    r.content = b"x"
    r.json.return_value = {"id": 1, "error": {"code": code, "message": message}}
    return r


def last_post_body(device):
    """Return the JSON body sent in the most recent POST."""
    call_kwargs = device._session.request.call_args[1]
    return call_kwargs["json"]


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestInit:
    def test_no_password_no_auth(self):
        d = ShellyGen2("192.168.1.1")
        assert d._password is None

    def test_password_sets_digest_auth(self):
        d = ShellyGen2("192.168.1.1", password="secret")
        assert isinstance(d.session.auth, ShellyDigestAuth)


# ---------------------------------------------------------------------------
# call() — JSON-RPC frame construction
# ---------------------------------------------------------------------------

class TestCall:
    def test_posts_to_rpc_endpoint(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"status": "ok"})
        d.call("Shelly.GetStatus")
        args = d._session.request.call_args[0]
        assert args[0] == "POST"
        assert args[1].endswith("/rpc")

    def test_frame_contains_method(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.call("Switch.Set", {"id": 0, "on": True})
        body = last_post_body(d)
        assert body["method"] == "Switch.Set"

    def test_frame_contains_params(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.call("Switch.Set", {"id": 0, "on": True})
        body = last_post_body(d)
        assert body["params"] == {"id": 0, "on": True}

    def test_frame_contains_id(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.call("Shelly.GetStatus")
        body = last_post_body(d)
        assert "id" in body
        assert isinstance(body["id"], int)

    def test_frame_id_is_monotonically_increasing(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.call("A")
        id1 = last_post_body(d)["id"]
        d.call("B")
        id2 = last_post_body(d)["id"]
        assert id2 > id1

    def test_no_params_omits_params_key(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.call("Shelly.GetStatus")
        body = last_post_body(d)
        assert "params" not in body

    def test_returns_result_value(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"output": True})
        result = d.call("Switch.GetStatus", {"id": 0})
        assert result == {"output": True}

    def test_raises_shelly_rpc_error_on_error_frame(self):
        d = make_gen2()
        d._session.request.return_value = rpc_error(-32601, "Method not found")
        with pytest.raises(ShellyRPCError) as exc_info:
            d.call("Unknown.Method")
        assert exc_info.value.code == -32601

    def test_rpc_error_message_in_exception(self):
        d = make_gen2()
        d._session.request.return_value = rpc_error(-32600, "Invalid Request")
        with pytest.raises(ShellyRPCError) as exc_info:
            d.call("Bad")
        assert "Invalid Request" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Device info / status
# ---------------------------------------------------------------------------

class TestDeviceInfo:
    def test_get_info_calls_shelly_get_device_info(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"mac": "AA:BB:CC:DD:EE:FF"})
        d.get_info()
        body = last_post_body(d)
        assert body["method"] == "Shelly.GetDeviceInfo"

    def test_get_status_calls_shelly_get_status(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"sys": {}})
        d.get_status()
        body = last_post_body(d)
        assert body["method"] == "Shelly.GetStatus"


# ---------------------------------------------------------------------------
# Switch component
# ---------------------------------------------------------------------------

class TestSwitch:
    def test_switch_set_on(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"was_on": False})
        d.switch_set(0, on=True)
        body = last_post_body(d)
        assert body["method"] == "Switch.Set"
        assert body["params"] == {"id": 0, "on": True}

    def test_switch_set_with_toggle_after(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({})
        d.switch_set(0, on=True, toggle_after=30)
        body = last_post_body(d)
        assert body["params"]["toggle_after"] == 30

    def test_switch_toggle(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"was_on": True})
        d.switch_toggle(0)
        body = last_post_body(d)
        assert body["method"] == "Switch.Toggle"
        assert body["params"]["id"] == 0

    def test_switch_get_status(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"output": True})
        d.switch_get_status(0)
        body = last_post_body(d)
        assert body["method"] == "Switch.GetStatus"
        assert body["params"]["id"] == 0


# ---------------------------------------------------------------------------
# Cover component
# ---------------------------------------------------------------------------

class TestCover:
    def test_cover_open(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.cover_open(0)
        body = last_post_body(d)
        assert body["method"] == "Cover.Open"
        assert body["params"]["id"] == 0

    def test_cover_close(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.cover_close(0)
        body = last_post_body(d)
        assert body["method"] == "Cover.Close"

    def test_cover_stop(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.cover_stop(0)
        body = last_post_body(d)
        assert body["method"] == "Cover.Stop"

    def test_cover_goto_position(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.cover_goto_position(0, pos=75)
        body = last_post_body(d)
        assert body["method"] == "Cover.GoToPosition"
        assert body["params"]["pos"] == 75

    def test_cover_get_status(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"state": "open"})
        d.cover_get_status(0)
        body = last_post_body(d)
        assert body["method"] == "Cover.GetStatus"

    def test_cover_calibrate(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.cover_calibrate(0)
        body = last_post_body(d)
        assert body["method"] == "Cover.Calibrate"


# ---------------------------------------------------------------------------
# Light component
# ---------------------------------------------------------------------------

class TestLight:
    def test_light_set_on(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({})
        d.light_set(0, on=True)
        body = last_post_body(d)
        assert body["method"] == "Light.Set"
        assert body["params"]["id"] == 0
        assert body["params"]["on"] is True

    def test_light_set_brightness(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({})
        d.light_set(0, on=True, brightness=60)
        body = last_post_body(d)
        assert body["params"]["brightness"] == 60

    def test_light_toggle(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({})
        d.light_toggle(0)
        body = last_post_body(d)
        assert body["method"] == "Light.Toggle"

    def test_light_get_status(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"output": True})
        d.light_get_status(0)
        body = last_post_body(d)
        assert body["method"] == "Light.GetStatus"


# ---------------------------------------------------------------------------
# Cloud component
# ---------------------------------------------------------------------------

class TestCloud:
    def test_cloud_get_status(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"connected": True})
        d.cloud_get_status()
        body = last_post_body(d)
        assert body["method"] == "Cloud.GetStatus"

    def test_cloud_set_config(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({})
        d.cloud_set_config(enable=True)
        body = last_post_body(d)
        assert body["method"] == "Cloud.SetConfig"
        assert body["params"]["config"]["enable"] is True


# ---------------------------------------------------------------------------
# WiFi
# ---------------------------------------------------------------------------

class TestWifi:
    def test_wifi_scan(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"results": []})
        d.wifi_scan()
        body = last_post_body(d)
        assert body["method"] == "Wifi.Scan"


# ---------------------------------------------------------------------------
# Firmware
# ---------------------------------------------------------------------------

class TestFirmware:
    def test_check_for_update(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok({"stable": {}, "beta": {}})
        d.check_for_update()
        body = last_post_body(d)
        assert body["method"] == "Shelly.CheckForUpdate"

    def test_update_firmware_stable(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.update_firmware(stage="stable")
        body = last_post_body(d)
        assert body["method"] == "Shelly.Update"
        assert body["params"]["stage"] == "stable"

    def test_update_firmware_custom_url(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.update_firmware(url="http://custom/fw.zip")
        body = last_post_body(d)
        assert body["params"]["url"] == "http://custom/fw.zip"


# ---------------------------------------------------------------------------
# Reboot / reset
# ---------------------------------------------------------------------------

class TestReboot:
    def test_reboot(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.reboot()
        body = last_post_body(d)
        assert body["method"] == "Shelly.Reboot"

    def test_factory_reset(self):
        d = make_gen2()
        d._session.request.return_value = rpc_ok(None)
        d.factory_reset()
        body = last_post_body(d)
        assert body["method"] == "Shelly.FactoryReset"


# ---------------------------------------------------------------------------
# set_auth — two-request flow
# ---------------------------------------------------------------------------

class TestSetAuth:
    def test_set_auth_with_password_fetches_device_info_first(self):
        d = make_gen2()
        # First call returns device info, second call is SetAuth
        device_info = {"id": "shellyplus1-aabbcc", "auth_domain": "shellyplus1-aabbcc"}
        d._session.request.side_effect = [rpc_ok(device_info),  # get_info()
            rpc_ok(None),  # Shelly.SetAuth
        ]
        d.set_auth("newpass")
        calls = d._session.request.call_args_list
        assert len(calls) == 2
        first_body = calls[0][1]["json"]
        assert first_body["method"] == "Shelly.GetDeviceInfo"

    def test_set_auth_with_password_sends_correct_ha1(self):
        d = make_gen2()
        realm = "shellyplus1-aabbcc"
        device_info = {"id": realm, "auth_domain": realm}
        d._session.request.side_effect = [rpc_ok(device_info), rpc_ok(None), ]
        d.set_auth("mypassword")
        second_body = d._session.request.call_args_list[1][1]["json"]
        assert second_body["method"] == "Shelly.SetAuth"
        params = second_body["params"]
        expected_ha1 = hashlib.sha256(f"admin:{realm}:mypassword".encode()).hexdigest()
        assert params["ha1"] == expected_ha1
        assert params["realm"] == realm
        assert params["user"] == "admin"

    def test_set_auth_with_password_updates_session_auth(self):
        d = make_gen2()
        device_info = {"id": "testdev", "auth_domain": "testdev"}
        d._session.request.side_effect = [rpc_ok(device_info), rpc_ok(None), ]
        d.set_auth("newpass")
        assert isinstance(d.session.auth, ShellyDigestAuth)
        assert d._password == "newpass"

    def test_set_auth_none_clears_auth(self):
        d = make_gen2(password="oldpass")
        d._session.request.return_value = rpc_ok(None)
        d.set_auth(None)
        assert d.session.auth is None
        assert d._password is None
