"""Sensor platform for Hyundai Kia Developers."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import (
    CONF_CAR_ID,
    EV_VEHICLE_TYPES,
    SUBENTRY_TYPE_VEHICLE,
    EntityKey,
    VehicleType,
)
from .coordinator import HyundaiKiaDataUpdateCoordinator
from .entity import HyundaiKiaVehicleEntity
from .models import HyundaiKiaConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaSensorEntityDescription(SensorEntityDescription):
    """Describe a Hyundai/Kia sensor."""

    entity_key: EntityKey
    applicable_types: frozenset[str] | None = None
    requires_initial_value: bool = False


SENSOR_DESCRIPTIONS: tuple[HyundaiKiaSensorEntityDescription, ...] = (
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.DISTANCE_TO_EMPTY,
        entity_key=EntityKey.DISTANCE_TO_EMPTY,
        translation_key=EntityKey.DISTANCE_TO_EMPTY,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.ODOMETER,
        entity_key=EntityKey.ODOMETER,
        translation_key=EntityKey.ODOMETER,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
    ),
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.COMBINED_DISTANCE_TO_EMPTY,
        entity_key=EntityKey.COMBINED_DISTANCE_TO_EMPTY,
        translation_key=EntityKey.COMBINED_DISTANCE_TO_EMPTY,
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        applicable_types=frozenset({VehicleType.PLUG_IN_HYBRID}),
        requires_initial_value=True,
    ),
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.EV_BATTERY_LEVEL,
        entity_key=EntityKey.EV_BATTERY_LEVEL,
        translation_key=EntityKey.EV_BATTERY_LEVEL,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        applicable_types=EV_VEHICLE_TYPES,
    ),
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.CHARGER_TYPE,
        entity_key=EntityKey.CHARGER_TYPE,
        translation_key=EntityKey.CHARGER_TYPE,
        device_class=SensorDeviceClass.ENUM,
        options=["not_connected", "fast", "normal", "unknown"],
        entity_registry_enabled_default=False,
        applicable_types=EV_VEHICLE_TYPES,
    ),
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.TARGET_STATE_OF_CHARGE,
        entity_key=EntityKey.TARGET_STATE_OF_CHARGE,
        translation_key=EntityKey.TARGET_STATE_OF_CHARGE,
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        applicable_types=EV_VEHICLE_TYPES,
    ),
    HyundaiKiaSensorEntityDescription(
        key=EntityKey.REMAINING_CHARGING_TIME,
        entity_key=EntityKey.REMAINING_CHARGING_TIME,
        translation_key=EntityKey.REMAINING_CHARGING_TIME,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        applicable_types=EV_VEHICLE_TYPES,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyundaiKiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up sensors for every vehicle subentry."""
    coordinator = entry.runtime_data.coordinator
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VEHICLE:
            continue
        car_id = str(subentry.data[CONF_CAR_ID])
        car_type = coordinator.car_type(subentry)
        initial_data = coordinator.data.get(subentry_id, {})
        descriptions = [
            description
            for description in SENSOR_DESCRIPTIONS
            if (
                description.applicable_types is None
                or car_type in description.applicable_types
            )
            and (
                not description.requires_initial_value
                or description.entity_key in initial_data
            )
        ]
        async_add_entities(
            [
                HyundaiKiaSensor(
                    entry,
                    coordinator,
                    subentry_id,
                    car_id,
                    subentry.title,
                    description,
                )
                for description in descriptions
            ],
            config_subentry_id=subentry_id,
        )


class HyundaiKiaSensor(HyundaiKiaVehicleEntity, SensorEntity):
    """Represent one vehicle sensor value."""

    entity_description: HyundaiKiaSensorEntityDescription

    def __init__(
        self,
        entry: HyundaiKiaConfigEntry,
        coordinator: HyundaiKiaDataUpdateCoordinator,
        subentry_id: str,
        car_id: str,
        car_name: str,
        description: HyundaiKiaSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            entry,
            coordinator,
            subentry_id,
            car_id,
            car_name,
            description.entity_key,
        )
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the native sensor value."""
        result = self.entity_result
        return result.value.value if result and result.value else None
