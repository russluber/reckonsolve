from datetime import UTC, date, datetime, timedelta

import pytest

from reckonsolve.domain.attention import (
    AttentionValidationError,
    needs_attention,
    ready_to_resolve,
    validate_stale_threshold_days,
)
from reckonsolve.domain.predictions import PredictionStatus


def test_needs_attention_begins_at_fourteen_elapsed_days() -> None:
    revised_at = datetime(2026, 8, 1, 18, 30, tzinfo=UTC)

    assert not needs_attention(
        PredictionStatus.OPEN,
        revised_at,
        revised_at + timedelta(days=14) - timedelta(microseconds=1),
        14,
    )
    assert needs_attention(
        PredictionStatus.OPEN,
        revised_at,
        revised_at + timedelta(days=14),
        14,
    )


def test_needs_attention_includes_locked_but_excludes_terminal_states() -> None:
    revised_at = datetime(2026, 8, 1, tzinfo=UTC)
    now = revised_at + timedelta(days=30)

    assert needs_attention(PredictionStatus.LOCKED, revised_at, now, 14)
    assert not needs_attention(PredictionStatus.RESOLVED, revised_at, now, 14)
    assert not needs_attention(PredictionStatus.INVALID, revised_at, now, 14)


def test_ready_to_resolve_starts_after_inclusive_expected_date() -> None:
    expected = date(2026, 8, 20)

    assert not ready_to_resolve(PredictionStatus.OPEN, expected, expected)
    assert ready_to_resolve(PredictionStatus.OPEN, expected, date(2026, 8, 21))
    assert ready_to_resolve(PredictionStatus.LOCKED, expected, date(2026, 8, 21))
    assert not ready_to_resolve(
        PredictionStatus.RESOLVED,
        expected,
        date(2026, 8, 21),
    )
    assert not ready_to_resolve(PredictionStatus.OPEN, None, date(2026, 8, 21))


@pytest.mark.parametrize("value", [True, 0, 10_000, 2.5, "14"])
def test_stale_threshold_rejects_invalid_values(value: object) -> None:
    with pytest.raises(AttentionValidationError):
        validate_stale_threshold_days(value)
