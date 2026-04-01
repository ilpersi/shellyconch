"""Base class shared by ShellyGen1 and ShellyGen2."""

from __future__ import annotations

from typing import Any

import requests

from .exceptions import (ShellyAuthError, ShellyConnectionError, ShellyHTTPError, ShellyTimeoutError, )


class BaseShelly:
    """
    Common HTTP session management and error-handling for all Shelly devices.

    Parameters
    ----------
    host:
        Hostname or IP address of the device (e.g. ``"192.168.1.100"`` or
        ``"shellypro4pm-aabbcc.local"``).
    port:
        HTTP port (default ``80``).
    timeout:
        Socket timeout in seconds for every request (default ``10``).
    """

    def __init__(self, host: str, port: int = 80, timeout: float = 10.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._session: requests.Session | None = None

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def session(self) -> requests.Session:
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def close(self) -> None:
        """Close the underlying HTTP session and release all connections."""
        if self._session is not None:
            self._session.close()
            self._session = None

    def __enter__(self) -> "BaseShelly":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(host={self.host!r})"

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict | None = None) -> Any:
        """Issue a GET request and return the parsed JSON body."""
        url = f"{self.base_url}{path}"
        return self._request("GET", url, params=params)

    def _post(self, path: str, json: Any = None, params: dict | None = None) -> Any:
        """Issue a POST request with an optional JSON body."""
        url = f"{self.base_url}{path}"
        return self._request("POST", url, json=json, params=params)

    def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        kwargs.setdefault("timeout", self.timeout)
        try:
            resp = self.session.request(method, url, **kwargs)
        except requests.exceptions.ConnectionError as exc:
            raise ShellyConnectionError(f"Cannot connect to {self.host}:{self.port}: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ShellyTimeoutError(f"Request to {url} timed out after {self.timeout}s") from exc

        if resp.status_code == 401:
            raise ShellyAuthError("Authentication required or credentials incorrect. "
                                  "Supply a password when creating the device instance.")
        if not resp.ok:
            raise ShellyHTTPError(resp.status_code, resp.text)

        if resp.content:
            return resp.json()
        return {}
