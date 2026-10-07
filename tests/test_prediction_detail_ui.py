"""Prediction Detail rendering, freshness, history, and action states."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from main_window_fakes import (
    FakeForecastRevision,
    FakeNumericPrediction,
    FakePrediction,
    FakePredictionOperations,
)
from main_window_helpers import (
    _open_revision_dialog,
    _required_child,
)
from main_window_helpers import (
    operations as operations,  # noqa: PLC0414 - pytest fixture registration
)
from main_window_helpers import (
    window as window,  # noqa: PLC0414 - pytest fixture registration
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.predictions import (
    PredictionStatus,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    QuantileRevision,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    BADGE_TONE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    SURFACE_ROLE_PROPERTY,
    TEXT_ROLE_PROPERTY,
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
)


def test_m42_binary_detail_separates_identity_common_and_lifecycle_actions(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        42,
        "Will this long question remain fully legible in the refreshed detail view?",
        65,
        tags=("presentation", "long-context"),
    )
    window = MainWindow(FakePredictionOperations(prediction))
    qtbot.addWidget(window)
    window.resize(800, 640)
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.waitUntil(window.isVisible)

    question = _required_child(window, QLabel, "predictionDetailQuestion")
    forecast_type = _required_child(window, QLabel, "predictionDetailType")
    status = _required_child(window, QLabel, "predictionDetailStatus")
    summary = _required_child(window, QFrame, "predictionDetailSummaryPanel")
    action_panel = _required_child(window, QFrame, "predictionDetailActionPanel")
    action_help = _required_child(window, QLabel, "predictionDetailActionHelp")
    action_container = _required_child(
        window,
        QWidget,
        "futurePredictionActions",
    )
    action_grid = action_container.layout()
    assert isinstance(action_grid, QGridLayout)

    assert question.text() == prediction.question
    assert question.property(TEXT_ROLE_PROPERTY) == TextRole.PAGE_TITLE.value
    assert (
        question.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    )
    assert forecast_type.text() == "BINARY · TRAJECTORY"
    assert status.property(BADGE_TONE_PROPERTY) == StatusTone.ACCENT.value
    assert summary.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert action_panel.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.RAISED.value
    assert window.findChild(QLabel, "predictionDetailLifecycleHeading") is None
    assert action_help.property(TEXT_ROLE_PROPERTY) == TextRole.LABEL.value
    assert action_help.contentsMargins().bottom() == int(Spacing.CONTROL)
    assert (
        _required_child(window, QPushButton, "reviseForecastButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(window, QPushButton, "deletePredictionButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.DESTRUCTIVE.value
    )
    edit = _required_child(window, QPushButton, "editPredictionDetailsButton")
    invalid = _required_child(window, QPushButton, "markInvalidButton")
    delete = _required_child(window, QPushButton, "deletePredictionButton")
    journal = _required_child(window, QPushButton, "addJournalEntryButton")
    revise = _required_child(window, QPushButton, "reviseForecastButton")
    review = _required_child(window, QPushButton, "reviewForecastButton")
    resolve = _required_child(window, QPushButton, "resolvePredictionButton")
    assert edit.property(ACTION_ROLE_PROPERTY) == ActionRole.SECONDARY.value
    assert invalid.property(ACTION_ROLE_PROPERTY) == ActionRole.CAUTION.value
    assert action_grid.getItemPosition(action_grid.indexOf(journal)) == (0, 1, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(revise)) == (0, 2, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(review)) == (0, 3, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(edit)) == (1, 1, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(resolve)) == (1, 2, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(invalid)) == (1, 3, 1, 1)
    assert action_grid.getItemPosition(action_grid.indexOf(delete)) == (2, 2, 1, 1)
    action_buttons = (
        revise,
        journal,
        review,
        edit,
        resolve,
        invalid,
        delete,
    )
    assert all(button.width() <= 210 for button in action_buttons)
    # Equal-stretch columns share leftover pixels when the width is not
    # divisible by three; a one-pixel remainder is not unequal button sizing.
    widths = [button.width() for button in action_buttons]
    assert max(widths) - min(widths) <= 1


def test_m42_dialogs_share_heading_context_error_and_action_roles(
    qtbot: QtBot,
) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(7, "Will this dialog stay clear?", 60))
    )
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    title = _required_child(dialog, QLabel, "reviseForecastTitle")
    context = _required_child(dialog, QLabel, "reviseCurrentProbability")
    error = _required_child(dialog, QLabel, "reviseForecastError")
    save = _required_child(dialog, QPushButton, "saveForecastRevisionButton")
    cancel = _required_child(dialog, QPushButton, "cancelForecastRevisionButton")

    assert title.property(TEXT_ROLE_PROPERTY) == TextRole.SECTION_TITLE.value
    assert context.property(SURFACE_ROLE_PROPERTY) == SurfaceRole.SELECTED.value
    assert context.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    assert error.property(MESSAGE_TONE_PROPERTY) == StatusTone.ERROR.value
    assert save.property(ACTION_ROLE_PROPERTY) == ActionRole.PRIMARY.value
    assert cancel.property(ACTION_ROLE_PROPERTY) == ActionRole.SECONDARY.value
    assert dialog.focusWidget() is _required_child(
        dialog,
        QSpinBox,
        "revisionProbabilityInput",
    )


def test_prediction_detail_prefers_the_newer_numeric_prediction_when_times_tie(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Binary first?", 60))
    revision = QuantileRevision(
        1,
        99,
        FiveQuantiles.from_values({5: 1, 25: 1, 50: 2, 75: 3, 95: 3}, 0),
        1,
        operations.latest.created_at,
    )
    numeric = FakeNumericPrediction(
        99,
        "Numeric later?",
        "days",
        0,
        PredictionStatus.OPEN,
        revision.created_at,
        revision.created_at,
        revision,
    )
    operations.numeric_revisions = [revision]
    operations.numeric_latest = replace(
        numeric,
        created_at=operations.latest.created_at,
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        "Numeric later?"
    )


def test_prediction_detail_loads_latest_prediction_at_construction(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will this survive a restart?",
        probability_percent=60,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "60%"
    )
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden() is (
        False
    )
    assert _required_child(window, QLabel, "predictionDetailEmptyState").isHidden()


def test_prediction_detail_renders_locked_status(qtbot: QtBot) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Has this prediction passed its forecast deadline?",
        probability_percent=60,
        status=PredictionStatus.LOCKED,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "LOCKED"


def test_returning_to_prediction_detail_refreshes_external_changes(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(42, "Original question", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")
    operations.get_calls.clear()
    operations.latest = replace(
        original,
        question="Externally refreshed question",
        probability_percent=45,
        status=PredictionStatus.LOCKED,
        background="Fresh context",
        metadata_version=2,
        current_revision_id=2,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            revision_id=2,
            prediction_id=42,
            probability_percent=45,
            sequence=2,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
        )
    )
    operations.revision_read_calls.clear()

    window.navigate_to("Dashboard")
    window.navigate_to("Prediction Detail")

    assert operations.get_calls == [42]
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Externally refreshed question"
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "LOCKED"
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        "Fresh context"
    )
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 2
    assert [sample.probability_percent for sample in chart.samples] == [60, 45]
    assert operations.revision_read_calls == [42]


def test_prediction_detail_refresh_failure_retains_last_visible_data(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(42, "Still-visible question", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")
    operations.latest = None

    window.navigate_to("Dashboard")
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Still-visible question"
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be refreshed" in error.text()
    assert not error.isHidden()


def test_prediction_detail_shows_present_metadata_and_hides_missing_sections(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will the release ship?",
        probability_percent=65,
        background="The implementation is nearly complete.",
        resolution_criteria="Yes if the installer is published.",
        forecast_deadline=date(2026, 9, 1),
        expected_resolution=None,
        tags=("release", "desktop"),
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "predictionDetailTags").text() == (
        "#release  #desktop"
    )
    deadline = _required_child(window, QLabel, "predictionDetailForecastDeadline")
    assert " at " in deadline.text()
    assert "(permanent)" not in deadline.text()
    assert "Exact, fixed deadline:" in deadline.toolTip()
    assert deadline.wordWrap()
    assert not _required_child(
        window,
        QWidget,
        "predictionDetailForecastDeadlineRow",
    ).isHidden()
    assert _required_child(
        window,
        QWidget,
        "predictionDetailExpectedResolutionRow",
    ).isHidden()
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        latest.background
    )
    assert (
        _required_child(
            window,
            QLabel,
            "predictionDetailResolutionCriteria",
        ).text()
        == latest.resolution_criteria
    )


def test_prediction_detail_hides_all_empty_optional_metadata(qtbot: QtBot) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(42, "Will the view stay calm?", 65))
    )
    qtbot.addWidget(window)

    for object_name in (
        "predictionDetailTags",
        "predictionDetailExpectedResolutionRow",
        "predictionDetailBackgroundSection",
        "predictionDetailResolutionCriteriaSection",
        "definitionHistoryGroup",
    ):
        assert _required_child(window, QWidget, object_name).isHidden()


def test_prediction_detail_enables_open_lifecycle_actions(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(1, "Will this stay in scope?", 50)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    revise = _required_child(window, QPushButton, "reviseForecastButton")
    assert revise.isEnabled()
    assert "preserving" in revise.toolTip()

    journal = _required_child(window, QPushButton, "addJournalEntryButton")
    assert journal.isEnabled()
    assert "without changing" in journal.toolTip()

    for object_name in (
        "resolvePredictionButton",
        "markInvalidButton",
        "deletePredictionButton",
    ):
        button = _required_child(window, QPushButton, object_name)
        assert button.isEnabled()
        assert button.toolTip()
    assert _required_child(window, QLabel, "timelinePlaceholder").isHidden()
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    assert not chart.isHidden()
    assert _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    ).isHidden()


def test_probability_history_empty_and_load_failure_states_are_honest(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a missing chart read be described honestly?", 60)
    )
    operations.revisions.clear()
    window = MainWindow(operations)
    qtbot.addWidget(window)

    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    placeholder = _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    )
    assert chart.revision_count == 0
    assert chart.samples == ()
    assert chart.isHidden()
    assert not placeholder.isHidden()
    assert "No forecast revisions" in placeholder.text()

    operations.revision_read_error = ApplicationError("Revision read failed.")
    window.navigate_to("Prediction Detail")

    assert chart.revision_count == 0
    assert chart.isHidden()
    assert not placeholder.isHidden()
    assert "could not be loaded" in placeholder.text()
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "Revision read failed" in error.text()
    assert not error.isHidden()


def test_probability_history_refresh_failure_retains_matching_loaded_chart(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a transient read preserve visible history?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    retained_samples = chart.samples

    operations.revision_read_error = ApplicationError("Temporary read failure.")
    window.navigate_to("Prediction Detail")

    placeholder = _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    )
    assert chart.revision_count == 1
    assert chart.samples == retained_samples
    assert not chart.isHidden()
    assert not placeholder.isHidden()
    assert "last loaded chart remains visible" in placeholder.text()
    assert (
        "Temporary read failure"
        in _required_child(
            window,
            QLabel,
            "predictionDetailError",
        ).text()
    )


def test_probability_history_accessibility_reports_timeline_read_failure(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the nonvisual equivalent stay truthful?", 60)
    )
    operations.timeline_error = ApplicationError("Timeline read failed.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )

    assert chart.revision_count == 1
    assert "currently unavailable" in chart.accessibleDescription()

    operations.timeline_error = None
    window.navigate_to("Prediction Detail")

    assert "listed in the Timeline" in chart.accessibleDescription()


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.LOCKED, PredictionStatus.RESOLVED, PredictionStatus.INVALID],
)
def test_prediction_detail_disables_revision_for_ineligible_lifecycle(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Can this forecast be revised?", 60, status=status)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    button = _required_child(window, QPushButton, "reviseForecastButton")
    assert not button.isEnabled()
    assert status.value in button.toolTip()


def test_prediction_detail_has_helpful_empty_state(window: MainWindow) -> None:
    window.navigate_to("Prediction Detail")

    empty_state = _required_child(window, QLabel, "predictionDetailEmptyState")
    assert not empty_state.isHidden()
    assert "Create one" in empty_state.text()
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden()
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 0
    assert chart.isHidden()
