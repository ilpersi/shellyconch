"""Tests for shelly/cloud.py — ShellyCloud HTTP client and control methods."""

from unittest.mock import MagicMock

import pytest
import requests
from shelly.cloud import ShellyCloud
from shelly.exceptions import ShellyAuthError, ShellyCloudError, ShellyConnectionError, ShellyTimeoutError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SERVER = "shelly-13-eu.shelly.cloud"
AUTH_KEY = "testkey123"


def make_cloud():
    cloud = ShellyCloud(SERVER, AUTH_KEY)
    cloud._session = MagicMock()
    return cloud


def _ok(data=None):
    r = MagicMock()
    r.status_code = 200
    r.ok = True
    if data is None:
        r.content = b""
        r.json.side_effect = ValueError("no content")
    else:
        r.content = b"x"
        r.json.return_value = data
    return r


def _error(status_code, payload=None):
    r = MagicMock()
    r.status_code = status_code
    r.ok = False
    r.text = "error"
    if payload:
        r.json.return_value = payload
    else:
        r.json.side_effect = ValueError("no json")
    return r


def last_post(cloud):
    """Return (url, json_body, params) from the most recent session.post call."""
    call = cloud._session.post.call_args
    return call[0][0], call[1].get("json", {}), call[1].get("params", {})


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestInit:
    def test_strips_trailing_slash_from_server(self):
        c = ShellyCloud("server.com/", "key")
        assert c._server == "server.com"

    def test_base_url(self):
        c = ShellyCloud("server.com", "key")
        assert c._base_url == "https://server.com/v2/devices/api/"

    def test_repr(self):
        c = ShellyCloud("server.com", "key")
        assert "server.com" in repr(c)


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSession:
    def test_session_is_lazy(self):
        c = ShellyCloud("s", "k")
        assert c._session is None
        sess = c.session
        assert isinstance(sess, requests.Session)

    def test_close_clears_session(self):
        c = make_cloud()
        c.close()
        assert c._session is None

    def test_context_manager_calls_close(self):
        c = make_cloud()
        with c:
            pass
        assert c._session is None


# ---------------------------------------------------------------------------
# _post() — request construction
# ---------------------------------------------------------------------------

class TestPost:
    def test_sends_to_correct_url(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c._post("set/switch", {"id": "abc"})
        url, _, _ = last_post(c)
        assert url == f"https://{SERVER}/v2/devices/api/set/switch"

    def test_sends_auth_key_as_query_param(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c._post("get", {"ids": ["abc"]})
        _, _, params = last_post(c)
        assert params["auth_key"] == AUTH_KEY

    def test_sends_body_as_json(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c._post("set/switch", {"id": "abc", "on": True})
        _, body, _ = last_post(c)
        assert body == {"id": "abc", "on": True}

    def test_empty_response_returns_empty_dict(self):
        c = make_cloud()
        c._session.post.return_value = _ok()  # no content
        result = c._post("set/switch", {})
        assert result == {}

    def test_json_response_returned(self):
        c = make_cloud()
        c._session.post.return_value = _ok(data=[{"id": "abc"}])
        result = c._post("get", {})
        assert result == [{"id": "abc"}]

    def test_401_raises_shelly_auth_error(self):
        c = make_cloud()
        c._session.post.return_value = _error(401)
        with pytest.raises(ShellyAuthError):
            c._post("set/switch", {})

    def test_non_2xx_raises_shelly_cloud_error(self):
        c = make_cloud()
        c._session.post.return_value = _error(400, {"error": "BAD_REQUEST", "data": {"messages": ["invalid id"]}})
        with pytest.raises(ShellyCloudError) as exc_info:
            c._post("set/switch", {})
        assert exc_info.value.error == "BAD_REQUEST"
        assert "invalid id" in exc_info.value.messages

    def test_non_2xx_no_json_raises_shelly_cloud_error(self):
        c = make_cloud()
        c._session.post.return_value = _error(500)
        with pytest.raises(ShellyCloudError):
            c._post("set/switch", {})

    def test_connection_error_raises_shelly_connection_error(self):
        c = make_cloud()
        c._session.post.side_effect = requests.exceptions.ConnectionError("refused")
        with pytest.raises(ShellyConnectionError):
            c._post("get", {})

    def test_timeout_raises_shelly_timeout_error(self):
        c = make_cloud()
        c._session.post.side_effect = requests.exceptions.Timeout("timed out")
        with pytest.raises(ShellyTimeoutError):
            c._post("get", {})


# ---------------------------------------------------------------------------
# get_devices_state
# ---------------------------------------------------------------------------

class TestGetDevicesState:
    def test_posts_to_get_endpoint(self):
        c = make_cloud()
        c._session.post.return_value = _ok(data=[])
        c.get_devices_state(["abc123"])
        url, _, _ = last_post(c)
        assert url.endswith("/get")

    def test_ids_in_body(self):
        c = make_cloud()
        c._session.post.return_value = _ok(data=[])
        c.get_devices_state(["abc", "def"])
        _, body, _ = last_post(c)
        assert body["ids"] == ["abc", "def"]

    def test_select_included_when_provided(self):
        c = make_cloud()
        c._session.post.return_value = _ok(data=[])
        c.get_devices_state(["abc"], select=["status"])
        _, body, _ = last_post(c)
        assert body["select"] == ["status"]

    def test_pick_included_when_provided(self):
        c = make_cloud()
        c._session.post.return_value = _ok(data=[])
        c.get_devices_state(["abc"], pick={"status": ["sys"]})
        _, body, _ = last_post(c)
        assert body["pick"] == {"status": ["sys"]}

    def test_empty_ids_raises_value_error(self):
        c = make_cloud()
        with pytest.raises(ValueError, match="at least one"):
            c.get_devices_state([])

    def test_more_than_10_ids_raises_value_error(self):
        c = make_cloud()
        with pytest.raises(ValueError, match="10"):
            c.get_devices_state([str(i) for i in range(11)])


# ---------------------------------------------------------------------------
# set_switch / turn_on / turn_off
# ---------------------------------------------------------------------------

class TestSetSwitch:
    def test_set_switch_posts_to_set_switch(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_switch("abc123", on=True)
        url, _, _ = last_post(c)
        assert url.endswith("/set/switch")

    def test_set_switch_body_fields(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_switch("abc123", on=True, channel=1)
        _, body, _ = last_post(c)
        assert body["id"] == "abc123"
        assert body["on"] is True
        assert body["channel"] == 1

    def test_set_switch_toggle_after(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_switch("abc123", on=True, toggle_after=60)
        _, body, _ = last_post(c)
        assert body["toggle_after"] == 60

    def test_turn_on_sends_on_true(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.turn_on("abc123")
        _, body, _ = last_post(c)
        assert body["on"] is True

    def test_turn_off_sends_on_false(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.turn_off("abc123")
        _, body, _ = last_post(c)
        assert body["on"] is False


# ---------------------------------------------------------------------------
# set_cover / cover convenience methods
# ---------------------------------------------------------------------------

class TestSetCover:
    def test_set_cover_posts_to_set_cover(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_cover("abc", position="open")
        url, _, _ = last_post(c)
        assert url.endswith("/set/cover")

    def test_set_cover_position_in_body(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_cover("abc", position="open")
        _, body, _ = last_post(c)
        assert body["position"] == "open"

    def test_set_cover_numeric_position(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_cover("abc", position=50)
        _, body, _ = last_post(c)
        assert body["position"] == 50

    def test_set_cover_relative(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_cover("abc", relative=20)
        _, body, _ = last_post(c)
        assert body["relative"] == 20

    def test_set_cover_slat_position(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_cover("abc", slat_position=45)
        _, body, _ = last_post(c)
        assert body["slatPosition"] == 45

    def test_set_cover_slat_relative(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_cover("abc", slat_relative=-10)
        _, body, _ = last_post(c)
        assert body["slatRelative"] == -10

    def test_position_and_relative_are_mutually_exclusive(self):
        c = make_cloud()
        with pytest.raises(ValueError, match="mutually exclusive"):
            c.set_cover("abc", position="open", relative=10)

    def test_slat_position_and_slat_relative_are_mutually_exclusive(self):
        c = make_cloud()
        with pytest.raises(ValueError, match="mutually exclusive"):
            c.set_cover("abc", slat_position=50, slat_relative=10)

    def test_cover_open_calls_set_cover_with_open(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.cover_open("abc")
        _, body, _ = last_post(c)
        assert body["position"] == "open"

    def test_cover_close_calls_set_cover_with_close(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.cover_close("abc")
        _, body, _ = last_post(c)
        assert body["position"] == "close"

    def test_cover_stop_calls_set_cover_with_stop(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.cover_stop("abc")
        _, body, _ = last_post(c)
        assert body["position"] == "stop"

    def test_cover_goto_position_sends_numeric_position(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.cover_goto_position("abc", pos=75)
        _, body, _ = last_post(c)
        assert body["position"] == 75

    def test_cover_open_with_duration(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.cover_open("abc", duration=5.0)
        _, body, _ = last_post(c)
        assert body["duration"] == 5.0


# ---------------------------------------------------------------------------
# set_light / light convenience methods
# ---------------------------------------------------------------------------

class TestSetLight:
    def test_set_light_posts_to_set_light(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_light("abc", on=True)
        url, _, _ = last_post(c)
        assert url.endswith("/set/light")

    def test_set_light_body_has_id_and_channel(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_light("abc", channel=1, on=True)
        _, body, _ = last_post(c)
        assert body["id"] == "abc"
        assert body["channel"] == 1

    def test_set_light_optional_params(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_light("abc", on=True, brightness=80, temperature=3000, red=255, green=0, blue=128)
        _, body, _ = last_post(c)
        assert body["brightness"] == 80
        assert body["temperature"] == 3000
        assert body["red"] == 255
        assert body["green"] == 0
        assert body["blue"] == 128

    def test_set_light_omits_none_params(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_light("abc", on=True)
        _, body, _ = last_post(c)
        assert "brightness" not in body
        assert "temperature" not in body

    def test_light_on_sends_on_true(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.light_on("abc", brightness=50)
        _, body, _ = last_post(c)
        assert body["on"] is True
        assert body["brightness"] == 50

    def test_light_off_sends_on_false(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.light_off("abc")
        _, body, _ = last_post(c)
        assert body["on"] is False


# ---------------------------------------------------------------------------
# set_groups
# ---------------------------------------------------------------------------

class TestSetGroups:
    def test_set_groups_posts_to_set_groups(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        c.set_groups(switch={"ids": ["abc_0"], "command": {"on": True}})
        url, _, _ = last_post(c)
        assert url.endswith("/set/groups")

    def test_set_groups_switch_body(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        group = {"ids": ["abc_0", "def_0"], "command": {"on": True}}
        c.set_groups(switch=group)
        _, body, _ = last_post(c)
        assert body["switch"] == group

    def test_set_groups_cover_body(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        group = {"ids": ["abc_0"], "command": {"position": "open"}}
        c.set_groups(cover=group)
        _, body, _ = last_post(c)
        assert body["cover"] == group

    def test_set_groups_light_body(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        group = {"ids": ["abc_0"], "command": {"on": True, "brightness": 75}}
        c.set_groups(light=group)
        _, body, _ = last_post(c)
        assert body["light"] == group

    def test_set_groups_multiple_types(self):
        c = make_cloud()
        c._session.post.return_value = _ok()
        sw = {"ids": ["abc_0"], "command": {"on": True}}
        cv = {"ids": ["def_0"], "command": {"position": "close"}}
        c.set_groups(switch=sw, cover=cv)
        _, body, _ = last_post(c)
        assert "switch" in body
        assert "cover" in body
        assert "light" not in body

    def test_set_groups_no_args_raises_value_error(self):
        c = make_cloud()
        with pytest.raises(ValueError, match="at least one"):
            c.set_groups()

    def test_set_groups_returns_empty_dict_on_success(self):
        c = make_cloud()
        c._session.post.return_value = _ok()  # empty response
        result = c.set_groups(switch={"ids": ["abc_0"], "command": {"on": True}})
        assert result == {}

    def test_set_groups_returns_failed_commands_on_partial_failure(self):
        c = make_cloud()
        c._session.post.return_value = _ok(data={"failedCommands": {"abc_0": "DEVICE_OFFLINE"}})
        result = c.set_groups(switch={"ids": ["abc_0"], "command": {"on": True}})
        assert "failedCommands" in result
        assert result["failedCommands"]["abc_0"] == "DEVICE_OFFLINE"
