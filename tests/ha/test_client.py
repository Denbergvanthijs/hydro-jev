from datetime import UTC, datetime  # noqa: D100

import pytest

from ha.client import HomeAssistantClient


class Response:  # noqa: D101
    def __init__(self, payload: object, error: Exception | None = None) -> None:  # noqa: D107
        self.payload = payload
        self.error = error

    def raise_for_status(self) -> None:  # noqa: D102
        if self.error:
            raise self.error

    def json(self) -> object:  # noqa: D102
        return self.payload


class Session:  # noqa: D101
    def __init__(self, response: Response) -> None:  # noqa: D107
        self.response = response
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs: object) -> Response:  # noqa: D102
        self.calls.append((url, kwargs))
        return self.response

    def post(self, url: str, **kwargs: object) -> Response:  # noqa: D102
        self.calls.append((url, kwargs))
        return self.response


def test_home_assistant_client_requests_and_payload_validation() -> None:  # noqa: D103
    session = Session(Response({"state": "on"}))
    client = HomeAssistantClient("http://ha.local/", "token", 3, session=session)

    assert client.get_state("switch.test") == {"state": "on"}  # noqa: S101
    assert "Authorization" in session.headers  # noqa: S101

    session.response = Response([{"state": "on"}])
    assert client.get_history(  # noqa: S101
        "switch.test",
        datetime.fromisoformat("2026-10-04T11:00:00+02:00"),
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    ) == [{"state": "on"}]

    session.response = Response({"weather.forecast_home": {"forecast": []}})
    assert client.get_weather_forecast("weather.forecast_home") == {"weather.forecast_home": {"forecast": []}}  # noqa: S101
    assert len(session.calls) == 3  # noqa: PLR2004, S101

    session.response = Response("invalid")
    with pytest.raises(TypeError):
        client.get_state("switch.test")
    with pytest.raises(TypeError):
        client.get_history("switch.test", datetime.now(UTC), datetime.now(UTC))
    with pytest.raises(TypeError):
        client.get_weather_forecast("weather.forecast_home")


def test_home_assistant_client_reraises_http_errors() -> None:  # noqa: D103
    error = RuntimeError("request failed")
    client = HomeAssistantClient("http://ha.local", "token", 10, session=Session(Response({}, error)))

    with pytest.raises(RuntimeError, match="request failed"):
        client.get_state("switch.test")
