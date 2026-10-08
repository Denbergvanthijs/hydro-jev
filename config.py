"""Application settings loaded from environment variables."""

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration for the irrigation application."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True)

    ha_url: str = "http://192.168.1.101"
    ha_token: str = ""
    typesafe_api_key: str = ""
    timezone: str = "Europe/Amsterdam"
    lawn_sowing_date: date = date(2026, 9, 26)
    dry_run: bool = True
    ha_pump_entity_id: str = "switch.athom_stekker_kantoor_switch"
    ha_weather_entity_id: str = "weather.forecast_home"
    ha_pump_power_entity_id: str = "sensor.athom_stekker_kantoor_power"
    ha_cumulative_energy_entity_id: str = "sensor.athom_stekker_kantoor_energy"
    ha_watering_events_today_entity_id: str = "sensor.hydrofoor_inschakelingen_vandaag"
    ha_watering_events_week_entity_id: str = "sensor.hydrofoor_inschakelingen_deze_week"
    ha_today_watering_minutes_entity_id: str = "sensor.hydrofoor_inschakelduur_vandaag"
    ha_watering_minutes_week_entity_id: str = "sensor.hydrofoor_inschakelduur_deze_week"
    ha_energy_kwh_today_entity_id: str = "sensor.hydrofoor_verbruik_vandaag"
    ha_energy_kwh_week_entity_id: str = "sensor.hydrofoor_verbruik_deze_week"
    sample_context_path: Path = Path(__file__).parent / "data" / "sample_context.json"
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

    @field_validator("timezone")
    @classmethod
    def _validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (TypeError, ZoneInfoNotFoundError) as error:
            raise ValueError(f"Onbekende tijdzone: {value}") from error
        return value

    @field_validator("ha_price_entity_id", "ha_price_forecast_entity_id", mode="before")
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        return value or None
