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
from concurrent.futures import ThreadPoolExecutor
from typing import Callable

import requests
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf

from .gen1 import ShellyGen1
from .gen2 import ShellyGen2
from .device import ShellyDevice

logger = logging.getLogger(__name__)

# mDNS service types to browse.
_SERVICE_TYPES = ["_shelly._tcp.local.", "_http._tcp.local.", ]

# Hostname prefixes that identify Shelly devices on _http._tcp.
_SHELLY_HOSTNAME_PREFIXES = ("shelly",)


class ShellyListener(ServiceListener):
    def __init__(self, lock: threading.Lock, discovered_hosts: set, devices: list, password: str | None,
                 gen1_password: str | None, gen1_username: str, http_timeout: float, executor: ThreadPoolExecutor,
                 include_updates: bool = False, on_device_found: Callable | None = None,
                 return_generic: bool = False, probe_attempts: int = 3, probe_retry_interval: float = 0.5):

        self.lock = lock
        self.discovered_hosts = discovered_hosts
        self.devices = devices
        self.password = password
        self.gen1_password = gen1_password
        self.gen1_username = gen1_username
        self.http_timeout = http_timeout
        self.executor = executor
        self.include_updates = include_updates
        self.on_device_found = on_device_found
        self.return_generic = return_generic
        self.probe_attempts = probe_attempts
        self.probe_retry_interval = probe_retry_interval

    def add_service(self, zc, type_: str, name: str) -> None:
        # Resolve the service info — retry once if the first call returns
        # None (zeroconf sometimes hasn't fully populated the record yet).
        info = zc.get_service_info(type_, name)
        if info is None:
            info = zc.get_service_info(type_, name, timeout=2000)
            if info is None:
                logger.debug("Could not resolve service info for %s after retry", name)
                return

        host = _pick_host(info.parsed_addresses())
        if host is None:
            return

        # For _http._tcp services, only consider hosts whose mDNS name
        # begins with "shelly" to avoid probing unrelated devices.
        if type_ == "_http._tcp.local.":
            server_name = (info.server or "").lower()
            if not any(server_name.startswith(p) for p in _SHELLY_HOSTNAME_PREFIXES):
                return

        # Dedup at "intent to probe" — prevents two parallel probes for the
        # same device announcing on both service types, while still letting
        # _probe()'s internal retries recover from transient HTTP failures.
        with self.lock:
            if host in self.discovered_hosts:
                return
            self.discovered_hosts.add(host)

        # Run the probe on the worker pool so the listener thread stays
        # responsive to incoming announcements.  RuntimeError is raised when
        # the executor has been shut down (late callback during teardown).
        try:
            self.executor.submit(self._probe_and_record, info, host)
        except RuntimeError:
            logger.debug("Skipping late probe for %s: executor shut down", host)

    def _probe_and_record(self, info, host: str) -> None:
        gen = _txt_gen(info.properties)
        device = _probe(
            host=host, port=info.port, txt_gen=gen, password=self.password,
            gen1_password=self.gen1_password, gen1_username=self.gen1_username,
            http_timeout=self.http_timeout, return_generic=self.return_generic,
            attempts=self.probe_attempts, retry_interval=self.probe_retry_interval,
        )
        if device is None:
            return

        with self.lock:
            self.devices.append(device)

        if self.on_device_found is not None:
            try:
                self.on_device_found(device)
            except Exception:
                logger.exception("on_device_found callback raised for %s", host)

    def remove_service(self, zc, type_: str, name: str) -> None:
        info = zc.get_service_info(type_, name)
        if info is None:
            return

        host = _pick_host(info.parsed_addresses())
        if host is None:
            return

        with self.lock:
            if host in self.discovered_hosts:
                self.discovered_hosts.remove(host)

    def update_service(self, zc, type_: str, name: str) -> None:
        if self.include_updates:
            self.add_service(zc, type_, name)


def discover_devices(timeout: float = 10.0, password: str | None = None, gen1_password: str | None = None,
                     gen1_username: str = "admin", http_timeout: float = 5.0, include_updates=False,
                     on_device_found: Callable | None = None,  return_generic: bool = False,
                     probe_attempts: int = 3, probe_retry_interval: float = 0.5,
                     max_concurrent_probes: int = 16) -> list[ShellyGen1 | ShellyGen2 | ShellyDevice]:
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
    return_generic:
        Optional boolean value. Set this to true to return devices using
        the ``ShellyDevice`` class
    probe_attempts:
        Number of HTTP probe attempts per candidate before giving up
        (default 3).
    probe_retry_interval:
        Seconds to wait between probe attempts (default 0.5).
    max_concurrent_probes:
        Maximum number of HTTP probes that may run in parallel.  Probes run
        in a worker pool so a slow/unreachable device cannot block discovery
        of others (default 16).

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

    executor = ThreadPoolExecutor(max_workers=max_concurrent_probes, thread_name_prefix="shelly-probe")
    listener = ShellyListener(lock=lock, discovered_hosts=discovered_hosts, devices=devices, password=password,
                              gen1_password=_gen1_pass, gen1_username=gen1_username, http_timeout=http_timeout,
                              executor=executor, include_updates=include_updates, on_device_found=on_device_found,
                              return_generic=return_generic, probe_attempts=probe_attempts,
                              probe_retry_interval=probe_retry_interval)

    zc = Zeroconf()
    browsers = [ServiceBrowser(zc, svc_type, listener) for svc_type in _SERVICE_TYPES]

    try:
        time.sleep(timeout)
    finally:
        # Stop new mDNS callbacks first, then drain in-flight probes, then
        # close zeroconf.  Order matters: closing zeroconf while probes are
        # still running can sever HTTP sockets mid-request.
        for browser in browsers:
            browser.cancel()
        executor.shutdown(wait=True)
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
                 http_timeout: float = 5.0, include_updates: bool = False, on_device_found: Callable | None = None,
                 return_generic: bool = False, probe_attempts: int = 3, probe_retry_interval: float = 0.5,
                 max_concurrent_probes: int = 16, ):

        self._password = password
        self._gen1_password = gen1_password if gen1_password is not None else password
        self._gen1_username = gen1_username
        self._http_timeout = http_timeout
        self._include_updates = include_updates
        self._on_device_found = on_device_found
        self.return_generic = return_generic
        self._probe_attempts = probe_attempts
        self._probe_retry_interval = probe_retry_interval
        self._max_concurrent_probes = max_concurrent_probes

        self._lock = threading.Lock()
        self._discovered_hosts: set[str] = set()
        self._devices: list[ShellyGen1 | ShellyGen2] = []
        self._zc: Zeroconf | None = None
        self._browsers: list = []
        self._executor: ThreadPoolExecutor | None = None

    @property
    def devices(self) -> list[ShellyGen1 | ShellyGen2]:
        """All Shelly devices found so far."""
        with self._lock:
            return list(self._devices)

    def start(self) -> None:
        """Begin mDNS browsing in the background."""
        self._executor = ThreadPoolExecutor(max_workers=self._max_concurrent_probes,
                                            thread_name_prefix="shelly-probe")
        listener = ShellyListener(lock=self._lock, discovered_hosts=self._discovered_hosts, devices=self._devices,
                                  password=self._password, gen1_password=self._gen1_password,
                                  gen1_username=self._gen1_username, http_timeout=self._http_timeout,
                                  executor=self._executor, include_updates=self._include_updates,
                                  on_device_found=self._on_device_found, return_generic=self.return_generic,
                                  probe_attempts=self._probe_attempts,
                                  probe_retry_interval=self._probe_retry_interval)

        self._zc = Zeroconf()
        self._browsers = [ServiceBrowser(self._zc, svc_type, listener) for svc_type in _SERVICE_TYPES]

    def stop(self) -> None:
        """Stop mDNS browsing and release resources."""
        for browser in self._browsers:
            browser.cancel()
        if self._executor is not None:
            self._executor.shutdown(wait=True)
            self._executor = None
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


def _pick_host(addresses: list[str]) -> str | None:
    """Prefer the first IPv4 address; fall back to IPv6 if that's all there is."""
    if not addresses:
        return None
    for a in addresses:
        if ":" not in a:
            return a
    return addresses[0]


def _probe(host: str, port: int | None, txt_gen: int | None, password: str | None, gen1_password: str | None,
           gen1_username: str, http_timeout: float, return_generic: bool = False,
           attempts: int = 3, retry_interval: float = 0.5) -> (ShellyGen1 | ShellyGen2 | ShellyDevice | None):
    """
    HTTP-probe a candidate IP to confirm it is a Shelly device and return
    the appropriate typed instance, or ``None`` if it is not a Shelly device.

    Retries up to ``attempts`` times on transient failure (connection refused
    mid-boot, network blip, slow first response) — Shelly devices that
    advertise via mDNS are sometimes briefly unreachable on HTTP.
    """
    url = f"http://{host}:{port}/shelly"
    info: dict | None = None
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.get(url, timeout=http_timeout)
            resp.raise_for_status()
            info = resp.json()
            break
        except Exception as exc:
            last_exc = exc
            logger.debug("Probe attempt %d/%d for %s failed: %s", attempt, attempts, host, exc)
            if attempt < attempts:
                time.sleep(retry_interval)
    if info is None:
        logger.debug("Probe gave up on %s after %d attempts (last error: %s)", host, attempts, last_exc)
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
        device = ShellyGen1(host=host, port=port, timeout=http_timeout, username=gen1_username, password=gen1_password, )
    else:
        device = ShellyGen2(host=host, port=port, timeout=http_timeout, password=password, )

    if return_generic:
        return ShellyDevice(device=device, generation=gen)
    else:
        return device
