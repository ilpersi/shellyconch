"""Tests for shelly/models.py"""

from shelly.models import (GEN1_MODELS, Gen1ButtonType, Gen1LightMode, Gen1OTAStatus, Gen1RollerDirection,
                           Gen1RollerState, Gen2CoverInMode, Gen2CoverState, Gen2InputType, Gen2SwitchInMode,
                           Gen2UpdateStage, InitialState, RelayState, )


class TestRelayState:
    def test_values(self):
        assert RelayState.ON == "on"
        assert RelayState.OFF == "off"
        assert RelayState.TOGGLE == "toggle"

    def test_is_str(self):
        assert isinstance(RelayState.ON, str)

    def test_usable_in_string_context(self):
        # str, Enum behaves as a str — the underlying value is "on"
        assert RelayState.ON == "on"
        assert RelayState.OFF == "off"


class TestInitialState:
    def test_gen1_values(self):
        assert InitialState.OFF == "off"
        assert InitialState.ON == "on"
        assert InitialState.RESTORE == "restore"
        assert InitialState.SWITCH == "switch"

    def test_gen2_values(self):
        assert InitialState.RESTORE_LAST == "restore_last"
        assert InitialState.MATCH_INPUT == "match_input"


class TestGen1RollerDirection:
    def test_values(self):
        assert Gen1RollerDirection.OPEN == "open"
        assert Gen1RollerDirection.CLOSE == "close"
        assert Gen1RollerDirection.STOP == "stop"
        assert Gen1RollerDirection.TO_POS == "to_pos"


class TestGen1RollerState:
    def test_values(self):
        assert Gen1RollerState.OPEN == "open"
        assert Gen1RollerState.CLOSE == "close"
        assert Gen1RollerState.STOP == "stop"


class TestGen1LightMode:
    def test_values(self):
        assert Gen1LightMode.COLOR == "color"
        assert Gen1LightMode.WHITE == "white"


class TestGen1ButtonType:
    def test_values(self):
        assert Gen1ButtonType.TOGGLE == "toggle"
        assert Gen1ButtonType.EDGE == "edge"
        assert Gen1ButtonType.DETACHED == "detached"
        assert Gen1ButtonType.MOMENTARY == "momentary"
        assert Gen1ButtonType.MOMENTARY_ON_RELEASE == "momentary_on_release"


class TestGen1OTAStatus:
    def test_values(self):
        assert Gen1OTAStatus.IDLE == "idle"
        assert Gen1OTAStatus.PENDING == "pending"
        assert Gen1OTAStatus.UPDATING == "updating"
        assert Gen1OTAStatus.UNKNOWN == "unknown"


class TestGen2SwitchInMode:
    def test_values(self):
        assert Gen2SwitchInMode.MOMENTARY == "momentary"
        assert Gen2SwitchInMode.FOLLOW == "follow"
        assert Gen2SwitchInMode.FLIP == "flip"
        assert Gen2SwitchInMode.DETACHED == "detached"
        assert Gen2SwitchInMode.CYCLE == "cycle"
        assert Gen2SwitchInMode.ACTIVATE == "activate"


class TestGen2CoverState:
    def test_values(self):
        assert Gen2CoverState.OPEN == "open"
        assert Gen2CoverState.CLOSED == "closed"
        assert Gen2CoverState.OPENING == "opening"
        assert Gen2CoverState.CLOSING == "closing"
        assert Gen2CoverState.STOPPED == "stopped"
        assert Gen2CoverState.CALIBRATING == "calibrating"


class TestGen2CoverInMode:
    def test_values(self):
        assert Gen2CoverInMode.SINGLE == "single"
        assert Gen2CoverInMode.DUAL == "dual"
        assert Gen2CoverInMode.DETACHED == "detached"


class TestGen2InputType:
    def test_values(self):
        assert Gen2InputType.SWITCH == "switch"
        assert Gen2InputType.BUTTON == "button"
        assert Gen2InputType.ANALOG == "analog"
        assert Gen2InputType.COUNT == "count"


class TestGen2UpdateStage:
    def test_values(self):
        assert Gen2UpdateStage.STABLE == "stable"
        assert Gen2UpdateStage.BETA == "beta"


class TestGEN1Models:
    def test_known_models_present(self):
        assert "SHSW-1" in GEN1_MODELS
        assert "SHSW-PM" in GEN1_MODELS
        assert "SHSW-25" in GEN1_MODELS
        assert "SHPLG-S" in GEN1_MODELS
        assert "SHEM" in GEN1_MODELS
        assert "SHEM-3" in GEN1_MODELS
        assert "SHTRV-01" in GEN1_MODELS
        assert "SHGS-1" in GEN1_MODELS

    def test_model_names_are_strings(self):
        for key, value in GEN1_MODELS.items():
            assert isinstance(key, str), f"Key {key!r} is not a string"
            assert isinstance(value, str), f"Value {value!r} for {key!r} is not a string"

    def test_specific_values(self):
        assert GEN1_MODELS["SHSW-1"] == "Shelly1"
        assert GEN1_MODELS["SHSW-PM"] == "Shelly1PM"
        assert GEN1_MODELS["SHSW-25"] == "Shelly2.5"
        assert GEN1_MODELS["SHPLG-S"] == "ShellyPlugS"
        assert GEN1_MODELS["SHEM-3"] == "Shelly3EM"
