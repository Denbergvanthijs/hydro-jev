from datetime import datetime
from types import SimpleNamespace

from irrigation.context import (
    WEATHER_ENTITY,
    _attributes,
    _duration_minutes,
    _forecast_items,
    _future_prices,
    _get_forecast,
    _numeric_state,
    _weather_observations,
    _weather_values,
)


def test_context_helpers_handle_missing_values() -> None:
    missing: list[str] = []
    assert _attributes(None) == {}
    assert _attributes({"attributes": "invalid"}) == {}
    assert _numeric_state(None, "missing", missing) is None
    assert _numeric_state({"state": "not-a-number"}, "invalid", missing) is None
    assert _numeric_state({"state": "inf"}, "infinite", missing) is None
    assert len(missing) == 3

    for unit, expected in (("s", 2 / 60), ("h", 120), ("minutes", 2)):
        assert _duration_minutes(2, {"attributes": {"unit_of_measurement": unit}}, "duration", []) == expected
    duration_missing: list[str] = []
    assert _duration_minutes(2, {"attributes": {}}, "duration", duration_missing) is None
    assert duration_missing

    assert _weather_values(None)["condition"] is None
    assert _weather_observations([[{"state": "cloudy", "attributes": "invalid"}]])[0]["temperature"] is None


def test_forecast_and_price_helpers_filter_invalid_and_out_of_range_rows() -> None:
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
    items = _forecast_items(forecast, now, missing, 12)
    assert [item["temperature"] for item in items] == [None, 20]
    assert len(missing) == 2
    assert _forecast_items({}, now, [], 12) == []

    forecast_missing: list[str] = []
    assert _get_forecast(
        SimpleNamespace(get_weather_forecast=lambda _: (_ for _ in ()).throw(RuntimeError("unavailable"))),
        forecast_missing,
    ) == {}
    assert forecast_missing == ["hourly weather forecast"]

    prices = [
        "invalid",
        {"from": "invalid"},
        {"from": "2026-10-04T13:00:00"},
        {"from": "2026-10-04T11:00:00+02:00", "price": 0.2},
        {"from": "2026-10-04T13:00:00+02:00", "value": "bad", "end": "2026-10-04T14:00:00+02:00"},
    ]
    price_missing: list[str] = []
    result = _future_prices(None, "sensor.price", now, price_missing, state={"attributes": {"forecast": prices}})
    assert result == [
        {
            "datetime": "2026-10-04T13:00:00+02:00",
            "valid_until": "2026-10-04T14:00:00+02:00",
            "price_eur_kwh": None,
        }
    ]
    assert len(price_missing) == 2
    assert _future_prices(None, None, now, []) == []
    assert _future_prices(None, "sensor.price", now, [], state={"attributes": {}}) == []
