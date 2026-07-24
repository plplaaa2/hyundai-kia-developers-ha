"""Button platform for Hyundai Kia Developers."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_CAR_ID, SUBENTRY_TYPE_VEHICLE, EntityKey
from .coordinator import HyundaiKiaDataUpdateCoordinator
from .entity import HyundaiKiaVehicleEntity
from .models import HyundaiKiaConfigEntry

# Related files: __init__.py (platform forwarding), coordinator.py (refresh cadence), sensor.py (vehicle entity pattern).


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HyundaiKiaConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up buttons for every vehicle subentry."""
    coordinator = entry.runtime_data.coordinator
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_VEHICLE:
            continue
        car_id = str(subentry.data[CONF_CAR_ID])
        async_add_entities(
            [
                HyundaiKiaRefreshButton(
                    entry,
                    coordinator,
                    subentry_id,
                    car_id,
                    subentry.title,
                )
            ],
            config_subentry_id=subentry_id,
        )


class HyundaiKiaRefreshButton(HyundaiKiaVehicleEntity, ButtonEntity):
    """Represent a manual refresh button for one vehicle."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "refresh"

    def __init__(
        self,
        entry: HyundaiKiaConfigEntry,
        coordinator: HyundaiKiaDataUpdateCoordinator,
        subentry_id: str,
        car_id: str,
        car_name: str,
    ) -> None:
        """Initialize the refresh button."""
        super().__init__(
            entry,
            coordinator,
            subentry_id,
            car_id,
            car_name,
            EntityKey.ODOMETER,
        )
        self._attr_unique_id = f"{self._attr_unique_id}_refresh"

    async def async_press(self) -> None:
        """Refresh all enabled vehicle data immediately."""
        await self.coordinator.async_request_refresh()
