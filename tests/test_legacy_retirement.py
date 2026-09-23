"""M54B compatibility refusal is whole-database, explicit, and non-mutating."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest

from reckonsolve import app, cli
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MIGRATIONS, Migration, apply_migrations
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.domain.quantiles import NumericValueConstraint

START = datetime(2026, 9, 20, 12, tzinfo=UTC)
STAMP = "2026-09-20T12:00:00.000000Z"


@dataclass
class Clock:
    instant: datetime = START

    def now(self):
        return self.instant


def historical_database(path, version):
    """Construct an old artifact, not a supported application's creation path."""
    with sqlite3.connect(path, autocommit=True) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        apply_migrations(connection, MIGRATIONS[:version])


def insert_retired(path, *, numeric=False, with_identity=True, state="open"):
    """Minimal immutable old-model fixture built only for refusal assertions."""
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        cursor = connection.execute(
            """INSERT INTO predictions
            (question, prediction_type, status, created_at, updated_at,
             numeric_unit, numeric_precision)
            VALUES ('Retired test?', ?, 'open', ?, ?, ?, ?)""",
            (
                "numeric" if numeric else "binary",
                STAMP,
                STAMP,
                "units" if numeric else None,
                0 if numeric else None,
            ),
        )
        identifier = cursor.lastrowid
        if with_identity:
            connection.execute(
                """INSERT INTO prediction_forecast_contracts
                (prediction_id, forecast_model, scoring_contract)
                VALUES (?, ?, ?)""",
                (
                    identifier,
                    "numeric-interval-v1" if numeric else "binary-final-v1",
                    "numeric-interval-score-v1" if numeric else "binary-final-brier-v1",
                ),
            )
        if numeric:
            connection.execute(
                """INSERT INTO numeric_forecast_revisions
                (prediction_id, lower_scaled, median_scaled, upper_scaled,
                 confidence_percent, created_at, sequence)
                VALUES (?, 0, 5, 10, 80, ?, 1)""",
                (identifier, STAMP),
            )
        else:
            connection.execute(
                """INSERT INTO forecast_revisions
                (prediction_id, probability_percent, created_at, sequence)
                VALUES (?, 50, ?, 1)""",
                (identifier, STAMP),
            )
        if state == "locked":
            connection.execute(
                "UPDATE predictions SET forecast_deadline = '2020-01-01' WHERE id = ?",
                (identifier,),
            )
        elif state == "invalid":
            connection.execute(
                "INSERT INTO prediction_invalidations (prediction_id, invalidated_at) VALUES (?, ?)",
                (identifier, STAMP),
            )
        elif state == "resolved":
            if numeric:
                connection.execute(
                    """INSERT INTO numeric_resolutions
                    (prediction_id, actual_scaled, resolved_at, scoring_revision_id)
                    SELECT ?, 2, ?, id FROM numeric_forecast_revisions WHERE prediction_id = ?""",
                    (identifier, STAMP, identifier),
                )
            else:
                connection.execute(
                    """INSERT INTO resolutions
                    (prediction_id, outcome, resolved_at, scoring_revision_id)
                    SELECT ?, 'yes', ?, id FROM forecast_revisions WHERE prediction_id = ?""",
                    (identifier, STAMP, identifier),
                )
    return identifier


@pytest.mark.parametrize("state", ["open", "locked", "resolved", "invalid"])
@pytest.mark.parametrize("numeric", [False, True])
def test_retired_lifecycle_and_backup_artifact_do_not_change_refusal(
    tmp_path, state, numeric
):
    path = tmp_path / "retired.sqlite3"
    historical_database(path, 18)
    insert_retired(path, state=state, numeric=numeric)
    backup = tmp_path / "old-backup.sqlite3"
    with sqlite3.connect(path) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    for artifact in (path, backup):
        before = artifact.read_bytes()
        with pytest.raises(ForecastContractIntegrityError, match="retired"):
            Database.open(artifact)
        assert artifact.read_bytes() == before


@pytest.mark.parametrize("damage", ["missing", "unknown", "mismatched"])
def test_current_schema_bad_identity_refuses_without_repair(tmp_path, damage):
    path = tmp_path / "damaged.sqlite3"
    database = Database.open(path)
    PredictionOperations(database, Clock(), UTC).create_prediction(
        "Current model?", 60, forecast_deadline=START + timedelta(days=1)
    )
    database.close()
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA ignore_check_constraints = ON")
        if damage == "missing":
            # Simulate a damaged artifact, not an application mutation.
            triggers = connection.execute(
                "SELECT name FROM sqlite_schema WHERE type = 'trigger' AND tbl_name = 'prediction_forecast_contracts'"
            ).fetchall()
            for (name,) in triggers:
                connection.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
            connection.execute("DELETE FROM prediction_forecast_contracts")
        else:
            connection.execute(
                "DROP TRIGGER prediction_forecast_contracts_are_immutable"
            )
            connection.execute(
                "UPDATE prediction_forecast_contracts SET scoring_contract = ?",
                ("future-score-v9" if damage == "unknown" else "numeric-wis-v1",),
            )
    before = path.read_bytes()
    with pytest.raises(ForecastContractIntegrityError, match="contract"):
        Database.open(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("version", [15, 16, 17, 18])
@pytest.mark.parametrize("numeric", [False, True])
def test_retired_database_refused_before_migration_or_search_repair(
    tmp_path, version, numeric
):
    path = tmp_path / "retired.sqlite3"
    historical_database(path, version)
    insert_retired(path, numeric=numeric, with_identity=version >= 16)
    before = path.read_bytes()
    with pytest.raises(ForecastContractIntegrityError, match="[Rr]etired"):
        Database.open(path)
    assert path.read_bytes() == before


@pytest.mark.parametrize("launcher", ["gui", "cli"])
@pytest.mark.parametrize("mixed", [False, True])
def test_both_launchers_refuse_whole_database_unchanged(
    tmp_path, monkeypatch, qtbot, launcher, mixed
):
    path = tmp_path / "mixed.sqlite3"
    database = Database.open(path)
    if mixed:
        PredictionOperations(database, Clock(), UTC).create_prediction(
            "Supported?", 60, forecast_deadline=START + timedelta(days=1)
        )
    database.close()
    insert_retired(path)
    before = path.read_bytes()
    if launcher == "gui":
        messages = []
        monkeypatch.setattr(
            app.QMessageBox, "critical", lambda *args: messages.append(args[-1])
        )
        assert app.run([], database_path=path) == 1
        message = messages[0]
    else:
        output, errors = StringIO(), StringIO()
        monkeypatch.setattr(cli, "resolve_database_path", lambda *_: path)
        assert cli.run(["list", "--type", "binary"], stdout=output, stderr=errors) == 1
        message = errors.getvalue()
    assert "retired" in message
    assert "No conversion or deletion occurred" in message
    assert path.read_bytes() == before


@pytest.mark.parametrize("version", [16, 17, 18])
def test_supported_staged_binary_history_survives_upgrade(tmp_path, version):
    path = tmp_path / "supported.sqlite3"
    database = Database.open(path, migrations=MIGRATIONS[:version])
    clock = Clock()
    ops = PredictionOperations(database, clock, UTC)
    prediction = ops.create_prediction(
        "Supported staged forecast?",
        60,
        forecast_deadline=START + timedelta(days=1),
        tags=("kept",),
        rationale="Initial reasoning",
    )
    clock.instant += timedelta(minutes=1)
    prediction = ops.revise_forecast(
        prediction.prediction_id,
        75,
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
        rationale="Evidence",
    )
    before = ops.list_forecast_revisions(prediction.prediction_id)
    database.close()
    reopened = Database.open(path)
    try:
        ops = PredictionOperations(reopened, clock, UTC)
        assert ops.get_prediction(prediction.prediction_id) == prediction
        assert ops.list_forecast_revisions(prediction.prediction_id) == before
        assert ops.search_predictions("Evidence").hits
        with reopened.transaction() as connection:
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        reopened.close()


def test_supported_both_models_backup_restart_scores_and_search(tmp_path):
    path = tmp_path / "supported.sqlite3"
    database = Database.open(path)
    clock = Clock()
    ops = PredictionOperations(database, clock, UTC)
    binary = ops.create_prediction(
        "Binary?", 60, forecast_deadline=START + timedelta(days=1)
    )
    numeric = ops.create_numeric_prediction(
        "Numeric?",
        "units",
        0,
        {5: -10, 25: -5, 50: 0, 75: 5, 95: 10},
        value_constraint=NumericValueConstraint.WHOLE_NUMBER,
        forecast_deadline=START + timedelta(days=1),
    )
    clock.instant += timedelta(hours=2)
    ops.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
        use_recorded_time=True,
    )
    ops.resolve_numeric_prediction(
        numeric.prediction_id,
        2,
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
        use_recorded_time=True,
    )
    identifiers = (binary.prediction_id, numeric.prediction_id)
    scores = tuple(
        ops.get_prediction_scorecard(identifier) for identifier in identifiers
    )
    analytics = ops.get_forecast_analytics()
    archive = ops.browse_predictions()
    backup = tmp_path / "backup.sqlite3"
    database.backup_to(backup)
    database.close()
    for artifact in (path, backup):
        reopened = Database.open(artifact)
        try:
            ops = PredictionOperations(reopened, clock, UTC)
            assert tuple(ops.get_prediction_scorecard(i) for i in identifiers) == scores
            assert ops.get_forecast_analytics() == analytics
            assert ops.browse_predictions() == archive
        finally:
            reopened.close()


def test_retired_artifact_is_refused_by_migration_entry_point(tmp_path):
    path = tmp_path / "old.sqlite3"
    historical_database(path, 16)
    insert_retired(path)
    before = path.read_bytes()
    with (
        sqlite3.connect(path, autocommit=True) as connection,
        pytest.raises(ForecastContractIntegrityError, match="retired"),
    ):
        apply_migrations(connection)
    assert path.read_bytes() == before


def test_existing_connection_refuses_external_legacy_insert_before_writing(tmp_path):
    path = tmp_path / "concurrent.sqlite3"
    database = Database.open(path)
    insert_retired(path)
    before = path.read_bytes()
    try:
        with pytest.raises(ForecastContractIntegrityError, match="retired"):
            PredictionOperations(database, Clock(), UTC).set_stale_threshold_days(30)
        assert path.read_bytes() == before
        with pytest.raises(ForecastContractIntegrityError, match="retired"):
            database.backup_to(tmp_path / "refused-backup.sqlite3")
        assert not (tmp_path / "refused-backup.sqlite3").exists()
    finally:
        database.close()


def test_supported_pending_migration_failure_preserves_canonical_database(tmp_path):
    path = tmp_path / "rollback.sqlite3"
    database = Database.open(path)
    PredictionOperations(database, Clock(), UTC).create_prediction(
        "Retain me", 20, forecast_deadline=START + timedelta(days=1)
    )
    database.close()
    before = path.read_bytes()
    migrations = (
        *MIGRATIONS,
        Migration(
            19,
            "forced failure",
            (
                "CREATE TABLE never_committed (id INTEGER)",
                "INVALID SQL",
            ),
        ),
    )
    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=migrations)
    assert path.read_bytes() == before
