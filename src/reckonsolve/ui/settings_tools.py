"""One Settings tool and its visit-local, selectable result."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from reckonsolve.ui.components import ContentPanel, PersistentMessageLabel
from reckonsolve.ui.quantile_analytics import _label
from reckonsolve.ui.visual_system import (
    ActionRole,
    StatusTone,
    SurfaceRole,
    apply_action_role,
    apply_surface_role,
)


class SettingsTool(ContentPanel):
    def __init__(
        self, title: str, description: str, action: str, name: str, parent: QWidget
    ) -> None:
        super().__init__(title, parent=parent)
        self.setObjectName(name + "Panel")
        apply_surface_role(self, SurfaceRole.CANVAS)
        row = QHBoxLayout()
        row.addWidget(_label(description, self.body), 1)
        self.button = QPushButton(action, self.body)
        self.button.setObjectName(name + "Button")
        apply_action_role(self.button, ActionRole.SECONDARY)
        row.addWidget(self.button, 0, Qt.AlignmentFlag.AlignTop)
        self.body_layout.addLayout(row)
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

    def show_result(self, message: str, tone: StatusTone = StatusTone.SUCCESS) -> None:
        self.result.show_message(message, tone)

    def clear_result(self) -> None:
        self.result.clear_message()
