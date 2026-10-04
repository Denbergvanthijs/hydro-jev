import argparse
import json
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

from config import WATERING_MINUTES, Settings
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
    context: IrrigationContext
    decision: IrrigationDecision | None
    safety: SafetyResult


@contextmanager
def _log_step(name: str) -> Iterator[None]:
    started = perf_counter()
    logger.info(f"Stap gestart: {name}")
    try:
        yield
    except Exception:
        logger.exception(f"Stap mislukt: {name} (na {perf_counter() - started:.2f} s)")
        raise
    else:
        logger.info(f"Stap gereed: {name} ({perf_counter() - started:.2f} s)")


def run_with_home_assistant(settings: Settings | None = None) -> RunResult:
    """Fetch live Home Assistant context, then run the shared decision pipeline."""
    run_started = perf_counter()
    with _log_step("configuratie laden"):
        settings = settings or Settings.from_environment()
    _require_typesafe_key(settings)
    if not settings.ha_token:
        raise RuntimeError("Vul HA_TOKEN in .env in om Home Assistant te gebruiken.")

    ha = HomeAssistantClient(settings.ha_url, settings.ha_token)
    with _log_step("Home Assistant-context ophalen en opbouwen"):
        context = build_context(ha, settings)
    result = run_context(context, settings, source="home_assistant", run_started=run_started)
    return result


def run_with_sample_json(
    sample_path: Path = DEFAULT_SAMPLE_PATH,
    settings: Settings | None = None,
) -> RunResult:
    """Load a saved context JSON file, then run the shared decision pipeline."""
    run_started = perf_counter()
    with _log_step("configuratie laden"):
        settings = settings or Settings.from_environment()
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
    logger.info(f"Contextbron: {source}")
    logger.info(f"Irrigation-context:\n{json.dumps(context.model_dump(mode='json'), ensure_ascii=False, indent=2)}")

    try:
        with _log_step("Jev-beslissing opvragen"):
            decision: IrrigationDecision | None = request_decision(context, settings.typesafe_api_key)
    except Exception as error:
        logger.error(f"Jev-aanroep mislukt; veilig niet sproeien ({type(error).__name__}).")
        decision = None

    with _log_step("veiligheidscontroles uitvoeren"):
        safety = apply_safety(decision, context.today_watering_minutes, WATERING_MINUTES)
    dryness = decision.dryness_score if decision else None
    probability = decision.probability if decision else None
    logger.info(
        f"Besluit: jev_sproeien_nu={decision.sproeien_nu if decision else False} "
        f"probability={probability} droogte_score={dryness} "
        f"veiligheidsinterventie={safety.intervention} safety_goedgekeurd={safety.approved} "
        f"duur_minuten={safety.minutes} dry_run={settings.dry_run} pomp_geactiveerd=false"
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
    logger.info(f"Hydro-Jev afgerond (totale duur {perf_counter() - run_started:.2f} s)")
    return RunResult(context=context, decision=decision, safety=safety)


def _require_typesafe_key(settings: Settings) -> None:
    if not settings.typesafe_api_key:
        raise RuntimeError("Vul TYPESAFE_API_KEY in .env in om Jev te gebruiken.")


def main(argv: Sequence[str] | None = None) -> None:
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
