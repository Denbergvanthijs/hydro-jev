from datetime import datetime  # noqa: D100
from zoneinfo import ZoneInfo

from ha.history import _timestamp, extract_watering_sessions


def test_multiple_pump_cycles_become_sessions() -> None:  # noqa: D103
    history = [
        [
            {"state": "off", "last_changed": "2026-10-04T08:00:00+02:00"},
            {"state": "on", "last_changed": "2026-10-04T09:00:00+02:00"},
            {"state": "off", "last_changed": "2026-10-04T09:05:00+02:00"},
            {"state": "on", "last_changed": "2026-10-04T11:00:00+02:00"},
            {"state": "off", "last_changed": "2026-10-04T11:05:00+02:00"},
        ]
    ]
    sessions = extract_watering_sessions(history, datetime.fromisoformat("2026-10-04T12:00:00+02:00"))

    assert [session.duration_minutes for session in sessions] == [5, 5]  # noqa: S101
    assert all(session.reliable for session in sessions)  # noqa: S101


def test_open_session_is_reported_as_unreliable() -> None:  # noqa: D103
    sessions = extract_watering_sessions(
        [[{"state": "on", "last_changed": "2026-10-04T11:00:00+02:00"}]],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert len(sessions) == 1  # noqa: S101
    assert sessions[0].duration_minutes is None  # noqa: S101
    assert not sessions[0].reliable  # noqa: S101


def test_missing_transition_timestamp_is_reported_as_unreliable() -> None:  # noqa: D103
    sessions = extract_watering_sessions(
        [[{"state": "on"}, {"state": "off", "last_changed": "2026-10-04T12:00:00+02:00"}]],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert len(sessions) == 1  # noqa: S101
    assert sessions[0].start_time is None  # noqa: S101
    assert not sessions[0].reliable  # noqa: S101


def test_short_manual_session_is_kept_and_duration_rounded() -> None:  # noqa: D103
    sessions = extract_watering_sessions(
        [
            [
                {"state": "on", "last_changed": "2026-10-04T11:56:51.000000+02:00"},
                {"state": "off", "last_changed": "2026-10-04T11:57:12.634078+02:00"},
            ]
        ],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert len(sessions) == 1  # noqa: S101
    assert sessions[0].duration_minutes == 0.36  # noqa: PLR2004, S101
    assert sessions[0].reliable  # noqa: S101


def test_invalid_history_timestamp_is_ignored() -> None:  # noqa: D103
    assert _timestamp({"last_changed": "invalid"}) is None  # noqa: S101
    assert _timestamp({"last_changed": "2026-10-04T11:00:00"}, ZoneInfo("Europe/Amsterdam")) == datetime.fromisoformat(  # noqa: S101
        "2026-10-04T11:00:00+02:00"
    )


def test_history_timestamps_are_normalized_to_configured_timezone() -> None:  # noqa: D103
    sessions = extract_watering_sessions(
        [
            [
                {"state": "on", "last_changed": "2026-10-04T09:00:00+00:00"},
                {"state": "off", "last_changed": "2026-10-04T09:05:00+00:00"},
            ]
        ],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
        ZoneInfo("Europe/Amsterdam"),
    )

    assert sessions[0].start_time == datetime.fromisoformat("2026-10-04T11:00:00+02:00")  # noqa: S101
    assert sessions[0].end_time == datetime.fromisoformat("2026-10-04T11:05:00+02:00")  # noqa: S101
