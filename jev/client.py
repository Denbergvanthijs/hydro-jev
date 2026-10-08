"""Request and validate irrigation decisions from the TypeSafe service."""

import logging
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field
from typesafe_sdk import (
    Choice,
    ChoiceAnswer,
    Score,
    ScoreAnswer,
    SystemOneResponse,
    TypeSafeClient,
)

from config import (
    HIGH_DRYNESS_SCORE,
    LIGHT_DRYNESS_SCORE,
    MAX_DRYNESS_SCORE,
    MAX_PROBABILITY,
    MIN_SCORE,
    MODERATE_DRYNESS_SCORE,
    Settings,
)
from jev.models import IrrigationContext

logger = logging.getLogger("hydro_jev.jev")


class IrrigationDecision(BaseModel):
    """Validated decision fields returned by Jev."""

    model_config = ConfigDict(extra="forbid", strict=True)

    sproeien_nu: bool
    probability: float = Field(ge=MIN_SCORE, le=MAX_PROBABILITY)
    dryness_score: float = Field(ge=MIN_SCORE, le=MAX_DRYNESS_SCORE)


class JevResponse(SystemOneResponse):
    """Schema for the structured TypeSafe response."""

    sproeien_nu: ChoiceAnswer
    droogte_inschatting: ScoreAnswer


def request_decision(context: IrrigationContext, settings: Settings) -> IrrigationDecision:
    """Ask Jev for a decision based on the supplied irrigation context."""
    started = perf_counter()
    logger.info("TypeSafe-verzoek gestart: irrigatiebeslissing")
    try:
        with TypeSafeClient(api_key=settings.typesafe_api_key) as client:
            result = client.system_one(
                state=context.model_dump(mode="json"),
                questions={
                    "sproeien_nu": Choice(
                        instructions=(
                            f"Beslis uitsluitend of dit gazon NU voor precies {settings.watering_minutes} minuten gesproeid "
                            "moet worden. Weeg recente sproeisessies en regen zwaar mee; uitgestelde "
                            "regen kan wachten rechtvaardigen, en felle directe zon kan sproeien "
                            "onwenselijk maken. Het gazon is pas ingezaaid, dus regelmatige vochtigheid "
                            f"is belangrijk. Beschouw elektriciteitsprijs boven "
                            f"EUR {settings.max_electricity_price_eur_kwh:.2f}/kWh als normaal "
                            "extreem duur, maar negeer dat zelf bij extreme droogte. Je bepaalt zelf "
                            "de droogte op basis van alle context. Ontbrekende gegevens zijn onbekend, "
                            "niet nul. Geef ja-kans als probability."
                        ),
                        criteria={
                            "sproeien": f"NU precies {settings.watering_minutes} minuten sproeien",
                            "niet_sproeien": "NU niet sproeien",
                        },
                    ),
                    "droogte_inschatting": Score(
                        instructions=f"Schat de droogte voor dit gazon in van {MIN_SCORE} tot en met {MAX_DRYNESS_SCORE}.",
                        criteria=[
                            f"{MIN_SCORE}: niet droog",
                            f"{LIGHT_DRYNESS_SCORE}: licht droog",
                            f"{MODERATE_DRYNESS_SCORE}: matig droog",
                            f"{HIGH_DRYNESS_SCORE}: erg droog",
                            f"{MAX_DRYNESS_SCORE}: extreem droog",
                        ],
                    ),
                },
                response_model=JevResponse,
            )
    except Exception as error:
        logger.error("TypeSafe-verzoek mislukt na %.2f s (%s)", perf_counter() - started, type(error).__name__)
        raise

    choice = result.sproeien_nu.choice
    if choice not in {"sproeien", "niet_sproeien"}:
        raise ValueError("Jev returned an unknown irrigation choice")
    decision = IrrigationDecision(
        sproeien_nu=choice == "sproeien",
        probability=result.sproeien_nu.probabilities["sproeien"],
        dryness_score=result.droogte_inschatting.score,
    )
    logger.info("TypeSafe-verzoek gereed (%.2f s)", perf_counter() - started)
    return decision
