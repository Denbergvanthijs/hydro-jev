"""Pydantic models shared with the irrigation decision service."""

from pydantic import BaseModel, ConfigDict, Field


class IrrigationContext(BaseModel):
    """Normalized sensor data and watering history supplied to Jev."""

    model_config = ConfigDict(extra="forbid")

    observed_at: str
    history_hours: int
    forecast_hours: int
    lawn: dict[str, int | float | str]
    current_weather: dict[str, object | None]
    weather_observations: list[dict[str, object | None]]
    weather_forecast: list[dict[str, object | None]]
    watering_sessions: list[dict[str, object | None]]
    pump_state: str | None = None
    today_watering_minutes: float | None = None
    watering_events_today: float | None = None
    watering_events_week: float | None = None
    watering_minutes_week: float | None = None
    energy_kwh_today: float | None = None
    energy_kwh_week: float | None = None
    pump_power_w: float | None = None
    cumulative_energy_kwh: float | None = None
    current_electricity_price_eur_kwh: float | None = None
    future_electricity_prices: list[dict[str, object | None]] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
