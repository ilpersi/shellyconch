"""Enumerations and constants for the Shelly library."""

from enum import Enum, StrEnum
from typing import Any, NotRequired, ReadOnly, TypedDict


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class RelayState(StrEnum):
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"


class InitialState(StrEnum):
    """Power-on state for relays and switches."""
    OFF = "off"
    ON = "on"
    RESTORE_LAST = "restore_last"  # Gen2 name
    RESTORE = "restore"  # Gen1 name ("restore" = same as restore_last)
    MATCH_INPUT = "match_input"  # Gen2 only
    SWITCH = "switch"  # Gen1 only (mirror physical switch)


# ---------------------------------------------------------------------------
# Gen1-specific
# ---------------------------------------------------------------------------

class Gen1ButtonType(StrEnum):
    TOGGLE = "toggle"
    EDGE = "edge"
    DETACHED = "detached"
    MOMENTARY = "momentary"
    MOMENTARY_ON_RELEASE = "momentary_on_release"


class Gen1RollerDirection(StrEnum):
    OPEN = "open"
    CLOSE = "close"
    STOP = "stop"
    TO_POS = "to_pos"


class Gen1RollerState(StrEnum):
    OPEN = "open"
    CLOSE = "close"
    STOP = "stop"


class Gen1LightMode(StrEnum):
    COLOR = "color"
    WHITE = "white"


class Gen1OTAStatus(StrEnum):
    IDLE = "idle"
    PENDING = "pending"
    UPDATING = "updating"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Model identifier → human-readable name lookups
#
# Source of truth (regenerate via ``python regenerate_models.py`` at the repo
# root):
#
#     https://raw.githubusercontent.com/home-assistant-libs/aioshelly/main/aioshelly/const.py
#
# Shelly's own firmware manifest (https://api.shelly.cloud/files/firmware) is
# keyed by these codes but does not include product names, so we mirror the
# mapping maintained by the Home Assistant ``aioshelly`` library.
# ---------------------------------------------------------------------------

# Gen1 (CoAP / Allterco HTTP) model identifiers returned by the ``type`` field
# of ``/shelly``.
GEN1_MODELS = {
    "SH2LED-1": "Shelly 2LED",
    "SHAIR-1": "Shelly Air",
    "SHBDUO-1": "Shelly DUO",
    "SHBLB-1": "Shelly Bulb",
    "SHBTN-1": "Shelly Button1",
    "SHBTN-2": "Shelly Button1",
    "SHBVIN-1": "Shelly Vintage",
    "SHCB-1": "Shelly Bulb RGBW",
    "SHCL-255": "Shelly Color",
    "SHDIMW-1": "Shelly Dimmer W1",
    "SHDM-1": "Shelly Dimmer",
    "SHDM-2": "Shelly Dimmer 2",
    "SHDW-1": "Shelly Door/Window",
    "SHDW-2": "Shelly Door/Window 2",
    "SHEM": "Shelly EM",
    "SHEM-3": "Shelly 3EM",
    "SHGS-1": "Shelly Gas",
    "SHHT-1": "Shelly H&T",
    "SHIX3-1": "Shelly i3",
    "SHMOS-01": "Shelly Motion",
    "SHMOS-02": "Shelly Motion 2",
    "SHPLG-1": "Shelly Plug",
    "SHPLG-S": "Shelly Plug S",
    "SHPLG-U1": "Shelly Plug US",
    "SHPLG2-1": "Shelly Plug E",
    "SHRGBW2": "Shelly RGBW2",
    "SHRGBWW-01": "Shelly RGBW",
    "SHSEN-1": "Shelly Sense",
    "SHSM-01": "Shelly Smoke",
    "SHSM-02": "Shelly Smoke 2",
    "SHSPOT-1": "Shelly Spot",
    "SHSPOT-2": "Shelly Spot 2",
    "SHSW-1": "Shelly 1",
    "SHSW-21": "Shelly 2",
    "SHSW-25": "Shelly 2.5",
    "SHSW-44": "Shelly 4Pro",
    "SHSW-L": "Shelly 1L",
    "SHSW-PM": "Shelly 1PM",
    "SHTRV-01": "Shelly Valve",
    "SHUNI-1": "Shelly UNI",
    "SHVIN-1": "Shelly Vintage",
    "SHWT-1": "Shelly Flood",
}

# Gen2+ (Plus / Pro / Gen3 / Gen4 — JSON-RPC) model identifiers returned by
# the ``model`` field of ``Shelly.GetDeviceInfo`` (or the ``model`` key of
# ``/shelly``).
GEN2_PLUS_MODELS = {
    "S3BL-C010007AEU": "Shelly Multicolor Bulb Gen3",
    "S3BL-D010009AEU": "Shelly Duo Bulb Gen3",
    "S3DM-0010WW": "Shelly Dimmer 0/1-10V PM Gen3",
    "S3DM-0A101WWL": "Shelly Dimmer Gen3",
    "S3DM-0A1WW": "Shelly DALI Dimmer Gen3",
    "S3EM-002CXCEU": "Shelly EM Gen3",
    "S3EM-003CXCEU63": "Shelly 3EM-63 Gen3",
    "S3GW-1DBT001": "Shelly BLU Gateway Gen3",
    "S3MX-0A": "Shelly X MOD1",
    "S3PL-00112EU": "Shelly Plug S Gen3",
    "S3PL-10112EU": "Shelly AZ Plug",
    "S3PL-20112EU": "Shelly Outdoor Plug S Gen3",
    "S3PL-30110EU": "Shelly Plug M Gen3",
    "S3PL-30116EU": "Shelly Plug PM Gen3",
    "S3PM-001PCEU16": "Shelly PM Mini Gen3",
    "S3SH-0A2P4EU": "Shelly Shutter",
    "S3SN-0024X": "Shelly I4 Gen3",
    "S3SN-0U12A": "Shelly H&T Gen3",
    "S3SN-0U53X": "Shelly Pill",
    "S3SN-1U12A": "Shelly AZ H&T",
    "S3SW-001P16EU": "Shelly 1PM Gen3",
    "S3SW-001P8EU": "Shelly 1PM Mini Gen3",
    "S3SW-001X16EU": "Shelly 1 Gen3",
    "S3SW-001X8EU": "Shelly 1 Mini Gen3",
    "S3SW-002P16EU": "Shelly 2PM Gen3",
    "S3SW-0A1X1EUL": "Shelly 1L Gen3",
    "S3SW-0A2X4EUL": "Shelly 2L Gen3",
    "S4DM-0A101WWL": "Shelly Dimmer Gen4",
    "S4EM-001PXCEU16": "Shelly EM Mini Gen4",
    "S4PB-00CU000002": "Shelly Cury",
    "S4PL-00116US": "Shelly Plug US Gen4",
    "S4PL-00415US": "Shelly Power Strip 4 US Gen4",
    "S4PL-00416EU": "Shelly Power Strip 4 Gen4",
    "S4PL-10416EU": "Shelly Power Strip 4 Gen4",
    "S4SN-0071A": "Shelly Flood Gen4",
    "S4SN-0071Z": "Shelly Flood S Gen4",
    "S4SN-0A24X": "Shelly I4 Gen4",
    "S4SN-0U61X": "Shelly Presence Gen4",
    "S4SW-001P16EU": "Shelly 1PM Gen4",
    "S4SW-001P8EU": "Shelly 1PM Mini Gen4",
    "S4SW-001X16EU": "Shelly 1 Gen4",
    "S4SW-001X8EU": "Shelly 1 Mini Gen4",
    "S4SW-002P16EU": "Shelly 2PM Gen4",
    "S4SW-0A1X1EUL": "Shelly 1L Gen4",
    "S4SW-0A2X4EUL": "Shelly 2L Gen4",
    "SAWD-0A1XX10EU1": "Shelly Wall Display",
    "SAWD-2A1XX10EU1": "Shelly Wall Display X2",
    "SAWD-3A1XE10EU2": "Shelly Wall Display XL",
    "SAWD-5A1XX10EU0": "Shelly Wall Display X2i",
    "SNDC-0D4P10WW": "Shelly Plus RGBW PM",
    "SNDM-00100WW": "Shelly Plus 0-10V Dimmer",
    "SNDM-0013US": "Shelly Plus Wall Dimmer",
    "SNGW-0A11WW010": "Shelly Plus 10V",
    "SNGW-BT01": "Shelly BLU Gateway",
    "SNPL-00110IT": "Shelly Plus Plug IT",
    "SNPL-00112EU": "Shelly Plus Plug S",
    "SNPL-00112UK": "Shelly Plus Plug UK",
    "SNPL-00116US": "Shelly Plus Plug US",
    "SNPL-10112EU": "Shelly Plus Plug S",
    "SNPM-001PCEU16": "Shelly Plus PM Mini",
    "SNSN-0013A": "Shelly Plus H&T",
    "SNSN-0024X": "Shelly Plus I4",
    "SNSN-0031Z": "Shelly Plus Smoke",
    "SNSN-0043X": "Shelly Plus Uni",
    "SNSN-0D24X": "Shelly Plus I4DC",
    "SNSW-001P15UL": "Shelly Plus 1PM UL",
    "SNSW-001P16EU": "Shelly Plus 1PM",
    "SNSW-001P8EU": "Shelly Plus 1PM Mini",
    "SNSW-001X15UL": "Shelly Plus 1 UL",
    "SNSW-001X16EU": "Shelly Plus 1",
    "SNSW-001X8EU": "Shelly Plus 1 Mini",
    "SNSW-002P15UL": "Shelly Plus 2PM UL",
    "SNSW-002P16EU": "Shelly Plus 2PM",
    "SNSW-102P16EU": "Shelly Plus 2PM",
    "SPCC-001PE10EU": "Shelly Pro Dimmer 0/1-10V PM",
    "SPDC-0D5PE16EU": "Shelly Pro RGBWW PM",
    "SPDM-001PE01EU": "Shelly Pro Dimmer 1PM",
    "SPDM-002PE01EU": "Shelly Pro Dimmer 2PM",
    "SPEM-002CEBEU50": "Shelly Pro EM",
    "SPEM-003CEBEU": "Shelly Pro 3EM",
    "SPEM-003CEBEU120": "Shelly Pro 3EM",
    "SPEM-003CEBEU400": "Shelly Pro 3EM-400",
    "SPEM-003CEBEU63": "Shelly Pro 3EM 3CT63",
    "SPSH-002PE16EU": "Shelly Pro Dual Cover PM",
    "SPSW-001PE16EU": "Shelly Pro 1PM",
    "SPSW-001XE16EU": "Shelly Pro 1",
    "SPSW-002PE16EU": "Shelly Pro 2PM",
    "SPSW-002XE16EU": "Shelly Pro 2",
    "SPSW-003XE16EU": "Shelly Pro 3",
    "SPSW-004PE16EU": "Shelly Pro 4PM",
    "SPSW-101PE16EU": "Shelly Pro 1PM",
    "SPSW-101XE16EU": "Shelly Pro 1",
    "SPSW-102XE16EU": "Shelly Pro 2",
    "SPSW-104PE16EU": "Shelly Pro 4PM",
    "SPSW-201PE15UL": "Shelly Pro 1PM UL",
    "SPSW-201PE16EU": "Shelly Pro 1PM",
    "SPSW-201XE15UL": "Shelly Pro 1 UL",
    "SPSW-201XE16EU": "Shelly Pro 1",
    "SPSW-202PE16EU": "Shelly Pro 2PM",
    "SPSW-202XE12UL": "Shelly Pro 2 UL",
    "SPSW-202XE16EU": "Shelly Pro 2",
    "SPSW-204PE16EU": "Shelly Pro 4PM",
}


# ---------------------------------------------------------------------------
# Gen2-specific
# ---------------------------------------------------------------------------

class Gen2SwitchInMode(StrEnum):
    """How the physical input affects the switch output."""
    MOMENTARY = "momentary"
    FOLLOW = "follow"
    FLIP = "flip"
    DETACHED = "detached"
    CYCLE = "cycle"
    ACTIVATE = "activate"


class Gen2CoverState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"
    OPENING = "opening"
    CLOSING = "closing"
    STOPPED = "stopped"
    CALIBRATING = "calibrating"


class Gen2CoverInMode(StrEnum):
    SINGLE = "single"
    DUAL = "dual"
    DETACHED = "detached"


class Gen2InputType(StrEnum):
    SWITCH = "switch"
    BUTTON = "button"
    ANALOG = "analog"
    COUNT = "count"


class Gen2UpdateStage(StrEnum):
    STABLE = "stable"
    BETA = "beta"


class Gen2AddonType(StrEnum):
    """Addon board type attached to the device (``Sys.device.addon_type``)."""
    SENSOR = "sensor"
    PRO_OUTPUT = "prooutput"
    LORA = "LoRa"


# ---------------------------------------------------------------------------
# Gen2 TypedDicts — configuration objects
# ---------------------------------------------------------------------------

class Gen2XValueTransform(TypedDict):
    """
    Expression-based value transformation applied to a derived reading.

    Shared by the ``xpercent`` (analog), ``xcounts``, and ``xfreq`` (counter)
    fields of :class:`Gen2InputConfig`.

    Attributes
    ----------
    expr:
        A JavaScript expression string (up to 100 characters) that transforms
        the raw value ``x`` into the desired unit.  Pass ``None`` or ``""``
        to disable the transformation.
    unit:
        Label for the transformed value (up to 20 characters), e.g. ``"°C"``
        or ``"Hz"``.  Pass ``None`` or ``""`` to clear.
    """
    expr: NotRequired[str | None]
    unit: NotRequired[str | None]


class Gen2SwitchConfig(TypedDict):
    """
    Switch component configuration object (Gen2+).

    Used as the ``config`` argument to
    :meth:`~shelly.ShellyGen2.switch_set_config` and as the shape of the dict
    returned by :meth:`~shelly.ShellyGen2.switch_get_config`.

    Fields without ``NotRequired`` are always present in ``GetConfig``
    responses.  All fields are effectively optional when calling
    ``switch_set_config`` — supply only the keys you want to change.
    ``id`` is present in ``GetConfig`` responses but is passed separately as
    ``switch_id`` to ``switch_set_config`` and should be omitted from the
    ``config`` dict.

    Metering-only fields (``power_limit``, ``voltage_limit``,
    ``undervoltage_limit``, ``current_limit``, ``reverse``) are absent on
    devices without built-in power measurement.

    Attributes
    ----------
    in_mode:
        How the physical input affects the switch output.
        One of ``"momentary"``, ``"follow"``, ``"flip"``, ``"detached"``,
        ``"cycle"`` (multi-switch devices only), ``"activate"`` (multi-switch
        devices only).
    in_locked:
        When ``True``, the physical input cannot change the output state.
    initial_state:
        Output state applied on power-on.
        One of ``"off"``, ``"on"``, ``"restore_last"``, ``"match_input"``.
    id:
        Component instance identifier (present in ``GetConfig`` responses;
        omit when calling ``switch_set_config``).
    name:
        Human-readable display name, or ``None`` to clear.
    auto_on:
        Enable automatic turn-on after ``auto_on_delay`` seconds.
    auto_on_delay:
        Seconds to wait before automatically turning on (requires
        ``auto_on=True``).
    auto_off:
        Enable automatic turn-off after ``auto_off_delay`` seconds.
    auto_off_delay:
        Seconds to wait before automatically turning off (requires
        ``auto_off=True``).
    autorecover_voltage_errors:
        When ``True``, the switch restores its previous state after a
        voltage error clears.
    input_id:
        ID of the associated Input component (``0`` or ``1``; Pro1/Pro1PM
        only).
    power_limit:
        Overpower protection threshold in Watts, or ``None`` to use the
        device default.  Range: ``0`` to the device's maximum rated power.
    voltage_limit:
        Overvoltage protection threshold in Volts, or ``None`` to use the
        device default.  Must be ≥ ``undervoltage_limit``.
    undervoltage_limit:
        Undervoltage protection threshold in Volts (``0`` disables it), or
        ``None`` to use the device default.  Must be ≤ ``voltage_limit``.
    current_limit:
        Overcurrent protection threshold in Amperes, or ``None`` to use the
        device default.  Range: ``0`` to the device's maximum rated current.
    reverse:
        When ``True``, reverses the direction of power and energy measurement.
        Requires a device restart to take effect.
    """
    in_mode: Gen2SwitchInMode
    in_locked: bool
    initial_state: InitialState
    id: NotRequired[int]
    name: NotRequired[str | None]
    auto_on: NotRequired[bool]
    auto_on_delay: NotRequired[float]
    auto_off: NotRequired[bool]
    auto_off_delay: NotRequired[float]
    autorecover_voltage_errors: NotRequired[bool]
    input_id: NotRequired[int]
    power_limit: NotRequired[float | None]
    voltage_limit: NotRequired[float | None]
    undervoltage_limit: NotRequired[float | None]
    current_limit: NotRequired[float | None]
    reverse: NotRequired[bool]


class Gen2InputConfig(TypedDict):
    """
    Input component configuration object (Gen2+).

    Used as the ``config`` argument to
    :meth:`~shelly.ShellyGen2.input_set_config` and as the shape of the dict
    returned by :meth:`~shelly.ShellyGen2.input_get_config`.

    Fields without ``NotRequired`` are always present in ``GetConfig``
    responses.  All fields are effectively optional when calling
    ``input_set_config`` — supply only the keys you want to change.
    ``id`` is present in ``GetConfig`` responses but is passed separately as
    ``input_id`` to ``input_set_config`` and should be omitted from the
    ``config`` dict.

    Type-specific fields:

    - ``switch`` / ``button``: ``invert``, ``factory_reset``
    - ``analog``: ``invert``, ``report_thr``, ``range_map``, ``range``,
      ``xpercent``
    - ``count``: ``count_rep_thr``, ``freq_window``, ``freq_rep_thr``,
      ``xcounts``, ``xfreq``

    Attributes
    ----------
    type:
        Input category: ``"switch"``, ``"button"``, ``"analog"``, or
        ``"count"``.
    enable:
        When ``False``, the input is disabled and all events and status
        fields report ``None``.
    id:
        Component instance identifier (present in ``GetConfig`` responses;
        omit when calling ``input_set_config``).
    name:
        Human-readable display name, or ``None`` to clear.
    invert:
        Invert the logical state of the input (switch/button/analog only).
        A physical toggle is required after changing this field for it to
        take effect.
    factory_reset:
        Allow a long-press factory-reset gesture on this input
        (switch/button only).
    report_thr:
        Minimum percentage-point change in the analog reading required to
        trigger a report.  Device-specific range, typically ``1.0``–``50.0``.
    range_map:
        Two-element list ``[min, max]`` that remaps the raw 0–100 % analog
        reading to a custom range.  ``max`` must be greater than ``min``;
        equal values are allowed for a fixed output.
    range:
        Input voltage range selector (device-specific, e.g. 0–15 VDC or
        0–30 VDC).
    xpercent:
        Optional expression-based transformation applied to the analog
        percentage value.  See :class:`Gen2XValueTransform`.
    count_rep_thr:
        Minimum pulse-count change required to trigger a count report.
        Range: ``1``–``2 147 483 647``.
    freq_window:
        Duration in seconds over which frequency is measured.
        Range: ``1``–``3 600``.
    freq_rep_thr:
        Minimum percentage-point change in frequency required to trigger a
        frequency report.  Range: ``0``–``10 000``.
    xcounts:
        Optional expression-based transformation applied to the pulse count.
        See :class:`Gen2XValueTransform`.
    xfreq:
        Optional expression-based transformation applied to the measured
        frequency.  See :class:`Gen2XValueTransform`.
    """
    type: Gen2InputType
    enable: bool
    id: NotRequired[int]
    name: NotRequired[str | None]
    invert: NotRequired[bool]
    factory_reset: NotRequired[bool]
    # Analog-specific
    report_thr: NotRequired[float]
    range_map: NotRequired[list[float]]   # exactly [min, max]
    range: NotRequired[float]
    xpercent: NotRequired[Gen2XValueTransform]
    # Counter-specific
    count_rep_thr: NotRequired[int]
    freq_window: NotRequired[int]
    freq_rep_thr: NotRequired[float]
    xcounts: NotRequired[Gen2XValueTransform]
    xfreq: NotRequired[Gen2XValueTransform]


class Gen2SysDeviceConfig(TypedDict):
    """
    ``device`` sub-object of :class:`Gen2SysConfig`.

    Attributes
    ----------
    eco_mode:
        Experimental power-saving mode.  Reduces execution speed and
        increases response latency.
    discoverable:
        Controls whether the device appears in network discovery results.
    name:
        Human-readable device display name, or ``None`` to clear.
    mac:
        Base MAC address.  Read-only — the device rejects attempts to set
        this field.  Present in ``GetConfig`` responses only.
    fw_id:
        Firmware build identifier.  Read-only — the device rejects attempts
        to set this field.  Present in ``GetConfig`` responses only.
    profile:
        Active configuration profile name (multi-profile devices only).
    addon_type:
        Addon board attached to the device, or ``None`` when no addon is
        present.  One of ``"sensor"``, ``"prooutput"``, ``"LoRa"``.
    sys_btn_toggle:
        When ``True``, the system button toggles the output instead of
        performing a factory reset (select Pro devices only).
    """
    eco_mode: bool
    discoverable: bool
    name: NotRequired[str | None]
    mac: ReadOnly[NotRequired[str]]
    fw_id: ReadOnly[NotRequired[str]]
    profile: NotRequired[str]
    addon_type: NotRequired[Gen2AddonType | None]
    sys_btn_toggle: NotRequired[bool]


class Gen2SysLocationConfig(TypedDict):
    """
    ``location`` sub-object of :class:`Gen2SysConfig`.

    All fields are optional — the device can operate without location data.

    Attributes
    ----------
    tz:
        IANA timezone identifier (e.g. ``"Europe/Sofia"``), or ``None`` to
        clear.
    lat:
        Latitude in decimal degrees, or ``None`` to clear.
    lon:
        Longitude in decimal degrees, or ``None`` to clear.
    """
    tz: NotRequired[str | None]
    lat: NotRequired[float | None]
    lon: NotRequired[float | None]


class Gen2SysDebugChannelConfig(TypedDict):
    """
    Single-field config for an individual debug log channel.

    Used for both the ``mqtt`` and ``websocket`` fields inside
    :class:`Gen2SysDebugConfig`.

    Attributes
    ----------
    enable:
        When ``True``, debug log entries are streamed over this channel.
    """
    enable: bool


class Gen2SysDebugUdpConfig(TypedDict):
    """
    ``debug.udp`` sub-object of :class:`Gen2SysDebugConfig`.

    Attributes
    ----------
    addr:
        Destination ``host:port`` string for UDP log streaming, or ``None``
        to disable UDP log output.
    """
    addr: NotRequired[str | None]


class Gen2SysDebugConfig(TypedDict):
    """
    ``debug`` sub-object of :class:`Gen2SysConfig`.

    Attributes
    ----------
    mqtt:
        MQTT debug log channel settings.
    websocket:
        WebSocket debug log channel settings.
    udp:
        UDP debug log channel settings.
    """
    mqtt: Gen2SysDebugChannelConfig
    websocket: Gen2SysDebugChannelConfig
    udp: Gen2SysDebugUdpConfig


class Gen2SysRpcUdpConfig(TypedDict):
    """
    ``rpc_udp`` sub-object of :class:`Gen2SysConfig`.

    Attributes
    ----------
    dst_addr:
        Destination ``host:port`` for outbound UDP RPC frames.
    listen_port:
        UDP port on which the device listens for inbound RPC calls, or
        ``None`` to disable.  A device restart is required for changes to
        take effect.
    """
    dst_addr: NotRequired[str]
    listen_port: NotRequired[int | None]


class Gen2SysSntpConfig(TypedDict):
    """
    ``sntp`` sub-object of :class:`Gen2SysConfig`.

    Attributes
    ----------
    server:
        NTP server hostname (e.g. ``"time.google.com"``).
    """
    server: str


class Gen2SysConfig(TypedDict):
    """
    System component configuration object (Gen2+).

    Used as the ``config`` argument to
    :meth:`~shelly.ShellyGen2.sys_set_config` and as the shape of the dict
    returned by :meth:`~shelly.ShellyGen2.sys_get_config`.

    Fields without ``NotRequired`` are always present in ``GetConfig``
    responses.  Supply only the sub-objects you want to change when calling
    ``sys_set_config``; partial nested updates are supported.

    Attributes
    ----------
    device:
        Device identity and behaviour settings.
    location:
        Geographic and timezone information.
    debug:
        Debug log channel configuration.
    ui_data:
        Arbitrary user-defined key/value storage for UI state.  The device
        stores and returns whatever is written here without interpretation.
    rpc_udp:
        UDP RPC channel settings.
    sntp:
        NTP server configuration.
    cfg_rev:
        Configuration revision counter.  Incremented by the device on every
        configuration change.  Read-only — the device rejects attempts to set
        this field.  Present in ``GetConfig`` responses only.
    """
    device: Gen2SysDeviceConfig
    location: Gen2SysLocationConfig
    debug: Gen2SysDebugConfig
    ui_data: dict[str, Any]
    rpc_udp: Gen2SysRpcUdpConfig
    sntp: Gen2SysSntpConfig
    cfg_rev: ReadOnly[NotRequired[int]]


# ---------------------------------------------------------------------------
# Cross-generation normalized shapes
# ---------------------------------------------------------------------------

class WifiStaInfo(TypedDict):
    """
    Normalized WiFi station-mode (client) configuration entry.

    Returned as the value of the ``sta`` and ``sta1`` keys of
    :class:`WifiInfo`.  Generation-specific key names (``enable`` vs.
    ``enabled``, ``ipv4mode`` vs. ``ipv4_method``, ``netmask`` vs. ``mask``,
    ``nameserver`` vs. ``dns``) are flattened into a single schema.

    Attributes
    ----------
    enabled:
        Whether this STA slot is active.
    ssid:
        Configured SSID, or ``None`` if unset.
    ipv4_method:
        IPv4 configuration mode — typically ``"dhcp"`` or ``"static"``.
    ip:
        Static IPv4 address, or ``None`` when in DHCP mode.
    gw:
        Static IPv4 gateway, or ``None`` when in DHCP mode.
    mask:
        Static IPv4 netmask, or ``None`` when in DHCP mode.
    dns:
        Static IPv4 DNS server, or ``None`` when in DHCP mode.
    is_open:
        ``True`` for an unsecured (open) network, ``False`` otherwise, or
        ``None`` when the generation does not report this field (Gen1).
    """
    enabled: bool
    ssid: str | None
    ipv4_method: str
    ip: str | None
    gw: str | None
    mask: str | None
    dns: str | None
    is_open: bool | None


class WifiInfo(TypedDict):
    """
    Normalized WiFi station-mode configuration.

    Shelly devices support a primary station (``sta``) and an optional
    backup (``sta1``).  Returned by
    :meth:`~shelly.ShellyDevice.get_wifi_sta`.

    Attributes
    ----------
    sta:
        Primary station configuration.
    sta1:
        Backup station configuration, or ``None`` when the device has none
        configured.
    """
    sta: WifiStaInfo
    sta1: WifiStaInfo | None
