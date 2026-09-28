"""User keyboard and mouse paths through the One-Shot wall-clock time editor."""

import pytest
from PySide6.QtCore import QPoint, Qt, QTime
from PySide6.QtWidgets import QLineEdit, QVBoxLayout, QWidget

from reckonsolve.ui.time_input import SegmentedTimeEdit
from reckonsolve.ui.visual_system import install_visual_system


@pytest.fixture
def time_form(qtbot, qapp):
    root = QWidget()
    qtbot.addWidget(root)
    layout = QVBoxLayout(root)
    before, editor, after = QLineEdit(root), SegmentedTimeEdit(root), QLineEdit(root)
    for widget in (before, editor, after):
        layout.addWidget(widget)
    install_visual_system(root)
    editor.setTime(QTime(8, 45))
    root.show()
    root.activateWindow()
    qapp.processEvents()
    before.setFocus()
    qtbot.keyClick(before, Qt.Key.Key_Tab)
    assert editor.hasFocus()
    yield before, editor, after


@pytest.mark.parametrize(
    "hour,minute,period,expected",
    [
        ("7", "30", "p", QTime(19, 30)),
        ("12", "00", "a", QTime(0, 0)),
        ("12", "00", "p", QTime(12, 0)),
        ("09", "05", "A", QTime(9, 5)),
    ],
)
def test_type_tab_and_leave_time_field(
    time_form, qtbot, hour, minute, period, expected
):
    _, editor, after = time_form
    assert editor.currentSection() == editor.Section.HourSection
    qtbot.keyClicks(editor, hour)
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.currentSection() == editor.Section.MinuteSection
    assert editor.lineEdit().selectedText() == "45"
    qtbot.keyClicks(editor, minute)
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    assert editor.currentSection() == editor.Section.AmPmSection
    qtbot.keyClicks(editor, period)
    assert editor.time() == expected
    assert editor.hasAcceptableInput()
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    assert after.hasFocus()


def test_bounded_hour_advances_and_arrows_adjust_sections(time_form, qtbot):
    _, editor, _ = time_form
    qtbot.keyClicks(editor, "13")
    assert editor.time() == QTime(0, 45)
    assert editor.currentSection() == editor.Section.MinuteSection
    qtbot.keyClicks(editor, "59")
    qtbot.keyClick(editor, Qt.Key.Key_Up)
    assert editor.time() == QTime(0, 0)
    qtbot.keyClick(editor, Qt.Key.Key_Down)
    assert editor.time() == QTime(0, 59)
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    qtbot.keyClick(editor, Qt.Key.Key_Up)
    assert editor.time() == QTime(12, 59)
    qtbot.keyClick(editor, Qt.Key.Key_Down)
    assert editor.time() == QTime(0, 59)
    qtbot.keyClick(editor, Qt.Key.Key_Backtab)
    qtbot.keyClick(editor, Qt.Key.Key_Backtab)
    qtbot.keyClick(editor, Qt.Key.Key_Up)
    assert editor.time() == QTime(1, 59)


def test_reverse_tab_and_reentry_replace_sections(time_form, qtbot):
    before, editor, after = time_form
    qtbot.keyClicks(editor, "1")
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    qtbot.keyClick(editor, Qt.Key.Key_Backtab)
    qtbot.keyClicks(editor, "7")
    assert editor.time() == QTime(7, 45)
    qtbot.keyClick(editor, Qt.Key.Key_Backtab)
    assert before.hasFocus()
    after.setFocus()
    qtbot.keyClick(after, Qt.Key.Key_Backtab)
    assert editor.hasFocus()
    assert editor.currentSection() == editor.Section.AmPmSection


def test_clicking_hour_again_replaces_pending_digit(time_form, qtbot):
    _, editor, _ = time_form
    qtbot.keyClicks(editor, "1")
    line = editor.lineEdit()
    point = QPoint(line.contentsRect().left() + 8, line.height() // 2)
    qtbot.mouseClick(line, Qt.MouseButton.LeftButton, pos=point)
    qtbot.keyClicks(editor, "7")
    assert editor.time() == QTime(7, 45)


def test_read_only_time_cannot_change(time_form, qtbot):
    _, editor, _ = time_form
    editor.setReadOnly(True)
    qtbot.keyClicks(editor, "7p")
    qtbot.keyClick(editor, Qt.Key.Key_Up)
    assert editor.time() == QTime(8, 45)
