"""Application-level, nonblocking acknowledgments for routine success."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QAccessible, QAccessibleEvent, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    SurfaceRole,
    apply_action_role,
    apply_surface_role,
)

_DEFAULT_DURATION_MS = 4_500
_MODAL_POLL_MS = 100
_MINIMUM_CARD_WIDTH = 340
_MAXIMUM_CARD_WIDTH = 520


class NotificationHost(QFrame):
    """Show at most one transient message over the shell without page reflow."""

    def __init__(
        self,
        parent: QWidget,
        *,
        duration_ms: int = _DEFAULT_DURATION_MS,
        modal_widget: Callable[[], QWidget | None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("notificationHost")
        self.setAccessibleName("Status notification")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        self.setMaximumWidth(_MAXIMUM_CARD_WIDTH)

        self.message_label = QLabel(self)
        self.message_label.setObjectName("notificationMessage")
        self.message_label.setTextFormat(Qt.TextFormat.PlainText)
        self.message_label.setWordWrap(True)
        self.message_label.setAccessibleName("Status notification message")
        self.dismiss_button = QPushButton("Dismiss", self)
        self.dismiss_button.setObjectName("dismissNotificationButton")
        self.dismiss_button.setToolTip("Dismiss status notification")
        apply_action_role(self.dismiss_button, ActionRole.QUIET)
        self.dismiss_button.clicked.connect(self.dismiss)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch()
        action_row.addWidget(self.dismiss_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
        )
        layout.setSpacing(int(Spacing.CONTROL))
        layout.addWidget(self.message_label)
        layout.addLayout(action_row)

        self._duration_ms = max(1, duration_ms)
        self._modal_widget = modal_widget or QApplication.activeModalWidget
        self._scope_modal_to_window = modal_widget is None
        self._message = ""
        self._repeat_count = 0
        self._pending_message: str | None = None
        self._pending_count = 0

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setObjectName("notificationDismissTimer")
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.dismiss)
        self._modal_timer = QTimer(self)
        self._modal_timer.setObjectName("notificationModalTimer")
        self._modal_timer.setInterval(_MODAL_POLL_MS)
        self._modal_timer.timeout.connect(self._present_pending_when_safe)

        parent.installEventFilter(self)
        self.installEventFilter(self)
        self.message_label.installEventFilter(self)
        self.dismiss_button.installEventFilter(self)
        apply_surface_role(self, SurfaceRole.SELECTED)
        self.hide()

    @property
    def current_message(self) -> str:
        return self._message

    @property
    def repeat_count(self) -> int:
        return self._repeat_count

    def show_message(self, message: str) -> None:
        """Queue or show a plain acknowledgment; presentation failure is contained."""

        try:
            normalized = message.strip()
            if not normalized:
                return
            if self._has_blocking_modal():
                self._queue_pending(normalized)
                self._modal_timer.start()
                return
            self._present(normalized)
        except (RuntimeError, TypeError, ValueError):
            # A transient acknowledgment is never allowed to affect the operation
            # that already committed before the caller requested presentation.
            self.hide()

    def dismiss(self) -> None:
        self._dismiss_timer.stop()
        self._message = ""
        self._repeat_count = 0
        self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self.parentWidget() and event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Move,
            QEvent.Type.LayoutRequest,
        ):
            self._reposition()
        if watched in (self, self.message_label, self.dismiss_button):
            if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn):
                self._dismiss_timer.stop()
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.FocusOut):
                QTimer.singleShot(0, self._resume_dismissal_if_idle)
            elif event.type() == QEvent.Type.KeyPress:
                key_event = event if isinstance(event, QKeyEvent) else None
                if key_event is not None and key_event.key() == Qt.Key.Key_Escape:
                    self.dismiss()
                    return True
        return super().eventFilter(watched, event)

    def _queue_pending(self, message: str) -> None:
        if self._pending_message == message:
            self._pending_count += 1
        else:
            self._pending_message = message
            self._pending_count = 1

    def _present_pending_when_safe(self) -> None:
        try:
            if self._has_blocking_modal():
                return
            self._modal_timer.stop()
            message = self._pending_message
            count = self._pending_count
            self._pending_message = None
            self._pending_count = 0
            if message is None:
                return
            self._present(message, repeat_count=count)
        except (RuntimeError, TypeError, ValueError):
            self._modal_timer.stop()
            self._pending_message = None
            self._pending_count = 0
            self.hide()

    def _present(self, message: str, *, repeat_count: int = 1) -> None:
        if self.isVisible() and self._message == message:
            repeat_count += self._repeat_count
        self._message = message
        self._repeat_count = max(1, repeat_count)
        displayed = (
            message
            if self._repeat_count == 1
            else f"{message} ({self._repeat_count} times)"
        )
        self.message_label.setText(displayed)
        self.message_label.setAccessibleDescription(displayed)
        self.adjustSize()
        self._reposition()
        self.show()
        self.raise_()
        self._announce()
        if not self._is_interacting():
            self._dismiss_timer.start(self._duration_ms)

    def _resume_dismissal_if_idle(self) -> None:
        try:
            if self.isVisible() and not self._is_interacting():
                self._dismiss_timer.start(self._duration_ms)
        except RuntimeError:
            # A queued focus/hover callback can outlive its closing parent window.
            return

    def _is_interacting(self) -> bool:
        return self.underMouse() or self.dismiss_button.hasFocus()

    def _has_blocking_modal(self) -> bool:
        modal = self._modal_widget()
        if modal is None or not modal.isVisible():
            return False
        if not self._scope_modal_to_window:
            return True
        window = self.window()
        return modal is window or window.isAncestorOf(modal)

    def _reposition(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        natural_text_width = self.message_label.fontMetrics().horizontalAdvance(
            self.message_label.text()
        )
        preferred_width = max(
            _MINIMUM_CARD_WIDTH,
            min(
                _MAXIMUM_CARD_WIDTH,
                natural_text_width + int(Spacing.PAGE) * 2,
            ),
        )
        available_width = max(180, parent.width() - int(Spacing.PAGE) * 2)
        width = min(preferred_width, available_width)
        layout = self.layout()
        height_for_width = layout.heightForWidth(width) if layout is not None else -1
        height = height_for_width if height_for_width > 0 else self.sizeHint().height()
        self.resize(width, height)
        margin = int(Spacing.SECTION)
        self.move(
            max(margin, parent.width() - self.width() - margin),
            max(margin, parent.height() - self.height() - margin),
        )

    def _announce(self) -> None:
        try:
            event = QAccessibleEvent(self, QAccessible.Event.Alert)
            QAccessible.updateAccessibility(event)
        except (RuntimeError, TypeError):
            # Accessibility backends are optional at runtime; visual feedback still
            # works and the message remains available through accessible properties.
            return


__all__ = ["NotificationHost"]
