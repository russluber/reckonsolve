from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPlainTextEdit, QPushButton, QWidget

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.numeric_history_chart import NumericHistoryChart
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)


def test_binary_review_dialog_cancel_save_timeline_and_chart(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    prediction = operations.create_prediction("Will this forecast hold?", 60)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    action = window.findChild(QPushButton, "reviewForecastButton")
    assert action is not None
    assert action.text() == "Still at 60%"
    qtbot.mouseClick(action, Qt.MouseButton.LeftButton)
    dialog = window.findChild(QDialog, "forecastReviewDialog")
    assert dialog is not None
    qtbot.waitUntil(dialog.isVisible)
    cancel = dialog.findChild(QPushButton, "cancelButton")
    if cancel is None:
        cancel = dialog.findChildren(QPushButton)[-1]
    qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)
    assert len(operations.list_timeline(prediction.prediction_id)) == 1

    qtbot.mouseClick(action, Qt.MouseButton.LeftButton)
    dialogs = window.findChildren(QDialog, "forecastReviewDialog")
    dialog = next(item for item in reversed(dialogs) if item.isVisible())
    note = dialog.findChild(QPlainTextEdit, "forecastReviewNoteInput")
    save = dialog.findChild(QPushButton, "saveForecastReviewButton")
    assert note is not None
    assert save is not None
    note.setPlainText("No new evidence changes my estimate.")
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)

    review = window.findChild(QLabel, "forecastReviewHeading1")
    chart = window.findChild(ProbabilityHistoryChart, "probabilityHistoryChart")
    assert review is not None
    assert review.text() == "REVIEW  STILL AT 60%"
    assert chart is not None
    assert len(chart.samples) == 1
    delete = window.findChild(QPushButton, "deletePredictionButton")
    assert delete is not None
    assert not delete.isEnabled()
    database.close()


def test_numeric_review_uses_interval_context_and_locked_disables_action(
    qtbot,
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created_operations = PredictionOperations(database, FixedClock(NOW), UTC)
    prediction = created_operations.create_numeric_prediction(
        "How many days?",
        "days",
        0,
        2,
        4,
        8,
        80,
        forecast_deadline=date(2026, 8, 20),
    )
    operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        UTC,
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    action = window.findChild(QPushButton, "reviewNumericForecastButton")
    chart = window.findChild(NumericHistoryChart)
    assert action is not None
    assert action.text() == "Keep this interval"
    assert not action.isEnabled()
    assert chart is not None
    assert len(chart.samples) == 1
    assert len(operations.list_numeric_timeline(prediction.prediction_id)) == 1
    database.close()


def test_numeric_review_saves_without_note_and_does_not_add_chart_point(
    qtbot,
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    prediction = operations.create_numeric_prediction(
        "How many days?", "days", 0, 2, 4, 8, 80
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    action = window.findChild(QPushButton, "reviewNumericForecastButton")
    assert action is not None
    qtbot.mouseClick(action, Qt.MouseButton.LeftButton)
    dialog = window.findChild(QDialog, "forecastReviewDialog")
    assert dialog is not None
    qtbot.waitUntil(dialog.isVisible)
    context = dialog.findChild(QLabel, "forecastReviewContext")
    save = dialog.findChild(QPushButton, "saveForecastReviewButton")
    assert context is not None
    assert "80% interval" in context.text()
    assert save is not None
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)

    assert window.findChild(QLabel, "numericReviewNote1") is None
    assert window.findChild(QWidget, "numericTimelineReview1") is not None
    chart = window.findChild(NumericHistoryChart)
    assert chart is not None
    assert len(chart.samples) == 1
    assert len(operations.list_numeric_timeline(prediction.prediction_id)) == 2
    database.close()
