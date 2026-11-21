"""Inline read-only history controls with bounded native height reconciliation."""

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from reckonsolve.ui.detail_workspace import collapse_section
from reckonsolve.ui.one_shot_reading import finish_disclosure
from reckonsolve.ui.visual_system import TextRole, apply_text_role


def _minimum_height(widget: QWidget) -> int:
    layout = widget.layout()
    # Qt returns -1 when a height-for-width measurement is unavailable, as with
    # empty/hidden startup content. Use the layout's natural minimum in that case.
    return max(
        0, layout.minimumSize().height(), layout.minimumHeightForWidth(widget.width())
    )


def history_disclosure(title: str, object_name: str, parent: QWidget) -> QWidget:
    content = QWidget(parent)
    content.setObjectName(f"{object_name}Content")
    column = QVBoxLayout(content)
    column.setContentsMargins(0, 0, 0, 0)
    group = finish_disclosure(
        collapse_section(content, title, text_link=True), end_rule=False
    )
    group.setObjectName(object_name)
    group.disclosure_count = QLabel(group)
    group.disclosure_count.setWordWrap(True)
    apply_text_role(group.disclosure_count, TextRole.DETAIL_TIME)
    group.layout().insertWidget(1, group.disclosure_count)
    _HistoryHeight(group)
    group.hide()
    return group


class _HistoryHeight(QObject):
    """Propagate expanded row heights through the retained outer Timeline row."""

    def __init__(self, group: QWidget) -> None:
        super().__init__(group)
        self.group = group
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fit)
        group.installEventFilter(self)
        group.disclosure_body.installEventFilter(self)
        group.disclosure_button.toggled.connect(self._schedule)

    def _schedule(self, *_args) -> None:
        if not self.timer.isActive():
            self.timer.start(0)

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self._schedule()
        return super().eventFilter(watched, event)

    def _fit(self) -> None:
        body = self.group.disclosure_body
        if not body.isHidden():
            height = _minimum_height(body)
            if height != body.minimumHeight():
                body.setMinimumHeight(height)
        height = _minimum_height(self.group)
        if height != self.group.minimumHeight():
            self.group.setMinimumHeight(height)
