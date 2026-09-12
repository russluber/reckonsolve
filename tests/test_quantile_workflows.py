"""M51 public workflows on disposable databases, including legacy separation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest

from reckonsolve.application.errors import ApplicationError, ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import _run_create, _run_show
from reckonsolve.data.database import Database
from reckonsolve.domain.forecast_contracts import ForecastCohort
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.quantiles import NumericValueConstraint, QuantileRevision
from reckonsolve.ui.quantile_input import FiveQuantileInput
from reckonsolve.ui.screens import (
    NumericPredictionDetailScreen,
    ReviseQuantileForecastDialog,
)

T0 = datetime(2026, 9, 11, 10, tzinfo=UTC)
VALUES = {5: "-2.00", 25: "-1.00", 50: "0.00", 75: "1.00", 95: "2.00"}


@dataclass
class Clock:
    instant: datetime = T0

    def now(self):
        return self.instant


@pytest.fixture
def app_ops(tmp_path):
    db = Database.open(tmp_path / "m51.sqlite3")
    clock = Clock()
    ops = PredictionOperations(db, clock, UTC)
    yield db, clock, ops
    db.close()


def create(ops, **kwargs):
    fields = {
        "question": "How much rain?",
        "unit": "mm",
        "decimal_places": 2,
        "quantiles": VALUES,
        "value_constraint": NumericValueConstraint.CONTINUOUS,
        "forecast_deadline": T0 + timedelta(hours=2),
        "tags": ("weather",),
        "rationale": "Initial evidence",
    }
    fields.update(kwargs)
    return ops.create_numeric_prediction(**fields)


def context(pred):
    return {
        "expected_revision_id": pred.current_revision.revision_id,
        "expected_metadata_version": pred.metadata_version,
    }


def test_create_revise_review_journal_restart_and_all_read_surfaces(app_ops):
    db, clock, ops = app_ops
    first = create(ops)
    assert first.forecast_contract.cohort is ForecastCohort.QUANTILE_NUMERIC
    assert isinstance(first.current_revision, QuantileRevision)
    clock.instant += timedelta(minutes=1)
    revised = ops.revise_quantile_forecast(
        first.prediction_id, VALUES | {95: "3.50"}, **context(first)
    )
    clock.instant += timedelta(minutes=1)
    review = ops.add_numeric_forecast_review(
        first.prediction_id, note="Still fits", **context(revised)
    )
    clock.instant += timedelta(minutes=1)
    journal = ops.add_numeric_journal_entry(
        first.prediction_id, "New evidence", **context(revised)
    )
    clock.instant += timedelta(minutes=1)
    corrected = ops.correct_numeric_journal_entry(
        first.prediction_id,
        journal.entry_id,
        "Corrected evidence",
        expected_correction_id=None,
    )
    assert corrected.body == "Corrected evidence"
    assert review.revision == revised.current_revision
    assert len(ops.list_numeric_forecast_revisions(first.prediction_id)) == 2
    assert [e.kind for e in ops.list_numeric_timeline(first.prediction_id)] == [
        "forecast",
        "forecast",
        "review",
        "journal",
    ]
    assert (
        ops.browse_predictions().predictions[0].numeric_quantiles
        == revised.current_revision.quantiles
    )
    assert (
        ops.get_dashboard().open_predictions[0].numeric_quantiles
        == revised.current_revision.quantiles
    )
    output = StringIO()
    _run_show(ops, first.prediction_id, output)
    assert "90% interval: -2.00 to 3.50 mm" in output.getvalue()
    assert "Original body" in output.getvalue()
    path = db.path
    db.close()
    reopened = Database.open(path)
    try:
        other = PredictionOperations(reopened, clock, UTC)
        assert (
            other.get_numeric_prediction(first.prediction_id).current_revision
            == revised.current_revision
        )
        assert len(other.list_numeric_timeline(first.prediction_id)) == 4
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "changes",
    [
        {"quantiles": VALUES | {25: "9.00"}},
        {"quantiles": VALUES | {5: "-2.001"}},
        {"quantiles": {5: 1}},
        {
            "value_constraint": NumericValueConstraint.WHOLE_NUMBER,
            "quantiles": VALUES | {95: "2.50"},
        },
        {"forecast_deadline": T0},
        {"value_constraint": None},
    ],
)
def test_invalid_creation_is_atomic(app_ops, changes):
    _db, _clock, ops = app_ops
    with pytest.raises(ValidationError):
        create(ops, **changes)
    assert not ops.browse_predictions().predictions


def test_deadline_noop_stale_and_anchored_locked_journal(app_ops):
    _db, clock, ops = app_ops
    first = create(ops)
    with pytest.raises(ValidationError):
        ops.revise_quantile_forecast(first.prediction_id, VALUES, **context(first))
    clock.instant += timedelta(minutes=1)
    revised = ops.revise_quantile_forecast(
        first.prediction_id, VALUES | {95: "3"}, **context(first)
    )
    with pytest.raises(ApplicationError):
        ops.add_numeric_forecast_review(
            first.prediction_id, note=None, **context(first)
        )
    clock.instant = T0 + timedelta(hours=2)
    assert (
        ops.get_numeric_prediction(first.prediction_id).status
        is PredictionStatus.LOCKED
    )
    with pytest.raises(ApplicationError):
        ops.revise_quantile_forecast(first.prediction_id, VALUES, **context(revised))
    with pytest.raises(ApplicationError):
        ops.add_numeric_forecast_review(
            first.prediction_id, note=None, **context(revised)
        )
    note = ops.add_numeric_journal_entry(
        first.prediction_id, "After deadline", **context(revised)
    )
    assert note.revision == revised.current_revision


def test_preview_valid_only_ties_and_detail(qtbot, app_ops):
    _db, _clock, ops = app_ops
    editor = FiveQuantileInput()
    qtbot.addWidget(editor)
    editor.set_definition("days", 2, NumericValueConstraint.WHOLE_NUMBER)
    editor.show()
    assert editor.preview.isHidden()
    first = create(
        ops,
        unit="days",
        value_constraint=NumericValueConstraint.WHOLE_NUMBER,
        quantiles={5: 1, 25: 1, 50: 1, 75: 2, 95: 2},
    )
    editor.set_quantiles(first.current_revision.quantiles)
    assert not editor.preview.isHidden()
    assert "Outer tails are unspecified" in editor.preview.accessibleDescription()
    editor.preview.grab()
    editor.inputs[25].setText("3")
    assert editor.preview.isHidden()
    detail = NumericPredictionDetailScreen(ops)
    qtbot.addWidget(detail)
    detail.show_prediction(first)
    detail.show()
    assert not detail.quantile_cdf.isHidden()
    assert not detail.resolve_button.isEnabled()
    detail.grab()
    dialog = ReviseQuantileForecastDialog(ops, first)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.grab()


def test_metadata_search_deadline_filter_and_delete_invalidation(app_ops):
    from reckonsolve.domain.browser import ArchiveDateMeaning

    db, clock, ops = app_ops
    first = create(ops)
    clock.instant += timedelta(minutes=1)
    metadata = {
        "question": first.question,
        "background": "Monsoon observations",
        "resolution_criteria": None,
        "forecast_deadline": None,
        "expected_resolution": None,
        "tags": ("monsoon",),
        "expected_metadata_version": 1,
    }
    updated = ops.update_metadata(first.prediction_id, **metadata)
    assert updated.current_revision == first.current_revision
    assert updated.forecast_contract == first.forecast_contract
    assert (
        ops.search_predictions("Monsoon").hits[0].prediction.numeric_quantiles
        == first.current_revision.quantiles
    )
    assert ops.browse_predictions(
        date_meaning=ArchiveDateMeaning.FORECAST_DEADLINE,
        date_start=T0.date(),
        date_end=T0.date(),
    ).predictions
    with pytest.raises(ValidationError):
        ops.update_metadata(
            first.prediction_id,
            **(
                metadata
                | {"forecast_deadline": T0.date(), "expected_metadata_version": 2}
            ),
        )
    with pytest.raises(ApplicationError):
        ops.delete_numeric_prediction(
            first.prediction_id, **context(updated), confirm_permanent_deletion=True
        )
    invalid = ops.invalidate_numeric_prediction(
        first.prediction_id, reason="Bad premise", **context(updated)
    )
    assert invalid.status is PredictionStatus.INVALID
    assert not ops.get_dashboard().open_predictions
    disposable = create(ops, question="Disposable")
    ops.delete_numeric_prediction(
        disposable.prediction_id, **context(disposable), confirm_permanent_deletion=True
    )
    assert [p.prediction_id for p in ops.browse_predictions().predictions] == [
        first.prediction_id
    ]
    with db.transaction() as connection:
        assert not connection.execute("PRAGMA foreign_key_check").fetchall()


@pytest.mark.parametrize("operation", ["revision", "review", "delete"])
def test_commit_clock_rechecks_deadline_inside_transaction(
    app_ops, monkeypatch, operation
):
    db, clock, ops = app_ops
    first = create(ops)
    monkeypatch.setattr(
        clock,
        "now",
        lambda: T0 + timedelta(hours=2 if db._connection.in_transaction else 1),
    )
    with pytest.raises(ApplicationError):
        if operation == "revision":
            ops.revise_quantile_forecast(
                first.prediction_id, VALUES | {95: 3}, **context(first)
            )
        elif operation == "review":
            ops.add_numeric_forecast_review(
                first.prediction_id, note=None, **context(first)
            )
        else:
            ops.delete_numeric_prediction(
                first.prediction_id, **context(first), confirm_permanent_deletion=True
            )
    assert len(ops.list_numeric_timeline(first.prediction_id)) == 1


def test_quantile_dialogs_preserve_anchors_and_cancel_without_writes(qtbot, app_ops):
    from reckonsolve.ui.screens import (
        AddNumericJournalEntryDialog,
        CorrectNumericJournalEntryDialog,
        EditPredictionDetailsDialog,
        ForecastReviewDialog,
    )

    _db, clock, ops = app_ops
    first = create(ops)
    revision = ReviseQuantileForecastDialog(ops, first)
    qtbot.addWidget(revision)
    revision.show()
    revision.reject()
    assert len(ops.list_numeric_timeline(first.prediction_id)) == 1
    clock.instant += timedelta(minutes=1)
    review = ForecastReviewDialog(ops, first)
    qtbot.addWidget(review)
    review.note_input.setPlainText("All five still fit")
    review.submit()
    clock.instant += timedelta(minutes=1)
    journal = AddNumericJournalEntryDialog(ops, first)
    qtbot.addWidget(journal)
    journal.body_input.setPlainText("Observed weather")
    journal.submit()
    event = ops.list_numeric_timeline(first.prediction_id)[-1]
    correction = CorrectNumericJournalEntryDialog(ops, event)
    qtbot.addWidget(correction)
    correction.body_input.setPlainText("Observed rainfall")
    correction.submit()
    assert (
        ops.list_numeric_timeline(first.prediction_id)[-1].body == "Observed rainfall"
    )
    details = EditPredictionDetailsDialog(ops, first)
    qtbot.addWidget(details)
    details.show()
    assert "Value constraint: continuous" in details.numeric_definition_context.text()
    assert len(ops.list_numeric_forecast_revisions(first.prediction_id)) == 1


def test_cli_quantiles_create_revise_review_and_legacy_dispatch(app_ops):
    from reckonsolve.cli_creation import PromptSession
    from reckonsolve.cli_mutations import review_interactively, revise_interactively

    _db, clock, ops = app_ops
    output = StringIO()
    assert (
        _run_create(
            ops,
            PredictionType.NUMERIC,
            StringIO(
                "How many days?\ndays\n2\nw\n1\n5\n3\n2\n4\n2026-09-11T12:00:00Z\n\n"
            ),
            output,
            StringIO(),
        )
        == 0
    )
    assert "90% interval: 1.00 to 5.00 days" in output.getvalue()
    clock.instant += timedelta(minutes=1)
    session = PromptSession(
        StringIO("\n\n\n\n\n\n6\n\n\n\nChanged outer anchor\n"), output, StringIO()
    )
    revise_interactively(ops, 1, session)
    assert "unchanged" in session.errors.getvalue()
    revised = ops.get_numeric_prediction(1)
    assert str(revised.current_revision.quantiles.q95) == "6.00"
    clock.instant += timedelta(minutes=1)
    review_interactively(
        ops, 1, PromptSession(StringIO("No change\n"), output, StringIO())
    )
    assert len(ops.list_numeric_forecast_revisions(1)) == 2
    legacy = ops._create_legacy_numeric_prediction(
        "Legacy days", "days", 0, 1, 3, 5, 80
    )
    revise_interactively(
        ops,
        legacy.prediction_id,
        PromptSession(StringIO("\n\n6\n\nLegacy change\n"), output, StringIO()),
    )
    assert (
        ops.get_numeric_prediction(
            legacy.prediction_id
        ).current_revision.confidence_percent
        == 80
    )


@pytest.mark.parametrize("width", [760, 1600])
def test_complete_quantile_form_and_detail_layout(qtbot, tmp_path, width):
    from PySide6.QtCore import QDate, Qt
    from PySide6.QtWidgets import QLabel, QScrollArea

    from reckonsolve.app import create_runtime
    from reckonsolve.ui.screens import NewPredictionScreen

    runtime = create_runtime(database_path=tmp_path / "layout.sqlite3")
    window = runtime.window
    qtbot.addWidget(window)
    window.resize(width, 1000)
    window.show()
    window.navigate_to("New Prediction")
    form = window.findChild(NewPredictionScreen)
    form.prediction_type_input.setCurrentIndex(
        form.prediction_type_input.findData("numeric")
    )
    form.question_input.setText("What value will this instrument report?")
    form.numeric_unit_input.setText("degrees")
    form.numeric_precision_input.setValue(2)
    form.numeric_constraint_input.setCurrentIndex(1)
    for level, value in VALUES.items():
        form.quantile_input.inputs[level].setText(value)
    form.numeric_exact_deadline.toggle.setChecked(True)
    form.numeric_exact_deadline.editor.setDate(QDate(2099, 12, 30))
    form.numeric_exact_deadline.offset.setText("+00:00")
    qtbot.wait(30)
    scroll = form.findChild(QScrollArea, "newPredictionScrollArea")
    assert scroll.horizontalScrollBar().maximum() == 0
    assert not form.quantile_input.preview.isHidden()
    assert window.grab().save(str(tmp_path / "quantile-create.png"))
    form.submit()
    assert window.current_screen_name == "Prediction Detail"
    clock_ops = PredictionOperations(runtime.database)
    created = clock_ops.get_numeric_prediction(1)
    clock_ops.add_numeric_journal_entry(
        1, "<b>Literal evidence</b>", **context(created)
    )
    detail = window.findChild(NumericPredictionDetailScreen)
    detail.show_prediction(created)
    qtbot.wait(30)
    for label in detail.findChildren(QLabel):
        if "Literal evidence" in label.text():
            assert label.textFormat() == Qt.TextFormat.PlainText
    assert window.grab().save(str(tmp_path / "quantile-detail.png"))
    runtime.close()


@pytest.mark.parametrize(
    "input_text",
    ["How many?\ndays\n0\nw\n1\n", "How many?\ndays\n0\nw\n1\n5\n3\n2\n4\n"],
)
def test_cli_quantile_cancellation_leaves_no_partial_forecast(app_ops, input_text):
    from reckonsolve.cli_creation import CliInputCancelled

    _db, _clock, ops = app_ops
    with pytest.raises(CliInputCancelled):
        _run_create(
            ops, PredictionType.NUMERIC, StringIO(input_text), StringIO(), StringIO()
        )
    assert not ops.browse_predictions().predictions


def test_search_reveals_quantile_journal_original_version(qtbot, app_ops):
    from PySide6.QtWidgets import QGroupBox, QLabel

    _db, clock, ops = app_ops
    first = create(ops)
    clock.instant += timedelta(minutes=1)
    note = ops.add_numeric_journal_entry(
        first.prediction_id, "Superseded drizzle", **context(first)
    )
    clock.instant += timedelta(minutes=1)
    ops.correct_numeric_journal_entry(
        first.prediction_id,
        note.entry_id,
        "Current rainfall",
        expected_correction_id=None,
    )
    assert not ops.search_predictions("drizzle").hits
    hit = ops.search_predictions("drizzle", include_superseded=True).hits[0]
    detail = NumericPredictionDetailScreen(ops)
    qtbot.addWidget(detail)
    detail.show_prediction(first)
    detail.show()
    history = detail.findChild(QGroupBox, f"journalEntryEditHistory{note.entry_id}")
    assert not history.isChecked()
    detail.focus_search_match(hit.best_match.document)
    assert history.isChecked()
    assert detail.findChild(
        QLabel, f"journalEntryOriginalBody{note.entry_id}"
    ).isVisible()
