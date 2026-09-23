from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from supported_fixtures import create_numeric

from reckonsolve.application.errors import (
    ConcurrentForecastUpdateError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database


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
        "precision": 1,
        "quantiles": {5: "3.0", 25: "5.0", 50: "7.0", 75: "14.0", 95: "21.0"},
    }
    values.update(kwargs)
    return create_numeric(operations, **values)


def test_numeric_revision_appends_changed_quantiles_and_causal_journal_timeline(
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
    operations = PredictionOperations(
        database, FixedClock(NOW + timedelta(minutes=1)), UTC
    )
    revised = operations.revise_quantile_forecast(
        created.prediction_id,
        {5: "5.0", 25: "7.0", 50: "10.0", 75: "20.0", 95: "30.0"},
        rationale="The reply queue is longer than expected.",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )

    assert revised.current_revision.sequence == 2
    assert str(revised.current_revision.quantiles.q05) == "5.0"
    assert str(revised.current_revision.quantiles.q50) == "10.0"
    timeline = operations.list_numeric_timeline(created.prediction_id)
    assert [event.kind for event in timeline] == ["forecast", "journal", "forecast"]
    assert timeline[1].entry_id == journal.entry_id
    assert timeline[1].revision == timeline[0].revision
    assert timeline[2].revision == revised.current_revision
    assert len(operations.list_numeric_forecast_revisions(created.prediction_id)) == 2
    database.close()


def test_numeric_unchanged_and_stale_revisions_append_nothing(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    created = _create(operations)

    operations = PredictionOperations(
        database, FixedClock(NOW + timedelta(minutes=1)), UTC
    )

    with pytest.raises(ValidationError, match="unchanged"):
        operations.revise_quantile_forecast(
            created.prediction_id,
            {5: "3.0", 25: "5.0", 50: "7.0", 75: "14.0", 95: "21.0"},
            expected_revision_id=created.current_revision.revision_id,
            expected_metadata_version=created.metadata_version,
        )
    with pytest.raises(ConcurrentForecastUpdateError):
        operations.revise_quantile_forecast(
            created.prediction_id,
            {5: 4, 25: 6, 50: 8, 75: 16, 95: 22},
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
        forecast_deadline=NOW + timedelta(hours=1),
    )
    later = PredictionOperations(database, FixedClock(NOW + timedelta(days=1)), UTC)

    with pytest.raises(ValidationError, match="before the Forecast Deadline"):
        later.revise_quantile_forecast(
            created.prediction_id,
            {5: 4, 25: 6, 50: 8, 75: 16, 95: 22},
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
    operations = PredictionOperations(
        database, FixedClock(NOW + timedelta(minutes=1)), UTC
    )
    revised = operations.revise_quantile_forecast(
        created.prediction_id,
        {5: "-2.5", 25: "0.0", 50: "4.5", 75: "10.0", 95: "18.0"},
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
    assert str(recovered.current_revision.quantiles.q05) == "-2.5"
    reopened.close()
