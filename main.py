from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter

from config import WATERING_MINUTES, Settings
from ha.client import HomeAssistantClient
from irrigation.context import build_context
from irrigation.safety import apply_safety
from jev.client import IrrigationDecision, request_decision

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hydro_jev")


@contextmanager
def _log_step(name: str) -> Iterator[None]:
    started = perf_counter()
    logger.info("Stap gestart: %s", name)
    try:
        yield
    except Exception:
        logger.exception("Stap mislukt: %s (na %.2f s)", name, perf_counter() - started)
        raise
    else:
        logger.info("Stap gereed: %s (%.2f s)", name, perf_counter() - started)


def main() -> None:
    run_started = perf_counter()
    logger.info("Hydro-Jev gestart")
    with _log_step("configuratie laden"):
        settings = Settings.from_environment()
    if not settings.ha_token or not settings.typesafe_api_key:
        raise RuntimeError("Vul HA_TOKEN en TYPESAFE_API_KEY in .env in.")

    ha = HomeAssistantClient(settings.ha_url, settings.ha_token)
    with _log_step("Home Assistant-context ophalen en opbouwen"):
        context = build_context(ha, settings)
    logger.info(
        "HA-context:\n%s",
        json.dumps(context.model_dump(mode="json"), ensure_ascii=False, indent=2),
    )

    try:
        with _log_step("Jev-beslissing opvragen"):
            decision: IrrigationDecision | None = request_decision(context, settings.typesafe_api_key)
    except Exception as error:
        logger.error("Jev-aanroep mislukt; veilig niet sproeien (%s).", type(error).__name__)
        decision = None

    with _log_step("veiligheidscontroles uitvoeren"):
        safety = apply_safety(decision, context.today_watering_minutes, WATERING_MINUTES)
    dryness = decision.dryness_score if decision else None
    probability = decision.probability if decision else None
    logger.info(
        "Besluit: jev_sproeien_nu=%s probability=%s droogte_score=%s "
        "veiligheidsinterventie=%s safety_goedgekeurd=%s duur_minuten=%s dry_run=%s "
        "pomp_geactiveerd=false",
        decision.sproeien_nu if decision else False,
        probability,
        dryness,
        safety.intervention,
        safety.approved,
        safety.minutes,
        settings.dry_run,
    )
    with _log_step("resultaat tonen"):
        print(
            json.dumps(
                {
                    "jev_decision": decision.model_dump() if decision else None,
                    "safety": safety.__dict__,
                    "dry_run": settings.dry_run,
                    "pump_activated": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    logger.info("Hydro-Jev afgerond (totale duur %.2f s)", perf_counter() - run_started)


if __name__ == "__main__":
    main()
