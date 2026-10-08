"""Application settings loaded from environment variables."""

from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SESSION_DURATION_DECIMAL_PLACES = 2
MEASUREMENT_DECIMAL_PLACES = 3
LOG_DECIMAL_PLACES = 2
MIN_SCORE = 0
ZERO_MINUTES = 0
MAX_PROBABILITY = 1
MAX_DRYNESS_SCORE = 4
LIGHT_DRYNESS_SCORE = 1
MODERATE_DRYNESS_SCORE = 2
HIGH_DRYNESS_SCORE = 3
DEFAULT_MAX_MINUTES_PER_DAY = 20
DEFAULT_HISTORY_HOURS = 12
DEFAULT_FORECAST_HOURS = 12


class Settings(BaseSettings):
    """Validated runtime configuration for the irrigation application."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", frozen=True)

    ha_url: str = "http://192.168.1.101"
    ha_token: str = ""
    typesafe_api_key: str = ""
    ha_timeout_seconds: float = 10.0
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
    lawn_area_m2: int = 45
    sprinkler_count: int = 2
    max_minutes_per_day: int = DEFAULT_MAX_MINUTES_PER_DAY
    watering_minutes: int = 5
    max_electricity_price_eur_kwh: float = 0.70
    history_hours: int = DEFAULT_HISTORY_HOURS
    forecast_hours: int = DEFAULT_FORECAST_HOURS

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
