"""Command-line entry point for the Hydro-Jev irrigation pipeline."""

import argparse
import json
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from config import Settings
from ha.client import HomeAssistantClient
from irrigation.context import build_context
from irrigation.safety import SafetyResult, apply_safety
from jev.client import IrrigationDecision, request_decision
from jev.models import IrrigationContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("hydro_jev")
DEFAULT_SAMPLE_PATH = Path(__file__).parent / "data" / "sample_context.json"


@dataclass(frozen=True)
class RunResult:
    """Context, decision, and safety outcome produced by one pipeline run."""

    context: IrrigationContext
    decision: IrrigationDecision | None
    safety: SafetyResult


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


def run_with_home_assistant(settings: Settings | None = None) -> RunResult:
    """Fetch live Home Assistant context, then run the shared decision pipeline."""
    run_started = perf_counter()
    with _log_step("configuratie laden"):
        settings = settings or Settings()
    _require_typesafe_key(settings)
    if not settings.ha_token:
        raise RuntimeError("Vul HA_TOKEN in .env in om Home Assistant te gebruiken.")

    ha = HomeAssistantClient(settings.ha_url, settings.ha_token)
    with _log_step("Home Assistant-context ophalen en opbouwen"):
        context = build_context(ha, settings)
    return run_context(context, settings, source="home_assistant", run_started=run_started)


def run_with_sample_json(
    sample_path: Path = DEFAULT_SAMPLE_PATH,
    settings: Settings | None = None,
) -> RunResult:
    """Load a saved context JSON file, then run the shared decision pipeline."""
    run_started = perf_counter()
    with _log_step("configuratie laden"):
        settings = settings or Settings()
    _require_typesafe_key(settings)
    with _log_step(f"sample-context laden: {sample_path}"):
        context = IrrigationContext.model_validate_json(sample_path.read_text(encoding="utf-8"))
    return run_context(context, settings, source="sample_json", run_started=run_started)


def run_context(
    context: IrrigationContext,
    settings: Settings,
    source: str = "provided_context",
    run_started: float | None = None,
) -> RunResult:
    """Ask Jev and apply safety checks to an already-built context."""
    run_started = run_started or perf_counter()
    logger.info("Contextbron: %s", source)
    logger.info("Irrigation-context:\n%s", json.dumps(context.model_dump(mode="json"), ensure_ascii=False, indent=2))

    try:
        with _log_step("Jev-beslissing opvragen"):
            decision: IrrigationDecision | None = request_decision(context, settings.typesafe_api_key)
    except Exception as error:
        logger.error("Jev-aanroep mislukt; veilig niet sproeien (%s).", type(error).__name__)
        decision = None

    with _log_step("veiligheidscontroles uitvoeren"):
        safety = apply_safety(decision, context.today_watering_minutes, settings.watering_minutes, settings.max_minutes_per_day)
    dryness = decision.dryness_score if decision else None
    probability = decision.probability if decision else None
    logger.info(
        "Besluit: jev_sproeien_nu=%s probability=%s droogte_score=%s "
        "veiligheidsinterventie=%s safety_goedgekeurd=%s duur_minuten=%s dry_run=%s pomp_geactiveerd=false",
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
                    "source": source,
                    "jev_decision": decision.model_dump() if decision else None,
                    "safety": asdict(safety),
                    "dry_run": settings.dry_run,
                    "pump_activated": False,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    logger.info("Hydro-Jev afgerond (totale duur %.2f s)", perf_counter() - run_started)
    return RunResult(context=context, decision=decision, safety=safety)


def _require_typesafe_key(settings: Settings) -> None:
    if not settings.typesafe_api_key:
        raise RuntimeError("Vul TYPESAFE_API_KEY in .env in om Jev te gebruiken.")


def main(argv: Sequence[str] | None = None) -> None:
    """Parse command-line arguments and run the selected input pipeline."""
    parser = argparse.ArgumentParser(description="Run hydro-jev using HA or saved sample context.")
    parser.add_argument("--source", choices=("ha", "sample"), default="ha")
    parser.add_argument("--sample-file", type=Path, default=DEFAULT_SAMPLE_PATH)
    args = parser.parse_args(argv)

    logger.info("Hydro-Jev gestart")
    if args.source == "sample":
        run_with_sample_json(args.sample_file)
    else:
        run_with_home_assistant()


if __name__ == "__main__":
    main()
