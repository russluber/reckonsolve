"""Ctrl+Enter clicks one local primary action without bypassing form guards."""

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from reckonsolve.ui.editor_submit import bind_editor_submit
from reckonsolve.ui.reflection_editor import ReflectionEditor


def test_submit_filter_does_not_retain_a_deleted_on_close_dialog(qtbot):
    from weakref import ref

    form = QDialog()
    form.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    qtbot.addWidget(form)
    layout = QVBoxLayout(form)
    field = QPlainTextEdit(form)
    save = QPushButton("Save", form)
    layout.addWidget(field)
    layout.addWidget(save)
    bind_editor_submit(form, save)
    reference = ref(form)
    form.show()
    form.reject()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    del form, layout, field, save
    assert reference() is None


def test_submit_commits_pending_native_input_like_clicking_save(qtbot):
    form = QDialog()
    qtbot.addWidget(form)
    layout = QVBoxLayout(form)
    spin = QSpinBox(form)
    spin.setRange(0, 100)
    spin.setValue(50)
    spin.setKeyboardTracking(False)
    layout.addWidget(spin)
    save = QPushButton("Save", form)
    layout.addWidget(save)
    values = []
    save.clicked.connect(lambda: values.append(spin.value()))
    bind_editor_submit(form, save)
    form.show()
    form.activateWindow()
    field = spin.lineEdit()
    field.setFocus()
    qtbot.waitUntil(field.hasFocus)
    field.selectAll()
    qtbot.keyClicks(field, "70")
    assert spin.value() == 50
    qtbot.keyClick(field, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    assert values == [70]


@pytest.mark.parametrize("field_type", [QLineEdit, QPlainTextEdit, QTextEdit])
@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter])
def test_local_submit_clicks_primary_once_and_retains_plain_enter(
    qtbot, field_type, key
):
    form = QDialog()
    qtbot.addWidget(form)
    layout = QVBoxLayout(form)
    field = field_type(form)
    layout.addWidget(field)
    save = QPushButton("Save", form)
    layout.addWidget(save)
    calls = []
    save.clicked.connect(lambda: calls.append(True))
    bind_editor_submit(form, save)
    bind_editor_submit(form, save)
    form.show()
    field.setFocus()
    qtbot.keyClicks(field, "Reasoning")
    if field_type is not QLineEdit:
        qtbot.keyClick(field, Qt.Key.Key_Return)
        assert field.toPlainText() == "Reasoning\n"
        assert not calls
    qtbot.keyClick(field, key, Qt.KeyboardModifier.ControlModifier)
    assert calls == [True]


@pytest.mark.parametrize(
    "state", ["disabled", "read_only", "hidden_button", "hidden_form", "repeat"]
)
def test_unavailable_or_repeated_action_never_submits(qtbot, state):
    form = QDialog()
    qtbot.addWidget(form)
    layout = QVBoxLayout(form)
    field = QPlainTextEdit(form)
    layout.addWidget(field)
    save = QPushButton("Save", form)
    save.setDefault(True)
    layout.addWidget(save)
    calls = []
    save.clicked.connect(lambda: calls.append(True))
    bind_editor_submit(form, save)
    form.show()
    field.setFocus()
    if state == "disabled":
        save.setEnabled(False)
    elif state == "read_only":
        field.setReadOnly(True)
    elif state == "hidden_button":
        save.hide()
    elif state == "hidden_form":
        form.hide()
    event = QKeyEvent(
        QEvent.Type.KeyPress,
        Qt.Key.Key_Return,
        Qt.KeyboardModifier.ControlModifier,
        "",
        state == "repeat",
        1,
    )
    QCoreApplication.sendEvent(field, event)
    assert calls == []
    assert field.toPlainText() == ""


def test_reflection_clear_still_requires_confirmation_and_keeps_draft(
    qtbot, monkeypatch
):
    calls = []
    confirmations = []
    editor = ReflectionEditor("Original reflection", lambda *args: calls.append(args))
    qtbot.addWidget(editor)
    editor.show()
    editor.body_input.clear()
    editor.reason.setText("Clear this reflection")

    def cancel_clear(*_args):
        confirmations.append(True)
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", cancel_clear)
    editor.reason.setFocus()
    qtbot.keyClick(
        editor.reason, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier
    )
    assert calls == []
    assert confirmations == [True]
    assert editor.isVisible()
    assert editor.reason.text() == "Clear this reflection"
