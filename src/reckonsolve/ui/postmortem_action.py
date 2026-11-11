"""An explicit reflection completion action, separate from written reflection."""

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QPushButton, QWidget

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.predictions import (
    BinaryResolutionHistory,
    NumericResolutionHistory,
)
from reckonsolve.ui.visual_system import ActionRole, apply_action_role


class PostmortemSkipButton(QPushButton):
    completed = Signal(str)

    def __init__(
        self,
        save: Callable,
        refresh: Callable[[], None],
        show_error: Callable[[str], None],
        parent: QWidget,
    ):
        super().__init__("Skip", parent)
        self.setAccessibleName("Skip Postmortem")
        self.setObjectName("skipAdaptivePostmortemButton")
        apply_action_role(self, ActionRole.QUIET)
        self._save, self._refresh, self._show_error = save, refresh, show_error
        self._history = None
        self.before_skip: Callable[[], bool] = lambda: True
        self.hide()
        self.clicked.connect(self._skip)

    def set_context(
        self, history: BinaryResolutionHistory | NumericResolutionHistory | None
    ) -> None:
        self._history = history
        self.setVisible(
            history is not None
            and history.effective.postmortem is None
            and history.postmortem_completion is None
        )

    def _skip(self) -> None:
        history = self._history
        if history is None:
            return
        if not self.before_skip():
            return
        if (
            QMessageBox.warning(
                self,
                "Skip Postmortem?",
                "Record reflection as deliberately complete without writing a Postmortem? "
                "This does not change the Resolution, score or lifecycle. You can still "
                "write a Postmortem later; this completion remains in history.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._save(
                history.effective.prediction_id,
                expected_correction_id=history.current_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self._refresh()
        self.completed.emit("Postmortem skipped. You can still write one later.")
