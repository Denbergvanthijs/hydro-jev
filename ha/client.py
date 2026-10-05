"""HTTP client for retrieving Home Assistant state and history."""

import logging
from contextlib import contextmanager
from collections.abc import Iterator
from datetime import datetime
from time import perf_counter
from typing import Any
from urllib.parse import quote

import requests

logger = logging.getLogger("hydro_jev.ha")


@contextmanager
def _log_request(operation: str, entity_id: str) -> Iterator[None]:
    """Log the start and outcome of one Home Assistant request."""
    started = perf_counter()
    logger.info("HA-call gestart: %s entity=%s", operation, entity_id)
    try:
        yield
    except Exception as error:
        logger.error(
            "HA-call mislukt: %s entity=%s na %.2f s (%s)",
            operation,
            entity_id,
            perf_counter() - started,
            type(error).__name__,
        )
        raise
    else:
        logger.info("HA-call gereed: %s entity=%s (%.2f s)", operation, entity_id, perf_counter() - started)


class HomeAssistantClient:
    """Small Home Assistant REST API client."""

    def __init__(
        self,
        base_url: str,
        token: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        """Create a client configured with its endpoint and bearer token."""
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        self.timeout = timeout

    def get_state(self, entity_id: str) -> dict[str, Any]:
        """Return the state payload for an entity."""
        with _log_request("state", entity_id):
            response = self.session.get(f"{self.base_url}/api/states/{quote(entity_id, safe='.')}", timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise TypeError(f"Home Assistant returned an invalid state for {entity_id}")
            return result

    def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, Any]]]:
        """Return state-history records for an entity and time interval."""
        start_path = quote(start.isoformat(), safe="")
        with _log_request("history", entity_id):
            response = self.session.get(
                f"{self.base_url}/api/history/period/{start_path}",
                params={"filter_entity_id": entity_id, "end_time": end.isoformat()},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, list):
                raise TypeError("Home Assistant returned invalid history data")
            return result

    def get_weather_forecast(self, entity_id: str) -> dict[str, Any]:
        """Return the hourly weather forecast for an entity."""
        with _log_request("uurlijkse weersverwachting", entity_id):
            response = self.session.post(
                f"{self.base_url}/api/services/weather/get_forecasts",
                params={"return_response": ""},
                json={"entity_id": entity_id, "type": "hourly"},
                timeout=self.timeout,
            )
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict):
                raise TypeError("Home Assistant returned invalid forecast data")
            return result
