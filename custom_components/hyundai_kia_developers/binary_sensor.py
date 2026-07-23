"""Binary sensor platform for Hyundai Kia Developers."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CAR_ID,
    EV_VEHICLE_TYPES,
    SUBENTRY_TYPE_VEHICLE,
    EntityKey,
)
from .coordinator import HyundaiKiaDataUpdateCoordinator
from .entity import HyundaiKiaVehicleEntity
from .models import HyundaiKiaConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class HyundaiKiaBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Hyundai/Kia binary sensor."""

    entity_key: EntityKey
    applicable_types: frozenset[str] | None = None


BINARY_SENSOR_DESCRIPTIONS: tuple[HyundaiKiaBinarySensorEntityDescription, ...] = (
    HyundaiKiaBinarySensorEntityDescription(
        key=EntityKey.CHARGING,
        entity_key=EntityKey.CHARGING,
        translation_key=EntityKey.CHARGING,
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        applicable_types=EV_VEHICLE_TYPES,
    ),
    HyundaiKiaBinarySensorEntityDescription(
        key=EntityKey.CHARGING_CABLE_CONNECTED,
        entity_key=EntityKey.CHARGING_CABLE_CONNECTED,
        translation_key=EntityKey.CHARGING_CABLE_CONNECTED,
        device_class=BinarySensorDeviceClass.PLUG,
        entity_registry_enabled_default=False,
        applicable_types=EV_VEHICLE_TYPES,
    ),
    *(
        HyundaiKiaBinarySensorEntityDescription(
            key=key,
            entity_key=key,
            translation_key=key,
            device_class=BinarySensorDeviceClass.PROBLEM,
            entity_registry_enabled_default=False,
        )
        for key in (
            EntityKey.LOW_FUEL_WARNING,
            EntityKey.TIRE_PRESSURE_WARNING,
            EntityKey.LAMP_WIRE_WARNING,
            EntityKey.SMART_KEY_BATTERY_WARNING,
            EntityKey.WASHER_FLUID_WARNING,
            EntityKey.BRAKE_FLUID_WARNING,
            EntityKey.ENGINE_OIL_WARNING,
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyundaiKiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up binary sensors for every vehicle subentry."""
    coordinator = entry.runtime_data.coordinator
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VEHICLE:
            continue
        car_id = str(subentry.data[CONF_CAR_ID])
        car_type = coordinator.car_type(subentry)
        descriptions = [
            description
            for description in BINARY_SENSOR_DESCRIPTIONS
            if description.applicable_types is None
            or car_type in description.applicable_types
        ]
        async_add_entities(
            [
                HyundaiKiaBinarySensor(
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


class HyundaiKiaBinarySensor(HyundaiKiaVehicleEntity, BinarySensorEntity):
    """Represent one vehicle boolean value."""

    entity_description: HyundaiKiaBinarySensorEntityDescription

    def __init__(
        self,
        entry: HyundaiKiaConfigEntry,
        coordinator: HyundaiKiaDataUpdateCoordinator,
        subentry_id: str,
        car_id: str,
        car_name: str,
        description: HyundaiKiaBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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
    def is_on(self) -> bool | None:
        """Return the native boolean value."""
        result = self.entity_result
        if not result or not result.value:
            return None
        return bool(result.value.value)
