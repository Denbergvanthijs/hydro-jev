from datetime import date, datetime, timedelta

import pytest

from config import Settings
from irrigation.context import build_context

PRICE_ENTITY = "sensor.frank_energie_prijzen_huidige_elektriciteitsprijs_all_in"


class IncompleteHA:
    def get_state(self, entity_id: str) -> dict[str, object]:
        if entity_id == "weather.forecast_home":
            return {
                "state": "sunny",
                "attributes": {"temperature": 18, "humidity": 60, "temperature_unit": "°C"},
            }
        raise RuntimeError("entity unavailable")

    def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, object]]]:
        raise RuntimeError("history unavailable")

    def get_weather_forecast(self, entity_id: str) -> dict[str, object]:
        return {}


def test_context_is_built_with_missing_home_assistant_data() -> None:
    settings = Settings(
        ha_url="http://ha.local:8123",
        ha_token="",
        typesafe_api_key="",
        lawn_sowing_date=date(2026, 9, 26),
        dry_run=True,
    )
    now = datetime.fromisoformat("2026-10-04T12:00:00+02:00")

    context = build_context(IncompleteHA(), settings, now)

    assert context.current_weather["condition"] == "sunny"
    assert context.current_weather["precipitation"] is None
    assert "apparent_temperature" not in context.current_weather
    assert "wind_gust_speed" not in context.current_weather
    assert "temperature_unit" not in context.current_weather
    assert "precipitation_unit" not in context.current_weather
    assert context.today_watering_minutes is None
    assert "history switch.athom_stekker_kantoor_switch" in context.missing_data
    assert "watering_sessions_reliable" not in context.model_dump()
    assert "pump_current_a" not in context.model_dump()


def test_context_labels_configured_history_window() -> None:
    class HistoryTrackingHA(IncompleteHA):
        def __init__(self) -> None:
            self.history_requests: list[tuple[datetime, datetime]] = []

        def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, object]]]:
            self.history_requests.append((start, end))
            return []

    settings = Settings(
        ha_url="http://ha.local:8123",
        ha_token="",
        typesafe_api_key="",
        lawn_sowing_date=date(2026, 9, 26),
        dry_run=True,
        history_hours=24,
    )
    ha = HistoryTrackingHA()
    now = datetime.fromisoformat("2026-10-04T12:00:00+02:00")

    context = build_context(ha, settings, now)

    assert context.history_hours == 24
    assert context.weather_observations == []
    assert context.watering_sessions == []
    assert ha.history_requests == [(now - timedelta(hours=24), now)] * 2


def test_context_labels_configured_forecast_window() -> None:
    class ForecastHA(IncompleteHA):
        def get_weather_forecast(self, entity_id: str) -> dict[str, object]:
            return {
                entity_id: {
                    "forecast": [
                        {"datetime": "2026-10-05T00:00:00+02:00", "condition": "cloudy", "precipitation": 0},
                        {"datetime": "2026-10-05T12:00:00+02:00", "condition": "rainy", "precipitation": 2.5},
                    ]
                }
            }

    settings = Settings(
        ha_url="http://ha.local:8123",
        ha_token="",
        typesafe_api_key="",
        lawn_sowing_date=date(2026, 9, 26),
        dry_run=True,
        forecast_hours=24,
    )
    now = datetime.fromisoformat("2026-10-04T12:00:00+02:00")

    context = build_context(ForecastHA(), settings, now)

    assert context.forecast_hours == 24
    assert [item["datetime"] for item in context.weather_forecast] == [
        "2026-10-05T00:00:00+02:00",
        "2026-10-05T12:00:00+02:00",
    ]
    assert [item["condition"] for item in context.weather_forecast] == ["cloudy", "rainy"]
    assert [item["precipitation"] for item in context.weather_forecast] == [0, 2.5]


def test_context_includes_precipitation_in_weather_observations() -> None:
    class ObservedWeatherHA(IncompleteHA):
        def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, object]]]:
            if entity_id == "weather.forecast_home":
                return [
                    [
                        {
                            "last_changed": "2026-10-04T11:00:00+02:00",
                            "state": "rainy",
                            "attributes": {"temperature": 17, "precipitation": 1.2},
                        }
                    ]
                ]
            return []

    settings = Settings(
        ha_url="http://ha.local:8123",
        ha_token="",
        typesafe_api_key="",
        lawn_sowing_date=date(2026, 9, 26),
        dry_run=True,
    )

    context = build_context(
        ObservedWeatherHA(),
        settings,
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert context.weather_observations == [
        {
            "observed_at": "2026-10-04T11:00:00+02:00",
            "condition": "rainy",
            "temperature": 17,
            "humidity": None,
            "dew_point": None,
            "cloud_coverage": None,
            "uv_index": None,
            "wind_speed": None,
            "precipitation": 1.2,
        }
    ]


class FrankPriceHA(IncompleteHA):
    def __init__(self) -> None:
        self.price_state_reads = 0
        self.duration_state_reads = 0

    def get_state(self, entity_id: str) -> dict[str, object]:
        if entity_id == PRICE_ENTITY:
            self.price_state_reads += 1
            return {
                "state": "0.41331",
                "attributes": {
                    "unit_of_measurement": "EUR/kWh",
                    "prices": [
                        {
                            "from": "2026-10-04T11:00:00+02:00",
                            "price": 0.41331,
                            "till": "2026-10-04T12:00:00+02:00",
                        },
                        {
                            "from": "2026-10-04T13:00:00+02:00",
                            "price": 0.39,
                            "till": "2026-10-04T14:00:00+02:00",
                        },
                    ],
                },
            }
        if entity_id in {
            "sensor.hydrofoor_inschakelduur_vandaag",
            "sensor.hydrofoor_inschakelduur_deze_week",
        }:
            self.duration_state_reads += 1
            value = "0.26" if entity_id.endswith("vandaag") else "1.24"
            return {"state": value, "attributes": {"unit_of_measurement": "h"}}
        energy_values = {
            "sensor.athom_stekker_kantoor_energy": "0.876739",
            "sensor.hydrofoor_verbruik_vandaag": "0.213601",
            "sensor.hydrofoor_verbruik_deze_week": "0.497557",
        }
        if entity_id in energy_values:
            return {"state": energy_values[entity_id], "attributes": {"unit_of_measurement": "kWh"}}
        return super().get_state(entity_id)


def test_same_frank_entity_provides_current_and_future_prices() -> None:
    settings = Settings(
        ha_url="http://ha.local",
        ha_token="",
        typesafe_api_key="",
        lawn_sowing_date=date(2026, 9, 26),
        dry_run=True,
        ha_price_entity_id=PRICE_ENTITY,
        ha_price_forecast_entity_id=PRICE_ENTITY,
    )
    ha = FrankPriceHA()
    now = datetime.fromisoformat("2026-10-04T12:00:00+02:00")

    context = build_context(ha, settings, now)

    assert context.current_electricity_price_eur_kwh == 0.413
    assert context.today_watering_minutes == pytest.approx(15.6)
    assert context.watering_minutes_week == pytest.approx(74.4)
    assert context.cumulative_energy_kwh == 0.877
    assert context.energy_kwh_today == 0.214
    assert context.energy_kwh_week == 0.498
    assert "pump_current_a" not in context.model_dump()
    assert context.future_electricity_prices == [
        {
            "datetime": "2026-10-04T13:00:00+02:00",
            "valid_until": "2026-10-04T14:00:00+02:00",
            "price_eur_kwh": 0.39,
        }
    ]
    assert ha.price_state_reads == 1
    assert ha.duration_state_reads == 2
