import json
from datetime import date

import pytest

import main as hydro_main
from config import Settings
from jev.client import IrrigationDecision
from jev.models import IrrigationContext


def _settings(ha_token: str = "") -> Settings:
    return Settings(
        ha_url="http://ha.local",
        ha_token=ha_token,
        typesafe_api_key="test-key",
        lawn_sowing_date=date(2026, 9, 26),
        dry_run=True,
    )


def _no_water_decision(context: IrrigationContext, api_key: str) -> IrrigationDecision:
    assert api_key == "test-key"
    return IrrigationDecision(sproeien_nu=False, probability=0.1, dryness_score=0.5)


def _unexpected_ha_client(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("Sample route must not construct an HA client")


def _context_builder_for(expected_client: object, context: IrrigationContext):
    def build_context_for(client: object, _settings: Settings) -> IrrigationContext:
        if client is not expected_client:
            raise AssertionError("Unexpected HA client")
        return context

    return build_context_for


def test_sample_runner_loads_json_without_creating_ha_client(monkeypatch, capsys) -> None:
    monkeypatch.setattr(hydro_main, "request_decision", _no_water_decision)
    monkeypatch.setattr(hydro_main, "HomeAssistantClient", _unexpected_ha_client)

    result = hydro_main.run_with_sample_json(settings=_settings())
    output = json.loads(capsys.readouterr().out)

    assert result.context.observed_at == "2026-10-04T12:00:00+02:00"
    assert output["source"] == "sample_json"
    assert output["pump_activated"] is False


def test_home_assistant_runner_uses_ha_context_builder(monkeypatch, capsys) -> None:
    sample_context = IrrigationContext.model_validate_json(hydro_main.DEFAULT_SAMPLE_PATH.read_text(encoding="utf-8"))
    expected_client = object()
    monkeypatch.setattr(hydro_main, "HomeAssistantClient", lambda *_args: expected_client)
    monkeypatch.setattr(hydro_main, "build_context", _context_builder_for(expected_client, sample_context))
    monkeypatch.setattr(hydro_main, "request_decision", _no_water_decision)

    result = hydro_main.run_with_home_assistant(settings=_settings(ha_token="test-ha-token"))
    output = json.loads(capsys.readouterr().out)

    assert result.context is sample_context
    assert output["source"] == "home_assistant"
    assert output["pump_activated"] is False


def test_home_assistant_runner_requires_ha_token() -> None:
    with pytest.raises(RuntimeError, match="HA_TOKEN"):
        hydro_main.run_with_home_assistant(settings=_settings())
