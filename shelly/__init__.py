"""
shelly — Python library for discovering and controlling Shelly devices.

Supports all first-generation (Gen1) and second-generation-and-newer
(Gen2+) Shelly devices over HTTP.

Quick-start
-----------
Discover devices::

    from shelly import discover_devices

    devices = discover_devices(timeout=10)
    for device in devices:
        print(device, device.get_info())

Use Gen1 directly::

    from shelly import ShellyGen1

    sw = ShellyGen1("192.168.1.100")
    print(sw.get_status())
    sw.relay_on(0)
    sw.relay_off(0, timer=30)

Use Gen2+ directly::

    from shelly import ShellyGen2

    sw = ShellyGen2("192.168.1.101", password="mypassword")
    print(sw.get_device_info())
    sw.switch_set(0, on=True)
    sw.cover_goto_position(0, pos=50)

References
----------
- Gen1 API: https://shelly-api-docs.shelly.cloud/gen1/
- Gen2+ API: https://shelly-api-docs.shelly.cloud/gen2/
"""

from .cloud import ShellyCloud
from .device import ShellyDevice
from .discovery import ShellyDiscovery, discover_devices
from .exceptions import (
    ShellyAuthError,
    ShellyCloudError,
    ShellyConnectionError,
    ShellyDiscoveryError,
    ShellyError,
    ShellyHTTPError,
    ShellyRPCError,
    ShellyTimeoutError,
)
from .gen1 import ShellyGen1
from .gen2 import ShellyGen2
from .models import (
    Gen1ButtonType,
    Gen1LightMode,
    Gen1RollerDirection,
    Gen2CoverInMode,
    Gen2CoverState,
    Gen2InputType,
    Gen2SwitchInMode,
    Gen2UpdateStage,
    InitialState,
    RelayState,
)

__all__ = [
    # Main classes
    "ShellyCloud",
    "ShellyDevice",
    "ShellyGen1",
    "ShellyGen2",
    # Discovery
    "discover_devices",
    "ShellyDiscovery",
    # Exceptions
    "ShellyError",
    "ShellyConnectionError",
    "ShellyAuthError",
    "ShellyTimeoutError",
    "ShellyHTTPError",
    "ShellyRPCError",
    "ShellyCloudError",
    "ShellyDiscoveryError",
    # Enums / constants
    "RelayState",
    "InitialState",
    "Gen1ButtonType",
    "Gen1LightMode",
    "Gen1RollerDirection",
    "Gen2SwitchInMode",
    "Gen2CoverState",
    "Gen2CoverInMode",
    "Gen2InputType",
    "Gen2UpdateStage",
]

__version__ = "0.1.0"
