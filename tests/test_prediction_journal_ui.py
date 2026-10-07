"""Journal creation, correction, and causal Timeline presentation."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from main_window_fakes import (
    AddJournalEntryCall,
    CorrectJournalEntryCall,
    FakeForecastRevision,
    FakeJournalCorrection,
    FakeJournalTimelineEvent,
    FakePrediction,
    FakePredictionOperations,
)
from main_window_helpers import (
    _click_correction_button,
    _open_correction_dialog,
    _open_journal_dialog,
    _required_child,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.predictions import (
    PredictionStatus,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart


def test_add_journal_entry_refreshes_context_and_cancel_has_no_effect(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(
        7,
        "Will a cancelled Journal form leave history alone?",
        60,
        metadata_version=1,
        current_revision_id=11,
        current_revision_sequence=1,
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        probability_percent=70,
        metadata_version=2,
        current_revision_id=12,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            revision_id=12,
            prediction_id=7,
            probability_percent=70,
            sequence=2,
            created_at=datetime(2026, 8, 13, tzinfo=UTC),
        )
    )

    dialog = _open_journal_dialog(qtbot, window)
    assert _required_child(dialog, QLabel, "journalForecastAtTime").text() == "70%"
    assert dialog.focusWidget() is _required_child(
        dialog,
        QPlainTextEdit,
        "journalEntryBodyInput",
    )
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.journal_calls == []
    assert operations.journal_entries == []


def test_blank_journal_entry_stays_inline_without_calling_operation(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will blank Journal entries be rejected?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")
    body.setPlainText("  \n ")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    error = _required_child(dialog, QLabel, "addJournalEntryError")
    assert "Write a journal entry" in error.text()
    assert not error.isHidden()
    assert operations.journal_calls == []


def test_journal_expected_error_keeps_multiline_body_and_dialog_open(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will stale Journal context be rejected?", 60)
    )
    operations.journal_error = ApplicationError(
        "This prediction changed before the Journal entry could be saved."
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")
    body.setPlainText("First line\nSecond line")

    qtbot.keyPress(body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert dialog.isVisible()
    assert body.toPlainText() == "First line\nSecond line"
    error = _required_child(dialog, QLabel, "addJournalEntryError")
    assert "changed before" in error.text()
    assert not error.isHidden()
    assert len(operations.journal_calls) == 1


def test_enter_adds_newline_and_ctrl_enter_saves_journal_with_tokens(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will keyboard entry remain comfortable?",
        65,
        metadata_version=4,
        current_revision_id=11,
        current_revision_sequence=3,
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    original_samples = chart.samples
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")

    qtbot.keyClicks(body, "Evidence one")
    qtbot.keyPress(body, Qt.Key.Key_Return)
    qtbot.keyClicks(body, "Evidence two")
    assert body.toPlainText() == "Evidence one\nEvidence two"
    qtbot.keyPress(body, Qt.Key.Key_Tab)
    assert dialog.focusWidget() is _required_child(
        dialog,
        QPushButton,
        "saveJournalEntryButton",
    )
    body.setFocus()
    qtbot.keyPress(body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert operations.journal_calls == [
        AddJournalEntryCall(
            prediction_id=7,
            body="Evidence one\nEvidence two",
            expected_revision_id=11,
            expected_metadata_version=4,
        )
    ]
    assert not dialog.isVisible()
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "65%"
    )
    assert (
        _required_child(window, QLabel, "journalEntryBody1").text()
        == "Evidence one\nEvidence two"
    )
    assert (
        _required_child(window, QLabel, "journalEntryForecastAtTime1").text()
        == "Forecast at the time: 65%"
    )
    assert chart.revision_count == 1
    assert chart.samples == original_samples


@pytest.mark.parametrize("status", [PredictionStatus.OPEN, PredictionStatus.LOCKED])
def test_journal_creation_is_enabled_for_nonterminal_statuses(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    window = MainWindow(
        FakePredictionOperations(
            FakePrediction(7, "Can this accept a Journal entry?", 60, status=status)
        )
    )
    qtbot.addWidget(window)

    assert _required_child(window, QPushButton, "addJournalEntryButton").isEnabled()


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.RESOLVED, PredictionStatus.INVALID],
)
def test_terminal_predictions_disable_new_journals_but_allow_corrections(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Can terminal history be corrected?", 60, status=status)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Original Journal text",
            original_body="Original Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    add_button = _required_child(window, QPushButton, "addJournalEntryButton")
    assert not add_button.isEnabled()
    correct_button = _required_child(
        window,
        QPushButton,
        "correctJournalEntryButton4",
    )
    assert correct_button.isEnabled()


def test_unified_timeline_renders_forecasts_and_journals_as_plain_text(
    qtbot: QtBot,
) -> None:
    markup = "<b>Literal Journal evidence</b>"
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the timeline be historically honest?", 40)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=8,
            prediction_id=7,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
            body=markup,
            original_body=markup,
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=40,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "timelineHeading").text() == "TIMELINE"
    body = _required_child(window, QLabel, "journalEntryBody8")
    assert body.text() == markup
    assert body.textFormat() is Qt.TextFormat.PlainText
    timestamp = _required_child(window, QLabel, "journalEntryTimestamp8")
    assert timestamp.text() == (
        datetime(2026, 8, 13, 19, 30, tzinfo=UTC)
        .astimezone()
        .strftime("%b %d, %Y at %H:%M")
        .strip()
    )


def test_correction_cancel_and_expected_error_preserve_current_body(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will correction failures remain safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Latest text",
            original_body="Original text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
            current_correction_id=3,
            corrections=(
                FakeJournalCorrection(
                    3,
                    "Latest text",
                    datetime(2026, 8, 13, tzinfo=UTC),
                ),
            ),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    original_samples = chart.samples
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    assert body.toPlainText() == "Latest text"
    qtbot.keyPress(dialog, Qt.Key.Key_Escape)
    assert operations.correction_calls == []

    operations.correction_error = ApplicationError(
        "This Journal entry changed before the correction could be saved."
    )
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    body.setPlainText("Corrected text")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )
    assert dialog.isVisible()
    assert body.toPlainText() == "Corrected text"
    assert (
        "changed before"
        in _required_child(
            dialog,
            QLabel,
            "correctJournalEntryError",
        ).text()
    )
    assert chart.revision_count == 1
    assert chart.samples == original_samples


def test_correction_dialog_refreshes_external_edits_and_recovers_after_stale_save(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will correction retries use the latest text?", 60)
    )
    original = FakeJournalTimelineEvent(
        entry_id=4,
        prediction_id=7,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
        body="Original text",
        original_body="Original text",
        forecast_revision_id=1,
        forecast_revision_sequence=1,
        forecast_probability_percent=60,
    )
    operations.journal_entries = [original]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    first_external_correction = FakeJournalCorrection(
        1,
        "First external correction",
        datetime(2026, 8, 13, tzinfo=UTC),
    )
    operations.journal_entries[0] = replace(
        original,
        body=first_external_correction.body,
        current_correction_id=first_external_correction.correction_id,
        corrections=(first_external_correction,),
    )

    dialog = _click_correction_button(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    assert body.toPlainText() == "First external correction"

    second_external_correction = FakeJournalCorrection(
        2,
        "Second external correction",
        datetime(2026, 8, 14, tzinfo=UTC),
    )
    operations.journal_entries[0] = replace(
        operations.journal_entries[0],
        body=second_external_correction.body,
        current_correction_id=second_external_correction.correction_id,
        corrections=(first_external_correction, second_external_correction),
    )
    operations.correction_error = ApplicationError(
        "This Journal entry changed before the correction could be saved."
    )
    body.setPlainText("Correction from the stale dialog")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert operations.correction_calls[-1].expected_correction_id == 1
    qtbot.keyPress(dialog, Qt.Key.Key_Escape)
    operations.correction_error = None

    retry_dialog = _click_correction_button(qtbot, window, entry_id=4)
    retry_body = _required_child(
        retry_dialog,
        QPlainTextEdit,
        "correctJournalEntryBodyInput",
    )
    assert retry_body.toPlainText() == "Second external correction"
    retry_body.setPlainText("Recovered correction")
    qtbot.mouseClick(
        _required_child(retry_dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.correction_calls[-1] == CorrectJournalEntryCall(
        prediction_id=7,
        entry_id=4,
        body="Recovered correction",
        expected_correction_id=2,
    )


def test_correction_refresh_error_is_visible_and_does_not_open_dialog(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a failed refresh stay safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Journal text",
            original_body="Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    operations.timeline_error = ApplicationError("The timeline is temporarily busy.")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "correctJournalEntryButton4"),
        Qt.MouseButton.LeftButton,
    )

    assert not any(
        dialog.isVisible()
        for dialog in window.findChildren(QDialog, "correctJournalEntryDialog")
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be refreshed" in error.text()
    assert "temporarily busy" in error.text()
    assert not error.isHidden()


def test_missing_journal_during_correction_refresh_is_reported_safely(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a missing entry stay safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Journal text",
            original_body="Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    operations.journal_entries.clear()

    qtbot.mouseClick(
        _required_child(window, QPushButton, "correctJournalEntryButton4"),
        Qt.MouseButton.LeftButton,
    )

    assert not any(
        dialog.isVisible()
        for dialog in window.findChildren(QDialog, "correctJournalEntryDialog")
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be found" in error.text()
    assert not error.isHidden()


def test_correction_displays_edited_marker_and_collapsed_plain_text_history(
    qtbot: QtBot,
) -> None:
    original_time = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations(
        FakePrediction(7, "Will corrections retain every prior body?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=original_time,
            body="First corrected body",
            original_body="<b>Original body</b>",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
            current_correction_id=1,
            corrections=(
                FakeJournalCorrection(
                    correction_id=1,
                    body="First corrected body",
                    corrected_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
                ),
            ),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    body.setPlainText("<i>Corrected body</i>")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.correction_calls == [
        CorrectJournalEntryCall(
            prediction_id=7,
            entry_id=4,
            body="<i>Corrected body</i>",
            expected_correction_id=1,
        )
    ]
    assert (
        _required_child(
            window,
            QLabel,
            "journalEntryEdited4",
        )
        .text()
        .startswith("Edited ")
    )
    assert (
        _required_child(window, QLabel, "journalEntryBody4").text()
        == "<i>Corrected body</i>"
    )
    history = _required_child(window, QGroupBox, "journalEntryEditHistory4")
    content = _required_child(window, QWidget, "journalEntryEditHistoryContent4")
    assert not history.isChecked()
    assert content.isHidden()
    history.setChecked(True)
    assert not content.isHidden()
    original = _required_child(window, QLabel, "journalEntryOriginalBody4")
    correction = _required_child(window, QLabel, "journalCorrectionBody1")
    assert original.text() == "<b>Original body</b>"
    assert correction.text() == "First corrected body"
    assert original.textFormat() is Qt.TextFormat.PlainText
    assert correction.textFormat() is Qt.TextFormat.PlainText
    assert chart.revision_count == 1
    assert (
        _required_child(window, QLabel, "journalCorrectionHeading1")
        .text()
        .startswith("Correction 1 ·")
    )
