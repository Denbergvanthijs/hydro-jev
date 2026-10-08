"""Interpret Home Assistant history records as watering sessions."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel


class WateringSession(BaseModel):
    """A watering session derived from pump state transitions."""

    start_time: datetime | None
    end_time: datetime | None
    duration_minutes: float | None
    reliable: bool
    note: str | None = None


def extract_watering_sessions(
    history: list[list[dict[str, Any]]],
    now: datetime,
    target_timezone: ZoneInfo | None = None,
) -> list[WateringSession]:
    """Extract completed and incomplete sessions from grouped history records."""
    records = [record for group in history for record in group]
    records.sort(key=lambda record: _timestamp(record, target_timezone) or now)
    sessions: list[WateringSession] = []
    active_since: datetime | None = None
    pump_is_active = False

    for record in records:
        state = str(record.get("state", "")).lower()
        changed_at = _timestamp(record, target_timezone)
        if state == "on" and not pump_is_active:
            pump_is_active = True
            active_since = changed_at
        elif state == "off" and pump_is_active:
            if active_since is None or changed_at is None or changed_at < active_since:
                sessions.append(
                    WateringSession(
                        start_time=active_since,
                        end_time=None,
                        duration_minutes=None,
                        reliable=False,
                        note="Pompuit-tijdstip ontbreekt of is ongeldig.",
                    )
                )
            else:
                duration = round((changed_at - active_since).total_seconds() / 60, 2)
                sessions.append(
                    WateringSession(
                        start_time=active_since,
                        end_time=changed_at,
                        duration_minutes=duration,
                        reliable=True,
                    )
                )
            pump_is_active = False
            active_since = None

    if pump_is_active:
        sessions.append(
            WateringSession(
                start_time=active_since,
                end_time=None,
                duration_minutes=None,
                reliable=False,
                note="Sproeisessie loopt nog of een uit-transitie ontbreekt.",
            )
        )
    return sessions


def _timestamp(record: dict[str, Any], target_timezone: ZoneInfo | None = None) -> datetime | None:
    value = record.get("last_changed")
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value)
        if target_timezone is None:
            return timestamp
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=target_timezone)
        return timestamp.astimezone(target_timezone)
    except ValueError:
        return None
