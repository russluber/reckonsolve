"""Small reusable presentation components for the desktop page grammar."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_badge_role,
    apply_message_role,
    apply_surface_role,
    apply_text_role,
)


class SectionRule(QFrame):
    """A palette-aware structural separator with no interactive behavior."""

    def __init__(self, parent: QWidget, *, vertical: bool = False) -> None:
        super().__init__(parent)
        self.setProperty("reckonsolveRule", "vertical" if vertical else "horizontal")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        if vertical:
            self.setFixedWidth(1)
        else:
            self.setFixedHeight(1)


class _TagChip(QLabel):
    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        # Long tag names may wrap without forcing a wider metadata row.
        hint.setWidth(0)
        return hint


class TagChips(QWidget):
    """Selectable, noninteractive tag names in a naturally wrapping group."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.names: tuple[str, ...] = ()
        self.chips: list[QLabel] = []
        self.flow = FlowLayout(self)
        self.setMinimumWidth(0)
        self.hide()

    def set_tags(self, names: tuple[str, ...]) -> None:
        if names == self.names:
            return
        self.flow.clear_widgets()
        self.names, self.chips = tuple(names), []
        for name in self.names:
            chip = _TagChip(name, self)
            chip.setTextFormat(Qt.TextFormat.PlainText)
            chip.setWordWrap(True)
            chip.setMinimumWidth(0)
            chip.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            chip.setProperty("reckonsolveTagChip", "true")
            apply_text_role(chip, TextRole.SECONDARY)
            self.chips.append(chip)
            self.flow.addWidget(chip)
        self.setAccessibleName("Tags: " + ", ".join(self.names))
        self.setVisible(bool(self.names))
        self.updateGeometry()

    def clear(self) -> None:
        self.set_tags(())

    def sizeHint(self) -> QSize:
        sizes = [chip.sizeHint() for chip in self.chips]
        return QSize(
            sum(size.width() for size in sizes)
            + max(0, len(sizes) - 1) * self.flow.spacing(),
            max((size.height() for size in sizes), default=0),
        )

    def minimumSizeHint(self) -> QSize:
        return QSize(0, self.flow.minimumSize().height())


class ProbabilityInput(QSpinBox):
    """Native percentage entry with quiet, separately clickable minus/plus steps."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("reckonsolveProbabilityInput", "true")
        self.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.decrease_button = self._step_button("−", "Decrease", -1)
        self.increase_button = self._step_button("+", "Increase", 1)
        self.valueChanged.connect(self._sync_steps)
        self._sync_steps()
        self._place_steps()

    def _step_button(self, symbol: str, name: str, step: int) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName("probability" + name)
        button.setText(symbol)
        button.setAccessibleName(name + " probability")
        button.setToolTip(name + " probability by 1 percentage point")
        button.setProperty("reckonsolveProbabilityStep", "true")
        button.setAutoRaise(True)
        button.setAutoRepeat(True)
        # Up/Down already provides the keyboard path on the native editor.
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(lambda: self._step(step))
        return button

    def _step(self, amount: int) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self.stepBy(amount)

    def _step_width(self) -> int:
        return max(28, self.fontMetrics().height() + 8)

    def _reserved_width(self) -> int:
        return 2 * self._step_width() + 10

    def _place_steps(self) -> None:
        width = self._step_width()
        x = self.width() - width - 4
        height = max(1, self.height() - 8)
        self.increase_button.setGeometry(x, 4, width, height)
        self.decrease_button.setGeometry(x - width - 2, 4, width, height)
        self.lineEdit().setTextMargins(0, 0, self._reserved_width(), 0)
        glyph_font = QFont(self.font())
        glyph_font.setPointSizeF(max(1, self.font().pointSizeF()) + 3)
        glyph_font.setWeight(QFont.Weight.DemiBold)
        for button in (self.decrease_button, self.increase_button):
            if button.font() != glyph_font:
                button.setFont(glyph_font)
        self.decrease_button.raise_()
        self.increase_button.raise_()

    def _sync_steps(self) -> None:
        enabled = self.isEnabled() and not self.isReadOnly()
        self.decrease_button.setEnabled(enabled and self.value() > self.minimum())
        self.increase_button.setEnabled(enabled and self.value() < self.maximum())

    def setReadOnly(self, read_only: bool) -> None:
        super().setReadOnly(read_only)
        self._sync_steps()

    def sizeHint(self) -> QSize:
        return super().sizeHint() + QSize(self._reserved_width(), 0)

    def minimumSizeHint(self) -> QSize:
        return super().minimumSizeHint() + QSize(self._reserved_width(), 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "increase_button"):
            self._place_steps()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if hasattr(self, "increase_button") and event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.EnabledChange,
        ):
            self._place_steps()
            self._sync_steps()
            self.updateGeometry()


class ProbabilityPresets(QWidget):
    """Direct-entry Binary shortcuts, optionally wrapping in a contextual editor."""

    def __init__(
        self,
        editor: QSpinBox,
        parent: QWidget,
        *,
        name_prefix: str = "probability",
        wrap: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(f"{name_prefix}Shortcuts")
        layout = FlowLayout(self) if wrap else QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.COMPACT))
        for value in range(10, 100, 10):
            button = QPushButton(str(value), self)
            button.setObjectName(f"{name_prefix}Shortcut{value}")
            button.setProperty("reckonsolveProbabilityPreset", "true")
            button.setAccessibleName(f"Set probability to {value}%")
            apply_action_role(button, ActionRole.QUIET)
            button.clicked.connect(
                lambda _checked=False, probability=value: editor.setValue(probability)
            )
            layout.addWidget(button)
        if isinstance(layout, QHBoxLayout):
            layout.addStretch()


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
        content_spacing: Spacing = Spacing.CONTROL,
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
        self._root_layout.setSpacing(int(content_spacing))

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
        heading.setHidden(not bool(title))
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
    "ProbabilityInput",
    "ProbabilityPresets",
    "StatusBadge",
]
