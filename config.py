import os
from dataclasses import dataclass
from datetime import date
from typing import Self

from dotenv import load_dotenv

MAX_MINUTES_PER_DAY = 20
WATERING_MINUTES = 5
HISTORY_HOURS = 12
FORECAST_HOURS = 12


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    ha_url: str
    ha_token: str
    typesafe_api_key: str
    lawn_sowing_date: date
    dry_run: bool
    ha_price_entity_id: str | None = None
    ha_price_forecast_entity_id: str | None = None

    @classmethod
    def from_environment(cls) -> Self:
        load_dotenv()
        sowing_date = date.fromisoformat(os.getenv("LAWN_SOWING_DATE", "2026-09-26"))
        return cls(
            ha_url=os.getenv("HA_URL", "http://192.168.1.101").rstrip("/"),
            ha_token=os.getenv("HA_TOKEN", ""),
            typesafe_api_key=os.getenv("TYPESAFE_API_KEY", ""),
            lawn_sowing_date=sowing_date,
            dry_run=_env_bool("DRY_RUN", True),
            ha_price_entity_id=os.getenv("HA_PRICE_ENTITY_ID") or None,
            ha_price_forecast_entity_id=os.getenv("HA_PRICE_FORECAST_ENTITY_ID") or None,
        )
