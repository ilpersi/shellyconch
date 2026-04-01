"""
SHA-256 Digest Authentication for Shelly Gen2+ devices.

Shelly Gen2+ implements a subset of RFC 7616.  Standard HTTP Digest Auth
(using the actual request method and URI path for HA2) is accepted by the
device over the HTTP transport.
"""

import hashlib
import os
import re
from urllib.parse import urlparse

from requests.auth import AuthBase


class ShellyDigestAuth(AuthBase):
    """
    Implements SHA-256 HTTP Digest Authentication compatible with Gen2+
    Shelly devices.

    The first unauthenticated request will receive a 401 challenge.  The
    handler extracts the realm and nonce, computes the SHA-256 response and
    transparently retries the request with a proper ``Authorization`` header.
    Subsequent requests on the same session reuse the cached realm/nonce
    (with an incrementing nonce-count) so only one extra round-trip is needed.
    """

    def __init__(self, password: str):
        self._password = password
        self._username = "admin"
        self._realm: str | None = None
        self._nonce: str | None = None
        self._nc = 0

    # ------------------------------------------------------------------
    # requests.auth.AuthBase interface
    # ------------------------------------------------------------------

    def __call__(self, r):
        if self._realm and self._nonce:
            self._nc += 1
            r.headers["Authorization"] = self._build_header(r.method, r.url, self._realm, self._nonce, self._nc)
        r.register_hook("response", self._handle_401)
        return r

    def _handle_401(self, r, **kwargs):
        if r.status_code != 401:
            return r

        www_auth = r.headers.get("WWW-Authenticate", "")
        realm = _parse_digest_param(www_auth, "realm")
        nonce = _parse_digest_param(www_auth, "nonce")
        if not realm or not nonce:
            return r

        self._realm = realm
        self._nonce = nonce
        self._nc = 1

        # Consume and release the failed response so the connection
        # can be reused for the retry.
        r.content
        r.raw.release_conn()

        prep = r.request.copy()
        prep.headers["Authorization"] = self._build_header(prep.method, prep.url, realm, nonce, self._nc)

        _r = r.connection.send(prep, **kwargs)
        _r.history.append(r)
        _r.request = prep
        return _r

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_header(self, method: str, url: str, realm: str, nonce: str, nc: int) -> str:
        uri = urlparse(url).path or "/"
        nc_str = f"{nc:08x}"
        cnonce = hashlib.sha256(os.urandom(8)).hexdigest()[:16]

        ha1 = _sha256(f"{self._username}:{realm}:{self._password}")
        ha2 = _sha256(f"{method}:{uri}")
        response = _sha256(f"{ha1}:{nonce}:{nc_str}:{cnonce}:auth:{ha2}")

        return (f'Digest username="{self._username}", realm="{realm}", '
                f'nonce="{nonce}", uri="{uri}", '
                f'nc={nc_str}, cnonce="{cnonce}", '
                f'response="{response}", algorithm=SHA-256, qop=auth')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse_digest_param(header: str, param: str) -> str | None:
    m = re.search(rf'{param}="([^"]*)"', header, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(rf'{param}=([^,\s]+)', header, re.IGNORECASE)
    return m.group(1) if m else None
