# shellyconch

A conch is a type of shell that you can blow into to communicate or listen to. shellyconch is a Python library for discovering and controlling [Shelly](https://www.shelly.com) smart home devices over HTTP — both locally on your LAN and remotely via the Shelly Cloud API.

## Features

- **Local control** of Gen1 and Gen2+ Shelly devices over HTTP
- **Auto-discovery** of devices on the local network via mDNS (no configuration needed)
- **Generation-agnostic wrapper** (`ShellyDevice`) that works transparently with both Gen1 and Gen2+
- **Cloud control** via the Shelly Cloud Control API v2
- **Authentication support**: HTTP Basic Auth (Gen1) and SHA-256 Digest Auth (Gen2+)
- Covers switches/relays, rollers/covers, lights/dimmers, RGBW, energy metering, sensors, schedules, scripts, and more

## Requirements

- Python >= 3.14
- `requests >= 2.26.0`
- `zeroconf >= 0.38.0`

## Installation

```bash
pip install shellyconch
```

The package installs as the import name `shelly`:

```python
from shelly import ShellyDevice, discover_devices
```

### From source

```bash
git clone https://github.com/ilpersi/shellyconch.git
cd shellyconch
pip install -e .
```

## Quick Start

```python
from shelly import ShellyDevice, ShellyGen1, ShellyGen2, ShellyCloud, discover_devices

# Generation-agnostic: auto-detect and connect
device = ShellyDevice.connect("192.168.1.100", password="secret")
print(device.get_info())   # {"mac": "...", "model": "...", "generation": 2, ...}
device.turn_on(0)
device.cover_goto_position(0, pos=50)

# Auto-discover all Shelly devices on the local network
for raw in discover_devices(timeout=10):
    d = ShellyDevice(raw)
    info = d.get_info()
    print(f"{info['model']}  gen={info['generation']}  mac={info['mac']}")

# Gen1 direct access (Shelly1, Plug, 2.5, etc.)
sw = ShellyGen1("192.168.1.100")
sw.relay_on(0)             # turn relay 0 ON
sw.relay_off(0)            # turn relay 0 OFF
sw.relay_toggle(0)         # toggle relay 0
sw.relay_on(0, timer=30)   # turn ON, auto-off after 30 s

# Gen2+ direct access (ShellyPlus, ShellyPro, etc.)
sw2 = ShellyGen2("192.168.1.101", password="mypassword")
sw2.switch_set(0, on=True)
sw2.switch_set(0, on=True, toggle_after=60)
sw2.switch_toggle(0)

# Cloud control — works regardless of local network
cloud = ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="your_auth_key")
cloud.turn_on("b48a0a1cd978")
cloud.cover_goto_position("dc4f2276846a", pos=30)
states = cloud.get_devices_state(["b48a0a1cd978"], select=["status"])
```

## Device Discovery

The library uses mDNS to find devices on your local network and probes each candidate's `/shelly` endpoint to confirm its generation and capabilities.

```python
from shelly import discover_devices, ShellyDiscovery

# One-shot scan
devices = discover_devices(timeout=10)
for device in devices:
    print(device)  # ShellyGen1(host='192.168.1.100') or ShellyGen2(...)

# Continuous discovery with a context manager
with ShellyDiscovery(on_discover=lambda d: print("Found:", d)) as disc:
    disc.start()
    # ... do other work ...
```

## Error Handling

All exceptions inherit from `ShellyError`:

| Exception | When raised |
|---|---|
| `ShellyConnectionError` | Cannot reach the device |
| `ShellyTimeoutError` | Request timed out |
| `ShellyAuthError` | HTTP 401 — bad credentials |
| `ShellyHTTPError` | Non-2xx HTTP response (`.status_code` attribute) |
| `ShellyRPCError` | Gen2+ JSON-RPC error response (`.code` attribute) |
| `ShellyCloudError` | Cloud API error (`.error` string, `.messages` list) |
| `ShellyDiscoveryError` | mDNS discovery failure |

```python
from shelly import ShellyGen2, ShellyAuthError, ShellyRPCError

try:
    sw = ShellyGen2("192.168.1.101", password="wrong")
    sw.switch_set(0, on=True)
except ShellyAuthError:
    print("Bad password")
except ShellyRPCError as e:
    print(f"RPC error {e.code}: {e}")
```

## Architecture

```
shelly/
  exceptions.py   — ShellyError hierarchy
  models.py       — str-enums and device lookup table
  auth.py         — ShellyDigestAuth (SHA-256 Digest, RFC 7616)
  base.py         — BaseShelly: HTTP session, error mapping
  gen1.py         — ShellyGen1: all Gen1 REST endpoints
  gen2.py         — ShellyGen2: JSON-RPC 2.0 over HTTP
  device.py       — ShellyDevice: generation-agnostic wrapper
  cloud.py        — ShellyCloud: Shelly Cloud Control API v2
  discovery.py    — discover_devices() + ShellyDiscovery
```

- **Gen1** — plain GET requests to REST endpoints; booleans as `"true"`/`"false"` strings.
- **Gen2+** — JSON-RPC 2.0 POSTed to `/rpc`; SHA-256 Digest authentication.
- **ShellyDevice** — composition wrapper; dispatches to Gen1 or Gen2 internally. Access generation-specific APIs via `device.underlying`.

## API Reference

See [`docs/usage.md`](docs/usage.md) for a complete, annotated reference covering every method group across all classes.

**External API docs:**
- Gen1: https://shelly-api-docs.shelly.cloud/gen1/
- Gen2+: https://shelly-api-docs.shelly.cloud/gen2/

## License

GNU GPL 3
