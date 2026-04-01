"""Custom exceptions for the Shelly library."""


class ShellyError(Exception):
    """Base exception for all Shelly errors."""


class ShellyConnectionError(ShellyError):
    """Failed to connect to the Shelly device."""


class ShellyAuthError(ShellyError):
    """Authentication failed (wrong credentials or auth required)."""


class ShellyTimeoutError(ShellyError):
    """Request to the Shelly device timed out."""


class ShellyHTTPError(ShellyError):
    """Unexpected HTTP error response from the device."""

    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        super().__init__(f"HTTP {status_code}: {message}")


class ShellyRPCError(ShellyError):
    """JSON-RPC error returned by a Gen2+ device."""

    def __init__(self, code: int, message: str):
        self.code = code
        super().__init__(f"RPC error {code}: {message}")


class ShellyDiscoveryError(ShellyError):
    """Error during mDNS device discovery."""


class ShellyCloudError(ShellyError):
    """Error returned by the Shelly Cloud Control API."""

    def __init__(self, error: str, messages: list | None = None):
        self.error = error  # API error string, e.g. "DEVICE_OFFLINE"
        self.messages = messages or []
        detail = "; ".join(self.messages) if self.messages else error
        super().__init__(f"Cloud API error [{error}]: {detail}")
