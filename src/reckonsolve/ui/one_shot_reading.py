"""Ruled reading sections for a completed One-Shot exercise, without card chrome."""

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from reckonsolve.ui.components import SectionRule
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


class OneShotReadingSection(QWidget):
    """Keep a subsection heading, its content and its ending rule together."""

    def __init__(self, title: str, parent: QWidget, *, end_rule: bool = True) -> None:
        super().__init__(parent)
        self._height_timer = QTimer(self)
        self._height_timer.setSingleShot(True)
        self._height_timer.timeout.connect(self._fit_height)
        self.setMinimumWidth(0)
        column = QVBoxLayout(self)
        column.setContentsMargins(0, int(Spacing.SECTION), 0, 0)
        column.setSpacing(int(Spacing.CONTROL))
        self.title_label = QLabel(title, self)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(0)
        self.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        apply_text_role(self.title_label, TextRole.DETAIL_EVENT)
        column.addWidget(self.title_label)
        self.body = QWidget(self)
        self.body.setMinimumWidth(0)
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(int(Spacing.CONTROL))
        column.addWidget(self.body)
        if end_rule:
            column.addSpacing(int(Spacing.ORDINARY))
            column.addWidget(SectionRule(self))

    def event(self, event: QEvent) -> bool:
        result = super().event(event)
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.Resize):
            timer = getattr(self, "_height_timer", None)
            if timer is not None and not timer.isActive():
                timer.start(0)
        return result

    def _fit_height(self) -> None:
        # Wait for nested editor/layout events to settle before changing the
        # minimum: synchronous resizing here can reenter the parent layout.
        # The child-owned timer also cancels pending work on destruction.
        height = self.layout().minimumHeightForWidth(self.width())
        if height != self.minimumHeight():
            self.setMinimumHeight(height)


def finish_disclosure(section: QWidget, *, end_rule: bool = True) -> QWidget:
    """Separate an existing native disclosure without changing its target or behavior."""
    column = section.layout()
    column.setContentsMargins(0, int(Spacing.ORDINARY), 0, 0)
    if end_rule:
        column.addSpacing(int(Spacing.ORDINARY))
        column.addWidget(SectionRule(section))
    _DisclosureCaption(section)
    return section


class _DisclosureCaption(QObject):
    """Wrap a native disclosure's complete caption when the reading pane is narrow."""

    def __init__(self, section: QWidget) -> None:
        super().__init__(section)
        self.section = section
        # The unwrapped caption must not force the scroll body wider before the
        # section receives its actual available width and can wrap the button.
        section.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.button = section.disclosure_button
        self.caption = self.button.accessibleName()
        self.button.toggled.connect(self._wrap_caption)
        section.installEventFilter(self)
        self.button.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if (watched is self.section and event.type() == QEvent.Type.Resize) or (
            watched is self.button
            and event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange)
        ):
            self._wrap_caption()
        return super().eventFilter(watched, event)

    def _wrap_caption(self, *_args) -> None:
        caption = self.button.property("reckonsolveDisclosureCaption") or self.caption
        metrics = self.button.fontMetrics()
        current_width = max(
            metrics.horizontalAdvance(line.replace("&&", "&"))
            for line in self.button.text().split("\n")
        )
        chrome = self.button.sizeHint().width() - current_width
        available = max(1, self.section.width() - chrome)
        lines = [""]
        for word in caption.split():
            candidate = (lines[-1] + " " + word).strip()
            if lines[-1] and metrics.horizontalAdvance(candidate) > available:
                lines.append(word)
            else:
                lines[-1] = candidate
        text = "\n".join(lines).replace("&", "&&")
        if text != self.button.text():
            self.button.setText(text)
