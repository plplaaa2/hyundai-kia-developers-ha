"""Data coordinator for Hyundai Kia Developers."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HyundaiKiaApiClient
from .const import (
    CONF_CAR_ID,
    CONF_CAR_MODEL,
    CONF_CAR_TYPE,
    CONF_ANDROID_AUTO_ENTITY,
    CORE_ENTITY_KEYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    ENTITY_ENDPOINT,
    EV_DEFAULT_ENTITY_KEYS,
    EV_VEHICLE_TYPES,
    MAX_PARALLEL_REQUESTS,
    STATIC_ENTITY_KEYS,
    SUBENTRY_TYPE_VEHICLE,
    EndpointKey,
    EntityKey,
    vehicle_type_label,
)
from .exceptions import (
    HyundaiKiaAuthenticationError,
    HyundaiKiaError,
    HyundaiKiaVehicleError,
)
from .models import EntityResult, EntityValue, HyundaiKiaConfigEntry, VehicleProfile

type CoordinatorData = dict[str, dict[EntityKey, EntityResult]]
type EntityContext = tuple[str, EntityKey]
type EndpointJob = tuple[str, EndpointKey]

_LOGGER = logging.getLogger(__name__)

# Related files: config_flow.py (selected Android Auto entity), __init__.py (option updates).
ANDROID_AUTO_CONNECTED_INTERVAL = timedelta(minutes=5)
ANDROID_AUTO_DISCONNECTED_INTERVAL = timedelta(hours=6)


class HyundaiKiaDataUpdateCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """Coordinate endpoint updates for every vehicle on an account."""

    config_entry: HyundaiKiaConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: HyundaiKiaConfigEntry,
        api: HyundaiKiaApiClient,
        vehicle_profiles: dict[str, VehicleProfile],
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        self.vehicle_profiles = vehicle_profiles
        self._request_semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)
        self._fallback_scan_interval = timedelta(
            minutes=int(entry.options.get("scan_interval", DEFAULT_SCAN_INTERVAL))
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=self._fallback_scan_interval,
            always_update=False,
        )
        entity_ids = self._android_auto_entities()
        if entity_ids:
            entry.async_on_unload(
                async_track_state_change_event(
                    hass, entity_ids, self._async_android_auto_state_changed
                )
            )

    async def _async_update_data(self) -> CoordinatorData:
        """Fetch unique endpoints requested by enabled entity contexts."""
        vehicles = {
            subentry_id: subentry
            for subentry_id, subentry in self.config_entry.subentries.items()
            if subentry.subentry_type == SUBENTRY_TYPE_VEHICLE
        }
        if not vehicles:
            return {}

        contexts = self._valid_contexts(vehicles)
        if not contexts:
            contexts = self._default_contexts(vehicles)
        polled_contexts = {
            (subentry_id, key)
            for subentry_id, key in contexts
            if key in ENTITY_ENDPOINT
        }

        jobs: dict[EndpointJob, set[EntityKey]] = {}
        for subentry_id, key in polled_contexts:
            jobs.setdefault((subentry_id, ENTITY_ENDPOINT[key]), set()).add(key)

        tasks = [
            self._async_fetch_endpoint(vehicles[subentry_id], endpoint, requested_keys)
            for (subentry_id, endpoint), requested_keys in sorted(
                jobs.items(), key=lambda item: (item[0][0], item[0][1].value)
            )
        ]
        try:
            results = await asyncio.gather(*tasks)
        except HyundaiKiaAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err

        previous = self.data or {}
        data: CoordinatorData = {
            subentry_id: dict(previous.get(subentry_id, {})) for subentry_id in vehicles
        }
        for subentry_id, subentry in vehicles.items():
            self._set_static_values(data[subentry_id], subentry)
        successes = 0
        errors: list[Exception] = []
        for subentry_id, values, requested_keys, error in results:
            if error is None:
                successes += 1
                for key, value in values.items():
                    data[subentry_id][key] = EntityResult(key=key, value=value)
                for missing_key in requested_keys - values.keys():
                    data[subentry_id][missing_key] = EntityResult(
                        key=missing_key,
                        value=None,
                        error="DataUnavailable",
                    )
            else:
                errors.append(error)
                for key in requested_keys:
                    data[subentry_id][key] = EntityResult(
                        key=key,
                        value=None,
                        error=error.__class__.__name__,
                        error_code=getattr(error, "error_code", None),
                        error_message=getattr(error, "error_message", None),
                    )

        if errors and not successes and not all(
            isinstance(error, HyundaiKiaVehicleError) for error in errors
        ):
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_failed",
            ) from errors[0]
        for subentry_id in vehicles:
            self._set_error_message(data[subentry_id])
            self._set_last_sensor_value_sent_at(data[subentry_id])
        self._update_scan_interval()
        return data

    def _valid_contexts(
        self, vehicles: dict[str, ConfigSubentry]
    ) -> set[EntityContext]:
        """Return valid entity contexts registered with the coordinator."""
        return {
            context
            for context in set(self.async_contexts())
            if isinstance(context, tuple)
            and len(context) == 2
            and context[0] in vehicles
            and isinstance(context[1], EntityKey)
        }

    def _default_contexts(
        self, vehicles: dict[str, ConfigSubentry]
    ) -> set[EntityContext]:
        """Return initial contexts before entities have been added."""
        contexts = {
            (subentry_id, key) for subentry_id in vehicles for key in CORE_ENTITY_KEYS
        }
        contexts.update(
            (subentry_id, key) for subentry_id in vehicles for key in STATIC_ENTITY_KEYS
        )
        for subentry_id, subentry in vehicles.items():
            if self.car_type(subentry) in EV_VEHICLE_TYPES:
                contexts.update((subentry_id, key) for key in EV_DEFAULT_ENTITY_KEYS)
        return contexts

    async def _async_fetch_endpoint(
        self,
        subentry: ConfigSubentry,
        endpoint: EndpointKey,
        requested_keys: set[EntityKey],
    ) -> tuple[
        str,
        dict[EntityKey, EntityValue],
        set[EntityKey],
        Exception | None,
    ]:
        """Fetch one endpoint and retain partial-failure context."""
        try:
            async with self._request_semaphore:
                values = await self.api.async_get_endpoint(
                    str(subentry.data[CONF_CAR_ID]), endpoint
                )
        except HyundaiKiaAuthenticationError:
            raise
        except HyundaiKiaError as err:
            return subentry.subentry_id, {}, requested_keys, err
        return subentry.subentry_id, values, requested_keys, None

    def car_type(self, subentry: ConfigSubentry) -> str:
        """Return a vehicle type from live profile data or stored fallback."""
        car_id = str(subentry.data[CONF_CAR_ID])
        if profile := self.vehicle_profiles.get(car_id):
            return profile.car_type
        return str(subentry.data.get(CONF_CAR_TYPE, "")).upper()

    def model_name(self, subentry: ConfigSubentry) -> str:
        """Return the best vehicle model name from live profile data or stored fallback."""
        car_id = str(subentry.data[CONF_CAR_ID])
        if profile := self.vehicle_profiles.get(car_id):
            return profile.sales_model or profile.model_code
        return str(subentry.data.get(CONF_CAR_MODEL, ""))

    def _set_static_values(
        self, values: dict[EntityKey, EntityResult], subentry: ConfigSubentry
    ) -> None:
        """Expose profile-backed values without polling extra API endpoints."""
        static_values = {
            EntityKey.VEHICLE_TYPE: vehicle_type_label(self.car_type(subentry)),
            EntityKey.MODEL_NAME: self.model_name(subentry),
        }
        for key, value in static_values.items():
            values[key] = EntityResult(
                key=key,
                value=EntityValue(value) if value else None,
                error=None if value else "DataUnavailable",
            )

    @staticmethod
    def _set_error_message(values: dict[EntityKey, EntityResult]) -> None:
        """Expose the latest endpoint error as one diagnostic sensor."""
        latest: EntityResult | None = None
        for key, result in values.items():
            if key is EntityKey.LAST_SENSOR_VALUE_SENT_AT:
                continue
            if not result.error:
                continue
            if result.error == "DataUnavailable" and not result.error_code and not result.error_message:
                continue
            latest = result

        if latest is None:
            values[EntityKey.ERROR_MESSAGE] = EntityResult(
                key=EntityKey.ERROR_MESSAGE,
                value=None,
                error="DataUnavailable",
            )
            return

        # Keep the entity state stable and language-neutral by exposing only the code.
        text = str(latest.error_code or latest.error or "Unknown error").strip()
        values[EntityKey.ERROR_MESSAGE] = EntityResult(
            key=EntityKey.ERROR_MESSAGE,
            value=EntityValue(text),
            error=None,
            error_code=latest.error_code,
            error_message=latest.error_message,
        )

    @staticmethod
    def _set_last_sensor_value_sent_at(values: dict[EntityKey, EntityResult]) -> None:
        """Expose the latest provider timestamp already returned by polled endpoints."""
        latest = max(
            (
                result.value.timestamp
                for key, result in values.items()
                if key is not EntityKey.LAST_SENSOR_VALUE_SENT_AT
                and result.value
                and result.value.timestamp
            ),
            default=None,
        )
        values[EntityKey.LAST_SENSOR_VALUE_SENT_AT] = EntityResult(
            key=EntityKey.LAST_SENSOR_VALUE_SENT_AT,
            value=EntityValue(latest) if latest else None,
            error=None if latest else "DataUnavailable",
        )

    def set_scan_interval(self, minutes: int) -> None:
        """Update the fallback polling interval for unconfigured vehicles."""
        self._fallback_scan_interval = timedelta(minutes=minutes)
        if not self._android_auto_entities():
            self.update_interval = self._fallback_scan_interval

    def _android_auto_entities(self) -> list[str]:
        """Return configured Android Auto connection entities."""
        return [
            str(subentry.data[CONF_ANDROID_AUTO_ENTITY])
            for subentry in self.config_entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_VEHICLE
            and subentry.data.get(CONF_ANDROID_AUTO_ENTITY)
        ]

    def _update_scan_interval(self) -> None:
        """Adjust polling speed from Android Auto connection state."""
        entities = self._android_auto_entities()
        if not entities:
            self.update_interval = self._fallback_scan_interval
            return

        connected = any(
            self.hass.states.is_state(entity_id, STATE_ON) for entity_id in entities
        )
        disconnected_states = {STATE_OFF, STATE_UNAVAILABLE, STATE_UNKNOWN}
        if connected:
            next_interval = ANDROID_AUTO_CONNECTED_INTERVAL
        else:
            states = [self.hass.states.get(entity_id) for entity_id in entities]
            if not all(
                state is None or state.state in disconnected_states for state in states
            ):
                _LOGGER.debug(
                    "Treating non-connected Android Auto states as disconnected"
                )
            next_interval = ANDROID_AUTO_DISCONNECTED_INTERVAL

        if self.update_interval != next_interval:
            _LOGGER.debug("Updating scan interval to %s", next_interval)
        self.update_interval = next_interval

    async def _async_android_auto_state_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        """Refresh promptly when Android Auto connects or disconnects."""
        del event
        previous_interval = self.update_interval
        self._update_scan_interval()
        if self.update_interval != previous_interval:
            await self.async_request_refresh()


def subentry_snapshot(
    entry: HyundaiKiaConfigEntry,
) -> tuple[tuple[str, str, str, str], ...]:
    """Return vehicle fields that require a platform reload."""
    return tuple(
        sorted(
            (
                subentry.subentry_id,
                subentry.title,
                str(subentry.data.get(CONF_CAR_ID, "")),
                str(subentry.data.get(CONF_ANDROID_AUTO_ENTITY, "")),
            )
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_VEHICLE
        )
    )
