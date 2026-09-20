"""Shared presentation-only metric rows and responsive plot/table pairs."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor, QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from .components import ContentPanel
from .visual_system import (
    Spacing,
    SurfaceRole,
    TextRole,
    apply_surface_role,
    apply_text_role,
    semantic_colors,
)


class AnalyticsPanel(ContentPanel):
    """An Analytics card with explanations on demand, not repeated subtitles."""

    def __init__(
        self,
        title: str,
        explanation: str | None = None,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent=parent)
        self.setAccessibleName(title)
        self.set_help_text(explanation or "")

    def set_help_text(self, text: str) -> None:
        self.title_label.setToolTip(text)
        self.title_label.setAccessibleDescription(text)
        self.setAccessibleDescription(text)


def _new_summary_metric(
    caption: str,
    *,
    value_object_name: str,
    parent: QWidget,
) -> tuple[QWidget, QLabel]:
    """Build one compact caption/value pair for an analytical headline."""

    metric = QWidget(parent)
    metric.setObjectName(f"{value_object_name}Metric")
    layout = QVBoxLayout(metric)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(int(Spacing.COMPACT))
    caption_label = QLabel(caption, metric)
    caption_label.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(caption_label, TextRole.SECONDARY)
    value = QLabel("Loading...", metric)
    value.setObjectName(value_object_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    value.setWordWrap(True)
    apply_text_role(value, TextRole.FORECAST)
    layout.addWidget(caption_label)
    layout.addWidget(value)
    return metric, value


def _new_update_metric(
    caption: str,
    *,
    value_object_name: str,
    parent: QWidget,
) -> tuple[QFrame, QLabel]:
    """Build one bordered retrospective metric that remains meaningful as text."""

    metric = QFrame(parent)
    metric.setObjectName(f"{value_object_name}Metric")
    apply_surface_role(metric, SurfaceRole.BASE)
    metric.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    layout = QVBoxLayout(metric)
    layout.setContentsMargins(
        int(Spacing.ORDINARY),
        int(Spacing.CONTROL),
        int(Spacing.ORDINARY),
        int(Spacing.CONTROL),
    )
    layout.setSpacing(int(Spacing.COMPACT))
    caption_label = QLabel(caption, metric)
    caption_label.setTextFormat(Qt.TextFormat.PlainText)
    caption_label.setWordWrap(True)
    apply_text_role(caption_label, TextRole.SECONDARY)
    value = QLabel("Loading...", metric)
    value.setObjectName(value_object_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    value.setWordWrap(True)
    value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    apply_text_role(value, TextRole.SECTION_TITLE)
    layout.addWidget(caption_label)
    layout.addWidget(value)
    return metric, value


class CompactMetricGroup(QWidget):
    """A flat, top-aligned set of label/value rows, without nested metric cards."""

    def __init__(self, title: str, *, parent: QWidget) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        heading = QLabel(title, self)
        apply_text_role(heading, TextRole.SECTION_TITLE)
        layout.addWidget(heading)
        self._rows = QGridLayout()
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setHorizontalSpacing(int(Spacing.CONTROL))
        self._rows.setVerticalSpacing(int(Spacing.COMPACT))
        # Extra width stays after the values, not between captions and values.
        self._rows.setColumnStretch(2, 1)
        layout.addLayout(self._rows)

    def add_metric(
        self, caption: str, object_name: str, *, primary: bool = False
    ) -> QLabel:
        row = self._rows.rowCount()
        label = QLabel(caption, self)
        label.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(label, TextRole.SECONDARY)
        value = QLabel("Loading...", self)
        value.setObjectName(object_name)
        value.setTextFormat(Qt.TextFormat.PlainText)
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        apply_text_role(value, TextRole.FORECAST if primary else TextRole.SECTION_TITLE)
        self._rows.addWidget(label, row, 0)
        self._rows.addWidget(value, row, 1, Qt.AlignmentFlag.AlignRight)
        return value


class _ResponsiveMetricRow(QWidget):
    """Keep summary metrics horizontal until their captions would crowd."""

    def __init__(
        self,
        metrics: tuple[QWidget, ...],
        *,
        stack_below: int,
        object_name: str,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._stack_below = stack_below
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(int(Spacing.SECTION))
        for metric in metrics:
            self._layout.addWidget(metric, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        direction = (
            QBoxLayout.Direction.LeftToRight
            if event.size().width() >= self._stack_below
            else QBoxLayout.Direction.TopToBottom
        )
        if self._layout.direction() != direction:
            self._layout.setDirection(direction)


class _ResponsiveChartTable(QWidget):
    """Pair a plot and its text table when both retain a useful width."""

    def __init__(
        self,
        chart: QWidget,
        table: QTableWidget,
        *,
        object_name: str,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._chart = chart
        self._table = table
        for widget in (chart, table):
            policy = widget.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            widget.setSizePolicy(policy)
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(int(Spacing.SECTION))
        self._layout.addWidget(chart)
        self._layout.addWidget(table)
        self._synchronize_surfaces()
        self._fit_table_height()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.StyleChange,
        ):
            self._synchronize_surfaces()
            self._fit_table_height()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        side_by_side = event.size().width() >= 1100
        direction = (
            QBoxLayout.Direction.LeftToRight
            if side_by_side
            else QBoxLayout.Direction.TopToBottom
        )
        if self._layout.direction() != direction:
            self._layout.setDirection(direction)
        self._layout.setStretch(0, 1 if side_by_side else 0)
        self._layout.setStretch(1, 1 if side_by_side else 0)
        self._fit_table_height()

    def _synchronize_surfaces(self) -> None:
        surface = QColor(semantic_colors(self.palette()).raised)
        for widget in (self._chart, self._table, self._table.viewport()):
            palette = widget.palette()
            palette.setColor(QPalette.ColorRole.Base, surface)
            palette.setColor(QPalette.ColorRole.AlternateBase, surface)
            widget.setPalette(palette)

    def _fit_table_height(self) -> None:
        self._table.resizeRowsToContents()
        content_height = (
            self._table.horizontalHeader().height()
            + sum(self._table.rowHeight(row) for row in range(self._table.rowCount()))
            + (2 * self._table.frameWidth())
            + 2
        )
        self._table.setFixedHeight(content_height)
