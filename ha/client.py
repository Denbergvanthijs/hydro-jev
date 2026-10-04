from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

import requests


class HomeAssistantClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        session: requests.Session | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        self.timeout = timeout

    def get_state(self, entity_id: str) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}/api/states/{quote(entity_id, safe='.')}", timeout=self.timeout)
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError(f"Home Assistant returned an invalid state for {entity_id}")
        return result

    def get_history(self, entity_id: str, start: datetime, end: datetime) -> list[list[dict[str, Any]]]:
        start_path = quote(start.isoformat(), safe="")
        response = self.session.get(
            f"{self.base_url}/api/history/period/{start_path}",
            params={"filter_entity_id": entity_id, "end_time": end.isoformat()},
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, list):
            raise ValueError("Home Assistant returned invalid history data")
        return result

    def get_weather_forecast(self, entity_id: str) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/services/weather/get_forecasts",
            params={"return_response": ""},
            json={"entity_id": entity_id, "type": "hourly"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Home Assistant returned invalid forecast data")
        return result
