"""Failure presentation retains the live form and never writes a draft."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QPushButton

from reckonsolve.application.errors import (
    ApplicationError,
    ForecastRevisionNotAllowedError,
    ValidationError,
)
from reckonsolve.domain.predictions import PredictionStatus
from reckonsolve.ui.visual_system import (
    ActionRole,
    StatusTone,
    apply_action_role,
    apply_message_role,
)


def show_editor_error(editor: QDialog, error: ApplicationError, label: QLabel) -> None:
    label.setText(str(error))
    if not (
        editor.property("contextualEditor")
        and (
            isinstance(error, ForecastRevisionNotAllowedError)
            and error.status is PredictionStatus.LOCKED
            or isinstance(error, ValidationError)
            and error.field == "forecast_deadline"
        )
    ):
        label.show()
        return
    label.hide()
    if getattr(editor, "_deadline_repeat", None) is None:
        cue = QPushButton("Deadline passed · Not saved", editor)
        cue.setObjectName("deadlineFailureRepeatButton")
        apply_action_role(cue, ActionRole.DESTRUCTIVE)
        editor.layout().insertWidget(max(0, editor.layout().count() - 1), cue)
        cue.show()
        toast = QLabel(editor)
        toast.setWordWrap(True)
        toast.setObjectName("revisionFailureNotification")
        toast.setAccessibleName("Revision not saved")
        apply_message_role(
            toast, StatusTone.ERROR, accessible_name="Revision not saved"
        )
        timer = QTimer(toast)
        timer.setSingleShot(True)
        timer.timeout.connect(toast.hide)

        def explain():
            toast.setText("Revision not saved\n" + label.text())
            width = max(200, min(360, editor.width() - 16))
            toast.setFixedWidth(width)
            toast.setFixedHeight(max(64, toast.heightForWidth(width) + 12))
            buttons = editor.findChild(QDialogButtonBox)
            bottom = buttons.y() if buttons is not None else editor.height()
            toast.move(
                max(4, editor.width() - width - 8), max(4, bottom - toast.height() - 8)
            )
            toast.show()
            toast.raise_()
            timer.start(5000)

        cue.clicked.connect(explain)
        editor._deadline_repeat = cue
        editor._deadline_explain = explain
    for buttons in editor.findChildren(QDialogButtonBox):
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            save.setEnabled(False)
    refresh = getattr(editor, "_refresh_reading", None)
    if refresh is not None:
        refresh()
    editor._deadline_explain()
