from datetime import UTC, datetime

import pytest

from ha.client import HomeAssistantClient


class Response:
    def __init__(self, payload: object, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:
        if self.error:
            raise self.error

    def json(self) -> object:
        return self.payload


class Session:
    def __init__(self, response: Response) -> None:
        self.response = response
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> Response:
        self.calls.append((url, kwargs))
        return self.response

    def post(self, url: str, **kwargs: object) -> Response:
        self.calls.append((url, kwargs))
        return self.response


def test_home_assistant_client_requests_and_payload_validation() -> None:
    session = Session(Response({"state": "on"}))
    client = HomeAssistantClient("http://ha.local/", "token", session=session, timeout=3)

    assert client.get_state("switch.test") == {"state": "on"}
    assert "Authorization" in session.headers

    session.response = Response([{"state": "on"}])
    assert client.get_history(
        "switch.test",
        datetime.fromisoformat("2026-10-04T11:00:00+02:00"),
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    ) == [{"state": "on"}]

    session.response = Response({"weather.forecast_home": {"forecast": []}})
    assert client.get_weather_forecast("weather.forecast_home") == {"weather.forecast_home": {"forecast": []}}
    assert len(session.calls) == 3

    session.response = Response("invalid")
    with pytest.raises(TypeError):
        client.get_state("switch.test")
    with pytest.raises(TypeError):
        client.get_history("switch.test", datetime.now(UTC), datetime.now(UTC))
    with pytest.raises(TypeError):
        client.get_weather_forecast("weather.forecast_home")


def test_home_assistant_client_reraises_http_errors() -> None:
    error = RuntimeError("request failed")
    client = HomeAssistantClient("http://ha.local", "token", session=Session(Response({}, error)))

    with pytest.raises(RuntimeError, match="request failed"):
        client.get_state("switch.test")
