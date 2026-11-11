"""One reflection form for inline One-Shot and contextual Adaptive writing."""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.ui.visual_system import (
    StatusTone,
    TextRole,
    apply_message_role,
    apply_text_role,
)


class ReflectionEditor(QDialog):
    saved = Signal(object)

    def __init__(
        self,
        body: str | None,
        save: Callable[[str, bool, str], object],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._save = save
        self._initial = body
        self.setWindowTitle("Write Postmortem")
        layout = QVBoxLayout(self)
        title = QLabel("Postmortem", self)
        apply_text_role(title, TextRole.SECTION_TITLE)
        layout.addWidget(title)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setAccessibleName("Postmortem")
        self.body_input.setTabChangesFocus(True)
        self.body_input.setPlainText(body or "")
        self.body_input.setMinimumHeight(150)
        layout.addWidget(self.body_input)
        self.reason = QLineEdit(self)
        self.reason.setAccessibleName("Explanation for clearing Postmortem")
        self.reason.setPlaceholderText(
            "Explanation for clearing the existing Postmortem"
        )
        layout.addWidget(self.reason)
        self.body_input.textChanged.connect(self._sync_reason)
        self._sync_reason()
        self.error = QLabel(self)
        self.error.setWordWrap(True)
        apply_message_role(
            self.error, StatusTone.ERROR, accessible_name="Postmortem save error"
        )
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setText(
            "Save Postmortem"
        )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def _sync_reason(self) -> None:
        self.reason.setVisible(
            bool(self._initial) and not self.body_input.toPlainText().strip()
        )

    def submit(self) -> None:
        body = self.body_input.toPlainText()
        clear = bool(self._initial) and not body.strip()
        if (
            clear
            and QMessageBox.warning(
                self,
                "Clear Postmortem?",
                "Clear the effective Postmortem? The earlier text remains in correction history.",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Save
        ):
            return
        try:
            result = self._save(body, clear, self.reason.text())
        except (ApplicationError, ValueError) as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.accept()
        self.saved.emit(result)
