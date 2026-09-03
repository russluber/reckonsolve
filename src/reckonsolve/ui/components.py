"""Small reusable presentation components for the desktop page grammar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.ui.visual_system import (
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_badge_role,
    apply_message_role,
    apply_surface_role,
    apply_text_role,
)


class PageHeader(QWidget):
    """Stable title, supporting-text, and optional action region for one page."""

    def __init__(
        self,
        title: str,
        supporting_text: str | None = None,
        *,
        title_object_name: str | None = None,
        supporting_object_name: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("pageHeader")

        heading = QWidget(self)
        heading_layout = QVBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(int(Spacing.COMPACT))

        self.title_label = QLabel(title, heading)
        if title_object_name:
            self.title_label.setObjectName(title_object_name)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(self.title_label, TextRole.PAGE_TITLE)
        heading_layout.addWidget(self.title_label)

        self.supporting_label = QLabel(supporting_text or "", heading)
        if supporting_object_name:
            self.supporting_label.setObjectName(supporting_object_name)
        self.supporting_label.setTextFormat(Qt.TextFormat.PlainText)
        self.supporting_label.setWordWrap(True)
        self.supporting_label.setHidden(not bool(supporting_text))
        apply_text_role(self.supporting_label, TextRole.SECONDARY)
        heading_layout.addWidget(self.supporting_label)

        self.action_region = QWidget(self)
        self.action_region.setObjectName("pageHeaderActions")
        self.action_layout = QHBoxLayout(self.action_region)
        self.action_layout.setContentsMargins(0, 0, 0, 0)
        self.action_layout.setSpacing(int(Spacing.CONTROL))
        self.action_region.setHidden(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.SECTION))
        layout.addWidget(heading, 1)
        layout.addWidget(self.action_region, 0, Qt.AlignmentFlag.AlignTop)

    def add_action(self, widget: QWidget) -> None:
        """Add a control without changing the stable heading geometry."""

        self.action_layout.addWidget(widget)
        self.action_region.setHidden(False)


class ContentPanel(QFrame):
    """A restrained raised panel with a consistent heading and body."""

    def __init__(
        self,
        title: str,
        supporting_text: str | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        apply_surface_role(self, SurfaceRole.RAISED)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
            int(Spacing.ORDINARY),
        )
        self._root_layout.setSpacing(int(Spacing.CONTROL))

        heading = QWidget(self)
        heading_layout = QHBoxLayout(heading)
        heading_layout.setContentsMargins(0, 0, 0, 0)
        heading_layout.setSpacing(int(Spacing.CONTROL))
        self.title_label = QLabel(title, heading)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(self.title_label, TextRole.SECTION_TITLE)
        heading_layout.addWidget(self.title_label)
        heading_layout.addStretch()
        self.count_badge = StatusBadge("0", StatusTone.NEUTRAL, parent=heading)
        self.count_badge.setHidden(True)
        heading_layout.addWidget(self.count_badge)
        self._root_layout.addWidget(heading)

        self.supporting_label = QLabel(supporting_text or "", self)
        self.supporting_label.setTextFormat(Qt.TextFormat.PlainText)
        self.supporting_label.setWordWrap(True)
        self.supporting_label.setHidden(not bool(supporting_text))
        apply_text_role(self.supporting_label, TextRole.SECONDARY)
        self._root_layout.addWidget(self.supporting_label)

        self.body = QWidget(self)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(int(Spacing.CONTROL))
        self._root_layout.addWidget(self.body)

    def set_count(self, value: int) -> None:
        self.count_badge.setText(str(value))
        self.count_badge.setAccessibleName(f"{value} items")
        self.count_badge.setHidden(False)


class StatusBadge(QLabel):
    """A compact textual badge whose meaning never relies on color."""

    def __init__(
        self,
        text: str,
        tone: StatusTone = StatusTone.NEUTRAL,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        apply_badge_role(self, tone)


class EmptyStateLabel(QLabel):
    """A quiet, explicit empty state that occupies the normal content region."""

    def __init__(self, text: str, *, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        apply_text_role(self, TextRole.SECONDARY)


class PersistentMessageLabel(QLabel):
    """An inline status or error that remains until its owning context clears it."""

    def __init__(
        self,
        *,
        accessible_name: str,
        tone: StatusTone = StatusTone.NEUTRAL,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._accessible_region_name = accessible_name
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setHidden(True)
        apply_message_role(
            self,
            tone,
            accessible_name=self._accessible_region_name,
        )

    def show_message(self, text: str, tone: StatusTone) -> None:
        self.setText(text)
        apply_message_role(
            self,
            tone,
            accessible_name=self._accessible_region_name,
        )
        self.setHidden(False)

    def clear_message(self) -> None:
        self.clear()
        self.setHidden(True)


__all__ = [
    "ContentPanel",
    "EmptyStateLabel",
    "PageHeader",
    "PersistentMessageLabel",
    "StatusBadge",
]
