# Shelly Library — Usage Guide

A Python library for discovering and controlling Shelly smart home devices over HTTP, both locally and via the Shelly Cloud.

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Device Discovery](#device-discovery)
- [Error Handling](#error-handling)
- [Authentication](#authentication)
- [ShellyDevice — Generation-Agnostic Wrapper](#shellydevice--generation-agnostic-wrapper)
  - [Constructor](#constructor-device)
  - [Connecting by Host](#connecting-by-host)
  - [Wrapping a Discovered Device](#wrapping-a-discovered-device)
  - [Device Identity](#device-identity)
  - [Switch / Relay](#switch--relay-device)
  - [Cover / Roller](#cover--roller-device)
  - [Light / Dimmer](#light--dimmer-device)
  - [System Operations](#system-operations-device)
  - [Firmware](#firmware-device)
  - [WiFi & Cloud](#wifi--cloud-device)
  - [Authentication Management](#authentication-management-device)
  - [Accessing Generation-Specific Features](#accessing-generation-specific-features)
- [ShellyCloud — Cloud Control API](#shellycloud--cloud-control-api)
  - [Setup & Credentials](#setup--credentials)
  - [Constructor](#constructor-cloud)
  - [Reading Device State](#reading-device-state)
  - [Switch / Relay Control](#switch--relay-control-cloud)
  - [Cover / Roller Control](#cover--roller-control-cloud)
  - [Light Control](#light-control-cloud)
  - [Group Control](#group-control)
  - [Error Handling](#error-handling-cloud)
- [ShellyGen1 — First-Generation Devices](#shellygen1--first-generation-devices)
  - [Constructor](#constructor-gen1)
  - [Device Information & Status](#device-information--status)
  - [Global Settings](#global-settings)
  - [WiFi Configuration](#wifi-configuration)
  - [Relay Control](#relay-control)
  - [Power Metering](#power-metering)
  - [Energy Metering (EM / 3EM)](#energy-metering-em--3em)
  - [Roller / Cover Control](#roller--cover-control)
  - [Light Control](#light-control)
  - [URL Action Callbacks](#url-action-callbacks)
  - [External Sensors (Shelly1 Add-on)](#external-sensors-shelly1-add-on)
  - [Input Channels (i3, Button1)](#input-channels-i3-button1)
  - [Analogue Input (Shelly Uni)](#analogue-input-shelly-uni)
  - [Thermostat / TRV](#thermostat--trv)
  - [Gas Detector](#gas-detector)
  - [Door/Window Sensor](#doorwindow-sensor)
  - [Firmware Management](#firmware-management-gen1)
  - [Reboot & Factory Reset](#reboot--factory-reset-gen1)
- [ShellyGen2 — Second-Generation and Newer Devices](#shellygen2--second-generation-and-newer-devices)
  - [Constructor](#constructor-gen2)
  - [Core RPC Call](#core-rpc-call)
  - [Device Management (Shelly.*)](#device-management-shelly)
  - [Switch Component](#switch-component)
  - [Cover Component](#cover-component)
  - [Light Component](#light-component)
  - [RGBW Component](#rgbw-component)
  - [Input Component](#input-component)
  - [Sensor Components](#sensor-components)
  - [Energy Metering](#energy-metering-gen2)
  - [System Component](#system-component)
  - [WiFi Component](#wifi-component)
  - [Cloud, MQTT & WebSocket](#cloud-mqtt--websocket)
  - [BLE Component](#ble-component)
  - [Schedule Service](#schedule-service)
  - [Webhook Service](#webhook-service)
  - [Key-Value Store (KVS)](#key-value-store-kvs)
  - [Script Component](#script-component)
  - [HTTP Outbound Calls](#http-outbound-calls)
  - [Matter Protocol](#matter-protocol)
  - [Firmware Management](#firmware-management-gen2)
- [Using as a Context Manager](#using-as-a-context-manager)
- [Device-Type Reference](#device-type-reference)

---

## Installation

```bash
pip install requests zeroconf
```

Or install from the project directory:

```bash
pip install -e .
```

**Requirements:** Python 3.10+, `requests >= 2.26.0`, `zeroconf >= 0.38.0`.

---

## Quick Start

```python
from shelly import ShellyDevice, ShellyGen1, ShellyGen2, ShellyCloud, discover_devices

# ── Generation-agnostic: auto-detect and connect ─────────────────────────────
device = ShellyDevice.connect("192.168.1.100", password="secret")
print(device.get_info())   # {"mac": "...", "model": "...", "generation": 2, ...}
device.turn_on(0)
device.cover_goto_position(0, pos=50)

# ── Auto-discover all Shelly devices on the local network ────────────────────
for raw in discover_devices(timeout=10):
    d = ShellyDevice(raw)          # wrap any discovered device uniformly
    info = d.get_info()
    print(f"{info['model']}  gen={info['generation']}  mac={info['mac']}")

# ── Gen1 — Shelly1 / Plug / 2.5 etc. (direct access) ────────────────────────
sw = ShellyGen1("192.168.1.100")
sw.relay_on(0)            # turn relay 0 ON
sw.relay_off(0)           # turn relay 0 OFF
sw.relay_toggle(0)        # toggle relay 0
sw.relay_on(0, timer=30)  # turn ON, auto-off after 30 s

# ── Gen2+ — ShellyPlus / ShellyPro etc. (direct access) ─────────────────────
sw2 = ShellyGen2("192.168.1.101", password="mypassword")
sw2.switch_set(0, on=True)
sw2.switch_set(0, on=True, toggle_after=60)
sw2.switch_toggle(0)

# ── Cloud — control any device regardless of local network ───────────────────
cloud = ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="your_auth_key")
cloud.turn_on("b48a0a1cd978")
cloud.cover_goto_position("dc4f2276846a", pos=30)
states = cloud.get_devices_state(["b48a0a1cd978"], select=["status"])
```

---

## Device Discovery

Discovery listens for mDNS announcements on the local network and probes each candidate device's `/shelly` HTTP endpoint to confirm its generation.

### One-shot scan

```python
from shelly import discover_devices

# Scan for 10 seconds, return all found devices
devices = discover_devices(timeout=10)

for device in devices:
    print(device)          # ShellyGen1(host='192.168.1.100') or ShellyGen2(...)
    print(type(device))    # shelly.gen1.ShellyGen1  /  shelly.gen2.ShellyGen2
```

### With credentials

```python
devices = discover_devices(
    timeout=15,
    password="gen2password",       # used for Gen2+ devices
    gen1_password="gen1password",  # used for Gen1 devices (falls back to password)
    gen1_username="admin",         # default; change if you customised the username
    http_timeout=5.0,              # per-request timeout during probing
)
```

### Callback as devices are found

```python
def on_found(device):
    print(f"Found: {device}")

devices = discover_devices(timeout=10, on_device_found=on_found)
```

### Long-lived / event-driven discovery

Use `ShellyDiscovery` as a context manager when you need to keep listening in the background:

```python
import time
from shelly import ShellyDiscovery

with ShellyDiscovery(password="secret", on_device_found=lambda d: print("Found:", d)) as sd:
    time.sleep(60)   # keep listening for 60 seconds

print("All devices:", sd.devices)
```

Or manage the lifecycle manually:

```python
sd = ShellyDiscovery(password="secret")
sd.start()
# ... do other work ...
time.sleep(30)
sd.stop()
devices = sd.devices
```

---

## Error Handling

All exceptions derive from `ShellyError`:

| Exception | When raised | Useful attributes |
|---|---|---|
| `ShellyConnectionError` | Device or cloud server unreachable | — |
| `ShellyAuthError` | HTTP 401 — wrong credentials or auth required | — |
| `ShellyTimeoutError` | Request exceeded the configured timeout | — |
| `ShellyHTTPError` | Unexpected HTTP error (4xx/5xx other than 401) from a local device | `.status_code` |
| `ShellyRPCError` | Gen2+ device returned a JSON-RPC error frame | `.code` |
| `ShellyCloudError` | Shelly Cloud API returned an error string | `.error`, `.messages` |

```python
from shelly import ShellyGen1, ShellyGen2, ShellyCloud
from shelly import (
    ShellyConnectionError,
    ShellyAuthError,
    ShellyTimeoutError,
    ShellyHTTPError,
    ShellyRPCError,
    ShellyCloudError,
    ShellyError,
)

# ── Local device errors ───────────────────────────────────────────────────────
device = ShellyGen1("192.168.1.100", password="secret")

try:
    status = device.get_status()
except ShellyAuthError:
    print("Wrong password or auth not configured")
except ShellyConnectionError as e:
    print(f"Cannot reach device: {e}")
except ShellyTimeoutError:
    print("Device did not respond in time")
except ShellyHTTPError as e:
    print(f"HTTP error {e.status_code}")
except ShellyError as e:
    print(f"Generic Shelly error: {e}")

# ── Gen2 RPC errors ───────────────────────────────────────────────────────────
device2 = ShellyGen2("192.168.1.101")
try:
    device2.switch_set(99, on=True)   # non-existent switch ID
except ShellyRPCError as e:
    print(f"RPC error code={e.code}")  # e.code is the numeric JSON-RPC error code

# ── Cloud API errors ──────────────────────────────────────────────────────────
cloud = ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="abc123")
try:
    cloud.turn_on("b48a0a1cd978")
except ShellyAuthError:
    print("auth_key is invalid or expired")
except ShellyCloudError as e:
    # e.error  — API error string, e.g. "DEVICE_OFFLINE", "BAD_REQUEST"
    # e.messages — list of detail strings from the server (may be empty)
    print(f"Cloud error: {e.error}")
    if e.messages:
        print("Details:", e.messages)
except ShellyConnectionError:
    print("Cannot reach Shelly Cloud servers")
```

### Cloud API error strings

| Error string | HTTP status | Meaning |
|---|---|---|
| `DEVICE_FAILED_COMMAND` | 400 | Device received but could not execute the command |
| `DEVICE_OFFLINE` | 400 | Device appears offline to the cloud |
| `DEVICE_INVALID_MODE` | 400 | Device not in a mode compatible with the command |
| `DEVICE_INVALID_CHANNEL` | 400 | Channel index is invalid or unsupported |
| `BAD_REQUEST` | 400 | Invalid request parameters |
| `INSTANCE_NOT_FOUND` | 404 | Cloud routing problem (try again) |
| `DEVICE_NOT_FOUND` | 404 | Device state not found in cloud |
| `UNEXPECTED_SUBSERVICE_ERROR` | 500 | Internal cloud error |

---

## Authentication

### Gen1 — HTTP Basic Auth

Gen1 devices ship with authentication **disabled**.  Enable it through the web UI or via the API:

```python
sw = ShellyGen1("192.168.1.100")

# Enable auth on the device and update the local session simultaneously
sw.set_auth(enabled=True, username="admin", password="mysecret")

# From this point, all requests use Basic Auth automatically.

# Connect to an already-protected device from the start:
sw = ShellyGen1("192.168.1.100", username="admin", password="mysecret")

# Disable auth
sw.set_auth(enabled=False)
```

### Gen2+ — SHA-256 Digest Auth

Gen2+ devices use a custom SHA-256 Digest Auth challenge-response.  The library handles this transparently:

```python
sw = ShellyGen2("192.168.1.101", password="mysecret")
# Every request will automatically handle the 401 challenge.

# Change the device password (also updates the local session):
sw.set_auth("newpassword")

# Remove the password (disable auth on the device):
sw.set_auth(None)
```

> **Note:** `Shelly.GetDeviceInfo` (and the `/shelly` HTTP endpoint) are always accessible without credentials, even when auth is enabled.

---

---

## ShellyDevice — Generation-Agnostic Wrapper

`ShellyDevice` wraps either a `ShellyGen1` or a `ShellyGen2` instance and exposes a **single unified API** that works identically for all device generations.  You do not need to know the generation in advance.

Use `ShellyDevice` when:
- You are writing code that must work with a mix of Gen1 and Gen2+ devices without branching.
- You have discovered devices via `discover_devices()` and want to treat them all uniformly.
- You only need the common feature set (relay, cover, light, firmware, WiFi, cloud, auth).

For generation-specific features — Gen2 scripts, KVS, webhooks, Gen1 TRV, gas sensors, etc. — access the underlying typed instance via `device.underlying`.

### Constructor (Device)

```python
ShellyDevice(device)
```

| Parameter | Type | Description |
|---|---|---|
| `device` | `ShellyGen1 \| ShellyGen2` | An already-constructed typed instance to wrap |

```python
from shelly import ShellyDevice, ShellyGen1, ShellyGen2

# Wrap an existing typed instance
gen1 = ShellyGen1("192.168.1.100", password="secret")
device = ShellyDevice(gen1)

gen2 = ShellyGen2("192.168.1.101", password="secret")
device = ShellyDevice(gen2)
```

### Connecting by Host

The `connect()` class method probes `/shelly` on the device, detects the generation automatically, constructs the right typed instance internally, and returns a `ShellyDevice`.

```python
ShellyDevice.connect(
    host,
    port=80,
    password=None,
    gen1_password=None,
    gen1_username="admin",
    timeout=10.0,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `host` | `str` | — | IP address or hostname |
| `port` | `int` | `80` | HTTP port |
| `password` | `str \| None` | `None` | Password for Gen2+ SHA-256 Digest Auth |
| `gen1_password` | `str \| None` | `None` | Password for Gen1 Basic Auth; falls back to `password` |
| `gen1_username` | `str` | `"admin"` | Gen1 username |
| `timeout` | `float` | `10.0` | Request timeout in seconds |

```python
from shelly import ShellyDevice

# No auth (most Gen1 devices ship with auth disabled)
device = ShellyDevice.connect("192.168.1.100")

# Single password for any generation
device = ShellyDevice.connect("192.168.1.100", password="secret")

# Separate passwords for each generation
device = ShellyDevice.connect(
    "192.168.1.100",
    password="gen2pass",
    gen1_password="gen1pass",
    gen1_username="admin",
)

# Check what was found
print(device)            # ShellyDevice(gen=2, host='192.168.1.100')
print(device.generation) # 2
print(type(device.underlying))  # <class 'shelly.gen2.ShellyGen2'>
```

Raises `ShellyConnectionError` if the device cannot be reached or does not respond as a Shelly device.

### Wrapping a Discovered Device

```python
from shelly import ShellyDevice, discover_devices

devices = discover_devices(timeout=15, password="secret")

for raw in devices:
    d = ShellyDevice(raw)
    info = d.get_info()
    print(f"{info['model']:20s}  gen={info['generation']}  mac={info['mac']}")
    d.turn_on(0)
```

Works as a context manager — the underlying session is closed on exit:

```python
with ShellyDevice.connect("192.168.1.100") as device:
    device.turn_on(0)
# session closed here
```

---

### Device Identity

#### `get_info() → dict`

Returns a **normalized** dict with the same keys for every generation:

| Key | Type | Description |
|---|---|---|
| `mac` | `str` | Hardware MAC address (no colons, e.g. `"B48A0A1CD978"`) |
| `model` | `str` | Human-readable model name (e.g. `"Shelly1PM"`, `"ShellyPlus1PM"`) |
| `firmware` | `str` | Firmware version string |
| `generation` | `int` | Generation number: `1`, `2`, `3`, or `4` |
| `auth_enabled` | `bool` | Whether HTTP authentication is currently active |

```python
info = device.get_info()
# {
#   "mac": "98F4ABB929CC",
#   "model": "Shelly1PM",
#   "firmware": "20230808-130340/v1.14.0-gcb84623",
#   "generation": 1,
#   "auth_enabled": False
# }

print(info["model"])       # "Shelly1PM"
print(info["generation"])  # 1
print(info["auth_enabled"])
```

> Compare this to the raw Gen1 `get_info()` (returns `type`, `fw`, `auth`, …) and Gen2 `get_device_info()` (returns `model`, `ver`, `auth_en`, …), which use completely different key schemas.

#### `get_status() → dict`

Returns the full device status, delegated directly to the underlying instance.  The response shape differs between generations — Gen1 is a flat dict; Gen2 is keyed by component identifier.

```python
status = device.get_status()

# Gen1 example keys: relays, meters, wifi_sta, cloud, update, ...
# Gen2 example keys: "switch:0", "cover:0", "sys", "wifi", ...
```

#### `generation` property

```python
device.generation   # int — 1, 2, 3, or 4
```

For devices obtained via `connect()` this is read from the `/shelly` probe response (no extra network call).  For devices passed directly to the constructor, Gen1 always returns `1`; for Gen2+ the generation is fetched from `get_device_info()` on first access and then cached.

---

### Switch / Relay (Device)

All methods accept a `channel` parameter (0-based index, default `0`) matching the relay or switch instance.

#### `turn_on(channel=0, timer=None) → dict`

Turn a relay/switch channel ON.

```python
device.turn_on(0)                  # channel 0
device.turn_on(1)                  # channel 1 (multi-channel devices)
device.turn_on(0, timer=30)        # ON, auto-off after 30 s
device.turn_on(0, timer=3600)      # ON for 1 hour
```

#### `turn_off(channel=0, timer=None) → dict`

Turn a relay/switch channel OFF.

```python
device.turn_off(0)
device.turn_off(0, timer=60)       # OFF, auto-on after 60 s
```

#### `toggle(channel=0) → dict`

Toggle the current output state.

```python
device.toggle(0)
```

#### `get_switch_status(channel=0) → dict`

Return the current state of a relay/switch channel.  The response is raw from the device.

```python
status = device.get_switch_status(0)

# Gen1 keys include: ison, has_timer, timer_remaining, source
# Gen2 keys include: id, output, source, apower, voltage, current
if isinstance(device.underlying, ShellyGen1):
    print("On:", status["ison"])
else:
    print("On:", status["output"])
```

---

### Cover / Roller (Device)

All cover methods accept a `channel` parameter (default `0`).

> **Duration units:** `ShellyDevice` always accepts duration in **seconds** for all methods.  Gen1 devices internally use milliseconds — the conversion is handled automatically.

#### `cover_open(channel=0, duration=None)`

Open the cover (move in the open direction).

```python
device.cover_open(0)              # open fully
device.cover_open(0, duration=5)  # open for 5 seconds then stop
```

#### `cover_close(channel=0, duration=None)`

Close the cover.

```python
device.cover_close(0)
device.cover_close(0, duration=3.5)
```

#### `cover_stop(channel=0)`

Stop the cover motor immediately.

```python
device.cover_stop(0)
```

#### `cover_goto_position(channel=0, pos)`

Move to an absolute position.  Requires prior calibration on the device.

```python
device.cover_goto_position(0, pos=0)    # fully open
device.cover_goto_position(0, pos=50)   # halfway
device.cover_goto_position(0, pos=100)  # fully closed
```

#### `cover_calibrate(channel=0)`

Start automatic calibration.  The device will fully open and close to measure travel time.  Required before `cover_goto_position` can be used.

```python
device.cover_calibrate(0)
```

#### `get_cover_status(channel=0) → dict`

Return the raw cover/roller status.

```python
status = device.get_cover_status(0)
print(status["state"])        # "open", "closed", "opening", "closing", "stopped"
print(status["current_pos"])  # 0–100 (present on both gens when calibrated)
```

---

### Light / Dimmer (Device)

#### `light_on(channel=0, brightness=None) → dict`

Turn a light channel ON.

```python
device.light_on(0)                  # ON at current brightness
device.light_on(0, brightness=75)   # ON at 75 %
device.light_on(0, brightness=10)   # ON dimmed to 10 %
```

#### `light_off(channel=0) → dict`

Turn a light channel OFF.

```python
device.light_off(0)
```

#### `light_toggle(channel=0) → dict`

Toggle a light channel.

```python
device.light_toggle(0)
```

#### `get_light_status(channel=0) → dict`

Return the raw light status.

```python
status = device.get_light_status(0)

# Gen1 keys: ison, brightness, mode, red, green, blue, white, gain, temp, ...
# Gen2 keys: id, output, brightness, timer_started_at, timer_duration, ...
```

---

### System Operations (Device)

#### `reboot()`

Reboot the device.

```python
device.reboot()
```

#### `factory_reset()`

Perform a factory reset.  All settings and credentials are erased.

```python
device.factory_reset()
```

---

### Firmware (Device)

#### `check_for_update() → dict`

Ask the device to check the firmware server for available updates.

```python
result = device.check_for_update()

# Gen1 response:  {"status": "ok"} or {"status": "running"}
# Gen2 response:  {"stable": {"version": "1.3.3"}, "beta": {"version": "1.4.0-beta1"}}
```

#### `update_firmware(url=None, beta=False)`

Trigger a firmware update.

```python
device.update_firmware()                      # install latest stable
device.update_firmware(beta=True)             # install latest beta
device.update_firmware(url="http://...")      # install from custom URL
```

---

### WiFi & Cloud (Device)

#### `wifi_scan() → dict`

Scan for nearby WiFi networks.

```python
networks = device.wifi_scan()
# Response shape differs between generations
```

#### `get_cloud_status() → dict`

Return cloud connectivity status.  Both generations include at least `"connected": bool`.

```python
status = device.get_cloud_status()
print(status["connected"])   # True / False
```

#### `set_cloud_enabled(enabled)`

Enable or disable Shelly Cloud connectivity.

```python
device.set_cloud_enabled(True)
device.set_cloud_enabled(False)
```

---

### Authentication Management (Device)

#### `set_auth(password, username="admin")`

Set or remove the device password.  The local session is updated simultaneously so subsequent calls continue to work.

```python
device.set_auth("newsecret")           # enable / change password
device.set_auth(None)                  # disable auth
device.set_auth("secret", "admin")     # explicit username (Gen1 only)
```

---

### Accessing Generation-Specific Features

Use `device.underlying` to reach the full typed API:

```python
from shelly import ShellyDevice, ShellyGen1, ShellyGen2

device = ShellyDevice.connect("192.168.1.101", password="secret")

if isinstance(device.underlying, ShellyGen2):
    gen2 = device.underlying

    # KVS
    gen2.kvs_set("my_key", "hello")
    print(gen2.kvs_get("my_key"))      # {"etag": "...", "value": "hello"}

    # Schedules
    gen2.schedule_create(
        timespec="0 0 8 * * MON,TUE,WED,THU,FRI",
        calls=[{"method": "Switch.Set", "params": {"id": 0, "on": True}}],
    )

    # Scripts
    script = gen2.script_create(name="morning")
    gen2.script_put_code(script["id"], "print('good morning')")
    gen2.script_start(script["id"])

elif isinstance(device.underlying, ShellyGen1):
    gen1 = device.underlying

    # TRV
    gen1.set_thermostat(0, target_t=21.5)

    # External sensors
    print(gen1.get_ext_temperature(0))
```

---

## ShellyCloud — Cloud Control API

`ShellyCloud` communicates with Shelly devices through Shelly's cloud servers.  The target device does **not** need to be on the same local network — it only needs to be online and registered to the account.

This is the only class in the library that requires an internet connection.  All others (`ShellyGen1`, `ShellyGen2`, `ShellyDevice`) communicate directly with the device over the local network.

### Setup & Credentials

You need two pieces of information, both available in the **Shelly Cloud mobile app** under **User Settings → Authorization cloud key**:

| Item | Description |
|---|---|
| **server** | Your assigned cloud server hostname, e.g. `shelly-13-eu.shelly.cloud`.  This is account-specific and may change if Shelly migrates your account. |
| **auth_key** | Your personal authorization key.  Anyone with this key can control all your devices — treat it as a password.  It is invalidated whenever you change your account password. |

> **Rate limit:** Shelly's servers enforce **1 request per second**.  The library does not throttle automatically — your code must observe this limit.

### Constructor (Cloud)

```python
ShellyCloud(server, auth_key, timeout=10.0)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `server` | `str` | — | Your cloud server hostname |
| `auth_key` | `str` | — | Your authorization key |
| `timeout` | `float` | `10.0` | HTTP request timeout in seconds |

```python
from shelly import ShellyCloud

cloud = ShellyCloud(
    server="shelly-13-eu.shelly.cloud",
    auth_key="MTIzNDU2Nzg5MGFiY2RlZg==",
)
```

Use as a context manager to close the HTTP session automatically:

```python
with ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="...") as cloud:
    cloud.turn_on("b48a0a1cd978")
# session closed here
```

---

### Reading Device State

#### `get_devices_state(ids, select=None, pick=None) → list[dict]`

Fetch the state of up to **10 devices** in a single request.

| Parameter | Type | Description |
|---|---|---|
| `ids` | `list[str]` | 1–10 device IDs (hex strings) |
| `select` | `list[str] \| None` | Sections to return: any of `"status"`, `"settings"`.  Omit for both. |
| `pick` | `dict \| None` | Restrict which top-level keys to return per section |

Each dict in the returned list contains at minimum:

| Key | Description |
|---|---|
| `id` | Device ID (hex string) |
| `type` | Device type category, e.g. `"relay"`, `"light"` |
| `code` | Model code, e.g. `"SNPL-00112EU"` |
| `gen` | Generation string: `"G1"`, `"G2"`, etc. |
| `online` | `1` = online, `0` = offline |
| `status` | Present when `"status"` is in `select` |
| `settings` | Present when `"settings"` is in `select` |

```python
# Fetch both sections for two devices
states = cloud.get_devices_state(
    ids=["b48a0a1cd978", "dc4f2276846a"],
    select=["status", "settings"],
)

for dev in states:
    print(f"{dev['id']}  online={dev['online']}  type={dev['type']}")

# Only online check (no status body):
states = cloud.get_devices_state(["b48a0a1cd978"])
print(states[0]["online"])

# Only specific sub-keys (reduce response size):
states = cloud.get_devices_state(
    ids=["b48a0a1cd978"],
    select=["status"],
    pick={"status": ["sys", "switch:0"]},
)
sys_info = states[0]["status"]["sys"]
print(sys_info["uptime"])        # seconds since last reboot
print(sys_info["ram_free"])      # free RAM in bytes

# Check for available firmware update:
states = cloud.get_devices_state(
    ids=["b48a0a1cd978"],
    select=["status"],
    pick={"status": ["sys"]},
)
updates = states[0]["status"]["sys"].get("available_updates", {})
if "stable" in updates:
    print(f"Firmware update available: {updates['stable']['version']}")
```

---

### Switch / Relay Control (Cloud)

#### `set_switch(device_id, on, channel=0, toggle_after=None)`

Set the output state of a switch/relay channel.

```python
cloud.set_switch("b48a0a1cd978", on=True)
cloud.set_switch("b48a0a1cd978", on=False, channel=1)
cloud.set_switch("b48a0a1cd978", on=True, toggle_after=30)  # auto-off in 30 s
```

#### `turn_on(device_id, channel=0, toggle_after=None)`

```python
cloud.turn_on("b48a0a1cd978")
cloud.turn_on("b48a0a1cd978", channel=1)
cloud.turn_on("b48a0a1cd978", toggle_after=3600)   # ON for 1 hour
```

#### `turn_off(device_id, channel=0, toggle_after=None)`

```python
cloud.turn_off("b48a0a1cd978")
cloud.turn_off("b48a0a1cd978", toggle_after=60)    # OFF, auto-on in 60 s
```

---

### Cover / Roller Control (Cloud)

#### `set_cover(device_id, channel=0, position=None, duration=None, relative=None, slat_position=None, slat_relative=None)`

Full cover control in a single call.

| Parameter | Type | Description |
|---|---|---|
| `position` | `"open"`, `"close"`, `"stop"`, or `int` 0–100 | Target position.  Integer = absolute % (0 = open, 100 = closed).  Mutually exclusive with `relative`. |
| `duration` | `float` | Move for this many seconds then stop.  Only valid with `"open"`, `"close"`, or `"stop"` (not with a numeric position). |
| `relative` | `int` −100–100 | Move by a relative amount.  Mutually exclusive with `position`. |
| `slat_position` | `int` 0–100 | Slat angle (devices with slat support).  Mutually exclusive with `slat_relative`. |
| `slat_relative` | `int` −100–100 | Relative slat change.  Mutually exclusive with `slat_position`. |

```python
cloud.set_cover("dc4f2276846a", position="open")
cloud.set_cover("dc4f2276846a", position="close", duration=5)
cloud.set_cover("dc4f2276846a", position=75)       # 75 % closed
cloud.set_cover("dc4f2276846a", relative=-20)      # open by 20 %
cloud.set_cover("dc4f2276846a", slat_position=45)  # set slat angle
```

#### `cover_open(device_id, channel=0, duration=None)`

```python
cloud.cover_open("dc4f2276846a")
cloud.cover_open("dc4f2276846a", duration=3)   # open for 3 s then stop
```

#### `cover_close(device_id, channel=0, duration=None)`

```python
cloud.cover_close("dc4f2276846a")
cloud.cover_close("dc4f2276846a", duration=2)
```

#### `cover_stop(device_id, channel=0)`

```python
cloud.cover_stop("dc4f2276846a")
```

#### `cover_goto_position(device_id, pos, channel=0)`

Move to an absolute position.  Requires prior calibration on the device.

```python
cloud.cover_goto_position("dc4f2276846a", pos=0)    # fully open
cloud.cover_goto_position("dc4f2276846a", pos=50)   # halfway
cloud.cover_goto_position("dc4f2276846a", pos=100)  # fully closed
```

---

### Light Control (Cloud)

#### `set_light(device_id, channel=0, on=None, toggle_after=None, mode=None, brightness=None, temperature=None, red=None, green=None, blue=None, white=None, gain=None, effect=None)`

Full light control.  `on` is required when no other parameters are supplied.

| Parameter | Range | Description |
|---|---|---|
| `on` | `bool` | Power state |
| `toggle_after` | `float` | Auto-revert delay in seconds |
| `mode` | `"color"` or `"white"` | Light mode (devices that support switching) |
| `brightness` | 0–100 | Brightness % (white mode / dimmers) |
| `temperature` | 2700–7000 | Colour temperature in Kelvin (white mode) |
| `red`, `green`, `blue` | 0–255 | RGB channel values (colour mode) |
| `white` | 0–255 | White channel (colour mode with white channel) |
| `gain` | 0–100 | Overall brightness multiplier (colour mode) |
| `effect` | 0–6 | Animated effect index |

```python
# Simple on/off
cloud.set_light("e8db84afab12", on=True)
cloud.set_light("e8db84afab12", on=False)

# Dimmer
cloud.set_light("e8db84afab12", on=True, brightness=60)

# White mode with colour temperature
cloud.set_light("e8db84afab12", on=True, mode="white", temperature=3000, brightness=80)

# Colour mode
cloud.set_light("e8db84afab12", on=True, mode="color", red=255, green=120, blue=0, gain=80)

# Auto-off after 30 minutes
cloud.set_light("e8db84afab12", on=True, toggle_after=1800)

# Animated effect
cloud.set_light("e8db84afab12", on=True, effect=3)
```

#### `light_on(device_id, channel=0, brightness=None, toggle_after=None)`

```python
cloud.light_on("e8db84afab12")
cloud.light_on("e8db84afab12", brightness=50)
cloud.light_on("e8db84afab12", brightness=100, toggle_after=600)
```

#### `light_off(device_id, channel=0)`

```python
cloud.light_off("e8db84afab12")
```

---

### Group Control

#### `set_groups(switch=None, cover=None, light=None) → dict`

Control multiple devices of different types in a **single request**.  Mix and match: send switch, cover, and light commands simultaneously.

Each argument is a dict with two keys:
- `ids` — list of `"<DEVICE_ID>_<CHANNEL>"` strings (channel suffix defaults to `0` if omitted)
- `command` — the command payload (same parameters as the single-device method)

At least one of `switch`, `cover`, `light` must be provided.

**Return value:** An empty dict on full success.  When individual devices fail the server still returns HTTP 200 and populates `failedCommands`:

```python
{
    "failedCommands": {
        "b48a0a1cd978_0": "DEVICE_OFFLINE",
        "dc4f2276846a_1": "DEVICE_INVALID_CHANNEL",
    }
}
```

| Group failure string | Meaning |
|---|---|
| `DEVICE_UNSUPPORTED_COMMAND` | Device received an unknown command |
| `BAD_REQUEST` | Invalid command parameters for this device |
| `DEVICE_NOT_FOUND` | Device state not found in cloud |
| `UNEXPECTED_SUBSERVICE_ERROR` | Internal cloud error |
| `DEVICE_FAILED_COMMAND` | Device could not execute the command |

```python
# Turn on three switches at once
result = cloud.set_groups(
    switch={
        "ids": ["b48a0a1cd978_0", "dc4f2276846a_0", "a1b2c3d4e5f6_0"],
        "command": {"on": True},
    }
)
if result.get("failedCommands"):
    for dev_id, error in result["failedCommands"].items():
        print(f"  {dev_id} failed: {error}")

# Open all covers in a room
result = cloud.set_groups(
    cover={
        "ids": ["dc4f2276846a_0", "dc4f2276846a_1"],
        "command": {"position": "open"},
    }
)

# Turn on all lights and set brightness
result = cloud.set_groups(
    light={
        "ids": ["e8db84afab12_0", "f1a2b3c4d5e6_0"],
        "command": {"on": True, "brightness": 80},
    }
)

# Mix types in one request — switches ON, covers open, lights to 50 %
result = cloud.set_groups(
    switch={
        "ids": ["b48a0a1cd978_0"],
        "command": {"on": True},
    },
    cover={
        "ids": ["dc4f2276846a_0"],
        "command": {"position": "open"},
    },
    light={
        "ids": ["e8db84afab12_0"],
        "command": {"on": True, "brightness": 50},
    },
)

# Auto-off a group of switches after 30 minutes
result = cloud.set_groups(
    switch={
        "ids": ["b48a0a1cd978_0", "dc4f2276846a_0"],
        "command": {"on": True, "toggle_after": 1800},
    }
)

# Move a group of covers to 30 %
result = cloud.set_groups(
    cover={
        "ids": ["dc4f2276846a_0", "aabbccddeeff_0"],
        "command": {"position": 30},
    }
)
```

---

### Error Handling (Cloud)

```python
from shelly import ShellyCloud, ShellyCloudError, ShellyAuthError, ShellyConnectionError

with ShellyCloud("shelly-13-eu.shelly.cloud", auth_key="abc123") as cloud:

    # Single-device errors are raised as ShellyCloudError
    try:
        cloud.turn_on("b48a0a1cd978")
    except ShellyCloudError as e:
        print(f"Error: {e.error}")        # e.g. "DEVICE_OFFLINE"
        print(f"Details: {e.messages}")   # list of server messages

    # Auth errors
    try:
        cloud.turn_on("b48a0a1cd978")
    except ShellyAuthError:
        print("auth_key is invalid or was invalidated by a password change")

    # Network errors
    try:
        cloud.turn_on("b48a0a1cd978")
    except ShellyConnectionError:
        print("Cannot reach Shelly Cloud servers")

    # Group commands: partial failures do NOT raise — check the return value
    result = cloud.set_groups(
        switch={"ids": ["b48a0a1cd978_0", "offline_device_0"], "command": {"on": True}}
    )
    if "failedCommands" in result:
        for dev, err in result["failedCommands"].items():
            print(f"  {dev}: {err}")
```

---

## ShellyGen1 — First-Generation Devices

Covers: Shelly1, Shelly1PM, Shelly1L, Shelly2, Shelly2.5, Shelly4Pro, ShellyPlug, ShellyPlugS, Shelly i3, ShellyButton1, ShellyBulb, ShellyVintage, ShellyDuo, ShellyDimmer1/2, ShellyRGBW2, ShellyEM, Shelly3EM, ShellyH&T, ShellySmoke, ShellyFlood, ShellyDoor/Window 1&2, ShellyMotion, ShellyTRV, ShellyGas, ShellySense, ShellyUni.

### Constructor (Gen1)

```python
ShellyGen1(
    host,              # str  — IP address or hostname
    port=80,           # int  — HTTP port
    timeout=10.0,      # float — request timeout in seconds
    username="admin",  # str  — Basic Auth username
    password=None,     # str | None — Basic Auth password
)
```

```python
sw = ShellyGen1("192.168.1.100")
sw = ShellyGen1("shelly1-B929CC.local")
sw = ShellyGen1("192.168.1.100", password="secret")
sw = ShellyGen1("192.168.1.100", timeout=3.0, password="secret")
```

---

### Device Information & Status

#### `get_info() → dict`

Always accessible without auth.  Returns basic identification.

```python
info = sw.get_info()
# {
#   "type": "SHSW-1",
#   "mac": "98F4ABB929CC",
#   "auth": false,
#   "fw": "20230808-130340/v1.14.0-gcb84623",
#   "longid": 1,
#   "discoverable": true
# }

print(info["type"])   # Model identifier, e.g. "SHSW-25"
print(info["mac"])    # Hardware MAC address (no colons)
print(info["auth"])   # True if HTTP Basic Auth is currently enabled
print(info["fw"])     # Firmware version string
```

**Known model identifiers:**

| `type` | Device |
|---|---|
| `SHSW-1` | Shelly1 |
| `SHSW-PM` | Shelly1PM |
| `SHSW-25` | Shelly2.5 |
| `SHSW-44` | Shelly4Pro |
| `SHPLG-S` | ShellyPlugS |
| `SHIX3-1` | Shelly i3 |
| `SHBLB-1` | ShellyBulb |
| `SHDM-2` | ShellyDimmer2 |
| `SHRGBW2` | ShellyRGBW2 |
| `SHEM` | ShellyEM |
| `SHEM-3` | Shelly3EM |
| `SHHT-1` | ShellyH&T |
| `SHTRV-01` | ShellyTRV |

#### `get_status() → dict`

Returns the full runtime state of the device.

```python
status = sw.get_status()

# Common fields in every status response:
print(status["wifi_sta"]["ip"])      # Device IP address
print(status["wifi_sta"]["rssi"])    # WiFi signal in dBm
print(status["cloud"]["connected"])  # Cloud connectivity
print(status["mqtt"]["connected"])   # MQTT connectivity
print(status["uptime"])              # Seconds since last boot
print(status["ram_free"])            # Free heap in bytes
print(status["has_update"])          # Firmware update available
print(status["update"]["status"])    # "idle" | "pending" | "updating" | "unknown"

# Relay devices add:
print(status["relays"][0]["ison"])   # Current relay state

# Metered relay devices also add:
print(status["meters"][0]["power"])  # Instantaneous power in Watts

# Sensor devices add:
print(status["tmp"]["tC"])           # Temperature in °C (H&T, Smoke, etc.)
print(status["hum"]["value"])        # Relative humidity % (H&T)
print(status["bat"]["value"])        # Battery % (battery devices)
print(status["flood"])               # True if flooding detected (ShellyFlood)
```

---

### Global Settings

#### `get_settings() → dict`

Returns the complete device configuration.

```python
cfg = sw.get_settings()
print(cfg["name"])              # Device name (if set)
print(cfg["timezone"])          # IANA timezone string
print(cfg["mqtt"]["enable"])    # MQTT enabled flag
print(cfg["coiot"]["enabled"])  # CoIoT enabled flag
```

#### `set_settings(**params) → dict`

Updates one or more global settings.  All parameters are optional.

```python
# Set device name and timezone
sw.set_settings(name="Living Room Switch", timezone="America/New_York")

# Enable MQTT
sw.set_settings(
    mqtt_enable=True,
    mqtt_server="192.168.1.10:1883",
    mqtt_user="shelly",
    mqtt_pass="mqttpass",
    mqtt_update_period=30,
)

# Enable CoIoT with unicast peer
sw.set_settings(
    coiot_enable=True,
    coiot_update_period=15,
    coiot_peer="192.168.1.50:5683",  # empty string = multicast
)

# Set NTP server
sw.set_settings(sntp_server="pool.ntp.org")

# Set geolocation for sunrise/sunset schedules
sw.set_settings(lat=40.7128, lng=-74.0060)

# Enable automatic timezone detection from IP
sw.set_settings(tzautodetect=True)

# Make device invisible to mDNS
sw.set_settings(discoverable=False)

# Factory reset via settings endpoint
sw.set_settings(reset=1)
```

---

### WiFi Configuration

#### `get_wifi_ap() → dict` / `set_wifi_ap(enabled, ssid=None, key=None) → dict`

```python
# Read current AP config
ap = sw.get_wifi_ap()
print(ap["enabled"])   # True if AP is active
print(ap["ssid"])      # AP network name

# Enable the Access Point
sw.set_wifi_ap(enabled=True)

# Disable the Access Point
sw.set_wifi_ap(enabled=False)

# Set a custom AP name and password
sw.set_wifi_ap(enabled=True, ssid="MyShelly", key="appassword")
```

#### `get_wifi_sta(index=0) → dict` / `set_wifi_sta(...) → dict`

`index=0` is the primary network; `index=1` is the fallback.

```python
# Read current STA config
sta = sw.get_wifi_sta()
print(sta["ssid"])           # Connected SSID

# Connect to a WiFi network (DHCP)
sw.set_wifi_sta(ssid="MyHomeNetwork", key="wifipassword")

# Connect with a static IP
sw.set_wifi_sta(
    ssid="MyHomeNetwork",
    key="wifipassword",
    ipv4_method="static",
    ip="192.168.1.50",
    gw="192.168.1.1",
    mask="255.255.255.0",
    dns="8.8.8.8",
)

# Configure the fallback network
sw.set_wifi_sta(ssid="BackupNetwork", key="backuppass", index=1)
```

#### `wifi_scan() → dict`

Only available when the device is in AP mode.

```python
results = sw.wifi_scan()
for net in results.get("results", []):
    print(net["ssid"], net["rssi"], net["channel"])
```

---

### Relay Control

Applies to: Shelly1, Shelly1PM, Shelly2, Shelly2.5 (relay mode), Shelly4Pro, ShellyPlug, ShellyPlugS.

#### State control

```python
# Simple on/off/toggle
sw.relay_on(0)        # Turn relay 0 ON
sw.relay_off(0)       # Turn relay 0 OFF
sw.relay_toggle(0)    # Toggle relay 0

# With auto-revert timer (seconds)
sw.relay_on(0, timer=30)    # ON, auto-off after 30 s
sw.relay_off(0, timer=10)   # OFF, auto-on after 10 s

# Generic setter
from shelly import RelayState
sw.set_relay(0, RelayState.ON)
sw.set_relay(0, "off", timer=60)

# Cancel an active timer
sw.set_relay(0, "on", timer=0)  # timer=0 cancels
```

#### Read relay state

```python
state = sw.get_relay(0)
# {
#   "ison": true,
#   "has_timer": false,
#   "timer_remaining": 0,
#   "source": "http",          # who triggered the last change
#   "overpower": false
# }

# Metered devices (1PM, PlugS, etc.) also include:
# "power": 52.3,     Watts
# "energy": 45678,   Watt-minutes cumulative
# "temperature": 38.2

print(state["ison"])           # True = ON
print(state["source"])         # "http" | "mqtt" | "cloud" | "input" | "schedule"
print(state.get("power", 0))  # 0 if device has no metering
```

#### Relay configuration

```python
# Read persistent config
cfg = sw.get_relay_settings(0)
print(cfg["default_state"])  # What to do on power-on
print(cfg["btn_type"])       # How the physical button behaves

# Update config
sw.set_relay_settings(
    0,
    default_state="restore",  # "off" | "on" | "restore" | "switch"
    btn_type="momentary",     # "toggle" | "edge" | "detached" | "momentary"
    btn_reverse=0,            # 1 to invert button logic
    auto_off=300.0,           # auto-off after 5 minutes (0 = disabled)
    auto_on=0.0,
    max_power=2000.0,         # overpower threshold in Watts
    name="Main Light",
)
```

---

### Power Metering

Applies to: Shelly1PM, ShellyPlugS, Shelly2.5, Shelly4Pro, ShellyEM, Shelly3EM.

```python
meter = sw.get_meter(0)
# {
#   "power": 52.3,         current power in Watts
#   "overpower": 0.0,      overpower threshold value
#   "is_valid": true,
#   "timestamp": 1691500960,
#   "counters": [125.5, 130.2, 128.1],  last 3 × 1-min Watt-minute averages
#   "total": 45678          cumulative Watt-minutes
# }

print(f"Current power: {meter['power']} W")
print(f"Total energy: {meter['total'] / 60:.1f} Wh")  # convert Wmin → Wh

# Shelly2.5 in relay mode has two meters
m0 = sw.get_meter(0)
m1 = sw.get_meter(1)
```

---

### Energy Metering (EM / 3EM)

Applies to: ShellyEM, Shelly3EM.

```python
# Read a single phase (index 0, 1, or 2 for 3EM)
em = sw.get_emeter(0)
# {
#   "power": 235.7,       W  active power
#   "pf": 0.98,           power factor
#   "current": 1.02,      A  RMS current
#   "voltage": 230.8,     V  RMS voltage
#   "is_valid": true,
#   "total": 12345.6,     Wh cumulative consumed
#   "total_returned": 0.0,Wh cumulative exported (solar / generator)
#   "reactive": 15.2      VAr reactive power
# }

print(f"Phase A: {em['voltage']:.1f} V, {em['current']:.2f} A, {em['power']:.1f} W")

# Reset energy counters (total and total_returned → 0)
sw.reset_emeter(0)

# Reset all phases at once
sw.reset_all_energy_data()

# Configure alert thresholds
sw.set_emeter_settings(
    0,
    max_power=5000.0,
    over_power_url="http://192.168.1.10/alert?event=overpower",
    over_power_url_threshold=4500.0,
)
```

---

### Roller / Cover Control

Applies to: Shelly2.5 when configured in roller mode.

#### Basic movement

```python
sw.roller_open(0)            # Move in the open direction
sw.roller_close(0)           # Move in the close direction
sw.roller_stop(0)            # Stop immediately

# Move for a fixed time (milliseconds)
sw.roller_open(0, duration=3000)   # Open for 3 seconds then stop
sw.roller_close(0, duration=2000)
```

#### Position control (requires calibration)

```python
# First-time setup: run calibration
sw.calibrate_roller(0)
# The device will fully open and close to measure travel time.
# Wait for it to complete before using position control.

# Go to a specific position (0 = open, 100 = closed)
sw.roller_to_position(0, pos=50)   # Half-open
sw.roller_to_position(0, pos=0)    # Fully open
sw.roller_to_position(0, pos=100)  # Fully closed

# Generic command
from shelly import Gen1RollerDirection
sw.set_roller(0, Gen1RollerDirection.TO_POS, pos=75)
sw.set_roller(0, "open", duration=2000)
```

#### Read roller state

```python
state = sw.get_roller(0)
# {
#   "state": "stop",           "open" | "close" | "stop"
#   "power": 0.0,              motor power in Watts
#   "current_pos": 50,         0=open, 100=closed (if calibrated)
#   "target_pos": 50,
#   "stop_reason": "normal",   "normal" | "limit" | "safety_switch"
#   "last_direction": "close",
#   "positioning": true        position tracking active
# }
```

#### Roller configuration

```python
sw.set_roller_settings(
    0,
    maxtime_open=20.0,         # max travel seconds
    maxtime_close=20.0,
    default_state="stop",      # power-on state: "stop" | "open" | "close"
    swap=False,                # swap open/close direction
    obstacle_mode="reverse",   # "reverse" or "stop" when motor stalls
    positioning=True,          # enable position tracking
)
```

---

### Light Control

#### Dimmers (ShellyDimmer1/2, ShellyVintage)

```python
# Turn on / off / toggle
sw.light_on(0)
sw.light_off(0)
sw.light_toggle(0)

# Set brightness (0–100%)
sw.light_on(0, brightness=75)

# Gradual transition to 50% over 2 seconds
sw.set_light(0, turn="on", brightness=50, transition=2000)

# Incremental dimming (Dimmer only)
sw.set_light(0, dim="up", step=10)    # +10%
sw.set_light(0, dim="down", step=5)   # -5%

# Auto-off timer
sw.light_on(0, timer=3600)   # auto-off after 1 hour
```

#### RGBW Bulbs (ShellyBulb, ShellyRGBW2 colour mode)

```python
# Colour mode: set RGB + white + gain
sw.set_light(
    0,
    turn="on",
    mode="color",
    red=255, green=100, blue=0, white=0,
    gain=80,              # overall brightness (0–100%)
    transition=500,       # 500 ms fade
)

# White mode: set brightness + colour temperature
sw.set_light(
    0,
    turn="on",
    mode="white",
    brightness=70,
    temp=4000,            # Kelvin (3000–6500)
)

# Use dedicated colour/white endpoints
sw.set_color(0, turn="on", red=0, green=255, blue=128, white=50, gain=100)
sw.set_white(0, turn="on", brightness=80, temp=3000)
```

#### RGBW2 — 4 independent white channels

```python
# Control each channel individually
sw.set_white(0, turn="on", brightness=100)
sw.set_white(1, turn="on", brightness=60)
sw.set_white(2, turn="off")
sw.set_white(3, turn="on", brightness=30)
```

#### Night mode

```python
sw.set_night_mode(
    enabled=True,
    brightness=20,
    active_between=["23:00", "06:00"],
)
```

#### Light configuration

```python
sw.set_light_settings(
    0,
    default_state="restore_last",
    auto_off=3600.0,         # auto-off after 1 hour
    transition=1000,         # default 1-second fade
    min_brightness=5,        # minimum brightness floor
)
```

---

### URL Action Callbacks

Gen1 devices can call HTTP URLs when events occur (relay toggled, sensor threshold crossed, etc.).

```python
# Read all configured actions
actions = sw.get_actions()
# {
#   "actions": {
#     "out_on_url":  [{"index": 0, "urls": [...], "enabled": true}],
#     "out_off_url": [{"index": 0, "urls": [],    "enabled": false}],
#     ...
#   }
# }

# Set an action: call a URL when relay 0 turns ON
sw.set_action(
    name="out_on_url",
    urls=["http://192.168.1.10/on"],
    index=0,
    enabled=True,
)

# Multiple URLs (up to 5) — all are called in sequence
sw.set_action(
    name="out_off_url",
    urls=[
        "http://192.168.1.10/off",
        "http://192.168.1.20/notify?relay=off",
    ],
    index=0,
    enabled=True,
)

# Disable an action without clearing its URLs
sw.set_action(name="out_on_url", urls=[], index=0, enabled=False)

# Self-referencing action: device calls itself (no external server needed)
sw.set_action(
    name="out_on_url",
    urls=["http://localhost/relay/1?turn=on"],
    index=0,
    enabled=True,
)
```

**Common action names by device type:**

| Device | Action names |
|---|---|
| Relay | `out_on_url`, `out_off_url`, `over_power_url`, `btn_on_url`, `btn_off_url`, `shortpush_url`, `longpush_url` |
| Roller | `roller_open_url`, `roller_close_url`, `roller_stop_url` |
| H&T sensor | `over_temp_url`, `under_temp_url`, `over_hum_url`, `under_hum_url` |
| Flood | `flood_detected_url`, `flood_gone_url` |
| Door/Window | `open_url`, `close_url`, `vibration_url` |
| Smoke | `alarm_url`, `alarm_off_url` |
| Gas | `alarm_url`, `alarm_clear_url`, `self_test_url` |
| i3 / Button1 | `btn1_shortpush_url`, `btn1_longpush_url`, `btn2_shortpush_url`, … |

---

### External Sensors (Shelly1 Add-on)

The Shelly1/1PM supports an add-on that connects up to three DS1820 temperature probes and one DHT22 humidity sensor.

```python
# Read sensor configuration and last value
temp = sw.get_ext_temperature(0)   # sensor index 0, 1, or 2
# {
#   "0": {
#     "hwID": "XXXXXXXX",
#     "tC": 20.5,
#     "tF": 68.9,
#     "over_temp_threshold": 30,
#     "under_temp_threshold": 10,
#     "offset_tC": 0.0
#   }
# }

hum = sw.get_ext_humidity(0)
# { "0": { "hwID": "...", "hum": 55.3, "over_humidity_threshold": 75, ... } }

# Configure thresholds and calibration offset
sw.set_ext_temperature(
    0,
    over_temp_threshold=35.0,
    under_temp_threshold=5.0,
    offset_tC=-0.5,          # calibration correction
)

sw.set_ext_humidity(0, over_humidity_threshold=80, under_humidity_threshold=20)

# Latest readings are also available in /status:
status = sw.get_status()
print(status["ext_temperature"]["0"]["tC"])
print(status["ext_humidity"]["0"]["hum"])
```

---

### Input Channels (i3, Button1)

```python
# Read live input state
inp = sw.get_input(0)
# { "input": 0, "event": "S", "event_cnt": 12 }
# event: "S" = short push, "L" = long push, "" = no event since last read

# Configure input
sw.set_input_settings(
    0,
    btn_type="momentary",    # "toggle" | "momentary" | "edge" | "detached"
    btn_reverse=0,           # 1 to invert
    longpush_time=800,       # ms threshold for long press (default 1000)
    btn_debounce=80,         # ms debounce interval
)
```

---

### Analogue Input (Shelly Uni)

```python
# Read ADC voltage
adc = sw.get_adc(0)
# { "voltage": 3.42 }
print(f"ADC voltage: {adc['voltage']} V")

# Configure the ADC voltage range
sw.set_adc_settings(0, range="0:10")   # 0–10 V
```

---

### Thermostat / TRV

Applies to: ShellyTRV.

```python
# Read current thermostat state
trv = sw.get_thermostat(0)
# {
#   "pos": 55,              valve position 0–100%
#   "target_t": { "enabled": true, "value": 21.5, "units": "C" },
#   "tmp": { "value": 20.1, "units": "C", "is_valid": true },
#   "schedule": false,
#   "boost_minutes": 0
# }

print(f"Target: {trv['target_t']['value']} °C")
print(f"Current: {trv['tmp']['value']} °C")
print(f"Valve: {trv['pos']}%")

# Set target temperature
sw.set_thermostat(0, target_t_enabled=True, target_t=22.0)

# Disable thermostat control (valve goes to manual/schedule mode)
sw.set_thermostat(0, target_t_enabled=False)
```

---

### Gas Detector

Applies to: ShellyGas.

```python
# Read sensor state
status = sw.get_status()
print(status["gas"]["alarm"])               # True if alarm active
print(status["gas"]["concentration_ppm"])   # Gas concentration

# Valve control
valve = sw.get_valve(0)
print(valve["state"])   # "open" | "closed" | "opening" | "closing"

sw.set_valve(0, "close")   # Close the gas valve
sw.set_valve(0, "open")    # Open the gas valve

# Sensor operations
sw.gas_self_test()   # Trigger sensor self-test
sw.gas_mute()        # Silence the alarm buzzer
sw.gas_unmute()      # Restore alarm sound
```

---

### Door/Window Sensor

Applies to: ShellyDW1, ShellyDW2.

```python
status = sw.get_status()
print(status["sensor"]["state"])       # "open" | "close"
print(status["sensor"]["is_valid"])    # False if sensor error
print(status["lux"]["value"])          # Ambient light in lux
print(status["accel"]["tilt"])         # Tilt angle (0–180°)
print(status["accel"]["vibration"])    # Vibration count

# Calibrate the open-position tilt angle
sw.calibrate_door_window(opened=True)   # calibrate the OPEN position
sw.calibrate_door_window(opened=False)  # clear calibration
```

---

### Firmware Management (Gen1)

```python
# Check current firmware info
ota = sw.get_ota_status()
print(ota["status"])       # "idle" | "pending" | "updating" | "unknown"
print(ota["has_update"])   # True if stable update available
print(ota["new_version"])
print(ota["old_version"])

# Trigger update check against Shelly servers
sw.check_update()

# Install latest stable firmware
sw.update_firmware()

# Install latest beta firmware
sw.update_firmware(beta=True)

# Install from a custom URL
sw.update_firmware(url="http://192.168.1.10/custom_fw.bin")
```

---

### Reboot & Factory Reset (Gen1)

```python
sw.reboot()           # Restart the device (returns immediately)
sw.factory_reset()    # Full factory reset (erases all settings)

# Reset STA connection cache (battery devices only)
sw.reset_sta_cache()

# Read debug log
log = sw.get_debug_log()        # /debug/log
log1 = sw.get_debug_log(1)      # /debug/log1 (second log)
```

---

## ShellyGen2 — Second-Generation and Newer Devices

Covers: ShellyPlus1, ShellyPlus1PM, ShellyPlus2PM, ShellyPlusPlugS, ShellyPlusDimmerUS, ShellyPro4PM, ShellyPro3EM, ShellyProEM, ShellyPlus H&T, ShellyPlusSmoke, ShellyBluButton1, and all Gen3/Gen4 devices.

### Constructor (Gen2)

```python
ShellyGen2(
    host,         # str   — IP address or hostname
    port=80,      # int   — HTTP port
    timeout=10.0, # float — request timeout in seconds
    password=None,# str | None — SHA-256 Digest Auth password
)
```

```python
sw = ShellyGen2("192.168.1.101")
sw = ShellyGen2("shellypro4pm-aabbcc.local")
sw = ShellyGen2("192.168.1.101", password="secret")
sw = ShellyGen2("192.168.1.101", timeout=5.0, password="secret")
```

---

### Core RPC Call

All Gen2 functionality is built on `call()`.  You can use it directly to invoke any method not covered by a named wrapper, or to use device-specific methods.

```python
# Generic call: method name + params dict
result = sw.call("Switch.Set", {"id": 0, "on": True})

# Call with no params
result = sw.call("Shelly.GetStatus")

# Call a method not wrapped in the library
result = sw.call("BTHome.StartDeviceDiscovery", {"duration": 10})

# On error, a ShellyRPCError is raised
from shelly import ShellyRPCError
try:
    sw.call("Switch.Set", {"id": 99, "on": True})
except ShellyRPCError as e:
    print(e.code, e)   # -105, "RPC error -105: Bad id=99"
```

---

### Device Management (Shelly.*)

#### `get_device_info(ident=False) → dict`

Always accessible without auth.

```python
info = sw.get_device_info()
# {
#   "id": "shellypro4pm-f008d1d8b8b8",
#   "mac": "F008D1D8B8B8",
#   "model": "SPSW-004PE16EU",
#   "gen": 2,
#   "fw_id": "20210720-153353/0.6.7-gc36674b",
#   "ver": "0.6.7",
#   "app": "FourPro",
#   "auth_en": false,
#   "auth_domain": "shellypro4pm-f008d1d8b8b8",
#   "discoverable": true
# }

print(info["id"])       # Unique device ID (hostname without .local)
print(info["mac"])      # Hardware MAC address
print(info["model"])    # Hardware model string
print(info["gen"])      # 2, 3, or 4
print(info["ver"])      # Firmware version, e.g. "1.2.3"
print(info["auth_en"])  # True if auth is enabled
```

#### `get_status() → dict`

```python
status = sw.get_status()

# Component keys follow the pattern <type>:<id>
print(status["switch:0"]["output"])   # True = ON
print(status["switch:0"]["apower"])   # Watts
print(status["switch:0"]["voltage"])  # Volts
print(status["switch:0"]["aenergy"]["total"])  # Wh

print(status["sys"]["uptime"])        # Seconds since boot
print(status["sys"]["ram_free"])      # Free heap bytes
print(status["wifi"]["sta_ip"])       # IP address
print(status["wifi"]["rssi"])         # Signal strength dBm
print(status["cloud"]["connected"])   # Cloud connectivity

# Cover device:
print(status["cover:0"]["state"])     # "open"/"closed"/"opening"/etc.
print(status["cover:0"]["current_pos"])

# Light device:
print(status["light:0"]["output"])
print(status["light:0"]["brightness"])
```

#### `get_config() → dict`

```python
cfg = sw.get_config()
print(cfg["switch:0"]["name"])
print(cfg["sys"]["device"]["name"])
print(cfg["wifi"]["sta"]["ssid"])
```

#### Other management methods

```python
methods = sw.list_methods()          # List all supported RPC methods

sw.reboot()                          # Reboot (default 500 ms delay)
sw.reboot(delay_ms=2000)             # Reboot after 2 seconds

sw.factory_reset()                   # Erase all settings

sw.reset_wifi_config()               # Forget WiFi, revert to AP mode

location = sw.detect_location()      # Auto-detect timezone from public IP
# {"tz": "America/New_York", "lat": 40.71, "lon": -74.01}

profiles = sw.list_profiles()        # ["relay", "cover"] on ShellyPlus2PM
sw.set_profile("cover")              # Switch profile (requires reboot)
```

---

### Switch Component

Applies to devices with relay outputs: ShellyPlus1, ShellyPlus1PM, ShellyPro4PM, ShellyPlusPlugS, etc.

```python
# Turn on / off
sw.switch_set(0, on=True)
sw.switch_set(0, on=False)

# Toggle
result = sw.switch_toggle(0)
print(result["was_on"])   # True if it was ON before the toggle

# Auto-revert timer (seconds)
sw.switch_set(0, on=True, toggle_after=30)    # ON for 30 s then OFF
sw.switch_set(0, on=False, toggle_after=300)  # OFF for 5 min then ON

# Read live state
state = sw.switch_get_status(0)
# {
#   "id": 0,
#   "source": "http",       who triggered this: "http"|"WS_in"|"button"|"timer"|etc.
#   "output": true,         current state
#   "apower": 8.9,          instantaneous Watts
#   "voltage": 237.5,       Volts
#   "current": 0.037,       Amperes
#   "freq": 50.0,           Hz
#   "aenergy": {
#     "total": 6.532,               cumulative Wh
#     "by_minute": [45.2, 47.1, 88.4],  last 3 × 1-min Wh
#     "minute_ts": 1626935779
#   },
#   "temperature": {"tC": 23.5, "tF": 74.4}
# }

# Read configuration
cfg = sw.switch_get_config(0)
print(cfg["name"])           # Human-readable label
print(cfg["in_mode"])        # Physical button behaviour
print(cfg["initial_state"])  # Power-on state
print(cfg["auto_off"])       # Auto-off enabled flag
print(cfg["auto_off_delay"]) # Auto-off delay in seconds
print(cfg["power_limit"])    # Overpower threshold in Watts

# Update configuration
sw.switch_set_config(0, {
    "name": "Garden Lights",
    "in_mode": "follow",       # "momentary"|"follow"|"flip"|"detached"|"cycle"|"activate"
    "initial_state": "restore_last",  # "off"|"on"|"restore_last"|"match_input"
    "auto_off": True,
    "auto_off_delay": 3600.0,  # auto-off after 1 hour
    "power_limit": 2300.0,     # overpower protection at 2300 W
    "voltage_limit": 255.0,
    "current_limit": 10.0,
})

# Reset energy counters
sw.switch_reset_counters(0)
sw.switch_reset_counters(0, counter_types=["aenergy"])
```

---

### Cover Component

Applies to: ShellyPlus2PM in cover mode, ShellyCover, etc.

```python
# Basic movement
sw.cover_open(0)       # Move in the open direction
sw.cover_close(0)      # Move in the close direction
sw.cover_stop(0)       # Stop immediately

# Timed movement
sw.cover_open(0, duration=3.0)    # Open for 3 seconds then stop
sw.cover_close(0, duration=2.5)

# Position control (requires calibration first)
sw.cover_calibrate(0)             # Run the 5-step auto-calibration sequence

sw.cover_goto_position(0, pos=0)    # Fully open
sw.cover_goto_position(0, pos=100)  # Fully closed
sw.cover_goto_position(0, pos=50)   # Half open
sw.cover_goto_position(0, rel=10)   # Move 10% more closed relative to current
sw.cover_goto_position(0, rel=-20)  # Move 20% more open

# Read state
state = sw.cover_get_status(0)
# {
#   "id": 0,
#   "source": "limit_switch",
#   "state": "open",           "open"|"closed"|"opening"|"closing"|"stopped"|"calibrating"
#   "current_pos": 100,        0=open, 100=closed
#   "last_direction": "open",
#   "pos_control": true,       position tracking enabled
#   "apower": 0,
#   "voltage": 233,
#   "aenergy": { "total": 48.996, ... }
# }

print(state["state"])
print(state["current_pos"])

# Configuration
cfg = sw.cover_get_config(0)
sw.cover_set_config(0, {
    "name": "Bedroom Blinds",
    "in_mode": "dual",          # "single"|"dual"|"detached"
    "initial_state": "stopped",
    "power_limit": 100.0,
})

# Reset energy counters
sw.cover_reset_counters(0)
```

---

### Light Component

Applies to: ShellyDimmer0PM G3, ShellyPlusDimmerUS, etc.

```python
# Turn on / off
sw.light_set(0, on=True)
sw.light_set(0, on=False)

# Set brightness
sw.light_set(0, on=True, brightness=75)

# Transition (fade)
sw.light_set(0, on=True, brightness=50, transition_duration=2.0)

# Auto-revert
sw.light_set(0, on=True, toggle_after=3600.0)   # ON for 1 hour

# Toggle
result = sw.light_toggle(0)
print(result["was_on"])

# Continuous dimming
sw.light_dim_up(0, rate=3)     # Start dimming up (rate 1–5)
sw.light_dim_down(0, rate=2)   # Start dimming down
sw.light_dim_stop(0)           # Stop continuous dim

# Read state
state = sw.light_get_status(0)
# {
#   "id": 0, "source": "http",
#   "output": true, "brightness": 75,
#   "timer_started_at": ..., "timer_duration": ...
# }

# Configuration
sw.light_set_config(0, {
    "name": "Hall Light",
    "initial_state": "restore_last",  # "off"|"on"|"restore_last"
    "auto_off": True,
    "auto_off_delay": 300.0,
    "transition_duration": 1.5,
    "min_brightness_on_toggle": 3,
    "night_mode": {
        "enable": True,
        "brightness": 20,
        "active_between": ["22:00", "07:00"],
    },
})
```

---

### RGBW Component

Applies to: ShellyRGBW Gen2 devices.

```python
# Set colour and brightness
sw.rgbw_set(
    0,
    on=True,
    brightness=80,           # overall 0–100%
    rgb=[255, 100, 0],        # [R, G, B] each 0–255
    white=30,                # white channel 0–255
    transition_duration=1.0,
)

# Turn off
sw.rgbw_set(0, on=False)

# Toggle
result = sw.rgbw_toggle(0)

# Read state
state = sw.rgbw_get_status(0)
print(state["output"])
print(state["brightness"])
print(state["rgb"])     # [R, G, B]
print(state["white"])

# Configuration
sw.rgbw_set_config(0, {"name": "Desk Light"})
```

---

### Input Component

Applies to all devices with physical inputs.

```python
# Read input state
state = sw.input_get_status(0)

# Switch/button type:
print(state["state"])     # True = pressed/closed, False = released/open

# Analog type:
print(state["percent"])   # 0–100 %

# Count type:
print(state["counts"]["total"])
print(state["counts"]["by_minute"])   # last 3 minutes
print(state["freq"])                  # Hz

# Configure input type
sw.input_set_config(0, {
    "type": "button",   # "switch"|"button"|"analog"|"count"
    "enable": True,
    "invert": False,    # invert the logic state
})

# Simulate a button press event (testing)
sw.input_trigger(0, "single_push")
sw.input_trigger(0, "long_push")
sw.input_trigger(0, "double_push")

# Reset pulse counters (count-type inputs)
sw.input_reset_counters(0)
```

---

### Sensor Components

#### Temperature

```python
state = sw.temperature_get_status(0)
# {"tC": 22.5, "tF": 72.5, "errors": []}
# tC and tF are None when the sensor is disconnected or out of range

print(state["tC"])
if state["errors"]:
    print("Sensor errors:", state["errors"])   # e.g. ["read", "out_of_range"]

sw.temperature_set_config(0, {
    "name": "Room Temp",
    "report_thr_C": 0.5,    # report if change > 0.5 °C (default)
    "offset_C": -0.3,       # calibration offset
})
```

#### Humidity

```python
state = sw.humidity_get_status(0)
print(state["rh"])   # relative humidity %, or None on error

sw.humidity_set_config(0, {
    "report_thr": 1.0,   # report if change > 1%
    "offset": 2.0,       # calibration offset %
})
```

#### Voltmeter (analog sensor)

```python
state = sw.voltmeter_get_status(0)
print(state["voltage"])    # raw voltage
print(state["xvoltage"])   # transformed voltage (if expression configured)
```

#### Smoke sensor

```python
state = sw.smoke_get_status(0)
print(state["alarm"])   # True if smoke detected
print(state["mute"])    # True if alarm is muted

sw.smoke_mute(0)        # Silence the alarm
```

#### Battery / device power

```python
power = sw.device_power_get_status(0)
print(power["battery"]["V"])        # Battery voltage
print(power["battery"]["percent"])  # Battery level 0–100%
print(power["external"]["present"]) # True if external power is connected
```

---

### Energy Metering (Gen2)

#### Single-phase power meter (PM1 — ShellyPlus1PM, ShellyPlusPlugS)

```python
state = sw.pm1_get_status(0)
# {
#   "voltage": 230.1, "current": 0.5, "apower": 115.0,
#   "freq": 50.0, "pf": 1.0,
#   "aenergy": {"total": 12.5, "by_minute": [...], "minute_ts": ...},
#   "ret_aenergy": {"total": 0.0, ...}
# }

print(f"{state['apower']:.1f} W @ {state['voltage']:.0f} V")
sw.pm1_reset_counters(0)
```

#### Three-phase energy meter (EM — ShellyPro3EM)

```python
state = sw.em_get_status(0)
# Phase A/B/C readings plus totals
print(state["a_voltage"], state["a_current"], state["a_act_power"])
print(state["b_voltage"], state["b_current"], state["b_act_power"])
print(state["c_voltage"], state["c_current"], state["c_act_power"])
print(state["total_act_power"])
```

#### Single-phase energy meter (EM1 — ShellyProEM)

```python
state = sw.em1_get_status(0)
print(state["act_power"], state["voltage"], state["current"])
```

#### Historical energy data (EMData)

```python
# Query by time range
data = sw.emdata_get_data(0, ts=1700000000, end_ts=1700086400)

# Reset counters
sw.emdata_reset_counters(0)

# Delete all stored records
sw.emdata_delete_all(0)
```

---

### System Component

```python
# Status
sys = sw.sys_get_status()
print(sys["uptime"])          # Seconds since boot
print(sys["ram_free"])        # Free heap bytes
print(sys["unixtime"])        # Current Unix timestamp
print(sys["cfg_rev"])         # Config revision counter
print(sys["available_updates"])  # {"stable": {...}, "beta": {...}} if any

# Configuration
cfg = sw.sys_get_config()
print(cfg["device"]["name"])
print(cfg["location"]["tz"])

# Update configuration
sw.sys_set_config({
    "device": {
        "name": "Office Hub",
        "eco_mode": True,       # reduce performance to save power
        "discoverable": True,
    },
    "location": {
        "tz": "Europe/London",
        "lat": 51.5074,
        "lon": -0.1278,
    },
    "sntp": {
        "server": "pool.ntp.org",
    },
})

# Set the clock manually
import time
sw.sys_set_time(int(time.time()))
```

---

### WiFi Component

```python
# Status
wifi = sw.wifi_get_status()
print(wifi["sta_ip"])   # Assigned IP address
print(wifi["status"])   # "connected" | "disconnected" | "connecting" | ...
print(wifi["ssid"])
print(wifi["rssi"])

# Scan for networks
networks = sw.wifi_scan()
for net in networks["results"]:
    print(f"{net['ssid']:30s} {net['rssi']} dBm  ch{net['channel']}")

# Configuration
cfg = sw.wifi_get_config()

sw.wifi_set_config({
    "sta": {
        "ssid": "MyHomeNetwork",
        "pass": "wifipassword",
        "enable": True,
        "ipv4mode": "dhcp",    # "dhcp" or "static"
    },
    "sta1": {
        "ssid": "BackupNetwork",
        "pass": "backuppass",
        "enable": True,
    },
    "ap": {
        "enable": False,
    },
    "roam": {
        "rssi_thr": -80,   # dBm threshold to trigger roaming
        "interval": 60,    # seconds between roaming checks
    },
})

# List AP clients
clients = sw.wifi_list_ap_clients()
for c in clients["ap_clients"]:
    print(c["mac"], c["ip"])
```

---

### Cloud, MQTT & WebSocket

```python
# Cloud
status = sw.cloud_get_status()
print(status["connected"])

sw.cloud_set_config(enable=True)
sw.cloud_set_config(enable=False)

# MQTT
status = sw.mqtt_get_status()
print(status["connected"])

sw.mqtt_set_config({
    "enable": True,
    "server": "192.168.1.10:1883",
    "client_id": "my-shelly",
    "user": "mqttuser",
    "pass": "mqttpass",
    "topic_prefix": "home/shelly",    # custom prefix (default = device ID)
    "rpc_ntf": True,                  # publish RPC notifications
    "status_ntf": False,              # publish full status on change
    "enable_control": True,           # accept commands via MQTT
})

# Outbound WebSocket (device connects to a WebSocket server)
sw.ws_set_config(
    enable=True,
    server="ws://192.168.1.10:8080/shelly",   # or wss:// for TLS
)
status = sw.ws_get_status()
print(status["connected"])
```

---

### BLE Component

```python
# Enable BLE radio
sw.ble_set_config(enable=True)
sw.ble_set_config(enable=True, rpc_enable=True)  # also enable BLE RPC

# Disable BLE
sw.ble_set_config(enable=False)

status = sw.ble_get_status()
cfg = sw.ble_get_config()
```

---

### Schedule Service

The device can execute RPC calls on a cron schedule (up to 20 jobs).

```python
# List all scheduled jobs
jobs = sw.schedule_list()
for job in jobs:
    print(job["id"], job["timespec"], job["enable"])

# Create a job — turn switch OFF every weeknight at 23:00
job = sw.schedule_create(
    timespec="0 0 23 * * MON,TUE,WED,THU,FRI",
    calls=[{"method": "Switch.Set", "params": {"id": 0, "on": False}}],
    enable=True,
)
print(f"Created job ID: {job['id']}")

# Multiple calls in one job
sw.schedule_create(
    timespec="0 0 7 * * MON,TUE,WED,THU,FRI",   # every weekday at 07:00
    calls=[
        {"method": "Switch.Set",  "params": {"id": 0, "on": True}},
        {"method": "Switch.Set",  "params": {"id": 1, "on": True}},
        {"method": "Light.Set",   "params": {"id": 0, "on": True, "brightness": 80}},
    ],
)

# Update a job (enable/disable, change time, change calls)
sw.schedule_update(job["id"], enable=False)
sw.schedule_update(job["id"], timespec="0 30 22 * * *")  # every day at 22:30

# Delete
sw.schedule_delete(job["id"])
sw.schedule_delete_all()
```

**Cron format:** `"<sec> <min> <hour> <dom> <month> <dow>"`

| Field | Values |
|---|---|
| seconds | 0–59 |
| minutes | 0–59 |
| hours | 0–23 |
| day-of-month | 1–31 or `*` |
| month | 1–12 or `*` |
| day-of-week | `SUN`, `MON`, `TUE`, `WED`, `THU`, `FRI`, `SAT` or `*` |

Examples:
- `"0 0 6 * * *"` — every day at 06:00:00
- `"0 30 20 * * SUN"` — every Sunday at 20:30:00
- `"0 0 8 1 * *"` — first day of every month at 08:00:00
- `"0 */15 * * * *"` — every 15 minutes

---

### Webhook Service

Webhooks call HTTP URLs when device events occur (up to 20 webhooks).

```python
# List all configured webhooks
hooks = sw.webhook_list()
for h in hooks:
    print(h["id"], h["event"], h["enable"], h["urls"])

# Discover all events that can trigger a webhook
supported = sw.webhook_list_supported()
# Returns event names grouped by component

# Create a webhook — call a URL when switch 0 turns ON
hook = sw.webhook_create(
    event="switch.on",
    cid=0,                              # component instance id
    urls=["http://192.168.1.10/on"],
    enable=True,
    name="Light on notification",
)

# Create with multiple URLs
sw.webhook_create(
    event="switch.off",
    cid=0,
    urls=[
        "http://192.168.1.10/off",
        "http://192.168.1.20/log?event=off",
    ],
)

# URL token interpolation — embed live sensor values in the URL
sw.webhook_create(
    event="temperature.change",
    cid=0,
    urls=['http://192.168.1.10/temp?value=${status["temperature:0"].tC}'],
)

# Conditional webhook — only fire if power > 100 W
sw.webhook_create(
    event="switch.active_power_change",
    cid=0,
    urls=["http://192.168.1.10/highpower"],
    condition='status["switch:0"].apower > 100',
)

# Fire at most once every 5 minutes
sw.webhook_create(
    event="switch.on",
    cid=0,
    urls=["http://192.168.1.10/on"],
    repeat_period=300,
)

# Active only during certain hours
sw.webhook_create(
    event="input.button_push",
    cid=0,
    urls=["http://192.168.1.10/doorbell"],
    active_between=["08:00", "22:00"],
)

# Update / disable / delete
sw.webhook_update(hook["id"], enable=False)
sw.webhook_delete(hook["id"])
sw.webhook_delete_all()
```

**Common event names:**

| Component | Events |
|---|---|
| switch | `switch.on`, `switch.off`, `switch.active_power_change` |
| cover | `cover.open`, `cover.closed`, `cover.opening`, `cover.closing`, `cover.stopped` |
| light | `light.on`, `light.off` |
| rgbw | `rgbw.on`, `rgbw.off` |
| input (switch) | `input.toggle_on`, `input.toggle_off` |
| input (button) | `input.button_push`, `input.button_longpush`, `input.button_doublepush`, `input.button_triplepush` |
| input (analog) | `input.analog_change`, `input.analog_measurement` |
| temperature | `temperature.change`, `temperature.measurement` |
| humidity | `humidity.change`, `humidity.measurement` |
| smoke | `smoke.alarm`, `smoke.alarm_off` |

---

### Key-Value Store (KVS)

The device has an embedded key-value store (up to 50 keys, max 42-char keys, max 253-char values).  Useful for storing small amounts of persistent state accessible from Shelly Scripts or external systems.

```python
# Store a value
result = sw.kvs_set("my_key", "hello world")
print(result["etag"])   # string hash of the value (for optimistic updates)

# Store any JSON-serialisable value
sw.kvs_set("counter", 42)
sw.kvs_set("config", {"threshold": 25.0, "unit": "C"})

# Retrieve
item = sw.kvs_get("my_key")
print(item["value"])
print(item["etag"])

# Atomic update (only succeeds if etag matches — prevents races)
sw.kvs_set("counter", 43, etag=item["etag"])

# List all keys matching a pattern
keys = sw.kvs_list(match="my_*")
print(keys["keys"])   # {"my_key": {"etag": "..."}, ...}

# Get multiple values at once
items = sw.kvs_get_many(match="config_*")
for key, data in items["items"].items():
    print(key, data["value"])

# Delete
sw.kvs_delete("my_key")
```

---

### Script Component

Gen2+ devices run a modified Espruino JavaScript interpreter.  Up to 3 scripts can run simultaneously.

```python
# List all scripts
scripts = sw.script_list()
for s in scripts:
    print(s["id"], s["name"], s["running"])

# Create a new script slot
new = sw.script_create(name="AutoOff")
script_id = new["id"]

# Upload JavaScript code
code = """
let handle = Timer.set(5000, false, function() {
    Shelly.call("Switch.Set", {id: 0, on: false}, null, null);
});
"""
sw.script_put_code(script_id, code)

# Append to existing code
sw.script_put_code(script_id, "\n// extra line", append=True)

# Download code
chunk = sw.script_get_code(script_id)
print(chunk["data"])    # source code
print(chunk["left"])    # remaining bytes not returned in this chunk

# Configure: enable auto-start on boot
sw.script_set_config(script_id, {"name": "AutoOff", "enable": True})

# Start / stop
sw.script_start(script_id)
sw.script_stop(script_id)

# Runtime status
status = sw.script_get_status(script_id)
print(status["running"])
print(status["mem_used"])
print(status["errors"])

# Evaluate a JS expression in a running script's context
result = sw.script_eval(script_id, "Shelly.getDeviceInfo().id")
print(result["result"])

# Delete
sw.script_delete(script_id)
```

---

### HTTP Outbound Calls

Instruct the device to make HTTP calls to external services.

```python
# GET request from the device
response = sw.http_get("http://192.168.1.10/api/temp")
print(response["code"])     # HTTP status code
print(response["body"])     # Response body string

# POST request
response = sw.http_post(
    url="http://192.168.1.10/api/log",
    body="event=switch_on&device=living_room",
    content_type="application/x-www-form-urlencoded",
)

# POST JSON
import json
response = sw.http_post(
    url="http://192.168.1.10/api/event",
    body=json.dumps({"event": "on", "source": "schedule"}),
    content_type="application/json",
)
```

---

### Matter Protocol

Applies to Gen4 devices primarily; some Gen3 devices also support Matter.

```python
# Check status
status = sw.matter_get_status()
print(status["num_fabrics"])     # Number of paired controllers
print(status["commissionable"])  # True if accepting new pairings

# Enable Matter
sw.matter_set_config(enable=True)

# Get pairing codes
codes = sw.matter_get_setup_code()
print(codes["qr_code"])       # QR code string for scanning
print(codes["manual_code"])   # 11-digit pairing code
```

---

### Firmware Management (Gen2)

```python
# Check for available updates
updates = sw.check_for_update()
# {
#   "stable": {"version": "1.3.0", "build_id": "20240101-..."},
#   "beta":   {"version": "1.4.0-beta", "build_id": "20240110-..."}
# }

if updates.get("stable"):
    print(f"Stable update available: {updates['stable']['version']}")

# Install stable update
sw.update_firmware()
sw.update_firmware(stage="stable")

# Install beta
sw.update_firmware(stage="beta")

# Install from a custom URL
sw.update_firmware(url="http://192.168.1.10/fw/shelly_custom.zip")
```

---

## Using as a Context Manager

Both classes implement the context manager protocol, ensuring the HTTP session is properly closed.

```python
with ShellyGen1("192.168.1.100", password="secret") as sw:
    print(sw.get_status())
    sw.relay_on(0)
# Session is closed automatically here

with ShellyGen2("192.168.1.101", password="secret") as sw:
    info = sw.get_device_info()
    sw.switch_set(0, on=True)
```

You can also close the session manually:

```python
sw = ShellyGen2("192.168.1.101", password="secret")
# ... use sw ...
sw.close()
```

---

## Device-Type Reference

### Which class to use?

| Device | Generation | Class |
|---|---|---|
| Shelly1, Shelly1PM, Shelly1L | 1 | `ShellyGen1` |
| Shelly2, Shelly2.5 | 1 | `ShellyGen1` |
| Shelly4Pro | 1 | `ShellyGen1` |
| ShellyPlug, ShellyPlugS (1st gen) | 1 | `ShellyGen1` |
| Shelly i3, ShellyButton1 | 1 | `ShellyGen1` |
| ShellyBulb, ShellyDimmer1/2, ShellyRGBW2 | 1 | `ShellyGen1` |
| ShellyEM, Shelly3EM | 1 | `ShellyGen1` |
| ShellyH&T, ShellySmoke, ShellyFlood | 1 | `ShellyGen1` |
| ShellyDoor/Window, ShellyMotion, ShellyTRV | 1 | `ShellyGen1` |
| ShellyGas, ShellySense, ShellyUni | 1 | `ShellyGen1` |
| ShellyPlus1, ShellyPlus1PM | 2 | `ShellyGen2` |
| ShellyPlus2PM (relay or cover mode) | 2 | `ShellyGen2` |
| ShellyPlusPlugS (2nd gen) | 2 | `ShellyGen2` |
| ShellyPlusDimmerUS | 2 | `ShellyGen2` |
| ShellyPro4PM | 2 | `ShellyGen2` |
| ShellyPro3EM, ShellyProEM | 2 | `ShellyGen2` |
| ShellyPlus H&T, ShellyPlusSmoke | 2 | `ShellyGen2` |
| All Gen3 devices (ShellyPlus…G3) | 3 | `ShellyGen2` |
| All Gen4 devices | 4 | `ShellyGen2` |

### How to detect device type programmatically

```python
# Gen1: use get_info()["type"]
device = ShellyGen1("192.168.1.100")
info = device.get_info()
model = info["type"]          # e.g. "SHSW-25" = Shelly2.5
mac   = info["mac"]

# Gen2: use get_device_info()
device = ShellyGen2("192.168.1.101")
info = device.get_device_info()
model = info["model"]         # e.g. "SPSW-004PE16EU" = ShellyPro4PM
gen   = info["gen"]           # 2, 3, or 4
app   = info["app"]           # friendly name, e.g. "FourPro"

# After discovery, use isinstance to branch
from shelly import discover_devices, ShellyGen1, ShellyGen2

for device in discover_devices(timeout=10):
    if isinstance(device, ShellyGen1):
        info = device.get_info()
        if info["type"] == "SHSW-25":
            # Shelly2.5: check roller vs relay mode
            settings = device.get_settings()
            if settings.get("mode") == "roller":
                device.roller_to_position(0, pos=50)
            else:
                device.relay_on(0)
    elif isinstance(device, ShellyGen2):
        info = device.get_device_info()
        status = device.get_status()
        if "cover:0" in status:
            device.cover_goto_position(0, pos=50)
        elif "switch:0" in status:
            device.switch_set(0, on=True)
```
