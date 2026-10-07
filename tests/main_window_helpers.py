"""Shared MainWindow fixtures and widget helpers."""

from __future__ import annotations

import pytest
from main_window_fakes import (
    FakePredictionOperations,
)
from PySide6.QtCore import QDate, Qt, QTime
from PySide6.QtWidgets import (
    QDialog,
    QPushButton,
    QTableWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.ui import MainWindow
from reckonsolve.ui.exact_deadline_input import ExactDeadlineInput


@pytest.fixture
def operations() -> FakePredictionOperations:
    return FakePredictionOperations()


@pytest.fixture
def window(
    qtbot: QtBot,
    operations: FakePredictionOperations,
) -> MainWindow:
    main_window = MainWindow(operations)
    qtbot.addWidget(main_window)
    return main_window


def _required_child[WidgetType: QWidget](
    parent: QWidget,
    widget_type: type[WidgetType],
    object_name: str,
) -> WidgetType:
    child = parent.findChild(widget_type, object_name)
    assert child is not None
    return child


def _select_tag_rows(table: QTableWidget, *display_names: str) -> None:
    table.clearSelection()
    wanted = set(display_names)
    for row in range(table.rowCount()):
        item = table.item(row, 0)
        if item is not None and item.text() in wanted:
            item.setSelected(True)


def _open_edit_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "editPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "editPredictionDetailsDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_numeric_edit_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(
            window,
            QPushButton,
            "editNumericPredictionDetailsButton",
        ),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "editPredictionDetailsDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_revision_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "reviseForecastButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "reviseForecastDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_journal_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "addJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "addJournalEntryDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_resolution_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "resolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "resolvePredictionDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_invalidation_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "markInvalidButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "markInvalidDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_correction_dialog(
    qtbot: QtBot,
    window: MainWindow,
    *,
    entry_id: int,
) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    return _click_correction_button(qtbot, window, entry_id=entry_id)


def _click_correction_button(
    qtbot: QtBot,
    window: MainWindow,
    *,
    entry_id: int,
) -> QDialog:
    qtbot.mouseClick(
        _required_child(
            window,
            QPushButton,
            f"correctJournalEntryButton{entry_id}",
        ),
        Qt.MouseButton.LeftButton,
    )
    dialogs = window.findChildren(QDialog, "correctJournalEntryDialog")
    dialog = next(
        (candidate for candidate in reversed(dialogs) if candidate.isVisible()),
        None,
    )
    assert dialog is not None
    return dialog


def _set_exact_deadline(window):
    deadline = window.findChild(ExactDeadlineInput)
    deadline.choose_custom()
    deadline.use_offset.setChecked(True)
    deadline.editor.setDate(QDate(2099, 12, 30))
    deadline.editor.setTime(QTime(18, 0))
    deadline.offset.setText("+00:00")
