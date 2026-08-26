from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
)

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome
from reckonsolve.ui.main_window import MainWindow


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


CREATED = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)
RESOLVED = CREATED + timedelta(days=1)
CORRECTED = RESOLVED + timedelta(days=1)
REFLECTED = CORRECTED + timedelta(days=1)


@pytest.fixture
def database(tmp_path):
    opened = Database.open(tmp_path / "reckonsolve.sqlite3")
    yield opened
    opened.close()


def test_binary_correction_and_later_postmortem_survive_restart(
    qtbot,
    database,
    monkeypatch,
) -> None:
    created = PredictionOperations(
        database, FixedClock(CREATED), UTC
    ).create_prediction(
        "Will the launch succeed?",
        80,
    )
    resolved = PredictionOperations(
        database,
        FixedClock(RESOLVED),
        UTC,
    ).resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Preliminary report",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    assert resolved.resolution is not None
    scoring_revision_id = resolved.resolution.scoring_revision_id

    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    correction_button = _child(window, QPushButton, "correctResolutionButton")
    assert correction_button.isEnabled()
    qtbot.mouseClick(correction_button, Qt.MouseButton.LeftButton)
    dialog = _visible_dialog(window, "correctBinaryResolutionDialog")

    save = _child(dialog, QPushButton, "saveBinaryResolutionCorrectionButton")
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert (
        "Change the outcome"
        in _child(
            dialog,
            QLabel,
            "correctBinaryResolutionError",
        ).text()
    )
    assert (
        operations.get_binary_resolution_history(created.prediction_id).corrections
        == ()
    )

    _child(dialog, QRadioButton, "correctResolutionOutcomeNo").setChecked(True)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert (
        "Explain why"
        in _child(
            dialog,
            QLabel,
            "correctBinaryResolutionError",
        ).text()
    )

    _child(dialog, QLineEdit, "binaryOutcomeCorrectionReasonInput").setText(
        "I read a preliminary status as final."
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Cancel,
    )
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    assert dialog.isVisible()
    assert (
        operations.get_binary_resolution_history(created.prediction_id).corrections
        == ()
    )

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: not dialog.isVisible())

    assert "No" in _child(window, QLabel, "predictionResolutionOutcome").text()
    first_history = operations.get_binary_resolution_history(created.prediction_id)
    assert first_history.original.outcome is BinaryOutcome.YES
    assert first_history.effective.outcome is BinaryOutcome.NO
    assert first_history.original.scoring_revision_id == scoring_revision_id
    assert first_history.corrections[0].correction_reason == (
        "I read a preliminary status as final."
    )
    assert operations.get_analytics().mean_brier == pytest.approx(0.64)

    reflection_operations = PredictionOperations(database, FixedClock(REFLECTED), UTC)
    reflection_window = MainWindow(reflection_operations)
    qtbot.addWidget(reflection_window)
    reflection_window.show()
    reflection_window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _child(reflection_window, QPushButton, "correctResolutionButton"),
        Qt.MouseButton.LeftButton,
    )
    reflection_dialog = _visible_dialog(
        reflection_window,
        "correctBinaryResolutionDialog",
    )
    _child(
        reflection_dialog,
        QPlainTextEdit,
        "correctResolutionPostmortemInput",
    ).setPlainText("I should have waited for the final report.")
    qtbot.mouseClick(
        _child(
            reflection_dialog,
            QPushButton,
            "saveBinaryResolutionCorrectionButton",
        ),
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(lambda: not reflection_dialog.isVisible())
    assert _child(reflection_window, QLabel, "predictionPostmortem").text() == (
        "I should have waited for the final report."
    )

    history_group = _child(
        reflection_window,
        QGroupBox,
        "resolutionCorrectionHistory",
    )
    assert not history_group.isHidden()
    assert "2 corrections" in history_group.title()
    history_group.setChecked(True)
    assert (
        _child(
            history_group,
            QLabel,
            "resolutionCorrection1Outcome",
        )
        .text()
        .endswith("Yes → No")
    )
    assert (
        "preliminary status"
        in _child(
            history_group,
            QLabel,
            "resolutionCorrection1Reason",
        ).text()
    )

    reflection_window.close()
    window.close()
    database.close()
    reopened = Database.open(database.path)
    try:
        recovered_operations = PredictionOperations(
            reopened, FixedClock(REFLECTED), UTC
        )
        recovered = recovered_operations.get_binary_resolution_history(
            created.prediction_id
        )
        assert recovered.original.outcome is BinaryOutcome.YES
        assert recovered.effective.outcome is BinaryOutcome.NO
        assert recovered.effective.postmortem == (
            "I should have waited for the final report."
        )
        assert recovered.original.scoring_revision_id == scoring_revision_id
    finally:
        reopened.close()


def test_numeric_actual_correction_is_exact_and_score_affecting(
    qtbot,
    database,
    monkeypatch,
) -> None:
    created = PredictionOperations(
        database, FixedClock(CREATED), UTC
    ).create_numeric_prediction(
        "How many hours will this take?",
        "hours",
        2,
        "1.00",
        "2.00",
        "3.00",
        80,
    )
    PredictionOperations(
        database, FixedClock(RESOLVED), UTC
    ).resolve_numeric_prediction(
        created.prediction_id,
        "2.00",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    qtbot.mouseClick(
        _child(window, QPushButton, "correctNumericResolutionButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _visible_dialog(window, "correctNumericResolutionDialog")
    _child(dialog, QLineEdit, "correctNumericActualValueInput").setText("4.25")
    _child(dialog, QLineEdit, "numericOutcomeCorrectionReasonInput").setText(
        "The final report used a corrected duration."
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(
        _child(dialog, QPushButton, "saveNumericResolutionCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )
    error = _child(dialog, QLabel, "correctNumericResolutionError")
    assert error.isHidden(), error.text()
    qtbot.waitUntil(lambda: not dialog.isVisible())

    assert _child(window, QLabel, "numericResolutionActualValue").text() == (
        "Actual value: 4.25 hours"
    )
    history = operations.get_numeric_resolution_history(created.prediction_id)
    assert str(history.original.actual_value) == "2.00"
    assert str(history.effective.actual_value) == "4.25"
    assert history.corrections[0].changed_fields == ("actual_value",)
    assert operations.get_forecast_analytics().numeric.scored_prediction_count == 1


def test_numeric_invalid_reason_can_be_corrected_and_cleared(
    qtbot,
    database,
    monkeypatch,
) -> None:
    created = PredictionOperations(
        database, FixedClock(CREATED), UTC
    ).create_numeric_prediction(
        "How many units?",
        "units",
        0,
        1,
        2,
        3,
        80,
    )
    PredictionOperations(
        database, FixedClock(RESOLVED), UTC
    ).invalidate_numeric_prediction(
        created.prediction_id,
        reason="Wrong reson",
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )

    qtbot.mouseClick(
        _child(window, QPushButton, "correctNumericInvalidationReasonButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _visible_dialog(window, "correctInvalidationReasonDialog")
    reason = _child(dialog, QPlainTextEdit, "correctInvalidationReasonInput")
    reason.setPlainText("The quantity became unresolvable.")
    qtbot.mouseClick(
        _child(dialog, QPushButton, "saveInvalidationReasonCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )
    qtbot.waitUntil(lambda: not dialog.isVisible())
    assert _child(window, QLabel, "numericInvalidationReason").text() == (
        "Reason: The quantity became unresolvable."
    )

    later = PredictionOperations(database, FixedClock(REFLECTED), UTC)
    history = later.correct_invalidation_reason(
        created.prediction_id,
        None,
        expected_correction_id=operations.get_invalidation_history(
            created.prediction_id
        ).current_correction_id,
    )
    assert history.original.reason == "Wrong reson"
    assert history.effective.reason is None
    assert len(history.corrections) == 2


def test_stale_resolution_dialog_keeps_competing_history_and_appends_nothing(
    qtbot,
    database,
    monkeypatch,
) -> None:
    created = PredictionOperations(
        database, FixedClock(CREATED), UTC
    ).create_prediction(
        "Will the source be corrected?",
        60,
    )
    PredictionOperations(database, FixedClock(RESOLVED), UTC).resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Original source",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    first = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    window = MainWindow(first)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _child(window, QPushButton, "correctResolutionButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _visible_dialog(window, "correctBinaryResolutionDialog")
    _child(dialog, QPlainTextEdit, "correctResolutionNotesInput").setPlainText(
        "Stale proposed source"
    )

    competing = PredictionOperations(database, FixedClock(REFLECTED), UTC)
    competing.correct_binary_resolution(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="Competing source",
        postmortem=None,
        expected_correction_id=None,
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(
        _child(dialog, QPushButton, "saveBinaryResolutionCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert (
        "changed before"
        in _child(
            dialog,
            QLabel,
            "correctBinaryResolutionError",
        ).text()
    )
    history = first.get_binary_resolution_history(created.prediction_id)
    assert len(history.corrections) == 1
    assert history.effective.resolution_notes == "Competing source"


def _visible_dialog(parent, object_name: str) -> QDialog:
    dialogs = parent.findChildren(QDialog, object_name)
    dialog = next(item for item in reversed(dialogs) if item.isVisible())
    return dialog


def _child(parent, widget_type, object_name: str):
    child = parent.findChild(widget_type, object_name)
    assert child is not None
    return child
