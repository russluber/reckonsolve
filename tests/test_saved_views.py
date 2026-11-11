import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from supported_fixtures import create_binary

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = datetime(2026, 8, 28, 12, tzinfo=UTC)

    def now(self):
        return self.instant


def test_schema_20_upgrade_keeps_existing_saved_view_and_tag_reference(
    tmp_path,
) -> None:
    path = tmp_path / "schema19.sqlite3"
    database = Database.open(path, migrations=MIGRATIONS[:19])
    operations = PredictionOperations(database, FixedClock(), UTC)
    prediction = create_binary(
        operations, "Will this view survive?", 50, tags=("Work",)
    )
    with database.transaction() as connection:
        view_id = connection.execute(
            """
            INSERT INTO saved_views (
                display_name, normalized_name, search_text, match_mode,
                include_superseded, tag_match_mode, date_meaning, sort
            ) VALUES ('Work', 'work', '', 'all', 0, 'all', 'created',
                      'created_newest')
            """
        ).lastrowid
        tag_id = connection.execute(
            "SELECT id FROM tags WHERE normalized_name = 'work'"
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO saved_view_tags (saved_view_id, tag_id) VALUES (?, ?)",
            (view_id, tag_id),
        )
        original = tuple(
            connection.execute(
                "SELECT * FROM saved_views WHERE id = ?", (view_id,)
            ).fetchone()
        )
    database.close()

    upgraded = Database.open(path, migrations=MIGRATIONS[:20])
    try:
        assert upgraded.schema_version == 20
        with upgraded.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM saved_views WHERE id = ?", (view_id,)
            ).fetchone()
            assert tuple(row) == (*original, None)
            assert not connection.execute("PRAGMA foreign_key_check").fetchall()
        reopened = PredictionOperations(upgraded, FixedClock(), UTC)
        assert (
            reopened.browse_predictions(tags=("Work",)).predictions[0].prediction_id
            == prediction.prediction_id
        )
        with upgraded.read_snapshot() as connection:
            assert (
                connection.execute(
                    "SELECT tag_id FROM saved_view_tags WHERE saved_view_id = ?",
                    (view_id,),
                ).fetchone()[0]
                == tag_id
            )
    finally:
        upgraded.close()


def test_schema_20_failure_rolls_back_saved_view_column(tmp_path) -> None:
    path = tmp_path / "rollback.sqlite3"
    database = Database.open(path, migrations=MIGRATIONS[:19])
    database.close()
    before = path.read_bytes()
    m58 = MIGRATIONS[19]
    broken = (
        *MIGRATIONS[:19],
        Migration(20, m58.name, (*m58.statements, "INVALID SQL")),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=broken)
    assert path.read_bytes() == before
    old = Database.open(path, migrations=MIGRATIONS[:19])
    try:
        assert old.schema_version == 19
        with old.transaction() as connection:
            assert "forecast_mode" not in {
                row["name"]
                for row in connection.execute("PRAGMA table_info(saved_views)")
            }
    finally:
        old.close()
