from datetime import UTC, datetime, timedelta, timezone

import pytest

from reckonsolve.clock import as_utc, format_utc, parse_utc


def test_utc_timestamp_round_trip_is_stable() -> None:
    instant = datetime(2026, 8, 12, 19, 3, 4, 5678, tzinfo=UTC)

    stored = format_utc(instant)

    assert stored == "2026-08-12T19:03:04.005678Z"
    assert parse_utc(stored) == instant
    assert parse_utc(stored).tzinfo is UTC


def test_offset_clock_value_is_normalized_to_utc() -> None:
    offset = timezone(timedelta(hours=-7))

    assert as_utc(datetime(2026, 8, 12, 12, 0, tzinfo=offset)) == datetime(
        2026,
        8,
        12,
        19,
        0,
        tzinfo=UTC,
    )


def test_naive_clock_value_is_rejected() -> None:
    with pytest.raises(ValueError, match="timezone"):
        format_utc(datetime(2026, 8, 12, 12, 0))  # noqa: DTZ001
