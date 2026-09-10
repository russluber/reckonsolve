import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import (
    ForecastContractIntegrityError,
    select_forecast_contract,
)
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.domain.forecast_contracts import ForecastCohort, legacy_contract
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType

STAMP = datetime(2026, 9, 9, 18, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime = STAMP

    def now(self) -> datetime:
        return self.instant


def test_v16_upgrade_preserves_v15_behavior_and_marks_every_record_legacy(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    v15 = Database.open(path, migrations=MIGRATIONS[:15])
    operations = PredictionOperations(v15, FixedClock(), UTC)
    binary = operations._create_legacy_prediction(
        "Will the legacy Binary forecast survive?",
        65,
        forecast_deadline=date(2026, 9, 12),
        tags=("migration",),
    )
    binary = operations.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Preserve this outcome",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    numeric = operations.create_numeric_prediction(
        "What legacy Numeric value will survive?",
        "days",
        1,
        "1.0",
        "2.0",
        "3.0",
        80,
        forecast_deadline=date(2026, 9, 13),
        tags=("migration",),
    )
    numeric = operations.resolve_numeric_prediction(
        numeric.prediction_id,
        "2.5",
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    before_binary = operations.get_prediction(binary.prediction_id)
    before_numeric = operations.get_numeric_prediction(numeric.prediction_id)
    before_analytics = operations.get_forecast_analytics()
    v15.close()

    upgraded = Database.open(path)
    recovered = PredictionOperations(upgraded, FixedClock(), UTC)

    assert upgraded.schema_version == 16
    assert recovered.get_prediction(binary.prediction_id) == replace(
        before_binary,
        forecast_contract=legacy_contract(PredictionType.BINARY),
    )
    assert recovered.get_numeric_prediction(numeric.prediction_id) == before_numeric
    assert recovered.get_forecast_analytics() == before_analytics
    with upgraded.transaction() as connection:
        binary_contract = select_forecast_contract(connection, binary.prediction_id)
        numeric_contract = select_forecast_contract(connection, numeric.prediction_id)
        exact_times = connection.execute(
            """
            SELECT
                (SELECT effective_resolution_at FROM resolutions
                 WHERE prediction_id = ?) AS binary_effective,
                (SELECT effective_resolution_at FROM numeric_resolutions
                 WHERE prediction_id = ?) AS numeric_effective
            """,
            (binary.prediction_id, numeric.prediction_id),
        ).fetchone()
        prospective_history_counts = tuple(
            connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "binary_trajectory_resolution_corrections",
                "numeric_quantile_resolution_corrections",
            )
        )

    assert binary_contract.cohort is ForecastCohort.LEGACY_BINARY
    assert numeric_contract.cohort is ForecastCohort.LEGACY_NUMERIC
    assert binary_contract.forecast_deadline is None
    assert numeric_contract.forecast_deadline is None
    assert tuple(exact_times) == (None, None)
    assert prospective_history_counts == (0, 0)
    upgraded.close()


def test_current_creation_stays_legacy_until_complete_vertical_flows_exist(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    binary = operations._create_legacy_prediction(
        "Will creation remain legacy for M46?", 50
    )
    numeric = operations.create_numeric_prediction(
        "How many legacy units remain?", "units", 0, "1", "2", "3", 80
    )

    with database.transaction() as connection:
        assert (
            select_forecast_contract(connection, binary.prediction_id).cohort
            is ForecastCohort.LEGACY_BINARY
        )
        assert (
            select_forecast_contract(connection, numeric.prediction_id).cohort
            is ForecastCohort.LEGACY_NUMERIC
        )
    database.close()


def test_v16_contract_constraints_reject_rewrite_mismatch_and_fake_deadline(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(), UTC)
    created = operations._create_legacy_prediction(
        "Will contract constraints hold?", 55
    )

    with database.transaction() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE prediction_forecast_contracts
                SET scoring_contract = 'binary-trajectory-brier-v1'
                WHERE prediction_id = ?
                """,
                (created.prediction_id,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO prediction_forecast_contracts (
                    prediction_id, forecast_model, scoring_contract,
                    forecast_deadline_at
                ) VALUES (?, 'numeric-interval-v1',
                          'numeric-interval-score-v1', NULL)
                """,
                (created.prediction_id,),
            )
    database.close()


def test_v16_persists_one_append_only_new_binary_time_and_outcome_chain(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    with database.transaction() as connection:
        prediction_id = connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES (
                'Will the prospective correction chain remain honest?',
                'binary', 'open',
                '2026-09-09T18:00:00.000000Z',
                '2026-09-09T18:00:00.000000Z'
            )
            """
        ).lastrowid
        revision_id = connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id, probability_percent, created_at, sequence
            ) VALUES (?, 60, '2026-09-09T18:00:00.000000Z', 1)
            """,
            (prediction_id,),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO prediction_forecast_contracts (
                prediction_id, forecast_model, scoring_contract,
                forecast_deadline_at
            ) VALUES (
                ?, 'binary-trajectory-v1', 'binary-trajectory-brier-v1',
                '2026-09-16T18:00:00.000000Z'
            )
            """,
            (prediction_id,),
        )
        resolution_id = connection.execute(
            """
            INSERT INTO resolutions (
                prediction_id, outcome, resolved_at, scoring_revision_id,
                resolution_notes, effective_resolution_at
            ) VALUES (
                ?, 'no', '2026-09-12T20:00:00.000000Z', ?, 'Original note',
                '2026-09-12T18:00:00.000000Z'
            )
            """,
            (prediction_id, revision_id),
        ).lastrowid
        connection.execute(
            "UPDATE predictions SET status = 'resolved' WHERE id = ?",
            (prediction_id,),
        )
        first_correction_id = connection.execute(
            """
            INSERT INTO binary_trajectory_resolution_corrections (
                prediction_id, resolution_id, sequence,
                old_outcome, new_outcome,
                old_effective_resolution_at, new_effective_resolution_at,
                old_resolution_notes, new_resolution_notes,
                old_postmortem, new_postmortem,
                outcome_changed, effective_time_changed,
                resolution_notes_changed, postmortem_changed,
                correction_reason, corrected_at
            ) VALUES (
                ?, ?, 1, 'no', 'yes',
                '2026-09-12T18:00:00.000000Z',
                '2026-09-12T17:30:00.000000Z',
                'Original note', NULL, NULL, NULL,
                1, 1, 1, 0, 'Corrected source record',
                '2026-09-13T18:00:00.000000Z'
            )
            """,
            (prediction_id, resolution_id),
        ).lastrowid
        connection.execute(
            """
            INSERT INTO binary_trajectory_resolution_corrections (
                prediction_id, resolution_id, sequence,
                old_outcome, new_outcome,
                old_effective_resolution_at, new_effective_resolution_at,
                old_resolution_notes, new_resolution_notes,
                old_postmortem, new_postmortem,
                outcome_changed, effective_time_changed,
                resolution_notes_changed, postmortem_changed,
                correction_reason, corrected_at
            ) VALUES (
                ?, ?, 2, 'yes', 'yes',
                '2026-09-12T17:30:00.000000Z',
                '2026-09-12T17:00:00.000000Z',
                NULL, NULL, NULL, NULL,
                0, 1, 0, 0, 'More precise source time',
                '2026-09-14T18:00:00.000000Z'
            )
            """,
            (prediction_id, resolution_id),
        )

        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                """
                UPDATE binary_trajectory_resolution_corrections
                SET correction_reason = 'rewrite'
                WHERE id = ?
                """,
                (first_correction_id,),
            )
        with pytest.raises(sqlite3.IntegrityError, match="legacy Binary"):
            connection.execute(
                """
                INSERT INTO resolution_corrections (
                    prediction_id, resolution_id, sequence,
                    old_outcome, new_outcome,
                    old_resolution_notes, new_resolution_notes,
                    old_postmortem, new_postmortem,
                    outcome_changed, resolution_notes_changed,
                    postmortem_changed, correction_reason, corrected_at
                ) VALUES (
                    ?, ?, 1, 'no', 'yes', 'Original note', NULL,
                    NULL, NULL, 1, 1, 0, 'Wrong cohort',
                    '2026-09-14T18:00:00.000000Z'
                )
                """,
                (prediction_id, resolution_id),
            )

    database.close()


def test_failing_v16_migration_rolls_back_all_foundation_schema(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    Database.open(path, migrations=MIGRATIONS[:15]).close()
    broken = Migration(
        version=16,
        name=MIGRATIONS[15].name,
        statements=(*MIGRATIONS[15].statements, "THIS IS NOT VALID SQL"),
    )

    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=(*MIGRATIONS[:15], broken))

    recovered = Database.open(path, migrations=MIGRATIONS[:15])
    assert recovered.schema_version == 15
    with recovered.transaction() as connection:
        assert (
            connection.execute(
                """
                SELECT 1 FROM sqlite_schema
                WHERE name = 'prediction_forecast_contracts'
                """
            ).fetchone()
            is None
        )
        assert "effective_resolution_at" not in {
            row[1] for row in connection.execute("PRAGMA table_info(resolutions)")
        }
    recovered.close()


def test_schema16_reopen_rejects_prediction_without_contract(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO predictions (
                question, prediction_type, status, created_at, updated_at
            ) VALUES (
                'Will missing identity be rejected?', 'binary', 'open',
                '2026-09-09T18:00:00.000000Z',
                '2026-09-09T18:00:00.000000Z'
            )
            """
        )
    database.close()

    with pytest.raises(ForecastContractIntegrityError, match="missing"):
        Database.open(path)
