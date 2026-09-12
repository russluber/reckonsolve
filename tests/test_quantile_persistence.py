import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.clock import format_utc
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import (
    check_forecast_contract_integrity,
    select_forecast_contract,
)
from reckonsolve.data.migrations import MIGRATIONS
from reckonsolve.data.predictions import ForecastContextChangedError
from reckonsolve.data.quantiles import QuantilePredictionRepository, read_definition
from reckonsolve.data.search_index import project_prediction_documents
from reckonsolve.domain.forecast_contracts import (
    ForecastCohort,
    ForecastContractValidationError,
    ForecastDeadline,
)
from reckonsolve.domain.predictions import PredictionValidationError
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NewQuantilePrediction,
    NumericValueConstraint,
    QuantileDefinition,
)

T0 = datetime(2026, 9, 11, 10, tzinfo=UTC)
DEADLINE = ForecastDeadline(T0 + timedelta(hours=2))


@dataclass
class Clock:
    instant: datetime = T0

    def now(self):
        return self.instant


def quantiles(delta=0):
    return FiveQuantiles.from_values(
        {5: -2 + delta, 25: -1 + delta, 50: delta, 75: 1 + delta, 95: 2 + delta}, 2
    )


def new(constraint=NumericValueConstraint.CONTINUOUS):
    return NewQuantilePrediction(
        "How much rainfall?",
        QuantileDefinition("mm", 2, constraint),
        quantiles(),
        DEADLINE,
        rationale="Forecast evidence",
        tags=("weather",),
    )


@pytest.fixture
def storage(tmp_path):
    database = Database.open(tmp_path / "quantiles.sqlite3")
    clock = Clock()
    repo = QuantilePredictionRepository(database, clock)
    try:
        yield database, clock, repo
    finally:
        database.close()


def context(revision):
    return {
        "expected_revision_id": revision.revision_id,
        "expected_metadata_version": 1,
    }


def history_entry(connection, table, revision, timestamp, text):
    field = "body" if table == "journal_entries" else "note"
    return connection.execute(
        f"INSERT INTO {table} (prediction_id, quantile_revision_id, created_at, {field}) VALUES (?, ?, ?, ?)",
        (revision.prediction_id, revision.revision_id, format_utc(timestamp), text),
    ).lastrowid


def resolution(connection, revision, actual=0, effective=T0 + timedelta(minutes=15)):
    return connection.execute(
        """INSERT INTO numeric_resolutions
        (prediction_id, quantile_revision_id, actual_scaled, resolved_at, effective_resolution_at, resolution_notes)
        VALUES (?, ?, ?, ?, ?, 'Resolved evidence')""",
        (
            revision.prediction_id,
            revision.revision_id,
            actual,
            format_utc(T0 + timedelta(hours=3)),
            format_utc(effective),
        ),
    ).lastrowid


def test_complete_roundtrip_timeline_search_and_backup(storage, tmp_path):
    database, clock, repo = storage
    first = repo.create_prediction(new())
    with database.transaction() as c:
        assert (
            select_forecast_contract(c, first.prediction_id).cohort
            is ForecastCohort.QUANTILE_NUMERIC
        )
        assert read_definition(c, first.prediction_id) == new().definition
        review_id = history_entry(
            c, "forecast_reviews", first, T0 + timedelta(minutes=1), "Retained evidence"
        )
        journal_id = history_entry(
            c, "journal_entries", first, T0 + timedelta(minutes=2), "Original journal"
        )
        c.execute(
            "INSERT INTO journal_entry_corrections (prediction_id, journal_entry_id, sequence, body, corrected_at) VALUES (?, ?, 1, 'Corrected journal', ?)",
            (first.prediction_id, journal_id, format_utc(T0 + timedelta(minutes=4))),
        )
    clock.instant += timedelta(minutes=30)
    second = repo.append_revision(
        first.prediction_id,
        quantiles(1),
        rationale="Revised evidence",
        **context(first),
    )
    timeline = repo.list_timeline(first.prediction_id)
    assert [e.kind for e in timeline] == ["forecast", "review", "journal", "forecast"]
    assert timeline[1].record_id == review_id
    assert timeline[2].revision == first
    assert timeline[2].text == "Corrected journal"
    assert timeline[2].original_text == "Original journal"
    assert len(timeline[2].corrections) == 1
    with database.transaction() as c:
        resolution(c, second)
        assert c.execute(
            "SELECT scoring_revision_id, quantile_revision_id FROM numeric_resolutions"
        ).fetchone()[:] == (None, second.revision_id)
        docs = project_prediction_documents(c, first.prediction_id)
        assert {d.text for d in docs} >= {
            "Forecast evidence",
            "Retained evidence",
            "Corrected journal",
            "Original journal",
            "Revised evidence",
            "Resolved evidence",
        }
        assert next(d for d in docs if d.text == "Original journal").is_superseded
        assert (
            next(d for d in docs if d.text == "Revised evidence").source_sequence == 2
        )
        assert (
            c.execute("SELECT COUNT(*) FROM numeric_forecast_revisions").fetchone()[0]
            == 0
        )
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
        check_forecast_contract_integrity(c)
    database.check_search_index()
    database.rebuild_search_index()
    database.check_search_index()
    backup = database.backup_to(tmp_path / "recovery.sqlite3")
    database.close()
    for path in (database.path, backup):
        recovered = Database.open(path)
        try:
            read = QuantilePredictionRepository(recovered, clock)
            assert read.list_revisions(first.prediction_id) == (first, second)
            assert read.list_timeline(first.prediction_id) == timeline
        finally:
            recovered.close()


def test_atomic_failure_noops_stale_context_and_time_boundaries(storage):
    database, clock, repo = storage
    with database.transaction() as c:
        c.execute(
            "CREATE TRIGGER force_quantile_failure BEFORE INSERT ON numeric_quantile_revisions BEGIN SELECT RAISE(ABORT, 'forced'); END"
        )
    with pytest.raises(sqlite3.IntegrityError, match="forced"):
        repo.create_prediction(new())
    with database.transaction() as c:
        for table in (
            "predictions",
            "prediction_forecast_contracts",
            "numeric_quantile_definitions",
            "numeric_quantile_revisions",
            "tags",
            "search_dirty_predictions",
        ):
            assert c.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        c.execute("DROP TRIGGER force_quantile_failure")
    first = repo.create_prediction(new())
    with pytest.raises(PredictionValidationError, match="unchanged"):
        repo.append_revision(first.prediction_id, first.quantiles, **context(first))
    with pytest.raises(ForecastContextChangedError):
        repo.append_revision(
            first.prediction_id,
            quantiles(1),
            expected_revision_id=999,
            expected_metadata_version=1,
        )
    with pytest.raises(ForecastContractValidationError, match="clock"):
        repo.append_revision(first.prediction_id, quantiles(1), **context(first))
    clock.instant = DEADLINE.instant
    with pytest.raises(ForecastContractValidationError, match="Deadline"):
        repo.append_revision(first.prediction_id, quantiles(1), **context(first))
    assert repo.list_revisions(first.prediction_id) == (first,)
    with pytest.raises(ForecastContractValidationError, match="later"):
        repo.create_prediction(new())


def test_revision_guard_preserves_model_integrity_and_history(storage):
    database, _clock, repo = storage
    first = repo.create_prediction(new(NumericValueConstraint.WHOLE_NUMBER))
    commands = [
        (
            "UPDATE numeric_quantile_revisions SET q50_scaled = 1 WHERE id = ?",
            (first.revision_id,),
        ),
        ("DELETE FROM numeric_quantile_revisions WHERE id = ?", (first.revision_id,)),
        (
            "INSERT OR REPLACE INTO numeric_quantile_revisions SELECT * FROM numeric_quantile_revisions WHERE id = ?",
            (first.revision_id,),
        ),
        (
            "UPDATE numeric_quantile_definitions SET value_constraint = 'continuous' WHERE prediction_id = ?",
            (first.prediction_id,),
        ),
        (
            "DELETE FROM numeric_quantile_definitions WHERE prediction_id = ?",
            (first.prediction_id,),
        ),
        (
            "UPDATE predictions SET numeric_precision = 0 WHERE id = ?",
            (first.prediction_id,),
        ),
        (
            "UPDATE prediction_forecast_contracts SET forecast_deadline_at = ? WHERE prediction_id = ?",
            (format_utc(T0), first.prediction_id),
        ),
        (
            "INSERT INTO numeric_forecast_revisions (prediction_id, lower_scaled, median_scaled, upper_scaled, confidence_percent, created_at, sequence) VALUES (?, 0, 0, 0, 80, ?, 1)",
            (first.prediction_id, format_utc(T0)),
        ),
    ]
    for sql, parameters in commands:
        with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
            c.execute(sql, parameters)
    for bad_values, sequence, instant in (
        ((-200, -100, 1, 100, 200), 2, T0 + timedelta(minutes=1)),  # nonintegral
        ((-200, 100, 0, 100, 200), 2, T0 + timedelta(minutes=1)),  # crossing
        ((-200, -100, 0, 100, 200), 2, T0 + timedelta(minutes=1)),  # no-op
        ((0, 100, 200, 300, 400), 3, T0 + timedelta(minutes=1)),  # gap
        ((0, 100, 200, 300, 400), 2, T0),
        ((0, 100, 200, 300, 400), 2, DEADLINE.instant),
    ):
        with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
            c.execute(
                "INSERT INTO numeric_quantile_revisions (prediction_id, sequence, created_at, q05_scaled, q25_scaled, q50_scaled, q75_scaled, q95_scaled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (first.prediction_id, sequence, format_utc(instant), *bad_values),
            )
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
        c.execute(
            "INSERT INTO numeric_quantile_revisions (prediction_id, sequence, created_at, q05_scaled) VALUES (?, 2, ?, 0)",
            (first.prediction_id, format_utc(T0 + timedelta(minutes=1))),
        )
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
        resolution(c, first, actual=1)
    assert repo.list_revisions(first.prediction_id) == (first,)
    # The normal guarded-delete workflow is M51; parent cascade remains coherent.
    with database.transaction() as c:
        c.execute("DELETE FROM predictions WHERE id = ?", (first.prediction_id,))
        assert not c.execute("SELECT * FROM numeric_quantile_revisions").fetchall()
        assert not c.execute("PRAGMA foreign_key_check").fetchall()


def test_history_anchors_reject_wrong_prediction_wrong_model_and_stale_revision(
    storage,
):
    database, clock, repo = storage
    first = repo.create_prediction(new())
    other = repo.create_prediction(new())
    legacy = PredictionOperations(
        database, clock, UTC
    )._create_legacy_numeric_prediction("Legacy?", "mm", 2, -2, 0, 2, 80)
    for prediction_id, anchor in (
        (first.prediction_id, other.revision_id),
        (legacy.prediction_id, first.revision_id),
    ):
        for table in ("journal_entries", "forecast_reviews"):
            with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
                history_entry(
                    c,
                    table,
                    replace(first, prediction_id=prediction_id, revision_id=anchor),
                    T0,
                    "Mismatch",
                )
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
        c.execute(
            "INSERT INTO journal_entries(prediction_id, numeric_forecast_revision_id, body, created_at) VALUES (?, ?, 'Wrong model', ?)",
            (first.prediction_id, legacy.current_revision.revision_id, format_utc(T0)),
        )
    clock.instant += timedelta(minutes=5)
    second = repo.append_revision(first.prediction_id, quantiles(1), **context(first))
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
        history_entry(c, "journal_entries", first, clock.instant, "Stale")
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
        resolution(c, first)
    with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
        history_entry(c, "forecast_reviews", second, DEADLINE.instant, "Locked")
    with database.transaction() as c:
        history_entry(
            c, "journal_entries", second, DEADLINE.instant, "Locked journal is allowed"
        )
        resolution(c, second)
    for table in ("journal_entries", "forecast_reviews"):
        with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
            history_entry(c, table, second, clock.instant, "Terminal")


def snapshot(connection):
    tables = [
        r[0]
        for r in connection.execute(
            "SELECT name FROM sqlite_schema WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        t: (
            [r[1] for r in connection.execute(f"PRAGMA table_info({t})")],
            [
                tuple(row)
                for row in connection.execute(f'SELECT * FROM "{t}" ORDER BY 1')
            ],
        )
        for t in tables
    }


def test_quantile_correction_search_and_postmortem_keep_original_resolution(storage):
    database, _clock, repo = storage
    first = repo.create_prediction(new(NumericValueConstraint.WHOLE_NUMBER))
    with database.transaction() as c:
        resolution_id = resolution(c, first)
        original = tuple(c.execute("SELECT * FROM numeric_resolutions").fetchone())
    sql = """INSERT INTO numeric_quantile_resolution_corrections (
        prediction_id, numeric_resolution_id, sequence, old_actual_scaled, new_actual_scaled,
        old_effective_resolution_at, new_effective_resolution_at, actual_value_changed,
        effective_time_changed, old_resolution_notes, new_resolution_notes, resolution_notes_changed,
        old_postmortem, new_postmortem, postmortem_changed, correction_reason, corrected_at)
        VALUES (?, ?, 1, 0, ?, ?, ?, 1, 1, 'Resolved evidence', 'Corrected source', 1,
        NULL, 'New reflection', 1, ?, ?)"""
    parameters = (
        first.prediction_id,
        resolution_id,
        100,
        format_utc(T0 + timedelta(minutes=15)),
        format_utc(T0 + timedelta(minutes=20)),
        "Source timestamp corrected",
        format_utc(T0 + timedelta(hours=4)),
    )
    for bad in (
        parameters[:2] + (1,) + parameters[3:],
        parameters[:5] + (None,) + parameters[6:],
    ):
        with pytest.raises(sqlite3.IntegrityError), database.transaction() as c:
            c.execute(sql, bad)
    with database.transaction() as c:
        c.execute(sql, parameters)
        assert (
            tuple(c.execute("SELECT * FROM numeric_resolutions").fetchone()) == original
        )
        docs = project_prediction_documents(c, first.prediction_id)
        assert {d.text for d in docs if not d.is_superseded} >= {
            "Corrected source",
            "New reflection",
            "Source timestamp corrected",
        }
        assert next(d for d in docs if d.text == "Resolved evidence").is_superseded
    with (
        pytest.raises(sqlite3.IntegrityError, match="blank"),
        database.transaction() as c,
    ):
        c.execute(
            "INSERT INTO postmortem_completions(prediction_id, completed_at) VALUES (?, ?)",
            (first.prediction_id, format_utc(T0 + timedelta(hours=5))),
        )
    database.check_search_index()


def test_search_projection_failure_rolls_back_quantile_creation_and_revision(
    storage, monkeypatch
):
    from reckonsolve.data.search_index import SearchIndexError

    database, clock, repo = storage
    first = repo.create_prediction(new())
    clock.instant += timedelta(minutes=1)
    with database.transaction() as c:
        before = snapshot(c)

    def fail(_connection):
        raise SearchIndexError("forced projection failure")

    with monkeypatch.context() as patch:
        patch.setattr(
            "reckonsolve.data.database.refresh_pending_search_documents", fail
        )
        for action in (
            lambda: repo.create_prediction(new()),
            lambda: repo.append_revision(
                first.prediction_id, quantiles(1), **context(first)
            ),
        ):
            with pytest.raises(SearchIndexError, match="forced"):
                action()
    with database.transaction() as c:
        assert snapshot(c) == before


@pytest.mark.parametrize("fail_midway", [False, True])
def test_schema18_preserves_populated_legacy_rows_and_rolls_back_failure(
    tmp_path, fail_midway
):
    path = tmp_path / "upgrade.sqlite3"
    db = Database.open(path, migrations=MIGRATIONS[:17])
    clock = Clock()
    ops = PredictionOperations(db, clock, UTC)
    for binary in (False, True):
        p = (
            ops._create_legacy_prediction("Legacy binary", 70)
            if binary
            else ops._create_legacy_numeric_prediction(
                "Legacy numeric", "mm", 2, -2, 0, 2, 80
            )
        )
        kwargs = {
            "expected_revision_id": p.current_revision_id
            if binary
            else p.current_revision.revision_id,
            "expected_metadata_version": 1,
        }
        journal = (ops.add_journal_entry if binary else ops.add_numeric_journal_entry)(
            p.prediction_id, "Historical journal", **kwargs
        )
        (ops.correct_journal_entry if binary else ops.correct_numeric_journal_entry)(
            p.prediction_id,
            journal.entry_id,
            "Historical corrected journal",
            expected_correction_id=None,
        )
        (ops.add_forecast_review if binary else ops.add_numeric_forecast_review)(
            p.prediction_id, note="Historical review", **kwargs
        )
        if not binary:
            ops.resolve_numeric_prediction(p.prediction_id, "1.50", **kwargs)
            ops.correct_numeric_resolution(
                p.prediction_id,
                "1.75",
                resolution_notes=None,
                postmortem=None,
                correction_reason="Historical correction",
                expected_correction_id=None,
            )
    with db.transaction() as c:
        before = snapshot(c)
        schema_before = [
            tuple(row)
            for row in c.execute(
                "SELECT type, name, sql FROM sqlite_schema ORDER BY type, name"
            )
        ]
    analytics = ops.get_forecast_analytics()
    db.close()
    steps = MIGRATIONS[17].statements
    position = (
        next(
            i for i, sql in enumerate(steps) if sql == "DROP TABLE numeric_resolutions"
        )
        + 1
        if fail_midway
        else len(steps)
    )
    broken = replace(
        MIGRATIONS[17],
        statements=(
            *steps[:position],
            "SELECT missing_m50_column FROM predictions",
            *steps[position:],
        ),
    )
    with pytest.raises(sqlite3.OperationalError):
        Database.open(path, migrations=(*MIGRATIONS[:17], broken))
    with sqlite3.connect(path) as c:
        assert snapshot(c) == before
        assert (
            c.execute(
                "SELECT type, name, sql FROM sqlite_schema ORDER BY type, name"
            ).fetchall()
            == schema_before
        )

    upgraded = Database.open(path)
    try:
        with upgraded.transaction() as c:
            for table, (columns, rows) in before.items():
                if table == "schema_migrations":
                    continue
                assert [
                    tuple(r)
                    for r in c.execute(
                        f'SELECT {", ".join(columns)} FROM "{table}" ORDER BY 1'
                    )
                ] == rows
            assert not c.execute("SELECT * FROM numeric_quantile_revisions").fetchall()
            assert not c.execute(
                "SELECT * FROM numeric_quantile_definitions"
            ).fetchall()
            assert not c.execute("PRAGMA foreign_key_check").fetchall()
        assert (
            PredictionOperations(upgraded, clock, UTC).get_forecast_analytics()
            == analytics
        )
        upgraded.check_search_index()
    finally:
        upgraded.close()
    reopened = Database.open(path)
    assert reopened.schema_version == 18
    reopened.close()
