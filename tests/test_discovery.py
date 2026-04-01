"""Tests for shelly/discovery.py — _txt_gen, _probe, and ShellyListener."""

import threading
from unittest.mock import MagicMock, patch

from shelly.discovery import ShellyListener, _probe, _txt_gen
from shelly.gen1 import ShellyGen1
from shelly.gen2 import ShellyGen2


# ---------------------------------------------------------------------------
# _txt_gen
# ---------------------------------------------------------------------------

class TestTxtGen:
    def test_bytes_key_bytes_value(self):
        assert _txt_gen({b"gen": b"2"}) == 2

    def test_str_key_str_value(self):
        assert _txt_gen({"gen": "3"}) == 3

    def test_case_insensitive_key(self):
        assert _txt_gen({b"Gen": b"1"}) == 1

    def test_missing_gen_returns_none(self):
        assert _txt_gen({"model": "Plus1PM"}) is None

    def test_none_properties_returns_none(self):
        assert _txt_gen(None) is None

    def test_empty_properties_returns_none(self):
        assert _txt_gen({}) is None

    def test_invalid_value_returns_none(self):
        assert _txt_gen({b"gen": b"invalid"}) is None


# ---------------------------------------------------------------------------
# _probe
# ---------------------------------------------------------------------------

def _probe_ok_resp(gen=2):
    r = MagicMock()
    r.raise_for_status = MagicMock()
    r.json.return_value = {"mac": "AABBCC001122", "gen": gen}
    return r


class TestProbe:
    @patch("shelly.discovery.requests.get")
    def test_probe_gen2_returns_shelly_gen2(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=2)
        device = _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert isinstance(device, ShellyGen2)

    @patch("shelly.discovery.requests.get")
    def test_probe_gen1_returns_shelly_gen1(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=1)
        device = _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert isinstance(device, ShellyGen1)

    @patch("shelly.discovery.requests.get")
    def test_probe_no_gen_field_defaults_to_gen1(self, mock_get):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"mac": "AA"}  # no gen field
        mock_get.return_value = r
        device = _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert isinstance(device, ShellyGen1)

    @patch("shelly.discovery.requests.get")
    def test_probe_no_gen_but_txt_gen_2_returns_gen2(self, mock_get):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"mac": "AA"}  # no gen in HTTP response
        mock_get.return_value = r
        device = _probe("192.168.1.1", 80, txt_gen=2, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert isinstance(device, ShellyGen2)

    @patch("shelly.discovery.requests.get")
    def test_probe_http_response_gen_overrides_txt_gen(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=1)  # HTTP says gen 1
        device = _probe("192.168.1.1", 80, txt_gen=2, password=None,  # TXT says gen 2
                        gen1_password=None, gen1_username="admin", http_timeout=5.0)
        assert isinstance(device, ShellyGen1)

    @patch("shelly.discovery.requests.get")
    def test_probe_missing_mac_returns_none(self, mock_get):
        r = MagicMock()
        r.raise_for_status = MagicMock()
        r.json.return_value = {"gen": 2}  # no mac
        mock_get.return_value = r
        device = _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert device is None

    @patch("shelly.discovery.requests.get")
    def test_probe_exception_returns_none(self, mock_get):
        mock_get.side_effect = Exception("connection refused")
        device = _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert device is None

    @patch("shelly.discovery.requests.get")
    def test_probe_sets_correct_host(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=2)
        device = _probe("10.0.0.5", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert device.host == "10.0.0.5"

    @patch("shelly.discovery.requests.get")
    def test_probe_passes_password_to_gen2(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=2)
        device = _probe("192.168.1.1", 80, txt_gen=None, password="secret", gen1_password=None, gen1_username="admin",
                        http_timeout=5.0)
        assert device._password == "secret"

    @patch("shelly.discovery.requests.get")
    def test_probe_passes_gen1_password(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=1)
        device = _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password="gen1pass", gen1_username="admin",
                        http_timeout=5.0)
        assert device._password == "gen1pass"

    @patch("shelly.discovery.requests.get")
    def test_probe_probes_shelly_endpoint(self, mock_get):
        mock_get.return_value = _probe_ok_resp(gen=2)
        _probe("192.168.1.1", 80, txt_gen=None, password=None, gen1_password=None, gen1_username="admin",
               http_timeout=5.0)
        called_url = mock_get.call_args[0][0]
        assert called_url == "http://192.168.1.1:80/shelly"


# ---------------------------------------------------------------------------
# ShellyListener helpers
# ---------------------------------------------------------------------------

def _make_listener(devices=None, on_device_found=None, include_updates=False):
    lock = threading.Lock()
    discovered = set()
    devs = devices if devices is not None else []
    return ShellyListener(lock=lock, discovered_hosts=discovered, devices=devs, password=None, gen1_password=None,
        gen1_username="admin", http_timeout=5.0, include_updates=include_updates,
        on_device_found=on_device_found, ), discovered, devs


def _service_info(host="192.168.1.1", server="shellyplus1pm-aabbcc.local.", port=80, properties=None):
    info = MagicMock()
    info.parsed_addresses.return_value = [host]
    info.server = server
    info.port = port
    info.properties = properties or {}
    return info


# ---------------------------------------------------------------------------
# ShellyListener.add_service
# ---------------------------------------------------------------------------

class TestShellyListenerAddService:
    @patch("shelly.discovery._probe")
    def test_add_service_calls_probe(self, mock_probe):
        mock_probe.return_value = MagicMock(spec=ShellyGen2)
        listener, _, _ = _make_listener()
        zc = MagicMock()
        zc.get_service_info.return_value = _service_info()
        listener.add_service(zc, "_shelly._tcp.local.", "shellyplus1pm-aabbcc._shelly._tcp.local.")
        mock_probe.assert_called_once()

    @patch("shelly.discovery._probe")
    def test_add_service_appends_to_devices(self, mock_probe):
        dev = MagicMock(spec=ShellyGen2)
        mock_probe.return_value = dev
        listener, _, devs = _make_listener()
        zc = MagicMock()
        zc.get_service_info.return_value = _service_info()
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        assert dev in devs

    @patch("shelly.discovery._probe")
    def test_add_service_deduplicates_by_host(self, mock_probe):
        mock_probe.return_value = MagicMock(spec=ShellyGen2)
        listener, discovered, devs = _make_listener()
        zc = MagicMock()
        info = _service_info(host="192.168.1.1")
        zc.get_service_info.return_value = info
        # Call twice with the same host
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        assert mock_probe.call_count == 1

    @patch("shelly.discovery._probe")
    def test_add_service_filters_non_shelly_http_tcp(self, mock_probe):
        mock_probe.return_value = None
        listener, _, devs = _make_listener()
        zc = MagicMock()
        # Non-shelly hostname on _http._tcp
        info = _service_info(server="someprinter.local.")
        zc.get_service_info.return_value = info
        listener.add_service(zc, "_http._tcp.local.", "printer._http._tcp.local.")
        mock_probe.assert_not_called()

    @patch("shelly.discovery._probe")
    def test_add_service_accepts_shelly_http_tcp(self, mock_probe):
        mock_probe.return_value = MagicMock(spec=ShellyGen1)
        listener, _, devs = _make_listener()
        zc = MagicMock()
        info = _service_info(server="shellyswitch25-aabbcc.local.")
        zc.get_service_info.return_value = info
        listener.add_service(zc, "_http._tcp.local.", "test._http._tcp.local.")
        mock_probe.assert_called_once()

    @patch("shelly.discovery._probe")
    def test_add_service_no_info_is_noop(self, mock_probe):
        listener, _, devs = _make_listener()
        zc = MagicMock()
        zc.get_service_info.return_value = None
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        mock_probe.assert_not_called()

    @patch("shelly.discovery._probe")
    def test_add_service_probe_returns_none_not_appended(self, mock_probe):
        mock_probe.return_value = None
        listener, _, devs = _make_listener()
        zc = MagicMock()
        zc.get_service_info.return_value = _service_info()
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        assert len(devs) == 0

    @patch("shelly.discovery._probe")
    def test_add_service_calls_on_device_found_callback(self, mock_probe):
        dev = MagicMock(spec=ShellyGen2)
        mock_probe.return_value = dev
        found = []
        listener, _, _ = _make_listener(on_device_found=found.append)
        zc = MagicMock()
        zc.get_service_info.return_value = _service_info()
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        assert found == [dev]

    @patch("shelly.discovery._probe")
    def test_add_service_no_addresses_is_noop(self, mock_probe):
        listener, _, devs = _make_listener()
        zc = MagicMock()
        info = MagicMock()
        info.parsed_addresses.return_value = []
        zc.get_service_info.return_value = info
        listener.add_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        mock_probe.assert_not_called()


# ---------------------------------------------------------------------------
# ShellyListener.remove_service
# ---------------------------------------------------------------------------

class TestShellyListenerRemoveService:
    def test_remove_service_removes_host_from_discovered(self):
        listener, discovered, _ = _make_listener()
        discovered.add("192.168.1.1")
        zc = MagicMock()
        zc.get_service_info.return_value = _service_info(host="192.168.1.1")
        listener.remove_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        assert "192.168.1.1" not in discovered

    def test_remove_service_no_info_is_noop(self):
        listener, discovered, _ = _make_listener()
        discovered.add("192.168.1.1")
        zc = MagicMock()
        zc.get_service_info.return_value = None
        listener.remove_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        assert "192.168.1.1" in discovered  # not removed


# ---------------------------------------------------------------------------
# ShellyListener.update_service
# ---------------------------------------------------------------------------

class TestShellyListenerUpdateService:
    @patch("shelly.discovery._probe")
    def test_update_service_ignored_when_include_updates_false(self, mock_probe):
        listener, _, _ = _make_listener(include_updates=False)
        zc = MagicMock()
        listener.update_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        mock_probe.assert_not_called()

    @patch("shelly.discovery._probe")
    def test_update_service_calls_add_when_include_updates_true(self, mock_probe):
        mock_probe.return_value = MagicMock(spec=ShellyGen2)
        listener, _, _ = _make_listener(include_updates=True)
        zc = MagicMock()
        zc.get_service_info.return_value = _service_info()
        listener.update_service(zc, "_shelly._tcp.local.", "test._shelly._tcp.local.")
        mock_probe.assert_called_once()
