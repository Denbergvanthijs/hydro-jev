from pathlib import Path  # noqa: D100
from types import SimpleNamespace
from typing import Self

import pytest

from config import Settings
from jev import client as jev_client
from jev.models import IrrigationContext


def _sample_context() -> IrrigationContext:
    return IrrigationContext.model_validate_json((Path(__file__).parents[2] / "data" / "sample_context.json").read_text(encoding="utf-8"))


def test_jev_request_success_and_invalid_choice(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: D103
    class FakeClient:
        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def system_one(self, **_: object) -> object:
            return SimpleNamespace(
                sproeien_nu=SimpleNamespace(choice="sproeien", probabilities={"sproeien": 0.75}),
                droogte_inschatting=SimpleNamespace(score=3),
            )

    monkeypatch.setattr(jev_client, "TypeSafeClient", FakeClient)
    settings = Settings(typesafe_api_key="key")
    decision = jev_client.request_decision(_sample_context(), settings)
    assert decision.sproeien_nu is True  # noqa: S101
    assert decision.probability == 0.75  # noqa: PLR2004, S101

    class InvalidClient(FakeClient):
        def system_one(self, **_: object) -> object:
            return SimpleNamespace(
                sproeien_nu=SimpleNamespace(choice="unknown", probabilities={}),
                droogte_inschatting=SimpleNamespace(score=3),
            )

    monkeypatch.setattr(jev_client, "TypeSafeClient", InvalidClient)
    with pytest.raises(ValueError, match="unknown"):
        jev_client.request_decision(_sample_context(), Settings(typesafe_api_key="key"))


def test_jev_request_reraises_client_error(monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: D103
    class FailingClient:
        def __init__(self, **_: object) -> None:
            raise RuntimeError("service unavailable")

    monkeypatch.setattr(jev_client, "TypeSafeClient", FailingClient)
    with pytest.raises(RuntimeError, match="service unavailable"):
        jev_client.request_decision(_sample_context(), Settings(typesafe_api_key="key"))
