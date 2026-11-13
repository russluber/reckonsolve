import sqlite3
from datetime import datetime
from pathlib import Path
from typing import cast
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QWidget,
)
from supported_fixtures import create_binary, create_numeric

import reckonsolve.app
from reckonsolve.app import APPLICATION_NAME, ApplicationRuntime, create_runtime
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MIGRATIONS, MigrationError
from reckonsolve.identity import DEVELOPMENT_APPLICATION, STABLE_APPLICATION
from reckonsolve.ui.exact_deadline_input import ExactDeadlineInput
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart


def _confirm_contextual_save(button: QPushButton) -> None:
    editor = button.parentWidget()
    while editor is not None and not isinstance(editor, QDialog):
        editor = editor.parentWidget()
    if editor is None or not editor.property("contextualEditor"):
        return

    def confirm():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QMessageBox)
        decision = (
            "Mark Invalid" if "invalid" in editor.objectName().lower() else "Resolve"
        )
        next(item for item in dialog.buttons() if item.text() == decision).click()

    QTimer.singleShot(0, confirm)


def _sqlite_logical_snapshot(
    database_path: Path,
) -> dict[str, tuple[tuple[object, ...], ...]]:
    """Capture every application and derived row without changing the database."""

    uri = f"{database_path.resolve().as_uri()}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, autocommit=True)
    try:
        table_names = tuple(
            str(row[0])
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        )
        snapshot: dict[str, tuple[tuple[object, ...], ...]] = {}
        for table_name in table_names:
            escaped_name = table_name.replace('"', '""')
            rows = tuple(
                sorted(
                    (
                        tuple(row)
                        for row in connection.execute(
                            f'SELECT * FROM "{escaped_name}"'
                        ).fetchall()
                    ),
                    key=repr,
                )
            )
            snapshot[table_name] = rows
        return snapshot
    finally:
        connection.close()


def test_application_runtime_reopens_same_database(qtbot, tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"

    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    assert first_runtime.window.isVisible()
    assert first_runtime.database.schema_version == len(MIGRATIONS)
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    assert second_runtime.window.windowTitle() == APPLICATION_NAME
    assert second_runtime.database.schema_version == len(MIGRATIONS)
    second_runtime.close()


def test_presentation_use_does_not_rewrite_current_schema_data(
    qtbot,
    tmp_path: Path,
) -> None:
    """Treat every SQLite row as a compatibility boundary for presentation."""

    database_path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(database_path)
    operations = PredictionOperations(database)
    binary = create_binary(
        operations,
        "Will the v0.5 Binary record remain byte-for-byte logical history?",
        60,
        rationale="Preserve the original rationale.",
        background="Preserve searchable background.",
        tags=("Compatibility", "Binary"),
    )
    operations.add_journal_entry(
        binary.prediction_id,
        "Preserve the Binary Journal entry.",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    operations.add_forecast_review(
        binary.prediction_id,
        note="Preserve the Binary Review.",
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    numeric = create_numeric(
        operations,
        "How many days will the v0.5 Numeric record retain?",
        "days",
        1,
        {5: "1.0", 25: "1.0", 50: "2.0", 75: "4.0", 95: "4.0"},
        rationale="Preserve the Numeric rationale.",
        tags=("Compatibility", "Numeric"),
    )
    operations.set_stale_threshold_days(23)
    database.check_search_index()
    assert database.schema_version == len(MIGRATIONS)
    database.close()

    before = _sqlite_logical_snapshot(database_path)
    presentation_path = database_path.parent / "presentation.ini"
    assert not presentation_path.exists()

    runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(runtime.window)
    runtime.window.show()
    for route in (
        "Journal",
        "Performance",
        "New Prediction",
        "Journal",
        "Settings",
    ):
        runtime.window.navigate_to(route)
        assert runtime.window.current_screen_name == route
    runtime.window._open_prediction(binary.prediction_id)
    assert runtime.window.current_screen_name == "Prediction Detail"
    runtime.window._open_prediction(numeric.prediction_id)
    assert runtime.window.current_screen_name == "Prediction Detail"
    assert runtime.database.schema_version == len(MIGRATIONS)
    runtime.close()

    assert presentation_path.is_file()
    assert _sqlite_logical_snapshot(database_path) == before


def test_development_runtime_has_visible_isolated_identity(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    def isolated_location(_location) -> str:
        return str(tmp_path / QApplication.applicationName())

    monkeypatch.setattr(
        "reckonsolve.paths.QStandardPaths.writableLocation",
        isolated_location,
    )

    development = create_runtime(identity=DEVELOPMENT_APPLICATION)
    qtbot.addWidget(development.window)
    assert development.identity is DEVELOPMENT_APPLICATION
    assert development.window.windowTitle() == "Reckonsolve Dev"
    assert development.database.path == (
        tmp_path / "Reckonsolve Dev" / "reckonsolve.sqlite3"
    )
    from reckonsolve.ui.presentation_settings import AppearanceMode

    development.window.appearance.select(AppearanceMode.DARK)
    assert development.window.appearance.dark
    development.close()

    stable = create_runtime(identity=STABLE_APPLICATION)
    qtbot.addWidget(stable.window)
    assert stable.window.windowTitle() == "Reckonsolve"
    assert stable.database.path == tmp_path / "Reckonsolve" / "reckonsolve.sqlite3"
    assert stable.database.path != development.database.path
    assert stable.window.appearance.mode is AppearanceMode.FOLLOW_WINDOWS
    stable.close()

    reopened_development = create_runtime(identity=DEVELOPMENT_APPLICATION)
    qtbot.addWidget(reopened_development.window)
    assert reopened_development.window.appearance.mode is AppearanceMode.DARK
    assert (tmp_path / "Reckonsolve Dev" / "presentation.ini").is_file()
    assert (tmp_path / "Reckonsolve" / "presentation.ini").is_file()
    reopened_development.close()


def test_settings_backup_and_export_work_end_to_end_across_restart(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    source_path = tmp_path / "reckonsolve.sqlite3"
    backup_path = tmp_path / "manual-backup.sqlite3"
    export_path = tmp_path / "manual-export.zip"
    runtime = create_runtime(database_path=source_path)
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    created = create_binary(
        operations,
        "Will Settings create complete data artifacts?",
        65,
        rationale="The export should retain this.",
        tags=("Recovery",),
    )
    selected = iter((str(backup_path), str(export_path)))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *_arguments: (next(selected), ""),
    )
    runtime.window.show()
    runtime.window.navigate_to("Settings")

    qtbot.mouseClick(
        runtime.window.findChild(QPushButton, "backUpNowButton"),
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(
        runtime.window.findChild(QPushButton, "exportCsvBundleButton"),
        Qt.MouseButton.LeftButton,
    )

    assert backup_path.is_file()
    assert export_path.is_file()
    with ZipFile(export_path) as archive:
        assert "Format version: 6" in archive.read("README.txt").decode("utf-8")
        assert "binary-trajectory-v1" in archive.read("predictions.csv").decode("utf-8")
    runtime.close()

    recovered = Database.open(backup_path)
    assert (
        PredictionOperations(recovered).get_prediction(created.prediction_id).question
        == created.question
    )
    recovered.close()

    reopened = create_runtime(database_path=source_path)
    qtbot.addWidget(reopened.window)
    reopened.window.show()
    reopened.window.navigate_to("Settings")
    assert (
        "Not yet"
        not in reopened.window.findChild(
            QLabel,
            "lastSuccessfulBackup",
        ).text()
    )
    reopened.close()


def test_cli_attention_setting_and_journal_survive_restart(qtbot, tmp_path):
    from io import StringIO

    from reckonsolve.cli import run

    path = tmp_path / "journal.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    prediction = create_binary(
        PredictionOperations(first.database), "Journal restart", 60
    )
    first.close()
    assert (
        run(
            ["settings", "attention-days", "--set", "21"],
            database_path=path,
            stdout=StringIO(),
        )
        == 0
    )
    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    journal = second.window._journal_screen
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    assert journal.cards[0].prediction_id == prediction.prediction_id
    assert PredictionOperations(second.database).get_stale_threshold_days() == 21
    assert second.window.findChild(QWidget, "staleThresholdInput") is None
    second.close()


def test_journal_search_and_filters_open_current_detail_after_restart(qtbot, tmp_path):
    from reckonsolve.domain.browser import ArchiveQuery

    path = tmp_path / "journal.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    operations = PredictionOperations(first.database)
    create_binary(operations, "Open archive item", 35, tags=("Durability",))
    invalid = create_binary(
        operations, "Invalid archive item", 65, tags=("Durability", "Review")
    )
    operations.invalidate_prediction(
        invalid.prediction_id,
        reason="Fixture terminal record",
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    first.close()
    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    journal = second.window._journal_screen
    journal._change(text="INVALID ARCHIVE", filters=ArchiveQuery(tags=("Durability",)))
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    assert journal.page.total == 1
    assert journal.cards[0].prediction_id == invalid.prediction_id
    journal._open(invalid.prediction_id, None)
    assert second.window.current_screen_name == "Prediction Detail"
    assert (
        second.window.findChild(QLabel, "predictionDetailQuestion").text()
        == invalid.question
    )
    second.close()


def test_resolve_through_ui_survives_restart_with_scoring_context(
    qtbot,
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    first.window.show()
    first.window.navigate_to("New Prediction")
    question = first.window.findChild(QLineEdit, "questionInput")
    probability = first.window.findChild(QSpinBox, "probabilityInput")
    create = first.window.findChild(QPushButton, "createPredictionButton")
    assert question is not None
    assert probability is not None
    assert create is not None
    question.setText("Will the M7 resolution survive restart?")
    probability.setValue(42)
    create_binary(
        PredictionOperations(first.database), question.text(), probability.value()
    )
    first.window.creation_task.reset()
    first.window.navigate_to("Prediction Detail")

    resolve = first.window.findChild(QPushButton, "resolvePredictionButton")
    assert resolve is not None
    qtbot.mouseClick(resolve, Qt.MouseButton.LeftButton)
    dialog = first.window.findChild(QDialog, "resolvePredictionDialog")
    assert dialog is not None
    qtbot.waitUntil(dialog.isVisible)
    outcome_no = dialog.findChild(QRadioButton, "resolutionOutcomeNo")
    notes = dialog.findChild(QPlainTextEdit, "resolutionNotesInput")
    postmortem = dialog.findChild(QPlainTextEdit, "resolutionPostmortemInput")
    save = dialog.findChild(QPushButton, "confirmResolvePredictionButton")
    assert outcome_no is not None
    assert notes is not None
    assert postmortem is not None
    assert save is not None
    outcome_no.setChecked(True)
    notes.setPlainText("Verified from the official result.")
    postmortem.setPlainText("I should have weighted the base rate more.")
    _confirm_contextual_save(save)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)

    status = first.window.findChild(QLabel, "predictionDetailStatus")
    scoring = first.window.findChild(QLabel, "predictionResolutionScoringForecast")
    assert status is not None
    assert scoring is not None
    assert status.text() == "RESOLVED"
    assert "42%" in scoring.text()
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.creation_task.reset()
    second.window.navigate_to("Prediction Detail")
    reopened_status = second.window.findChild(QLabel, "predictionDetailStatus")
    reopened_outcome = second.window.findChild(QLabel, "predictionResolutionOutcome")
    reopened_notes = second.window.findChild(QLabel, "predictionResolutionNotes")
    reopened_postmortem = second.window.findChild(QLabel, "predictionPostmortem")
    assert reopened_status is not None
    assert reopened_outcome is not None
    assert reopened_notes is not None
    assert reopened_postmortem is not None
    assert reopened_status.text() == "RESOLVED"
    assert reopened_outcome.text() == "Outcome: No"
    assert reopened_notes.text() == "Verified from the official result."
    assert reopened_postmortem.text() == "I should have weighted the base rate more."
    second.close()


def test_mark_invalid_through_ui_survives_restart(qtbot, tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    first.window.show()
    first.window.navigate_to("New Prediction")
    question = first.window.findChild(QLineEdit, "questionInput")
    create = first.window.findChild(QPushButton, "createPredictionButton")
    assert question is not None
    assert create is not None
    question.setText("Will this cancelled event happen?")
    _set_exact_deadline(create.window())
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)
    create.window().navigate_to("Prediction Detail")

    mark_invalid = first.window.findChild(QPushButton, "markInvalidButton")
    assert mark_invalid is not None
    qtbot.mouseClick(mark_invalid, Qt.MouseButton.LeftButton)
    dialog = first.window.findChild(QDialog, "markInvalidDialog")
    assert dialog is not None
    qtbot.waitUntil(dialog.isVisible)
    reason = dialog.findChild(QPlainTextEdit, "invalidationReasonInput")
    save = dialog.findChild(QPushButton, "confirmMarkInvalidButton")
    assert reason is not None
    assert save is not None
    reason.setPlainText("The underlying event was cancelled.")
    _confirm_contextual_save(save)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.creation_task.reset()
    second.window.navigate_to("Prediction Detail")
    status = second.window.findChild(QLabel, "predictionDetailStatus")
    reopened_reason = second.window.findChild(QLabel, "predictionInvalidationReason")
    assert status is not None
    assert reopened_reason is not None
    assert status.text() == "INVALID"
    assert reopened_reason.text() == "The underlying event was cancelled."
    second.close()


def test_confirmed_untouched_delete_through_ui_remains_deleted_after_restart(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    first.window.show()
    first.window.navigate_to("New Prediction")
    question = first.window.findChild(QLineEdit, "questionInput")
    create = first.window.findChild(QPushButton, "createPredictionButton")
    assert question is not None
    assert create is not None
    question.setText("Accidental duplicate")
    _set_exact_deadline(create.window())
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)
    create.window().navigate_to("Prediction Detail")
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    delete = first.window.findChild(QPushButton, "deletePredictionButton")
    assert delete is not None
    assert delete.isEnabled()
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    with first.database.transaction() as connection:
        assert connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0] == 0
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.creation_task.reset()
    second.window.navigate_to("Prediction Detail")
    empty = second.window.findChild(QLabel, "predictionDetailEmptyState")
    assert empty is not None
    assert not empty.isHidden()
    second.close()


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
    _set_exact_deadline(create_button.window())
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert first_runtime.window.current_screen_name == "Journal"
    first_runtime.window.creation_task.reset()
    first_runtime.window.navigate_to("Prediction Detail")
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.creation_task.reset()
    second_runtime.window.navigate_to("Prediction Detail")
    question = second_runtime.window.findChild(QLabel, "predictionDetailQuestion")
    probability = second_runtime.window.findChild(QLabel, "predictionDetailProbability")
    assert question is not None
    assert probability is not None
    assert question.text() == "Will this prediction survive restart?"
    assert probability.text() == "60%"
    second_runtime.close()


def test_numeric_create_close_reopen_displays_the_complete_interval(qtbot, tmp_path):
    from reckonsolve.ui.screens import NewPredictionScreen

    database_path = tmp_path / "reckonsolve.sqlite3"
    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    first_runtime.window.navigate_to("New Prediction")
    screen = first_runtime.window.findChild(NewPredictionScreen)
    screen.prediction_type_input.setCurrentIndex(
        screen.prediction_type_input.findData("numeric")
    )
    screen.question_input.setText("How many pages will the manuscript contain?")
    screen.numeric_unit_input.setText("pages")
    screen.numeric_constraint_input.setCurrentIndex(2)
    for level, value in {5: "120", 25: "150", 50: "180", 75: "210", 95: "240"}.items():
        screen.quantile_input.inputs[level].setText(value)
    screen.numeric_exact_deadline.choose_custom()
    screen.numeric_exact_deadline.use_offset.setChecked(True)
    screen.numeric_exact_deadline.editor.setDate(QDate(2099, 12, 30))
    screen.numeric_exact_deadline.offset.setText("+00:00")
    screen.submit()
    assert first_runtime.window.current_screen_name == "Journal"
    first_runtime.window.creation_task.reset()
    first_runtime.window.navigate_to("Prediction Detail")
    assert (
        first_runtime.window.findChild(QLabel, "numericCurrentInterval").text()
        == "90% interval: 120 to 240 pages"
    )
    first_runtime.close()
    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.creation_task.reset()
    second_runtime.window.navigate_to("Prediction Detail")
    assert (
        second_runtime.window.findChild(QLabel, "numericPredictionQuestion").text()
        == "How many pages will the manuscript contain?"
    )
    assert (
        second_runtime.window.findChild(QLabel, "numericCurrentInterval").text()
        == "90% interval: 120 to 240 pages"
    )
    assert (
        "Median: 180 pages"
        in second_runtime.window.findChild(QLabel, "numericCurrentMedian").text()
    )
    second_runtime.close()


def test_numeric_revision_journal_timeline_and_chart_work_end_to_end(
    qtbot,
    tmp_path,
) -> None:
    """Numeric revision and Journal correction retain exact quantile history."""

    runtime = create_runtime(database_path=tmp_path / "reckonsolve.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    created = create_numeric(
        operations,
        "How many pages will the second draft contain?",
        "pages",
        0,
        {5: "100", 25: "100", 50: "160", 75: "240", 95: "240"},
    )
    runtime.window.show()
    runtime.window._prediction_detail_host.show_numeric_prediction(created)
    runtime.window.creation_task.reset()
    runtime.window.navigate_to("Prediction Detail")

    revise = runtime.window.findChild(QPushButton, "reviseNumericForecastButton")
    assert revise is not None
    qtbot.mouseClick(revise, Qt.MouseButton.LeftButton)
    dialog = runtime.window.findChild(QDialog, "reviseQuantileForecastDialog")
    assert dialog is not None
    lower = dialog.findChild(QLineEdit, "quantile05Input")
    median = dialog.findChild(QLineEdit, "quantile50Input")
    upper = dialog.findChild(QLineEdit, "quantile95Input")
    save_revision = dialog.findChild(QDialogButtonBox).button(
        QDialogButtonBox.StandardButton.Save
    )
    assert lower is not None
    assert median is not None
    assert upper is not None
    assert save_revision is not None
    lower.setText("120")
    median.setText("180")
    upper.setText("300")
    dialog.findChild(QLineEdit, "quantile25Input").setText("140")
    dialog.findChild(QLineEdit, "quantile75Input").setText("240")
    qtbot.mouseClick(save_revision, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog.isHidden())

    journal = runtime.window.findChild(QPushButton, "addNumericJournalEntryButton")
    assert journal is not None
    qtbot.mouseClick(journal, Qt.MouseButton.LeftButton)
    journal_dialog = runtime.window.findChild(QDialog, "addNumericJournalEntryDialog")
    assert journal_dialog is not None
    body = journal_dialog.findChild(QPlainTextEdit, "numericJournalEntryBodyInput")
    save_journal = journal_dialog.findChild(
        QPushButton, "saveNumericJournalEntryButton"
    )
    assert body is not None
    assert save_journal is not None
    body.setPlainText("The outline grew after reviewing the new chapter plan.")
    qtbot.mouseClick(save_journal, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: journal_dialog.isHidden())

    journal_row = runtime.window.findChild(QWidget, "numericTimelineJournal1")
    correct = journal_row.findChild(QPushButton)
    assert correct is not None
    qtbot.mouseClick(correct, Qt.MouseButton.LeftButton)
    correction_dialog = runtime.window.findChild(
        QDialog,
        "correctNumericJournalEntryDialog",
    )
    assert correction_dialog is not None
    corrected_body = correction_dialog.findChild(
        QPlainTextEdit,
        "correctNumericJournalEntryBodyInput",
    )
    save_correction = correction_dialog.findChild(
        QPushButton,
        "saveNumericJournalCorrectionButton",
    )
    assert corrected_body is not None
    assert save_correction is not None
    corrected_body.setPlainText("The outline expanded after the chapter plan review.")
    qtbot.mouseClick(save_correction, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: correction_dialog.isHidden())

    revisions = operations.list_numeric_forecast_revisions(created.prediction_id)
    timeline = operations.list_numeric_timeline(created.prediction_id)
    chart = runtime.window._prediction_detail_host._numeric_detail.quantile_cdf
    assert len(revisions) == 2
    assert len(timeline) == 3
    assert chart is not None
    assert str(chart.quantiles.q50) == "180"
    journal_row = runtime.window.findChild(QWidget, "numericTimelineJournal1")
    assert any(
        "The outline expanded after the chapter plan review." in label.text()
        for label in journal_row.findChildren(QLabel)
    )
    runtime.close()


def test_journal_opens_type_aware_numeric_predictions(qtbot, tmp_path):
    from reckonsolve.domain.browser import ArchiveQuery
    from reckonsolve.domain.predictions import PredictionType

    runtime = create_runtime(database_path=tmp_path / "journal.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    create_binary(operations, "Binary row", 60)
    numeric = create_numeric(
        operations,
        "Numeric row",
        "days",
        1,
        {5: "2.0", 25: "2.0", 50: "4.0", 75: "8.0", 95: "8.0"},
    )
    runtime.window.show()
    journal = runtime.window._journal_screen
    journal._change(filters=ArchiveQuery(prediction_type=PredictionType.NUMERIC))
    qtbot.waitUntil(lambda: not journal.loading, timeout=10000)
    assert journal.page.total == 1
    assert journal.cards[0].prediction_id == numeric.prediction_id
    journal._open(numeric.prediction_id, None)
    assert (
        runtime.window.findChild(QLabel, "numericPredictionQuestion").text()
        == numeric.question
    )
    runtime.close()


def test_numeric_resolution_ui_persists_exact_terminal_information(
    qtbot,
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    runtime = create_runtime(database_path=path)
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    created = create_numeric(
        operations,
        "What will the signed quantity be?",
        "units",
        1,
        {5: "1.0", 25: "1.0", 50: "4.0", 75: "8.0", 95: "8.0"},
    )
    runtime.window.show()
    runtime.window._prediction_detail_host.show_numeric_prediction(created)
    runtime.window.creation_task.reset()
    runtime.window.navigate_to("Prediction Detail")

    resolve = runtime.window.findChild(QPushButton, "resolveNumericPredictionButton")
    assert resolve is not None
    qtbot.mouseClick(resolve, Qt.MouseButton.LeftButton)
    dialog = runtime.window.findChild(QDialog, "resolveNumericPredictionDialog")
    assert dialog is not None
    cancel = dialog.findChild(QPushButton, "cancelNumericResolutionButton")
    assert cancel is not None
    qtbot.mouseClick(cancel, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog.isHidden())
    with runtime.database.transaction() as connection:
        assert (
            connection.execute("SELECT COUNT(*) FROM numeric_resolutions").fetchone()[0]
            == 0
        )

    qtbot.mouseClick(resolve, Qt.MouseButton.LeftButton)
    dialog = runtime.window.findChild(QDialog, "resolveNumericPredictionDialog")
    assert dialog is not None
    actual = dialog.findChild(QLineEdit, "numericResolutionActualValueInput")
    notes = dialog.findChild(QPlainTextEdit, "numericResolutionNotesInput")
    postmortem = dialog.findChild(QPlainTextEdit, "numericResolutionPostmortemInput")
    save = dialog.findChild(QPushButton, "saveNumericResolutionButton")
    assert actual is not None
    assert notes is not None
    assert postmortem is not None
    assert save is not None
    actual.setText("-2.5")
    notes.setPlainText("The certified final measurement.")
    postmortem.setPlainText("The lower tail was too narrow.")
    _confirm_contextual_save(save)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: dialog.isHidden())

    assert runtime.window.findChild(QLabel, "numericPredictionStatus").text() == (
        "RESOLVED"
    )
    assert (
        runtime.window.findChild(QLabel, "numericResolutionActualValue").text()
        == "Actual value: -2.5 units"
    )
    assert not runtime.window.findChild(
        QPushButton, "reviseNumericForecastButton"
    ).isEnabled()
    runtime.close()

    reopened = create_runtime(database_path=path)
    qtbot.addWidget(reopened.window)
    reopened.window.show()
    reopened.window.creation_task.reset()
    reopened.window.navigate_to("Prediction Detail")
    assert (
        reopened.window.findChild(QLabel, "numericResolutionActualValue").text()
        == "Actual value: -2.5 units"
    )
    assert (
        "strictly before"
        in reopened.window.findChild(QLabel, "numericResolutionScoringForecast").text()
    )
    reopened.close()


def test_numeric_invalidation_and_confirmed_delete_work_in_detail(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    runtime = create_runtime(database_path=tmp_path / "reckonsolve.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    invalid_candidate = create_numeric(
        operations,
        "How many invalid units?",
        "units",
        0,
        {5: 1, 25: 1, 50: 2, 75: 3, 95: 3},
    )
    runtime.window.show()
    runtime.window._prediction_detail_host.show_numeric_prediction(invalid_candidate)
    runtime.window.creation_task.reset()
    runtime.window.navigate_to("Prediction Detail")
    mark_invalid = runtime.window.findChild(
        QPushButton, "markNumericPredictionInvalidButton"
    )
    assert mark_invalid is not None
    qtbot.mouseClick(mark_invalid, Qt.MouseButton.LeftButton)
    invalid_dialog = runtime.window.findChild(
        QDialog, "markNumericPredictionInvalidDialog"
    )
    assert invalid_dialog is not None
    reason = invalid_dialog.findChild(QPlainTextEdit, "numericInvalidationReasonInput")
    save_invalid = invalid_dialog.findChild(
        QPushButton, "saveNumericInvalidationButton"
    )
    assert reason is not None
    assert save_invalid is not None
    reason.setPlainText("The measurement became undefined.")
    _confirm_contextual_save(save_invalid)
    qtbot.mouseClick(save_invalid, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: invalid_dialog.isHidden())
    assert runtime.window.findChild(QLabel, "numericPredictionStatus").text() == (
        "INVALID"
    )

    disposable = create_numeric(
        operations,
        "Delete this Numeric test record",
        "items",
        0,
        {5: 1, 25: 1, 50: 2, 75: 3, 95: 3},
    )
    runtime.window._prediction_detail_host.show_numeric_prediction(disposable)
    delete = runtime.window.findChild(QPushButton, "deleteNumericPredictionButton")
    assert delete is not None
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_arguments: QMessageBox.StandardButton.Cancel,
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert operations.get_numeric_prediction(disposable.prediction_id).question

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_arguments: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    with runtime.database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM predictions WHERE id = ?",
                (disposable.prediction_id,),
            ).fetchone()[0]
            == 0
        )
    assert runtime.window.findChild(QLabel, "numericPredictionStatus").text() == (
        "INVALID"
    )
    runtime.close()


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
    create_binary(
        PredictionOperations(first_runtime.database), question_input.text(), 50
    )
    first_runtime.window.creation_task.reset()
    first_runtime.window.navigate_to("Prediction Detail")

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
    assert dialog.findChild(QCheckBox, "editForecastDeadlineToggle") is None
    assert dialog.findChild(QDateEdit, "editForecastDeadlineInput") is None
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
            expected_toggle,
            expected,
            tags,
            save_button,
        )
    )
    edited_question.setText("Will the M3 workflow persist after restart?")
    background.setPlainText("End-to-end metadata context.")
    criteria.setPlainText("Yes if the same details reopen from SQLite.")
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

    assert warning_messages == []
    assert dialog.review.active
    assert "Definition snapshot" in dialog.review.text.text()
    qtbot.mouseClick(save_button, Qt.MouseButton.LeftButton)
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
    second_runtime.window.creation_task.reset()
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
    assert "UTC" not in reopened_deadline.text()
    assert (
        datetime.fromisoformat(
            reopened_deadline.toolTip().removeprefix("Exact, fixed deadline: ")
        ).utcoffset()
        is not None
    )
    assert "(permanent)" not in reopened_deadline.text()
    assert (
        "2099-01-01"
        in PredictionOperations(second_runtime.database)
        .get_latest_prediction()
        .forecast_contract.forecast_deadline.instant.isoformat()
    )
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
    expected_toggle.setChecked(True)
    expected.setDate(QDate(2099, 12, 31))
    tags.setText("m4, persistence")
    _set_exact_deadline(create_button.window())
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert first_runtime.window.current_screen_name == "Journal"
    first_runtime.window.creation_task.reset()
    first_runtime.window.navigate_to("Prediction Detail")
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
    second_runtime.window.creation_task.reset()
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
    _set_exact_deadline(create_button.window())
    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert first_runtime.window.current_screen_name == "Journal"
    first_runtime.window.navigate_to("Prediction Detail")

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
    second_runtime.window.creation_task.reset()
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
    ] == ["forecastRevision2", "journalEntry1", "forecastRevision1"]
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


@pytest.mark.parametrize("error_type", [MigrationError, ForecastContractIntegrityError])
def test_run_reports_expected_database_startup_failure(
    monkeypatch, qtbot, error_type
) -> None:
    def fail_to_create_runtime(**_kwargs) -> None:
        raise error_type("unrecognized database")

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


def _set_exact_deadline(window):
    deadline = window.findChild(ExactDeadlineInput)
    deadline.choose_custom()
    deadline.use_offset.setChecked(True)
    deadline.editor.setDate(QDate(2099, 12, 30))
    deadline.offset.setText("+00:00")
