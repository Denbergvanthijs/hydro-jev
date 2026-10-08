"""Build Jev's irrigation context from Home Assistant data."""

import math
from datetime import datetime, timedelta
from typing import Any, Protocol

from config import Settings
from ha.history import extract_watering_sessions
from jev.models import IrrigationContext

PUMP_ENTITY = "switch.athom_stekker_kantoor_switch"
WEATHER_ENTITY = "weather.forecast_home"
WEATHER_FIELDS = (
    "temperature",
    "humidity",
    "dew_point",
    "cloud_coverage",
    "uv_index",
    "wind_speed",
    "precipitation",
)
KWH_FIELDS = {"cumulative_energy_kwh", "energy_kwh_today", "energy_kwh_week"}


class HAReader(Protocol):
    """Home Assistant operations required by the context builder."""

    def get_state(self, entity_id: str) -> dict[str, Any]:
        """Return the current state of an entity."""
        ...

    def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, Any]]]:
        """Return an entity's state history for a time interval."""
        ...

    def get_weather_forecast(self, entity_id: str) -> dict[str, Any]:
        """Return the forecast payload for a weather entity."""
        ...


def build_context(ha: HAReader, settings: Settings, now: datetime | None = None) -> IrrigationContext:
    """Fetch sensor data and assemble a normalized irrigation context."""
    now = now or datetime.now().astimezone()
    start = now - timedelta(hours=settings.history_hours)
    missing: list[str] = []

    pump_state = _read_state(ha, PUMP_ENTITY, missing)
    weather_state = _read_state(ha, WEATHER_ENTITY, missing)
    history, _ = _read_history(ha, PUMP_ENTITY, start, now, missing)
    weather_history, _ = _read_history(ha, WEATHER_ENTITY, start, now, missing)
    sessions = extract_watering_sessions(history, now)
    stats: dict[str, float | None] = {}
    states: dict[str, dict[str, Any] | None] = {}
    state_entities = _state_entities(settings)
    for field, entity_id in state_entities.items():
        raw = _read_state(ha, entity_id, missing)
        states[field] = raw
        stats[field] = _numeric_state(raw, entity_id, missing)

    today_minutes = _duration_minutes(
        stats["today_watering_minutes"],
        states["today_watering_minutes"],
        state_entities["today_watering_minutes"],
        missing,
    )
    stats["watering_minutes_week"] = _duration_minutes(
        stats["watering_minutes_week"],
        states["watering_minutes_week"],
        state_entities["watering_minutes_week"],
        missing,
    )
    if stats["watering_minutes_week"] is not None:
        stats["watering_minutes_week"] = round(stats["watering_minutes_week"], 2)
    if today_minutes is not None:
        today_minutes = round(today_minutes, 2)
    for field in KWH_FIELDS:
        value = stats[field]
        if value is not None:
            stats[field] = round(value, 3)

    forecast = _get_forecast(ha, missing)
    current_weather = _weather_values(weather_state)
    weather_observations = _weather_observations(weather_history)
    forecast_items = _forecast_items(forecast, now, missing, settings.forecast_hours)
    current_price = None
    price_state = None
    if settings.ha_price_entity_id:
        price_state = _read_state(ha, settings.ha_price_entity_id, missing)
        current_price = _numeric_state(price_state, settings.ha_price_entity_id, missing)
    else:
        missing.append("HA_PRICE_ENTITY_ID (actuele elektriciteitsprijs)")

    future_price_state = price_state if settings.ha_price_forecast_entity_id == settings.ha_price_entity_id else None
    future_prices = _future_prices(
        ha,
        settings.ha_price_forecast_entity_id,
        now,
        missing,
        state=future_price_state,
        forecast_hours=settings.forecast_hours,
    )
    return IrrigationContext(
        observed_at=now.isoformat(),
        history_hours=settings.history_hours,
        forecast_hours=settings.forecast_hours,
        lawn={
            "area_m2": 45,
            "sprinkler_count": 2,
            "sowing_date": settings.lawn_sowing_date.isoformat(),
            "age_days": max((now.date() - settings.lawn_sowing_date).days, 0),
        },
        current_weather=current_weather,
        weather_observations=weather_observations,
        weather_forecast=forecast_items,
        watering_sessions=[
            {
                **item.model_dump(mode="json"),
                "duration_minutes": round(item.duration_minutes, 2) if item.duration_minutes is not None else None,
            }
            for item in sessions
        ],
        pump_state=str(pump_state.get("state")) if pump_state else None,
        today_watering_minutes=today_minutes,
        current_electricity_price_eur_kwh=round(current_price, 3) if current_price is not None else None,
        future_electricity_prices=future_prices,
        missing_data=sorted(set(missing)),
        **{key: value for key, value in stats.items() if key not in {"today_watering_minutes", "pump_current_a"}},
    )


def _attributes(state: dict[str, Any] | None) -> dict[str, Any]:
    attributes = state.get("attributes") if state else None
    return attributes if isinstance(attributes, dict) else {}


def _state_entities(settings: Settings) -> dict[str, str]:
    return {
        "pump_power_w": settings.ha_pump_power_entity_id,
        "cumulative_energy_kwh": settings.ha_cumulative_energy_entity_id,
        "watering_events_today": settings.ha_watering_events_today_entity_id,
        "watering_events_week": settings.ha_watering_events_week_entity_id,
        "today_watering_minutes": settings.ha_today_watering_minutes_entity_id,
        "watering_minutes_week": settings.ha_watering_minutes_week_entity_id,
        "energy_kwh_today": settings.ha_energy_kwh_today_entity_id,
        "energy_kwh_week": settings.ha_energy_kwh_week_entity_id,
    }


def _read_state(ha: HAReader, entity_id: str, missing: list[str]) -> dict[str, Any] | None:
    try:
        return ha.get_state(entity_id)
    except Exception:
        missing.append(entity_id)
        return None


def _read_history(
    ha: HAReader,
    entity_id: str,
    start: datetime,
    end: datetime,
    missing: list[str],
) -> tuple[list[list[dict[str, Any]]], bool]:
    try:
        return ha.get_history(entity_id, start, end), True
    except Exception:
        missing.append(f"history {entity_id}")
        return [], False


def _numeric_state(state: dict[str, Any] | None, entity_id: str, missing: list[str]) -> float | None:
    try:
        value = float(state["state"]) if state else None
    except (KeyError, TypeError, ValueError):
        value = None
    if value is None or not math.isfinite(value):
        missing.append(entity_id)
        return None
    return value


def _duration_minutes(value: float | None, state: dict[str, Any] | None, entity_id: str, missing: list[str]) -> float | None:
    if value is None:
        return None
    unit = str(_attributes(state).get("unit_of_measurement", "")).strip().lower()
    if unit in {"s", "sec", "second", "seconds"}:
        return value / 60
    if unit in {"h", "hr", "hour", "hours"}:
        return value * 60
    if unit in {"min", "minute", "minutes"}:
        return value
    missing.append(f"unit {entity_id} (duur in minuten)")
    return None


def _weather_values(state: dict[str, Any] | None) -> dict[str, object | None]:
    attributes = _attributes(state)
    return {
        "condition": state.get("state") if state else None,
        **{field: attributes.get(field) for field in WEATHER_FIELDS},
    }


def _weather_observations(history: list[list[dict[str, Any]]]) -> list[dict[str, object | None]]:
    observations: list[dict[str, object | None]] = []
    for group in history:
        for record in group:
            attributes = record.get("attributes")
            attributes = attributes if isinstance(attributes, dict) else {}
            observations.append(
                {
                    "observed_at": record.get("last_changed"),
                    "condition": record.get("state"),
                    **{field: attributes.get(field) for field in WEATHER_FIELDS},
                }
            )
    return observations


def _get_forecast(ha: HAReader, missing: list[str]) -> dict[str, Any]:
    try:
        return ha.get_weather_forecast(WEATHER_ENTITY)
    except Exception:
        missing.append("hourly weather forecast")
        return {}


def _forecast_items(forecast: dict[str, Any], now: datetime, missing: list[str], forecast_hours: int) -> list[dict[str, object | None]]:
    response = forecast.get("service_response", forecast)
    entity_data = response.get(WEATHER_ENTITY) if isinstance(response, dict) else None
    rows = entity_data.get("forecast") if isinstance(entity_data, dict) else None
    if not isinstance(rows, list):
        return []
    limit = now + timedelta(hours=forecast_hours)
    result: list[dict[str, object | None]] = []
    fields = ("datetime", "condition", *WEATHER_FIELDS)
    for row in rows:
        if not isinstance(row, dict):
            continue
        at = row.get("datetime")
        try:
            forecast_at = datetime.fromisoformat(at) if isinstance(at, str) else None
        except ValueError:
            forecast_at = None
        if forecast_at is None or forecast_at.tzinfo is None or now.tzinfo is None:
            missing.append("forecasttijdstip ontbreekt of heeft geen tijdzone")
            continue
        if forecast_at < now or forecast_at > limit:
            continue
        result.append({field: row.get(field) for field in fields})
    return result


def _future_prices(
    ha: HAReader,
    entity_id: str | None,
    now: datetime,
    missing: list[str],
    state: dict[str, Any] | None = None,
    forecast_hours: int = 12,
) -> list[dict[str, object | None]]:
    if not entity_id:
        missing.append("HA_PRICE_FORECAST_ENTITY_ID (toekomstige elektriciteitsprijzen)")
        return []
    if state is None:
        state = _read_state(ha, entity_id, missing)
    attributes = _attributes(state)
    values = attributes.get("prices", attributes.get("forecast"))
    if not isinstance(values, list):
        missing.append(f"bruikbare prijsverwachting {entity_id}")
        return []
    result: list[dict[str, object | None]] = []
    limit = now + timedelta(hours=forecast_hours)
    for value in values:
        if isinstance(value, dict):
            raw_datetime = value.get("datetime", value.get("from", value.get("start", value.get("time"))))
            try:
                price_time = datetime.fromisoformat(raw_datetime) if isinstance(raw_datetime, str) else None
            except ValueError:
                price_time = None
            if price_time is None or price_time.tzinfo is None or now.tzinfo is None:
                missing.append(f"tijdstip ontbreekt in prijsverwachting {entity_id}")
                continue
            if price_time < now or price_time > limit:
                continue
            result.append(
                {
                    "datetime": raw_datetime,
                    "valid_until": value.get("till", value.get("end")),
                    "price_eur_kwh": _round_optional(value.get("price", value.get("value")), 3),
                }
            )
    return result


def _round_optional(value: Any, digits: int) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return round(number, digits) if math.isfinite(number) else None
