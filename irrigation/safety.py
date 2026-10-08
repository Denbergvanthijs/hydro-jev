"""Apply deterministic safety constraints to Jev's irrigation decision."""

import math
from dataclasses import dataclass

from config import (
    MAX_DRYNESS_SCORE,
    MAX_PROBABILITY,
    MIN_SCORE,
    ZERO_MINUTES,
    Settings,
)
from jev.client import IrrigationDecision


@dataclass(frozen=True)
class SafetyResult:
    """The outcome of applying safety limits to a watering request."""

    requested: bool
    approved: bool
    minutes: int
    intervention: str | None


def apply_safety(
    decision: IrrigationDecision | None,
    today_minutes: float | None,
    settings: Settings,
) -> SafetyResult:
    """Approve a valid watering request only when the daily limit allows it."""
    requested_minutes = settings.watering_minutes
    max_minutes_per_day = settings.max_minutes_per_day
    if decision is None or not _valid_decision(decision):
        return SafetyResult(requested=False, approved=False, minutes=ZERO_MINUTES, intervention="Ongeldige of ontbrekende Jev-beslissing.")
    if not decision.sproeien_nu:
        return SafetyResult(requested=False, approved=False, minutes=ZERO_MINUTES, intervention=None)
    if requested_minutes <= MIN_SCORE or requested_minutes > max_minutes_per_day:
        return SafetyResult(
            requested=True,
            approved=False,
            minutes=ZERO_MINUTES,
            intervention="Ongeldige of onrealistische sproeiduur.",
        )
    if today_minutes is None or not math.isfinite(today_minutes) or today_minutes < MIN_SCORE:
        return SafetyResult(
            requested=True,
            approved=False,
            minutes=ZERO_MINUTES,
            intervention="Dagduur onbekend of ongeldig; daglimiet niet veilig te controleren.",
        )
    if today_minutes + requested_minutes > max_minutes_per_day:
        return SafetyResult(
            requested=True,
            approved=False,
            minutes=ZERO_MINUTES,
            intervention=f"Daglimiet van {max_minutes_per_day} minuten zou worden overschreden.",
        )
    return SafetyResult(requested=True, approved=True, minutes=requested_minutes, intervention=None)


def _valid_decision(decision: IrrigationDecision) -> bool:
    return (
        isinstance(decision.sproeien_nu, bool)
        and math.isfinite(decision.probability)
        and MIN_SCORE <= decision.probability <= MAX_PROBABILITY
        and math.isfinite(decision.dryness_score)
        and MIN_SCORE <= decision.dryness_score <= MAX_DRYNESS_SCORE
    )
