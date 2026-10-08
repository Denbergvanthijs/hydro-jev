from datetime import UTC, datetime  # noqa: D100
from zoneinfo import ZoneInfo

import pytest

from irrigation.context import (
    _attributes,
    _duration_minutes,
    _forecast_items,
    _future_prices,
    _get_forecast,
    _normalize_datetime_string,
    _numeric_state,
    _weather_observations,
    _weather_values,
)

WEATHER_ENTITY = "weather.forecast_home"


class FailingForecastHA:
    """Home Assistant fake that raises for every operation."""

    def get_state(self, entity_id: str) -> dict[str, object]:
        """Raise when a state is requested."""
        raise RuntimeError(entity_id)

    def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, object]]]:
        """Raise when history is requested."""
        raise RuntimeError(f"{entity_id} from {start} to {end}")

    def get_weather_forecast(self, entity_id: str) -> dict[str, object]:
        """Raise when a forecast is requested."""
        raise RuntimeError(entity_id)


def test_failing_forecast_fake_rejects_all_operations() -> None:
    """Exercise all failure methods on the forecast fake."""
    ha = FailingForecastHA()
    with pytest.raises(RuntimeError):
        ha.get_state("sensor.test")
    with pytest.raises(RuntimeError):
        ha.get_history("sensor.test", datetime.now(UTC), datetime.now(UTC))
    with pytest.raises(RuntimeError):
        ha.get_weather_forecast("weather.test")


def test_context_helpers_handle_missing_values() -> None:  # noqa: D103
    missing: list[str] = []
    assert _attributes(None) == {}  # noqa: S101
    assert _attributes({"attributes": "invalid"}) == {}  # noqa: S101
    assert _numeric_state(None, "missing", missing) is None  # noqa: S101
    assert _numeric_state({"state": "not-a-number"}, "invalid", missing) is None  # noqa: S101
    assert _numeric_state({"state": "inf"}, "infinite", missing) is None  # noqa: S101
    assert len(missing) == 3  # noqa: PLR2004, S101

    for unit, expected in (("s", 2 / 60), ("h", 120), ("minutes", 2)):
        assert _duration_minutes(2, {"attributes": {"unit_of_measurement": unit}}, "duration", []) == expected  # noqa: S101
    duration_missing: list[str] = []
    assert _duration_minutes(2, {"attributes": {}}, "duration", duration_missing) is None  # noqa: S101
    assert duration_missing  # noqa: S101

    assert _weather_values(None)["condition"] is None  # noqa: S101
    assert _weather_observations([[{"state": "cloudy", "attributes": "invalid"}]])[0]["temperature"] is None  # noqa: S101
    assert (  # noqa: S101
        _weather_observations(
            [[{"last_changed": "2026-10-04T09:00:00+00:00", "state": "rainy", "attributes": {}}]],
            ZoneInfo("Europe/Amsterdam"),
        )[0]["observed_at"]
        == "2026-10-04T11:00:00+02:00"
    )
    assert _normalize_datetime_string("invalid", ZoneInfo("Europe/Amsterdam")) == "invalid"  # noqa: S101
    assert _normalize_datetime_string("2026-10-04T11:00:00", ZoneInfo("Europe/Amsterdam")) == "2026-10-04T11:00:00+02:00"  # noqa: S101


def test_forecast_and_price_helpers_filter_invalid_and_out_of_range_rows() -> None:  # noqa: D103
    now = datetime.fromisoformat("2026-10-04T12:00:00+02:00")
    missing: list[str] = []
    forecast = {
        "service_response": {
            WEATHER_ENTITY: {
                "forecast": [
                    "invalid",
                    {"datetime": "invalid"},
                    {"datetime": "2026-10-04T12:00:00"},
                    {"datetime": "2026-10-04T11:00:00+02:00"},
                    {"datetime": "2026-10-04T23:00:00+02:00", "condition": "rainy"},
                    {"datetime": "2026-10-04T13:00:00+02:00", "temperature": 20},
                ]
            }
        }
    }
    items = _forecast_items(forecast, WEATHER_ENTITY, now, missing, 12)
    assert [item["temperature"] for item in items] == [None, 20]  # noqa: S101
    assert len(missing) == 2  # noqa: PLR2004, S101
    assert _forecast_items({}, WEATHER_ENTITY, now, [], 12) == []  # noqa: S101
    normalized = _forecast_items(
        {WEATHER_ENTITY: {"forecast": [{"datetime": "2026-10-04T11:00:00+00:00"}]}},
        WEATHER_ENTITY,
        now,
        [],
        12,
        ZoneInfo("Europe/Amsterdam"),
    )
    assert normalized[0]["datetime"] == "2026-10-04T13:00:00+02:00"  # noqa: S101

    forecast_missing: list[str] = []
    assert (  # noqa: S101
        _get_forecast(
            FailingForecastHA(),
            WEATHER_ENTITY,
            forecast_missing,
        )
        == {}
    )
    assert forecast_missing == ["hourly weather forecast"]  # noqa: S101

    prices = [
        "invalid",
        {"from": "invalid"},
        {"from": "2026-10-04T13:00:00"},
        {"from": "2026-10-04T11:00:00+02:00", "price": 0.2},
        {"from": "2026-10-04T13:00:00+02:00", "value": "bad", "end": "2026-10-04T14:00:00+02:00"},
    ]
    price_missing: list[str] = []
    ha = FailingForecastHA()
    result = _future_prices(ha, "sensor.price", now, price_missing, state={"attributes": {"forecast": prices}})
    assert result == [  # noqa: S101
        {
            "datetime": "2026-10-04T13:00:00+02:00",
            "valid_until": "2026-10-04T14:00:00+02:00",
            "price_eur_kwh": None,
        }
    ]
    assert len(price_missing) == 2  # noqa: PLR2004, S101
    assert _future_prices(ha, None, now, []) == []  # noqa: S101
    assert _future_prices(ha, "sensor.price", now, [], state={"attributes": {}}) == []  # noqa: S101
    normalized_prices = _future_prices(
        ha,
        "sensor.price",
        now,
        [],
        state={
            "attributes": {
                "prices": [
                    {
                        "from": "2026-10-04T11:00:00+00:00",
                        "till": "2026-10-04T12:00:00+00:00",
                        "price": 0.2,
                    }
                ]
            }
        },
        target_timezone=ZoneInfo("Europe/Amsterdam"),
    )
    assert normalized_prices[0]["datetime"] == "2026-10-04T13:00:00+02:00"  # noqa: S101
    assert normalized_prices[0]["valid_until"] == "2026-10-04T14:00:00+02:00"  # noqa: S101
