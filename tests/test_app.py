from typing import cast

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateEdit,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

import reckonsolve.app
from reckonsolve.app import APPLICATION_NAME, ApplicationRuntime, create_runtime
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MigrationError
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart


def test_application_runtime_reopens_same_database(qtbot, tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"

    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    assert first_runtime.window.isVisible()
    assert first_runtime.database.schema_version == 5
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    assert second_runtime.window.windowTitle() == APPLICATION_NAME
    assert second_runtime.database.schema_version == 5
    second_runtime.close()


def test_create_close_reopen_displays_persisted_prediction(qtbot, tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    first_runtime.window.navigate_to("New Prediction")

    question_input = first_runtime.window.findChild(QLineEdit, "questionInput")
    probability_input = first_runtime.window.findChild(QSpinBox, "probabilityInput")
    create_button = first_runtime.window.findChild(
        QPushButton, "createPredictionButton"
    )
    assert question_input is not None
    assert probability_input is not None
    assert create_button is not None
    question_input.setText("Will this prediction survive restart?")
    probability_input.setValue(60)
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert first_runtime.window.current_screen_name == "Prediction Detail"
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.navigate_to("Prediction Detail")
    question = second_runtime.window.findChild(QLabel, "predictionDetailQuestion")
    probability = second_runtime.window.findChild(QLabel, "predictionDetailProbability")
    assert question is not None
    assert probability is not None
    assert question.text() == "Will this prediction survive restart?"
    assert probability.text() == "60%"
    second_runtime.close()


def test_edit_confirm_close_reopen_displays_metadata_and_history(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    first_runtime.window.navigate_to("New Prediction")

    question_input = first_runtime.window.findChild(QLineEdit, "questionInput")
    create_button = first_runtime.window.findChild(
        QPushButton,
        "createPredictionButton",
    )
    assert question_input is not None
    assert create_button is not None
    question_input.setText("Will the M3 workflow persist?")
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    edit_button = first_runtime.window.findChild(
        QPushButton,
        "editPredictionDetailsButton",
    )
    assert edit_button is not None
    qtbot.mouseClick(edit_button, Qt.MouseButton.LeftButton)
    dialog = first_runtime.window.findChild(QDialog, "editPredictionDetailsDialog")
    assert dialog is not None
    qtbot.waitUntil(dialog.isVisible)

    edited_question = dialog.findChild(QLineEdit, "editQuestionInput")
    background = dialog.findChild(QPlainTextEdit, "editBackgroundInput")
    criteria = dialog.findChild(QPlainTextEdit, "editResolutionCriteriaInput")
    deadline_toggle = dialog.findChild(QCheckBox, "editForecastDeadlineToggle")
    deadline = dialog.findChild(QDateEdit, "editForecastDeadlineInput")
    expected_toggle = dialog.findChild(QCheckBox, "editExpectedResolutionToggle")
    expected = dialog.findChild(QDateEdit, "editExpectedResolutionInput")
    tags = dialog.findChild(QLineEdit, "editTagsInput")
    save_button = dialog.findChild(QPushButton, "savePredictionDetailsButton")
    assert all(
        widget is not None
        for widget in (
            edited_question,
            background,
            criteria,
            deadline_toggle,
            deadline,
            expected_toggle,
            expected,
            tags,
            save_button,
        )
    )
    edited_question.setText("Will the M3 workflow persist after restart?")
    background.setPlainText("End-to-end metadata context.")
    criteria.setPlainText("Yes if the same details reopen from SQLite.")
    deadline_toggle.setChecked(True)
    deadline.setDate(QDate(2099, 12, 30))
    expected_toggle.setChecked(True)
    expected.setDate(QDate(2099, 12, 31))
    tags.setText("m3, persistence")
    warning_messages: list[str] = []

    def confirm_definition_change(
        _parent,
        _title,
        message,
        _buttons,
        _default,
    ) -> QMessageBox.StandardButton:
        warning_messages.append(message)
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", confirm_definition_change)
    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)

    assert warning_messages
    assert not dialog.isVisible()
    with first_runtime.database.transaction() as connection:
        history_count = connection.execute(
            "SELECT COUNT(*) FROM prediction_definition_changes"
        ).fetchone()[0]
    assert history_count == 1
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.navigate_to("Prediction Detail")

    question = second_runtime.window.findChild(QLabel, "predictionDetailQuestion")
    reopened_background = second_runtime.window.findChild(
        QLabel,
        "predictionDetailBackground",
    )
    reopened_criteria = second_runtime.window.findChild(
        QLabel,
        "predictionDetailResolutionCriteria",
    )
    reopened_tags = second_runtime.window.findChild(QLabel, "predictionDetailTags")
    reopened_deadline = second_runtime.window.findChild(
        QLabel,
        "predictionDetailForecastDeadline",
    )
    reopened_expected = second_runtime.window.findChild(
        QLabel,
        "predictionDetailExpectedResolution",
    )
    history = second_runtime.window.findChild(QGroupBox, "definitionHistoryGroup")
    assert question is not None
    assert reopened_background is not None
    assert reopened_criteria is not None
    assert reopened_tags is not None
    assert reopened_deadline is not None
    assert reopened_expected is not None
    assert history is not None
    assert question.text() == "Will the M3 workflow persist after restart?"
    assert reopened_background.text() == "End-to-end metadata context."
    assert reopened_criteria.text() == ("Yes if the same details reopen from SQLite.")
    assert reopened_tags.text() == "#m3  #persistence"
    assert "2099" in reopened_deadline.text()
    assert "2099" in reopened_expected.text()
    assert not history.isHidden()
    assert not history.isChecked()
    second_runtime.close()


def test_complete_creation_and_forecast_revision_survive_restart(
    qtbot,
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    first_runtime.window.navigate_to("New Prediction")

    question = first_runtime.window.findChild(QLineEdit, "questionInput")
    probability = first_runtime.window.findChild(QSpinBox, "probabilityInput")
    more_details = first_runtime.window.findChild(
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    rationale = first_runtime.window.findChild(
        QPlainTextEdit,
        "initialRationaleInput",
    )
    background = first_runtime.window.findChild(
        QPlainTextEdit,
        "initialBackgroundInput",
    )
    criteria = first_runtime.window.findChild(
        QPlainTextEdit,
        "initialResolutionCriteriaInput",
    )
    deadline_toggle = first_runtime.window.findChild(
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline = first_runtime.window.findChild(
        QDateEdit,
        "initialForecastDeadlineInput",
    )
    expected_toggle = first_runtime.window.findChild(
        QCheckBox,
        "initialExpectedResolutionToggle",
    )
    expected = first_runtime.window.findChild(
        QDateEdit,
        "initialExpectedResolutionInput",
    )
    tags = first_runtime.window.findChild(QLineEdit, "initialTagsInput")
    create_button = first_runtime.window.findChild(
        QPushButton,
        "createPredictionButton",
    )
    assert all(
        widget is not None
        for widget in (
            question,
            probability,
            more_details,
            rationale,
            background,
            criteria,
            deadline_toggle,
            deadline,
            expected_toggle,
            expected,
            tags,
            create_button,
        )
    )

    question.setText("Will the complete M4 forecast survive restart?")
    probability.setValue(60)
    more_details.setChecked(True)
    rationale.setPlainText("This is the initial evidence.")
    background.setPlainText("A complete creation workflow.")
    criteria.setPlainText("Yes if all values and revisions reopen from SQLite.")
    deadline_toggle.setChecked(True)
    deadline.setDate(QDate(2099, 12, 30))
    expected_toggle.setChecked(True)
    expected.setDate(QDate(2099, 12, 31))
    tags.setText("m4, persistence")
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert first_runtime.window.current_screen_name == "Prediction Detail"
    current_probability = first_runtime.window.findChild(
        QLabel,
        "predictionDetailProbability",
    )
    probability_history = first_runtime.window.findChild(
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    revise_button = first_runtime.window.findChild(
        QPushButton,
        "reviseForecastButton",
    )
    initial_rationale = first_runtime.window.findChild(
        QLabel,
        "forecastRevisionRationale1",
    )
    assert current_probability is not None
    assert probability_history is not None
    assert revise_button is not None
    assert initial_rationale is not None
    assert current_probability.text() == "60%"
    assert probability_history.revision_count == 1
    assert initial_rationale.text() == "This is the initial evidence."

    with first_runtime.database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM prediction_definition_changes"
            ).fetchone()[0]
            == 0
        )

    qtbot.mouseClick(revise_button, Qt.MouseButton.LeftButton)
    revision_dialog = first_runtime.window.findChild(
        QDialog,
        "reviseForecastDialog",
    )
    assert revision_dialog is not None
    qtbot.waitUntil(revision_dialog.isVisible)
    revision_probability = revision_dialog.findChild(
        QSpinBox,
        "revisionProbabilityInput",
    )
    revision_rationale = revision_dialog.findChild(
        QPlainTextEdit,
        "revisionRationaleInput",
    )
    save_revision = revision_dialog.findChild(
        QPushButton,
        "saveForecastRevisionButton",
    )
    assert revision_probability is not None
    assert revision_rationale is not None
    assert save_revision is not None
    revision_probability.setValue(75)
    revision_rationale.setPlainText("New evidence moved the forecast upward.")
    qtbot.mouseClick(save_revision, Qt.MouseButton.LeftButton)

    qtbot.waitUntil(lambda: current_probability.text() == "75%")
    assert probability_history.revision_count == 2
    revised_rationale = first_runtime.window.findChild(
        QLabel,
        "forecastRevisionRationale2",
    )
    assert revised_rationale is not None
    assert revised_rationale.text() == "New evidence moved the forecast upward."
    with first_runtime.database.transaction() as connection:
        revisions = connection.execute(
            """
            SELECT sequence, probability_percent, rationale
            FROM forecast_revisions
            ORDER BY sequence
            """
        ).fetchall()
    assert [tuple(row) for row in revisions] == [
        (1, 60, "This is the initial evidence."),
        (2, 75, "New evidence moved the forecast upward."),
    ]
    expected_chart_samples = probability_history.samples
    assert [sample.probability_percent for sample in expected_chart_samples] == [
        60,
        75,
    ]
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.navigate_to("Prediction Detail")
    reopened_question = second_runtime.window.findChild(
        QLabel,
        "predictionDetailQuestion",
    )
    reopened_probability = second_runtime.window.findChild(
        QLabel,
        "predictionDetailProbability",
    )
    reopened_probability_history = second_runtime.window.findChild(
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    reopened_initial_rationale = second_runtime.window.findChild(
        QLabel,
        "forecastRevisionRationale1",
    )
    reopened_revised_rationale = second_runtime.window.findChild(
        QLabel,
        "forecastRevisionRationale2",
    )
    assert reopened_question is not None
    assert reopened_probability is not None
    assert reopened_probability_history is not None
    assert reopened_initial_rationale is not None
    assert reopened_revised_rationale is not None
    assert reopened_question.text() == "Will the complete M4 forecast survive restart?"
    assert reopened_probability.text() == "75%"
    assert reopened_probability_history.revision_count == 2
    assert reopened_probability_history.samples == expected_chart_samples
    assert reopened_initial_rationale.text() == "This is the initial evidence."
    assert (
        reopened_revised_rationale.text() == "New evidence moved the forecast upward."
    )
    second_runtime.close()


def test_journal_correction_timeline_and_forecast_context_survive_restart(
    qtbot,
    tmp_path,
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    first_runtime.window.navigate_to("New Prediction")

    question = first_runtime.window.findChild(QLineEdit, "questionInput")
    probability = first_runtime.window.findChild(QSpinBox, "probabilityInput")
    create_button = first_runtime.window.findChild(
        QPushButton,
        "createPredictionButton",
    )
    assert question is not None
    assert probability is not None
    assert create_button is not None
    question.setText("Will the M5 Journal remain historically honest?")
    probability.setValue(60)
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    add_journal = first_runtime.window.findChild(
        QPushButton,
        "addJournalEntryButton",
    )
    current_probability = first_runtime.window.findChild(
        QLabel,
        "predictionDetailProbability",
    )
    probability_history = first_runtime.window.findChild(
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert add_journal is not None
    assert current_probability is not None
    assert probability_history is not None
    assert probability_history.revision_count == 1
    qtbot.mouseClick(add_journal, Qt.MouseButton.LeftButton)
    journal_dialog = first_runtime.window.findChild(
        QDialog,
        "addJournalEntryDialog",
    )
    assert journal_dialog is not None
    qtbot.waitUntil(journal_dialog.isVisible)
    journal_body = journal_dialog.findChild(
        QPlainTextEdit,
        "journalEntryBodyInput",
    )
    save_journal = journal_dialog.findChild(
        QPushButton,
        "saveJournalEntryButton",
    )
    assert journal_body is not None
    assert save_journal is not None
    journal_body.setPlainText("The evidence teh supports 60%.")
    qtbot.mouseClick(save_journal, Qt.MouseButton.LeftButton)

    assert current_probability.text() == "60%"
    assert probability_history.revision_count == 1
    journal_context = first_runtime.window.findChild(
        QLabel,
        "journalEntryForecastAtTime1",
    )
    correct_journal = first_runtime.window.findChild(
        QPushButton,
        "correctJournalEntryButton1",
    )
    assert journal_context is not None
    assert correct_journal is not None
    assert journal_context.text() == "Forecast at the time: 60%"
    with first_runtime.database.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM forecast_revisions").fetchone()[0]
            == 1
        )

    qtbot.mouseClick(correct_journal, Qt.MouseButton.LeftButton)
    correction_dialog = first_runtime.window.findChild(
        QDialog,
        "correctJournalEntryDialog",
    )
    assert correction_dialog is not None
    qtbot.waitUntil(correction_dialog.isVisible)
    corrected_body = correction_dialog.findChild(
        QPlainTextEdit,
        "correctJournalEntryBodyInput",
    )
    save_correction = correction_dialog.findChild(
        QPushButton,
        "saveJournalCorrectionButton",
    )
    assert corrected_body is not None
    assert save_correction is not None
    corrected_body.setPlainText("The evidence supports 60%.")
    qtbot.mouseClick(save_correction, Qt.MouseButton.LeftButton)
    assert probability_history.revision_count == 1

    displayed_body = first_runtime.window.findChild(QLabel, "journalEntryBody1")
    original_body = first_runtime.window.findChild(
        QLabel,
        "journalEntryOriginalBody1",
    )
    assert displayed_body is not None
    assert original_body is not None
    assert displayed_body.text() == "The evidence supports 60%."
    assert original_body.text() == "The evidence teh supports 60%."

    revise = first_runtime.window.findChild(QPushButton, "reviseForecastButton")
    assert revise is not None
    qtbot.mouseClick(revise, Qt.MouseButton.LeftButton)
    revision_dialog = first_runtime.window.findChild(
        QDialog,
        "reviseForecastDialog",
    )
    assert revision_dialog is not None
    qtbot.waitUntil(revision_dialog.isVisible)
    revised_probability = revision_dialog.findChild(
        QSpinBox,
        "revisionProbabilityInput",
    )
    save_revision = revision_dialog.findChild(
        QPushButton,
        "saveForecastRevisionButton",
    )
    assert revised_probability is not None
    assert save_revision is not None
    revised_probability.setValue(75)
    qtbot.mouseClick(save_revision, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: current_probability.text() == "75%")
    assert probability_history.revision_count == 2

    with first_runtime.database.transaction() as connection:
        journal_row = connection.execute(
            "SELECT body, forecast_revision_id FROM journal_entries"
        ).fetchone()
        correction_row = connection.execute(
            "SELECT body FROM journal_entry_corrections"
        ).fetchone()
        revision_count = connection.execute(
            "SELECT COUNT(*) FROM forecast_revisions"
        ).fetchone()[0]
    assert tuple(journal_row) == ("The evidence teh supports 60%.", 1)
    assert tuple(correction_row) == ("The evidence supports 60%.",)
    assert revision_count == 2
    expected_chart_samples = probability_history.samples
    assert [sample.probability_percent for sample in expected_chart_samples] == [
        60,
        75,
    ]
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.navigate_to("Prediction Detail")

    reopened_probability = second_runtime.window.findChild(
        QLabel,
        "predictionDetailProbability",
    )
    reopened_probability_history = second_runtime.window.findChild(
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    reopened_body = second_runtime.window.findChild(QLabel, "journalEntryBody1")
    reopened_original = second_runtime.window.findChild(
        QLabel,
        "journalEntryOriginalBody1",
    )
    reopened_context = second_runtime.window.findChild(
        QLabel,
        "journalEntryForecastAtTime1",
    )
    edited = second_runtime.window.findChild(QLabel, "journalEntryEdited1")
    edit_history = second_runtime.window.findChild(
        QGroupBox,
        "journalEntryEditHistory1",
    )
    timeline = second_runtime.window.findChild(QWidget, "forecastTimeline")
    assert reopened_probability is not None
    assert reopened_probability_history is not None
    assert reopened_body is not None
    assert reopened_original is not None
    assert reopened_context is not None
    assert edited is not None
    assert edit_history is not None
    assert timeline is not None
    assert reopened_probability.text() == "75%"
    assert reopened_probability_history.revision_count == 2
    assert reopened_probability_history.samples == expected_chart_samples
    assert reopened_body.text() == "The evidence supports 60%."
    assert reopened_original.text() == "The evidence teh supports 60%."
    assert reopened_context.text() == "Forecast at the time: 60%"
    assert edited.text().startswith("Edited ")
    assert not edit_history.isChecked()
    assert [
        timeline.layout().itemAt(index).widget().objectName()
        for index in range(timeline.layout().count())
    ] == ["forecastRevision1", "journalEntry1", "forecastRevision2"]
    second_runtime.close()


def test_runtime_closes_database_when_window_close_fails(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    class FailingWindow:
        def close(self) -> None:
            raise RuntimeError("window close failed")

    runtime = ApplicationRuntime(
        qt_app=cast(QApplication, object()),
        database=database,
        window=cast(QMainWindow, FailingWindow()),
    )

    with pytest.raises(RuntimeError, match="window close failed"):
        runtime.close()

    assert not database.is_open


def test_run_closes_runtime_when_show_fails(monkeypatch, tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    class FailingWindow:
        close_called = False

        def show(self) -> None:
            raise RuntimeError("window show failed")

        def close(self) -> None:
            self.close_called = True

    window = FailingWindow()
    runtime = ApplicationRuntime(
        qt_app=cast(QApplication, object()),
        database=database,
        window=cast(QMainWindow, window),
    )
    monkeypatch.setattr(reckonsolve.app, "create_runtime", lambda **_kwargs: runtime)

    with pytest.raises(RuntimeError, match="window show failed"):
        reckonsolve.app.run([])

    assert window.close_called
    assert not database.is_open


def test_run_reports_expected_database_startup_failure(monkeypatch, qtbot) -> None:
    def fail_to_create_runtime(**_kwargs) -> None:
        raise MigrationError("unrecognized database")

    shown_errors: list[tuple[str, str]] = []

    def record_error(_parent, title: str, message: str) -> None:
        shown_errors.append((title, message))

    monkeypatch.setattr(reckonsolve.app, "create_runtime", fail_to_create_runtime)
    monkeypatch.setattr(reckonsolve.app.QMessageBox, "critical", record_error)

    assert reckonsolve.app.run([]) == 1
    assert shown_errors == [
        (
            "Reckonsolve could not start",
            (
                "Reckonsolve could not open its database. No existing data was "
                "replaced.\n\nunrecognized database"
            ),
        )
    ]
