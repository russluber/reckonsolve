"""Tag management dialogs and archive navigation into them."""

from __future__ import annotations

import pytest
from main_window_fakes import (
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
    _select_tag_rows,
)
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.domain.tags import (
    TagLibraryItem,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.tag_manager import TagManagerDialog
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    MESSAGE_TONE_PROPERTY,
    TEXT_ROLE_PROPERTY,
    ActionRole,
    StatusTone,
    TextRole,
)


def test_prediction_browser_opens_secondary_tag_manager(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    opened: list[FakePredictionOperations] = []

    class FakeTagDialog(QObject):
        change_committed = Signal(object)
        result_reported = Signal(str, bool)
        archive_refused = Signal(object)
        archive_error = None
        latest_result = None
        changed = False

        def __init__(self, supplied_operations, _parent) -> None:
            super().__init__()
            opened.append(supplied_operations)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(
        "reckonsolve.ui.settings_screen.TagManagerDialog",
        FakeTagDialog,
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Settings")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "manageTagsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert opened == [operations]


def test_tag_manager_filters_and_confirms_rename_merge_and_delete(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    operations.tag_library = [
        TagLibraryItem(1, "Work", "work", 2),
        TagLibraryItem(2, "Personal", "personal", 1),
        TagLibraryItem(3, "Old", "old", 1),
    ]
    dialog = TagManagerDialog(operations)
    qtbot.addWidget(dialog)
    committed = []
    dialog.change_committed.connect(committed.append)
    table = _required_child(dialog, QTableWidget, "tagManagerTable")
    filter_input = _required_child(dialog, QLineEdit, "tagManagerFilter")

    assert (
        _required_child(dialog, QLabel, "tagManagerTitle").property(TEXT_ROLE_PROPERTY)
        == TextRole.PAGE_TITLE.value
    )
    assert _required_child(dialog, ContentPanel, "tagManagerLibraryPanel") is not None
    assert (
        _required_child(dialog, QPushButton, "deleteTagButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.DESTRUCTIVE.value
    )
    assert table.rowCount() == 3
    filter_input.setText("pers")
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "Personal"
    filter_input.clear()

    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Career", True),
    )
    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    _select_tag_rows(table, "Work")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "renameTagButton"),
        Qt.MouseButton.LeftButton,
    )
    assert {tag.display_name for tag in operations.tag_library} == {
        "Career",
        "Personal",
        "Old",
    }

    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QInputDialog.getItem",
        lambda *_args, **_kwargs: ("Career", True),
    )
    _select_tag_rows(table, "Career", "Personal")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "mergeTagsButton"),
        Qt.MouseButton.LeftButton,
    )
    assert {tag.display_name for tag in operations.tag_library} == {
        "Career",
        "Old",
    }

    confirmations: list[str] = []

    def confirm_delete(*args, **_kwargs):
        confirmations.append(str(args[2]))
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QMessageBox.question",
        confirm_delete,
    )
    _select_tag_rows(table, "Old")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "deleteTagButton"),
        Qt.MouseButton.LeftButton,
    )
    assert [tag.display_name for tag in operations.tag_library] == ["Career"]
    assert "Prediction associations removed" in confirmations[-1]
    assert (
        _required_child(dialog, QLabel, "tagManagerStatus").property(
            MESSAGE_TONE_PROPERTY
        )
        == StatusTone.SUCCESS.value
    )
    assert dialog.changed
    assert [c.kind for c in committed] == ["rename", "merge", "delete"]
    assert committed[0].source_ids == (1,) and committed[0].target_id == 1
    assert committed[1].source_ids == (2,) and committed[1].target_id == 1
    assert committed[1].target_name == "Career"
    assert committed[2].source_ids == (3,) and committed[2].target_id is None


def test_tag_manager_cancellation_leaves_library_unchanged(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    original = TagLibraryItem(1, "Work", "work", 2)
    operations.tag_library = [original]
    dialog = TagManagerDialog(operations)
    qtbot.addWidget(dialog)
    committed = []
    dialog.change_committed.connect(committed.append)
    table = _required_child(dialog, QTableWidget, "tagManagerTable")
    _select_tag_rows(table, "Work")
    monkeypatch.setattr(
        "reckonsolve.ui.tag_manager.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Career", False),
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "renameTagButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.tag_library == [original]
    assert not dialog.changed
    assert not committed
