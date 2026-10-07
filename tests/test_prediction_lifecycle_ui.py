"""Resolution, invalidation, and guarded deletion workflows."""

from __future__ import annotations

from datetime import UTC, datetime

from main_window_fakes import (
    DeletePredictionCall,
    FakePrediction,
    FakePredictionOperations,
    FakeResolution,
    InvalidatePredictionCall,
    ResolvePredictionCall,
)
from main_window_helpers import (
    _open_invalidation_dialog,
    _open_resolution_dialog,
    _required_child,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    PredictionStatus,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    ActionRole,
)


def test_resolve_dialog_is_side_effect_free_until_an_outcome_is_saved(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Will it resolve?", 35))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)

    explanation = _required_child(dialog, QLabel, "resolvePredictionExplanation")
    save = _required_child(dialog, QPushButton, "confirmResolvePredictionButton")
    assert "Resolution is final" in explanation.text()
    assert explanation.textFormat() is Qt.TextFormat.PlainText
    assert not save.isEnabled()
    assert operations.resolve_calls == []

    dialog.reject()
    assert operations.resolve_calls == []


def test_resolve_yes_saves_reviewed_context_and_renders_terminal_facts(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        7,
        "Will it resolve?",
        35,
        current_revision_id=9,
        current_revision_sequence=3,
        metadata_version=4,
        deletion_allowed=False,
    )
    operations = FakePredictionOperations(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)
    _required_child(dialog, QRadioButton, "resolutionOutcomeYes").setChecked(True)
    _required_child(dialog, QPlainTextEdit, "resolutionNotesInput").setPlainText(
        "Certified result"
    )
    _required_child(dialog, QPlainTextEdit, "resolutionPostmortemInput").setPlainText(
        "I updated too slowly."
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmResolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.resolve_calls == [
        ResolvePredictionCall(
            prediction_id=7,
            outcome=BinaryOutcome.YES,
            resolution_notes="Certified result",
            postmortem="I updated too slowly.",
            expected_revision_id=9,
            expected_metadata_version=4,
        )
    ]
    assert (
        _required_child(window, QLabel, "predictionDetailStatus").text() == "RESOLVED"
    )
    section = _required_child(window, QGroupBox, "predictionResolutionSection")
    assert not section.isHidden()
    assert (
        "Yes"
        in _required_child(
            section,
            QLabel,
            "predictionResolutionOutcome",
        ).text()
    )
    assert (
        "35%"
        in _required_child(
            section,
            QLabel,
            "predictionResolutionScoringForecast",
        ).text()
    )
    assert (
        _required_child(
            section,
            QLabel,
            "predictionResolutionNotes",
        ).text()
        == "Certified result"
    )
    assert (
        _required_child(
            section,
            QLabel,
            "predictionPostmortem",
        ).text()
        == "I updated too slowly."
    )
    for object_name in (
        "reviseForecastButton",
        "addJournalEntryButton",
        "resolvePredictionButton",
        "markInvalidButton",
        "deletePredictionButton",
    ):
        assert not _required_child(window, QPushButton, object_name).isEnabled()


def test_resolve_expected_error_keeps_dialog_and_inputs_for_retry(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Will it resolve?", 35))
    operations.resolve_error = ApplicationError("The prediction changed.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)
    _required_child(dialog, QRadioButton, "resolutionOutcomeNo").setChecked(True)
    notes = _required_child(dialog, QPlainTextEdit, "resolutionNotesInput")
    notes.setPlainText("Keep this source")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmResolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert notes.toPlainText() == "Keep this source"
    error = _required_child(dialog, QLabel, "resolvePredictionError")
    assert "changed" in error.text()
    assert not error.isHidden()


def test_mark_invalid_saves_optional_reason_and_renders_preserved_state(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        7,
        "Was this cancelled?",
        55,
        current_revision_id=4,
        metadata_version=2,
        deletion_allowed=False,
    )
    operations = FakePredictionOperations(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_invalidation_dialog(qtbot, window)
    assert (
        _required_child(dialog, QPushButton, "confirmMarkInvalidButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.CAUTION.value
    )
    explanation = _required_child(dialog, QLabel, "markInvalidExplanation")
    assert "excludes it from scoring" in explanation.text()
    reason = _required_child(dialog, QPlainTextEdit, "invalidationReasonInput")
    reason.setPlainText("The event was cancelled.")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmMarkInvalidButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.invalidate_calls == [
        InvalidatePredictionCall(
            prediction_id=7,
            reason="The event was cancelled.",
            expected_revision_id=4,
            expected_metadata_version=2,
        )
    ]
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "INVALID"
    section = _required_child(window, QGroupBox, "predictionInvalidationSection")
    assert not section.isHidden()
    assert (
        _required_child(
            section,
            QLabel,
            "predictionInvalidationReason",
        ).text()
        == "The event was cancelled."
    )
    assert not _required_child(
        window, QPushButton, "deletePredictionButton"
    ).isEnabled()


def test_mark_invalid_cancel_writes_nothing(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Keep this Open?", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_invalidation_dialog(qtbot, window)
    _required_child(dialog, QPlainTextEdit, "invalidationReasonInput").setPlainText(
        "Do not save this"
    )

    dialog.reject()

    assert operations.invalidate_calls == []
    assert operations.latest is not None
    assert operations.latest.status is PredictionStatus.OPEN


def test_locked_prediction_can_resolve_or_invalidate_but_not_revise_or_delete(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Locked question?",
            55,
            status=PredictionStatus.LOCKED,
            deletion_allowed=False,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QPushButton, "resolvePredictionButton").isEnabled()
    assert _required_child(window, QPushButton, "markInvalidButton").isEnabled()
    assert _required_child(window, QPushButton, "addJournalEntryButton").isEnabled()
    assert not _required_child(window, QPushButton, "reviseForecastButton").isEnabled()
    delete = _required_child(window, QPushButton, "deletePredictionButton")
    assert not delete.isEnabled()
    assert "Mark Invalid" in delete.toolTip()


def test_terminal_user_text_is_rendered_as_plain_text(qtbot: QtBot) -> None:
    resolution = FakeResolution(
        resolution_id=1,
        prediction_id=7,
        outcome=BinaryOutcome.NO,
        resolved_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        scoring_revision_id=1,
        scoring_revision_sequence=1,
        scoring_probability_percent=60,
        resolution_notes="<b>literal source</b>",
        postmortem="<i>literal reflection</i>",
    )
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Question?",
            60,
            status=PredictionStatus.RESOLVED,
            resolution=resolution,
            deletion_allowed=False,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name, expected in (
        ("predictionResolutionNotes", "<b>literal source</b>"),
        ("predictionPostmortem", "<i>literal reflection</i>"),
    ):
        label = _required_child(window, QLabel, object_name)
        assert label.textFormat() is Qt.TextFormat.PlainText
        assert label.text() == expected


def test_delete_cancel_is_side_effect_free_and_confirm_clears_detail(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Duplicate?", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    delete = _required_child(window, QPushButton, "deletePredictionButton")

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Cancel,
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert operations.delete_calls == []

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        # PySide may return an equal integral button value rather than the
        # identical Python enum object used in this test process.
        lambda *_args: int(QMessageBox.StandardButton.Yes),
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)

    assert operations.delete_calls == [
        DeletePredictionCall(
            prediction_id=7,
            expected_revision_id=1,
            expected_metadata_version=1,
            confirm_permanent_deletion=True,
        )
    ]
    assert not _required_child(
        window,
        QLabel,
        "predictionDetailEmptyState",
    ).isHidden()


def test_meaningful_open_prediction_disables_delete_and_guides_invalid(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Meaningful?", 55, deletion_allowed=False)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    delete = _required_child(window, QPushButton, "deletePredictionButton")
    assert not delete.isEnabled()
    assert "Mark Invalid" in delete.toolTip()
    assert _required_child(window, QPushButton, "markInvalidButton").isEnabled()
