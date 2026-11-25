from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def get_clock() -> Clock:
    return SystemClock()


def as_utc(value: datetime) -> datetime:
    """SQLite drops the timezone on read; Postgres keeps it."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)
