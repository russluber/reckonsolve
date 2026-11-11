"""Explicit review inside the same focused editing dialog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
)

from reckonsolve.ui.creation_task import form_values
from reckonsolve.ui.visual_system import ActionRole, apply_action_role


class DialogReview:
    """Preserve the form and bind final consent to exactly the reviewed inputs."""

    def __init__(self, dialog: QDialog, buttons: QDialogButtonBox) -> None:
        self.dialog, self.buttons = dialog, buttons
        self.active = False
        self.values: tuple = ()
        self.hidden: list[tuple[QWidget, bool]] = []
        self.panel = QScrollArea(dialog)
        self.panel.setWidgetResizable(True)
        self.panel.setMinimumHeight(160)
        self.text = QLabel(self.panel)
        self.text.setTextFormat(Qt.TextFormat.PlainText)
        self.text.setWordWrap(True)
        self.text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.text.setAccessibleName("Review proposed changes")
        self.panel.setWidget(self.text)
        dialog.layout().insertWidget(0, self.panel, 1)
        self.panel.hide()
        self.back = QPushButton("Back to editing", dialog)
        self.back.clicked.connect(self.edit)
        apply_action_role(self.back, ActionRole.SECONDARY)
        buttons.addButton(self.back, QDialogButtonBox.ButtonRole.ActionRole)
        self.back.hide()
        self.save = buttons.button(QDialogButtonBox.StandardButton.Save)
        self.original_label = self.save.text()

    def show(self, message: str, label: str) -> None:
        self.values = form_values(self.dialog, ())
        self.hidden = [
            (widget, not widget.isHidden())
            for widget in self.dialog.findChildren(
                QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly
            )
            if widget not in (self.panel, self.buttons, self.back)
        ]
        for widget, _visible in self.hidden:
            widget.hide()
        self.text.setText(message)
        self.panel.show()
        self.back.show()
        self.save.setText(label)
        self.active = True
        self.back.setFocus(Qt.FocusReason.OtherFocusReason)

    def consent_matches(self) -> bool:
        if self.active and self.values == form_values(self.dialog, ()):
            return True
        self.edit()
        return False

    def edit(self) -> None:
        self.active = False
        self.panel.hide()
        self.back.hide()
        self.save.setText(self.original_label)
        for widget, visible in self.hidden:
            widget.setVisible(visible)


def confirm_contextual_terminal(editor: QDialog, decision: str, facts: str) -> bool:
    """Only contextual preparation needs this separate terminal confirmation."""
    if not editor.property("contextualEditor"):
        return True
    from PySide6.QtWidgets import QMessageBox

    dialog = QMessageBox(editor)
    dialog.setWindowTitle("Confirm " + decision.lower())
    dialog.setIcon(QMessageBox.Icon.Warning)
    dialog.setTextFormat(Qt.TextFormat.PlainText)
    question = editor.property("reviewedQuestion") or "Prediction"
    forecast = editor.property("reviewedForecast") or "See committed header"
    dialog.setText(
        f"{question}\n\n{facts}\n\nLatest committed forecast: {forecast}\n\n"
        "This terminal decision preserves history and cannot reopen forecasting. "
        + (
            "This record will not be scored."
            if decision == "Mark Invalid"
            else "Scoring eligibility is determined from the saved outcome time and Deadline."
        )
    )
    keep = dialog.addButton("Keep editing", QMessageBox.ButtonRole.RejectRole)
    commit = dialog.addButton(decision, QMessageBox.ButtonRole.AcceptRole)
    dialog.setDefaultButton(keep)
    dialog.exec()
    return dialog.clickedButton() is commit
