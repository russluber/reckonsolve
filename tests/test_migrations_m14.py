import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.data.search_index import SearchIndexUnavailableError
from reckonsolve.domain.search import SearchSourceKind

STAMP = datetime(2026, 8, 27, 18, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = STAMP

    def now(self) -> datetime:
        return self.instant


def test_v14_upgrade_preserves_v13_data_and_builds_search_projection(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old = Database.open(path, migrations=MIGRATIONS[:13])
    created = PredictionOperations(old, FixedClock(), UTC).create_prediction(
        "Will the migration preserve this launch forecast?",
        65,
        rationale="The launch permit was approved.",
        tags=("Spaceflight",),
    )
    old.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:14])
    operations = PredictionOperations(upgraded, FixedClock(), UTC)

    assert upgraded.schema_version == 14
    results = operations.search_predictions("launch permit")
    assert [hit.prediction.prediction_id for hit in results.hits] == [
        created.prediction_id
    ]
    assert results.hits[0].best_match.document.source_kind in {
        SearchSourceKind.QUESTION,
        SearchSourceKind.FORECAST_RATIONALE,
    }
    upgraded.check_search_index()
    upgraded.close()


def test_failing_v14_rolls_back_every_search_schema_change(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:13]).close()
    broken = Migration(
        version=14,
        name="broken search migration",
        statements=(
            "CREATE TABLE search_index_state (id INTEGER PRIMARY KEY) STRICT",
            "CREATE VIRTUAL TABLE prediction_search USING fts5(body)",
            "THIS IS NOT VALID SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:13], broken))

    recovered = Database.open(path, migrations=MIGRATIONS[:13])
    assert recovered.schema_version == 13
    with recovered.transaction() as connection:
        for name in ("search_index_state", "prediction_search"):
            assert (
                connection.execute(
                    "SELECT 1 FROM sqlite_schema WHERE name = ?", (name,)
                ).fetchone()
                is None
            )
    recovered.close()


def test_v14_creates_versioned_projection_and_update_triggers(tmp_path) -> None:
    database = Database.open(
        tmp_path / "reckonsolve.sqlite3", migrations=MIGRATIONS[:14]
    )

    with database.transaction() as connection:
        state = connection.execute(
            """
            SELECT projection_version, document_count
            FROM search_index_state
            WHERE singleton_id = 1
            """
        ).fetchone()
        objects = {
            str(row[0])
            for row in connection.execute(
                """
                SELECT name FROM sqlite_schema
                WHERE name IN (
                    'prediction_search', 'prediction_search_vocabulary',
                    'search_dirty_after_prediction_update',
                    'search_dirty_after_journal_correction_insert',
                    'search_dirty_after_binary_resolution_correction_insert'
                )
                """
            ).fetchall()
        }

    assert tuple(state) == (1, 0)
    assert objects == {
        "prediction_search",
        "prediction_search_vocabulary",
        "search_dirty_after_prediction_update",
        "search_dirty_after_journal_correction_insert",
        "search_dirty_after_binary_resolution_correction_insert",
    }
    database.close()


def test_v14_startup_reports_an_explicit_missing_fts5_capability(
    tmp_path, monkeypatch
) -> None:
    def unavailable(_connection) -> None:
        raise SearchIndexUnavailableError("FTS5 is unavailable in this runtime.")

    monkeypatch.setattr("reckonsolve.data.database.require_fts5", unavailable)

    with pytest.raises(SearchIndexUnavailableError, match="FTS5 is unavailable"):
        Database.open(tmp_path / "reckonsolve.sqlite3", migrations=MIGRATIONS[:14])
