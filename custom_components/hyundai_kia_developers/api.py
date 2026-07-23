"""Asynchronous Korean Hyundai/Kia connected-car API client."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ClientResponse, ClientSession, encode_basic_auth

from .const import (
    BRAND_ENDPOINTS,
    REQUEST_TIMEOUT_SECONDS,
    TOKEN_REFRESH_MARGIN_SECONDS,
    Brand,
    EndpointKey,
    EntityKey,
)
from .exceptions import (
    HyundaiKiaAuthenticationError,
    HyundaiKiaConnectionError,
    HyundaiKiaRateLimitError,
    HyundaiKiaVehicleError,
)
from .models import EntityValue, TokenResponse, VehicleProfile

_LOGGER = logging.getLogger(__name__)

RefreshTokenCallback = Callable[[str], None]

ENDPOINT_PATHS: dict[EndpointKey, str] = {
    EndpointKey.DISTANCE_TO_EMPTY: "/api/v1/car/status/{car_id}/dte",
    EndpointKey.ODOMETER: "/api/v1/car/status/{car_id}/odometer",
    EndpointKey.EV_BATTERY: "/api/v1/car/status/{car_id}/ev/battery",
    EndpointKey.EV_CHARGING: "/api/v1/car/status/{car_id}/ev/charging",
    EndpointKey.LOW_FUEL_WARNING: "/api/v1/car/status/warning/{car_id}/lowFuel",
    EndpointKey.TIRE_PRESSURE_WARNING: (
        "/api/v1/car/status/warning/{car_id}/tirePressure"
    ),
    EndpointKey.LAMP_WIRE_WARNING: "/api/v1/car/status/warning/{car_id}/lampWire",
    EndpointKey.SMART_KEY_BATTERY_WARNING: (
        "/api/v1/car/status/warning/{car_id}/smartKeyBattery"
    ),
    EndpointKey.WASHER_FLUID_WARNING: (
        "/api/v1/car/status/warning/{car_id}/washerFluid"
    ),
    EndpointKey.BRAKE_FLUID_WARNING: "/api/v1/car/status/warning/{car_id}/breakOil",
    EndpointKey.ENGINE_OIL_WARNING: "/api/v1/car/status/warning/{car_id}/engineOil",
}

WARNING_ENTITY_KEYS: dict[EndpointKey, EntityKey] = {
    EndpointKey.LOW_FUEL_WARNING: EntityKey.LOW_FUEL_WARNING,
    EndpointKey.TIRE_PRESSURE_WARNING: EntityKey.TIRE_PRESSURE_WARNING,
    EndpointKey.LAMP_WIRE_WARNING: EntityKey.LAMP_WIRE_WARNING,
    EndpointKey.SMART_KEY_BATTERY_WARNING: EntityKey.SMART_KEY_BATTERY_WARNING,
    EndpointKey.WASHER_FLUID_WARNING: EntityKey.WASHER_FLUID_WARNING,
    EndpointKey.BRAKE_FLUID_WARNING: EntityKey.BRAKE_FLUID_WARNING,
    EndpointKey.ENGINE_OIL_WARNING: EntityKey.ENGINE_OIL_WARNING,
}

DISTANCE_TO_KM = {
    0: 0.0003048,
    1: 1.0,
    2: 0.001,
    3: 1.609344,
}
TIME_TO_MINUTES = {
    0: 60.0,
    1: 1.0,
    2: 1 / 60000,
    3: 1 / 60,
}
CHARGER_TYPES = {0: "not_connected", 1: "fast", 2: "normal"}
VEHICLE_AUTH_ERROR_CODES = {"4011", "4012", "4016"}
# 차량이 존재하지만 일시적으로 데이터를 제공할 수 없는 비치명적 에러 코드
# (장기 미운행, 단말 전송 오류, 서비스 미지원 차량 등)
# 관련 파일: config_flow.py (async_step_vehicle_name → async_validate_vehicle)
VEHICLE_NONFATAL_ERROR_CODES = {
    "4045",  # No data: 장기 미운행 또는 단말 데이터 전송 오류
    "4041",  # Unregistered Device: CCS 미가입 차량
    "5032",  # Service Unavailable: 데이터 조회 불가 차량
    "5003",  # Service Provider Error: 연동 서비스 오류
    "5004",  # Internal Server Permission Error
    "5041",  # Gateway Timeout
}


class HyundaiKiaApiClient:
    """Client for the matching Hyundai and Kia Korean developer APIs."""

    def __init__(
        self,
        session: ClientSession,
        brand: Brand,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        refresh_token: str | None = None,
        on_refresh_token: RefreshTokenCallback | None = None,
    ) -> None:
        """Initialize the API client."""
        self._session = session
        self.brand = brand
        self._client_id = client_id
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._refresh_token = refresh_token
        self._on_refresh_token = on_refresh_token
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._token_lock = asyncio.Lock()

    @property
    def refresh_token(self) -> str | None:
        """Return the current refresh token."""
        return self._refresh_token

    def authorization_url(self, state: str) -> str:
        """Build the interactive OAuth authorization URL."""
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self._client_id,
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{BRAND_ENDPOINTS[self.brand].authorize_url}?{query}"

    async def async_exchange_authorization_code(self, code: str) -> TokenResponse:
        """Exchange a one-time authorization code and activate the token set."""
        token = await self._async_token_request(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
            }
        )
        self._activate_token(token)
        return token

    async def async_ensure_access_token(self, *, force: bool = False) -> str:
        """Return a usable access token, refreshing it when needed."""
        if not force and self._access_token_is_valid():
            return self._access_token  # type: ignore[return-value]

        async with self._token_lock:
            if not force and self._access_token_is_valid():
                return self._access_token  # type: ignore[return-value]
            if not self._refresh_token:
                raise HyundaiKiaAuthenticationError("No refresh token is available")

            token = await self._async_token_request(
                {
                    "grant_type": "refresh_token",
                    "refresh_token": self._refresh_token,
                    "redirect_uri": self.redirect_uri,
                }
            )
            self._activate_token(token)
            return token.access_token

    async def async_get_vehicles(self) -> list[VehicleProfile]:
        """Return vehicles authorized for this account."""
        url = f"{BRAND_ENDPOINTS[self.brand].vehicle_base}/api/v1/car/profile/carlist"
        status, payload = await self._async_authenticated_json(url)
        error_code = self._error_code(payload)
        if error_code == "4045":
            return []
        self._raise_for_api_error(status, error_code, "Vehicle list")

        cars = payload.get("cars")
        if not isinstance(cars, list):
            raise HyundaiKiaVehicleError("Vehicle list response was malformed")

        vehicles: list[VehicleProfile] = []
        try:
            for car in cars:
                if not isinstance(car, dict) or not str(car.get("carId", "")).strip():
                    raise ValueError
                vehicles.append(
                    VehicleProfile(
                        car_id=str(car["carId"]).strip(),
                        nickname=str(car.get("carNickname", "")).strip(),
                        car_type=str(car.get("carType", "")).strip().upper(),
                        model_code=str(car.get("carName", "")).strip(),
                        sales_model=str(car.get("carSellname", "")).strip(),
                    )
                )
        except (KeyError, TypeError, ValueError) as err:
            raise HyundaiKiaVehicleError("Vehicle list response was malformed") from err
        return vehicles

    async def async_get_endpoint(
        self, car_id: str, endpoint: EndpointKey
    ) -> dict[EntityKey, EntityValue]:
        """Fetch and parse one independently polled vehicle endpoint."""
        path = ENDPOINT_PATHS[endpoint].format(car_id=car_id)
        url = f"{BRAND_ENDPOINTS[self.brand].vehicle_base}{path}"
        status, payload = await self._async_authenticated_json(url)
        self._raise_for_api_error(status, self._error_code(payload), endpoint.value)
        return self._parse_endpoint(endpoint, payload)

    async def async_validate_vehicle(self, car_id: str) -> None:
        """Validate a car ID; non-fatal data-unavailability errors are tolerated.

        carlist에서 이미 차량이 확인된 경우, DTE/Odometer 엔드포인트가
        일시적 데이터 부재(4045, 5032 등) 에러를 반환해도 설정을 계속할 수 있음.
        """
        await asyncio.gather(
            self._async_check_endpoint(car_id, EndpointKey.DISTANCE_TO_EMPTY),
            self._async_check_endpoint(car_id, EndpointKey.ODOMETER),
        )

    async def _async_check_endpoint(self, car_id: str, endpoint: EndpointKey) -> None:
        """엔드포인트 도달 가능 여부를 확인하되, 비치명적 데이터 에러는 허용한다."""
        path = ENDPOINT_PATHS[endpoint].format(car_id=car_id)
        url = f"{BRAND_ENDPOINTS[self.brand].vehicle_base}{path}"
        status, payload = await self._async_authenticated_json(url)
        error_code = self._error_code(payload)
        if error_code in VEHICLE_NONFATAL_ERROR_CODES:
            _LOGGER.warning(
                "차량 ••••%s %s 엔드포인트: errCode=%s (일시적 데이터 부재, 설정 계속)",
                car_id[-4:],
                endpoint.value,
                error_code,
            )
            return
        self._raise_for_api_error(status, error_code, endpoint.value)

    def _access_token_is_valid(self) -> bool:
        """Return whether the in-memory access token has adequate lifetime."""
        return bool(
            self._access_token
            and self._access_token_expires_at
            > time.time() + TOKEN_REFRESH_MARGIN_SECONDS
        )

    def _activate_token(self, token: TokenResponse) -> None:
        """Activate token data and persist a rotated refresh token."""
        self._access_token = token.access_token
        self._access_token_expires_at = time.time() + token.expires_in
        if token.refresh_token and token.refresh_token != self._refresh_token:
            self._refresh_token = token.refresh_token
            if self._on_refresh_token:
                self._on_refresh_token(token.refresh_token)

    async def _async_token_request(self, data: dict[str, str]) -> TokenResponse:
        """Make a provider-specific OAuth token request."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                response = await self._session.post(
                    BRAND_ENDPOINTS[self.brand].token_url,
                    headers={
                        "Accept": "application/json",
                        "Authorization": encode_basic_auth(
                            self._client_id, self._client_secret
                        ),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data=data,
                )
        except (TimeoutError, ClientError) as err:
            raise HyundaiKiaConnectionError("OAuth token request failed") from err

        payload = await self._async_json(response)
        error_code = self._error_code(payload)
        if response.status >= 400:
            if response.status in (400, 401, 403) or error_code == "4002":
                raise HyundaiKiaAuthenticationError(
                    f"OAuth token request was rejected ({error_code})"
                )
            if response.status == 429:
                raise HyundaiKiaRateLimitError("OAuth token rate limit reached")
            raise HyundaiKiaConnectionError(
                f"OAuth token endpoint returned HTTP {response.status}"
            )

        try:
            return TokenResponse(
                access_token=str(payload["access_token"]),
                refresh_token=(
                    str(payload["refresh_token"])
                    if payload.get("refresh_token")
                    else None
                ),
                expires_in=int(payload["expires_in"]),
                token_type=str(payload.get("token_type", "Bearer")),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise HyundaiKiaConnectionError(
                "OAuth token response was incomplete"
            ) from err

    async def _async_authenticated_json(self, url: str) -> tuple[int, dict[str, Any]]:
        """Make an authenticated GET, retrying once after token rejection."""
        for attempt in range(2):
            access_token = await self.async_ensure_access_token(force=attempt == 1)
            response = await self._async_get(
                url, headers={"Authorization": f"Bearer {access_token}"}
            )
            payload = await self._async_json(response)
            if response.status in (401, 403):
                self._access_token = None
                self._access_token_expires_at = 0.0
                if attempt == 0:
                    continue
                raise HyundaiKiaAuthenticationError(
                    "Vehicle API rejected refreshed credentials"
                )
            if response.status == 429:
                raise HyundaiKiaRateLimitError("Vehicle API rate limit reached")
            return response.status, payload
        raise HyundaiKiaAuthenticationError("Unable to authenticate vehicle request")

    async def _async_get(self, url: str, *, headers: dict[str, str]) -> ClientResponse:
        """Make a bounded GET request."""
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
                return await self._session.get(
                    url, headers={"Accept": "application/json", **headers}
                )
        except (TimeoutError, ClientError) as err:
            raise HyundaiKiaConnectionError("Vehicle API request failed") from err

    @staticmethod
    async def _async_json(response: ClientResponse) -> dict[str, Any]:
        """Decode a JSON response without trusting its content type."""
        try:
            payload = await response.json(content_type=None)
        except (ClientError, json.JSONDecodeError, ValueError) as err:
            raise HyundaiKiaConnectionError("API returned invalid JSON") from err
        if not isinstance(payload, dict):
            raise HyundaiKiaConnectionError("API returned an unexpected JSON value")
        return payload

    @staticmethod
    def _error_code(payload: dict[str, Any]) -> str:
        """Return a provider error code across known response variants."""
        return str(
            payload.get(
                "errCode",
                payload.get("resCode", payload.get("error", "unknown")),
            )
        )

    @staticmethod
    def _raise_for_api_error(status: int, error_code: str, operation: str) -> None:
        """Classify a vehicle API error without exposing response contents."""
        if error_code in VEHICLE_AUTH_ERROR_CODES:
            _LOGGER.debug(
                "%s 인증 에러: errCode=%s (HTTP %d)", operation, error_code, status
            )
            raise HyundaiKiaAuthenticationError(
                f"{operation} request was rejected ({error_code})"
            )
        if status < 400:
            if error_code != "unknown":
                _LOGGER.debug(
                    "%s API 에러: errCode=%s (HTTP %d)", operation, error_code, status
                )
                raise HyundaiKiaVehicleError(
                    f"{operation} request was rejected ({error_code})"
                )
            return
        if status in (401, 403):
            _LOGGER.debug(
                "%s 인증 거부: HTTP %d errCode=%s", operation, status, error_code
            )
            raise HyundaiKiaAuthenticationError(
                f"{operation} request was rejected ({error_code})"
            )
        _LOGGER.debug(
            "%s HTTP 에러: HTTP %d errCode=%s", operation, status, error_code
        )
        raise HyundaiKiaVehicleError(f"{operation} request returned HTTP {status}")

    @classmethod
    def _parse_endpoint(
        cls, endpoint: EndpointKey, payload: dict[str, Any]
    ) -> dict[EntityKey, EntityValue]:
        """Parse one documented vehicle endpoint response."""
        try:
            if endpoint is EndpointKey.DISTANCE_TO_EMPTY:
                timestamp = cls._timestamp(payload)
                values = {
                    EntityKey.DISTANCE_TO_EMPTY: EntityValue(
                        cls._distance_to_km(payload["value"], payload["unit"]),
                        timestamp,
                    )
                }
                if payload.get("phevTotalValue") is not None:
                    values[EntityKey.COMBINED_DISTANCE_TO_EMPTY] = EntityValue(
                        cls._distance_to_km(
                            payload["phevTotalValue"], payload["phevTotalUnit"]
                        ),
                        timestamp,
                    )
                return values

            if endpoint is EndpointKey.ODOMETER:
                odometers = payload["odometers"]
                if not isinstance(odometers, list) or not odometers:
                    raise ValueError
                odometer = odometers[0]
                return {
                    EntityKey.ODOMETER: EntityValue(
                        cls._distance_to_km(odometer["value"], odometer["unit"]),
                        str(odometer.get("timestamp", "")) or None,
                    )
                }

            if endpoint is EndpointKey.EV_BATTERY:
                return {
                    EntityKey.EV_BATTERY_LEVEL: EntityValue(
                        float(payload["soc"]), cls._timestamp(payload)
                    )
                }

            if endpoint is EndpointKey.EV_CHARGING:
                timestamp = cls._timestamp(payload)
                plugin = int(payload["batteryPlugin"])
                values = {
                    EntityKey.CHARGING: EntityValue(
                        bool(payload["batteryCharge"]), timestamp
                    ),
                    EntityKey.CHARGING_CABLE_CONNECTED: EntityValue(
                        plugin > 0, timestamp
                    ),
                    EntityKey.CHARGER_TYPE: EntityValue(
                        CHARGER_TYPES.get(plugin, "unknown"), timestamp
                    ),
                }
                target_soc = payload.get("targetSOC")
                if (
                    isinstance(target_soc, dict)
                    and target_soc.get("targetSOClevel") is not None
                ):
                    values[EntityKey.TARGET_STATE_OF_CHARGE] = EntityValue(
                        float(target_soc["targetSOClevel"]), timestamp
                    )
                remain_time = payload.get("remainTime")
                if (
                    isinstance(remain_time, dict)
                    and remain_time.get("value") is not None
                ):
                    unit = int(remain_time["unit"])
                    values[EntityKey.REMAINING_CHARGING_TIME] = EntityValue(
                        float(remain_time["value"]) * TIME_TO_MINUTES[unit],
                        timestamp,
                    )
                return values

            entity_key = WARNING_ENTITY_KEYS[endpoint]
            return {entity_key: EntityValue(bool(payload["status"]))}
        except (KeyError, TypeError, ValueError, IndexError) as err:
            raise HyundaiKiaVehicleError(
                f"Vehicle API returned invalid {endpoint.value} data"
            ) from err

    @staticmethod
    def _distance_to_km(value: Any, unit: Any) -> float:
        """Convert a documented distance value to kilometres."""
        return float(value) * DISTANCE_TO_KM[int(unit)]

    @staticmethod
    def _timestamp(payload: dict[str, Any]) -> str | None:
        """Return an optional vehicle timestamp."""
        return str(payload.get("timestamp", "")) or None
