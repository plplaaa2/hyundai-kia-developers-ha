"""Config flows for Hyundai Kia Developers."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import HyundaiKiaApiClient
from .const import (
    CONF_ACCOUNT_ID,
    CONF_BRAND,
    CONF_CAR_ID,
    CONF_CAR_NAME,
    CONF_CAR_TYPE,
    CONF_REDIRECT_URI,
    CONF_REDIRECT_URL,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_VEHICLE,
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    SUBENTRY_TYPE_VEHICLE,
    Brand,
)
from .exceptions import (
    HyundaiKiaAuthenticationError,
    HyundaiKiaConnectionError,
    HyundaiKiaError,
    HyundaiKiaVehicleError,
)
from .models import HyundaiKiaConfigEntry, TokenResponse, VehicleProfile
from .util import parse_authorization_redirect, vehicle_key


def _credentials_schema(
    values: Mapping[str, Any] | None = None,
    *,
    include_brand: bool,
    require_secret: bool = True,
) -> vol.Schema:
    """Return the developer credentials schema."""
    values = values or {}
    schema: dict[vol.Marker, Any] = {}
    if include_brand:
        schema[
            vol.Required(CONF_BRAND, default=values.get(CONF_BRAND, Brand.HYUNDAI))
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(value=brand.value, label=brand.value.title())
                    for brand in Brand
                ],
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
    schema[vol.Required(CONF_CLIENT_ID, default=values.get(CONF_CLIENT_ID, ""))] = (
        TextSelector()
    )
    secret_key: vol.Marker = (
        vol.Required(CONF_CLIENT_SECRET)
        if require_secret
        else vol.Optional(CONF_CLIENT_SECRET)
    )
    schema[secret_key] = TextSelector(
        TextSelectorConfig(type=TextSelectorType.PASSWORD)
    )
    schema[
        vol.Required(
            CONF_REDIRECT_URI,
            default=values.get(CONF_REDIRECT_URI, DEFAULT_REDIRECT_URI),
        )
    ] = TextSelector(TextSelectorConfig(type=TextSelectorType.URL))
    return vol.Schema(schema)


def _vehicle_name_schema(default: str = "") -> vol.Schema:
    """Return the editable vehicle-name schema."""
    return vol.Schema({vol.Required(CONF_CAR_NAME, default=default): TextSelector()})


def _manual_vehicle_schema(values: Mapping[str, Any] | None = None) -> vol.Schema:
    """Return the manual vehicle fallback schema."""
    values = values or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_CAR_NAME, default=values.get(CONF_CAR_NAME, "")
            ): TextSelector(),
            vol.Required(CONF_CAR_ID, default=values.get(CONF_CAR_ID, "")): str,
        }
    )


def _vehicle_label(profile: VehicleProfile) -> str:
    """Return a useful, disambiguated selector label."""
    detail = profile.sales_model or profile.model_code or profile.car_type
    suffix = profile.car_id[-4:]
    if detail and detail != profile.suggested_name:
        return f"{profile.suggested_name} — {detail} (••••{suffix})"
    return f"{profile.suggested_name} (••••{suffix})"


class HyundaiKiaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle account configuration."""

    VERSION = 1
    MINOR_VERSION = 2

    def __init__(self) -> None:
        """Initialize flow state."""
        self._pending: dict[str, Any] = {}
        self._oauth_state = ""
        self._flow_mode = "user"
        self._target_entry: HyundaiKiaConfigEntry | None = None
        self._api: HyundaiKiaApiClient | None = None
        self._token: TokenResponse | None = None
        self._vehicles: dict[str, VehicleProfile] = {}
        self._selected_vehicle: VehicleProfile | None = None

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return supported vehicle subentry flows."""
        return {SUBENTRY_TYPE_VEHICLE: VehicleSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return HyundaiKiaOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect brand and developer application credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _valid_redirect_uri(str(user_input[CONF_REDIRECT_URI])):
                errors[CONF_REDIRECT_URI] = "invalid_redirect_uri"
            else:
                self._flow_mode = "user"
                self._pending = dict(user_input)
                return await self._start_authorization()
        return self.async_show_form(
            step_id="user",
            data_schema=_credentials_schema(user_input, include_brand=True),
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Accept and validate the pasted OAuth redirect URL."""
        errors: dict[str, str] = {}
        self._api = self._api or self._build_api(self._pending)
        if user_input is not None:
            try:
                code = parse_authorization_redirect(
                    str(user_input[CONF_REDIRECT_URL]),
                    str(self._pending[CONF_REDIRECT_URI]),
                    self._oauth_state,
                )
                self._token = await self._api.async_exchange_authorization_code(code)
                if not self._token.refresh_token:
                    raise HyundaiKiaAuthenticationError(
                        "Authorization response had no refresh token"
                    )
                if self._flow_mode == "user":
                    return await self.async_step_vehicle()
                return await self._finish_existing_authorization()
            except HyundaiKiaAuthenticationError:
                errors["base"] = "invalid_auth"
            except HyundaiKiaConnectionError:
                errors["base"] = "cannot_connect"
        return self._show_authorize_form(errors)

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Discover and select the first vehicle."""
        if user_input is not None:
            selected = self._vehicles.get(str(user_input[CONF_VEHICLE]))
            if selected is None:
                return await self._load_vehicle_choices()
            self._selected_vehicle = selected
            return await self.async_step_vehicle_name()
        return await self._load_vehicle_choices()

    async def async_step_vehicle_name(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect an editable name for the selected vehicle."""
        assert self._selected_vehicle and self._api
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_CAR_NAME]).strip()
            if not name:
                errors[CONF_CAR_NAME] = "required"
            else:
                try:
                    await self._api.async_validate_vehicle(
                        self._selected_vehicle.car_id
                    )
                except HyundaiKiaAuthenticationError:
                    errors["base"] = "invalid_auth"
                except HyundaiKiaConnectionError:
                    errors["base"] = "cannot_connect"
                except HyundaiKiaError:
                    errors["base"] = "invalid_vehicle"
                else:
                    return await self._create_account_entry(
                        name, self._selected_vehicle
                    )
        return self.async_show_form(
            step_id="vehicle_name",
            data_schema=_vehicle_name_schema(self._selected_vehicle.suggested_name),
            errors=errors,
            description_placeholders={
                "vehicle": _vehicle_label(self._selected_vehicle)
            },
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry vehicle discovery using the active token."""
        self._vehicles = {}
        return await self.async_step_vehicle()

    async def async_step_vehicle_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer recovery after vehicle discovery fails."""
        return self.async_show_menu(
            step_id="vehicle_discovery_failed",
            menu_options=["retry", "manual"],
        )

    async def async_step_no_vehicles(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Offer recovery when discovery returns no vehicles."""
        return self.async_show_menu(
            step_id="no_vehicles",
            menu_options=["retry", "manual"],
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manually add the first vehicle after discovery failure."""
        assert self._api
        errors: dict[str, str] = {}
        if user_input is not None:
            car_id = str(user_input[CONF_CAR_ID]).strip()
            name = str(user_input[CONF_CAR_NAME]).strip()
            if car_id and _vehicle_configured(self.hass, self._vehicle_key(car_id)):
                return self.async_abort(reason="already_configured")
            if not name or not car_id:
                errors["base"] = "required"
            else:
                try:
                    await self._api.async_validate_vehicle(car_id)
                except HyundaiKiaAuthenticationError:
                    errors["base"] = "invalid_auth"
                except HyundaiKiaConnectionError:
                    errors["base"] = "cannot_connect"
                except HyundaiKiaError:
                    errors["base"] = "invalid_vehicle"
                else:
                    profile = VehicleProfile(car_id, "", "", "", "")
                    return await self._create_account_entry(name, profile)
        return self.async_show_form(
            step_id="manual",
            data_schema=_manual_vehicle_schema(user_input),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Begin account reauthentication."""
        self._target_entry = self._get_reauth_entry()
        self._flow_mode = "reauth"
        self._pending = dict(entry_data)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication before redirecting the user."""
        if user_input is not None:
            return await self._start_authorization()
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=vol.Schema({})
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Update developer credentials without changing the brand."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not _valid_redirect_uri(str(user_input[CONF_REDIRECT_URI])):
                errors[CONF_REDIRECT_URI] = "invalid_redirect_uri"
            else:
                self._target_entry = entry
                self._flow_mode = "reconfigure"
                self._pending = {
                    **dict(entry.data),
                    **dict(user_input),
                    CONF_CLIENT_SECRET: (
                        str(user_input.get(CONF_CLIENT_SECRET, ""))
                        or str(entry.data[CONF_CLIENT_SECRET])
                    ),
                }
                return await self._start_authorization()
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_credentials_schema(
                entry.data,
                include_brand=False,
                require_secret=False,
            ),
            errors=errors,
        )

    async def async_step_validation_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Retry account validation after a temporary connection failure."""
        if user_input is not None:
            return await self._finish_existing_authorization()
        return self.async_show_form(
            step_id="validation_retry", data_schema=vol.Schema({})
        )

    async def _start_authorization(self) -> ConfigFlowResult:
        """Create fresh OAuth state and show the authorization step."""
        self._oauth_state = secrets.token_urlsafe(32)
        self._api = self._build_api(self._pending)
        return await self.async_step_authorize()

    def _show_authorize_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the manual OAuth redirect-paste form."""
        assert self._api
        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REDIRECT_URL): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    )
                }
            ),
            errors=errors,
            description_placeholders={
                "authorization_url": self._api.authorization_url(self._oauth_state),
                "brand": Brand(str(self._pending[CONF_BRAND])).value.title(),
            },
        )

    async def _load_vehicle_choices(self) -> ConfigFlowResult:
        """Load and display unconfigured vehicles for initial setup."""
        assert self._api
        try:
            discovered = await self._api.async_get_vehicles()
        except HyundaiKiaAuthenticationError:
            self._oauth_state = secrets.token_urlsafe(32)
            return self._show_authorize_form({"base": "invalid_auth"})
        except (HyundaiKiaConnectionError, HyundaiKiaVehicleError):
            return await self.async_step_vehicle_discovery_failed()

        self._vehicles = {
            profile.car_id: profile
            for profile in discovered
            if not _vehicle_configured(self.hass, self._vehicle_key(profile.car_id))
        }
        if discovered and not self._vehicles:
            return self.async_abort(reason="all_vehicles_configured")
        if not self._vehicles:
            return await self.async_step_no_vehicles()
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VEHICLE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=profile.car_id,
                                    label=_vehicle_label(profile),
                                )
                                for profile in self._vehicles.values()
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def _finish_existing_authorization(self) -> ConfigFlowResult:
        """Validate and update a reauthenticated or reconfigured entry."""
        assert self._api and self._token and self._target_entry
        try:
            vehicles = await self._api.async_get_vehicles()
        except HyundaiKiaAuthenticationError:
            self._oauth_state = secrets.token_urlsafe(32)
            return self._show_authorize_form({"base": "invalid_auth"})
        except (HyundaiKiaConnectionError, HyundaiKiaVehicleError):
            return await self.async_step_validation_retry()

        configured_ids = {
            str(subentry.data[CONF_CAR_ID])
            for subentry in self._target_entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_VEHICLE
        }
        discovered_ids = {profile.car_id for profile in vehicles}
        if configured_ids and configured_ids.isdisjoint(discovered_ids):
            return self.async_abort(reason="wrong_account")

        refresh_token = self._api.refresh_token or self._token.refresh_token
        assert refresh_token
        return self.async_update_reload_and_abort(
            self._target_entry,
            data_updates={
                CONF_CLIENT_ID: str(self._pending[CONF_CLIENT_ID]),
                CONF_CLIENT_SECRET: str(self._pending[CONF_CLIENT_SECRET]),
                CONF_REDIRECT_URI: str(self._pending[CONF_REDIRECT_URI]),
                CONF_REFRESH_TOKEN: refresh_token,
            },
        )

    async def _create_account_entry(
        self, vehicle_name: str, profile: VehicleProfile
    ) -> ConfigFlowResult:
        """Create the account and its first vehicle atomically."""
        assert self._api and self._token
        refresh_token = self._api.refresh_token or self._token.refresh_token
        assert refresh_token
        brand = Brand(str(self._pending[CONF_BRAND]))
        account_id = uuid4().hex
        await self.async_set_unique_id(f"{brand.value}:{account_id}")
        car_data: dict[str, str] = {CONF_CAR_ID: profile.car_id}
        if profile.car_type:
            car_data[CONF_CAR_TYPE] = profile.car_type
        return self.async_create_entry(
            title=_next_account_title(self.hass, brand),
            data={
                CONF_ACCOUNT_ID: account_id,
                CONF_BRAND: brand.value,
                CONF_CLIENT_ID: str(self._pending[CONF_CLIENT_ID]),
                CONF_CLIENT_SECRET: str(self._pending[CONF_CLIENT_SECRET]),
                CONF_REDIRECT_URI: str(self._pending[CONF_REDIRECT_URI]),
                CONF_REFRESH_TOKEN: refresh_token,
            },
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
            subentries=[
                {
                    "subentry_type": SUBENTRY_TYPE_VEHICLE,
                    "title": vehicle_name,
                    "data": car_data,
                    "unique_id": self._vehicle_key(profile.car_id),
                }
            ],
        )

    def _vehicle_key(self, car_id: str) -> str:
        """Return a privacy-preserving vehicle key for this pending brand."""
        return vehicle_key(str(self._pending[CONF_BRAND]), car_id)

    def _build_api(self, data: Mapping[str, Any]) -> HyundaiKiaApiClient:
        """Build an API client for config-flow validation."""
        return HyundaiKiaApiClient(
            async_get_clientsession(self.hass),
            Brand(str(data[CONF_BRAND])),
            str(data[CONF_CLIENT_ID]),
            str(data[CONF_CLIENT_SECRET]),
            str(data[CONF_REDIRECT_URI]),
            str(data.get(CONF_REFRESH_TOKEN, "")) or None,
        )


class VehicleSubentryFlowHandler(ConfigSubentryFlow):
    """Discover, add, and rename vehicles under an account."""

    def __init__(self) -> None:
        """Initialize vehicle-flow state."""
        self._api: HyundaiKiaApiClient | None = None
        self._vehicles: dict[str, VehicleProfile] = {}
        self._selected_vehicle: VehicleProfile | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Start vehicle discovery."""
        return await self.async_step_vehicle(user_input)

    async def async_step_vehicle(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Discover and select a vehicle."""
        if user_input is not None:
            selected = self._vehicles.get(str(user_input[CONF_VEHICLE]))
            if selected is not None:
                self._selected_vehicle = selected
                return await self.async_step_vehicle_name()

        entry = self._get_entry()
        self._api = self._api or self._build_api(entry)
        try:
            discovered = await self._api.async_get_vehicles()
        except HyundaiKiaAuthenticationError:
            entry.async_start_reauth_if_available(self.hass)
            return self.async_abort(reason="reauth_required")
        except (HyundaiKiaConnectionError, HyundaiKiaVehicleError):
            return await self.async_step_vehicle_discovery_failed()

        self._vehicles = {
            profile.car_id: profile
            for profile in discovered
            if not _vehicle_configured(
                self.hass, vehicle_key(str(entry.data[CONF_BRAND]), profile.car_id)
            )
        }
        if discovered and not self._vehicles:
            return self.async_abort(reason="all_vehicles_configured")
        if not self._vehicles:
            return await self.async_step_no_vehicles()
        return self.async_show_form(
            step_id="vehicle",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_VEHICLE): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=profile.car_id,
                                    label=_vehicle_label(profile),
                                )
                                for profile in self._vehicles.values()
                            ]
                        )
                    )
                }
            ),
        )

    async def async_step_vehicle_name(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Collect the selected vehicle's friendly name."""
        assert self._selected_vehicle and self._api
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_CAR_NAME]).strip()
            if not name:
                errors[CONF_CAR_NAME] = "required"
            else:
                try:
                    await self._api.async_validate_vehicle(
                        self._selected_vehicle.car_id
                    )
                except HyundaiKiaAuthenticationError:
                    self._get_entry().async_start_reauth_if_available(self.hass)
                    return self.async_abort(reason="reauth_required")
                except HyundaiKiaConnectionError:
                    errors["base"] = "cannot_connect"
                except HyundaiKiaError:
                    errors["base"] = "invalid_vehicle"
                else:
                    data = {CONF_CAR_ID: self._selected_vehicle.car_id}
                    if self._selected_vehicle.car_type:
                        data[CONF_CAR_TYPE] = self._selected_vehicle.car_type
                    return self.async_create_entry(
                        title=name,
                        data=data,
                        unique_id=self._vehicle_unique_id(
                            self._selected_vehicle.car_id
                        ),
                    )
        return self.async_show_form(
            step_id="vehicle_name",
            data_schema=_vehicle_name_schema(self._selected_vehicle.suggested_name),
            errors=errors,
            description_placeholders={
                "vehicle": _vehicle_label(self._selected_vehicle)
            },
        )

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Retry vehicle discovery."""
        self._vehicles = {}
        return await self.async_step_vehicle()

    async def async_step_vehicle_discovery_failed(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer recovery after vehicle discovery fails."""
        return self.async_show_menu(
            step_id="vehicle_discovery_failed",
            menu_options=["retry", "manual"],
        )

    async def async_step_no_vehicles(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Offer recovery when discovery returns no vehicles."""
        return self.async_show_menu(
            step_id="no_vehicles",
            menu_options=["retry", "manual"],
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Manually add a vehicle after discovery failure."""
        entry = self._get_entry()
        self._api = self._api or self._build_api(entry)
        errors: dict[str, str] = {}
        if user_input is not None:
            car_id = str(user_input[CONF_CAR_ID]).strip()
            name = str(user_input[CONF_CAR_NAME]).strip()
            unique_id = self._vehicle_unique_id(car_id)
            if _vehicle_configured(self.hass, unique_id):
                return self.async_abort(reason="already_configured")
            if not name or not car_id:
                errors["base"] = "required"
            else:
                try:
                    await self._api.async_validate_vehicle(car_id)
                except HyundaiKiaAuthenticationError:
                    entry.async_start_reauth_if_available(self.hass)
                    return self.async_abort(reason="reauth_required")
                except HyundaiKiaConnectionError:
                    errors["base"] = "cannot_connect"
                except HyundaiKiaError:
                    errors["base"] = "invalid_vehicle"
                else:
                    return self.async_create_entry(
                        title=name,
                        data={CONF_CAR_ID: car_id},
                        unique_id=unique_id,
                    )
        return self.async_show_form(
            step_id="manual",
            data_schema=_manual_vehicle_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Rename a vehicle without changing its identity."""
        entry = self._get_entry()
        subentry = self._get_reconfigure_subentry()
        errors: dict[str, str] = {}
        if user_input is not None:
            name = str(user_input[CONF_CAR_NAME]).strip()
            if not name:
                errors[CONF_CAR_NAME] = "required"
            else:
                return self.async_update_and_abort(entry, subentry, title=name)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_vehicle_name_schema(subentry.title),
            errors=errors,
        )

    def _build_api(self, entry: HyundaiKiaConfigEntry) -> HyundaiKiaApiClient:
        """Build an API client that persists rotated refresh tokens."""

        def persist_refresh_token(refresh_token: str) -> None:
            if refresh_token != entry.data[CONF_REFRESH_TOKEN]:
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_REFRESH_TOKEN: refresh_token},
                )

        return HyundaiKiaApiClient(
            async_get_clientsession(self.hass),
            Brand(str(entry.data[CONF_BRAND])),
            str(entry.data[CONF_CLIENT_ID]),
            str(entry.data[CONF_CLIENT_SECRET]),
            str(entry.data[CONF_REDIRECT_URI]),
            str(entry.data[CONF_REFRESH_TOKEN]),
            persist_refresh_token,
        )

    def _vehicle_unique_id(self, car_id: str) -> str:
        """Return the selected vehicle's privacy-preserving unique ID."""
        entry = self._get_entry()
        return vehicle_key(str(entry.data[CONF_BRAND]), car_id)


class HyundaiKiaOptionsFlow(OptionsFlow):
    """Manage account polling options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Configure account options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    )
                }
            ),
        )


def _valid_redirect_uri(value: str) -> bool:
    """Return whether the registered redirect URI is valid for this flow."""
    redirect = urlparse(value)
    return redirect.scheme == "https" and bool(redirect.netloc)


def _vehicle_configured(hass: Any, unique_id: str) -> bool:
    """Return whether a vehicle exists in any configured account."""
    return any(
        subentry.unique_id == unique_id
        for entry in hass.config_entries.async_entries(DOMAIN)
        for subentry in entry.subentries.values()
    )


def _next_account_title(hass: Any, brand: Brand) -> str:
    """Generate a simple brand title with a same-brand suffix."""
    count = sum(
        entry.data.get(CONF_BRAND) == brand.value
        for entry in hass.config_entries.async_entries(DOMAIN)
    )
    return brand.value.title() if count == 0 else f"{brand.value.title()} {count + 1}"
