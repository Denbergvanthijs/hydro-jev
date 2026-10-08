from irrigation.safety import apply_safety  # noqa: D100
from jev.client import IrrigationDecision


def _decision(should_water: bool = True) -> IrrigationDecision:  # noqa: FBT001, FBT002
    return IrrigationDecision(sproeien_nu=should_water, probability=0.9, dryness_score=3)


def test_no_recent_watering_and_safe_daily_total_allows_advice() -> None:  # noqa: D103
    result = apply_safety(_decision(), today_minutes=0, requested_minutes=5)

    assert result.approved  # noqa: S101
    assert result.minutes == 5  # noqa: PLR2004, S101


def test_daily_limit_blocks_watering() -> None:  # noqa: D103
    result = apply_safety(_decision(), today_minutes=16, requested_minutes=5)

    assert not result.approved  # noqa: S101
    assert "Daglimiet" in (result.intervention or "")  # noqa: S101


def test_invalid_or_missing_jev_decision_fails_closed() -> None:  # noqa: D103
    assert not apply_safety(None, today_minutes=0, requested_minutes=5).approved  # noqa: S101
    assert not apply_safety(_decision(), today_minutes=0, requested_minutes=-1).approved  # noqa: S101
    assert not apply_safety(_decision(), today_minutes=0, requested_minutes=99).approved  # noqa: S101


def test_unknown_daily_duration_fails_closed_for_yes_decision() -> None:  # noqa: D103
    result = apply_safety(_decision(), today_minutes=None, requested_minutes=5)

    assert not result.approved  # noqa: S101
    assert "onbekend" in (result.intervention or "")  # noqa: S101


def test_no_water_decision_is_not_overridden_by_safety() -> None:  # noqa: D103
    result = apply_safety(_decision(False), today_minutes=0, requested_minutes=5)  # noqa: FBT003

    assert not result.approved  # noqa: S101
    assert result.intervention is None  # noqa: S101
