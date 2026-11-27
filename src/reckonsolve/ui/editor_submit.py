"""Local text-editor submission through the form's existing primary button."""

from weakref import ref

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)


def bind_editor_submit(form: QWidget, button: QAbstractButton) -> None:
    """Bind current text fields, safely repeating after a form is shown again."""
    handler = getattr(form, "_editor_submit_key_filter", None)
    if handler is None:
        handler = _EditorSubmit(form, button)
        form._editor_submit_key_filter = handler
    else:
        handler.set_button(button)
    for field in form.findChildren(QWidget):
        if isinstance(field, (QLineEdit, QPlainTextEdit, QTextEdit)):
            field.installEventFilter(handler)
    if "Ctrl+Enter" not in button.toolTip():
        button.setToolTip((button.toolTip() + "\nCtrl+Enter").strip())
    if "Ctrl+Enter" not in button.accessibleDescription():
        button.setAccessibleDescription(
            (button.accessibleDescription() + "\nShortcut: Ctrl+Enter.").strip()
        )


class _EditorSubmit(QObject):
    def __init__(self, form: QWidget, button: QAbstractButton) -> None:
        super().__init__(form)
        # The form owns the filter. Reverse strong references would retain a
        # deleted-on-close dialog wrapper after its native widget is gone.
        self._form = ref(form)
        self.set_button(button)

    def set_button(self, button: QAbstractButton) -> None:
        self._button = ref(button)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
            and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and not event.modifiers()
            & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier)
        ):
            event.accept()
            form, button = self._form(), self._button()
            # Consume disabled/read-only submissions too: native Return handling
            # must not fall through to a dialog's default button.
            if (
                not event.isAutoRepeat()
                and form is not None
                and button is not None
                and isinstance(watched, (QLineEdit, QPlainTextEdit, QTextEdit))
                and not watched.isReadOnly()
                and watched.isEnabled()
                and watched.isVisibleTo(form)
                and form.isVisible()
                and button.isVisibleTo(form)
                and button.isEnabled()
            ):
                # Match a real button click: native date/spin editors commit
                # any pending text on focus-out before the save handler reads it.
                button.setFocus(Qt.FocusReason.ShortcutFocusReason)
                button.click()
            return True
        return super().eventFilter(watched, event)
