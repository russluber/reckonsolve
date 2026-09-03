"""Native interval-band rendering for one Numeric Prediction's history."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from PySide6.QtCore import QEvent, QLineF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from reckonsolve.ui.visual_system import SemanticColors, semantic_colors


class NumericRevisionLike(Protocol):
    revision_id: int
    sequence: int
    lower_bound: object
    median_estimate: object
    upper_bound: object
    confidence_percent: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class NumericHistorySample:
    revision_id: int
    sequence: int
    lower_bound: float
    median_estimate: float
    upper_bound: float
    confidence_percent: int
    created_at: datetime


class NumericHistoryChart(QWidget):
    """Paint an interval band and median markers from immutable revisions."""

    _HISTORICAL_RADIUS = 4.0
    _CURRENT_RADIUS = 5.5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._samples: tuple[NumericHistorySample, ...] = ()
        self.setObjectName("numericHistoryChart")
        self.setAccessibleName("Numeric interval history chart")
        self.setAccessibleDescription("No Numeric ForecastRevisions are available.")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    @property
    def samples(self) -> tuple[NumericHistorySample, ...]:
        return self._samples

    def set_revisions(self, revisions: Iterable[NumericRevisionLike]) -> None:
        samples = tuple(
            sorted(
                (
                    NumericHistorySample(
                        revision_id=item.revision_id,
                        sequence=item.sequence,
                        # FixedPrecisionValue deliberately does not expose a
                        # float conversion: persistence and application logic
                        # must retain its exact base-ten representation.  This
                        # widget only needs display coordinates, so make that
                        # lossy conversion at this presentation boundary.
                        lower_bound=float(str(item.lower_bound)),
                        median_estimate=float(str(item.median_estimate)),
                        upper_bound=float(str(item.upper_bound)),
                        confidence_percent=item.confidence_percent,
                        created_at=item.created_at,
                    )
                    for item in revisions
                ),
                key=lambda item: item.sequence,
            )
        )
        if len({item.sequence for item in samples}) != len(samples):
            raise ValueError("Numeric revision sequences must be unique.")
        self._samples = samples
        self.setAccessibleDescription(_summary(samples))
        self.update()

    def clear(self) -> None:
        self.set_revisions(())

    def sizeHint(self) -> QSize:
        minimum = self.minimumSizeHint()
        return QSize(max(640, minimum.width()), max(280, minimum.height()))

    def minimumSizeHint(self) -> QSize:
        left, top, right, bottom = self._chart_margins()
        return QSize(
            max(320, round(left + right + 200.0)),
            max(220, round(top + bottom + 100.0)),
        )

    def changeEvent(self, event: QEvent) -> None:
        """Recalculate chart layout after theme, style, or font changes."""

        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
        ):
            self.updateGeometry()
            self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        colors = semantic_colors(palette)
        painter.fillRect(self.rect(), QColor(colors.surface))
        rect = self._plot_rect()
        low, high = _value_range(self._samples)
        self._paint_axes(painter, colors, rect, low=low, high=high)
        if not self._samples:
            return
        xs, lower, median, upper = _coordinates(self._samples, rect)
        self._paint_interval(painter, colors, xs, lower, upper)
        self._paint_medians(painter, colors, rect, xs, median)
        self._paint_time_labels(painter, colors, rect)

    def _plot_rect(self) -> QRectF:
        left, top, right, bottom = self._chart_margins()
        return QRectF(
            left,
            top,
            max(1.0, self.width() - left - right),
            max(1.0, self.height() - top - bottom),
        )

    def _chart_margins(self) -> tuple[float, float, float, float]:
        low, high = _value_range(self._samples)
        metrics = self.fontMetrics()
        tick_width = max(
            metrics.horizontalAdvance(_format_axis_value(value))
            for value in _axis_ticks(low, high)
        )
        left = metrics.height() + tick_width + 28.0
        top = metrics.height() / 2 + self._CURRENT_RADIUS + 6.0
        right = self._CURRENT_RADIUS + 14.0
        bottom = metrics.height() * 2 + 18.0
        return left, top, right, bottom

    def _paint_axes(
        self,
        painter: QPainter,
        colors: SemanticColors,
        rect: QRectF,
        *,
        low: float,
        high: float,
    ) -> None:
        axis_color = QColor(colors.text)
        grid_color = QColor(colors.border)
        grid_color.setAlpha(100)
        metrics = painter.fontMetrics()
        title_band_width = metrics.height() + 8.0
        tick_label_left = title_band_width
        tick_label_width = max(1.0, rect.left() - tick_label_left - 8.0)

        painter.setPen(QPen(grid_color, 1.0))
        ticks = _axis_ticks(low, high)
        for index, value in enumerate(ticks):
            y = rect.bottom() - index / (len(ticks) - 1) * rect.height()
            painter.drawLine(QLineF(rect.left(), y, rect.right(), y))
            painter.setPen(QPen(axis_color, 1.0))
            painter.drawText(
                QRectF(
                    tick_label_left,
                    y - metrics.height() / 2,
                    tick_label_width,
                    metrics.height(),
                ),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _format_axis_value(value),
            )
            painter.setPen(QPen(grid_color, 1.0))

        painter.setPen(QPen(axis_color, 1.0))
        painter.drawRect(rect)
        painter.save()
        painter.translate(metrics.height() / 2 + 2.0, rect.center().y())
        painter.rotate(-90.0)
        painter.drawText(
            QRectF(
                -rect.height() / 2,
                -metrics.height() / 2,
                rect.height(),
                metrics.height(),
            ),
            Qt.AlignmentFlag.AlignCenter,
            "Value",
        )
        painter.restore()
        painter.drawText(
            QRectF(
                rect.left(),
                self.height() - metrics.height() - 2.0,
                rect.width(),
                metrics.height(),
            ),
            Qt.AlignmentFlag.AlignCenter,
            "Time (local)",
        )

    @staticmethod
    def _paint_interval(
        painter: QPainter,
        colors: SemanticColors,
        xs: list[float],
        lower: list[float],
        upper: list[float],
    ) -> None:
        accent = QColor(colors.accent)
        if len(xs) == 1:
            cap = 7.0
            painter.setPen(QPen(accent, 2.4))
            painter.drawLine(QLineF(xs[0], upper[0], xs[0], lower[0]))
            painter.drawLine(QLineF(xs[0] - cap, upper[0], xs[0] + cap, upper[0]))
            painter.drawLine(QLineF(xs[0] - cap, lower[0], xs[0] + cap, lower[0]))
            return

        band = QPainterPath()
        band.moveTo(xs[0], upper[0])
        for x, y in zip(xs[1:], upper[1:], strict=True):
            band.lineTo(x, y)
        for x, y in zip(reversed(xs), reversed(lower), strict=True):
            band.lineTo(x, y)
        band.closeSubpath()
        shade = QColor(accent)
        shade.setAlpha(55)
        painter.fillPath(band, shade)

        edge = QColor(accent)
        edge.setAlpha(190)
        painter.setPen(QPen(edge, 1.4))
        for values in (upper, lower):
            path = QPainterPath()
            path.moveTo(xs[0], values[0])
            for x, y in zip(xs[1:], values[1:], strict=True):
                path.lineTo(x, y)
            painter.drawPath(path)

    def _paint_medians(
        self,
        painter: QPainter,
        colors: SemanticColors,
        rect: QRectF,
        xs: list[float],
        median: list[float],
    ) -> None:
        accent = QColor(colors.accent)
        painter.setPen(QPen(accent, 2.2))
        path = QPainterPath()
        path.moveTo(xs[0], median[0])
        for x, y in zip(xs[1:], median[1:], strict=True):
            path.lineTo(x, y)
        painter.drawPath(path)
        background = QColor(colors.surface)
        for index, (x, y) in enumerate(zip(xs, median, strict=True)):
            current = index == len(xs) - 1
            radius = self._CURRENT_RADIUS if current else self._HISTORICAL_RADIUS
            painter.setBrush(accent if current else background)
            painter.drawEllipse(QRectF(x - radius, y - radius, radius * 2, radius * 2))

        current_label = (
            f"Median {_format_axis_value(self._samples[-1].median_estimate)}"
        )
        metrics = painter.fontMetrics()
        label_width = metrics.horizontalAdvance(current_label) + 10.0
        label_height = metrics.height() + 4.0
        label_x = min(
            max(xs[-1] - label_width / 2, rect.left()),
            rect.right() - label_width,
        )
        if median[-1] - label_height - 8.0 >= rect.top():
            label_y = median[-1] - label_height - 8.0
        else:
            label_y = median[-1] + 8.0
        painter.setPen(QPen(QColor(colors.text), 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(
            QRectF(label_x, label_y, label_width, label_height),
            Qt.AlignmentFlag.AlignCenter,
            current_label,
        )

    def _paint_time_labels(
        self,
        painter: QPainter,
        colors: SemanticColors,
        rect: QRectF,
    ) -> None:
        instants = tuple(item.created_at.astimezone(UTC) for item in self._samples)
        earliest = min(instants)
        latest = max(instants)
        painter.setPen(QPen(QColor(colors.text), 1.0))
        metrics = painter.fontMetrics()
        label_y = rect.bottom() + 7.0
        label_height = metrics.height()
        earliest_text = _format_local_timestamp(earliest)
        if earliest == latest:
            painter.drawText(
                QRectF(rect.left(), label_y, rect.width(), label_height),
                Qt.AlignmentFlag.AlignCenter,
                metrics.elidedText(
                    earliest_text,
                    Qt.TextElideMode.ElideRight,
                    int(rect.width()),
                ),
            )
            return

        half_width = max(1.0, rect.width() / 2 - 4.0)
        latest_text = _format_local_timestamp(latest)
        painter.drawText(
            QRectF(rect.left(), label_y, half_width, label_height),
            Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(
                earliest_text,
                Qt.TextElideMode.ElideRight,
                int(half_width),
            ),
        )
        painter.drawText(
            QRectF(rect.right() - half_width, label_y, half_width, label_height),
            Qt.AlignmentFlag.AlignRight,
            metrics.elidedText(
                latest_text,
                Qt.TextElideMode.ElideLeft,
                int(half_width),
            ),
        )


def _coordinates(
    samples: tuple[NumericHistorySample, ...],
    rect: QRectF,
) -> tuple[list[float], list[float], list[float], list[float]]:
    instants = [item.created_at.astimezone(UTC) for item in samples]
    earliest, latest = min(instants), max(instants)
    duration = (latest - earliest).total_seconds()
    low, high = _value_range(samples)
    xs = [
        rect.center().x()
        if duration == 0
        else rect.left()
        + (instant - earliest).total_seconds() / duration * rect.width()
        for instant in instants
    ]

    def y(value: float) -> float:
        return rect.bottom() - (value - low) / (high - low) * rect.height()

    return (
        xs,
        [y(item.lower_bound) for item in samples],
        [y(item.median_estimate) for item in samples],
        [y(item.upper_bound) for item in samples],
    )


def _value_range(samples: tuple[NumericHistorySample, ...]) -> tuple[float, float]:
    if not samples:
        return 0.0, 1.0
    values = [
        value for item in samples for value in (item.lower_bound, item.upper_bound)
    ]
    low, high = min(values), max(values)
    if low == high:
        padding = max(1.0, abs(low) * 0.05)
        return low - padding, high + padding
    return low, high


def _axis_ticks(low: float, high: float) -> tuple[float, ...]:
    return tuple(low + (high - low) * index / 4 for index in range(5))


def _format_axis_value(value: float) -> str:
    if abs(value) < 1e-12:
        value = 0.0
    return format(value, ".6g")


def _format_local_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y %H:%M")


def _summary(samples: tuple[NumericHistorySample, ...]) -> str:
    if not samples:
        return "No Numeric ForecastRevisions are available."
    return "; ".join(
        f"Revision {item.sequence}: {item.confidence_percent}% interval {item.lower_bound} to {item.upper_bound}, median {item.median_estimate}"
        for item in samples
    )
