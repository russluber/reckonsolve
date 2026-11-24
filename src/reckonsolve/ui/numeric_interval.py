"""Exact committed quantile labels above a proportional interval display."""

from fractions import Fraction

from PySide6.QtCore import QEvent, QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from reckonsolve.domain.predictions import FixedPrecisionValue
from reckonsolve.domain.quantiles import FiveQuantiles, quantile_summary
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.visual_system import TextRole, apply_text_role, semantic_colors


class IntervalLegend(QWidget):
    """Text and matching stroke shapes explain the committed interval display."""

    def __init__(self, parent: QWidget, *, checked_answer: bool = False) -> None:
        super().__init__(parent)
        self.setObjectName("numericIntervalLegend")
        self.setAccessibleName(
            "Numeric interval legend: thin line for 90% interval, thick line for 50% interval, vertical mark for median"
        )
        layout = FlowLayout(self)
        entries = (
            ("outer", "90% interval"),
            ("inner", "50% interval"),
            ("median", "Median"),
        ) + ((("actual", "Checked Answer"),) if checked_answer else ())
        if checked_answer:
            self.setAccessibleName(
                self.accessibleName() + ", gold diamond for checked answer"
            )
        for kind, title in entries:
            group = QWidget(self)
            row = QHBoxLayout(group)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(4)
            row.addWidget(_LegendSwatch(kind, group))
            label = QLabel(title, group)
            apply_text_role(label, TextRole.SECONDARY)
            row.addWidget(label)
            layout.addWidget(group)

    def sizeHint(self) -> QSize:
        layout = self.layout()
        sizes = [layout.itemAt(index).sizeHint() for index in range(layout.count())]
        return QSize(
            sum(size.width() for size in sizes)
            + max(0, len(sizes) - 1) * layout.spacing(),
            max((size.height() for size in sizes), default=0),
        )


class _LegendSwatch(QWidget):
    def __init__(self, kind: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setObjectName("intervalLegend" + kind.title())
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(20, max(18, self.fontMetrics().height()))

    def paintEvent(self, event) -> None:
        colors = semantic_colors(self.window().palette())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(
                QColor(colors.text if self.kind == "median" else colors.accent),
                9 if self.kind == "inner" else 3,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.FlatCap,
            )
        )
        if self.kind == "actual":
            x, y = self.width() / 2, self.height() / 2
            painter.setPen(QPen(QColor(colors.actual_outline), 1.25))
            painter.setBrush(QColor(colors.actual_fill))
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(x, y - 5),
                        QPointF(x + 5, y),
                        QPointF(x, y + 5),
                        QPointF(x - 5, y),
                    ]
                )
            )
        elif self.kind == "median":
            x = self.width() / 2
            painter.drawLine(QPointF(x, 3), QPointF(x, self.height() - 3))
        else:
            y = self.height() / 2
            painter.drawLine(QPointF(1, y), QPointF(self.width() - 1, y))
        painter.end()


class NumericInterval(QWidget):
    """Move crowded labels, never the exact forecast marks they describe."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._metrics_timer = QTimer(self)
        self._metrics_timer.setSingleShot(True)
        self._metrics_timer.timeout.connect(self._refresh_metrics)
        self.setObjectName("committedNumericInterval")
        self.setAccessibleName("Current committed five-percentile forecast")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.quantiles: FiveQuantiles | None = None
        self.actual: FixedPrecisionValue | None = None
        self.actual_position: float | None = None
        self.actual_label = QLabel(self)
        self.actual_label.setObjectName("numericHeaderCheckedAnswer")
        self.actual_label.setWordWrap(True)
        self.actual_label.setTextFormat(Qt.TextFormat.PlainText)
        self.actual_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        apply_text_role(self.actual_label, TextRole.LABEL)
        self.actual_label.hide()
        self.unit = ""
        self.labels: list[QLabel] = []
        self.positions: list[float] = []
        self.connectors: list[tuple[QPointF, QPointF]] = []
        self._line_y = 70
        self._needed_height = 120

    def set_forecast(
        self,
        quantiles: FiveQuantiles,
        unit: str,
        *,
        actual: FixedPrecisionValue | None = None,
    ) -> None:
        self.quantiles, self.unit = quantiles, unit
        self.actual = actual
        self.actual_label.setText(
            f"Checked Answer: {actual} {unit}".rstrip() if actual is not None else ""
        )
        self.actual_label.setVisible(actual is not None)
        for label in self.labels:
            label.hide()
            label.deleteLater()
        self.labels.clear()
        groups: dict[int, tuple[str, list[str]]] = {}
        for level, value in zip((5, 25, 50, 75, 95), quantiles.values, strict=True):
            name = f"{level}th" + (" · Median" if level == 50 else "")
            if value.scaled_value not in groups:
                groups[value.scaled_value] = (str(value), [])
            groups[value.scaled_value][1].append(name)
        for value, roles in groups.values():
            label = QLabel(value + "\n" + " · ".join(roles), self)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            label.setIndent(0)
            apply_text_role(label, TextRole.LABEL)
            self.labels.append(label)
            label.installEventFilter(self)
            label.show()
        self.setAccessibleDescription(
            quantile_summary(quantiles, unit)
            + (
                f". Gold diamond: checked answer {actual} {unit}."
                if actual is not None
                else ""
            )
        )
        self._arrange()
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(620, self._needed_height)

    def minimumSizeHint(self) -> QSize:
        return QSize(220, self._needed_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._arrange()

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.StyleChange,
        ):
            self._queue_metrics_refresh()

    def eventFilter(self, watched, event) -> bool:
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._queue_metrics_refresh()
        return super().eventFilter(watched, event)

    def _queue_metrics_refresh(self) -> None:
        if not self._metrics_timer.isActive():
            # Styles can change child label metrics without resizing us.
            # Ownership cancels the queued work if this interval is destroyed.
            self._metrics_timer.start(0)

    def _refresh_metrics(self) -> None:
        self._arrange()
        self.updateGeometry()
        self.update()

    def _arrange(self) -> None:
        if self.quantiles is None:
            return
        values = [value.scaled_value for value in self.quantiles.values]
        # An outside answer extends only the display scale. The forecast bands
        # still end at their elicited percentiles; no tail shape is drawn.
        scale_values = values + (
            [self.actual.scaled_value] if self.actual is not None else []
        )
        low, high = min(scale_values), max(scale_values)
        span = high - low
        left, right = 24.0, max(25.0, self.width() - 24.0)
        self.positions = [
            left + (right - left) * float(Fraction(value - low, span))
            if span
            else self.width() / 2
            for value in values
        ]
        distinct = list(dict.fromkeys(zip(values, self.positions, strict=True)))
        widths = [
            min(
                max(
                    48,
                    max(
                        label.fontMetrics().horizontalAdvance(line)
                        for line in label.text().splitlines()
                    )
                    + 8,
                ),
                max(80, self.width() - 8),
            )
            for label in self.labels
        ]
        # Greedy rows preserve all labels even for extreme exact values. Within
        # each row, forward/backward placement separates labels; leaders retain
        # their true proportional anchors, including subpixel inner intervals.
        rows: list[list[int]] = [[]]
        used = 0
        for index, width in enumerate(widths):
            if rows[-1] and used + width + 12 > self.width() - 8:
                rows.append([])
                used = 0
            rows[-1].append(index)
            used += width + 12
        self.connectors.clear()
        top = 0
        placements = []
        for row in rows:
            starts = []
            previous = 4.0
            height = max(max(38, self.labels[i].heightForWidth(widths[i])) for i in row)
            for index in row:
                desired = distinct[index][1] - widths[index] / 2
                start = max(previous, min(desired, self.width() - widths[index] - 4))
                starts.append(start)
                previous = start + widths[index] + 12
            boundary = self.width() - 4.0
            for offset in range(len(row) - 1, -1, -1):
                index = row[offset]
                starts[offset] = min(starts[offset], boundary - widths[index])
                boundary = starts[offset] - 12
            for index, start in zip(row, starts, strict=True):
                label = self.labels[index]
                label.setGeometry(round(start), top, widths[index], height)
                placements.append(
                    (start + widths[index] / 2, top + height, distinct[index][1])
                )
            top += height + 5
        self._line_y = top + 20
        self.connectors = [
            (QPointF(center, bottom + 2), QPointF(anchor, self._line_y - 9))
            for center, bottom, anchor in placements
        ]
        needed = self._line_y + 28
        self.actual_position = None
        if self.actual is not None:
            self.actual_position = (
                left
                + (right - left) * float(Fraction(self.actual.scaled_value - low, span))
                if span
                else self.width() / 2
            )
            label_width = max(1, self.width() - 8)
            label_height = self.actual_label.heightForWidth(label_width)
            self.actual_label.setGeometry(4, needed, label_width, label_height)
            needed += label_height + 4
        if needed != self._needed_height:
            self._needed_height = needed
            self.setMinimumHeight(needed)
            self.updateGeometry()

    def paintEvent(self, event) -> None:
        if self.quantiles is None:
            return
        colors = semantic_colors(self.window().palette())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(colors.secondary_text), 1))
        for start, end in self.connectors:
            painter.drawLine(start, end)
        y = float(self._line_y)
        painter.setPen(QPen(QColor(colors.accent), 3))
        painter.drawLine(QPointF(self.positions[0], y), QPointF(self.positions[-1], y))
        painter.setPen(QPen(QColor(colors.accent), 9))
        painter.drawLine(QPointF(self.positions[1], y), QPointF(self.positions[3], y))
        for index, x in enumerate(self.positions):
            painter.setPen(
                QPen(
                    QColor(colors.text if index == 2 else colors.accent),
                    3 if index == 2 else 1.5,
                )
            )
            height = 15 if index == 2 else 9
            painter.drawLine(QPointF(x, y - height), QPointF(x, y + height))
        if self.actual_position is not None:
            x, center = self.actual_position, y + 19
            painter.setPen(QPen(QColor(colors.actual_outline), 1.25))
            painter.setBrush(QColor(colors.actual_fill))
            # Below the band, the diamond cannot hide a tied median/percentile.
            painter.drawLine(QPointF(x, y + 10), QPointF(x, center - 5))
            painter.drawPolygon(
                QPolygonF(
                    [
                        QPointF(x, center - 5),
                        QPointF(x + 5, center),
                        QPointF(x, center + 5),
                        QPointF(x - 5, center),
                    ]
                )
            )
        painter.end()
