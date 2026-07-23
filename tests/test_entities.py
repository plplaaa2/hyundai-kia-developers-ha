"""Tests for entity applicability and polling groups."""

from custom_components.hyundai_kia_developers.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
)
from custom_components.hyundai_kia_developers.const import (
    ENTITY_ENDPOINT,
    EV_VEHICLE_TYPES,
    EndpointKey,
    EntityKey,
    VehicleType,
)
from custom_components.hyundai_kia_developers.sensor import SENSOR_DESCRIPTIONS


def test_existing_entity_keys_remain_stable() -> None:
    """The two v0.1 unique-ID suffixes do not change."""
    assert EntityKey.DISTANCE_TO_EMPTY.value == "distance_to_empty"
    assert EntityKey.ODOMETER.value == "odometer"


def test_hev_does_not_support_ev_entities() -> None:
    """EV-only descriptions exclude the live Niro HEV vehicle type."""
    ev_sensor_descriptions = [
        description
        for description in SENSOR_DESCRIPTIONS
        if description.applicable_types == EV_VEHICLE_TYPES
    ]
    ev_binary_descriptions = [
        description
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.applicable_types == EV_VEHICLE_TYPES
    ]
    assert ev_sensor_descriptions
    assert ev_binary_descriptions
    assert VehicleType.HYBRID not in EV_VEHICLE_TYPES


def test_new_entity_defaults() -> None:
    """EV essentials are enabled while detailed and warning entities are disabled."""
    sensors = {
        description.entity_key: description for description in SENSOR_DESCRIPTIONS
    }
    binary = {
        description.entity_key: description
        for description in BINARY_SENSOR_DESCRIPTIONS
    }
    assert sensors[EntityKey.EV_BATTERY_LEVEL].entity_registry_enabled_default
    assert binary[EntityKey.CHARGING].entity_registry_enabled_default
    assert not sensors[EntityKey.CHARGER_TYPE].entity_registry_enabled_default
    assert not binary[EntityKey.LOW_FUEL_WARNING].entity_registry_enabled_default


def test_charging_entities_share_one_endpoint() -> None:
    """Enabling several charging entities still requires one HTTP endpoint."""
    keys = {
        EntityKey.CHARGING,
        EntityKey.CHARGING_CABLE_CONNECTED,
        EntityKey.CHARGER_TYPE,
        EntityKey.TARGET_STATE_OF_CHARGE,
        EntityKey.REMAINING_CHARGING_TIME,
    }
    assert {ENTITY_ENDPOINT[key] for key in keys} == {EndpointKey.EV_CHARGING}
