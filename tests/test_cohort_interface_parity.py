"""M54 mixed-cohort parity through independent desktop and CLI connections."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from io import StringIO

import pytest

from reckonsolve import cli
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.domain.browser import ArchiveDateMeaning, ArchiveQuery
from reckonsolve.domain.forecast_contracts import ForecastCohort
from reckonsolve.domain.predictions import BinaryOutcome, NumericPrediction
from reckonsolve.domain.quantiles import NumericValueConstraint
from reckonsolve.domain.saved_views import SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode
from reckonsolve.identity import DEVELOPMENT_APPLICATION

START = datetime(2026, 9, 13, 4, 5, 6, 123456, tzinfo=UTC)
DEADLINE = START + timedelta(hours=2)
VALUES = {5: -10, 25: -5, 50: 0, 75: 5, 95: 10}
COHORTS = tuple(ForecastCohort)


@dataclass
class Clock:
    instant: datetime = START

    def now(self) -> datetime:
        return self.instant


@pytest.fixture
def mixed(tmp_path, monkeypatch):
    database = Database.open(tmp_path / "m54.sqlite3")
    clock = Clock()
    ops = PredictionOperations(database, clock, UTC)

    def runtime(**_kwargs):
        other = Database.open(database.path)
        return cli.CliRuntime(
            other, PredictionOperations(other, clock, UTC), DEVELOPMENT_APPLICATION
        )

    monkeypatch.setattr(cli, "create_runtime", runtime)
    yield database, clock, ops
    database.close()


def create(ops, cohort):
    common = {"tags": ("parity",), "rationale": "original evidence"}
    question = f"Archive subject {cohort.value}?"
    if cohort is ForecastCohort.LEGACY_BINARY:
        return ops._create_legacy_prediction(question, 40, **common)
    if cohort is ForecastCohort.TRAJECTORY_BINARY:
        return ops.create_prediction(question, 40, forecast_deadline=DEADLINE, **common)
    if cohort is ForecastCohort.LEGACY_NUMERIC:
        return ops._create_legacy_numeric_prediction(
            question, "units", 0, -10, 0, 10, 80, **common
        )
    return ops.create_numeric_prediction(
        question,
        "units",
        0,
        VALUES,
        value_constraint=NumericValueConstraint.WHOLE_NUMBER,
        forecast_deadline=DEADLINE,
        **common,
    )


def context(prediction):
    return {
        "expected_revision_id": prediction.current_revision.revision_id
        if isinstance(prediction, NumericPrediction)
        else prediction.current_revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


def command(*args, input_text="", input_stream=None):
    output, errors = StringIO(), StringIO()
    code = cli.run(
        args,
        stdin=input_stream or StringIO(input_text),
        stdout=output,
        stderr=errors,
        identity=DEVELOPMENT_APPLICATION,
    )
    return code, output.getvalue(), errors.getvalue()


def canonical_dump(database):
    """Skip derived search rows: repair may legitimately replace those."""
    connection = database._require_connection()
    tables = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return tuple(
        (
            name,
            tuple(
                tuple(row)
                for row in connection.execute(f'SELECT * FROM "{name}" ORDER BY 1')
            ),
        )
        for (name,) in tables
        if "search" not in name
    )


@pytest.mark.parametrize("cohort", COHORTS)
def test_cli_mutations_read_back_through_existing_desktop_connection(mixed, cohort):
    db, clock, ops = mixed
    prediction = create(ops, cohort)
    identifier = str(prediction.prediction_id)
    clock.instant += timedelta(minutes=1)
    revision_input = (
        "55\nchanged evidence\n"
        if not isinstance(prediction, NumericPrediction)
        else "-9\n0\n11\n85\nchanged evidence\n"
        if cohort is ForecastCohort.LEGACY_NUMERIC
        else "-9\n11\n0\n-4\n6\nchanged evidence\n"
    )
    code, _, errors = command("revise", identifier, input_text=revision_input)
    assert code == 0, errors
    current = ops.get_prediction_for_navigation(prediction.prediction_id)
    assert current.forecast_contract == prediction.forecast_contract
    assert (
        context(current)["expected_revision_id"]
        != context(prediction)["expected_revision_id"]
    )
    for action, note in (
        ("review", "retained evidence"),
        ("journal", "journal evidence"),
    ):
        clock.instant += timedelta(minutes=1)
        code, _, errors = command(action, identifier, input_text=note + "\n")
        assert code == 0, errors
        assert ops.search_predictions(note).hits
        assert context(
            ops.get_prediction_for_navigation(prediction.prediction_id)
        ) == context(current)

    # A Windows ISO offset must retain the exact same UTC instant and microseconds.
    effective = clock.instant + timedelta(minutes=1)
    clock.instant = effective + timedelta(minutes=2)
    timing = (
        ""
        if prediction.forecast_contract.is_legacy
        else effective.astimezone(timezone(timedelta(hours=-7))).isoformat() + "\n"
    )
    outcome = "yes" if not isinstance(prediction, NumericPrediction) else "2"
    code, _, errors = command(
        "resolve",
        identifier,
        input_text=f"{outcome}\n{timing}originalterminal\n\ny\n",
    )
    assert code == 0, errors
    history = (
        ops.get_binary_resolution_history(prediction.prediction_id)
        if not isinstance(prediction, NumericPrediction)
        else ops.get_numeric_resolution_history(prediction.prediction_id)
    )
    assert history.original.resolved_at == clock.instant
    if not prediction.forecast_contract.is_legacy:
        assert history.original.effective_resolution_at == effective
    before = canonical_dump(db)
    code, output, errors = command("show", identifier)
    assert code == 0, errors
    assert f"Model: {prediction.forecast_contract.forecast_model.value}" in output
    assert (
        f"Scoring contract: {prediction.forecast_contract.scoring_contract.value}"
        in output
    )
    for note in (
        "changed evidence",
        "retained evidence",
        "journal evidence",
        "originalterminal",
    ):
        assert note in output
    if not prediction.forecast_contract.is_legacy:
        assert DEADLINE.astimezone().isoformat(sep=" ") in output
        assert effective.astimezone().isoformat(sep=" ") in output
    assert canonical_dump(db) == before


def test_mixed_retrieval_saved_tags_and_repair_remain_dynamic_and_read_only(mixed):
    db, clock, ops = mixed
    predictions = [create(ops, cohort) for cohort in COHORTS]
    config = SavedViewConfiguration(
        "Archive", SearchMatchMode.ALL, False, ArchiveQuery(tags=("parity",))
    )
    view = ops.create_saved_view("Mixed cohorts", config)
    before = canonical_dump(db)
    for args in (
        ("list",),
        ("search", "Archive"),
        ("saved-view", "--id", str(view.saved_view_id)),
    ):
        code, output, errors = command(*args)
        assert code == 0, errors
        for prediction in predictions:
            assert prediction.question in output
    assert canonical_dump(db) == before
    assert len(ops.get_dashboard().open_predictions) == 4

    # A stable tag rename updates a saved configuration, not stored result membership.
    tag = ops.list_tags()[0]
    ops.rename_tag(ops.preview_tag_rename(tag.tag_id, "renamed"))
    current_view = ops.list_saved_views()[0]
    assert current_view.configuration.archive_query.tags == ("renamed",)
    clock.instant += timedelta(minutes=1)
    extra = ops.create_prediction(
        "Additional Archive subject?",
        60,
        forecast_deadline=DEADLINE,
        tags=("renamed", "merge target"),
    )
    code, output, errors = command("saved-view", "--id", str(view.saved_view_id))
    assert code == 0, errors
    assert extra.question in output
    tags = {tag.display_name: tag for tag in ops.list_tags()}
    ops.merge_tags(
        ops.preview_tag_merge((tags["renamed"].tag_id,), tags["merge target"].tag_id)
    )
    assert len(ops.search_predictions("Archive", tags=("merge target",)).hits) == 5
    before = canonical_dump(db)
    hits = ops.search_predictions("Archive")
    ops.repair_search_index()
    assert ops.search_predictions("Archive") == hits
    assert canonical_dump(db) == before
    ops.delete_tag(ops.preview_tag_delete(tags["merge target"].tag_id))
    assert not ops.list_tags()
    assert len(ops.search_predictions("Archive").hits) == 5


@pytest.mark.parametrize("cohort", COHORTS)
def test_stale_cli_review_does_not_overwrite_concurrent_gui_revision(mixed, cohort):
    _db, clock, ops = mixed
    prediction = create(ops, cohort)
    clock.instant += timedelta(minutes=1)

    class ConcurrentInput(StringIO):
        changed = False

        def readline(self, *args, **kwargs):
            if not self.changed:
                self.changed = True
                if not isinstance(prediction, NumericPrediction):
                    ops.revise_forecast(
                        prediction.prediction_id, 70, **context(prediction)
                    )
                elif cohort is ForecastCohort.LEGACY_NUMERIC:
                    ops.revise_numeric_forecast(
                        prediction.prediction_id, -9, 0, 11, 85, **context(prediction)
                    )
                else:
                    ops.revise_quantile_forecast(
                        prediction.prediction_id,
                        VALUES | {95: 11},
                        **context(prediction),
                    )
            return super().readline(*args, **kwargs)

    code, _, errors = command(
        "review",
        str(prediction.prediction_id),
        input_stream=ConcurrentInput("stale review\n"),
    )
    assert code == 1
    assert "changed" in errors
    assert not ops.search_predictions("stale review").hits
    assert (
        context(ops.get_prediction_for_navigation(prediction.prediction_id))[
            "expected_revision_id"
        ]
        != context(prediction)["expected_revision_id"]
    )


@pytest.mark.parametrize("cohort", COHORTS)
def test_lock_at_cli_commit_rolls_back_without_partial_history(
    mixed, monkeypatch, cohort
):
    db, clock, ops = mixed
    prediction = create(ops, cohort)
    clock.instant += timedelta(minutes=1)
    other = Database.open(db.path)
    other._require_connection().execute("PRAGMA busy_timeout = 1")
    monkeypatch.setattr(
        cli,
        "create_runtime",
        lambda **kwargs: cli.CliRuntime(
            other, PredictionOperations(other, clock, UTC), DEVELOPMENT_APPLICATION
        ),
    )
    before = canonical_dump(db)

    class LockedInput(StringIO):
        def readline(self, *args, **kwargs):
            db._require_connection().execute("BEGIN IMMEDIATE")
            return super().readline(*args, **kwargs)

    try:
        code, _, errors = command(
            "review",
            str(prediction.prediction_id),
            input_stream=LockedInput("locked review\n"),
        )
    finally:
        db._require_connection().execute("ROLLBACK")
    assert code == 1
    assert "locked" in errors.casefold()
    assert canonical_dump(db) == before


def test_local_deadline_calendar_filter_keeps_exact_instant(mixed):
    db, _, ops = mixed
    for cohort in COHORTS:
        create(ops, cohort)
    local_zone = timezone(timedelta(hours=-7))
    local_ops = PredictionOperations(db, Clock(), local_zone)
    day = DEADLINE.astimezone(local_zone).date()
    results = local_ops.browse_predictions(
        date_meaning=ArchiveDateMeaning.FORECAST_DEADLINE, date_start=day, date_end=day
    )
    assert len(results.predictions) == 2
    assert all(
        p.forecast_contract.forecast_deadline.instant == DEADLINE
        for p in results.predictions
    )


@pytest.mark.parametrize(
    "column,value",
    [
        ("forecast_model", "numeric-future-v9"),
        ("scoring_contract", "numeric-future-score"),
        ("scoring_contract", "numeric-interval-score-v1"),
    ],
)
def test_unknown_or_mismatched_identity_fails_closed_live_and_on_reopen(
    mixed, column, value
):
    db, _, ops = mixed
    prediction = create(ops, ForecastCohort.QUANTILE_NUMERIC)
    connection = db._require_connection()
    # Deliberately emulate an unsupported/corrupted file, only in a disposable DB.
    connection.execute("DROP TRIGGER prediction_forecast_contracts_are_immutable")
    connection.execute("PRAGMA ignore_check_constraints = ON")
    connection.execute(
        f"UPDATE prediction_forecast_contracts SET {column} = ? WHERE prediction_id = ?",
        (value, prediction.prediction_id),
    )
    for read in (
        ops.browse_predictions,
        ops.get_dashboard,
        ops.get_forecast_analytics,
        lambda: ops.search_predictions("Archive"),
        lambda: ops.search_predictions("nohitswhatsoever"),
    ):
        with pytest.raises(ForecastContractIntegrityError, match="contract"):
            read()
    with pytest.raises(ForecastContractIntegrityError, match="contract"):
        Database.open(db.path)
    code, _, errors = command("list")
    assert code == 1
    assert errors.startswith("Error:") and "contract" in errors


@pytest.mark.parametrize("forecast_type", ["binary", "numeric"])
def test_public_cli_creation_exact_offset_and_cancel_without_partial_rows(
    mixed, forecast_type
):
    db, _clock, ops = mixed
    question = "Created from the independent terminal?"
    fields = (
        f"{question}\n50\n"
        if forecast_type == "binary"
        else f"{question}\nunits\n2\nw\n-10\n10\n0\n-5\n5\n"
    )
    # Reject offset-free input, then accept an explicitly offset exact instant.
    iso = DEADLINE.astimezone(timezone(timedelta(hours=5, minutes=30))).isoformat()
    code, _, errors = command(
        "create",
        forecast_type,
        input_text=fields + "2026-09-13T06:05\n" + iso + "\nn\n",
    )
    assert code == 0, errors
    assert "offset" in errors
    prediction = ops.get_prediction_for_navigation(1)
    assert prediction.forecast_contract.forecast_deadline.instant == DEADLINE
    assert not prediction.forecast_contract.is_legacy
    assert prediction.question == question
    before = canonical_dump(db)
    code, _, _ = command("create", forecast_type, input_text=fields)
    assert code == 130
    assert canonical_dump(db) == before


@pytest.mark.parametrize("cohort", COHORTS)
def test_gui_corrections_update_cli_effective_and_superseded_retrieval(mixed, cohort):
    db, clock, ops = mixed
    prediction = create(ops, cohort)
    identifier = str(prediction.prediction_id)
    numeric = isinstance(prediction, NumericPrediction)
    clock.instant += timedelta(minutes=1)
    action = ops.add_numeric_journal_entry if numeric else ops.add_journal_entry
    journal = action(prediction.prediction_id, "oldjournalword", **context(prediction))
    correct_journal = (
        ops.correct_numeric_journal_entry if numeric else ops.correct_journal_entry
    )
    correct_journal(
        prediction.prediction_id,
        journal.entry_id,
        "newjournalword",
        expected_correction_id=None,
    )
    clock.instant += timedelta(minutes=1)
    recorded = clock.instant
    code, _, errors = command(
        "resolve",
        identifier,
        input_text=("2\n" if numeric else "yes\n")
        + ("now\n" if not prediction.forecast_contract.is_legacy else "")
        + "oldterminalword\n\ny\n",
    )
    assert code == 0, errors
    original = ops.get_prediction_scorecard(prediction.prediction_id)
    correction = (
        ops.correct_numeric_resolution if numeric else ops.correct_binary_resolution
    )
    clock.instant += timedelta(minutes=1)
    timing = (
        {"effective_resolution_at": START + timedelta(seconds=30)}
        if not prediction.forecast_contract.is_legacy
        else {}
    )
    correction(
        prediction.prediction_id,
        3 if numeric else BinaryOutcome.NO,
        resolution_notes="newterminalword",
        postmortem="retrospectiveword",
        correction_reason="auditreasonword",
        expected_correction_id=None,
        **timing,
    )
    corrected = ops.get_prediction_scorecard(prediction.prediction_id)
    assert corrected != original
    before = canonical_dump(db)
    for repair in (False, True):
        if repair:
            ops.repair_search_index()
        for term in ("oldjournalword", "oldterminalword"):
            assert not ops.search_predictions(term).hits
            assert len(ops.search_predictions(term, include_superseded=True).hits) == 1
            code, output, errors = command("search", term, "--include-superseded")
            assert code == 0, errors
            assert prediction.question in output
        for term in (
            "newjournalword",
            "newterminalword",
            "retrospectiveword",
            "auditreasonword",
        ):
            assert len(ops.search_predictions(term).hits) == 1
        assert not ops.get_dashboard().needs_postmortem_predictions
        code, output, errors = command("show", identifier)
        assert code == 0, errors
        assert "oldterminalword" in output and "newterminalword" in output
        assert recorded.astimezone().isoformat(sep=" ") in output
        assert ops.get_prediction_scorecard(prediction.prediction_id) == corrected
        assert canonical_dump(db) == before
    # Structured model/scoring identities and times are not searchable prose.
    for term in (
        prediction.forecast_contract.forecast_model.value,
        prediction.forecast_contract.scoring_contract.value,
        "123456",
    ):
        assert not ops.search_predictions(term).hits
