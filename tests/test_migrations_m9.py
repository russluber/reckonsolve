import sqlite3
from datetime import UTC, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.data.numeric_predictions import NumericPredictionRepository
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    JournalTimelineEvent,
    NewNumericForecastRevision,
    NewNumericPrediction,
    PredictionStatus,
)

TIMESTAMP = "2026-08-20T20:00:00.000000Z"


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 20, 20, tzinfo=UTC)


def new_numeric_prediction() -> NewNumericPrediction:
    decimal_places = 2
    return NewNumericPrediction(
        "How many days?",
        "days",
        decimal_places,
        NewNumericForecastRevision(
            FixedPrecisionValue.from_value("-1.25", decimal_places),
            FixedPrecisionValue.from_value("4.00", decimal_places),
            FixedPrecisionValue.from_value("12.75", decimal_places),
            80,
            "Initial range",
        ),
    )


def test_v9_upgrade_preserves_existing_binary_data_and_behavior(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    old_database = Database.open(path, migrations=MIGRATIONS[:8])
    old_operations = PredictionOperations(old_database, FixedClock())
    created = old_operations.create_prediction(
        "Will the v8 binary prediction survive?",
        64,
        rationale="Original binary rationale",
        tags=("migration",),
    )
    revised = old_operations.revise_forecast(
        created.prediction_id,
        71,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    old_operations.add_journal_entry(
        created.prediction_id,
        "Preserve this binary Journal history.",
        expected_revision_id=revised.current_revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    old_operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Preserve this binary Resolution.",
        expected_revision_id=revised.current_revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    old_database.close()

    upgraded = Database.open(path)
    upgraded_operations = PredictionOperations(upgraded, FixedClock())
    reopened = upgraded_operations.get_prediction(created.prediction_id)

    assert upgraded.schema_version == 9
    assert reopened.question == created.question
    assert reopened.probability_percent == 71
    assert reopened.current_revision_id == revised.current_revision_id
    assert reopened.tags == ("migration",)
    assert reopened.status is PredictionStatus.RESOLVED
    assert reopened.resolution is not None
    assert reopened.resolution.outcome is BinaryOutcome.YES
    assert reopened.resolution.resolution_notes == "Preserve this binary Resolution."
    timeline = upgraded_operations.list_timeline(created.prediction_id)
    assert any(
        isinstance(event, JournalTimelineEvent)
        and event.body == "Preserve this binary Journal history."
        for event in timeline
    )
    with upgraded.transaction() as connection:
        type_row = connection.execute(
            """
            SELECT prediction_type, numeric_unit, numeric_precision
            FROM predictions
            WHERE id = ?
            """,
            (created.prediction_id,),
        ).fetchone()
    assert tuple(type_row) == ("binary", None, None)
    upgraded.close()


def test_v9_enforces_type_specific_definitions_and_revision_ownership(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    numeric = NumericPredictionRepository(database).create_prediction(
        new_numeric_prediction(),
        FixedClock().now(),
    )
    binary = PredictionOperations(database, FixedClock()).create_prediction(
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
        (2, 1, 3, 80),
        (1, 4, 3, 80),
        (1, 2, 3, 0),
        (1, 2, 3, 100),
        (-1_000_000_000_000_000_000, 0, 1, 80),
    ],
)
def test_v9_numeric_revision_constraints_reject_invalid_rows(
    tmp_path,
    values: tuple[int, int, int, int],
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    numeric = NumericPredictionRepository(database).create_prediction(
        new_numeric_prediction(),
        FixedClock().now(),
    )
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
    numeric = repository.create_prediction(new_numeric_prediction(), FixedClock().now())
    revision = numeric.current_revision

    for statement, parameters in (
        (
            "UPDATE predictions SET numeric_unit = 'hours' WHERE id = ?",
            (numeric.prediction_id,),
        ),
        (
            "UPDATE numeric_forecast_revisions SET median_scaled = 500 WHERE id = ?",
            (revision.revision_id,),
        ),
        (
            "DELETE FROM numeric_forecast_revisions WHERE id = ?",
            (revision.revision_id,),
        ),
        (
            """
            INSERT OR REPLACE INTO numeric_forecast_revisions (
                id, prediction_id, lower_scaled, median_scaled, upper_scaled,
                confidence_percent, created_at, sequence, rationale
            )
            VALUES (?, ?, -100, 500, 1300, 80, ?, 1, NULL)
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
