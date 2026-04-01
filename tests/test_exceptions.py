"""Tests for shelly/exceptions.py"""

from shelly.exceptions import (ShellyAuthError, ShellyCloudError, ShellyConnectionError, ShellyDiscoveryError,
                               ShellyError, ShellyHTTPError, ShellyRPCError, ShellyTimeoutError, )


class TestExceptionHierarchy:
    def test_all_exceptions_derive_from_shelly_error(self):
        for cls in (ShellyConnectionError, ShellyAuthError, ShellyTimeoutError, ShellyHTTPError, ShellyRPCError,
                    ShellyCloudError, ShellyDiscoveryError,):
            assert issubclass(cls, ShellyError)

    def test_shelly_error_derives_from_exception(self):
        assert issubclass(ShellyError, Exception)

    def test_instances_are_catchable_as_shelly_error(self):
        for exc in (ShellyConnectionError("x"), ShellyAuthError("x"), ShellyTimeoutError("x"), ShellyHTTPError(500),
                    ShellyRPCError(-32600, "invalid"), ShellyCloudError("DEVICE_OFFLINE"), ShellyDiscoveryError("x"),):
            assert isinstance(exc, ShellyError)


class TestShellyHTTPError:
    def test_status_code_attribute(self):
        err = ShellyHTTPError(404, "Not Found")
        assert err.status_code == 404

    def test_str_contains_status_and_message(self):
        err = ShellyHTTPError(500, "Internal Server Error")
        assert "500" in str(err)
        assert "Internal Server Error" in str(err)

    def test_message_defaults_to_empty(self):
        err = ShellyHTTPError(403)
        assert err.status_code == 403
        assert "403" in str(err)


class TestShellyRPCError:
    def test_code_attribute(self):
        err = ShellyRPCError(-32600, "Invalid Request")
        assert err.code == -32600

    def test_str_contains_code_and_message(self):
        err = ShellyRPCError(-32601, "Method not found")
        assert "-32601" in str(err)
        assert "Method not found" in str(err)

    def test_zero_code(self):
        err = ShellyRPCError(0, "")
        assert err.code == 0


class TestShellyCloudError:
    def test_error_attribute(self):
        err = ShellyCloudError("DEVICE_OFFLINE")
        assert err.error == "DEVICE_OFFLINE"

    def test_messages_attribute_defaults_to_empty_list(self):
        err = ShellyCloudError("BAD_REQUEST")
        assert err.messages == []

    def test_messages_attribute_populated(self):
        err = ShellyCloudError("BAD_REQUEST", ["field 'on' is required"])
        assert err.messages == ["field 'on' is required"]

    def test_messages_none_becomes_empty_list(self):
        err = ShellyCloudError("BAD_REQUEST", None)
        assert err.messages == []

    def test_str_contains_error_string(self):
        err = ShellyCloudError("DEVICE_OFFLINE")
        assert "DEVICE_OFFLINE" in str(err)

    def test_str_contains_messages_when_present(self):
        err = ShellyCloudError("BAD_REQUEST", ["invalid channel"])
        assert "invalid channel" in str(err)

    def test_multiple_messages(self):
        err = ShellyCloudError("BAD_REQUEST", ["msg1", "msg2"])
        assert err.messages == ["msg1", "msg2"]
