"""Data models for Hyundai Kia Developers."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

from .const import EntityKey

if TYPE_CHECKING:
    from .api import HyundaiKiaApiClient
    from .coordinator import HyundaiKiaDataUpdateCoordinator


@dataclass(frozen=True, slots=True)
class TokenResponse:
    """OAuth token response."""

    access_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str = "Bearer"


@dataclass(frozen=True, slots=True)
class VehicleProfile:
    """One vehicle returned by the account profile endpoint."""

    car_id: str
    nickname: str
    car_type: str
    model_code: str
    sales_model: str

    @property
    def suggested_name(self) -> str:
        """Return the best user-facing vehicle name available."""
        return self.nickname or self.sales_model or self.model_code or "Vehicle"


type VehicleStateValue = float | bool | str


@dataclass(frozen=True, slots=True)
class EntityValue:
    """One entity value returned by a vehicle endpoint."""

    value: VehicleStateValue
    timestamp: str | None = None


@dataclass(frozen=True, slots=True)
class EntityResult:
    """One coordinator entity result."""

    key: EntityKey
    value: EntityValue | None
    error: str | None = None


@dataclass(slots=True)
class HyundaiKiaRuntimeData:
    """Runtime data attached to a config entry."""

    api: "HyundaiKiaApiClient"
    coordinator: "HyundaiKiaDataUpdateCoordinator"
    vehicle_profiles: dict[str, VehicleProfile]
    subentry_snapshot: tuple[tuple[str, str, str], ...]


type HyundaiKiaConfigEntry = ConfigEntry[HyundaiKiaRuntimeData]
