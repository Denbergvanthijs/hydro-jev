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

from jev.models import IrrigationContext

logger = logging.getLogger("hydro_jev.jev")


class IrrigationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sproeien_nu: bool
    probability: float = Field(ge=0, le=1)
    dryness_score: float = Field(ge=0, le=4)


class JevResponse(SystemOneResponse):
    sproeien_nu: ChoiceAnswer
    droogte_inschatting: ScoreAnswer


def request_decision(context: IrrigationContext, api_key: str) -> IrrigationDecision:
    started = perf_counter()
    logger.info("TypeSafe-verzoek gestart: irrigatiebeslissing")
    try:
        with TypeSafeClient(api_key=api_key) as client:
            result = client.system_one(
                state=context.model_dump(mode="json"),
                questions={
                    "sproeien_nu": Choice(
                        instructions=(
                            "Beslis uitsluitend of dit gazon NU voor precies 5 minuten gesproeid "
                            "moet worden. Weeg recente sproeisessies en regen zwaar mee; uitgestelde "
                            "regen kan wachten rechtvaardigen, en felle directe zon kan sproeien "
                            "onwenselijk maken. Het gazon is pas ingezaaid, dus regelmatige vochtigheid "
                            "is belangrijk. Beschouw elektriciteitsprijs boven EUR 0,70/kWh als normaal "
                            "extreem duur, maar negeer dat zelf bij extreme droogte. Je bepaalt zelf "
                            "de droogte op basis van alle context. Ontbrekende gegevens zijn onbekend, "
                            "niet nul. Geef ja-kans als probability."
                        ),
                        criteria={
                            "sproeien": "NU precies 5 minuten sproeien",
                            "niet_sproeien": "NU niet sproeien",
                        },
                    ),
                    "droogte_inschatting": Score(
                        instructions="Schat de droogte voor dit gazon in van 0 tot en met 4.",
                        criteria=[
                            "0: niet droog",
                            "1: licht droog",
                            "2: matig droog",
                            "3: erg droog",
                            "4: extreem droog",
                        ],
                    ),
                },
                response_model=JevResponse,
            )
    except Exception as error:
        logger.error(f"TypeSafe-verzoek mislukt na {perf_counter() - started:.2f} s ({type(error).__name__})")
        raise

    choice = result.sproeien_nu.choice
    if choice not in {"sproeien", "niet_sproeien"}:
        raise ValueError("Jev returned an unknown irrigation choice")
    decision = IrrigationDecision(
        sproeien_nu=choice == "sproeien",
        probability=result.sproeien_nu.probabilities["sproeien"],
        dryness_score=result.droogte_inschatting.score,
    )
    logger.info(f"TypeSafe-verzoek gereed ({perf_counter() - started:.2f} s)")
    return decision
