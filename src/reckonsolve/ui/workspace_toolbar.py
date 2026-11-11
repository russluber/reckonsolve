"""One compact toolbar, with page-appropriate actions and no navigation stack."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QPushButton, QWidget

from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.visual_system import (
    ActionRole,
    TextRole,
    apply_action_role,
    apply_text_role,
)
from reckonsolve.ui.workspace_state import Route


class AppearanceButton(QPushButton):
    """A mouse display adjustment preserves the editor's native selection/focus."""

    def mousePressEvent(self, event) -> None:
        self._editor_focus = QApplication.focusWidget()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        previous = getattr(self, "_editor_focus", None)
        super().mouseReleaseEvent(event)
        if previous is not None and previous is not self:
            QTimer.singleShot(
                0, lambda: previous.setFocus(Qt.FocusReason.OtherFocusReason)
            )


class WorkspaceToolbar(QWidget):
    back_requested = Signal()
    journal_requested = Signal()
    new_requested = Signal()
    performance_requested = Signal()
    settings_requested = Signal()
    appearance_requested = Signal()

    def __init__(self, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("workspaceToolbar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        identity = QLabel(title, self)
        apply_text_role(identity, TextRole.SECTION_TITLE)
        layout.addWidget(identity)
        self.back = self._button(
            "", "workspaceBack", self.back_requested, LucideIcon.ARROW_LEFT
        )
        self.home = self._button("Journal", "journalHomeButton", self.journal_requested)
        layout.addWidget(self.back)
        layout.addWidget(self.home)
        self.new = self._button(
            "+ New", "newPredictionNavigationButton", self.new_requested
        )
        apply_action_role(self.new, ActionRole.PRIMARY)
        self.new.setToolTip("New Prediction (Ctrl+N)")
        layout.addWidget(self.new)
        layout.addStretch()
        self.performance = self._button(
            "",
            "performanceNavigationButton",
            self.performance_requested,
            LucideIcon.CHART,
        )
        self.performance.setAccessibleName("Performance")
        self.performance.setToolTip("Performance")
        self.appearance = AppearanceButton(self)
        self.appearance.setObjectName("appearanceToggle")
        self.appearance.setAccessibleName("Change appearance")
        apply_action_role(self.appearance, ActionRole.QUIET)
        self.appearance.clicked.connect(self.appearance_requested)
        self.settings = self._button(
            "", "settingsNavigationButton", self.settings_requested, LucideIcon.SETTINGS
        )
        self.settings.setAccessibleName("Settings")
        self.settings.setToolTip("Settings (Ctrl+,)")
        for button in (self.performance, self.appearance, self.settings):
            layout.addWidget(button)

    def _button(self, text, name, signal, icon=None):
        button = QPushButton(text, self)
        button.setObjectName(name)
        button.setAccessibleName(
            text or ("Settings" if name == "settingsNavigationButton" else "Back")
        )
        apply_action_role(button, ActionRole.QUIET)
        if icon:
            apply_lucide_icon(button, icon)
        button.clicked.connect(signal)
        return button

    def update_route(self, route: Route, back: str, *, separate_home: bool) -> None:
        self.back.setText(back)
        self.back.setAccessibleName(back)
        self.back.setVisible(route is not Route.JOURNAL)
        self.home.setVisible(separate_home)
        self.new.setVisible(route in (Route.JOURNAL, Route.DETAIL, Route.PERFORMANCE))
        self.performance.setVisible(route in (Route.JOURNAL, Route.DETAIL))
        self.settings.setVisible(
            route in (Route.JOURNAL, Route.DETAIL, Route.PERFORMANCE)
        )

    def update_appearance(self, dark: bool) -> None:
        action = "Switch to light mode" if dark else "Switch to dark mode"
        self.appearance.setText("")
        apply_lucide_icon(self.appearance, LucideIcon.SUN if dark else LucideIcon.MOON)
        self.appearance.setAccessibleName(action)
        self.appearance.setToolTip(action)
