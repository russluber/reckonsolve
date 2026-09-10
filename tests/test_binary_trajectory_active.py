"""M47's public creation path, exact active lifecycle, and legacy isolation."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

import pytest

from reckonsolve.application.errors import (
    ConcurrentForecastUpdateError,
    CsvExportError,
    ForecastReviewNotAllowedError,
    ForecastRevisionNotAllowedError,
    PredictionDeletionNotAllowedError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import run
from reckonsolve.data.database import Database
from reckonsolve.domain.browser import ArchiveDateMeaning
from reckonsolve.domain.forecast_contracts import ForecastCohort
from reckonsolve.domain.predictions import BinaryOutcome, PredictionStatus

START = datetime(2026, 9, 10, 18, 0, 0, 123456, tzinfo=UTC)
DEADLINE = START + timedelta(minutes=30)


@dataclass
class Clock:
    instant: datetime = START

    def now(self) -> datetime:
        return self.instant


@pytest.fixture
def active(tmp_path):
    database = Database.open(tmp_path / "active.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    yield database, clock, operations
    database.close()


def context(prediction):
    return {
        "expected_revision_id": prediction.current_revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


@pytest.mark.parametrize("probability", [0, 37, 100])
def test_creation_persists_exact_contract_and_restarts(active, probability):
    database, clock, operations = active
    offset = timezone(timedelta(hours=5, minutes=45))
    prediction = operations.create_prediction(
        "Will the sub-day window survive?",
        probability,
        forecast_deadline=DEADLINE.astimezone(offset),
        tags=("window",),
    )
    assert prediction.forecast_contract.cohort is ForecastCohort.TRAJECTORY_BINARY
    assert prediction.forecast_contract.forecast_deadline.instant == DEADLINE
    assert prediction.forecast_deadline is None
    assert prediction.created_at == prediction.latest_revision_at == START
    assert prediction.probability_percent == probability
    assert (
        operations.browse_predictions().predictions[0].forecast_contract
        == prediction.forecast_contract
    )
    assert (
        operations.search_predictions("sub-day").hits[0].prediction.forecast_contract
        == prediction.forecast_contract
    )
    with database.transaction() as connection:
        path = connection.execute("PRAGMA database_list").fetchone()[2]
    database.close()
    reopened = Database.open(Path(path))
    try:
        assert (
            PredictionOperations(reopened, clock, UTC).get_prediction(
                prediction.prediction_id
            )
            == prediction
        )
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "deadline",
    [
        None,
        date(2026, 9, 11),
        START.replace(tzinfo=None),
        START,
        START - timedelta(seconds=1),
    ],
)
def test_missing_naive_or_nonfuture_deadline_never_creates_partial_data(
    active, deadline
):
    database, _, operations = active
    with pytest.raises(ValidationError):
        operations.create_prediction(
            "Invalid deadline?", 50, forecast_deadline=deadline, tags=("orphan",)
        )
    with database.transaction() as connection:
        for table in (
            "predictions",
            "forecast_revisions",
            "prediction_forecast_contracts",
            "tags",
        ):
            assert (
                connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
            )


def test_exact_lock_boundary_across_reads_and_mutations(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Exact boundary?", 50, forecast_deadline=DEADLINE
    )
    clock.instant = DEADLINE - timedelta(microseconds=1)
    revised = operations.revise_forecast(
        prediction.prediction_id, 70, **context(prediction)
    )
    operations.add_forecast_review(
        prediction.prediction_id, note="Still convinced", **context(revised)
    )
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 2
    clock.instant = DEADLINE
    assert (
        operations.get_prediction(prediction.prediction_id).status
        is PredictionStatus.LOCKED
    )
    assert (
        operations.browse_predictions(status=PredictionStatus.LOCKED)
        .predictions[0]
        .prediction_id
        == prediction.prediction_id
    )
    assert operations.search_predictions(
        "boundary", status=PredictionStatus.LOCKED
    ).hits
    with pytest.raises(ForecastRevisionNotAllowedError):
        operations.revise_forecast(prediction.prediction_id, 80, **context(revised))
    with pytest.raises(ForecastReviewNotAllowedError):
        operations.add_forecast_review(prediction.prediction_id, **context(revised))
    operations.add_journal_entry(
        prediction.prediction_id, "Locked reasoning", **context(revised)
    )
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 2


@pytest.mark.parametrize("delta", [timedelta(0), timedelta(seconds=-1)])
def test_revision_rejects_equal_or_regressed_clock(active, delta):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "No invented time?", 50, forecast_deadline=DEADLINE
    )
    clock.instant = START + delta
    with pytest.raises(ValidationError):
        operations.revise_forecast(prediction.prediction_id, 60, **context(prediction))
    assert operations.get_prediction(prediction.prediction_id) == prediction


def test_transaction_rechecks_clock_after_waiting_for_write_access(active):
    database, _, operations = active
    prediction = operations.create_prediction(
        "Late save?", 50, forecast_deadline=DEADLINE
    )

    class AdvancingClock:
        calls = 0

        def now(self):
            self.calls += 1
            return DEADLINE - timedelta(seconds=1) if self.calls == 1 else DEADLINE

    late_operations = PredictionOperations(database, AdvancingClock(), UTC)
    with pytest.raises(ForecastRevisionNotAllowedError):
        late_operations.revise_forecast(
            prediction.prediction_id, 60, **context(prediction)
        )
    late_review = PredictionOperations(database, AdvancingClock(), UTC)
    with pytest.raises(ForecastReviewNotAllowedError):
        late_review.add_forecast_review(prediction.prediction_id, **context(prediction))
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 1
    assert len(operations.list_timeline(prediction.prediction_id)) == 1


def test_stale_revision_and_locked_deletion_preserve_history(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Stale dialog?", 50, forecast_deadline=DEADLINE
    )
    clock.instant += timedelta(seconds=1)
    operations.revise_forecast(prediction.prediction_id, 60, **context(prediction))
    with pytest.raises(ConcurrentForecastUpdateError):
        operations.revise_forecast(prediction.prediction_id, 70, **context(prediction))
    untouched = operations.create_prediction(
        "Untouched?", 50, forecast_deadline=DEADLINE
    )
    clock.instant = DEADLINE
    with pytest.raises(PredictionDeletionNotAllowedError):
        operations.delete_prediction(
            untouched.prediction_id,
            confirm_permanent_deletion=True,
            **context(untouched),
        )


def test_contract_insert_failure_rolls_back_initial_revision_and_tags(active):
    database, _, operations = active
    with database.transaction() as connection:
        connection.execute(
            "CREATE TRIGGER fail_contract BEFORE INSERT ON prediction_forecast_contracts BEGIN SELECT RAISE(ABORT, 'injected'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="injected"):
        operations.create_prediction(
            "Rollback?", 50, forecast_deadline=DEADLINE, tags=("no orphan",)
        )
    assert operations.browse_predictions().predictions == ()
    with database.transaction() as connection:
        assert connection.execute("SELECT count(*) FROM tags").fetchone()[0] == 0


def test_new_resolution_is_explicitly_staged_while_legacy_resolution_works(active):
    _, _, operations = active
    new = operations.create_prediction("New cohort?", 60, forecast_deadline=DEADLINE)
    with pytest.raises(ValidationError, match="M48"):
        operations.resolve_prediction(
            new.prediction_id, BinaryOutcome.YES, **context(new)
        )
    legacy = operations._create_legacy_prediction("Legacy cohort?", 60)
    resolved = operations.resolve_prediction(
        legacy.prediction_id, BinaryOutcome.YES, **context(legacy)
    )
    assert resolved.status is PredictionStatus.RESOLVED


def test_deadline_archive_filter_uses_exact_instant_local_date(active):
    database, clock, _ = active
    local = timezone(timedelta(hours=-7))
    operations = PredictionOperations(database, clock, local)
    deadline = datetime(2026, 9, 11, 1, tzinfo=UTC)
    prediction = operations.create_prediction(
        "Local day?", 50, forecast_deadline=deadline
    )
    rows = operations.browse_predictions(
        date_meaning=ArchiveDateMeaning.FORECAST_DEADLINE,
        date_start=date(2026, 9, 10),
        date_end=date(2026, 9, 10),
    )
    assert rows.predictions[0].prediction_id == prediction.prediction_id


def test_cli_requires_exact_deadline_and_can_cancel_without_creation(tmp_path):
    path = tmp_path / "cli.sqlite3"
    errors = StringIO()
    assert (
        run(
            ["create", "binary"],
            database_path=path,
            stdin=StringIO("Required?\n50\n"),
            stdout=StringIO(),
            stderr=errors,
        )
        == 130
    )
    output = StringIO()
    assert (
        run(
            ["create", "binary"],
            database_path=path,
            stdin=StringIO(
                "CLI window?\n100\n?\n2099-01-01\n2099-01-01T00:30:00+05:45\n\n"
            ),
            stdout=output,
            stderr=StringIO(),
        )
        == 0
    )
    assert "self-control" in output.getvalue()
    database = Database.open(path)
    try:
        created = PredictionOperations(database).get_prediction(1)
        assert created.forecast_contract.forecast_deadline.instant == datetime(
            2098, 12, 31, 18, 45, tzinfo=UTC
        )
    finally:
        database.close()


def test_metadata_can_change_without_rewriting_exact_deadline_or_freshness(active):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Permanent cutoff?", 40, forecast_deadline=DEADLINE
    )
    clock.instant += timedelta(seconds=30)
    details = {
        "question": prediction.question,
        "background": "New context",
        "resolution_criteria": None,
        "forecast_deadline": None,
        "expected_resolution": date(2026, 9, 12),
        "tags": ("new-tag",),
        "expected_metadata_version": prediction.metadata_version,
    }
    updated = operations.update_metadata(prediction.prediction_id, **details)
    assert updated.forecast_contract == prediction.forecast_contract
    assert updated.latest_revision_at == prediction.latest_revision_at
    assert updated.current_revision_id == prediction.current_revision_id
    details["forecast_deadline"] = date(2026, 9, 13)
    details["expected_metadata_version"] = updated.metadata_version
    with pytest.raises(ValidationError, match="permanent"):
        operations.update_metadata(prediction.prediction_id, **details)
    assert operations.get_prediction(prediction.prediction_id) == updated
    clock.instant = DEADLINE
    invalid = operations.invalidate_prediction(
        prediction.prediction_id, reason="Policy breached", **context(updated)
    )
    assert invalid.status is PredictionStatus.INVALID
    assert invalid.forecast_contract == prediction.forecast_contract
    assert (
        operations.browse_predictions(status=PredictionStatus.RESOLVED).predictions
        == ()
    )


def test_backup_retains_contract_and_old_csv_cannot_silently_drop_it(active, tmp_path):
    _, clock, operations = active
    prediction = operations.create_prediction(
        "Complete recovery?", 50, forecast_deadline=DEADLINE
    )
    backup_path = tmp_path / "recovery.sqlite3"
    operations.create_backup(backup_path)
    backup = Database.open(backup_path)
    try:
        assert (
            PredictionOperations(backup, clock, UTC).get_prediction(
                prediction.prediction_id
            )
            == prediction
        )
    finally:
        backup.close()
    export_path = tmp_path / "incomplete.zip"
    with pytest.raises(CsvExportError, match="M55"):
        operations.export_csv_bundle(export_path)
    assert not export_path.exists()
