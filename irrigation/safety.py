import math
from dataclasses import dataclass

from config import MAX_MINUTES_PER_DAY
from jev.client import IrrigationDecision


@dataclass(frozen=True)
class SafetyResult:
    requested: bool
    approved: bool
    minutes: int
    intervention: str | None


def apply_safety(
    decision: IrrigationDecision | None,
    today_minutes: float | None,
    requested_minutes: int,
) -> SafetyResult:
    if decision is None or not _valid_decision(decision):
        return SafetyResult(False, False, 0, "Ongeldige of ontbrekende Jev-beslissing.")
    if not decision.sproeien_nu:
        return SafetyResult(False, False, 0, None)
    if requested_minutes <= 0 or requested_minutes > 5:
        return SafetyResult(True, False, 0, "Ongeldige of onrealistische sproeiduur.")
    if today_minutes is None or not math.isfinite(today_minutes) or today_minutes < 0:
        return SafetyResult(True, False, 0, "Dagduur onbekend of ongeldig; daglimiet niet veilig te controleren.")
    if today_minutes + requested_minutes > MAX_MINUTES_PER_DAY:
        return SafetyResult(True, False, 0, "Daglimiet van 20 minuten zou worden overschreden.")
    return SafetyResult(True, True, requested_minutes, None)


def _valid_decision(decision: IrrigationDecision) -> bool:
    return (
        isinstance(decision.sproeien_nu, bool)
        and math.isfinite(decision.probability)
        and 0 <= decision.probability <= 1
        and math.isfinite(decision.dryness_score)
        and 0 <= decision.dryness_score <= 4
    )
