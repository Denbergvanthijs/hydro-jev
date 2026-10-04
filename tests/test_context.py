from datetime import date, datetime

from config import Settings
from irrigation.context import build_context


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
