"""Metadata editing, definition confirmations, and audited history."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from main_window_fakes import (
    FakeNumericPrediction,
    FakeNumericRevision,
    FakePrediction,
    FakePredictionOperations,
    MetadataUpdateCall,
)
from main_window_helpers import (
    _open_edit_dialog,
    _open_numeric_edit_dialog,
    _required_child,
)
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.predictions import (
    DefinitionChange,
    PredictionStatus,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
)
from reckonsolve.ui import MainWindow


def test_numeric_edit_details_reuses_metadata_dialog_and_preserves_definition(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    revision = FakeNumericRevision(
        revision_id=20,
        prediction_id=2,
        quantiles=FiveQuantiles.from_values(
            {5: "1.25", 25: "2.00", 50: "3.50", 75: "7.00", 95: "10.75"}, 2
        ),
        sequence=1,
        created_at=instant,
        rationale="Initial rationale",
    )
    numeric = FakeNumericPrediction(
        prediction_id=2,
        question="How many days will this take?",
        unit="days",
        decimal_places=2,
        status=PredictionStatus.OPEN,
        created_at=instant,
        updated_at=instant,
        current_revision=revision,
        background="Original background",
        tags=("Original",),
    )
    operations = FakePredictionOperations()
    operations.numeric_latest = numeric
    operations.numeric_revisions = [revision]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dialog = _open_numeric_edit_dialog(qtbot, window)
    context = _required_child(dialog, QLabel, "editNumericDefinitionContext")
    assert "fixed after creation" in context.text()
    assert "Unit: days" in context.text()
    assert "Precision: 2 decimal places" in context.text()
    assert context.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    assert dialog.findChild(QLineEdit, "editNumericUnitInput") is None
    assert dialog.findChild(QSpinBox, "editNumericPrecisionInput") is None

    _required_child(dialog, QPlainTextEdit, "editBackgroundInput").setPlainText(
        "Updated numeric background"
    )
    _required_child(dialog, QLineEdit, "editTagsInput").setText("Planning, Numeric")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.update_calls[0].prediction_id == numeric.prediction_id
    assert operations.update_calls[0].expected_metadata_version == 1
    assert operations.numeric_latest is not None
    assert operations.numeric_latest.background == "Updated numeric background"
    assert operations.numeric_latest.unit == numeric.unit
    assert operations.numeric_latest.decimal_places == numeric.decimal_places
    assert operations.numeric_latest.current_revision == revision
    assert _required_child(window, QLabel, "numericBackgroundValue").text() == (
        "Updated numeric background"
    )
    assert not dialog.isVisible()


def test_numeric_edit_details_cancel_is_side_effect_free(qtbot: QtBot) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    revision = FakeNumericRevision(
        revision_id=20,
        prediction_id=2,
        quantiles=FiveQuantiles.from_values(
            {5: "1.25", 25: "2.00", 50: "3.50", 75: "7.00", 95: "10.75"}, 2
        ),
        sequence=1,
        created_at=instant,
    )
    numeric = FakeNumericPrediction(
        prediction_id=2,
        question="How many days will this take?",
        unit="days",
        decimal_places=2,
        status=PredictionStatus.OPEN,
        created_at=instant,
        updated_at=instant,
        current_revision=revision,
    )
    operations = FakePredictionOperations()
    operations.numeric_latest = numeric
    operations.numeric_revisions = [revision]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dialog = _open_numeric_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText(
        "Unsaved Numeric question?"
    )
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == []
    assert operations.mutation_count == 0
    assert operations.numeric_latest == numeric
    assert not dialog.isVisible()


def test_edit_details_dialog_prefills_values_and_optional_date_controls(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=7,
        question="Will this dialog be prefilled?",
        probability_percent=55,
        background="Context",
        resolution_criteria="A public release counts.",
        forecast_deadline=date(2026, 9, 2),
        tags=("ui", "m3"),
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)

    assert _required_child(dialog, QLineEdit, "editQuestionInput").text() == (
        latest.question
    )
    assert _required_child(
        dialog, QPlainTextEdit, "editBackgroundInput"
    ).toPlainText() == ("Context")
    assert _required_child(dialog, QLineEdit, "editTagsInput").text() == "ui, m3"
    assert dialog.findChild(QCheckBox, "editForecastDeadlineToggle") is None
    assert dialog.findChild(QDateEdit, "editForecastDeadlineInput") is None
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    assert not expected_toggle.isChecked()
    assert not expected_input.isEnabled()
    assert expected_input.isHidden()
    assert expected_input.minimumDate() == QDate(1752, 9, 14)
    assert expected_input.maximumDate() == QDate(9999, 12, 31)


def test_unset_optional_date_is_revealed_only_when_enabled(qtbot: QtBot) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(7, "Will dates stay optional?", 55))
    )
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    deadline_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )

    assert not deadline_toggle.isChecked()
    assert not deadline_input.isEnabled()
    assert deadline_input.isHidden()

    qtbot.keyClick(deadline_toggle, Qt.Key.Key_Space)

    assert deadline_toggle.isChecked()
    assert deadline_input.isEnabled()
    assert deadline_input.isVisible()

    qtbot.keyClick(deadline_toggle, Qt.Key.Key_Space)

    assert not deadline_toggle.isChecked()
    assert not deadline_input.isEnabled()
    assert deadline_input.isHidden()


def test_edit_details_dialog_preserves_earliest_supported_date(
    qtbot: QtBot,
) -> None:
    earliest = date(1752, 9, 14)
    window = MainWindow(
        FakePredictionOperations(
            FakePrediction(
                7,
                "Earliest supported expected resolution?",
                55,
                expected_resolution=earliest,
            )
        )
    )
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)

    deadline = _required_child(dialog, QDateEdit, "editExpectedResolutionInput")
    assert deadline.date() == QDate(1752, 9, 14)
    assert deadline.isVisible()


def test_user_definition_text_is_always_rendered_as_plain_text(qtbot: QtBot) -> None:
    markup = "<b>Literal forecast wording</b>"
    operations = FakePredictionOperations(
        FakePrediction(
            prediction_id=7,
            question=markup,
            probability_percent=55,
            background="<i>Literal background</i>",
            resolution_criteria="<a href='x'>Literal criteria</a>",
            tags=("<u>tag</u>",),
        )
    )
    operations.definition_changes = (
        DefinitionChange(
            change_id=4,
            prediction_id=7,
            changed_at=datetime(2026, 8, 12, 19, 30, tzinfo=UTC),
            changed_fields=("question",),
            old_question="<em>Old literal</em>",
            new_question=markup,
            old_resolution_criteria=None,
            new_resolution_criteria=None,
            old_forecast_deadline=None,
            new_forecast_deadline=None,
        ),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name in (
        "predictionDetailQuestion",
        "predictionDetailTags",
        "predictionDetailBackground",
        "predictionDetailResolutionCriteria",
        "definitionChange4Question",
    ):
        label = _required_child(window, QLabel, object_name)
        assert label.textFormat() is Qt.TextFormat.PlainText
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == markup
    assert (
        "<em>Old literal</em>"
        in _required_child(
            window,
            QLabel,
            "definitionChange4Question",
        ).text()
    )


def test_open_edit_details_refreshes_externally_changed_prediction(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(7, "Original question", 55)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        question="Externally changed question",
        background="Newer context",
        metadata_version=2,
    )

    dialog = _open_edit_dialog(qtbot, window)

    assert operations.get_calls == [7, 7]
    assert _required_child(dialog, QLineEdit, "editQuestionInput").text() == (
        "Externally changed question"
    )
    assert (
        _required_child(
            dialog,
            QPlainTextEdit,
            "editBackgroundInput",
        ).toPlainText()
        == "Newer context"
    )
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Externally changed question"
    )


def test_cancel_edit_details_does_not_call_update(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Unsaved edit")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == []
    assert operations.mutation_count == 0
    assert not dialog.isVisible()


def test_repeated_cancel_deletes_finished_edit_dialogs(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for _attempt in range(3):
        dialog = _open_edit_dialog(qtbot, window)
        qtbot.mouseClick(
            _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
            Qt.MouseButton.LeftButton,
        )
        qtbot.waitUntil(lambda current=dialog: not current.isVisible())
        qtbot.waitUntil(
            lambda: (
                not window.findChildren(
                    QDialog,
                    "editPredictionDetailsDialog",
                )
            )
        )

    remaining = [
        dialog
        for dialog in window.findChildren(QDialog)
        if dialog.objectName() == "editPredictionDetailsDialog"
    ]
    assert remaining == []
    assert operations.update_calls == []


def test_noop_edit_closes_without_mutation(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.mutation_count == 0
    assert not dialog.isVisible()


def test_unprotected_edit_saves_without_warning_and_refreshes_detail(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: pytest.fail("Unexpected confirmation warning"),
    )
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QPlainTextEdit, "editBackgroundInput").setPlainText(
        "New background"
    )
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    expected_toggle.setChecked(True)
    expected_input.setDate(QDate(2026, 10, 20))
    _required_child(dialog, QLineEdit, "editTagsInput").setText("launch, ui")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == [
        MetadataUpdateCall(
            prediction_id=7,
            question="Original question",
            background="New background",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=date(2026, 10, 20),
            tags=("launch", "ui"),
            expected_metadata_version=1,
            confirm_meaning_change=False,
        )
    ]
    assert operations.mutation_count == 1
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        "New background"
    )
    assert _required_child(window, QLabel, "predictionDetailTags").text() == (
        "#launch  #ui"
    )
    assert (
        "2026"
        in _required_child(
            window,
            QLabel,
            "predictionDetailExpectedResolution",
        ).text()
    )


def test_expected_resolution_only_saves_without_warning(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: pytest.fail("Unexpected confirmation warning"),
    )
    dialog = _open_edit_dialog(qtbot, window)
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    qtbot.mouseClick(expected_toggle, Qt.MouseButton.LeftButton)
    expected_input.setDate(QDate(2026, 10, 20))

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.update_calls[0].expected_resolution == date(2026, 10, 20)
    assert not operations.update_calls[0].confirm_meaning_change
    assert operations.mutation_count == 1
    assert not dialog.isVisible()


def test_expected_edit_failure_is_shown_inline(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.update_error = ApplicationError("Those details could not be saved.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    error = _required_child(dialog, QLabel, "editDetailsError")
    assert error.text() == "Those details could not be saved."
    assert not error.isHidden()
    assert dialog.isVisible()
    assert operations.mutation_count == 0


def test_permanent_deadline_has_no_metadata_edit_controls(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    assert dialog.findChild(QCheckBox, "editForecastDeadlineToggle") is None
    assert dialog.findChild(QDateEdit, "editForecastDeadlineInput") is None
    assert any(
        "Forecast deadline: " in label.text() and " at " in label.text()
        for label in dialog.findChildren(QLabel)
    )
    assert operations.update_calls == []


def test_semantic_change_warning_decline_does_not_retry_or_mutate(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def decline_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", decline_warning)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert not operations.update_calls[0].confirm_meaning_change
    assert operations.mutation_count == 0
    assert operations.latest is not None
    assert operations.latest.question == "Original question"
    assert dialog.isVisible()
    assert warnings[0][0] == "Confirm definition change"
    assert "what this prediction means" in warnings[0][1]
    assert "create a new prediction" in warnings[0][1]
    assert "forecast revisions become locked" not in warnings[0][1]


def test_meaning_change_confirmation_retries_and_refreshes_returned_detail(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question", "resolution_criteria")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def accept_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", accept_warning)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")
    _required_child(dialog, QPlainTextEdit, "editResolutionCriteriaInput").setPlainText(
        "Published result counts."
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [call.confirm_meaning_change for call in operations.update_calls] == [
        False,
        True,
    ]
    assert [call.expected_metadata_version for call in operations.update_calls] == [
        1,
        1,
    ]
    assert operations.mutation_count == 1
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Changed question"
    )
    assert warnings[0][0] == "Confirm definition change"
    assert "what this prediction means" in warnings[0][1]
    assert "create a new prediction" in warnings[0][1]
    assert "forecast revisions become locked" not in warnings[0][1]
    assert "Definition history" in warnings[0][1]
    assert not dialog.isVisible()
    assert operations.definition_change_calls == [7, 7, 7, 7]


def test_stale_confirmation_retry_stays_inline_without_mutating(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")

    def make_stale(*args, **kwargs) -> QMessageBox.StandardButton:
        assert operations.latest is not None
        operations.latest = replace(
            operations.latest,
            background="Intervening edit",
            metadata_version=2,
        )
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", make_stale)
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [call.expected_metadata_version for call in operations.update_calls] == [
        1,
        1,
    ]
    assert operations.mutation_count == 0
    assert operations.latest is not None
    assert operations.latest.question == "Original question"
    assert operations.latest.background == "Intervening edit"
    error = _required_child(dialog, QLabel, "editDetailsError")
    assert "changed before" in error.text()
    assert not error.isHidden()
    assert dialog.isVisible()


def test_definition_history_is_collapsed_and_shows_snapshot_in_local_time(
    qtbot: QtBot,
) -> None:
    changed_at = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations(FakePrediction(7, "Changed question", 55))
    operations.definition_changes = (
        DefinitionChange(
            change_id=3,
            prediction_id=7,
            changed_at=changed_at,
            changed_fields=(
                "question",
                "resolution_criteria",
                "forecast_deadline",
            ),
            old_question="Original question",
            new_question="Changed question",
            old_resolution_criteria=None,
            new_resolution_criteria="A public release counts.",
            old_forecast_deadline=None,
            new_forecast_deadline=date(2026, 9, 30),
        ),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    history = _required_child(window, QGroupBox, "definitionHistoryGroup")
    content = _required_child(window, QWidget, "definitionHistoryContent")
    assert not history.isHidden()
    assert not history.isChecked()
    assert content.isHidden()
    history.setChecked(True)
    assert not content.isHidden()
    expected_timestamp = changed_at.astimezone().strftime("%b %d, %Y at %H:%M").strip()
    assert (
        _required_child(
            history,
            QLabel,
            "definitionChangeTimestamp3",
        ).text()
        == expected_timestamp
    )
    assert (
        "Original question"
        in _required_child(
            history,
            QLabel,
            "definitionChange3Question",
        ).text()
    )
    assert (
        "Not set"
        in _required_child(
            history,
            QLabel,
            "definitionChange3ResolutionCriteria",
        ).text()
    )
    assert (
        "2026"
        in _required_child(
            history,
            QLabel,
            "definitionChange3ForecastDeadline",
        ).text()
    )
