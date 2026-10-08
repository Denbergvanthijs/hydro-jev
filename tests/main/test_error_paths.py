from datetime import datetime
from pathlib import Path

import pytest

import main
from config import Settings
from irrigation.context import build_context
from jev.models import IrrigationContext


def _sample_context() -> IrrigationContext:
    return IrrigationContext.model_validate_json(
        (Path(__file__).parents[2] / "data" / "sample_context.json").read_text(encoding="utf-8")
    )


def test_main_error_and_cli_paths(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    with pytest.raises(ValueError, match="failed"), main._log_step("failing step"):  # noqa: SLF001
        raise ValueError("failed")
    assert "Stap mislukt" in caplog.text

    settings = Settings(typesafe_api_key="key", ha_token="token", ha_price_entity_id=None, ha_price_forecast_entity_id=None)
    monkeypatch.setattr(main, "HomeAssistantClient", lambda *_: object())
    monkeypatch.setattr(main, "build_context", lambda *_: _sample_context())
    monkeypatch.setattr(main, "request_decision", lambda *_: None)
    result = main.run_with_home_assistant(settings)
    assert result.decision is None

    monkeypatch.setattr(main, "request_decision", lambda *_: (_ for _ in ()).throw(RuntimeError("jev failed")))
    failed_result = main.run_context(_sample_context(), settings)
    assert failed_result.decision is None

    with pytest.raises(RuntimeError, match="TYPESAFE_API_KEY"):
        main._require_typesafe_key(Settings(typesafe_api_key=""))  # noqa: SLF001

    class MissingPriceHA:
        def get_state(self, entity_id: str) -> dict[str, object]:
            if entity_id == "weather.forecast_home":
                return {"state": "sunny", "attributes": {}}
            raise RuntimeError("missing")

        def get_history(self, *_: object) -> list[list[dict[str, object]]]:
            raise RuntimeError("missing")

        def get_weather_forecast(self, _: str) -> dict[str, object]:
            return {}

    missing_price_context = build_context(
        MissingPriceHA(),
        Settings(ha_price_entity_id=None, ha_price_forecast_entity_id=None),
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )
    assert "HA_PRICE_ENTITY_ID (actuele elektriciteitsprijs)" in missing_price_context.missing_data

    monkeypatch.setattr(main, "run_with_sample_json", lambda path=None: None)
    main.main(["--source", "sample"])
    monkeypatch.setattr(main, "run_with_home_assistant", lambda: None)
    main.main(["--source", "ha"])
