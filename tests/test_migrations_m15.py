import sqlite3

import pytest

from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration


def test_v15_upgrade_adds_saved_views_without_changing_v14_data(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    v14 = Database.open(path, migrations=MIGRATIONS[:14])
    v14.close()

    upgraded = Database.open(path)

    assert upgraded.schema_version == 15
    with upgraded.transaction() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'table'"
            ).fetchall()
        }
        connection.execute(
            """
            INSERT INTO saved_views (
                display_name, normalized_name, search_text, match_mode,
                include_superseded, status, prediction_type, tag_match_mode,
                attention, date_meaning, date_start, date_end, sort
            ) VALUES (
                'Locked focus', 'locked focus', '', 'all', 0, 'locked', NULL,
                'all', NULL, 'created', NULL, NULL, 'created_newest'
            )
            """
        )
    assert {"saved_views", "saved_view_tags"}.issubset(tables)
    upgraded.close()


def test_failing_v15_migration_rolls_back_saved_view_schema(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:14]).close()
    broken_v15 = Migration(
        version=15,
        name=MIGRATIONS[14].name,
        statements=(
            *MIGRATIONS[14].statements,
            "INSERT INTO table_that_does_not_exist DEFAULT VALUES",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:14], broken_v15))

    reopened = Database.open(path, migrations=MIGRATIONS[:14])
    assert reopened.schema_version == 14
    with reopened.transaction() as connection:
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_schema WHERE name = 'saved_views'"
            ).fetchone()
            is None
        )
    reopened.close()
