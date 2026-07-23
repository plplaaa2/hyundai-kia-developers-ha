"""Tests for revised onboarding helpers and compatibility."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET

from custom_components.hyundai_kia_developers.config_flow import (
    HyundaiKiaConfigFlow,
    VehicleSubentryFlowHandler,
    _credentials_schema,
    _next_account_title,
    _vehicle_label,
)
from custom_components.hyundai_kia_developers.const import (
    CONF_BRAND,
    CONF_REDIRECT_URI,
    Brand,
)
from custom_components.hyundai_kia_developers.models import VehicleProfile


def test_vehicle_label_and_suggested_name() -> None:
    """Discovery suggests the nickname but still disambiguates the selector."""
    profile = VehicleProfile("sensitive-car-1234", "My Niro", "HEV", "DE", "Niro")
    assert profile.suggested_name == "My Niro"
    label = _vehicle_label(profile)
    assert label == "My Niro — Niro (••••1234)"
    assert "sensitive-car" not in label


def test_suggested_name_fallbacks() -> None:
    """Sales model and model code are deterministic naming fallbacks."""
    assert VehicleProfile("1", "", "EV", "CV", "EV6").suggested_name == "EV6"
    assert VehicleProfile("1", "", "EV", "CV", "").suggested_name == "CV"


def test_account_titles_are_generated_per_brand() -> None:
    """Same-brand entries receive a numeric suffix regardless of custom titles."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = [
        SimpleNamespace(data={CONF_BRAND: Brand.KIA}),
        SimpleNamespace(data={CONF_BRAND: Brand.HYUNDAI}),
    ]
    assert _next_account_title(hass, Brand.KIA) == "Kia 2"
    assert _next_account_title(hass, Brand.HYUNDAI) == "Hyundai 2"


def test_reconfigure_schema_cannot_change_brand() -> None:
    """Reconfiguration exposes credentials but keeps the existing brand immutable."""
    schema = _credentials_schema(
        {
            CONF_BRAND: Brand.KIA,
            CONF_CLIENT_ID: "client",
            CONF_CLIENT_SECRET: "secret",
            CONF_REDIRECT_URI: "https://example.com/redirect",
        },
        include_brand=False,
        require_secret=False,
    )
    keys = {marker.schema for marker in schema.schema}
    assert CONF_BRAND not in keys
    assert keys == {CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_REDIRECT_URI}


def test_recovery_menu_steps_have_handlers() -> None:
    """Home Assistant can route both discovery recovery menus."""
    for handler in (HyundaiKiaConfigFlow, VehicleSubentryFlowHandler):
        assert hasattr(handler, "async_step_vehicle_discovery_failed")
        assert hasattr(handler, "async_step_no_vehicles")
        assert hasattr(handler, "async_step_retry")
        assert hasattr(handler, "async_step_manual")
