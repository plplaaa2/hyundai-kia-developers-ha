"""Utility helpers for Hyundai Kia Developers."""

from __future__ import annotations

import hmac
from hashlib import sha256
from urllib.parse import parse_qs, urlparse

from .exceptions import HyundaiKiaAuthenticationError


def vehicle_key(brand: str, car_id: str) -> str:
    """Return a stable, non-reversible vehicle identifier."""
    return sha256(f"{brand}:{car_id}".encode()).hexdigest()


def parse_authorization_redirect(
    pasted_url: str, expected_redirect_uri: str, expected_state: str
) -> str:
    """Validate a pasted OAuth redirect URL and return its one-time code."""
    pasted = urlparse(pasted_url.strip())
    expected = urlparse(expected_redirect_uri)
    if (
        pasted.scheme.lower() != expected.scheme.lower()
        or pasted.netloc.lower() != expected.netloc.lower()
        or pasted.path.rstrip("/") != expected.path.rstrip("/")
    ):
        raise HyundaiKiaAuthenticationError("OAuth redirect URL does not match")

    query = parse_qs(pasted.query, keep_blank_values=True)
    if query.get("error"):
        raise HyundaiKiaAuthenticationError("OAuth provider returned an error")
    state = query.get("state", [""])[0]
    if not state or not hmac.compare_digest(state, expected_state):
        raise HyundaiKiaAuthenticationError("OAuth state did not match")
    code = query.get("code", [""])[0]
    if not code:
        raise HyundaiKiaAuthenticationError("OAuth redirect URL has no code")
    return code
