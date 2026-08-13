"""Native rendering for one prediction's immutable probability history."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import pairwise
from typing import Protocol

from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


class ForecastRevisionLike(Protocol):
    """Structural revision data consumed by the presentation-only chart."""

    revision_id: int
    sequence: int
    probability_percent: int
    created_at: datetime
    rationale: str | None


@dataclass(frozen=True, slots=True)
class ProbabilityHistorySample:
    """One real forecast-revision marker in canonical sequence order."""

    revision_id: int
    sequence: int
    probability_percent: int
    created_at: datetime
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class ChartCoordinate:
    """A logical-pixel coordinate used by chart geometry."""

    x: float
    y: float


@dataclass(frozen=True, slots=True)
class RevisionMarker:
    """The coordinate of one genuine revision observation."""

    sample: ProbabilityHistorySample
    coordinate: ChartCoordinate


@dataclass(frozen=True, slots=True)
class ProbabilityChartGeometry:
    """Marker and synthetic step vertices for one paint pass."""

    markers: tuple[RevisionMarker, ...]
    step_vertices: tuple[ChartCoordinate, ...]
    earliest_instant: datetime | None
    latest_instant: datetime | None


def calculate_chart_geometry(
    samples: Iterable[ProbabilityHistorySample],
    plot_rect: QRectF,
) -> ProbabilityChartGeometry:
    """Project revision samples onto elapsed time and a fixed 0-100 scale."""

    ordered = tuple(sorted(samples, key=lambda sample: sample.sequence))
    if not ordered:
        return ProbabilityChartGeometry((), (), None, None)
    if plot_rect.width() <= 0 or plot_rect.height() <= 0:
        raise ValueError("Chart plot dimensions must be positive.")

    instants = tuple(_as_utc(sample.created_at) for sample in ordered)
    earliest = min(instants)
    latest = max(instants)
    duration_seconds = (latest - earliest).total_seconds()

    markers: list[RevisionMarker] = []
    for sample, instant in zip(ordered, instants, strict=True):
        if duration_seconds == 0:
            x = plot_rect.center().x()
        else:
            elapsed_fraction = (instant - earliest).total_seconds() / duration_seconds
            x = plot_rect.left() + elapsed_fraction * plot_rect.width()
        y = plot_rect.top() + (
            (100 - sample.probability_percent) / 100 * plot_rect.height()
        )
        markers.append(RevisionMarker(sample, ChartCoordinate(x, y)))

    step_vertices: list[ChartCoordinate] = [markers[0].coordinate]
    for previous, current in pairwise(markers):
        step_vertices.append(
            ChartCoordinate(current.coordinate.x, previous.coordinate.y)
        )
        step_vertices.append(current.coordinate)

    return ProbabilityChartGeometry(
        tuple(markers),
        tuple(step_vertices),
        earliest,
        latest,
    )


class ProbabilityHistoryChart(QWidget):
    """Paint an accessible, theme-aware probability history without dependencies."""

    _HISTORICAL_RADIUS = 4.0
    _CURRENT_RADIUS = 5.5

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._samples: tuple[ProbabilityHistorySample, ...] = ()
        self.setAccessibleName("Probability history chart")
        self.setAccessibleDescription(
            "No forecast revisions are available. Exact revision details are listed "
            "in the Timeline."
        )
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._timeline_available = True

    @property
    def samples(self) -> tuple[ProbabilityHistorySample, ...]:
        """Return the real revision samples currently represented."""

        return self._samples

    @property
    def revision_count(self) -> int:
        """Return the number of real revision markers represented."""

        return len(self._samples)

    def set_revisions(self, revisions: Iterable[ForecastRevisionLike]) -> None:
        """Replace chart data with validated revisions in canonical sequence order."""

        samples = tuple(
            sorted(
                (_sample_from_revision(revision) for revision in revisions),
                key=lambda sample: sample.sequence,
            )
        )
        if len({sample.sequence for sample in samples}) != len(samples):
            raise ValueError("Forecast revision sequences must be unique.")
        if len({sample.revision_id for sample in samples}) != len(samples):
            raise ValueError("Forecast revision identifiers must be unique.")
        self._samples = samples
        self.setAccessibleDescription(
            _accessible_summary(
                samples,
                timeline_available=self._timeline_available,
            )
        )
        self.update()

    def clear(self) -> None:
        """Remove all represented revisions."""

        self.set_revisions(())

    def set_timeline_available(self, available: bool) -> None:
        """Keep the nonvisual-equivalent note truthful after a Timeline read."""

        self._timeline_available = available
        self.setAccessibleDescription(
            _accessible_summary(self._samples, timeline_available=available)
        )

    def sizeHint(self) -> QSize:
        """Provide a useful default while remaining responsive inside the scroll area."""

        minimum = self.minimumSizeHint()
        return QSize(max(640, minimum.width()), max(270, minimum.height()))

    def minimumSizeHint(self) -> QSize:
        """Grow with the active font so axes and labels remain legible."""

        left, top, right, bottom = self._chart_margins()
        minimum_plot_height = max(
            100.0,
            self.fontMetrics().horizontalAdvance("Probability") + 12.0,
        )
        return QSize(
            max(320, round(left + right + 200.0)),
            max(220, round(top + bottom + minimum_plot_height)),
        )

    def changeEvent(self, event: QEvent) -> None:
        """Recalculate layout hints after font, style, or palette changes."""

        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.PaletteChange,
        ):
            self.updateGeometry()
            self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        """Recompute and paint geometry for the current logical-pixel size."""

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Base))

        plot_rect = self._plot_rect()
        self._paint_axes(painter, palette, plot_rect)
        if not self._samples:
            return

        geometry = calculate_chart_geometry(self._samples, plot_rect)
        self._paint_step_line(painter, palette, geometry)
        self._paint_markers(painter, palette, plot_rect, geometry)
        self._paint_time_labels(painter, palette, plot_rect, geometry)

    def _plot_rect(self) -> QRectF:
        left, top, right, bottom = self._chart_margins()
        width = max(1.0, self.width() - left - right)
        height = max(1.0, self.height() - top - bottom)
        return QRectF(
            left,
            top,
            width,
            height,
        )

    def _chart_margins(self) -> tuple[float, float, float, float]:
        metrics = self.fontMetrics()
        tick_width = max(
            metrics.horizontalAdvance(f"{probability}%")
            for probability in (0, 25, 50, 75, 100)
        )
        left = metrics.height() + tick_width + 28.0
        top = metrics.height() / 2 + self._CURRENT_RADIUS + 6.0
        right = self._CURRENT_RADIUS + 14.0
        bottom = metrics.height() * 2 + 18.0
        return left, top, right, bottom

    def _paint_axes(
        self,
        painter: QPainter,
        palette: QPalette,
        plot_rect: QRectF,
    ) -> None:
        axis_color = palette.color(QPalette.ColorRole.Text)
        grid_color = palette.color(QPalette.ColorRole.Mid)
        grid_color.setAlpha(85)
        metrics = painter.fontMetrics()
        left_margin = plot_rect.left()
        title_band_width = metrics.height() + 8.0
        tick_label_left = title_band_width
        tick_label_width = max(
            1.0,
            left_margin - tick_label_left - 8.0,
        )

        painter.setPen(QPen(grid_color, 1.0))
        for probability in (0, 25, 50, 75, 100):
            y = plot_rect.top() + (100 - probability) / 100 * plot_rect.height()
            painter.drawLine(plot_rect.left(), y, plot_rect.right(), y)
            painter.setPen(QPen(axis_color, 1.0))
            painter.drawText(
                QRectF(
                    tick_label_left,
                    y - metrics.height() / 2,
                    tick_label_width,
                    metrics.height(),
                ),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{probability}%",
            )
            painter.setPen(QPen(grid_color, 1.0))

        painter.setPen(QPen(axis_color, 1.0))
        painter.drawRect(plot_rect)
        painter.save()
        painter.translate(metrics.height() / 2 + 2.0, plot_rect.center().y())
        painter.rotate(-90.0)
        painter.drawText(
            QRectF(
                -plot_rect.height() / 2,
                -metrics.height() / 2,
                plot_rect.height(),
                metrics.height(),
            ),
            Qt.AlignmentFlag.AlignCenter,
            "Probability",
        )
        painter.restore()
        painter.drawText(
            QRectF(
                plot_rect.left(),
                self.height() - metrics.height() - 2.0,
                plot_rect.width(),
                metrics.height(),
            ),
            Qt.AlignmentFlag.AlignCenter,
            "Time (local)",
        )

    @staticmethod
    def _paint_step_line(
        painter: QPainter,
        palette: QPalette,
        geometry: ProbabilityChartGeometry,
    ) -> None:
        if len(geometry.step_vertices) < 2:
            return
        path = QPainterPath()
        first = geometry.step_vertices[0]
        path.moveTo(first.x, first.y)
        for vertex in geometry.step_vertices[1:]:
            path.lineTo(vertex.x, vertex.y)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Highlight), 2.2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

    def _paint_markers(
        self,
        painter: QPainter,
        palette: QPalette,
        plot_rect: QRectF,
        geometry: ProbabilityChartGeometry,
    ) -> None:
        highlight = palette.color(QPalette.ColorRole.Highlight)
        background = palette.color(QPalette.ColorRole.Base)
        text_color = palette.color(QPalette.ColorRole.Text)
        last_index = len(geometry.markers) - 1
        for index, marker in enumerate(geometry.markers):
            current = index == last_index
            radius = self._CURRENT_RADIUS if current else self._HISTORICAL_RADIUS
            painter.setPen(QPen(highlight, 2.0))
            painter.setBrush(highlight if current else background)
            painter.drawEllipse(
                marker.coordinate.x - radius,
                marker.coordinate.y - radius,
                radius * 2,
                radius * 2,
            )

        current = geometry.markers[-1]
        label = f"{current.sample.probability_percent}%"
        metrics = painter.fontMetrics()
        label_width = metrics.horizontalAdvance(label) + 10.0
        label_height = metrics.height() + 4.0
        label_x = min(
            max(current.coordinate.x - label_width / 2, plot_rect.left()),
            plot_rect.right() - label_width,
        )
        if current.coordinate.y - label_height - 8.0 >= plot_rect.top():
            label_y = current.coordinate.y - label_height - 8.0
        else:
            label_y = current.coordinate.y + 8.0
        painter.setPen(QPen(text_color, 1.0))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(
            QRectF(label_x, label_y, label_width, label_height),
            Qt.AlignmentFlag.AlignCenter,
            label,
        )

    @staticmethod
    def _paint_time_labels(
        painter: QPainter,
        palette: QPalette,
        plot_rect: QRectF,
        geometry: ProbabilityChartGeometry,
    ) -> None:
        if geometry.earliest_instant is None or geometry.latest_instant is None:
            return
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Text), 1.0))
        metrics = painter.fontMetrics()
        label_y = plot_rect.bottom() + 7.0
        label_height = metrics.height()
        earliest_text = _format_local_timestamp(geometry.earliest_instant)
        if geometry.earliest_instant == geometry.latest_instant:
            text = metrics.elidedText(
                earliest_text,
                Qt.TextElideMode.ElideRight,
                int(plot_rect.width()),
            )
            painter.drawText(
                QRectF(plot_rect.left(), label_y, plot_rect.width(), label_height),
                Qt.AlignmentFlag.AlignCenter,
                text,
            )
            return

        half_width = max(1.0, plot_rect.width() / 2 - 4.0)
        latest_text = _format_local_timestamp(geometry.latest_instant)
        painter.drawText(
            QRectF(plot_rect.left(), label_y, half_width, label_height),
            Qt.AlignmentFlag.AlignLeft,
            metrics.elidedText(
                earliest_text,
                Qt.TextElideMode.ElideRight,
                int(half_width),
            ),
        )
        painter.drawText(
            QRectF(
                plot_rect.right() - half_width,
                label_y,
                half_width,
                label_height,
            ),
            Qt.AlignmentFlag.AlignRight,
            metrics.elidedText(
                latest_text,
                Qt.TextElideMode.ElideLeft,
                int(half_width),
            ),
        )


def _sample_from_revision(revision: ForecastRevisionLike) -> ProbabilityHistorySample:
    if not isinstance(revision.revision_id, int) or isinstance(
        revision.revision_id, bool
    ):
        raise TypeError("Forecast revision identifiers must be integers.")
    if not isinstance(revision.sequence, int) or isinstance(revision.sequence, bool):
        raise TypeError("Forecast revision sequences must be integers.")
    if revision.revision_id < 1 or revision.sequence < 1:
        raise ValueError(
            "Forecast revision identifiers and sequences must be positive."
        )
    probability = revision.probability_percent
    if not isinstance(probability, int) or isinstance(probability, bool):
        raise TypeError("Forecast probabilities must be whole-number percentages.")
    if not 0 <= probability <= 100:
        raise ValueError("Forecast probabilities must be between 0% and 100%.")
    created_at = _as_utc(revision.created_at)
    return ProbabilityHistorySample(
        revision_id=revision.revision_id,
        sequence=revision.sequence,
        probability_percent=probability,
        created_at=created_at,
        rationale=revision.rationale,
    )


def _as_utc(value: datetime) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError("Forecast revision timestamps must be timezone-aware.")
    return value.astimezone(UTC)


def _format_local_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y %H:%M")


def _accessible_summary(
    samples: tuple[ProbabilityHistorySample, ...],
    *,
    timeline_available: bool = True,
) -> str:
    if timeline_available:
        timeline_note = "Exact revision details are listed in the Timeline."
    else:
        timeline_note = "The exact textual Timeline is currently unavailable."
    if not samples:
        return f"No forecast revisions are available. {timeline_note}"

    first = samples[0]
    current = samples[-1]
    if len(samples) == 1:
        return (
            f"1 forecast revision. Current forecast {current.probability_percent}% "
            f"recorded {_format_local_timestamp(current.created_at)} local time. "
            f"{timeline_note}"
        )

    probabilities = tuple(sample.probability_percent for sample in samples)
    return (
        f"{len(samples)} forecast revisions in sequence order. Started at "
        f"{first.probability_percent}% on "
        f"{_format_local_timestamp(first.created_at)} local time; current forecast "
        f"{current.probability_percent}% on "
        f"{_format_local_timestamp(current.created_at)} local time. Probability "
        f"range {min(probabilities)}% to {max(probabilities)}%. {timeline_note}"
    )
