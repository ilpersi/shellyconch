"""Shared fixtures and helpers for the shelly test suite."""

import json
from unittest.mock import MagicMock

import pytest
from shelly.gen1 import ShellyGen1
from shelly.gen2 import ShellyGen2


# ---------------------------------------------------------------------------
# Response factory
# ---------------------------------------------------------------------------

def make_response(json_data=None, status_code=200, text="", content=None):
    """
    Return a mock ``requests.Response`` with the given attributes.

    If *json_data* is provided it is serialised as the response body and
    ``resp.json()`` returns it.  Otherwise ``resp.json()`` raises
    ``ValueError`` and ``resp.content`` is empty.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = status_code < 400
    if json_data is not None:
        body = json.dumps(json_data).encode()
        resp.json.return_value = json_data
        resp.text = json.dumps(json_data)
    else:
        body = text.encode() if text else b""
        resp.json.side_effect = ValueError("No JSON content")
        resp.text = text
    resp.content = content if content is not None else body
    return resp


# ---------------------------------------------------------------------------
# Device fixtures with injected mock session
# ---------------------------------------------------------------------------

@pytest.fixture
def gen1():
    """ShellyGen1 instance with a pre-injected mock session."""
    device = ShellyGen1("192.168.1.100")
    session = MagicMock()
    device._session = session
    return device, session


@pytest.fixture
def gen1_auth():
    """ShellyGen1 instance with password, pre-injected mock session."""
    device = ShellyGen1("192.168.1.100", password="secret")
    session = MagicMock()
    device._session = session
    return device, session


@pytest.fixture
def gen2():
    """ShellyGen2 instance with a pre-injected mock session."""
    device = ShellyGen2("192.168.1.101")
    session = MagicMock()
    device._session = session
    return device, session


@pytest.fixture
def gen2_auth():
    """ShellyGen2 instance with password, pre-injected mock session."""
    device = ShellyGen2("192.168.1.101", password="secret")
    session = MagicMock()
    device._session = session
    return device, session
