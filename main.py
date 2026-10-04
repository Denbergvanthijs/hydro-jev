from __future__ import annotations

import json
import logging

from config import WATERING_MINUTES, Settings
from ha.client import HomeAssistantClient
from irrigation.context import build_context
from irrigation.safety import apply_safety
from jev.client import IrrigationDecision, request_decision

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hydro_jev")


def main() -> None:
    settings = Settings.from_environment()
    if not settings.ha_token or not settings.typesafe_api_key:
        raise RuntimeError("Vul HA_TOKEN en TYPESAFE_API_KEY in .env in.")

    ha = HomeAssistantClient(settings.ha_url, settings.ha_token)
    context = build_context(ha, settings)
    logger.info("Context: %s", json.dumps(context.model_dump(mode="json"), ensure_ascii=True))

    try:
        decision: IrrigationDecision | None = request_decision(context, settings.typesafe_api_key)
        reason = "Jev-beslissing op basis van de verstrekte context."
    except Exception as error:
        logger.exception("Jev-aanroep mislukt; veilig niet sproeien: %s", type(error).__name__)
        decision = None
        reason = "Jev-beslissing ontbreekt of kon niet gevalideerd worden."

    safety = apply_safety(decision, context.today_watering_minutes, WATERING_MINUTES)
    dryness = decision.dryness_score if decision else None
    probability = decision.probability if decision else None
    logger.info(
        "Besluit: jev_sproeien_nu=%s probability=%s droogte_score=%s reden=%s "
        "veiligheidsinterventie=%s safety_goedgekeurd=%s duur_minuten=%s dry_run=%s "
        "pomp_geactiveerd=false",
        decision.sproeien_nu if decision else False,
        probability,
        dryness,
        reason,
        safety.intervention,
        safety.approved,
        safety.minutes,
        settings.dry_run,
    )
    print(
        json.dumps(
            {
                "jev_decision": decision.model_dump() if decision else None,
                "safety": safety.__dict__,
                "dry_run": settings.dry_run,
                "pump_activated": False,
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
