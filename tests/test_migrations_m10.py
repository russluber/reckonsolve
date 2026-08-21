import sqlite3
from datetime import UTC, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.domain.predictions import JournalTimelineEvent


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 21, 19, 30, tzinfo=UTC)


def test_v10_upgrade_preserves_binary_journal_and_correction_history(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old_database = Database.open(path, migrations=MIGRATIONS[:9])
    old_operations = PredictionOperations(old_database, FixedClock(), UTC)
    created = old_operations.create_prediction("Will the journal migrate?", 60)
    entry = old_operations.add_journal_entry(
        created.prediction_id,
        "Original observation.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    old_operations.correct_journal_entry(
        created.prediction_id,
        entry.entry_id,
        "Corrected observation.",
        expected_correction_id=None,
    )
    old_database.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:10])
    operations = PredictionOperations(upgraded, FixedClock(), UTC)
    timeline = operations.list_timeline(created.prediction_id)
    journal = next(
        event for event in timeline if isinstance(event, JournalTimelineEvent)
    )

    assert upgraded.schema_version == 10
    assert journal.body == "Corrected observation."
    assert journal.original_body == "Original observation."
    assert len(journal.corrections) == 1
    with upgraded.transaction() as connection:
        anchors = connection.execute(
            """
            SELECT forecast_revision_id, numeric_forecast_revision_id
            FROM journal_entries WHERE id = ?
            """,
            (entry.entry_id,),
        ).fetchone()
    assert anchors[0] == created.current_revision_id
    assert anchors[1] is None
    upgraded.close()


def test_failing_v10_rolls_back_rebuilt_journal_schema_and_history(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:9]).close()
    broken_v10 = Migration(
        version=10,
        name="broken type-aware journal migration",
        statements=(
            "ALTER TABLE journal_entries RENAME TO journal_entries_v9",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:9], broken_v10))

    recovered = Database.open(path, migrations=MIGRATIONS[:9])
    assert recovered.schema_version == 9
    with recovered.transaction() as connection:
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'journal_entries'"
            ).fetchone()
            is not None
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'journal_entries_v9'"
            ).fetchone()
            is None
        )
    recovered.close()
