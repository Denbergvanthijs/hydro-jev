from datetime import datetime

from ha.history import extract_watering_sessions


def test_multiple_pump_cycles_become_sessions() -> None:
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

    assert [session.duration_minutes for session in sessions] == [5, 5]
    assert all(session.reliable for session in sessions)


def test_open_session_is_reported_as_unreliable() -> None:
    sessions = extract_watering_sessions(
        [[{"state": "on", "last_changed": "2026-10-04T11:00:00+02:00"}]],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert len(sessions) == 1
    assert sessions[0].duration_minutes is None
    assert not sessions[0].reliable


def test_missing_transition_timestamp_is_reported_as_unreliable() -> None:
    sessions = extract_watering_sessions(
        [[{"state": "on"}, {"state": "off", "last_changed": "2026-10-04T12:00:00+02:00"}]],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert len(sessions) == 1
    assert sessions[0].start_time is None
    assert not sessions[0].reliable


def test_short_manual_session_is_kept_and_duration_rounded() -> None:
    sessions = extract_watering_sessions(
        [
            [
                {"state": "on", "last_changed": "2026-10-04T11:56:51.000000+02:00"},
                {"state": "off", "last_changed": "2026-10-04T11:57:12.634078+02:00"},
            ]
        ],
        datetime.fromisoformat("2026-10-04T12:00:00+02:00"),
    )

    assert len(sessions) == 1
    assert sessions[0].duration_minutes == 0.36
    assert sessions[0].reliable
