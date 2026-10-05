"""Apply deterministic safety constraints to Jev's irrigation decision."""

import math
from dataclasses import dataclass

from jev.client import IrrigationDecision

MAX_REQUESTED_MINUTES = 5
MAX_DRYNESS_SCORE = 4


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
    requested_minutes: int,
    max_minutes_per_day: int = 20,
) -> SafetyResult:
    """Approve a valid watering request only when the daily limit allows it."""
    if decision is None or not _valid_decision(decision):
        return SafetyResult(requested=False, approved=False, minutes=0, intervention="Ongeldige of ontbrekende Jev-beslissing.")
    if not decision.sproeien_nu:
        return SafetyResult(requested=False, approved=False, minutes=0, intervention=None)
    if requested_minutes <= 0 or requested_minutes > MAX_REQUESTED_MINUTES:
        return SafetyResult(requested=True, approved=False, minutes=0, intervention="Ongeldige of onrealistische sproeiduur.")
    if today_minutes is None or not math.isfinite(today_minutes) or today_minutes < 0:
        return SafetyResult(
            requested=True,
            approved=False,
            minutes=0,
            intervention="Dagduur onbekend of ongeldig; daglimiet niet veilig te controleren.",
        )
    if today_minutes + requested_minutes > max_minutes_per_day:
        return SafetyResult(
            requested=True,
            approved=False,
            minutes=0,
            intervention=f"Daglimiet van {max_minutes_per_day} minuten zou worden overschreden.",
        )
    return SafetyResult(requested=True, approved=True, minutes=requested_minutes, intervention=None)


def _valid_decision(decision: IrrigationDecision) -> bool:
    return (
        isinstance(decision.sproeien_nu, bool)
        and math.isfinite(decision.probability)
        and 0 <= decision.probability <= 1
        and math.isfinite(decision.dryness_score)
        and 0 <= decision.dryness_score <= MAX_DRYNESS_SCORE
    )
