"""
Shelly device discovery using mDNS (Multicast DNS / Bonjour / Zeroconf).

Gen1 devices advertise ``_http._tcp.local.`` services with the hostname
pattern ``shelly<model>-<6-digit-mac>``.

Gen2+ devices additionally advertise ``_shelly._tcp.local.`` services and
include a ``gen=<N>`` TXT record.  Gen1 devices do *not* have a ``gen``
TXT record.

Discovery strategy
------------------
1. Browse both ``_shelly._tcp.local.`` and ``_http._tcp.local.`` service
   types simultaneously.
2. For each discovered service, probe the device's ``/shelly`` HTTP
   endpoint (always accessible without auth) to confirm it is a Shelly
   device and to read its generation number.
3. Wrap the device in a :class:`~shelly.gen1.ShellyGen1` or
   :class:`~shelly.gen2.ShellyGen2` instance and return it.

Requires the ``zeroconf`` package (``pip install zeroconf``).
"""

import logging
import threading
import time
from typing import Callable

import requests
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from .gen1 import ShellyGen1
from .gen2 import ShellyGen2

logger = logging.getLogger(__name__)

# mDNS service types to browse.
_SERVICE_TYPES = ["_shelly._tcp.local.", "_http._tcp.local.", ]

# Hostname prefixes that identify Shelly devices on _http._tcp.
_SHELLY_HOSTNAME_PREFIXES = ("shelly",)


class ShellyListener(ServiceListener):
    def __init__(self, lock: threading.Lock, discovered_hosts: set, devices: list, password: str | None,
                 gen1_password: str | None, gen1_username: str, http_timeout: float, include_updates: bool = False,
                 on_device_found: Callable | None = None, ):

        self.lock = lock
        self.discovered_hosts = discovered_hosts
        self.devices = devices
        self.password = password
        self.gen1_password = gen1_password
        self.gen1_username = gen1_username
        self.http_timeout = http_timeout
        self.include_updates = include_updates
        self.on_device_found = on_device_found

    def add_service(self, zc, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return

        addresses = info.parsed_addresses()
        if not addresses:
            return
        host = addresses[0]

        # For _http._tcp services, only consider hosts whose mDNS name
        # begins with "shelly" to avoid probing unrelated devices.
        if type_ == "_http._tcp.local.":
            server_name = (info.server or "").lower()
            if not any(server_name.startswith(p) for p in _SHELLY_HOSTNAME_PREFIXES):
                return

        with self.lock:
            if host in self.discovered_hosts:
                return
            self.discovered_hosts.add(host)

        # Determine generation from the TXT record first (fast path).
        gen = _txt_gen(info.properties)

        # Probe the device to confirm it is Shelly and get accurate gen.
        device = _probe(host=host, port=info.port, txt_gen=gen, password=self.password,
                        gen1_password=self.gen1_password, gen1_username=self.gen1_username,
                        http_timeout=self.http_timeout, )
        if device is None:
            return

        with self.lock:
            self.devices.append(device)

        if self.on_device_found is not None:
            self.on_device_found(device)

    def remove_service(self, zc, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return

        addresses = info.parsed_addresses()
        if not addresses:
            return
        host = addresses[0]

        with self.lock:
            if host in self.discovered_hosts:
                self.discovered_hosts.remove(host)

    def update_service(self, zc, type_: str, name: str) -> None:
        if self.include_updates:
            self.add_service(zc, type_, name)


def discover_devices(timeout: float = 10.0, password: str | None = None, gen1_password: str | None = None,
                     gen1_username: str = "admin", http_timeout: float = 5.0, include_updates=False,
                     on_device_found: Callable | None = None) -> list[ShellyGen1 | ShellyGen2]:
    """
    Discover all Shelly devices on the local network via mDNS.

    Scans for ``_shelly._tcp.local.`` and ``_http._tcp.local.`` mDNS
    services for *timeout* seconds, then probes each candidate via HTTP
    to confirm it is a Shelly device and determine its generation.

    Parameters
    ----------
    timeout:
        How long to listen for mDNS announcements, in seconds (default 10).
    password:
        Password used for Gen2+ devices (SHA-256 Digest Auth).
    gen1_password:
        Password used for Gen1 devices (HTTP Basic Auth).  When ``None``,
        falls back to ``password``.
    gen1_username:
        Username for Gen1 HTTP Basic Auth (default ``"admin"``).
    http_timeout:
        Socket timeout in seconds for the HTTP probe (default 5).
    include_updates:
        Should the listener also receive updates to existing devices?
    on_device_found:
        Optional callback invoked for each device as soon as it is
        confirmed (before the full scan completes).  Receives a single
        argument — the device instance.

    Returns
    -------
    list
        A list of :class:`~shelly.gen1.ShellyGen1` and/or
        :class:`~shelly.gen2.ShellyGen2` instances, one per unique device
        found.  An empty list is returned when no devices are found or when
        ``zeroconf`` is not installed.
    """

    discovered_hosts: set[str] = set()
    devices: list[ShellyGen1 | ShellyGen2] = []
    lock = threading.Lock()

    # Resolve the effective Gen1 password.
    _gen1_pass = gen1_password if gen1_password is not None else password

    listener = ShellyListener(lock=lock, discovered_hosts=discovered_hosts, devices=devices, password=password,
                              gen1_password=_gen1_pass, gen1_username=gen1_username, http_timeout=http_timeout,
                              include_updates=include_updates, on_device_found=on_device_found, )

    zc = Zeroconf()
    browsers = [ServiceBrowser(zc, svc_type, listener) for svc_type in _SERVICE_TYPES]

    try:
        time.sleep(timeout)
    finally:
        for browser in browsers:
            browser.cancel()
        zc.close()

    return devices


class ShellyDiscovery:
    """
    Context-manager wrapper around :func:`discover_devices` for long-lived
    or event-driven discovery scenarios.

    Usage::

        with ShellyDiscovery(on_device_found=handle) as sd:
            time.sleep(30)  # or wait for an event

        devices = sd.devices
    """

    def __init__(self, password: str | None = None, gen1_password: str | None = None, gen1_username: str = "admin",
                 http_timeout: float = 5.0, include_updates: bool = False, on_device_found: Callable | None = None, ):

        self._password = password
        self._gen1_password = gen1_password if gen1_password is not None else password
        self._gen1_username = gen1_username
        self._http_timeout = http_timeout
        self._include_updates = include_updates
        self._on_device_found = on_device_found

        self._lock = threading.Lock()
        self._discovered_hosts: set[str] = set()
        self._devices: list[ShellyGen1 | ShellyGen2] = []
        self._zc: Zeroconf | None = None
        self._browsers: list = []

    @property
    def devices(self) -> list[ShellyGen1 | ShellyGen2]:
        """All Shelly devices found so far."""
        with self._lock:
            return list(self._devices)

    def start(self) -> None:
        """Begin mDNS browsing in the background."""
        listener = ShellyListener(lock=self._lock, discovered_hosts=self._discovered_hosts, devices=self._devices,
                                  password=self._password, gen1_password=self._gen1_password,
                                  gen1_username=self._gen1_username, http_timeout=self._http_timeout,
                                  include_updates=self._include_updates, on_device_found=self._on_device_found, )

        self._zc = Zeroconf()
        self._browsers = [ServiceBrowser(self._zc, svc_type, listener) for svc_type in _SERVICE_TYPES]

    def stop(self) -> None:
        """Stop mDNS browsing and release resources."""
        for browser in self._browsers:
            browser.cancel()
        if self._zc is not None:
            self._zc.close()
            self._zc = None
        self._browsers = []

    def __enter__(self) -> "ShellyDiscovery":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _txt_gen(properties: dict | None) -> int | None:
    """Extract the ``gen`` value from mDNS TXT records, or return None."""
    if not properties:
        return None
    for key, value in properties.items():
        k = key.decode() if isinstance(key, bytes) else key
        if k.lower() == "gen":
            v = value.decode() if isinstance(value, bytes) else str(value)
            try:
                return int(v)
            except (ValueError, TypeError):
                pass
    return None


def _probe(host: str, port: int, txt_gen: int | None, password: str | None, gen1_password: str | None,
           gen1_username: str, http_timeout: float, ) -> ShellyGen1 | ShellyGen2 | None:
    """
    HTTP-probe a candidate IP to confirm it is a Shelly device and return
    the appropriate typed instance, or ``None`` if it is not a Shelly device.
    """
    url = f"http://{host}:{port}/shelly"
    try:
        resp = requests.get(url, timeout=http_timeout)
        resp.raise_for_status()
        info = resp.json()
    except Exception as exc:
        logger.debug("Probe failed for %s: %s", host, exc)
        return None

    # Confirm the response looks like a Shelly /shelly endpoint.
    if "mac" not in info:
        return None

    # Determine generation: prefer the HTTP response field over TXT record.
    gen = info.get("gen", txt_gen)

    if gen is None:
        # No gen field ⟹ Gen1 device.
        gen = 1

    if gen == 1:
        return ShellyGen1(host=host, port=port, timeout=http_timeout, username=gen1_username, password=gen1_password, )
    else:
        return ShellyGen2(host=host, port=port, timeout=http_timeout, password=password, )
