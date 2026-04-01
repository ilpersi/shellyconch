"""Tests for shelly/base.py — BaseShelly HTTP helpers and error mapping."""

from unittest.mock import MagicMock

import pytest
import requests
from shelly.base import BaseShelly
from shelly.exceptions import (ShellyAuthError, ShellyConnectionError, ShellyHTTPError, ShellyTimeoutError, )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_base(host="192.168.1.1", port=80, timeout=10.0):
    b = BaseShelly(host, port, timeout)
    b._session = MagicMock()
    return b


def _resp(status_code=200, text="", json_data=None, content=b""):
    r = MagicMock()
    r.status_code = status_code
    r.ok = status_code < 400
    r.text = text
    if json_data is not None:
        r.json.return_value = json_data
        r.content = b"x"  # non-empty
    else:
        r.content = content
    return r


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------

class TestSession:
    def test_session_is_lazy(self):
        b = BaseShelly("host")
        assert b._session is None
        sess = b.session
        assert isinstance(sess, requests.Session)
        assert b._session is sess

    def test_session_returns_same_instance(self):
        b = BaseShelly("host")
        assert b.session is b.session

    def test_close_clears_session(self):
        b = make_base()
        b.close()
        assert b._session is None

    def test_close_when_no_session_is_noop(self):
        b = BaseShelly("host")
        b.close()  # should not raise

    def test_context_manager_calls_close(self):
        b = make_base()
        with b:
            pass
        assert b._session is None


# ---------------------------------------------------------------------------
# base_url
# ---------------------------------------------------------------------------

class TestBaseUrl:
    def test_default_port(self):
        b = BaseShelly("192.168.1.1")
        assert b.base_url == "http://192.168.1.1:80"

    def test_custom_port(self):
        b = BaseShelly("192.168.1.1", port=8080)
        assert b.base_url == "http://192.168.1.1:8080"


# ---------------------------------------------------------------------------
# Error mapping in _request
# ---------------------------------------------------------------------------

class TestRequestErrorMapping:
    def test_401_raises_shelly_auth_error(self):
        b = make_base()
        b._session.request.return_value = _resp(status_code=401)
        with pytest.raises(ShellyAuthError):
            b._get("/test")

    def test_non_2xx_raises_shelly_http_error(self):
        b = make_base()
        b._session.request.return_value = _resp(status_code=500, text="err")
        with pytest.raises(ShellyHTTPError) as exc_info:
            b._get("/test")
        assert exc_info.value.status_code == 500

    def test_404_raises_shelly_http_error(self):
        b = make_base()
        b._session.request.return_value = _resp(status_code=404)
        with pytest.raises(ShellyHTTPError) as exc_info:
            b._get("/test")
        assert exc_info.value.status_code == 404

    def test_connection_error_raises_shelly_connection_error(self):
        b = make_base()
        b._session.request.side_effect = requests.exceptions.ConnectionError("refused")
        with pytest.raises(ShellyConnectionError):
            b._get("/test")

    def test_timeout_raises_shelly_timeout_error(self):
        b = make_base()
        b._session.request.side_effect = requests.exceptions.Timeout("timed out")
        with pytest.raises(ShellyTimeoutError):
            b._get("/test")


# ---------------------------------------------------------------------------
# Successful responses
# ---------------------------------------------------------------------------

class TestRequestSuccess:
    def test_json_response_returned(self):
        b = make_base()
        b._session.request.return_value = _resp(json_data={"key": "value"})
        result = b._get("/test")
        assert result == {"key": "value"}

    def test_empty_content_returns_empty_dict(self):
        b = make_base()
        r = MagicMock()
        r.status_code = 200
        r.ok = True
        r.content = b""
        b._session.request.return_value = r
        result = b._get("/test")
        assert result == {}

    def test_default_timeout_applied(self):
        b = make_base(timeout=7.5)
        b._session.request.return_value = _resp(json_data={})
        b._get("/test")
        call_kwargs = b._session.request.call_args[1]
        assert call_kwargs["timeout"] == 7.5

    def test_get_builds_correct_url(self):
        b = make_base(host="10.0.0.1", port=80)
        b._session.request.return_value = _resp(json_data={})
        b._get("/relay/0")
        args = b._session.request.call_args[0]
        assert args[0] == "GET"
        assert args[1] == "http://10.0.0.1:80/relay/0"

    def test_post_sends_json_body(self):
        b = make_base()
        b._session.request.return_value = _resp(json_data={})
        b._post("/rpc", json={"id": 1})
        call_kwargs = b._session.request.call_args[1]
        assert call_kwargs["json"] == {"id": 1}


# ---------------------------------------------------------------------------
# repr
# ---------------------------------------------------------------------------

class TestRepr:
    def test_repr(self):
        b = BaseShelly("192.168.1.100")
        assert "BaseShelly" in repr(b)
        assert "192.168.1.100" in repr(b)
