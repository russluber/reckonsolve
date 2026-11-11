"""Small contextual prose forms; canonical operations own validation and saving."""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.ui.dialog_review import confirm_contextual_terminal
from reckonsolve.ui.visual_system import (
    StatusTone,
    TextRole,
    apply_message_role,
    apply_text_role,
)


class BodyEditor(QDialog):
    saved = Signal(object)

    def __init__(
        self,
        title: str,
        body: str,
        save: Callable[[str], object],
        parent: QWidget | None = None,
        *,
        terminal: bool = False,
    ) -> None:
        super().__init__(parent)
        self._save, self._terminal = save, terminal
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        heading = QLabel(title, self)
        apply_text_role(heading, TextRole.SECTION_TITLE)
        layout.addWidget(heading)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setAccessibleName(title)
        self.body_input.setTabChangesFocus(True)
        self.body_input.setPlainText(body)
        self.body_input.setMinimumHeight(180)
        layout.addWidget(self.body_input)
        self.error = QLabel(self)
        self.error.setWordWrap(True)
        apply_message_role(
            self.error, StatusTone.ERROR, accessible_name=title + " error"
        )
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            title if terminal else "Save entry"
        )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def submit(self) -> None:
        body = self.body_input.toPlainText()
        if self._terminal and not confirm_contextual_terminal(
            self,
            "Mark Invalid",
            "Reason: " + (body.strip() or "Not supplied") + "\nNot scored.",
        ):
            return
        try:
            result = self._save(body)
        except ApplicationError as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.accept()
        self.saved.emit(result)
