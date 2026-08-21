"""End-to-end v0.1-to-v0.2 migration and recovery coverage."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MIGRATIONS
from reckonsolve.domain.predictions import BinaryOutcome, PredictionStatus

NOW = datetime(2026, 8, 20, 20, 0, tzinfo=UTC)


class FixedClock:
    def now(self) -> datetime:
        return NOW


def test_real_v01_database_migrates_through_v02_and_recovers_every_type(
    tmp_path,
) -> None:
    """A v8 database reaches every v0.2 schema with its history intact."""

    source_path = tmp_path / "v01.sqlite3"
    backup_path = tmp_path / "v02-recovery.sqlite3"
    v01_database = Database.open(source_path, migrations=MIGRATIONS[:8])
    v01_operations = PredictionOperations(v01_database, FixedClock())
    v01_prediction = v01_operations.create_prediction(
        "Will the original Binary record reach v0.2?",
        40,
        rationale="Created by the completed v0.1 application.",
        tags=("migration",),
    )
    v01_prediction = v01_operations.revise_forecast(
        v01_prediction.prediction_id,
        55,
        rationale="The v0.1 revision must remain immutable.",
        expected_revision_id=v01_prediction.current_revision_id,
        expected_metadata_version=v01_prediction.metadata_version,
    )
    v01_operations.add_journal_entry(
        v01_prediction.prediction_id,
        "The v0.1 Journal anchor must remain intact.",
        expected_revision_id=v01_prediction.current_revision_id,
        expected_metadata_version=v01_prediction.metadata_version,
    )
    v01_database.close()

    upgraded_database = Database.open(source_path)
    operations = PredictionOperations(upgraded_database, FixedClock())
    with upgraded_database.transaction() as connection:
        history = tuple(
            row[0]
            for row in connection.execute(
                "SELECT version FROM schema_migrations ORDER BY version"
            ).fetchall()
        )
    assert history == tuple(range(1, len(MIGRATIONS) + 1))

    preserved_binary = operations.get_prediction(v01_prediction.prediction_id)
    assert preserved_binary.probability_percent == 55
    assert len(operations.list_forecast_revisions(preserved_binary.prediction_id)) == 2
    assert len(operations.list_timeline(preserved_binary.prediction_id)) == 3

    operations.add_forecast_review(
        preserved_binary.prediction_id,
        note="The upgraded app can review the preserved Binary forecast.",
        expected_revision_id=preserved_binary.current_revision_id,
        expected_metadata_version=preserved_binary.metadata_version,
    )
    resolved_binary = operations.resolve_prediction(
        preserved_binary.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=preserved_binary.current_revision_id,
        expected_metadata_version=preserved_binary.metadata_version,
    )
    assert resolved_binary.status is PredictionStatus.RESOLVED

    numeric = operations.create_numeric_prediction(
        "How many signed days will the v0.2 migration test take?",
        "days",
        1,
        "-2.5",
        "1.0",
        "6.5",
        80,
        rationale="The first v0.2 Numeric interval.",
        tags=("migration",),
    )
    operations.add_numeric_forecast_review(
        numeric.prediction_id,
        note="The first Numeric interval was deliberately retained.",
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    numeric = operations.resolve_numeric_prediction(
        numeric.prediction_id,
        "9.5",
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    assert numeric.status is PredictionStatus.RESOLVED

    operations.create_backup(backup_path)
    upgraded_database.close()

    recovered_database = Database.open(backup_path)
    recovered = PredictionOperations(recovered_database, FixedClock())
    recovered_binary = recovered.get_prediction(v01_prediction.prediction_id)
    recovered_numeric = recovered.get_numeric_prediction(numeric.prediction_id)
    assert recovered_database.schema_version == len(MIGRATIONS)
    assert recovered_binary.status is PredictionStatus.RESOLVED
    assert len(recovered.list_timeline(recovered_binary.prediction_id)) == 4
    assert recovered_numeric.status is PredictionStatus.RESOLVED
    assert recovered_numeric.current_revision.lower_bound.decimal_value == Decimal(
        "-2.5"
    )
    assert recovered_numeric.resolution is not None
    assert recovered_numeric.resolution.actual_value.decimal_value == Decimal("9.5")
    assert len(recovered.list_numeric_timeline(recovered_numeric.prediction_id)) == 2
    recovered_database.close()
