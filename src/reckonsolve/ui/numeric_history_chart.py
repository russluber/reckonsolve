"""Native interval-band rendering for one Numeric Prediction's history."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from PySide6.QtCore import QRectF, QSize
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget


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
        return QSize(640, 280)

    def minimumSizeHint(self) -> QSize:
        return QSize(320, 220)

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.color(QPalette.ColorRole.Base))
        rect = QRectF(58, 16, max(1, self.width() - 78), max(1, self.height() - 58))
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid)))
        painter.drawRect(rect)
        if not self._samples:
            return
        xs, lower, median, upper = _coordinates(self._samples, rect)
        band = QPainterPath()
        band.moveTo(xs[0], upper[0])
        for x, y in zip(xs[1:], upper[1:], strict=True):
            band.lineTo(x, y)
        for x, y in zip(reversed(xs), reversed(lower), strict=True):
            band.lineTo(x, y)
        band.closeSubpath()
        shade = QColor(palette.color(QPalette.ColorRole.Highlight))
        shade.setAlpha(55)
        painter.fillPath(band, shade)
        pen = QPen(palette.color(QPalette.ColorRole.Highlight), 2)
        painter.setPen(pen)
        path = QPainterPath()
        path.moveTo(xs[0], median[0])
        for x, y in zip(xs[1:], median[1:], strict=True):
            path.lineTo(x, y)
        painter.drawPath(path)
        painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
        for x, y in zip(xs, median, strict=True):
            painter.drawEllipse(x - 4, y - 4, 8, 8)


def _coordinates(
    samples: tuple[NumericHistorySample, ...],
    rect: QRectF,
) -> tuple[list[float], list[float], list[float], list[float]]:
    instants = [item.created_at.astimezone(UTC) for item in samples]
    earliest, latest = min(instants), max(instants)
    duration = (latest - earliest).total_seconds()
    values = [
        value for item in samples for value in (item.lower_bound, item.upper_bound)
    ]
    low, high = min(values), max(values)
    if low == high:
        low, high = low - 1, high + 1
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


def _summary(samples: tuple[NumericHistorySample, ...]) -> str:
    if not samples:
        return "No Numeric ForecastRevisions are available."
    return "; ".join(
        f"Revision {item.sequence}: {item.confidence_percent}% interval {item.lower_bound} to {item.upper_bound}, median {item.median_estimate}"
        for item in samples
    )
