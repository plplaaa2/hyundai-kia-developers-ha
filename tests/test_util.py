"""Tests for OAuth URL and vehicle identity helpers."""

import pytest

from custom_components.hyundai_kia_developers.exceptions import (
    HyundaiKiaAuthenticationError,
)
from custom_components.hyundai_kia_developers.util import (
    parse_authorization_redirect,
    vehicle_key,
)


def test_parse_authorization_redirect() -> None:
    """A matching redirect returns only its one-time code."""
    assert (
        parse_authorization_redirect(
            "https://example.com/redirect?code=secret-code&state=expected",
            "https://example.com/redirect",
            "expected",
        )
        == "secret-code"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://wrong.example/redirect?code=code&state=expected",
        "https://example.com/redirect?code=code&state=wrong",
        "https://example.com/redirect?state=expected",
        "https://example.com/redirect?error=access_denied&state=expected",
    ],
)
def test_parse_authorization_redirect_rejects_invalid_input(url: str) -> None:
    """Redirect origin, state, errors, and missing codes are validated."""
    with pytest.raises(HyundaiKiaAuthenticationError):
        parse_authorization_redirect(
            url,
            "https://example.com/redirect",
            "expected",
        )


def test_vehicle_key_is_stable_and_brand_scoped() -> None:
    """Vehicle registry identifiers are stable without exposing car IDs."""
    key = vehicle_key("kia", "sensitive-car-id")
    assert key == vehicle_key("kia", "sensitive-car-id")
    assert key != vehicle_key("hyundai", "sensitive-car-id")
    assert "sensitive-car-id" not in key
