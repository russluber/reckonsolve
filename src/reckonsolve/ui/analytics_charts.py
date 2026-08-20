"""Native, presentation-only charts for aggregate scoring analytics."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise

from PySide6.QtCore import QLineF, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from reckonsolve.analytics import BrierTrendPoint, CalibrationBin


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


@dataclass(frozen=True, slots=True)
class BrierTrendMarker:
    """One cumulative Brier observation projected over resolution time."""

    point: BrierTrendPoint
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


def calculate_brier_trend_markers(
    points: Iterable[BrierTrendPoint],
    plot_rect: QRectF,
) -> tuple[BrierTrendMarker, ...]:
    """Project cumulative Brier means onto actual elapsed resolution time."""

    _validate_plot_rect(plot_rect)
    ordered = tuple(
        sorted(points, key=lambda point: (point.resolved_at, point.resolution_id))
    )
    if not ordered:
        return ()
    instants = tuple(_as_utc(point.resolved_at) for point in ordered)
    earliest = min(instants)
    latest = max(instants)
    duration = (latest - earliest).total_seconds()
    markers: list[BrierTrendMarker] = []
    for point, instant in zip(ordered, instants, strict=True):
        x = (
            plot_rect.center().x()
            if duration == 0
            else plot_rect.left()
            + (instant - earliest).total_seconds() / duration * plot_rect.width()
        )
        markers.append(
            BrierTrendMarker(
                point=point,
                coordinate=ChartPoint(
                    x=x,
                    y=plot_rect.top()
                    + (1 - point.cumulative_mean_brier) * plot_rect.height(),
                ),
            )
        )
    return tuple(markers)


class CalibrationChart(QWidget):
    """Paint a fixed-scale reliability diagram and perfect-calibration line."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
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

        reference_pen = QPen(palette.color(QPalette.ColorRole.Mid), 1.5)
        reference_pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(reference_pen)
        painter.drawLine(plot.bottomLeft(), plot.topRight())

        markers = calculate_calibration_markers(self._bins, plot)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Highlight), 2.0))
        for previous, current in pairwise(markers):
            painter.drawLine(
                QLineF(
                    previous.coordinate.x,
                    previous.coordinate.y,
                    current.coordinate.x,
                    current.coordinate.y,
                )
            )
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        for marker in markers:
            painter.drawEllipse(
                QRectF(
                    marker.coordinate.x - 5,
                    marker.coordinate.y - 5,
                    10,
                    10,
                )
            )


class BrierTrendChart(QWidget):
    """Paint cumulative mean Brier over actual resolution time."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._points: tuple[BrierTrendPoint, ...] = ()
        self.setObjectName("brierTrendChart")
        self.setAccessibleName("Cumulative mean Brier by resolution time")
        self.setAccessibleDescription("No scored predictions are available.")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    @property
    def points(self) -> tuple[BrierTrendPoint, ...]:
        return self._points

    def set_points(self, points: Iterable[BrierTrendPoint]) -> None:
        self._points = tuple(
            sorted(points, key=lambda point: (point.resolved_at, point.resolution_id))
        )
        if not self._points:
            description = "No scored predictions are available."
        else:
            description = "Cumulative mean Brier, lower is better: " + "; ".join(
                f"after {point.scored_count} scored, {point.cumulative_mean_brier:.3f}"
                for point in self._points
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
        _paint_brier_axes(painter, palette, plot)
        markers = calculate_brier_trend_markers(self._points, plot)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Highlight), 2.0))
        for previous, current in pairwise(markers):
            painter.drawLine(
                QLineF(
                    previous.coordinate.x,
                    previous.coordinate.y,
                    current.coordinate.x,
                    current.coordinate.y,
                )
            )
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        for marker in markers:
            painter.drawEllipse(
                QRectF(
                    marker.coordinate.x - 4.5,
                    marker.coordinate.y - 4.5,
                    9,
                    9,
                )
            )
        if markers:
            _paint_time_range(painter, palette, plot, self._points)


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
) -> None:
    painter.setPen(QPen(palette.color(QPalette.ColorRole.Text), 1.0))
    painter.drawRect(plot)
    metrics = painter.fontMetrics()
    for value in (0, 25, 50, 75, 100):
        x = plot.left() + value / 100 * plot.width()
        y = plot.top() + (100 - value) / 100 * plot.height()
        painter.drawText(
            QRectF(x - 22, plot.bottom() + 5, 44, metrics.height()),
            Qt.AlignmentFlag.AlignCenter,
            f"{value}%",
        )
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


def _paint_brier_axes(
    painter: QPainter,
    palette: QPalette,
    plot: QRectF,
) -> None:
    painter.setPen(QPen(palette.color(QPalette.ColorRole.Text), 1.0))
    painter.drawRect(plot)
    metrics = painter.fontMetrics()
    for value in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = plot.top() + (1 - value) * plot.height()
        painter.drawText(
            QRectF(0, y - metrics.height() / 2, plot.left() - 7, metrics.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{value:.2f}",
        )
    painter.drawText(
        QRectF(plot.left(), 0, plot.width(), metrics.height() + 4),
        Qt.AlignmentFlag.AlignCenter,
        "Cumulative mean Brier (lower is better)",
    )


def _paint_time_range(
    painter: QPainter,
    palette: QPalette,
    plot: QRectF,
    points: tuple[BrierTrendPoint, ...],
) -> None:
    painter.setPen(palette.color(QPalette.ColorRole.Text))
    metrics = painter.fontMetrics()
    earliest = min(points, key=lambda point: _as_utc(point.resolved_at)).resolved_at
    latest = max(points, key=lambda point: _as_utc(point.resolved_at)).resolved_at
    if _as_utc(earliest) == _as_utc(latest):
        painter.drawText(
            QRectF(plot.left(), plot.bottom() + 6, plot.width(), metrics.height()),
            Qt.AlignmentFlag.AlignCenter,
            _local_date_label(earliest),
        )
    else:
        painter.drawText(
            QRectF(plot.left(), plot.bottom() + 6, plot.width() / 2, metrics.height()),
            Qt.AlignmentFlag.AlignLeft,
            _local_date_label(earliest),
        )
        painter.drawText(
            QRectF(
                plot.center().x(),
                plot.bottom() + 6,
                plot.width() / 2,
                metrics.height(),
            ),
            Qt.AlignmentFlag.AlignRight,
            _local_date_label(latest),
        )
    painter.drawText(
        QRectF(plot.left(), plot.bottom() + metrics.height() + 7, plot.width(), 22),
        Qt.AlignmentFlag.AlignCenter,
        "Resolution time",
    )


def _validate_plot_rect(plot_rect: QRectF) -> None:
    if plot_rect.width() <= 0 or plot_rect.height() <= 0:
        raise ValueError("Chart plot dimensions must be positive.")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Analytics timestamps must be timezone-aware.")
    return value.astimezone(UTC)


def _local_date_label(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y").replace(" 0", " ")
