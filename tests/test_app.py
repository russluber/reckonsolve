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
)

import reckonsolve.app
from reckonsolve.app import APPLICATION_NAME, ApplicationRuntime, create_runtime
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MigrationError


def test_application_runtime_reopens_same_database(qtbot, tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"

    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    assert first_runtime.window.isVisible()
    assert first_runtime.database.schema_version == 3
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    assert second_runtime.window.windowTitle() == APPLICATION_NAME
    assert second_runtime.database.schema_version == 3
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
