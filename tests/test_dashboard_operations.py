from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    PredictionStatus,
    PredictionType,
)

NOW = datetime(2026, 8, 20, 18, 30, tzinfo=UTC)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def _create(database: Database, question: str, age_days: int, **details):
    return PredictionOperations(
        database,
        FixedClock(NOW - timedelta(days=age_days)),
        UTC,
    ).create_prediction(question, 60, **details)


def test_dashboard_derives_overlapping_buckets_and_excludes_terminal(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    fresh = _create(database, "Fresh Open", 13)
    stale = _create(database, "Stale Open", 14)
    locked_overlap = _create(
        database,
        "Locked, stale, and ready",
        20,
        forecast_deadline=date(2026, 8, 2),
        expected_resolution=date(2026, 8, 3),
    )
    ready = _create(
        database,
        "Ready but fresh",
        1,
        expected_resolution=date(2026, 8, 19),
    )
    terminal = _create(database, "Already resolved", 3)
    PredictionOperations(database, FixedClock(NOW), UTC).resolve_prediction(
        terminal.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=terminal.current_revision_id,
        expected_metadata_version=terminal.metadata_version,
    )

    dashboard = PredictionOperations(database, FixedClock(NOW), UTC).get_dashboard()

    assert dashboard.stale_threshold_days == 14
    assert tuple(item.prediction_id for item in dashboard.open_predictions) == (
        ready.prediction_id,
        fresh.prediction_id,
        stale.prediction_id,
    )
    assert tuple(
        item.prediction_id for item in dashboard.needs_attention_predictions
    ) == (
        locked_overlap.prediction_id,
        stale.prediction_id,
    )
    assert tuple(
        item.prediction_id for item in dashboard.ready_to_resolve_predictions
    ) == (
        locked_overlap.prediction_id,
        ready.prediction_id,
    )
    assert tuple(item.prediction_id for item in dashboard.locked_predictions) == (
        locked_overlap.prediction_id,
    )
    assert dashboard.locked_predictions[0].status is PredictionStatus.LOCKED
    assert all(
        terminal.prediction_id not in {item.prediction_id for item in bucket}
        for bucket in (
            dashboard.open_predictions,
            dashboard.needs_attention_predictions,
            dashboard.ready_to_resolve_predictions,
            dashboard.locked_predictions,
        )
    )
    database.close()


def test_expected_resolution_is_inclusive_in_computer_local_date(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    expected = date(2026, 8, 20)
    created = _create(
        database,
        "Resolve after today",
        1,
        expected_resolution=expected,
    )

    on_date = PredictionOperations(database, FixedClock(NOW), UTC).get_dashboard()
    next_date = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        UTC,
    ).get_dashboard()

    assert created.prediction_id not in {
        item.prediction_id for item in on_date.ready_to_resolve_predictions
    }
    assert created.prediction_id in {
        item.prediction_id for item in next_date.ready_to_resolve_predictions
    }
    database.close()


def test_ready_to_resolve_uses_computer_local_date_boundary(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    pacific = timezone(timedelta(hours=-7))
    created = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 19, 18, 30, tzinfo=UTC)),
        pacific,
    ).create_prediction(
        "Ready after the Pacific expected date",
        60,
        expected_resolution=date(2026, 8, 19),
    )

    before_local_midnight = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 20, 6, 59, tzinfo=UTC)),
        pacific,
    ).get_dashboard()
    after_local_midnight = PredictionOperations(
        database,
        FixedClock(datetime(2026, 8, 20, 7, 0, tzinfo=UTC)),
        pacific,
    ).get_dashboard()

    assert created.prediction_id not in {
        item.prediction_id
        for item in before_local_midnight.ready_to_resolve_predictions
    }
    assert created.prediction_id in {
        item.prediction_id for item in after_local_midnight.ready_to_resolve_predictions
    }
    database.close()


def test_persisted_threshold_changes_classification_after_restart(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    created = _create(first_database, "Sixteen days old", 16)
    first_operations = PredictionOperations(first_database, FixedClock(NOW), UTC)
    assert created.prediction_id in {
        item.prediction_id
        for item in first_operations.get_dashboard().needs_attention_predictions
    }
    assert first_operations.set_stale_threshold_days(30) == 30
    first_database.close()

    reopened_database = Database.open(path)
    reopened = PredictionOperations(reopened_database, FixedClock(NOW), UTC)
    assert reopened.get_stale_threshold_days() == 30
    assert created.prediction_id not in {
        item.prediction_id
        for item in reopened.get_dashboard().needs_attention_predictions
    }
    reopened_database.close()


@pytest.mark.parametrize("value", [True, 0, 10_000, 2.5])
def test_threshold_operation_rejects_invalid_values(tmp_path, value: object) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    with pytest.raises(ValidationError, match="threshold"):
        PredictionOperations(database, FixedClock(NOW)).set_stale_threshold_days(
            value  # type: ignore[arg-type]
        )

    assert (
        PredictionOperations(database, FixedClock(NOW)).get_stale_threshold_days() == 14
    )
    database.close()


def test_journal_entry_does_not_reset_needs_attention(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database, "Old forecast with new reasoning", 20)
    operations = PredictionOperations(database, FixedClock(NOW), UTC)

    entry = operations.add_journal_entry(
        created.prediction_id,
        "New evidence, but my probability remains unchanged.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )

    assert created.prediction_id in {
        item.prediction_id
        for item in operations.get_dashboard().needs_attention_predictions
    }

    next_day = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        UTC,
    )
    next_day.correct_journal_entry(
        created.prediction_id,
        entry.entry_id,
        "Corrected evidence, with the probability still unchanged.",
        expected_correction_id=entry.current_correction_id,
    )
    assert created.prediction_id in {
        item.prediction_id
        for item in next_day.get_dashboard().needs_attention_predictions
    }
    database.close()


def test_new_forecast_revision_resets_needs_attention(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(database, "Old forecast revised today", 20)
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    assert created.prediction_id in {
        item.prediction_id
        for item in operations.get_dashboard().needs_attention_predictions
    }

    operations.revise_forecast(
        created.prediction_id,
        65,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )

    assert created.prediction_id not in {
        item.prediction_id
        for item in operations.get_dashboard().needs_attention_predictions
    }
    database.close()


def test_dashboard_includes_type_aware_numeric_rows_and_attention_buckets(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    numeric = PredictionOperations(
        database,
        FixedClock(NOW - timedelta(days=20)),
        UTC,
    ).create_numeric_prediction(
        "How many Numeric days remain?",
        "days",
        1,
        "2.0",
        "4.0",
        "8.0",
        80,
        forecast_deadline=(NOW - timedelta(days=20)).date(),
        expected_resolution=(NOW - timedelta(days=19)).date(),
    )
    binary = _create(database, "Fresh Binary companion", 1)
    resolved_numeric = PredictionOperations(
        database, FixedClock(NOW), UTC
    ).create_numeric_prediction(
        "How many terminal Numeric days?",
        "days",
        0,
        1,
        2,
        3,
        80,
    )
    PredictionOperations(database, FixedClock(NOW), UTC).resolve_numeric_prediction(
        resolved_numeric.prediction_id,
        2,
        expected_revision_id=resolved_numeric.current_revision.revision_id,
        expected_metadata_version=resolved_numeric.metadata_version,
    )

    snapshot = PredictionOperations(database, FixedClock(NOW), UTC).get_dashboard()

    numeric_row = next(
        item
        for item in snapshot.locked_predictions
        if item.prediction_id == numeric.prediction_id
    )
    assert numeric_row.prediction_type is PredictionType.NUMERIC
    assert numeric_row.probability_percent is None
    assert str(numeric_row.numeric_lower_bound) == "2.0"
    assert str(numeric_row.numeric_median_estimate) == "4.0"
    assert str(numeric_row.numeric_upper_bound) == "8.0"
    assert numeric_row.numeric_confidence_percent == 80
    assert numeric_row.numeric_unit == "days"
    assert numeric_row.needs_attention
    assert numeric_row.ready_to_resolve
    assert numeric.prediction_id in {
        item.prediction_id for item in snapshot.needs_attention_predictions
    }
    assert numeric.prediction_id in {
        item.prediction_id for item in snapshot.ready_to_resolve_predictions
    }
    assert binary.prediction_id in {
        item.prediction_id for item in snapshot.open_predictions
    }
    assert all(
        resolved_numeric.prediction_id not in {item.prediction_id for item in bucket}
        for bucket in (
            snapshot.open_predictions,
            snapshot.needs_attention_predictions,
            snapshot.ready_to_resolve_predictions,
            snapshot.locked_predictions,
        )
    )
    database.close()
