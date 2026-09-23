"""Native, presentation-only charts for aggregate scoring analytics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise

from PySide6.QtCore import QLineF, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from reckonsolve.analytics import (
    CalibrationBin,
)
from reckonsolve.ui.visual_system import semantic_colors


@dataclass(frozen=True, slots=True)
class ChartPoint:
    """One logical-pixel point used by analytics chart tests and painting."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class CalibrationMarker:
    """One occupied calibration bin projected onto the fixed axes."""

    calibration_bin: CalibrationBin
    coordinate: ChartPoint


def calculate_calibration_markers(
    bins: Iterable[CalibrationBin],
    plot_rect: QRectF,
) -> tuple[CalibrationMarker, ...]:
    """Project occupied bin means and observed frequencies onto 0-100 axes."""

    _validate_plot_rect(plot_rect)
    markers: list[CalibrationMarker] = []
    for calibration_bin in bins:
        if calibration_bin.count == 0:
            continue
        if (
            calibration_bin.mean_forecast_percent is None
            or calibration_bin.observed_yes_percent is None
        ):
            raise ValueError("Occupied calibration bins require both means.")
        markers.append(
            CalibrationMarker(
                calibration_bin=calibration_bin,
                coordinate=ChartPoint(
                    x=plot_rect.left()
                    + calibration_bin.mean_forecast_percent / 100 * plot_rect.width(),
                    y=plot_rect.top()
                    + (100 - calibration_bin.observed_yes_percent)
                    / 100
                    * plot_rect.height(),
                ),
            )
        )
    return tuple(markers)


class CalibrationChart(QWidget):
    """Paint a fixed-scale reliability diagram and perfect-calibration line."""

    def __init__(self, parent: QWidget | None = None, *, scatter: bool = False) -> None:
        super().__init__(parent)
        self._scatter = scatter
        self._bins: tuple[CalibrationBin, ...] = ()
        self.setObjectName("calibrationChart")
        self.setAccessibleName("Calibration reliability diagram")
        self.setAccessibleDescription("No scored predictions are available.")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    @property
    def bins(self) -> tuple[CalibrationBin, ...]:
        return self._bins

    def set_bins(self, bins: Iterable[CalibrationBin]) -> None:
        self._bins = tuple(bins)
        occupied = tuple(item for item in self._bins if item.count)
        if not occupied:
            description = "No scored predictions are available."
        else:
            details = "; ".join(
                f"{item.label}: {item.count} scored, mean forecast "
                f"{item.mean_forecast_percent:.1f} percent, observed Yes "
                f"{item.observed_yes_percent:.1f} percent"
                for item in occupied
                if item.mean_forecast_percent is not None
                and item.observed_yes_percent is not None
            )
            description = (
                "Perfect calibration is the diagonal. Occupied bins: " + details
            )
            if self._scatter:
                description += (
                    ". Diamonds show occupied bins; no interpolation between bins."
                )
        self.setAccessibleDescription(description)
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(640, 300)

    def minimumSizeHint(self) -> QSize:
        return QSize(340, 240)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Base))
        plot = _plot_rect(self)
        _paint_percent_axes(
            painter,
            palette,
            plot,
            x_title="Mean forecast probability",
            y_title="Observed Yes frequency",
        )

        reference_pen = QPen(
            QColor(semantic_colors(palette).border)
            if self._scatter
            else palette.color(QPalette.ColorRole.Mid),
            1.0 if self._scatter else 1.5,
        )
        reference_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(reference_pen)
        painter.drawLine(plot.bottomLeft(), plot.topRight())

        markers = calculate_calibration_markers(self._bins, plot)
        accent = (
            QColor(semantic_colors(palette).accent)
            if self._scatter
            else palette.color(QPalette.ColorRole.Highlight)
        )
        painter.setPen(QPen(accent, 2.0))
        if not self._scatter:
            for previous, current in pairwise(markers):
                painter.drawLine(
                    QLineF(
                        previous.coordinate.x,
                        previous.coordinate.y,
                        current.coordinate.x,
                        current.coordinate.y,
                    )
                )
        painter.setBrush(accent)
        for marker in markers:
            if self._scatter:
                x, y = marker.coordinate.x, marker.coordinate.y
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
                continue
            painter.drawEllipse(
                QRectF(
                    marker.coordinate.x - 5,
                    marker.coordinate.y - 5,
                    10,
                    10,
                )
            )


def _plot_rect(widget: QWidget) -> QRectF:
    metrics = widget.fontMetrics()
    left = metrics.horizontalAdvance("100%") + 18
    right = 24
    top = metrics.height() + 18
    bottom = metrics.height() * 3 + 18
    return QRectF(
        left,
        top,
        max(1, widget.width() - left - right),
        max(1, widget.height() - top - bottom),
    )


def _paint_percent_axes(
    painter: QPainter,
    palette: QPalette,
    plot: QRectF,
    *,
    x_title: str,
    y_title: str,
    x_ticks: tuple[int, ...] = (0, 25, 50, 75, 100),
) -> None:
    painter.setPen(QPen(palette.color(QPalette.ColorRole.Text), 1.0))
    painter.drawRect(plot)
    metrics = painter.fontMetrics()
    for value in x_ticks:
        x = plot.left() + value / 100 * plot.width()
        painter.drawText(
            QRectF(x - 22, plot.bottom() + 5, 44, metrics.height()),
            Qt.AlignmentFlag.AlignCenter,
            f"{value}%",
        )
    for value in (0, 25, 50, 75, 100):
        y = plot.top() + (100 - value) / 100 * plot.height()
        painter.drawText(
            QRectF(0, y - metrics.height() / 2, plot.left() - 7, metrics.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{value}%",
        )
    painter.drawText(
        QRectF(plot.left(), plot.bottom() + metrics.height() + 7, plot.width(), 22),
        Qt.AlignmentFlag.AlignCenter,
        x_title,
    )
    painter.drawText(
        QRectF(plot.left(), 0, plot.width(), metrics.height() + 4),
        Qt.AlignmentFlag.AlignCenter,
        y_title,
    )


def _validate_plot_rect(plot_rect: QRectF) -> None:
    if plot_rect.width() <= 0 or plot_rect.height() <= 0:
        raise ValueError("Chart plot dimensions must be positive.")
