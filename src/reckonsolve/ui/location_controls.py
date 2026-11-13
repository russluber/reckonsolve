"""Focused folder review and explicit interrupted-move recovery."""

import logging
import sqlite3
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QEventLoop, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.relocation import MoveReview, RelocationService
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.journal_location import MoveRecoveryRequired
from reckonsolve.data.location_native import LocationError
from reckonsolve.data.migrations import MigrationError
from reckonsolve.ui.components import PageHeader, PersistentMessageLabel
from reckonsolve.ui.visual_system import ActionRole, StatusTone, apply_action_role

logger = logging.getLogger(__name__)


class MoveReviewDialog(QDialog):
    def __init__(self, review: MoveReview, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Move journal and restart?")
        self.setObjectName("moveJournalReview")
        self.resize(660, 420)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        layout.addWidget(
            PageHeader(
                "Move journal",
                "Move the complete journal, including all saved history.",
                parent=self,
            )
        )
        for title, path in (
            ("Current location", review.source),
            ("New location", review.destination),
            ("Verified recovery copy will be kept at", review.recovery),
        ):
            label = QLabel(f"{title}\n{path}", self)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            layout.addWidget(label)
        guidance = QLabel(
            "Choose an unsynchronized local folder. Close other Reckonsolve windows and CLI commands first.\n\n"
            "The old location will be protected against further writes. Backups and exports elsewhere stay in place. "
            "Reckonsolve restarts at Journal, keeping appearance and window size.",
            self,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.move_button = buttons.addButton(
            "Move and restart", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.move_button.setObjectName("confirmMoveAndRestart")
        self.move_button.setAutoDefault(False)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setDefault(True)
        apply_action_role(self.move_button, ActionRole.PRIMARY)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)


class LocationControls(QWidget):
    storage_failed = Signal(object)
    archive_refused = Signal(object)

    def __init__(
        self,
        preview: Callable[[Path], MoveReview],
        move: Callable[[MoveReview], None],
        parent: QWidget,
    ):
        super().__init__(parent)
        self.preview, self.move = preview, move
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        guidance = QLabel(
            "Move this complete journal to a local folder that isn't synchronized by another app.",
            self,
        )
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        self.choose = QPushButton("Choose folder…", self)
        self.choose.setObjectName("chooseJournalFolder")
        apply_action_role(self.choose, ActionRole.SECONDARY)
        layout.addWidget(self.choose, 0, Qt.AlignmentFlag.AlignLeft)
        self.result = PersistentMessageLabel(
            accessible_name="Journal location result", parent=self
        )
        self.result.setObjectName("journalLocationResult")
        self.result.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.result)
        self.choose.clicked.connect(self._choose)

    def _choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose a new journal folder")
        if not folder:
            return
        try:
            review = self.preview(Path(folder))
            if MoveReviewDialog(review, self).exec() != QDialog.DialogCode.Accepted:
                return
            self.result.show_message("Moving the complete journal…", StatusTone.NEUTRAL)
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                QApplication.processEvents(
                    QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents
                )
                self.move(review)
            finally:
                QApplication.restoreOverrideCursor()
        except (ForecastContractIntegrityError, MigrationError) as error:
            self.result.show_message(str(error), StatusTone.ERROR)
            self.storage_failed.emit(error)
            self.archive_refused.emit(error)
        except (LocationError, OSError, sqlite3.Error) as error:
            self.result.show_message(str(error), StatusTone.ERROR)
            self.storage_failed.emit(error)
        except Exception as error:
            logger.exception("Unexpected journal relocation failure")
            self.result.show_message(
                f"The move could not complete. {error}", StatusTone.ERROR
            )
            self.storage_failed.emit(error)

    def clear_result(self) -> None:
        self.result.clear_message()


def review_recovery(error: MoveRecoveryRequired) -> bool:
    service = RelocationService(error.store)
    try:
        action = service.recovery_action()
        state = error.state
        box = QMessageBox()
        box.setWindowTitle("Recover interrupted journal move")
        box.setIcon(QMessageBox.Icon.Warning)
        if action == "keep":
            box.setText(
                "The journal is still at its current location. Keep that location and cancel this interrupted move?"
            )
            label = "Keep current location"
        else:
            box.setText(
                "The original location is write-protected. Verify the complete copies and finish the interrupted move?"
            )
            label = "Verify and finish move"
        box.setInformativeText(
            f"Current: {state['source']}\nNew: {state['destination']}\nRecovery: {state['recovery']}\n\n"
            "Uncertain or changed files stop recovery. Existing copies are retained."
        )
        box.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        proceed = box.addButton(label, QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        if box.clickedButton() is not proceed:
            return False
        service.recover(action)
        return True
    except (
        LocationError,
        OSError,
        sqlite3.Error,
        ForecastContractIntegrityError,
        MigrationError,
    ) as failure:
        QMessageBox.critical(
            None,
            "Journal recovery stopped",
            f"No journal was opened. Keep all files, including {error.store.move_file}.\n\n{failure}",
        )
        return False
