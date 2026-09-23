import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from supported_fixtures import create_binary

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


def test_v13_upgrade_of_empty_archive_preserves_schema_path(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:12])
    with old.transaction() as connection:
        connection.execute("CREATE TABLE sentinel(value TEXT NOT NULL)")
        connection.execute("INSERT INTO sentinel VALUES ('preserved')")
    old.close()
    upgraded = Database.open(path, migrations=MIGRATIONS[:13])
    assert upgraded.schema_version == 13
    with upgraded.transaction() as connection:
        assert (
            connection.execute("SELECT value FROM sentinel").fetchone()[0]
            == "preserved"
        )
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
    created = create_binary(operations, "Will constraints hold?", 60)
    resolved = operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.NO,
        resolution_notes="Original",
        use_recorded_time=True,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    assert resolved.resolution is not None
    resolution_id = resolved.resolution.resolution_id
    with database.transaction() as connection:
        correction_id = int(
            connection.execute(
                """
                INSERT INTO binary_trajectory_resolution_corrections (
                    prediction_id, resolution_id, sequence,
                    old_outcome, new_outcome,
                    old_resolution_notes, new_resolution_notes,
                    old_postmortem, new_postmortem,
                    outcome_changed, resolution_notes_changed,
                    postmortem_changed, correction_reason, old_effective_resolution_at, new_effective_resolution_at, effective_time_changed, corrected_at
                ) VALUES (?, ?, 1, 'no', 'yes', 'Original', 'Corrected',
                          NULL, NULL, 1, 1, 0, 'Certified outcome', '2026-08-26T18:00:00.000000Z', '2026-08-26T18:00:00.000000Z', 0, ?)
                """,
                (created.prediction_id, resolution_id, STAMP_TEXT),
            ).lastrowid
        )

    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "UPDATE binary_trajectory_resolution_corrections SET new_outcome = 'no' WHERE id = ?",
            (correction_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
        database.transaction() as connection,
    ):
        connection.execute(
            "DELETE FROM binary_trajectory_resolution_corrections WHERE id = ?",
            (correction_id,),
        )
    with (
        pytest.raises(sqlite3.IntegrityError, match="current snapshot"),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO binary_trajectory_resolution_corrections (
                prediction_id, resolution_id, sequence,
                old_outcome, new_outcome,
                old_resolution_notes, new_resolution_notes,
                old_postmortem, new_postmortem,
                outcome_changed, resolution_notes_changed,
                postmortem_changed, correction_reason, old_effective_resolution_at, new_effective_resolution_at, effective_time_changed, corrected_at
            ) VALUES (?, ?, 2, 'no', 'yes', 'Original', 'Another',
                      NULL, NULL, 1, 1, 0, 'Stale snapshot', '2026-08-26T18:00:00.000000Z', '2026-08-26T18:00:00.000000Z', 0, ?)
            """,
            (created.prediction_id, resolution_id, STAMP_TEXT),
        )
    with (
        pytest.raises(
            sqlite3.IntegrityError, match="invalid trajectory resolution correction"
        ),
        database.transaction() as connection,
    ):
        connection.execute(
            """
            INSERT INTO binary_trajectory_resolution_corrections (
                prediction_id, resolution_id, sequence,
                old_outcome, new_outcome,
                old_resolution_notes, new_resolution_notes,
                old_postmortem, new_postmortem,
                outcome_changed, resolution_notes_changed,
                postmortem_changed, correction_reason, old_effective_resolution_at, new_effective_resolution_at, effective_time_changed, corrected_at
            ) VALUES (?, ?, 3, 'yes', 'yes', 'Corrected', 'Next',
                      NULL, NULL, 0, 1, 0, NULL, '2026-08-26T18:00:00.000000Z', '2026-08-26T18:00:00.000000Z', 0, ?)
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
                "SELECT 1 FROM binary_trajectory_resolution_corrections WHERE id = ?",
                (correction_id,),
            ).fetchone()
            is None
        )
    database.close()
