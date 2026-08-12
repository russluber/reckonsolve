"""Centralized, injectable acquisition and serialization of UTC instants."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Provide the current instant for time-dependent application operations."""

    def now(self) -> datetime:
        """Return an aware datetime representing the current instant."""


class SystemClock:
    """Read the system clock in UTC."""

    def now(self) -> datetime:
        return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize an aware datetime to UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Clock values must include timezone information.")
    return value.astimezone(UTC)


def format_utc(value: datetime) -> str:
    """Serialize an aware instant as a stable UTC database value."""

    return as_utc(value).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    """Parse a database UTC timestamp into an aware UTC datetime."""

    if not value.endswith("Z"):
        raise ValueError("Stored timestamps must be UTC values ending in 'Z'.")
    parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    return as_utc(parsed)
