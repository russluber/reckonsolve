"""Retained creation work and guards across the existing mode-specific forms."""

from collections.abc import Callable

from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QCheckBox,
    QComboBox,
    QDateTimeEdit,
    QDoubleSpinBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QSpinBox,
    QWidget,
)


def form_values(form: QWidget, excluded: tuple[QWidget, ...]) -> tuple:
    """Inspect raw input text, including invalid values, without validating it.

    This adapter deliberately ignores labels, focus and disclosure state. It is
    temporary integration for the existing forms until their dedicated slice;
    it neither creates a canonical draft nor hides incomplete entered inputs.
    """
    result = []
    for widget in form.findChildren(QWidget):
        if widget in excluded:
            continue
        if isinstance(widget, QDateTimeEdit):
            result.append(
                widget.dateTime().toString()
                if widget.hasAcceptableInput()
                else widget.text()
            )
        elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
            result.append(
                widget.value() if widget.hasAcceptableInput() else widget.text()
            )
        elif isinstance(widget, QLineEdit) and not isinstance(
            widget.parentWidget(), (QAbstractSpinBox, QComboBox)
        ):
            result.append(widget.text())
        elif isinstance(widget, QPlainTextEdit):
            result.append(widget.toPlainText())
        elif isinstance(widget, QComboBox):
            result.append(widget.currentData())
        elif isinstance(widget, (QCheckBox, QRadioButton)):
            result.append(widget.isChecked())
    return tuple(result)


class CreationTask:
    def __init__(
        self,
        parent: QWidget,
        forms: tuple[QWidget, QWidget],
        resetters: tuple[Callable[[], None], Callable[[], None]],
        excluded: tuple[QWidget, ...],
    ) -> None:
        self.parent, self.forms, self.resetters, self.excluded = (
            parent,
            forms,
            resetters,
            excluded,
        )
        self.baselines = tuple(form_values(form, excluded) for form in forms)

    def dirty(self, index: int | None = None) -> bool:
        indexes = range(len(self.forms)) if index is None else (index,)
        return any(
            form_values(self.forms[i], self.excluded) != self.baselines[i]
            for i in indexes
        )

    def reset(self) -> None:
        for reset in self.resetters:
            reset()
        self.baselines = tuple(form_values(form, self.excluded) for form in self.forms)

    def confirm_exit(self) -> bool:
        if not self.dirty():
            return True
        dialog = QMessageBox(self.parent)
        dialog.setWindowTitle("Leave New Prediction?")
        dialog.setText("Discard the entered work in both creation modes and return?")
        keep = dialog.addButton("Keep editing", QMessageBox.ButtonRole.RejectRole)
        discard = dialog.addButton(
            "Discard changes and return", QMessageBox.ButtonRole.DestructiveRole
        )
        dialog.setDefaultButton(keep)
        dialog.exec()
        return dialog.clickedButton() is discard

    def confirm_save(self, active: int) -> bool:
        if not self.dirty(1 - active):
            return True
        return (
            QMessageBox.question(
                self.parent,
                "Save Prediction?",
                "Saving this Prediction will clear the entered creation work in both modes. "
                "If saving fails, all inputs will be retained. Continue?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            == QMessageBox.StandardButton.Save
        )
