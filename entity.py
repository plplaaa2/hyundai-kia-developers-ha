"""Base entities for Hyundai Kia Developers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_BRAND, DOMAIN, EntityKey
from .coordinator import HyundaiKiaDataUpdateCoordinator
from .models import EntityResult, HyundaiKiaConfigEntry
from .util import vehicle_key


class HyundaiKiaVehicleEntity(CoordinatorEntity[HyundaiKiaDataUpdateCoordinator]):
    """Base class for a vehicle entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: HyundaiKiaConfigEntry,
        coordinator: HyundaiKiaDataUpdateCoordinator,
        subentry_id: str,
        car_id: str,
        car_name: str,
        key: EntityKey,
    ) -> None:
        """Initialize the vehicle entity."""
        super().__init__(coordinator, context=(subentry_id, key))
        self._subentry_id = subentry_id
        self._entity_key = key
        brand = str(entry.data[CONF_BRAND])
        identifier = vehicle_key(brand, car_id)
        self._attr_unique_id = f"{identifier}_{key.value}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            manufacturer=brand.title(),
            name=car_name,
        )

    @property
    def entity_result(self) -> EntityResult | None:
        """Return the current result for this entity."""
        return self.coordinator.data.get(self._subentry_id, {}).get(self._entity_key)

    @property
    def available(self) -> bool:
        """Return whether this entity currently has a valid value."""
        result = self.entity_result
        return bool(super().available and result and result.value and not result.error)
