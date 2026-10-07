"""Forecast revision dialogs, concurrency, and history refresh."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from main_window_fakes import (
    FakeForecastRevision,
    FakePrediction,
    FakePredictionOperations,
    ReviseForecastCall,
)
from main_window_helpers import (
    _open_revision_dialog,
    _required_child,
)
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
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


def test_opening_and_cancelling_revision_dialog_appends_nothing(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Will opening the editor preserve history?",
            60,
            current_revision_id=11,
            current_revision_sequence=3,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    assert _required_child(dialog, QLabel, "reviseCurrentProbability").text() == "60%"
    assert _required_child(dialog, QSpinBox, "revisionProbabilityInput").value() == 60
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == []
    assert len(operations.revisions) == 1


def test_opening_revision_refreshes_probability_and_concurrency_tokens(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(
        7,
        "Will the revision editor use fresh state?",
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
            12,
            7,
            70,
            2,
            datetime(2026, 8, 13, tzinfo=UTC),
        )
    )

    dialog = _open_revision_dialog(qtbot, window)
    assert _required_child(dialog, QLabel, "reviseCurrentProbability").text() == "70%"
    _required_child(dialog, QSpinBox, "revisionProbabilityInput").setValue(45)
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == [
        ReviseForecastCall(
            prediction_id=7,
            probability_percent=45,
            rationale="",
            expected_revision_id=12,
            expected_metadata_version=2,
        )
    ]


def test_revision_refresh_that_finds_locked_state_opens_no_dialog(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(7, "Will this lock before the dialog opens?", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    operations.latest = replace(original, status=PredictionStatus.LOCKED)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "reviseForecastButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.findChild(QDialog, "reviseForecastDialog") is None
    assert operations.revise_calls == []
    assert not _required_child(window, QPushButton, "reviseForecastButton").isEnabled()
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "locked" in error.text()
    assert not error.isHidden()


def test_same_probability_revision_error_stays_inline_and_open(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will an unchanged forecast be rejected?", 60)
    )
    operations.revise_error = ApplicationError(
        "The new forecast matches the current 60%. Add a journal entry instead."
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    error = _required_child(dialog, QLabel, "reviseForecastError")
    assert "matches the current" in error.text()
    assert not error.isHidden()
    assert len(operations.revisions) == 1


def test_revision_rationale_helper_explains_when_to_use_journal(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will revision guidance clarify the Journal?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dialog = _open_revision_dialog(qtbot, window)

    helper = _required_child(dialog, QLabel, "revisionRationaleHelper")
    assert helper.text() == (
        "This explanation stays attached to the new forecast. To record a thought "
        "without changing probability, add a Journal entry."
    )
    assert helper.textFormat() is Qt.TextFormat.PlainText
    assert helper.wordWrap()
    rationale = _required_child(dialog, QPlainTextEdit, "revisionRationaleInput")
    assert rationale.accessibleDescription() == helper.text()
    layout = dialog.layout()
    assert layout.indexOf(rationale) < layout.indexOf(helper)
    assert layout.indexOf(helper) < layout.indexOf(
        _required_child(dialog, QLabel, "reviseForecastError")
    )


@pytest.mark.parametrize("new_probability", [0, 37, 100])
def test_revision_appends_with_tokens_and_refreshes_forecast_history(
    qtbot: QtBot,
    new_probability: int,
) -> None:
    original = FakePrediction(
        7,
        "Will a revision append honestly?",
        60,
        metadata_version=4,
        current_revision_id=11,
        current_revision_sequence=3,
        current_rationale="Initial <b>reason</b>",
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    dialog = _open_revision_dialog(qtbot, window)
    _required_child(dialog, QSpinBox, "revisionProbabilityInput").setValue(
        new_probability
    )
    _required_child(dialog, QPlainTextEdit, "revisionRationaleInput").setPlainText(
        "New <i>evidence</i>"
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == [
        ReviseForecastCall(
            prediction_id=7,
            probability_percent=new_probability,
            rationale="New <i>evidence</i>",
            expected_revision_id=11,
            expected_metadata_version=4,
        )
    ]
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        f"{new_probability}%"
    )
    assert (
        _required_child(window, QLabel, "forecastRevisionProbability12").text()
        == f"FORECAST  60% \N{RIGHTWARDS ARROW} {new_probability}%"
    )
    rationale = _required_child(window, QLabel, "forecastRevisionRationale12")
    assert rationale.text() == "New <i>evidence</i>"
    assert rationale.textFormat() is Qt.TextFormat.PlainText
    assert chart.revision_count == 2
    assert [sample.sequence for sample in chart.samples] == [3, 4]
    assert [sample.probability_percent for sample in chart.samples] == [
        60,
        new_probability,
    ]


def test_forecast_history_uses_previous_revision_for_nonconsecutive_return(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will the forecast return to its starting value?",
        60,
        current_revision_id=3,
        current_revision_sequence=3,
    )
    operations = FakePredictionOperations(latest)
    operations.revisions = [
        FakeForecastRevision(1, 7, 60, 1, datetime(2026, 8, 10, tzinfo=UTC)),
        FakeForecastRevision(2, 7, 40, 2, datetime(2026, 8, 11, tzinfo=UTC)),
        FakeForecastRevision(3, 7, 60, 3, datetime(2026, 8, 12, tzinfo=UTC)),
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert (
        _required_child(
            window,
            QLabel,
            "forecastRevisionProbability3",
        ).text()
        == "FORECAST  40% \N{RIGHTWARDS ARROW} 60%"
    )
