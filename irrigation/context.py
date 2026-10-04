from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Protocol

from config import FORECAST_HOURS, HISTORY_HOURS, Settings
from ha.history import extract_watering_sessions
from jev.models import IrrigationContext

PUMP_ENTITY = "switch.athom_stekker_kantoor_switch"
WEATHER_ENTITY = "weather.forecast_home"
STATE_ENTITIES = {
    "pump_current_a": "sensor.athom_stekker_kantoor_current",
    "pump_power_w": "sensor.athom_stekker_kantoor_power",
    "cumulative_energy_kwh": "sensor.athom_stekker_kantoor_energy",
    "watering_events_today": "sensor.hydrofoor_inschakelingen_vandaag",
    "watering_events_week": "sensor.hydrofoor_inschakelingen_deze_week",
    "today_watering_minutes": "sensor.hydrofoor_inschakelduur_vandaag",
    "watering_minutes_week": "sensor.hydrofoor_inschakelduur_deze_week",
    "energy_kwh_today": "sensor.hydrofoor_verbruik_vandaag",
    "energy_kwh_week": "sensor.hydrofoor_verbruik_deze_week",
}
WEATHER_FIELDS = (
    "temperature",
    "humidity",
    "precipitation",
    "apparent_temperature",
    "dew_point",
    "cloud_coverage",
    "uv_index",
    "wind_speed",
    "wind_gust_speed",
)


class HAReader(Protocol):
    def get_state(self, entity_id: str) -> dict[str, Any]: ...

    def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, Any]]]: ...

    def get_weather_forecast(self, entity_id: str) -> dict[str, Any]: ...


def build_context(ha: HAReader, settings: Settings, now: datetime | None = None) -> IrrigationContext:
    now = now or datetime.now().astimezone()
    start = now - timedelta(hours=HISTORY_HOURS)
    missing: list[str] = []

    pump_state = _read_state(ha, PUMP_ENTITY, missing)
    weather_state = _read_state(ha, WEATHER_ENTITY, missing)
    history, pump_history_available = _read_history(ha, PUMP_ENTITY, start, now, missing)
    weather_history, _ = _read_history(ha, WEATHER_ENTITY, start, now, missing)
    sessions = extract_watering_sessions(history, now)
    stats: dict[str, float | None] = {}
    for field, entity_id in STATE_ENTITIES.items():
        raw = _read_state(ha, entity_id, missing)
        stats[field] = _numeric_state(raw, entity_id, missing)

    today_minutes = stats["today_watering_minutes"]
    if today_minutes is not None:
        unit = str(_attributes(_read_state(ha, STATE_ENTITIES["today_watering_minutes"], missing)).get("unit_of_measurement", "")).lower()
        if unit in {"s", "sec", "second", "seconds"}:
            today_minutes /= 60
        elif unit in {"h", "hr", "hour", "hours"}:
            today_minutes *= 60
        elif unit not in {"min", "minute", "minutes"}:
            missing.append("unit sensor.hydrofoor_inschakelduur_vandaag (daglimiet)")
            today_minutes = None

    forecast = _get_forecast(ha, missing)
    current_weather = _weather_values(weather_state)
    weather_observations = _weather_observations(weather_history)
    forecast_items = _forecast_items(forecast, now, missing)
    current_price = None
    if settings.ha_price_entity_id:
        price_state = _read_state(ha, settings.ha_price_entity_id, missing)
        current_price = _numeric_state(price_state, settings.ha_price_entity_id, missing)
    else:
        missing.append("HA_PRICE_ENTITY_ID (actuele elektriciteitsprijs)")

    future_prices = _future_prices(ha, settings.ha_price_forecast_entity_id, now, missing)
    missing.append("totale neerslag laatste 12 uur (geen betrouwbare aggregatie beschikbaar)")

    return IrrigationContext(
        observed_at=now.isoformat(),
        lawn={
            "area_m2": 45,
            "sprinkler_count": 2,
            "sowing_date": settings.lawn_sowing_date.isoformat(),
            "age_days": max((now.date() - settings.lawn_sowing_date).days, 0),
        },
        current_weather=current_weather,
        weather_observations_last_12h=weather_observations,
        forecast_next_12h=forecast_items,
        recent_rainfall_mm=None,
        watering_sessions_last_12h=[item.model_dump(mode="json") for item in sessions],
        watering_sessions_reliable=pump_history_available and all(item.reliable for item in sessions),
        pump_state=str(pump_state.get("state")) if pump_state else None,
        today_watering_minutes=today_minutes,
        current_electricity_price_eur_kwh=current_price,
        future_electricity_prices=future_prices,
        missing_data=sorted(set(missing)),
        **{key: value for key, value in stats.items() if key != "today_watering_minutes"},
    )


def _attributes(state: dict[str, Any] | None) -> dict[str, Any]:
    attributes = state.get("attributes") if state else None
    return attributes if isinstance(attributes, dict) else {}


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


def _weather_values(state: dict[str, Any] | None) -> dict[str, object | None]:
    attributes = _attributes(state)
    return {
        "condition": state.get("state") if state else None,
        **{field: attributes.get(field) for field in WEATHER_FIELDS},
        "temperature_unit": attributes.get("temperature_unit"),
        "precipitation_unit": attributes.get("precipitation_unit"),
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


def _forecast_items(forecast: dict[str, Any], now: datetime, missing: list[str]) -> list[dict[str, object | None]]:
    response = forecast.get("service_response", forecast)
    entity_data = response.get(WEATHER_ENTITY) if isinstance(response, dict) else None
    rows = entity_data.get("forecast") if isinstance(entity_data, dict) else None
    if not isinstance(rows, list):
        return []
    limit = now + timedelta(hours=FORECAST_HOURS)
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


def _future_prices(ha: HAReader, entity_id: str | None, now: datetime, missing: list[str]) -> list[dict[str, object | None]]:
    if not entity_id:
        missing.append("HA_PRICE_FORECAST_ENTITY_ID (toekomstige elektriciteitsprijzen)")
        return []
    state = _read_state(ha, entity_id, missing)
    attributes = _attributes(state)
    values = attributes.get("prices", attributes.get("forecast"))
    if not isinstance(values, list):
        missing.append(f"bruikbare prijsverwachting {entity_id}")
        return []
    result: list[dict[str, object | None]] = []
    limit = now + timedelta(hours=FORECAST_HOURS)
    for value in values:
        if isinstance(value, dict):
            raw_datetime = value.get("datetime", value.get("start", value.get("time")))
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
                    "price_eur_kwh": value.get("price", value.get("value")),
                }
            )
    return result
