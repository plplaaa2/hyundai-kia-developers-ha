"""Constants for Hyundai Kia Developers."""

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "hyundai_kia_developers"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_ACCOUNT_ID = "account_id"
CONF_BRAND = "brand"
CONF_CAR_ID = "car_id"
CONF_CAR_NAME = "car_name"
CONF_CAR_TYPE = "car_type"
CONF_REDIRECT_URI = "redirect_uri"
CONF_REDIRECT_URL = "redirect_url"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_VEHICLE = "vehicle"

SUBENTRY_TYPE_VEHICLE = "vehicle"

DEFAULT_REDIRECT_URI = "https://example.com/redirect"
DEFAULT_SCAN_INTERVAL = 60
MIN_SCAN_INTERVAL = 30
MAX_SCAN_INTERVAL = 1440

TOKEN_REFRESH_MARGIN_SECONDS = 300
REQUEST_TIMEOUT_SECONDS = 30
MAX_PARALLEL_REQUESTS = 2


class Brand(StrEnum):
    """Supported vehicle brands."""

    HYUNDAI = "hyundai"
    KIA = "kia"


class VehicleType(StrEnum):
    """Vehicle types returned by the profile API."""

    COMBUSTION = "GN"
    ELECTRIC = "EV"
    HYBRID = "HEV"
    PLUG_IN_HYBRID = "PHEV"
    FUEL_CELL = "FCEV"


EV_VEHICLE_TYPES = frozenset({VehicleType.ELECTRIC, VehicleType.PLUG_IN_HYBRID})


class EndpointKey(StrEnum):
    """Independently polled vehicle API endpoints."""

    DISTANCE_TO_EMPTY = "distance_to_empty"
    ODOMETER = "odometer"
    EV_BATTERY = "ev_battery"
    EV_CHARGING = "ev_charging"
    LOW_FUEL_WARNING = "low_fuel_warning"
    TIRE_PRESSURE_WARNING = "tire_pressure_warning"
    LAMP_WIRE_WARNING = "lamp_wire_warning"
    SMART_KEY_BATTERY_WARNING = "smart_key_battery_warning"
    WASHER_FLUID_WARNING = "washer_fluid_warning"
    BRAKE_FLUID_WARNING = "brake_fluid_warning"
    ENGINE_OIL_WARNING = "engine_oil_warning"


class EntityKey(StrEnum):
    """Entity values produced by endpoint responses."""

    DISTANCE_TO_EMPTY = "distance_to_empty"
    ODOMETER = "odometer"
    COMBINED_DISTANCE_TO_EMPTY = "combined_distance_to_empty"
    EV_BATTERY_LEVEL = "ev_battery_level"
    CHARGING = "charging"
    CHARGING_CABLE_CONNECTED = "charging_cable_connected"
    CHARGER_TYPE = "charger_type"
    TARGET_STATE_OF_CHARGE = "target_state_of_charge"
    REMAINING_CHARGING_TIME = "remaining_charging_time"
    LOW_FUEL_WARNING = "low_fuel_warning"
    TIRE_PRESSURE_WARNING = "tire_pressure_warning"
    LAMP_WIRE_WARNING = "lamp_wire_warning"
    SMART_KEY_BATTERY_WARNING = "smart_key_battery_warning"
    WASHER_FLUID_WARNING = "washer_fluid_warning"
    BRAKE_FLUID_WARNING = "brake_fluid_warning"
    ENGINE_OIL_WARNING = "engine_oil_warning"


ENTITY_ENDPOINT: dict[EntityKey, EndpointKey] = {
    EntityKey.DISTANCE_TO_EMPTY: EndpointKey.DISTANCE_TO_EMPTY,
    EntityKey.COMBINED_DISTANCE_TO_EMPTY: EndpointKey.DISTANCE_TO_EMPTY,
    EntityKey.ODOMETER: EndpointKey.ODOMETER,
    EntityKey.EV_BATTERY_LEVEL: EndpointKey.EV_BATTERY,
    EntityKey.CHARGING: EndpointKey.EV_CHARGING,
    EntityKey.CHARGING_CABLE_CONNECTED: EndpointKey.EV_CHARGING,
    EntityKey.CHARGER_TYPE: EndpointKey.EV_CHARGING,
    EntityKey.TARGET_STATE_OF_CHARGE: EndpointKey.EV_CHARGING,
    EntityKey.REMAINING_CHARGING_TIME: EndpointKey.EV_CHARGING,
    EntityKey.LOW_FUEL_WARNING: EndpointKey.LOW_FUEL_WARNING,
    EntityKey.TIRE_PRESSURE_WARNING: EndpointKey.TIRE_PRESSURE_WARNING,
    EntityKey.LAMP_WIRE_WARNING: EndpointKey.LAMP_WIRE_WARNING,
    EntityKey.SMART_KEY_BATTERY_WARNING: EndpointKey.SMART_KEY_BATTERY_WARNING,
    EntityKey.WASHER_FLUID_WARNING: EndpointKey.WASHER_FLUID_WARNING,
    EntityKey.BRAKE_FLUID_WARNING: EndpointKey.BRAKE_FLUID_WARNING,
    EntityKey.ENGINE_OIL_WARNING: EndpointKey.ENGINE_OIL_WARNING,
}


ENDPOINT_ENTITIES: dict[EndpointKey, frozenset[EntityKey]] = {
    endpoint: frozenset(
        key for key, value in ENTITY_ENDPOINT.items() if value is endpoint
    )
    for endpoint in EndpointKey
}

CORE_ENTITY_KEYS = frozenset({EntityKey.DISTANCE_TO_EMPTY, EntityKey.ODOMETER})
EV_DEFAULT_ENTITY_KEYS = frozenset({EntityKey.EV_BATTERY_LEVEL, EntityKey.CHARGING})


@dataclass(frozen=True, slots=True)
class BrandEndpoints:
    """API endpoints for a vehicle brand."""

    auth_base: str
    vehicle_base: str

    @property
    def authorize_url(self) -> str:
        """Return the authorization URL."""
        return f"{self.auth_base}/api/v1/user/oauth2/authorize"

    @property
    def token_url(self) -> str:
        """Return the token URL."""
        return f"{self.auth_base}/api/v1/user/oauth2/token"


BRAND_ENDPOINTS: dict[Brand, BrandEndpoints] = {
    Brand.HYUNDAI: BrandEndpoints(
        auth_base="https://prd.kr-ccapi.hyundai.com",
        vehicle_base="https://dev.kr-ccapi.hyundai.com",
    ),
    Brand.KIA: BrandEndpoints(
        auth_base="https://prd.kr-ccapi.kia.com",
        vehicle_base="https://dev.kr-ccapi.kia.com",
    ),
}
