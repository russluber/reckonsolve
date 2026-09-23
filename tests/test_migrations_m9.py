import sqlite3
from datetime import UTC, datetime

import pytest
from supported_fixtures import create_binary, create_numeric

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.data.numeric_predictions import NumericPredictionRepository

TIMESTAMP = "2026-08-20T20:00:00.000000Z"


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 20, 20, tzinfo=UTC)


def new_numeric_prediction(operations):
    return create_numeric(
        operations,
        "How many days?",
        "days",
        2,
        {5: "-1.25", 25: "0.00", 50: "4.00", 75: "8.00", 95: "12.75"},
        rationale="Initial quantiles",
    )


def test_v9_upgrade_of_empty_database_preserves_migration_path(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:8]).close()
    upgraded = Database.open(path, migrations=MIGRATIONS[:9])
    assert upgraded.schema_version == 9
    with upgraded.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(predictions)")
        }
        assert {"prediction_type", "numeric_unit", "numeric_precision"} <= columns
    upgraded.close()


def test_v9_enforces_type_specific_definitions_and_revision_ownership(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    numeric = new_numeric_prediction(PredictionOperations(database, FixedClock()))
    binary = create_binary(
        PredictionOperations(database, FixedClock()),
        "Will this stay binary?",
        60,
    )

    for statement, parameters in (
        (
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            )
            VALUES ('Missing numeric definition', 'numeric', 'open', ?, ?)
            """,
            (TIMESTAMP, TIMESTAMP),
        ),
        (
            """
            INSERT INTO numeric_forecast_revisions (
                prediction_id, lower_scaled, median_scaled, upper_scaled,
                confidence_percent, created_at, sequence, rationale
            )
            VALUES (?, 1, 2, 3, 80, ?, 2, NULL)
            """,
            (binary.prediction_id, TIMESTAMP),
        ),
        (
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence, rationale
            )
            VALUES (?, 50, ?, 2, NULL)
            """,
            (numeric.prediction_id, TIMESTAMP),
        ),
    ):
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as connection,
        ):
            connection.execute(statement, parameters)

    database.close()


@pytest.mark.parametrize(
    "values",
    [
        (1, 2, 3, 80),  # Even a valid retired interval cannot anchor a v0.7 forecast.
        (2, 1, 3, 80),
        (1, 4, 3, 80),
        (1, 2, 3, 0),
        (1, 2, 3, 100),
        (-1_000_000_000_000_000_000, 0, 1, 80),
    ],
)
def test_v9_retained_interval_table_rejects_rows_for_quantile_predictions(
    tmp_path,
    values: tuple[int, int, int, int],
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    numeric = new_numeric_prediction(PredictionOperations(database, FixedClock()))
    lower, median, upper, confidence = values

    with pytest.raises(sqlite3.IntegrityError), database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO numeric_forecast_revisions (
                prediction_id, lower_scaled, median_scaled, upper_scaled,
                confidence_percent, created_at, sequence, rationale
            )
            VALUES (?, ?, ?, ?, ?, ?, 2, NULL)
            """,
            (
                numeric.prediction_id,
                lower,
                median,
                upper,
                confidence,
                TIMESTAMP,
            ),
        )

    database.close()


def test_v9_numeric_definition_and_revision_history_are_immutable(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    repository = NumericPredictionRepository(database)
    numeric = new_numeric_prediction(PredictionOperations(database, FixedClock()))
    revision = numeric.current_revision

    for statement, parameters in (
        (
            "UPDATE predictions SET numeric_unit = 'hours' WHERE id = ?",
            (numeric.prediction_id,),
        ),
        (
            "UPDATE numeric_quantile_revisions SET q50_scaled = 500 WHERE id = ?",
            (revision.revision_id,),
        ),
        (
            "DELETE FROM numeric_quantile_revisions WHERE id = ?",
            (revision.revision_id,),
        ),
        (
            """
            INSERT OR REPLACE INTO numeric_quantile_revisions (
                id, prediction_id, q05_scaled, q25_scaled, q50_scaled,
                q75_scaled, q95_scaled, created_at, sequence, rationale
            )
            VALUES (?, ?, -100, 0, 500, 800, 1300, ?, 1, NULL)
            """,
            (revision.revision_id, numeric.prediction_id, TIMESTAMP),
        ),
    ):
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as connection,
        ):
            connection.execute(statement, parameters)

    assert repository.get_prediction(numeric.prediction_id) == numeric

    with database.transaction() as connection:
        connection.execute(
            "DELETE FROM predictions WHERE id = ?",
            (numeric.prediction_id,),
        )
    assert repository.get_prediction(numeric.prediction_id) is None
    database.close()


def test_failing_v9_rolls_back_schema_and_migration_history(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:8]).close()
    broken_v9 = Migration(
        version=9,
        name="broken numeric foundation",
        statements=(
            """
            ALTER TABLE predictions
            RENAME COLUMN prediction_type TO prediction_type_binary_legacy
            """,
            """
            ALTER TABLE predictions
            ADD COLUMN prediction_type TEXT NOT NULL DEFAULT 'binary'
            """,
            "THIS IS NOT SQL",
        ),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:8], broken_v9))

    connection = sqlite3.connect(path)
    try:
        version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        columns = tuple(
            row[1] for row in connection.execute("PRAGMA table_info(predictions)")
        )
        numeric_table = connection.execute(
            """
            SELECT 1 FROM sqlite_schema
            WHERE type = 'table' AND name = 'numeric_forecast_revisions'
            """
        ).fetchone()
    finally:
        connection.close()

    assert version == 8
    assert "prediction_type" in columns
    assert "prediction_type_binary_legacy" not in columns
    assert "numeric_unit" not in columns
    assert numeric_table is None
