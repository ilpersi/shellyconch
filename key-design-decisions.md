  # Key design decisions

  ## ShellyGen1
  - HTTP Basic Auth (disabled by default on devices)
  - Every Gen1 endpoint is covered: relay, roller, light/color/white, meter, emeter, TRV thermostat, gas valve, door/window sensor, external DS1820/DHT22 sensors, ADC (Uni), CoIoT description, OTA, WiFi, actions, schedules, debug logs
  - Both semantic helpers (relay_on(), roller_close(), light_on()) and the generic setters (set_relay(), set_light()) are provided

  ## ShellyGen2

  - JSON-RPC 2.0 via POST to /rpc
  - SHA-256 Digest Auth (RFC 7616 subset) implemented in auth.py as a requests.AuthBase subclass — handles the 401 challenge/retry transparently
  - All components covered: Switch, Cover, Light, RGBW, Input, Temperature, Humidity, Voltmeter, Smoke, DevicePower, PM1, EM (3-phase), EM1, EMData, System, WiFi, Cloud, MQTT, WebSocket, BLE, Schedule, Webhook, KVS, Script, HTTP outbound, Matter

  ## Discovery

  - Browses both _shelly._tcp.local. (Gen2+ specific) and _http._tcp.local. (Gen1+Gen2)
  - Probes /shelly HTTP endpoint to confirm the device and read the gen field
  - Returns correctly typed ShellyGen1 or ShellyGen2 instances
  - discover_devices() for one-shot scans; ShellyDiscovery context manager for long-lived browsing