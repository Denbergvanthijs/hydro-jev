from datetime import date

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True)

    ha_url: str = "http://192.168.1.101"
    ha_token: str = ""
    typesafe_api_key: str = ""
    lawn_sowing_date: date = date(2026, 9, 26)
    dry_run: bool = True
    ha_price_entity_id: str | None = None
    ha_price_forecast_entity_id: str | None = None
    max_minutes_per_day: int = 20
    watering_minutes: int = 5
    history_hours: int = 12
    forecast_hours: int = 12

    @field_validator("ha_url")
    @classmethod
    def _strip_trailing_slash(cls, value: str) -> str:
        return value.rstrip("/")

    @field_validator("ha_price_entity_id", "ha_price_forecast_entity_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return value or None
