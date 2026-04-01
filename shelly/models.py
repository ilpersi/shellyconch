"""Enumerations and constants for the Shelly library."""

from enum import Enum


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class RelayState(str, Enum):
    ON = "on"
    OFF = "off"
    TOGGLE = "toggle"


class InitialState(str, Enum):
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

class Gen1ButtonType(str, Enum):
    TOGGLE = "toggle"
    EDGE = "edge"
    DETACHED = "detached"
    MOMENTARY = "momentary"
    MOMENTARY_ON_RELEASE = "momentary_on_release"


class Gen1RollerDirection(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    STOP = "stop"
    TO_POS = "to_pos"


class Gen1RollerState(str, Enum):
    OPEN = "open"
    CLOSE = "close"
    STOP = "stop"


class Gen1LightMode(str, Enum):
    COLOR = "color"
    WHITE = "white"


class Gen1OTAStatus(str, Enum):
    IDLE = "idle"
    PENDING = "pending"
    UPDATING = "updating"
    UNKNOWN = "unknown"


# Known Gen1 model identifiers returned by /shelly
GEN1_MODELS = {"SHSW-1": "Shelly1", "SHSW-PM": "Shelly1PM", "SHSW-L": "Shelly1L", "SHSW-21": "Shelly2",
    "SHSW-25": "Shelly2.5", "SHSW-44": "Shelly4Pro", "SHPLG-1": "ShellyPlug", "SHPLG-S": "ShellyPlugS",
    "SHPLG-U1": "ShellyPlugUS", "SHIX3-1": "Shellyi3", "SHBTN-1": "ShellyButton1", "SHBLB-1": "ShellyBulb",
    "SHVIN-1": "ShellyVintage", "SHDM-1": "ShellyDimmer1", "SHDM-2": "ShellyDimmer2", "SHRGBW2": "ShellyRGBW2",
    "SHEM": "ShellyEM", "SHEM-3": "Shelly3EM", "SHSM-01": "ShellySmoke", "SHHT-1": "ShellyHT", "SHFW-1": "ShellyFlood",
    "SHDW-1": "ShellyDoorWindow1", "SHDW-2": "ShellyDoorWindow2", "SHMOS-01": "ShellyMotion",
    "SHMOS-02": "ShellyMotion2", "SHTRV-01": "ShellyTRV", "SHGS-1": "ShellyGas", "SHSNS-1": "ShellySense",
    "SHUNI-1": "ShellyUni", }


# ---------------------------------------------------------------------------
# Gen2-specific
# ---------------------------------------------------------------------------

class Gen2SwitchInMode(str, Enum):
    """How the physical input affects the switch output."""
    MOMENTARY = "momentary"
    FOLLOW = "follow"
    FLIP = "flip"
    DETACHED = "detached"
    CYCLE = "cycle"
    ACTIVATE = "activate"


class Gen2CoverState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    OPENING = "opening"
    CLOSING = "closing"
    STOPPED = "stopped"
    CALIBRATING = "calibrating"


class Gen2CoverInMode(str, Enum):
    SINGLE = "single"
    DUAL = "dual"
    DETACHED = "detached"


class Gen2InputType(str, Enum):
    SWITCH = "switch"
    BUTTON = "button"
    ANALOG = "analog"
    COUNT = "count"


class Gen2UpdateStage(str, Enum):
    STABLE = "stable"
    BETA = "beta"
