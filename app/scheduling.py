"""Minimal schedule arithmetic: daily or weekly at a chosen UTC hour."""

from datetime import datetime, timedelta, timezone


def compute_next_run(frequency: str, hour: int, now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate


def advance_next_run(
    current: datetime, frequency: str, now: datetime | None = None
) -> datetime:
    step = timedelta(days=7 if frequency == "weekly" else 1)
    now = now or datetime.now(timezone.utc)
    nxt = current + step
    while nxt <= now:
        nxt += step
    return nxt
