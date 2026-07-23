"""The Hyundai Kia Developers integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HyundaiKiaApiClient
from .const import (
    CONF_BRAND,
    CONF_CAR_ID,
    CONF_CAR_TYPE,
    CONF_REDIRECT_URI,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    Brand,
)
from .coordinator import HyundaiKiaDataUpdateCoordinator, subentry_snapshot
from .exceptions import (
    HyundaiKiaAuthenticationError,
    HyundaiKiaConnectionError,
    HyundaiKiaError,
)
from .models import HyundaiKiaConfigEntry, HyundaiKiaRuntimeData

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HyundaiKiaConfigEntry) -> bool:
    """Set up Hyundai Kia Developers from a config entry."""

    def persist_refresh_token(refresh_token: str) -> None:
        """Persist a rotated refresh token without reloading the entry."""
        if refresh_token == entry.data.get(CONF_REFRESH_TOKEN):
            return
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_REFRESH_TOKEN: refresh_token},
        )

    api = HyundaiKiaApiClient(
        async_get_clientsession(hass),
        Brand(str(entry.data[CONF_BRAND])),
        str(entry.data[CONF_CLIENT_ID]),
        str(entry.data[CONF_CLIENT_SECRET]),
        str(entry.data[CONF_REDIRECT_URI]),
        str(entry.data[CONF_REFRESH_TOKEN]),
        persist_refresh_token,
    )
    vehicle_profiles = {}
    try:
        vehicle_profiles = {
            profile.car_id: profile for profile in await api.async_get_vehicles()
        }
    except HyundaiKiaAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except HyundaiKiaError as err:
        _LOGGER.warning(
            "Vehicle profile discovery was unavailable; using stored vehicle data: %s",
            err,
        )

    for subentry in entry.subentries.values():
        car_id = str(subentry.data.get(CONF_CAR_ID, ""))
        profile = vehicle_profiles.get(car_id)
        if profile and profile.car_type != subentry.data.get(CONF_CAR_TYPE):
            hass.config_entries.async_update_subentry(
                entry,
                subentry,
                data={**subentry.data, CONF_CAR_TYPE: profile.car_type},
            )

    coordinator = HyundaiKiaDataUpdateCoordinator(hass, entry, api, vehicle_profiles)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        raise
    except HyundaiKiaAuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="invalid_auth",
        ) from err
    except HyundaiKiaConnectionError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cannot_connect",
        ) from err

    entry.runtime_data = HyundaiKiaRuntimeData(
        api=api,
        coordinator=coordinator,
        vehicle_profiles=vehicle_profiles,
        subentry_snapshot=subentry_snapshot(entry),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: HyundaiKiaConfigEntry
) -> None:
    """Apply option changes and reload when vehicle topology changes."""
    if entry.state is not ConfigEntryState.LOADED:
        return
    runtime = entry.runtime_data
    current_snapshot = subentry_snapshot(entry)
    if current_snapshot != runtime.subentry_snapshot:
        await hass.config_entries.async_reload(entry.entry_id)
        return
    runtime.coordinator.set_scan_interval(
        int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    )


async def async_unload_entry(hass: HomeAssistant, entry: HyundaiKiaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
