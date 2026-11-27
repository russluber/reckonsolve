"""One Settings tool and its visit-local, selectable result."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QBoxLayout, QLabel, QPushButton, QWidget

from reckonsolve.ui.components import ContentPanel, PersistentMessageLabel
from reckonsolve.ui.quantile_analytics import _label
from reckonsolve.ui.visual_system import (
    ActionRole,
    StatusTone,
    SurfaceRole,
    apply_action_role,
    apply_surface_role,
)


class SettingsActionRow(QBoxLayout):
    """Place a description and its action together across Settings layouts."""

    def __init__(self, description: QLabel, button: QPushButton) -> None:
        super().__init__(QBoxLayout.Direction.LeftToRight)
        self.description = description
        self.button = button
        self.setContentsMargins(0, 0, 0, 0)
        self.addWidget(description, 1)
        self.addWidget(button, 0, Qt.AlignmentFlag.AlignTop)

    def inline_width(self) -> int:
        # Leave space for a readable phrase before the action button.
        return (
            self.description.fontMetrics().horizontalAdvance("Complete SQLite backup")
            + self.button.sizeHint().width()
            + self.spacing()
        )

    def set_stacked(self, stacked: bool) -> None:
        direction = (
            QBoxLayout.Direction.TopToBottom
            if stacked
            else QBoxLayout.Direction.LeftToRight
        )
        if self.direction() == direction:
            return
        self.setDirection(direction)
        self.setAlignment(
            self.button,
            Qt.AlignmentFlag.AlignLeft if stacked else Qt.AlignmentFlag.AlignTop,
        )


class SettingsTool(ContentPanel):
    def __init__(
        self, title: str, description: str, action: str, name: str, parent: QWidget
    ) -> None:
        super().__init__(title, parent=parent)
        self.setObjectName(name + "Panel")
        apply_surface_role(self, SurfaceRole.CANVAS)
        self.button = QPushButton(action, self.body)
        self.button.setObjectName(name + "Button")
        apply_action_role(self.button, ActionRole.SECONDARY)
        self.action_row = SettingsActionRow(_label(description, self.body), self.button)
        self.body_layout.addLayout(self.action_row)
        self.result = PersistentMessageLabel(
            accessible_name=title + " result", parent=self.body
        )
        self.result.setObjectName(name + "Result")
        self.result.setWordWrap(True)
        self.result.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        self.body_layout.addWidget(self.result)
        self.date_renderer: Callable[[], str] | None = None

    def show_result(self, message: str, tone: StatusTone = StatusTone.SUCCESS) -> None:
        self.result.show_message(message, tone)

    def clear_result(self) -> None:
        self.date_renderer = None
        self.result.clear_message()
