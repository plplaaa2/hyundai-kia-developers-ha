"""Tests for the Hyundai/Kia developer API client."""

import asyncio
from collections import defaultdict, deque
from typing import Any, cast

import pytest
from aiohttp import ClientSession

from custom_components.hyundai_kia_developers.api import (
    DISTANCE_TO_KM,
    TIME_TO_MINUTES,
    HyundaiKiaApiClient,
)
from custom_components.hyundai_kia_developers.const import (
    BRAND_ENDPOINTS,
    Brand,
    EndpointKey,
    EntityKey,
)
from custom_components.hyundai_kia_developers.exceptions import (
    HyundaiKiaAuthenticationError,
    HyundaiKiaVehicleError,
)


class FakeResponse:
    """Minimal aiohttp response used by the API client."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def json(self, *, content_type: str | None = None) -> dict[str, Any]:
        """Return the prepared JSON body."""
        return self._payload


class FakeSession:
    """Queue deterministic responses by method and URL."""

    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], deque[FakeResponse]] = defaultdict(deque)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def add(
        self,
        method: str,
        url: str,
        *,
        status: int = 200,
        payload: dict[str, Any],
    ) -> None:
        """Queue a response."""
        self._responses[(method, url)].append(FakeResponse(status, payload))

    async def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """Return the next POST response."""
        return self._request("POST", url, kwargs)

    async def get(self, url: str, **kwargs: Any) -> FakeResponse:
        """Return the next GET response."""
        return self._request("GET", url, kwargs)

    def _request(self, method: str, url: str, kwargs: dict[str, Any]) -> FakeResponse:
        """Record a request and pop its prepared response."""
        self.requests.append((method, url, kwargs))
        return self._responses[(method, url)].popleft()


def make_api(session: FakeSession, brand: Brand = Brand.KIA) -> HyundaiKiaApiClient:
    """Create a client and queue its initial token refresh."""
    session.add(
        "POST",
        BRAND_ENDPOINTS[brand].token_url,
        payload={
            "access_token": "access-1",
            "refresh_token": "refresh-2",
            "expires_in": 3600,
            "token_type": "Bearer",
        },
    )
    return HyundaiKiaApiClient(
        cast(ClientSession, session),
        brand,
        "client-id",
        "client-secret",
        "https://example.com/redirect",
        "refresh-1",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("brand", list(Brand))
async def test_vehicle_discovery_for_both_brands(brand: Brand) -> None:
    """Vehicle profiles parse identically for Hyundai and Kia."""
    session = FakeSession()
    api = make_api(session, brand)
    session.add(
        "GET",
        f"{BRAND_ENDPOINTS[brand].vehicle_base}/api/v1/car/profile/carlist",
        payload={
            "cars": [
                {
                    "carId": "car-1",
                    "carNickname": "Niro",
                    "carType": "HEV",
                    "carName": "DE",
                    "carSellname": "Niro",
                }
            ]
        },
    )

    vehicles = await api.async_get_vehicles()

    assert vehicles[0].car_id == "car-1"
    assert vehicles[0].car_type == "HEV"
    assert vehicles[0].suggested_name == "Niro"


@pytest.mark.asyncio
async def test_vehicle_discovery_4045_is_empty() -> None:
    """Provider no-data code 4045 becomes an empty vehicle list."""
    session = FakeSession()
    api = make_api(session)
    session.add(
        "GET",
        f"{BRAND_ENDPOINTS[Brand.KIA].vehicle_base}/api/v1/car/profile/carlist",
        status=404,
        payload={"errCode": "4045", "errMsg": "No data"},
    )

    assert await api.async_get_vehicles() == []


@pytest.mark.asyncio
async def test_malformed_vehicle_list_is_rejected() -> None:
    """Malformed discovery payloads never become selectable vehicles."""
    session = FakeSession()
    api = make_api(session)
    session.add(
        "GET",
        f"{BRAND_ENDPOINTS[Brand.KIA].vehicle_base}/api/v1/car/profile/carlist",
        payload={"cars": [{"carNickname": "Missing ID"}]},
    )

    with pytest.raises(HyundaiKiaVehicleError):
        await api.async_get_vehicles()


@pytest.mark.asyncio
async def test_refresh_rotation_and_core_metrics() -> None:
    """One refresh is shared while DTE and odometer normalize to kilometres."""
    session = FakeSession()
    rotations: list[str] = []
    session.add(
        "POST",
        BRAND_ENDPOINTS[Brand.KIA].token_url,
        payload={
            "access_token": "access-1",
            "refresh_token": "refresh-2",
            "expires_in": 3600,
        },
    )
    base = BRAND_ENDPOINTS[Brand.KIA].vehicle_base
    session.add(
        "GET",
        f"{base}/api/v1/car/status/car-1/dte",
        payload={"value": 100, "unit": 3, "timestamp": "20260719010000"},
    )
    session.add(
        "GET",
        f"{base}/api/v1/car/status/car-1/odometer",
        payload={"odometers": [{"value": 1000, "unit": 2}]},
    )
    api = HyundaiKiaApiClient(
        cast(ClientSession, session),
        Brand.KIA,
        "client-id",
        "client-secret",
        "https://example.com/redirect",
        "refresh-1",
        rotations.append,
    )

    dte, odometer = await asyncio.gather(
        api.async_get_endpoint("car-1", EndpointKey.DISTANCE_TO_EMPTY),
        api.async_get_endpoint("car-1", EndpointKey.ODOMETER),
    )

    assert dte[EntityKey.DISTANCE_TO_EMPTY].value == pytest.approx(160.9344)
    assert odometer[EntityKey.ODOMETER].value == 1
    assert rotations == ["refresh-2"]
    assert [method for method, _url, _kwargs in session.requests].count("POST") == 1


def test_phev_dte_and_charging_fan_out() -> None:
    """Shared endpoint payloads produce every related entity value once."""
    dte = HyundaiKiaApiClient._parse_endpoint(
        EndpointKey.DISTANCE_TO_EMPTY,
        {
            "value": 30,
            "unit": 1,
            "phevTotalValue": 80,
            "phevTotalUnit": 1,
        },
    )
    charging = HyundaiKiaApiClient._parse_endpoint(
        EndpointKey.EV_CHARGING,
        {
            "batteryPlugin": 1,
            "batteryCharge": True,
            "targetSOC": {"targetSOClevel": 80},
            "remainTime": {"value": 2, "unit": 0},
        },
    )

    assert dte[EntityKey.COMBINED_DISTANCE_TO_EMPTY].value == 80
    assert charging[EntityKey.CHARGING].value is True
    assert charging[EntityKey.CHARGING_CABLE_CONNECTED].value is True
    assert charging[EntityKey.CHARGER_TYPE].value == "fast"
    assert charging[EntityKey.TARGET_STATE_OF_CHARGE].value == 80
    assert charging[EntityKey.REMAINING_CHARGING_TIME].value == 120


@pytest.mark.parametrize(
    ("endpoint", "key"),
    [
        (EndpointKey.LOW_FUEL_WARNING, EntityKey.LOW_FUEL_WARNING),
        (EndpointKey.TIRE_PRESSURE_WARNING, EntityKey.TIRE_PRESSURE_WARNING),
        (EndpointKey.LAMP_WIRE_WARNING, EntityKey.LAMP_WIRE_WARNING),
        (
            EndpointKey.SMART_KEY_BATTERY_WARNING,
            EntityKey.SMART_KEY_BATTERY_WARNING,
        ),
        (EndpointKey.WASHER_FLUID_WARNING, EntityKey.WASHER_FLUID_WARNING),
        (EndpointKey.BRAKE_FLUID_WARNING, EntityKey.BRAKE_FLUID_WARNING),
        (EndpointKey.ENGINE_OIL_WARNING, EntityKey.ENGINE_OIL_WARNING),
    ],
)
def test_warning_payloads(endpoint: EndpointKey, key: EntityKey) -> None:
    """Every documented warning endpoint maps true to a problem state."""
    values = HyundaiKiaApiClient._parse_endpoint(endpoint, {"status": True})
    assert values[key].value is True


@pytest.mark.parametrize(("unit", "factor"), list(DISTANCE_TO_KM.items()))
def test_distance_unit_conversion(unit: int, factor: float) -> None:
    """Every documented distance unit converts to kilometres."""
    assert HyundaiKiaApiClient._distance_to_km(10, unit) == pytest.approx(10 * factor)


@pytest.mark.parametrize(("unit", "factor"), list(TIME_TO_MINUTES.items()))
def test_charging_time_unit_conversion(unit: int, factor: float) -> None:
    """Every documented duration unit converts to minutes."""
    values = HyundaiKiaApiClient._parse_endpoint(
        EndpointKey.EV_CHARGING,
        {
            "batteryPlugin": 0,
            "batteryCharge": False,
            "remainTime": {"value": 10, "unit": unit},
        },
    )
    assert values[EntityKey.REMAINING_CHARGING_TIME].value == pytest.approx(10 * factor)


@pytest.mark.asyncio
async def test_error_4002_requests_reauthentication() -> None:
    """Provider error 4002 is classified as an authentication failure."""
    session = FakeSession()
    session.add(
        "POST",
        BRAND_ENDPOINTS[Brand.HYUNDAI].token_url,
        status=400,
        payload={"resCode": "4002", "resMsg": "Invalid parameters"},
    )
    api = HyundaiKiaApiClient(
        cast(ClientSession, session),
        Brand.HYUNDAI,
        "client-id",
        "client-secret",
        "https://example.com/redirect",
        "expired-refresh-token",
    )

    with pytest.raises(HyundaiKiaAuthenticationError):
        await api.async_ensure_access_token()


@pytest.mark.asyncio
async def test_vehicle_api_4002_is_a_request_error() -> None:
    """Vehicle API 4002 follows its documented invalid-request meaning."""
    session = FakeSession()
    api = make_api(session)
    session.add(
        "GET",
        f"{BRAND_ENDPOINTS[Brand.KIA].vehicle_base}/api/v1/car/profile/carlist",
        payload={"resCode": "4002", "resMsg": "Invalid token"},
    )

    with pytest.raises(HyundaiKiaVehicleError):
        await api.async_get_vehicles()


@pytest.mark.asyncio
async def test_vehicle_api_session_error_requests_reauthentication() -> None:
    """Documented session failures start reauthentication."""
    session = FakeSession()
    api = make_api(session)
    session.add(
        "GET",
        f"{BRAND_ENDPOINTS[Brand.KIA].vehicle_base}/api/v1/car/profile/carlist",
        status=400,
        payload={"errCode": "4012", "errMsg": "Invalid session"},
    )

    with pytest.raises(HyundaiKiaAuthenticationError):
        await api.async_get_vehicles()
