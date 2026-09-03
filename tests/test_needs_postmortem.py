from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QMessageBox, QPushButton, QWidget

from reckonsolve.application.errors import ConcurrentTerminalCorrectionError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.notifications import NotificationHost

CREATED = datetime(2026, 8, 27, 9, tzinfo=UTC)
RESOLVED = CREATED + timedelta(days=1)
CORRECTED = RESOLVED + timedelta(days=1)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


def test_needs_postmortem_queue_uses_effective_terminal_facts_and_skip_is_stable(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    created = PredictionOperations(database, FixedClock(CREATED), UTC)
    binary = created.create_prediction("Will this need reflection?", 70)
    numeric = created.create_numeric_prediction(
        "How many units need reflection?",
        "units",
        1,
        "1.0",
        "2.0",
        "3.0",
        80,
    )
    with_postmortem = created.create_prediction("Already reflected", 50)
    invalid = created.create_prediction("Invalid is excluded", 50)
    terminal = PredictionOperations(database, FixedClock(RESOLVED), UTC)
    terminal.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    terminal.resolve_numeric_prediction(
        numeric.prediction_id,
        "2.0",
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    terminal.resolve_prediction(
        with_postmortem.prediction_id,
        BinaryOutcome.NO,
        postmortem="I captured the key lesson.",
        expected_revision_id=with_postmortem.current_revision_id,
        expected_metadata_version=with_postmortem.metadata_version,
    )
    terminal.invalidate_prediction(
        invalid.prediction_id,
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    operations.correct_binary_resolution(
        binary.prediction_id,
        BinaryOutcome.NO,
        resolution_notes=None,
        postmortem=None,
        correction_reason="The final record superseded the preliminary result.",
        expected_correction_id=None,
    )

    before_skip = operations.get_dashboard()
    assert [
        item.prediction_id for item in before_skip.needs_postmortem_predictions
    ] == [
        binary.prediction_id,
        numeric.prediction_id,
    ]
    binary_row, numeric_row = before_skip.needs_postmortem_predictions
    assert binary_row.prediction_type is PredictionType.BINARY
    assert binary_row.binary_outcome is BinaryOutcome.NO
    assert binary_row.current_correction_id is not None
    assert numeric_row.prediction_type is PredictionType.NUMERIC
    assert str(numeric_row.numeric_actual_value) == "2.0"
    assert numeric_row.numeric_unit == "units"
    before_scores = operations.get_forecast_analytics()

    completion = operations.record_postmortem_skip(
        numeric.prediction_id,
        expected_correction_id=numeric_row.current_correction_id,
    )

    after_skip = operations.get_dashboard()
    assert [item.prediction_id for item in after_skip.needs_postmortem_predictions] == [
        binary.prediction_id
    ]
    assert operations.get_forecast_analytics() == before_scores
    numeric_history = operations.get_numeric_resolution_history(numeric.prediction_id)
    assert numeric_history.postmortem_completion == completion
    assert numeric_history.effective.postmortem is None

    later = operations.correct_numeric_resolution(
        numeric.prediction_id,
        "2.0",
        resolution_notes=None,
        postmortem="I should have considered the bottleneck earlier.",
        expected_correction_id=None,
    )
    assert later.postmortem_completion == completion
    assert (
        later.effective.postmortem == "I should have considered the bottleneck earlier."
    )
    assert numeric.prediction_id not in {
        item.prediction_id
        for item in operations.get_dashboard().needs_postmortem_predictions
    }
    database.close()

    reopened = Database.open(path)
    restarted = PredictionOperations(reopened, FixedClock(CORRECTED), UTC)
    assert [
        item.prediction_id
        for item in restarted.get_dashboard().needs_postmortem_predictions
    ] == [binary.prediction_id]
    recovered = restarted.get_numeric_resolution_history(numeric.prediction_id)
    assert recovered.postmortem_completion == completion
    assert recovered.effective.postmortem == (
        "I should have considered the bottleneck earlier."
    )
    reopened.close()


def test_dashboard_skip_confirmation_and_detail_completion_display(
    qtbot,
    tmp_path,
    monkeypatch,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(
        database,
        FixedClock(CREATED),
        UTC,
    ).create_numeric_prediction(
        "How many days will this take?",
        "days",
        0,
        1,
        2,
        3,
        80,
    )
    PredictionOperations(
        database, FixedClock(RESOLVED), UTC
    ).resolve_numeric_prediction(
        created.prediction_id,
        2,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Dashboard")

    section = _child(window, ContentPanel, "dashboardNeedsPostmortemSection")
    assert section.title_label.text() == "Needs Postmortem"
    assert section.count_badge.text() == "1"
    row = _child(
        window,
        QPushButton,
        f"dashboardNeedsPostmortemPrediction{created.prediction_id}",
    )
    assert "NUMERIC | Actual: 2 days" in row.text()
    skip = _child(
        window,
        QPushButton,
        f"skipPostmortemPrediction{created.prediction_id}",
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Cancel,
    )
    qtbot.mouseClick(skip, Qt.MouseButton.LeftButton)
    assert section.count_badge.text() == "1"
    assert (
        operations.get_numeric_resolution_history(
            created.prediction_id
        ).postmortem_completion
        is None
    )

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(skip, Qt.MouseButton.LeftButton)
    assert section.count_badge.text() == "0"
    notification = _child(window, NotificationHost, "notificationHost")
    assert notification.current_message.startswith("Postmortem skipped.")
    assert notification.isVisible()
    assert _child(window, QLabel, "dashboardNeedsPostmortemEmpty").text() == (
        "No Resolved Predictions need a Postmortem decision."
    )

    window.navigate_to("Prediction Detail")
    completion = _child(window, QLabel, "numericPostmortemCompletion")
    assert not completion.isHidden()
    assert "Postmortem completion: Skipped" in completion.text()
    window.close()
    database.close()


def test_cleared_postmortem_enters_queue_and_stale_skip_appends_nothing(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(
        database,
        FixedClock(CREATED),
        UTC,
    ).create_prediction("Will a cleared reflection need attention?", 60)
    resolved = PredictionOperations(database, FixedClock(RESOLVED), UTC)
    resolved.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.YES,
        postmortem="Initial reflection.",
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    operations = PredictionOperations(database, FixedClock(CORRECTED), UTC)
    operations.correct_binary_resolution(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes=None,
        postmortem=None,
        expected_correction_id=None,
    )
    queued = operations.get_dashboard().needs_postmortem_predictions
    assert [item.prediction_id for item in queued] == [created.prediction_id]
    stale_token = queued[0].current_correction_id
    advanced = operations.correct_binary_resolution(
        created.prediction_id,
        BinaryOutcome.YES,
        resolution_notes="A later factual note.",
        postmortem=None,
        expected_correction_id=stale_token,
    )

    with pytest.raises(ConcurrentTerminalCorrectionError):
        operations.record_postmortem_skip(
            created.prediction_id,
            expected_correction_id=stale_token,
        )

    history = operations.get_binary_resolution_history(created.prediction_id)
    assert history.postmortem_completion is None
    assert history.current_correction_id == advanced.current_correction_id
    assert [
        item.prediction_id
        for item in operations.get_dashboard().needs_postmortem_predictions
    ] == [created.prediction_id]
    database.close()


def _child(parent: QWidget, widget_type, name: str):
    child = parent.findChild(widget_type, name)
    assert child is not None, name
    return child
