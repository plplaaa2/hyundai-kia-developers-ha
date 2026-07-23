"""Diagnostics support for Hyundai Kia Developers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CAR_ID,
    CONF_REDIRECT_URI,
    CONF_REFRESH_TOKEN,
    EntityKey,
)
from .models import HyundaiKiaConfigEntry

TO_REDACT = {
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_REFRESH_TOKEN,
    CONF_REDIRECT_URI,
    CONF_CAR_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HyundaiKiaConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    runtime = entry.runtime_data
    vehicles: list[dict[str, Any]] = []
    for subentry_id, subentry in entry.subentries.items():
        metric_data = runtime.coordinator.data.get(subentry_id, {})
        vehicles.append(
            {
                "title": subentry.title,
                "subentry_type": subentry.subentry_type,
                "data": async_redact_data(dict(subentry.data), TO_REDACT),
                "metrics": {
                    key.value: {
                        "available": bool(
                            (result := metric_data.get(key))
                            and result.value
                            and not result.error
                        ),
                        "value": (
                            result.value.value
                            if result and result.value and not result.error
                            else None
                        ),
                        "timestamp": (
                            result.value.timestamp
                            if result and result.value and not result.error
                            else None
                        ),
                        "error": result.error if result else None,
                    }
                    for key in EntityKey
                },
            }
        )
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "coordinator": {
            "last_update_success": runtime.coordinator.last_update_success,
            "vehicle_count": len(vehicles),
            "vehicles": vehicles,
        },
    }
