# Reported wall-clock minutes intentionally have no timezone.
# ruff: noqa: DTZ001
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from reckonsolve.analytics.one_shot import one_shot_score
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.clock import format_utc
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MIGRATIONS, Migration
from reckonsolve.data.one_shot import OneShotRepository
from reckonsolve.data.predictions import ForecastContextChangedError
from reckonsolve.data.transfer import DataTransferRepository
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotValues,
    ReportedTime,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
    PredictionValidationError,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)

NOW = datetime(2026, 9, 26, 20, tzinfo=UTC)


@dataclass
class Clock:
    instant: datetime = NOW

    def now(self):
        return self.instant


def request(numeric=False, answered=True):
    wall = ReportedTime(datetime(2026, 9, 26, 12, 5), True, -420)
    return NewOneShotPrediction(
        "Tree height?",
        one_shot_contract(PredictionType.NUMERIC if numeric else PredictionType.BINARY),
        OneShotValues(
            probability_percent=None if numeric else 80,
            quantiles=FiveQuantiles.from_values({5: -2, 25: -1, 50: 0, 75: 1, 95: 2}, 2)
            if numeric
            else None,
            answer=(FixedPrecisionValue(0, 2) if numeric else BinaryOutcome.YES)
            if answered
            else None,
            forecast_reported=wall,
            reveal_reported=wall if answered else None,
            resolution_notes="Measured" if answered else None,
        ),
        QuantileDefinition("m", 2, NumericValueConstraint.WHOLE_NUMBER)
        if numeric
        else None,
        rationale="A phone note",
        resolution_criteria="Check the same tree",
        tags=("outdoors",),
    )


@pytest.fixture
def storage(tmp_path):
    database = Database.open(tmp_path / "foundation.sqlite3")
    clock = Clock()
    try:
        yield database, clock, OneShotRepository(database, clock)
    finally:
        database.close()


@pytest.mark.parametrize("numeric", [False, True])
def test_create_correct_backup_and_restart_retains_every_fact(
    storage, tmp_path, numeric
):
    database, clock, repo = storage
    original = repo.create_prediction(request(numeric))
    assert original.recorded_at == original.answer_recorded_at == NOW
    assert original.status is PredictionStatus.RESOLVED
    assert original.original == original.effective == request(numeric).values
    clock.instant += timedelta(minutes=1)
    corrected_values = replace(
        original.effective,
        forecast_reported=None,
        answer=FixedPrecisionValue(300, 2) if numeric else BinaryOutcome.NO,
        postmortem="Copied wrong result",
    )
    corrected = repo.correct(original, corrected_values)
    assert corrected.original == original.original
    assert corrected.effective == corrected_values
    assert corrected.corrections[0].before == original.original
    assert corrected.corrections[0].after == corrected_values
    score = one_shot_score(
        corrected.contract, corrected.status, corrected.effective, corrected.definition
    )
    if not numeric:
        assert score == Fraction(16, 25)
    with database.transaction() as c:
        revision_table = (
            "numeric_quantile_revisions" if numeric else "forecast_revisions"
        )
        assert c.execute(f"SELECT COUNT(*) FROM {revision_table}").fetchone()[0] == 1
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
        assert (
            c.execute(
                "SELECT forecast_deadline_at FROM prediction_forecast_contracts"
            ).fetchone()[0]
            is None
        )
        assert (
            c.execute("SELECT wall FROM one_shot_forecast_times").fetchone()[0]
            == "2026-09-26T12:05"
        )
    backup = database.backup_to(tmp_path / "backup.sqlite3")
    database.close()
    for path in (database.path, backup):
        reopened = Database.open(path)
        try:
            assert (
                OneShotRepository(reopened, clock).get(original.prediction_id)
                == corrected
            )
        finally:
            reopened.close()


@pytest.mark.parametrize("numeric", [False, True])
def test_correct_while_waiting_add_answer_then_correct_again(storage, numeric):
    _database, clock, repo = storage
    pending = repo.create_prediction(request(numeric, False))
    assert (
        one_shot_score(
            pending.contract, pending.status, pending.effective, pending.definition
        )
        is None
    )
    clock.instant += timedelta(minutes=1)
    forecast = replace(pending.effective, forecast_reported=None)
    if numeric:
        forecast = replace(
            forecast,
            quantiles=FiveQuantiles.from_values(
                dict.fromkeys((5, 25, 50, 75, 95), 1), 2
            ),
        )
    else:
        forecast = replace(forecast, probability_percent=90)
    corrected = repo.correct(pending, forecast, note="Phone transcription")
    with pytest.raises(ForecastContextChangedError):
        repo.correct(pending, forecast)
    clock.instant += timedelta(minutes=1)
    values = replace(
        corrected.effective,
        answer=FixedPrecisionValue(100, 2) if numeric else BinaryOutcome.YES,
    )
    answered = repo.add_answer(corrected, values)
    assert answered.effective == values
    assert answered.recorded_at == NOW
    assert answered.answer_recorded_at == clock.instant
    assert answered.original.probability_percent == pending.original.probability_percent
    with pytest.raises(ForecastContextChangedError):
        repo.correct(
            corrected,
            replace(
                forecast, forecast_reported=request(numeric).values.forecast_reported
            ),
        )
    final = repo.correct(
        answered,
        replace(
            values,
            resolution_notes="Answer source",
            reveal_reported=ReportedTime(datetime(2026, 9, 25, 12)),
        ),
    )
    assert final.corrections[1].before == values
    assert one_shot_score(
        final.contract, final.status, final.effective, final.definition
    ) == (
        one_shot_score(
            answered.contract, answered.status, answered.effective, answered.definition
        )
    )
    with pytest.raises(PredictionValidationError, match="unchanged"):
        repo.correct(final, final.effective)
    with pytest.raises(ValueError, match="add or remove"):
        repo.correct(
            final,
            replace(
                final.effective,
                answer=None,
                reveal_reported=None,
                resolution_notes=None,
            ),
        )


@pytest.mark.parametrize("numeric", [False, True])
def test_creation_failure_rolls_back_parent_contract_tags_and_answer(storage, numeric):
    database, _, repo = storage
    with database.transaction() as c:
        c.execute(
            "CREATE TRIGGER force_failure BEFORE INSERT ON one_shot_answer_times BEGIN SELECT RAISE(ABORT, 'forced failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="forced failure"):
        repo.create_prediction(request(numeric))
    with database.transaction() as c:
        for table in (
            "predictions",
            "prediction_forecast_contracts",
            "forecast_revisions",
            "numeric_quantile_revisions",
            "one_shot_forecast_times",
            "one_shot_answer_times",
            "resolutions",
            "numeric_resolutions",
            "tags",
            "search_dirty_predictions",
        ):
            assert c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_invalid_exclusion_and_guarded_pending_answer(storage):
    database, _, repo = storage
    pending = repo.create_prediction(request(answered=False))
    with database.transaction() as c:
        c.execute(
            "INSERT INTO prediction_invalidations (prediction_id, invalidated_at) VALUES (?, ?)",
            (pending.prediction_id, format_utc(NOW)),
        )
    invalid = repo.get(pending.prediction_id)
    assert one_shot_score(invalid.contract, invalid.status, invalid.effective) is None
    with pytest.raises(ValueError, match="waiting"):
        repo.add_answer(invalid, replace(invalid.effective, answer=BinaryOutcome.NO))


@pytest.mark.parametrize("numeric", [False, True])
def test_sql_guards_reject_revisions_reviews_rewrites_and_deadlines(storage, numeric):
    database, _, repo = storage
    record = repo.create_prediction(request(numeric, False))
    commands = [
        "UPDATE one_shot_forecast_times SET wall = NULL",
        "DELETE FROM one_shot_forecast_times",
        "INSERT OR REPLACE INTO one_shot_forecast_times SELECT * FROM one_shot_forecast_times",
        "INSERT OR REPLACE INTO prediction_forecast_contracts SELECT * FROM prediction_forecast_contracts",
        "UPDATE predictions SET forecast_deadline = '2027-01-01'",
    ]
    if numeric:
        commands.extend(
            [
                "INSERT INTO numeric_quantile_revisions (prediction_id, sequence, created_at, q05_scaled, q25_scaled, q50_scaled, q75_scaled, q95_scaled) SELECT prediction_id, 2, '2026-09-26T20:01:00.000000Z', 0, 0, 0, 0, 0 FROM numeric_quantile_revisions",
                "INSERT INTO forecast_reviews (prediction_id, quantile_revision_id, created_at) SELECT prediction_id, id, created_at FROM numeric_quantile_revisions",
            ]
        )
    else:
        commands.extend(
            [
                "INSERT INTO forecast_revisions (prediction_id, sequence, created_at, probability_percent) SELECT prediction_id, 2, '2026-09-26T20:01:00.000000Z', 40 FROM forecast_revisions",
                "INSERT INTO forecast_reviews (prediction_id, forecast_revision_id, created_at) SELECT prediction_id, id, created_at FROM forecast_revisions",
            ]
        )
    for command in commands:
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as c,
        ):
            c.execute(command)
        assert repo.get(record.prediction_id) == record


def test_correction_chain_constraints_and_failure_rollback(storage):
    database, clock, repo = storage
    original = repo.create_prediction(request())
    clock.instant += timedelta(minutes=1)
    first = repo.correct(original, replace(original.effective, probability_percent=70))
    commands = [
        "UPDATE one_shot_corrections SET new_probability_percent = 60",
        "DELETE FROM one_shot_corrections",
        "INSERT OR REPLACE INTO one_shot_corrections SELECT * FROM one_shot_corrections",
    ]
    for command in commands:
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as c,
        ):
            c.execute(command)
    clock.instant -= timedelta(minutes=2)
    with pytest.raises(sqlite3.IntegrityError):
        repo.correct(first, replace(first.effective, probability_percent=60))
    assert repo.get(original.prediction_id) == first


def test_missing_reported_metadata_is_rejected_before_commit(storage):
    database, _, _ = storage
    with (
        pytest.raises(ForecastContractIntegrityError),
        database.transaction() as c,
    ):
        c.execute(
            "INSERT INTO predictions (question, status, prediction_type, created_at, updated_at) VALUES ('Broken', 'open', 'binary', ?, ?)",
            (format_utc(NOW), format_utc(NOW)),
        )
        c.execute(
            "INSERT INTO prediction_forecast_contracts (prediction_id, forecast_model, scoring_contract) VALUES (1, 'binary-one-shot-v1', 'binary-one-shot-brier-v1')"
        )
        c.execute(
            "INSERT INTO forecast_revisions (prediction_id, sequence, created_at, probability_percent) VALUES (1, 1, ?, 50)",
            (format_utc(NOW),),
        )
    with database.transaction() as c:
        assert c.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0


def test_format_five_exports_while_public_archive_includes_one_shots(storage, tmp_path):
    database, clock, repo = storage
    repo.create_prediction(request())
    destination = tmp_path / "existing.zip"
    destination.write_bytes(b"keep this artifact")
    DataTransferRepository(database).export_csv_bundle(destination, exported_at=NOW)
    assert destination.read_bytes().startswith(b"PK")
    assert (
        len(PredictionOperations(database, clock, UTC).browse_predictions().predictions)
        == 1
    )


def canonical_snapshot(connection):
    result = {}
    for row in connection.execute(
        "SELECT name FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'prediction_search%' AND name NOT LIKE 'search_%' AND name != 'schema_migrations' ORDER BY name"
    ).fetchall():
        table = row[0]
        result[table] = tuple(
            tuple(r) for r in connection.execute(f'SELECT * FROM "{table}" ORDER BY 1')
        )
    return result


def populated_v18(path):
    database = Database.open(path, migrations=MIGRATIONS[:18])
    clock = Clock()
    ops = PredictionOperations(database, clock, UTC)
    binary = ops.create_prediction(
        "Existing Binary?",
        60,
        forecast_deadline=NOW + timedelta(days=1),
        tags=("preserved",),
    )
    numeric = ops.create_numeric_prediction(
        "Existing Numeric?",
        "m",
        2,
        {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
        value_constraint=NumericValueConstraint.CONTINUOUS,
        forecast_deadline=NOW + timedelta(days=1),
    )
    clock.instant += timedelta(minutes=1)
    ops.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
        use_recorded_time=True,
    )
    ops.resolve_numeric_prediction(
        numeric.prediction_id,
        1,
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
        use_recorded_time=True,
    )
    return database, ops, clock


def test_v18_upgrade_preserves_all_existing_rows_scores_search_and_export(tmp_path):
    path = tmp_path / "upgrade.sqlite3"
    database, ops, clock = populated_v18(path)
    with database.transaction() as c:
        before = canonical_snapshot(c)
    analytics = ops.get_forecast_analytics()
    archive = ops.browse_predictions()
    matches = ops.search_predictions("Existing")
    database.close()
    upgraded = Database.open(path)
    try:
        assert upgraded.schema_version == 20
        with upgraded.transaction() as c:
            after = canonical_snapshot(c)
            for table, rows in before.items():
                assert after[table] == rows, table
            assert not c.execute("PRAGMA foreign_key_check").fetchall()
        ops = PredictionOperations(upgraded, clock, UTC)
        assert ops.get_forecast_analytics() == analytics
        assert ops.browse_predictions() == archive
        assert ops.search_predictions("Existing") == matches
        ops.export_csv_bundle(tmp_path / "v07.zip")
    finally:
        upgraded.close()


@pytest.mark.parametrize("phase", [5, -1])
def test_m56_failure_rolls_back_ddl_and_data_byte_for_byte(tmp_path, phase):
    path = tmp_path / "rollback.sqlite3"
    database, _, _ = populated_v18(path)
    database.close()
    before = path.read_bytes()
    m56 = MIGRATIONS[18]
    statements = m56.statements
    statements = (*statements[:phase], "INVALID SQL", *statements[phase:])
    broken = (*MIGRATIONS[:18], Migration(19, m56.name, statements))
    with pytest.raises(sqlite3.Error):
        Database.open(path, migrations=broken)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "damage", ["unknown", "mismatched", "deadline", "chain", "missing-times"]
)
def test_bad_one_shot_archive_is_refused_before_repair_or_write(tmp_path, damage):
    path = tmp_path / "bad.sqlite3"
    database = Database.open(path)
    repo = OneShotRepository(database, Clock())
    original = repo.create_prediction(request())
    repo.correct(original, replace(original.effective, probability_percent=70))
    database.close()
    with sqlite3.connect(path) as c:
        c.execute("PRAGMA ignore_check_constraints = ON")
        if damage in ("unknown", "mismatched", "deadline"):
            c.execute("DROP TRIGGER prediction_forecast_contracts_are_immutable")
            if damage == "deadline":
                c.execute(
                    "UPDATE prediction_forecast_contracts SET forecast_deadline_at = ?",
                    (format_utc(NOW + timedelta(days=1)),),
                )
            else:
                c.execute(
                    "UPDATE prediction_forecast_contracts SET scoring_contract = ?",
                    (
                        "unknown"
                        if damage == "unknown"
                        else "binary-trajectory-brier-v1",
                    ),
                )
        elif damage == "chain":
            c.execute("DROP TRIGGER one_shot_corrections_immutable")
            c.execute("UPDATE one_shot_corrections SET old_probability_percent = 20")
        else:
            c.execute("DROP TRIGGER one_shot_forecast_times_no_delete")
            c.execute("DELETE FROM one_shot_forecast_times")
        # If startup repaired before checking contracts it would change these rows.
        c.execute("DELETE FROM prediction_search")
    before = path.read_bytes()
    with pytest.raises(ForecastContractIntegrityError):
        Database.open(path)
    assert path.read_bytes() == before


def test_existing_connection_checks_external_damage_before_repair_and_backup(
    storage, tmp_path
):
    database, _, repo = storage
    original = repo.create_prediction(request())
    with sqlite3.connect(database.path) as c:
        c.execute("DROP TRIGGER prediction_forecast_contracts_are_immutable")
        c.execute("PRAGMA ignore_check_constraints = ON")
        c.execute("UPDATE prediction_forecast_contracts SET scoring_contract = 'bad'")
    before = database.path.read_bytes()
    for action in (
        lambda: repo.get(original.prediction_id),
        database.rebuild_search_index,
        lambda: database.backup_to(tmp_path / "refused.sqlite3"),
    ):
        with pytest.raises(ForecastContractIntegrityError):
            action()
        assert database.path.read_bytes() == before
    assert not (tmp_path / "refused.sqlite3").exists()


def test_independent_connections_reject_stale_values_and_bounded_lock(storage):
    database, clock, repo = storage
    original = repo.create_prediction(
        replace(request(answered=False), values=OneShotValues(probability_percent=60))
    )
    second_db = Database.open(database.path)
    try:
        second = OneShotRepository(second_db, clock)
        second.correct(
            second.get(original.prediction_id),
            replace(original.effective, probability_percent=70),
        )
        with pytest.raises(ForecastContextChangedError):
            repo.correct(original, replace(original.effective, probability_percent=80))
        current = repo.get(original.prediction_id)
        with database.transaction() as c:
            c.execute("PRAGMA busy_timeout = 1")
        with (
            second_db.transaction(),
            pytest.raises(sqlite3.OperationalError, match="locked"),
        ):
            repo.add_answer(
                current, replace(current.effective, answer=BinaryOutcome.YES)
            )
        assert repo.get(original.prediction_id) == current
    finally:
        second_db.close()


def test_sql_rejects_broken_correction_sequence_and_stale_before_snapshot(storage):
    database, _, repo = storage
    original = repo.create_prediction(request())
    corrected = repo.correct(
        original, replace(original.effective, probability_percent=70)
    )
    with database.transaction() as c:
        row = dict(c.execute("SELECT * FROM one_shot_corrections").fetchone())
    for changes in (
        {"sequence": 3},
        {"old_probability_percent": 20},
        {"new_probability_percent": 70},
    ):
        proposed = (
            row
            | {
                "id": None,
                "sequence": 2,
                "old_probability_percent": 70,
                "new_probability_percent": 60,
            }
            | changes
        )
        with (
            pytest.raises(sqlite3.IntegrityError),
            database.transaction() as c,
        ):
            c.execute(
                f"INSERT INTO one_shot_corrections ({', '.join(proposed)}) VALUES ({', '.join('?' for _ in proposed)})",
                tuple(proposed.values()),
            )
        assert repo.get(original.prediction_id) == corrected
