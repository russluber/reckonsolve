import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.domain.predictions import BinaryOutcome


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = datetime(2026, 8, 23, 19, 30, tzinfo=UTC)

    def now(self) -> datetime:
        return self.instant


def test_v11_upgrade_preserves_v10_binary_terminal_and_numeric_history(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:10])
    operations = PredictionOperations(old, FixedClock(), UTC)
    binary = operations.create_prediction("Will Binary history survive?", 65)
    operations.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    with old.transaction() as connection:
        numeric_cursor = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at,
                numeric_unit, numeric_precision
            ) VALUES (?, 'numeric', 'open', ?, ?, 'days', 0)
            """,
            (
                "How many days will migration take?",
                "2026-08-23T19:30:00.000000Z",
                "2026-08-23T19:30:00.000000Z",
            ),
        )
        numeric_id = int(numeric_cursor.lastrowid)
        revision_cursor = connection.execute(
            """
            INSERT INTO numeric_forecast_revisions (
                prediction_id, lower_scaled, median_scaled, upper_scaled,
                confidence_percent, created_at, sequence
            ) VALUES (?, 2, 4, 8, 80, ?, 1)
            """,
            (numeric_id, "2026-08-23T19:30:00.000000Z"),
        )
        connection.execute(
            """
            INSERT INTO journal_entries (
                prediction_id, numeric_forecast_revision_id, body, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (
                numeric_id,
                int(revision_cursor.lastrowid),
                "Preserve this Numeric Journal entry.",
                "2026-08-23T19:30:00.000000Z",
            ),
        )
    old.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:11])
    recovered = PredictionOperations(upgraded, FixedClock(), UTC)

    assert upgraded.schema_version == 11
    assert recovered.get_prediction(binary.prediction_id).resolution is not None
    assert recovered.get_numeric_prediction(numeric_id).question == (
        "How many days will migration take?"
    )
    assert len(recovered.list_numeric_timeline(numeric_id)) == 2
    with upgraded.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )
    upgraded.close()


def test_failing_v11_rolls_back_table_and_trigger_changes(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:10]).close()
    broken = Migration(
        version=11,
        name="broken numeric lifecycle migration",
        statements=(
            "DROP TRIGGER predictions_status_requires_terminal_record",
            "CREATE TABLE numeric_resolutions (id INTEGER PRIMARY KEY) STRICT",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:10], broken))

    recovered = Database.open(path, migrations=MIGRATIONS[:10])
    assert recovered.schema_version == 10
    with recovered.transaction() as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'numeric_resolutions'"
            ).fetchone()
            is None
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name = 'predictions_status_requires_terminal_record'"
            ).fetchone()
            is not None
        )
    recovered.close()
