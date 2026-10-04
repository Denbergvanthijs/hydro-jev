from datetime import date, datetime

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
    assert context.today_watering_minutes is None
    assert not context.watering_sessions_reliable
    assert "history switch.athom_stekker_kantoor_switch" in context.missing_data
    assert context.recent_rainfall_mm is None


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

    assert context.current_electricity_price_eur_kwh == 0.41331
    assert context.today_watering_minutes == pytest.approx(15.6)
    assert context.watering_minutes_week == pytest.approx(74.4)
    assert context.future_electricity_prices == [
        {
            "datetime": "2026-10-04T13:00:00+02:00",
            "valid_until": "2026-10-04T14:00:00+02:00",
            "price_eur_kwh": 0.39,
        }
    ]
    assert ha.price_state_reads == 1
    assert ha.duration_state_reads == 2
