import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.domain.predictions import BinaryOutcome

STAMP = datetime(2026, 8, 26, 18, tzinfo=UTC)
STAMP_TEXT = "2026-08-26T18:00:00.000000Z"


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = STAMP

    def now(self) -> datetime:
        return self.instant


def test_v13_upgrade_preserves_v12_terminal_data_and_adds_empty_histories(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:12])
    operations = PredictionOperations(old, FixedClock(), UTC)
    binary = operations.create_prediction("Will Binary Resolution survive?", 65)
    resolved_binary = operations.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Preserve Binary provenance",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    numeric = operations.create_numeric_prediction(
        "What Numeric value will survive?",
        "units",
        2,
        "1.00",
        "2.00",
        "3.00",
        80,
    )
    resolved_numeric = operations.resolve_numeric_prediction(
        numeric.prediction_id,
        "2.50",
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    invalid = operations.create_prediction("Will Invalidation survive?", 40)
    invalidated = operations.invalidate_prediction(
        invalid.prediction_id,
        reason="Preserve this reason",
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    old.close()

    upgraded = Database.open(path)
    recovered = PredictionOperations(upgraded, FixedClock(), UTC)

    assert upgraded.schema_version == 13
    binary_history = recovered.get_binary_resolution_history(
        resolved_binary.prediction_id
    )
    numeric_history = recovered.get_numeric_resolution_history(
        resolved_numeric.prediction_id
    )
    invalidation_history = recovered.get_invalidation_history(invalidated.prediction_id)
    assert binary_history.original.outcome is BinaryOutcome.YES
    assert binary_history.original.resolution_notes == "Preserve Binary provenance"
    assert binary_history.corrections == ()
    assert str(numeric_history.original.actual_value) == "2.50"
    assert numeric_history.corrections == ()
    assert invalidation_history.original.reason == "Preserve this reason"
    assert invalidation_history.corrections == ()
    with upgraded.transaction() as connection:
        for table in (
            "resolution_corrections",
            "numeric_resolution_corrections",
            "invalidation_reason_corrections",
            "postmortem_completions",
        ):
            assert (
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
            )
    upgraded.close()


def test_failing_v13_rolls_back_every_terminal_history_schema_change(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:12]).close()
    broken = Migration(
        version=13,
        name="broken terminal correction migration",
        statements=(
            "CREATE TABLE resolution_corrections (id INTEGER PRIMARY KEY) STRICT",
            "CREATE TABLE postmortem_completions (id INTEGER PRIMARY KEY) STRICT",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:12], broken))

    recovered = Database.open(path, migrations=MIGRATIONS[:12])
    assert recovered.schema_version == 12
    with recovered.transaction() as connection:
        for name in ("resolution_corrections", "postmortem_completions"):
            assert (
                connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE name = ?",
                    (name,),
                ).fetchone()
                is None
            )
    recovered.close()


def test_binary_correction_table_rejects_rewrite_gaps_and_stale_snapshots(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    created = operations.create_prediction("Will constraints hold?", 60)
    resolved = operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Original",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    assert resolved.resolution is not None
    resolution_id = resolved.resolution.resolution_id
    with database.transaction() as connection:
        correction_id = int(
            connection.execute(
                """
                INSERT INTO resolution_corrections (
                    prediction_id, resolution_id, sequence,
                    old_outcome, new_outcome,
                    old_resolution_notes, new_resolution_notes,
                    old_postmortem, new_postmortem,
                    outcome_changed, resolution_notes_changed,
                    postmortem_changed, correction_reason, corrected_at
                ) VALUES (?, ?, 1, 'no', 'yes', 'Original', 'Corrected',
                          NULL, NULL, 1, 1, 0, 'Certified outcome', ?)
                """,
                (created.prediction_id, resolution_id, STAMP_TEXT),
            ).lastrowid
        )

    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE resolution_corrections SET new_outcome = 'no' WHERE id = ?",
            (correction_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "DELETE FROM resolution_corrections WHERE id = ?",
            (correction_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="current snapshot"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO resolution_corrections (
                prediction_id, resolution_id, sequence,
                old_outcome, new_outcome,
                old_resolution_notes, new_resolution_notes,
                old_postmortem, new_postmortem,
                outcome_changed, resolution_notes_changed,
                postmortem_changed, correction_reason, corrected_at
            ) VALUES (?, ?, 2, 'no', 'yes', 'Original', 'Another',
                      NULL, NULL, 1, 1, 0, 'Stale snapshot', ?)
            """,
            (created.prediction_id, resolution_id, STAMP_TEXT),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="contiguous"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO resolution_corrections (
                prediction_id, resolution_id, sequence,
                old_outcome, new_outcome,
                old_resolution_notes, new_resolution_notes,
                old_postmortem, new_postmortem,
                outcome_changed, resolution_notes_changed,
                postmortem_changed, correction_reason, corrected_at
            ) VALUES (?, ?, 3, 'yes', 'yes', 'Corrected', 'Next',
                      NULL, NULL, 0, 1, 0, NULL, ?)
            """,
            (created.prediction_id, resolution_id, STAMP_TEXT),
        )

    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM predictions WHERE id = ?",
            (created.prediction_id,),
        )
        assert (
            connection.execute(
                "SELECT 1 FROM resolution_corrections WHERE id = ?",
                (correction_id,),
            ).fetchone()
            is None
        )
    database.close()
