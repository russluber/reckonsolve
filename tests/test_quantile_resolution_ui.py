"""M52 exact terminal input and scorecard parity across desktop and CLI."""

from datetime import UTC, timedelta
from io import StringIO

import pytest
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QGroupBox, QLabel, QMessageBox
from test_quantile_resolution import START, Clock, context, create

from reckonsolve import cli
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.ui.screens import (
    CorrectNumericResolutionDialog,
    NumericPredictionDetailScreen,
    ResolveNumericPredictionDialog,
)
from reckonsolve.ui.visual_system import install_visual_system


@pytest.fixture
def active(tmp_path):
    db = Database.open(tmp_path / "forms.sqlite3")
    clock = Clock()
    ops = PredictionOperations(db, clock, UTC)
    first = create(ops)
    clock.instant += timedelta(hours=1)
    p = ops.revise_quantile_forecast(
        first.prediction_id, {5: 0, 25: 5, 50: 10, 75: 15, 95: 20}, **context(first)
    )
    clock.instant += timedelta(hours=2)
    yield db, clock, ops, p
    db.close()


def set_time(widget, value):
    widget.use_now.setChecked(False)
    widget.editor.setDate(QDate(value.year, value.month, value.day))
    widget.editor.setTime(
        QTime(value.hour, value.minute, value.second, value.microsecond // 1000)
    )
    widget.offset.setText("+00:00")


def texts(widget):
    return "\n".join(label.text() for label in widget.findChildren(QLabel))


def test_resolution_dialog_and_scored_revision_exclusion(qtbot, active):
    _, clock, ops, p = active
    dialog = ResolveNumericPredictionDialog(ops, p)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.actual_value_input.setText("10")
    set_time(dialog.effective_time, clock.instant + timedelta(hours=1))
    dialog.submit()
    assert dialog.form_error.isVisible()
    assert ops.get_numeric_prediction(p.prediction_id).resolution is None
    set_time(dialog.effective_time, START + timedelta(hours=1))
    dialog.submit()
    screen = NumericPredictionDetailScreen(ops)
    qtbot.addWidget(screen)
    screen.show_prediction(ops.get_numeric_prediction(p.prediction_id))
    screen.show()
    assert screen.quantile_scorecard.isVisible()
    assert screen.scorecard_section.isHidden()
    assert "Recorded at" in screen.resolution_time.text()
    assert "Effective resolution" in screen.resolution_time.text()
    assert "Scored revision 1" in texts(screen.quantile_scorecard)
    assert "WIS:" in texts(screen.quantile_scorecard)
    assert "Delta WIS" in texts(screen.quantile_scorecard)
    assert "weighted contribution" in texts(screen.quantile_scorecard)
    assert "Updating Gain" not in texts(screen.quantile_scorecard)
    details = screen.quantile_scorecard.findChild(QGroupBox)
    assert not details.isChecked()
    details.setChecked(True)
    assert (
        screen.findChild(
            QLabel, f"numericForecastExcluded{p.current_revision.revision_id}"
        )
        is not None
    )
    assert len(ops.list_numeric_forecast_revisions(p.prediction_id)) == 2


def test_resolution_dialog_cancel_preserves_open_history(qtbot, active):
    _, _, ops, p = active
    before = ops.list_numeric_forecast_revisions(p.prediction_id)
    dialog = ResolveNumericPredictionDialog(ops, p)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.actual_value_input.setText("10")
    dialog.reject()
    assert ops.get_numeric_prediction(p.prediction_id).resolution is None
    assert ops.list_numeric_forecast_revisions(p.prediction_id) == before


def test_correction_preserves_hidden_precision_cancel_and_unscored(
    qtbot, active, monkeypatch
):
    _, _, ops, p = active
    exact = START + timedelta(hours=2, microseconds=123456)
    p = ops.resolve_numeric_prediction(
        p.prediction_id, 10, effective_resolution_at=exact, **context(p)
    )
    original = ops.get_numeric_resolution_history(p.prediction_id)
    dialog = CorrectNumericResolutionDialog(ops, p, original)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    dialog.show()
    assert dialog.effective_time.value() == exact
    dialog.notes_input.setPlainText("Text-only correction")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Cancel
    )
    dialog.submit()
    assert ops.get_numeric_resolution_history(p.prediction_id) == original
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *_args: QMessageBox.StandardButton.Yes
    )
    dialog.submit()
    history = ops.get_numeric_resolution_history(p.prediction_id)
    assert history.effective.effective_resolution_at == exact
    assert history.corrections[0].changed_fields == ("resolution_notes",)
    next_dialog = CorrectNumericResolutionDialog(ops, p, history)
    next_dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(next_dialog)
    next_dialog.show()
    set_time(next_dialog.effective_time, START)
    next_dialog.submit()
    assert "Explain why" in next_dialog.form_error.text()
    next_dialog.reason_input.setText("Source was known at creation")
    next_dialog.submit()
    screen = NumericPredictionDetailScreen(ops)
    qtbot.addWidget(screen)
    screen.show_prediction(ops.get_numeric_prediction(p.prediction_id))
    screen.show()
    assert "Not scored" in texts(screen.quantile_scorecard)
    assert "at or before" in texts(screen.quantile_scorecard)
    assert "Effective resolution time" in texts(screen.resolution_history)
    assert (
        ops.get_numeric_resolution_history(p.prediction_id).original
        == original.original
    )


@pytest.mark.parametrize(
    "effective", ["now", "2026-09-12T13:00:00+00:00", "2026-09-12T12:00:00+00:00"]
)
def test_cli_resolution_show_and_corrected_history(active, monkeypatch, effective):
    db, clock, ops, p = active
    factory = cli.create_runtime

    def runtime(**kwargs):
        result = factory(**kwargs)
        result.operations = PredictionOperations(result.database, clock, UTC)
        return result

    monkeypatch.setattr(cli, "create_runtime", runtime)
    output, errors = StringIO(), StringIO()
    assert (
        cli.run(
            ["resolve", str(p.prediction_id)],
            database_path=db.path,
            stdin=StringIO(f"10\ninvalid\n{effective}\nSource\nReflection\ny\n"),
            stdout=output,
            stderr=errors,
        )
        == 0
    )
    assert "exact time with an offset" in errors.getvalue()
    output = StringIO()
    assert (
        cli.run(
            ["show", str(p.prediction_id)],
            database_path=db.path,
            stdout=output,
            stderr=errors,
        )
        == 0
    )
    text = output.getvalue()
    assert "Recorded at:" in text
    assert "Effective resolution time:" in text
    assert "not scoring authority" in text
    assert "Numeric WIS scorecard" in text
    assert "Updating Gain" not in text
    if "12:00" in effective:
        assert "Not scored" in text
    else:
        assert "Delta WIS" in text
    ops.correct_numeric_resolution(
        p.prediction_id,
        20,
        effective_resolution_at=START + timedelta(hours=1),
        resolution_notes="Amended source",
        postmortem="Reflection",
        correction_reason="Corrected source time",
        expected_correction_id=None,
    )
    output = StringIO()
    assert (
        cli.run(
            ["show", str(p.prediction_id)],
            database_path=db.path,
            stdout=output,
            stderr=errors,
        )
        == 0
    )
    assert "Corrected source time" in output.getvalue()
    assert "Excluded from scoring" in output.getvalue()


def test_cli_cancel_and_future_time_write_nothing(active, monkeypatch):
    db, clock, ops, p = active
    factory = cli.create_runtime

    def runtime(**kwargs):
        result = factory(**kwargs)
        result.operations = PredictionOperations(result.database, clock, UTC)
        return result

    monkeypatch.setattr(cli, "create_runtime", runtime)
    for prompts, status in (
        ("10\n", 130),
        ("10\nnow\n\n\nn\n", 130),
        ("10\n2099-01-01T00:00:00Z\n\n\ny\n", 1),
    ):
        assert (
            cli.run(
                ["resolve", str(p.prediction_id)],
                database_path=db.path,
                stdin=StringIO(prompts),
                stdout=StringIO(),
                stderr=StringIO(),
            )
            == status
        )
        assert ops.get_numeric_prediction(p.prediction_id).resolution is None


@pytest.mark.parametrize("width", [500, 1300])
def test_scorecard_wraps_at_narrow_and_wide_sizes(
    qtbot, active, tmp_path, width, dark_desktop
):
    _, _, ops, p = active
    resolved = ops.resolve_numeric_prediction(
        p.prediction_id, 30, use_recorded_time=True, **context(p)
    )
    screen = NumericPredictionDetailScreen(ops)
    qtbot.addWidget(screen)
    install_visual_system(screen)
    screen.resize(width, 900)
    screen.show_prediction(resolved)
    screen.show()
    screen.quantile_scorecard.findChild(QGroupBox).setChecked(True)
    qtbot.wait(30)
    screen.scroll_area.ensureWidgetVisible(screen.quantile_scorecard)
    qtbot.wait(20)
    assert screen.quantile_scorecard.width() <= screen.width()
    assert screen.scroll_area.horizontalScrollBar().maximum() == 0
    for label in screen.quantile_scorecard.findChildren(QLabel):
        if label.isVisible():
            assert label.width() <= screen.quantile_scorecard.width()
    assert screen.grab().save(str(tmp_path / f"numeric-wis-{width}.png"))


@pytest.fixture
def dark_desktop(qapp):
    original_font, original_palette = qapp.font(), qapp.palette()
    palette = QPalette(original_palette)
    for role, color in (
        (QPalette.ColorRole.Window, "#202020"),
        (QPalette.ColorRole.Base, "#202020"),
        (QPalette.ColorRole.AlternateBase, "#303030"),
        (QPalette.ColorRole.WindowText, "#ffffff"),
        (QPalette.ColorRole.Text, "#ffffff"),
        (QPalette.ColorRole.ButtonText, "#ffffff"),
        (QPalette.ColorRole.Mid, "#707070"),
    ):
        palette.setColor(role, QColor(color))
    qapp.setFont(QFont("Segoe UI", 9))
    qapp.setPalette(palette)
    try:
        yield
    finally:
        qapp.setFont(original_font)
        qapp.setPalette(original_palette)


@pytest.mark.parametrize("width", [500, 600])
def test_numeric_correction_reserves_wrapped_time_form_height(
    qtbot, active, dark_desktop, width
):
    _, _, ops, prediction = active
    prediction = ops.resolve_numeric_prediction(
        prediction.prediction_id, 10, use_recorded_time=True, **context(prediction)
    )
    history = ops.get_numeric_resolution_history(prediction.prediction_id)
    dialog = CorrectNumericResolutionDialog(ops, prediction, history)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    qtbot.addWidget(dialog)
    install_visual_system(dialog)
    dialog.resize(width, 620)
    dialog.show()
    qtbot.wait(30)
    for actual in ("10", "12", "10", "invalid"):
        dialog.actual_value_input.setText(actual)
        if actual == "12":
            dialog.submit()
            assert dialog.form_error.isVisible()
        qtbot.wait(30)
        layout = dialog.layout()
        required = max(
            layout.minimumSize().height(),
            layout.minimumHeightForWidth(dialog.width()),
        )
        assert dialog.minimumHeight() >= required
        assert dialog.height() >= required
        assert dialog.buttons.geometry().bottom() < dialog.height()
    dialog.reject()
    assert ops.get_numeric_resolution_history(prediction.prediction_id) == history
