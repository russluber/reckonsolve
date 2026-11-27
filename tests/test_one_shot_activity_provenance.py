"""Canonical reflection provenance retains full replay and unchanged scores."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest
from supported_fixtures import journal_migrations

from reckonsolve.application.errors import ApplicationError, ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotSourceAction,
    OneShotValues,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)


@dataclass
class Clock:
    instant: datetime = datetime(2026, 11, 1, tzinfo=UTC)

    def now(self):
        return self.instant


@pytest.mark.parametrize("kind", tuple(PredictionType))
def test_postmortem_action_retains_originals_replay_and_pure_score(tmp_path, kind):
    database = Database.open(
        tmp_path / "activity.sqlite3", migrations=journal_migrations()
    )
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    numeric = kind is PredictionType.NUMERIC
    values = OneShotValues(
        probability_percent=None if numeric else 70,
        quantiles=FiveQuantiles.from_values({5: -2, 25: -1, 50: 0, 75: 1, 95: 2}, 0)
        if numeric
        else None,
        answer=FixedPrecisionValue(1, 0) if numeric else BinaryOutcome.YES,
    )
    try:
        original = operations.one_shots.create(
            NewOneShotPrediction(
                "Reflection provenance",
                one_shot_contract(kind),
                values,
                QuantileDefinition("units", 0, NumericValueConstraint.WHOLE_NUMBER)
                if numeric
                else None,
            )
        )
        score = operations.one_shots.score(original)
        clock.instant += timedelta(minutes=1)
        written = operations.one_shots.save_postmortem(original, "New reflection")
        assert written.record.original == original.record.original
        assert (
            written.record.corrections[-1].source_action
            is OneShotSourceAction.POSTMORTEM
        )
        assert written.record.corrections[-1].before.postmortem is None
        assert operations.one_shots.score(written) == score
        clock.instant += timedelta(minutes=1)
        repaired = operations.one_shots.correct(
            written, replace(written.record.effective, postmortem="Repaired text")
        )
        assert (
            repaired.record.corrections[-1].source_action
            is OneShotSourceAction.TRANSCRIPTION
        )
        with pytest.raises(ApplicationError, match="Confirm clearing"):
            operations.one_shots.save_postmortem(repaired, None)
        assert (
            len(operations.one_shots.get(original.prediction_id).record.corrections)
            == 2
        )
        clock.instant += timedelta(minutes=1)
        cleared = operations.one_shots.save_postmortem(
            repaired, None, confirm_clear=True
        )
        assert cleared.record.effective.postmortem is None
        assert (
            cleared.record.corrections[-1].source_action
            is OneShotSourceAction.POSTMORTEM
        )
        assert operations.one_shots.score(cleared) == score
        saved_id = original.prediction_id
        path = database.path
    finally:
        database.close()
    restarted = Database.open(path, migrations=journal_migrations())
    try:
        replay = PredictionOperations(restarted, clock, UTC).one_shots.get(saved_id)
        assert replay.record == cleared.record
        assert replay.record.original == original.record.original
    finally:
        restarted.close()


def test_reflection_provenance_cannot_disguise_forecast_changes(tmp_path):
    database = Database.open(
        tmp_path / "guard.sqlite3", migrations=journal_migrations()
    )
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    try:
        original = operations.one_shots.create(
            NewOneShotPrediction(
                "No disguised repair",
                one_shot_contract(PredictionType.BINARY),
                OneShotValues(probability_percent=70, answer=BinaryOutcome.YES),
            )
        )
        clock.instant += timedelta(minutes=1)
        with pytest.raises(ValidationError, match="reflection alone"):
            operations.one_shots._perform(
                lambda: operations.one_shots.repository.correct_detail(
                    original.record,
                    replace(
                        original.record.effective,
                        probability_percent=80,
                        postmortem="Mixed facts",
                    ),
                    source_action=OneShotSourceAction.POSTMORTEM,
                )
            )
        assert (
            operations.one_shots.get(original.prediction_id).record == original.record
        )
    finally:
        database.close()


@pytest.mark.parametrize("kind", tuple(PredictionType))
def test_cleared_one_shot_reflection_cross_surface_skip_and_readd(tmp_path, kind):
    from test_journal_retrieval import create

    from reckonsolve.domain.browser import ArchiveAttention
    from reckonsolve.domain.journal import JournalRequest, JournalView

    path = tmp_path / "reflection.sqlite3"
    clock = Clock()
    database = Database.open(path)
    operations = PredictionOperations(database, clock, UTC)
    try:
        original = create(operations, kind, one_shot=True, answered=True)
        clock.instant += timedelta(minutes=1)
        written = operations.one_shots.save_postmortem(original, "Original reflection")
        score = operations.one_shots.score(written)
        activity = operations.journal.query(JournalRequest()).rows[0].last_active
        clock.instant += timedelta(minutes=1)
        cleared = operations.one_shots.save_postmortem(
            written, None, confirm_clear=True
        )

        def check(reader):
            scope = {"attention": ArchiveAttention.NEEDS_POSTMORTEM}
            assert len(reader.browse_predictions(**scope).predictions) == 1
            assert len(reader.search_predictions("marker", **scope).hits) == 1
            page = reader.journal.query(
                JournalRequest(view=JournalView.NEEDS_POSTMORTEM)
            )
            assert page.total == 1 and page.rows[0].last_active == activity
            assert (
                reader.one_shots.score(reader.one_shots.get(original.prediction_id))
                == score
            )

        check(operations)
        independent = Database.open(path)
        try:
            check(PredictionOperations(independent, clock, UTC))
        finally:
            independent.close()
        clock.instant += timedelta(minutes=1)
        rewritten = operations.one_shots.save_postmortem(
            cleared, "Later deliberate reflection"
        )
        assert (
            operations.journal.query(JournalRequest()).rows[0].last_active
            == clock.instant
        )
        clock.instant += timedelta(minutes=1)
        cleared = operations.one_shots.save_postmortem(
            rewritten, None, confirm_clear=True
        )
        activity = operations.journal.query(JournalRequest()).rows[0].last_active
        clock.instant += timedelta(minutes=1)
        skipped = operations.one_shots.skip_postmortem(cleared)
        assert (
            operations.journal.query(
                JournalRequest(view=JournalView.NEEDS_POSTMORTEM)
            ).total
            == 0
        )
        assert (
            operations.journal.query(JournalRequest()).rows[0].last_active == activity
        )
        assert skipped.record.original == original.record.original
        assert operations.one_shots.score(skipped) == score
    finally:
        database.close()
    restarted = Database.open(path)
    try:
        reader = PredictionOperations(restarted, clock, UTC)
        assert (
            reader.journal.query(
                JournalRequest(view=JournalView.NEEDS_POSTMORTEM)
            ).total
            == 0
        )
        assert (
            reader.one_shots.get(original.prediction_id).postmortem_completion
            is not None
        )
    finally:
        restarted.close()
