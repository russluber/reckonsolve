import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reckonsolve.application.errors import (
    ConcurrentTerminalCorrectionError,
    PostmortemCompletionNotAllowedError,
    TerminalCorrectionUnchangedError,
    ValidationError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.analytics import AnalyticsRepository
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome

CREATED = datetime(2026, 8, 20, 10, tzinfo=UTC)
RESOLVED = datetime(2026, 8, 21, 10, tzinfo=UTC)
CORRECTED = datetime(2026, 8, 26, 10, 30, 12, 3456, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


class CountingClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.instant


def _resolved_binary(database: Database, *, postmortem: str | None = None):
    created = PredictionOperations(
        database, FixedClock(CREATED), UTC
    ).create_prediction(
        "Will the recorded outcome be corrected?",
        70,
    )
    return PredictionOperations(database, FixedClock(RESOLVED), UTC).resolve_prediction(
        created.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Original source",
        postmortem=postmortem,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )


def _resolved_numeric(database: Database):
    created = PredictionOperations(
        database,
        FixedClock(CREATED),
        UTC,
    ).create_numeric_prediction(
        "What exact value will be observed?",
        "units",
        2,
        "-5.00",
        "0.00",
        "5.00",
        80,
    )
    return PredictionOperations(
        database,
        FixedClock(RESOLVED),
        UTC,
    ).resolve_numeric_prediction(
        created.prediction_id,
        "1.25",
        resolution_notes="Original measurement",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )


def test_binary_corrections_append_snapshots_and_drive_effective_analytics(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    resolved = _resolved_binary(database)
    assert resolved.resolution is not None
    original_scoring_revision_id = resolved.resolution.scoring_revision_id
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)

    first = operations.correct_binary_resolution(
        resolved.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Certified source",
        postmortem=None,
        correction_reason="The original source reported the preliminary result.",
        expected_correction_id=None,
    )
    second = operations.correct_binary_resolution(
        resolved.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Certified source",
        postmortem="I should have waited for certification.",
        expected_correction_id=first.current_correction_id,
    )

    assert second.original.outcome is BinaryOutcome.NO
    assert second.original.resolution_notes == "Original source"
    assert second.original.postmortem is None
    assert second.effective.outcome is BinaryOutcome.YES
    assert second.effective.resolution_notes == "Certified source"
    assert second.effective.postmortem == "I should have waited for certification."
    assert second.effective.resolved_at == RESOLVED
    assert second.effective.scoring_revision_id == original_scoring_revision_id
    assert [correction.sequence for correction in second.corrections] == [1, 2]
    assert second.corrections[0].changed_fields == ("outcome", "resolution_notes")
    assert second.corrections[1].changed_fields == ("postmortem",)
    assert second.corrections[0].corrected_at == CORRECTED

    source = AnalyticsRepository(database).get_source()
    assert len(source.observations) == 1
    assert source.observations[0].outcome is BinaryOutcome.YES
    assert source.observations[0].scoring_revision_id == original_scoring_revision_id
    assert source.observations[0].outcome_corrected is True
    scorecard = operations.get_prediction_scorecard(resolved.prediction_id)
    assert scorecard is not None
    assert scorecard.scoring_revision_id == original_scoring_revision_id
    assert scorecard.outcome is BinaryOutcome.YES
    assert scorecard.brier_score == pytest.approx(0.09)
    assert scorecard.outcome_corrected is True
    assert operations.get_analytics().scored_prediction_count == 1
    with database.transaction() as connection:
        original = connection.execute(
            "SELECT outcome, resolution_notes, postmortem FROM resolutions"
        ).fetchone()
        assert tuple(original) == ("no", "Original source", None)
        assert (
            connection.execute(
                "SELECT status FROM predictions WHERE id = ?",
                (resolved.prediction_id,),
            ).fetchone()[0]
            == "resolved"
        )
        assert connection.execute("SELECT COUNT(*) FROM resolutions").fetchone()[0] == 1
    database.close()

    reopened = Database.open(tmp_path / "reckonsolve.sqlite3")
    recovered = PredictionOperations(reopened).get_binary_resolution_history(
        resolved.prediction_id
    )
    assert len(recovered.corrections) == 2
    assert recovered.effective.outcome is BinaryOutcome.YES
    assert recovered.effective.postmortem == "I should have waited for certification."
    reopened.close()


def test_score_affecting_correction_requires_reason_and_no_op_reads_no_clock(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    resolved = _resolved_binary(database)
    clock = CountingClock(CORRECTED)
    operations = PredictionOperations(database, clock, UTC)

    with pytest.raises(ValidationError) as missing_reason:
        operations.correct_binary_resolution(
            resolved.prediction_id,
            BinaryOutcome.YES,
            resolution_notes="Original source",
            postmortem=None,
            expected_correction_id=None,
        )
    assert missing_reason.value.field == "correction_reason"

    with pytest.raises(TerminalCorrectionUnchangedError):
        operations.correct_binary_resolution(
            resolved.prediction_id,
            BinaryOutcome.NO,
            resolution_notes="  Original source  ",
            postmortem="",
            expected_correction_id=None,
        )

    assert clock.calls == 0
    with database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM resolution_corrections"
            ).fetchone()[0]
            == 0
        )
    database.close()


def test_stale_correction_token_is_rejected_across_connections(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    resolved = _resolved_binary(first_database)
    second_database = Database.open(path)
    first = PredictionOperations(first_database, FixedClock(CORRECTED), UTC)
    second = PredictionOperations(second_database, FixedClock(CORRECTED), UTC)

    first.correct_binary_resolution(
        resolved.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Corrected by the first connection",
        postmortem=None,
        expected_correction_id=None,
    )

    with pytest.raises(ConcurrentTerminalCorrectionError):
        second.correct_binary_resolution(
            resolved.prediction_id,
            BinaryOutcome.NO,
            resolution_notes="Stale replacement",
            postmortem=None,
            expected_correction_id=None,
        )

    history = first.get_binary_resolution_history(resolved.prediction_id)
    assert len(history.corrections) == 1
    assert history.effective.resolution_notes == "Corrected by the first connection"
    second_database.close()
    first_database.close()


def test_numeric_correction_round_trips_exactly_and_updates_one_observation(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    resolved = _resolved_numeric(database)
    assert resolved.resolution is not None
    scoring_revision_id = resolved.resolution.scoring_revision_id
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)

    history = operations.correct_numeric_resolution(
        resolved.prediction_id,
        "-2.50",
        resolution_notes="Corrected measurement",
        postmortem="The lower tail was too narrow.",
        correction_reason="The sign was transcribed incorrectly.",
        expected_correction_id=None,
    )

    assert str(history.original.actual_value) == "1.25"
    assert str(history.effective.actual_value) == "-2.50"
    assert history.effective.resolved_at == RESOLVED
    assert history.effective.scoring_revision_id == scoring_revision_id
    assert history.corrections[0].old_actual_value.scaled_value == 125
    assert history.corrections[0].new_actual_value.scaled_value == -250
    source = AnalyticsRepository(database).get_numeric_source()
    assert len(source.observations) == 1
    assert str(source.observations[0].actual_value) == "-2.50"
    assert source.observations[0].scoring_revision_id == scoring_revision_id
    assert source.observations[0].actual_value_corrected is True
    scorecard = operations.get_prediction_scorecard(resolved.prediction_id)
    assert scorecard is not None
    assert scorecard.scoring_revision_id == scoring_revision_id
    assert str(scorecard.actual_value) == "-2.50"
    assert scorecard.contained is True
    assert scorecard.actual_value_corrected is True
    assert operations.get_forecast_analytics().numeric.scored_prediction_count == 1

    with pytest.raises(ValidationError) as precision_error:
        operations.correct_numeric_resolution(
            resolved.prediction_id,
            "1.234",
            resolution_notes="Corrected measurement",
            postmortem="The lower tail was too narrow.",
            correction_reason="Another correction",
            expected_correction_id=history.current_correction_id,
        )
    assert precision_error.value.field == "actual_value"
    database.close()


def test_invalidation_reason_correction_is_append_only_for_both_types(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(CREATED), UTC)
    binary = operations.create_prediction("Will this remain meaningful?", 50)
    numeric = operations.create_numeric_prediction(
        "How many meaningful units?",
        "units",
        0,
        1,
        2,
        3,
        80,
    )
    terminal = PredictionOperations(database, FixedClock(RESOLVED), UTC)
    binary_invalid = terminal.invalidate_prediction(
        binary.prediction_id,
        reason="Original reason",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    numeric_invalid = terminal.invalidate_numeric_prediction(
        numeric.prediction_id,
        reason=None,
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    corrections = PredictionOperations(database, FixedClock(CORRECTED), UTC)

    binary_history = corrections.correct_invalidation_reason(
        binary_invalid.prediction_id,
        "The event was cancelled.",
        expected_correction_id=None,
    )
    numeric_history = corrections.correct_invalidation_reason(
        numeric_invalid.prediction_id,
        "The quantity became undefined.",
        expected_correction_id=None,
    )

    assert binary_history.original.reason == "Original reason"
    assert binary_history.effective.reason == "The event was cancelled."
    assert numeric_history.original.reason is None
    assert numeric_history.effective.reason == "The quantity became undefined."
    assert binary_history.effective.invalidated_at == RESOLVED
    assert numeric_history.effective.invalidated_at == RESOLVED
    database.close()


def test_unresolved_and_invalid_predictions_have_no_scorecard(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(CREATED), UTC)
    open_prediction = operations.create_prediction("Will this remain open?", 50)
    invalid_candidate = operations.create_prediction("Will this be invalid?", 50)
    invalid = operations.invalidate_prediction(
        invalid_candidate.prediction_id,
        reason="The premise was withdrawn.",
        expected_revision_id=invalid_candidate.current_revision_id,
        expected_metadata_version=invalid_candidate.metadata_version,
    )

    assert operations.get_prediction_scorecard(open_prediction.prediction_id) is None
    assert operations.get_prediction_scorecard(invalid.prediction_id) is None
    database.close()


def test_postmortem_skip_requires_a_blank_resolved_postmortem(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    blank = _resolved_binary(database)
    with_postmortem = _resolved_binary(database, postmortem="Already reflected.")
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)

    completion = operations.record_postmortem_skip(
        blank.prediction_id,
        expected_correction_id=None,
    )

    assert completion.completed_at == CORRECTED
    history = operations.get_binary_resolution_history(blank.prediction_id)
    assert history.postmortem_completion == completion
    assert history.effective.postmortem is None
    later_reflection = operations.correct_binary_resolution(
        blank.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Original source",
        postmortem="I returned to this reflection later.",
        expected_correction_id=None,
    )
    assert later_reflection.postmortem_completion == completion
    assert later_reflection.effective.postmortem == (
        "I returned to this reflection later."
    )
    with pytest.raises(PostmortemCompletionNotAllowedError) as repeated:
        operations.record_postmortem_skip(
            blank.prediction_id,
            expected_correction_id=later_reflection.current_correction_id,
        )
    assert repeated.value.reason == "already_completed"
    with pytest.raises(PostmortemCompletionNotAllowedError) as nonblank:
        operations.record_postmortem_skip(
            with_postmortem.prediction_id,
            expected_correction_id=None,
        )
    assert nonblank.value.reason == "has_postmortem"
    database.close()


def test_database_failure_rolls_back_entire_correction(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    resolved = _resolved_binary(database)
    with database.transaction() as connection:
        connection.execute(
            """
            CREATE TRIGGER fail_m26_correction
            AFTER INSERT ON resolution_corrections
            BEGIN SELECT RAISE(ABORT, 'forced correction failure'); END
            """
        )

    with pytest.raises(sqlite3.IntegrityError, match="forced correction failure"):
        PredictionOperations(
            database, FixedClock(CORRECTED), UTC
        ).correct_binary_resolution(
            resolved.prediction_id,
            BinaryOutcome.YES,
            resolution_notes="Would have changed",
            postmortem=None,
            correction_reason="Required reason",
            expected_correction_id=None,
        )

    history = PredictionOperations(database).get_binary_resolution_history(
        resolved.prediction_id
    )
    assert history.corrections == ()
    assert history.effective.outcome is BinaryOutcome.NO
    database.close()
