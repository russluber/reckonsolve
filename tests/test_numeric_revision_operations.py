from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.application.errors import (
    ConcurrentForecastUpdateError,
    ForecastRevisionNotAllowedError,
    NumericForecastUnchangedError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    NumericForecastTimelineEvent,
    NumericJournalTimelineEvent,
)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 21, 19, 30, tzinfo=UTC)


def _create(operations: PredictionOperations, **kwargs):
    values = {
        "question": "How many days will the reply take?",
        "unit": "days",
        "decimal_places": 1,
        "lower_bound": "3.0",
        "median_estimate": "7.0",
        "upper_bound": "21.0",
        "confidence_percent": 80,
    }
    values.update(kwargs)
    return operations.create_numeric_prediction(**values)


def test_numeric_revision_appends_changed_interval_and_causal_journal_timeline(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    created = _create(operations, rationale="Initial interval")

    journal = operations.add_numeric_journal_entry(
        created.prediction_id,
        "New information suggests a longer wait.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    revised = operations.revise_numeric_forecast(
        created.prediction_id,
        "5.0",
        "10.0",
        "30.0",
        90,
        rationale="The reply queue is longer than expected.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )

    assert revised.current_revision.sequence == 2
    assert str(revised.current_revision.lower_bound) == "5.0"
    assert str(revised.current_revision.median_estimate) == "10.0"
    assert revised.current_revision.confidence_percent == 90
    timeline = operations.list_numeric_timeline(created.prediction_id)
    assert [type(event) for event in timeline] == [
        NumericForecastTimelineEvent,
        NumericJournalTimelineEvent,
        NumericForecastTimelineEvent,
    ]
    assert timeline[1] == journal
    assert timeline[2].previous_median_estimate == timeline[0].median_estimate
    assert len(operations.list_numeric_forecast_revisions(created.prediction_id)) == 2
    database.close()


def test_numeric_unchanged_and_stale_revisions_append_nothing(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    created = _create(operations)

    with pytest.raises(NumericForecastUnchangedError):
        operations.revise_numeric_forecast(
            created.prediction_id,
            "3.0",
            "7.0",
            "21.0",
            80,
            expected_revision_id=created.current_revision.revision_id,
            expected_metadata_version=created.metadata_version,
        )
    with pytest.raises(ConcurrentForecastUpdateError):
        operations.revise_numeric_forecast(
            created.prediction_id,
            4,
            8,
            22,
            80,
            expected_revision_id=created.current_revision.revision_id + 1,
            expected_metadata_version=created.metadata_version,
        )
    assert len(operations.list_numeric_forecast_revisions(created.prediction_id)) == 1
    database.close()


def test_locked_numeric_prediction_rejects_revision_but_accepts_journal_and_correction(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = _create(
        PredictionOperations(database, FixedClock(NOW), UTC),
        forecast_deadline=NOW.date(),
    )
    later = PredictionOperations(database, FixedClock(NOW + timedelta(days=1)), UTC)

    with pytest.raises(ForecastRevisionNotAllowedError):
        later.revise_numeric_forecast(
            created.prediction_id,
            4,
            8,
            22,
            80,
            expected_revision_id=created.current_revision.revision_id,
            expected_metadata_version=created.metadata_version,
        )
    journal = later.add_numeric_journal_entry(
        created.prediction_id,
        "The decision is still pending.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    corrected = later.correct_numeric_journal_entry(
        created.prediction_id,
        journal.entry_id,
        "The decision remains pending.",
        expected_correction_id=None,
    )
    assert corrected.body == "The decision remains pending."
    assert len(later.list_numeric_forecast_revisions(created.prediction_id)) == 1
    database.close()


def test_numeric_revision_round_trips_after_restart(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    created = _create(operations)
    revised = operations.revise_numeric_forecast(
        created.prediction_id,
        "-2.5",
        "4.5",
        "18.0",
        95,
        rationale="Signed values remain exact.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    database.close()

    reopened = Database.open(path)
    recovered = PredictionOperations(
        reopened, FixedClock(NOW), UTC
    ).get_numeric_prediction(created.prediction_id)
    assert recovered == revised
    assert str(recovered.current_revision.lower_bound) == "-2.5"
    reopened.close()
