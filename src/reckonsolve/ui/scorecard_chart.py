"""Final scored intervals versus the effective actual; no scoring or selection."""

from fractions import Fraction
from math import ceil

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
    QRegion,
    QResizeEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from reckonsolve.analytics.quantiles import QuantileScorecard
from reckonsolve.ui.visual_system import semantic_colors


class ScoredIntervalsChart(QWidget):
    """Two interval rows on one linear scale, including out-of-range actuals."""

    def __init__(self, card: QuantileScorecard, parent: QWidget) -> None:
        super().__init__(parent)
        assert card.scoring_revision is not None and card.actual_value is not None
        assert card.definition is not None
        self.setObjectName("scoredIntervalsChart")
        q = card.scoring_revision.quantiles
        self._values = (q.q05, q.q25, q.q50, q.q75, q.q95, card.actual_value)
        self._scaled = tuple(v.scaled_value for v in self._values)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(0)
        self.setAccessibleName("Final scored intervals and actual outcome")
        self.setAccessibleDescription(
            f"90% interval {q.q05} to {q.q95}; 50% interval {q.q25} to {q.q75}; "
            f"median {q.q50}; actual {card.actual_value}. Unit: {card.definition.unit}. "
            "Vertical tick: median. Diamond: actual. Endpoints are inclusive."
        )
        self.setToolTip(self.accessibleDescription())
        self._fit_height()

    def _fit_height(self) -> None:
        _, labels = self.label_layout()[-1]
        self.setFixedHeight(
            ceil(
                max(rect.bottom() for _, rect, _ in labels)
                + self.fontMetrics().height()
            )
        )

    def sizeHint(self) -> QSize:
        return QSize(600, self.height())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_height()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.ApplicationFontChange):
            self._fit_height()
        self.update()

    def marker_positions(self) -> tuple[float, ...]:
        """Project exact differences before converting bounded ratios to pixels."""
        lo, hi = min(self._scaled), max(self._scaled)
        left = self.fontMetrics().horizontalAdvance("90%") + 20
        right = max(left + 1, self.width() - 16)
        pad = (right - left) * 0.06
        if lo == hi:
            return ((left + right) / 2,) * len(self._scaled)
        return tuple(
            left + pad + float(Fraction(v - lo, hi - lo)) * (right - left - 2 * pad)
            for v in self._scaled
        )

    def label_layout(
        self,
    ) -> tuple[tuple[float, tuple[tuple[str, QRectF, float], ...]], ...]:
        """Place endpoint, median, and actual labels without collisions.

        Tied values share one label; crowded distinct values use separate lanes.
        The scale includes the actual, but its extremes are not interval bounds.
        """
        fm = self.fontMetrics()
        h = fm.height()
        points = self.marker_positions()
        rows = []
        y = h * 2
        for indices in ((0, 2, 4), (1, 2, 3)):
            grouped = {}
            for index, role in zip(
                (*indices, 5), ("lower", "median", "upper", "actual"), strict=True
            ):
                grouped.setdefault(self._scaled[index], (index, []))[1].append(role)
            labels = []
            for index, roles in grouped.values():
                text = str(self._values[index])
                if len(roles) > 1:
                    text += " (" + "/".join(roles) + ")"
                elif roles == ["actual"]:
                    # Prefer a bare value. Name its role only if that value would
                    # crowd a bound/median label at the normal label baseline.
                    plain_width = min(
                        fm.horizontalAdvance(text) + 4, max(1, self.width() - 16)
                    )
                    plain_left = max(
                        8,
                        min(
                            points[index] - plain_width / 2,
                            self.width() - 8 - plain_width,
                        ),
                    )
                    if any(
                        plain_left - 4 < other.right()
                        and plain_left + plain_width + 4 > other.left()
                        for _, other, _ in labels
                    ):
                        text += " (actual)"
                text = fm.elidedText(
                    text, Qt.TextElideMode.ElideRight, max(1, self.width() - 16)
                )
                width = min(fm.horizontalAdvance(text) + 4, max(1, self.width() - 16))
                x = max(8, min(points[index] - width / 2, self.width() - 8 - width))
                rect = QRectF(x, y + h, width, h)
                while any(
                    rect.adjusted(-4, -2, 4, 2).intersects(other)
                    for _, other, _ in labels
                ):
                    rect.translate(0, h + 4)
                labels.append((text, rect, points[index]))
            rows.append((y, tuple(labels)))
            y = max(rect.bottom() for _, rect, _ in labels) + h * 3
        return tuple(rows)

    def paintEvent(self, event: QPaintEvent) -> None:
        colors = semantic_colors(self.palette())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        fm = self.fontMetrics()
        h = fm.height()
        points = self.marker_positions()
        for (label, low, high, thickness), (y, labels) in zip(
            (("90%", points[0], points[4], 5), ("50%", points[1], points[3], 9)),
            self.label_layout(),
            strict=True,
        ):
            painter.setPen(QColor(colors.text))
            painter.drawText(
                QRectF(0, y - h / 2, fm.horizontalAdvance("90%") + 8, h),
                Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            painter.setPen(QPen(QColor(colors.border), 1))
            painter.drawLine(QPointF(min(points), y), QPointF(max(points), y))
            painter.setPen(
                QPen(
                    QColor(colors.accent),
                    thickness,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(QPointF(low, y), QPointF(high, y))
            for endpoint in (low, high):
                painter.setPen(QPen(QColor(colors.accent), 2))
                painter.drawLine(QPointF(endpoint, y - 7), QPointF(endpoint, y + 7))
            painter.setPen(QPen(QColor(colors.text), 2))
            painter.drawLine(QPointF(points[2], y - 12), QPointF(points[2], y + 12))
            x = points[5]
            painter.setPen(QPen(QColor(colors.warning), 2))
            painter.setBrush(QColor(colors.warning))
            # The diamond sits above the band so ties never hide the median tick.
            center = y - 17
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
            painter.drawLine(QPointF(x, center + 5), QPointF(x, y + 9))
            for text, rect, anchor in labels:
                painter.setPen(QColor(colors.secondary_text))
                painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter, text)
                if rect.top() > y + h:
                    painter.save()
                    clip = QRegion(self.rect())
                    for _, label_rect, _ in labels:
                        clip -= QRegion(
                            label_rect.adjusted(-2, -2, 2, 2).toAlignedRect()
                        )
                    painter.setClipRegion(clip)
                    painter.setPen(QPen(QColor(colors.border), 1, Qt.PenStyle.DotLine))
                    painter.drawLine(
                        QPointF(anchor, y + 13), QPointF(anchor, rect.top() - 2)
                    )
                    painter.restore()
        painter.end()
