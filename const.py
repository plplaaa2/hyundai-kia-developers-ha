"""Constants for Hyundai Kia Developers."""

from dataclasses import dataclass
from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "hyundai_kia_developers"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

CONF_ACCOUNT_ID = "account_id"
CONF_BRAND = "brand"
CONF_CAR_ID = "car_id"
CONF_CAR_NAME = "car_name"
CONF_CAR_MODEL = "car_model"
CONF_CAR_TYPE = "car_type"
CONF_ANDROID_AUTO_ENTITY = "android_auto_entity"
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

VEHICLE_TYPE_LABELS: dict[str, str] = {
    VehicleType.COMBUSTION: "내연기관",
    VehicleType.ELECTRIC: "전기",
    VehicleType.HYBRID: "하이브리드",
    VehicleType.PLUG_IN_HYBRID: "플러그인하이브리드",
    VehicleType.FUEL_CELL: "수소전기",
}


def vehicle_type_label(value: str) -> str:
    """Return a localized vehicle type label."""
    normalized = value.strip().upper()
    return VEHICLE_TYPE_LABELS.get(normalized, normalized or "알 수 없음")


class EndpointKey(StrEnum):
    """Independently polled vehicle API endpoints."""

    DISTANCE_TO_EMPTY = "distance_to_empty"
    ODOMETER = "odometer"
    EV_BATTERY = "ev_battery"
    EV_CHARGING = "ev_charging"
    CONNECTED_SERVICE_CONTRACT = "connected_service_contract"
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
    VEHICLE_TYPE = "vehicle_type"
    MODEL_NAME = "model_name"
    CONNECTED_SERVICE_SUBSCRIBE_DATE = "connected_service_subscribe_date"
    CONNECTED_SERVICE_END_DATE = "connected_service_end_date"
    CONNECTED_SERVICE_END_D_DAY = "connected_service_end_d_day"
    LAST_SENSOR_VALUE_SENT_AT = "last_sensor_value_sent_at"
    ERROR_MESSAGE = "error_message"
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
    EntityKey.CONNECTED_SERVICE_SUBSCRIBE_DATE: EndpointKey.CONNECTED_SERVICE_CONTRACT,
    EntityKey.CONNECTED_SERVICE_END_DATE: EndpointKey.CONNECTED_SERVICE_CONTRACT,
    EntityKey.CONNECTED_SERVICE_END_D_DAY: EndpointKey.CONNECTED_SERVICE_CONTRACT,
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
STATIC_ENTITY_KEYS = frozenset(
    {
        EntityKey.VEHICLE_TYPE,
        EntityKey.MODEL_NAME,
        EntityKey.LAST_SENSOR_VALUE_SENT_AT,
    }
)


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
