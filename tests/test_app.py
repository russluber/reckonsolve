from typing import cast
from zipfile import ZipFile

import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QTableWidget,
    QWidget,
)

import reckonsolve.app
from reckonsolve.app import APPLICATION_NAME, ApplicationRuntime, create_runtime
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MigrationError
from reckonsolve.data.transfer import EXPORT_ARCHIVE_NAMES
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.identity import DEVELOPMENT_APPLICATION, STABLE_APPLICATION
from reckonsolve.ui.analytics_charts import (
    BrierTrendChart,
    CalibrationChart,
    ContainmentCalibrationChart,
)
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart


def test_application_runtime_reopens_same_database(qtbot, tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"

    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    assert first_runtime.window.isVisible()
    assert first_runtime.database.schema_version == 15
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    assert second_runtime.window.windowTitle() == APPLICATION_NAME
    assert second_runtime.database.schema_version == 15
    second_runtime.close()


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
    development.close()

    stable = create_runtime(identity=STABLE_APPLICATION)
    qtbot.addWidget(stable.window)
    assert stable.window.windowTitle() == "Reckonsolve"
    assert stable.database.path == tmp_path / "Reckonsolve" / "reckonsolve.sqlite3"
    assert stable.database.path != development.database.path
    stable.close()


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
    created = operations.create_prediction(
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
    assert (
        "Exported 16 CSV files"
        in runtime.window.findChild(
            QLabel,
            "dataManagementStatus",
        ).text()
    )
    runtime.close()

    recovered = Database.open(backup_path)
    assert (
        PredictionOperations(recovered).get_prediction(created.prediction_id).question
        == created.question
    )
    recovered.close()
    with ZipFile(export_path) as archive:
        assert tuple(archive.namelist()) == EXPORT_ARCHIVE_NAMES
        assert b"Settings create complete data artifacts" in archive.read(
            "predictions.csv"
        )

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


def test_dashboard_and_attention_setting_survive_restart(qtbot, tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    first.window.show()
    first.window.navigate_to("New Prediction")
    question = first.window.findChild(QLineEdit, "questionInput")
    create = first.window.findChild(QPushButton, "createPredictionButton")
    assert question is not None
    assert create is not None
    question.setText("Will the M8 Dashboard survive restart?")
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)

    first.window.navigate_to("Settings")
    threshold = first.window.findChild(QSpinBox, "staleThresholdInput")
    save = first.window.findChild(QPushButton, "saveStaleThresholdButton")
    assert threshold is not None
    assert save is not None
    threshold.setValue(21)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.navigate_to("Settings")
    reopened_threshold = second.window.findChild(QSpinBox, "staleThresholdInput")
    assert reopened_threshold is not None
    assert reopened_threshold.value() == 21
    second.window.navigate_to("Dashboard")
    row = second.window.findChild(QPushButton, "dashboardOpenPrediction1")
    dashboard_threshold = second.window.findChild(QLabel, "dashboardThreshold")
    assert row is not None
    assert dashboard_threshold is not None
    assert "M8 Dashboard" in row.text()
    assert dashboard_threshold.text() == "Needs Attention threshold: 21 days"
    second.close()


def test_prediction_browser_filters_and_opens_persisted_archive_after_restart(
    qtbot,
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    operations = PredictionOperations(first.database)
    operations.create_prediction(
        "Will the open archive item survive?",
        35,
        tags=("Durability",),
    )
    invalid = operations.create_prediction(
        "Will the Invalid archive item survive?",
        65,
        tags=("Durability", "Review"),
    )
    operations.invalidate_prediction(
        invalid.prediction_id,
        reason="Test the terminal archive filter.",
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.navigate_to("Predictions")
    search = second.window.findChild(QLineEdit, "predictionSearchInput")
    status_filter = second.window.findChild(QComboBox, "predictionStatusFilter")
    tag_filter = second.window.findChild(QListWidget, "predictionTagFilter")
    apply_filters = second.window.findChild(
        QPushButton,
        "applyPredictionFiltersButton",
    )
    results = second.window.findChild(QListWidget, "predictionBrowserResults")
    assert search is not None
    assert status_filter is not None
    assert tag_filter is not None
    assert apply_filters is not None
    assert results is not None
    assert results.count() == 2

    search.setText("INVALID ARCHIVE")
    status_filter.setCurrentIndex(status_filter.findData("invalid"))
    tag_filter.item(0).setSelected(True)
    qtbot.mouseClick(apply_filters, Qt.MouseButton.LeftButton)

    assert results.count() == 1
    assert "65%  |  INVALID" in results.item(0).text()
    assert "Tags: Durability, Review" in results.item(0).text()
    results.itemActivated.emit(results.item(0))
    assert second.window.current_screen_name == "Prediction Detail"
    detail_question = second.window.findChild(QLabel, "predictionDetailQuestion")
    detail_status = second.window.findChild(QLabel, "predictionDetailStatus")
    assert detail_question is not None
    assert detail_status is not None
    assert detail_question.text() == invalid.question
    assert detail_status.text() == "INVALID"
    second.close()


def test_analytics_score_resolved_predictions_and_filters_after_restart(
    qtbot,
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    operations = PredictionOperations(first.database)
    work = operations.create_prediction(
        "Will the scored Work event occur?",
        70,
        tags=("Work",),
    )
    operations.resolve_prediction(
        work.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=work.current_revision_id,
        expected_metadata_version=work.metadata_version,
    )
    personal = operations.create_prediction(
        "Will the scored Personal event occur?",
        20,
        tags=("Personal",),
    )
    operations.resolve_prediction(
        personal.prediction_id,
        BinaryOutcome.NO,
        expected_revision_id=personal.current_revision_id,
        expected_metadata_version=personal.metadata_version,
    )
    invalid = operations.create_prediction("Exclude this Invalid event?", 100)
    operations.invalidate_prediction(
        invalid.prediction_id,
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.navigate_to("Analytics")
    count = second.window.findChild(QLabel, "analyticsScoredCount")
    mean = second.window.findChild(QLabel, "analyticsMeanBrier")
    calibration = second.window.findChild(CalibrationChart, "calibrationChart")
    trend = second.window.findChild(BrierTrendChart, "brierTrendChart")
    table = second.window.findChild(QTableWidget, "calibrationBinTable")
    tag_filter = second.window.findChild(QComboBox, "analyticsTagFilter")
    assert count is not None
    assert mean is not None
    assert calibration is not None
    assert trend is not None
    assert table is not None
    assert tag_filter is not None
    assert count.text() == "Scored predictions: 2"
    assert mean.text() == "Mean Brier: 0.065"
    assert sum(item.count for item in calibration.bins) == 2
    assert len(trend.points) == 2
    assert table.item(2, 1).text() == "1"
    assert table.item(7, 1).text() == "1"

    tag_filter.setCurrentIndex(tag_filter.findData("Work"))

    assert count.text() == "Scored predictions: 1"
    assert mean.text() == "Mean Brier: 0.090"
    assert sum(item.count for item in calibration.bins) == 1
    assert len(trend.points) == 1
    second.close()


def test_numeric_analytics_filter_type_tag_and_unit_after_restart(
    qtbot,
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first = create_runtime(database_path=path)
    qtbot.addWidget(first.window)
    operations = PredictionOperations(first.database)
    days = operations.create_numeric_prediction(
        "How many days will this take?",
        "days",
        0,
        3,
        7,
        21,
        80,
        tags=("Work",),
    )
    operations.resolve_numeric_prediction(
        days.prediction_id,
        21,
        expected_revision_id=days.current_revision.revision_id,
        expected_metadata_version=days.metadata_version,
    )
    dollars = operations.create_numeric_prediction(
        "How many USD will this cost?",
        "USD",
        0,
        100,
        150,
        200,
        80,
        tags=("Money",),
    )
    operations.resolve_numeric_prediction(
        dollars.prediction_id,
        250,
        expected_revision_id=dollars.current_revision.revision_id,
        expected_metadata_version=dollars.metadata_version,
    )
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
    second.window.navigate_to("Analytics")
    numeric_count = second.window.findChild(QLabel, "numericAnalyticsScoredCount")
    containment = second.window.findChild(QLabel, "numericAnalyticsContainment")
    raw_scope = second.window.findChild(QLabel, "numericAnalyticsRawScope")
    chart = second.window.findChild(
        ContainmentCalibrationChart,
        "containmentCalibrationChart",
    )
    table = second.window.findChild(QTableWidget, "containmentCalibrationBinTable")
    type_filter = second.window.findChild(QComboBox, "analyticsTypeFilter")
    tag_filter = second.window.findChild(QComboBox, "analyticsTagFilter")
    unit_filter = second.window.findChild(QComboBox, "analyticsUnitFilter")
    assert numeric_count is not None
    assert containment is not None
    assert raw_scope is not None
    assert chart is not None
    assert table is not None
    assert type_filter is not None
    assert tag_filter is not None
    assert unit_filter is not None
    assert numeric_count.text() == "Scored Numeric Predictions: 2"
    assert containment.text() == "Contained outcomes: 1 of 2 (50%)"
    assert "will not average unlike units" in raw_scope.text()
    assert sum(item.count for item in chart.bins) == 2
    assert table.item(8, 1).text() == "2"
    assert table.item(8, 3).text() == "50%"

    type_filter.setCurrentIndex(type_filter.findData(PredictionType.NUMERIC))
    days_index = unit_filter.findData("days")
    assert unit_filter.isEnabled()
    assert days_index >= 0
    unit_filter.setCurrentIndex(days_index)
    assert unit_filter.currentData() == "days"
    analytics_error = second.window.findChild(QLabel, "analyticsError")
    assert analytics_error is not None
    assert analytics_error.isHidden(), analytics_error.text()

    median_error = second.window.findChild(QLabel, "numericMeanMedianAbsoluteError")
    width = second.window.findChild(QLabel, "numericMeanIntervalWidth")
    interval_score = second.window.findChild(QLabel, "numericMeanIntervalScore")
    assert median_error is not None
    assert width is not None
    assert interval_score is not None
    assert numeric_count.text() == "Scored Numeric Predictions: 1"
    assert median_error.text() == "Mean median absolute error: 14 days"
    assert width.text() == "Mean interval width: 18 days"
    assert interval_score.text() == "Mean interval score: 18 days"

    unit_filter.setCurrentIndex(0)
    tag_filter.setCurrentIndex(tag_filter.findData("Money"))
    assert numeric_count.text() == "Scored Numeric Predictions: 1"
    assert containment.text() == "Contained outcomes: 0 of 1 (0%)"
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
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)

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
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)

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
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)
    first.close()

    second = create_runtime(database_path=path)
    qtbot.addWidget(second.window)
    second.window.show()
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
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)
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


def test_numeric_create_close_reopen_displays_the_complete_interval(
    qtbot, tmp_path
) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    first_runtime.window.navigate_to("New Prediction")

    prediction_type = first_runtime.window.findChild(QComboBox, "predictionTypeInput")
    question = first_runtime.window.findChild(QLineEdit, "questionInput")
    unit = first_runtime.window.findChild(QLineEdit, "numericUnitInput")
    precision = first_runtime.window.findChild(QSpinBox, "numericPrecisionInput")
    lower = first_runtime.window.findChild(QLineEdit, "numericLowerBoundInput")
    median = first_runtime.window.findChild(QLineEdit, "numericMedianEstimateInput")
    upper = first_runtime.window.findChild(QLineEdit, "numericUpperBoundInput")
    confidence = first_runtime.window.findChild(QSpinBox, "numericConfidenceInput")
    create = first_runtime.window.findChild(QPushButton, "createPredictionButton")
    assert prediction_type is not None
    assert question is not None
    assert unit is not None
    assert precision is not None
    assert lower is not None
    assert median is not None
    assert upper is not None
    assert confidence is not None
    assert create is not None
    prediction_type.setCurrentIndex(prediction_type.findData("numeric"))
    question.setText("How many pages will the manuscript contain?")
    unit.setText("pages")
    precision.setValue(0)
    lower.setText("120")
    median.setText("180")
    upper.setText("240")
    confidence.setValue(80)
    qtbot.mouseClick(create, Qt.MouseButton.LeftButton)

    assert first_runtime.window.current_screen_name == "Prediction Detail"
    assert (
        first_runtime.window.findChild(QLabel, "numericCurrentInterval").text()
        == "80% interval: 120 to 240 pages"
    )
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    second_runtime.window.navigate_to("Prediction Detail")
    reopened_question = second_runtime.window.findChild(
        QLabel,
        "numericPredictionQuestion",
    )
    reopened_interval = second_runtime.window.findChild(
        QLabel,
        "numericCurrentInterval",
    )
    reopened_median = second_runtime.window.findChild(
        QLabel,
        "numericCurrentMedian",
    )
    assert reopened_question is not None
    assert reopened_interval is not None
    assert reopened_median is not None
    assert reopened_question.text() == "How many pages will the manuscript contain?"
    assert reopened_interval.text() == "80% interval: 120 to 240 pages"
    assert reopened_median.text() == "Median estimate: 180 pages"
    second_runtime.close()


def test_numeric_revision_journal_timeline_and_chart_work_end_to_end(
    qtbot,
    tmp_path,
) -> None:
    """M15's visible flows preserve interval history across a real UI session."""

    runtime = create_runtime(database_path=tmp_path / "reckonsolve.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    created = operations.create_numeric_prediction(
        "How many pages will the second draft contain?",
        "pages",
        0,
        "100",
        "160",
        "240",
        80,
    )
    runtime.window.show()
    runtime.window._prediction_detail_host.show_numeric_prediction(created)
    runtime.window.navigate_to("Prediction Detail")

    revise = runtime.window.findChild(QPushButton, "reviseNumericForecastButton")
    assert revise is not None
    qtbot.mouseClick(revise, Qt.MouseButton.LeftButton)
    dialog = runtime.window.findChild(QDialog, "reviseNumericForecastDialog")
    assert dialog is not None
    lower = dialog.findChild(QLineEdit, "numericRevisionLowerBoundInput")
    median = dialog.findChild(QLineEdit, "numericRevisionMedianEstimateInput")
    upper = dialog.findChild(QLineEdit, "numericRevisionUpperBoundInput")
    save_revision = dialog.findChild(QPushButton, "saveNumericForecastRevisionButton")
    assert lower is not None
    assert median is not None
    assert upper is not None
    assert save_revision is not None
    lower.setText("120")
    median.setText("180")
    upper.setText("300")
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

    correct = runtime.window.findChild(
        QPushButton,
        "correctNumericJournalEntryButton1",
    )
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
    chart = runtime.window.findChild(QWidget, "numericHistoryChart")
    assert len(revisions) == 2
    assert len(timeline) == 3
    assert chart is not None
    assert len(chart.samples) == 2
    assert chart.samples[-1].median_estimate == 180.0
    assert (
        runtime.window.findChild(QLabel, "numericJournalBody1").text()
        == "The outline expanded after the chapter plan review."
    )
    runtime.close()


def test_dashboard_and_browser_open_type_aware_numeric_predictions(
    qtbot,
    tmp_path,
) -> None:
    runtime = create_runtime(database_path=tmp_path / "reckonsolve.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database)
    operations.create_prediction("Will the Binary row remain clear?", 60)
    numeric = operations.create_numeric_prediction(
        "How many Numeric days?",
        "days",
        1,
        "2.0",
        "4.0",
        "8.0",
        80,
    )
    runtime.window.show()

    runtime.window.navigate_to("New Prediction")
    runtime.window.navigate_to("Dashboard")
    dashboard_row = runtime.window.findChild(
        QPushButton,
        f"dashboardOpenPrediction{numeric.prediction_id}",
    )
    assert dashboard_row is not None
    assert "NUMERIC" in dashboard_row.text()
    assert "80% interval: 2.0–8.0 days; median: 4.0 days" in dashboard_row.text()
    qtbot.mouseClick(dashboard_row, Qt.MouseButton.LeftButton)
    assert runtime.window.current_screen_name == "Prediction Detail"
    assert runtime.window.findChild(QLabel, "numericPredictionQuestion").text() == (
        numeric.question
    )

    runtime.window.navigate_to("Predictions")
    type_filter = runtime.window.findChild(QComboBox, "predictionTypeFilter")
    results = runtime.window.findChild(QListWidget, "predictionBrowserResults")
    assert type_filter is not None
    assert results is not None
    type_filter.setCurrentIndex(type_filter.findData("numeric"))
    assert results.count() == 1
    assert "NUMERIC" in results.item(0).text()
    results.itemActivated.emit(results.item(0))
    assert runtime.window.current_screen_name == "Prediction Detail"
    assert runtime.window.findChild(QLabel, "numericPredictionQuestion").text() == (
        numeric.question
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
    created = operations.create_numeric_prediction(
        "What will the signed quantity be?",
        "units",
        1,
        "1.0",
        "4.0",
        "8.0",
        80,
    )
    runtime.window.show()
    runtime.window._prediction_detail_host.show_numeric_prediction(created)
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
    reopened.window.navigate_to("Prediction Detail")
    assert (
        reopened.window.findChild(QLabel, "numericResolutionActualValue").text()
        == "Actual value: -2.5 units"
    )
    assert (
        "revision 1"
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
    invalid_candidate = operations.create_numeric_prediction(
        "How many invalid units?", "units", 0, 1, 2, 3, 80
    )
    runtime.window.show()
    runtime.window._prediction_detail_host.show_numeric_prediction(invalid_candidate)
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
    qtbot.mouseClick(save_invalid, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: invalid_dialog.isHidden())
    assert runtime.window.findChild(QLabel, "numericPredictionStatus").text() == (
        "INVALID"
    )

    disposable = operations.create_numeric_prediction(
        "Delete this Numeric test record", "items", 0, 1, 2, 3, 80
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
