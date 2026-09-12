"""Five elicited values and a presentation-only central CDF."""

from itertools import pairwise

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.predictions import PredictionValidationError
from reckonsolve.domain.quantiles import (
    QUANTILE_LEVELS,
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
    quantile_summary,
)

from .visual_system import Spacing, TextRole, apply_text_role, semantic_colors


class QuantileCDF(QWidget):
    """Only interpolate between anchors; never extrapolate unsupported tails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.quantiles: FiveQuantiles | None = None
        self.unit = ""
        self.setObjectName("quantileCDF")
        self.setAccessibleName("Implied central cumulative distribution")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.setMinimumHeight(210)

    def set_forecast(self, quantiles: FiveQuantiles | None, unit: str) -> None:
        self.quantiles, self.unit = quantiles, unit
        self.setAccessibleDescription(
            "No complete valid forecast."
            if quantiles is None
            else quantile_summary(quantiles, unit)
            + ". Markers are elicited percentiles; dashed lines interpolate only between them. Equal values form vertical jumps. Outer tails are unspecified."
        )
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(480, 240)

    def paintEvent(self, event) -> None:
        if self.quantiles is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = semantic_colors(self.palette())
        text = self.palette().color(self.palette().ColorRole.Text)
        area = QRectF(45, 22, max(1, self.width() - 65), max(1, self.height() - 67))
        values = [v.scaled_value for v in self.quantiles.values]
        lo, hi = values[0], values[-1]
        span = hi - lo or max(1, 10**self.quantiles.q50.decimal_places)
        padding = span * 0.06 if hi != lo else span / 2
        width = span * 1.12 if hi != lo else span
        points = [
            QPointF(
                area.left() + ((value - lo) + padding) / width * area.width(),
                area.bottom() - level / 100 * area.height(),
            )
            for value, level in zip(values, QUANTILE_LEVELS, strict=True)
        ]
        painter.setPen(QPen(text, 1))
        painter.drawLine(area.bottomLeft(), area.bottomRight())
        painter.drawLine(area.topLeft(), area.bottomLeft())
        for level in QUANTILE_LEVELS:
            y = area.bottom() - level / 100 * area.height()
            painter.drawText(
                QRectF(0, y - 9, 39, 18), Qt.AlignmentFlag.AlignRight, f"{level}%"
            )
        painter.setPen(QPen(QColor(colors.accent), 1.5, Qt.PenStyle.DashLine))
        for a, b in pairwise(points):
            painter.drawLine(a, b)
        painter.setPen(QPen(QColor(colors.accent), 1.5))
        painter.setBrush(QColor(colors.accent))
        for point in points:
            painter.drawEllipse(point, 4, 4)
        painter.setPen(text)
        painter.drawText(
            QRectF(area.left(), area.bottom() + 6, area.width() / 2, 20),
            Qt.AlignmentFlag.AlignLeft,
            str(self.quantiles.q05),
        )
        painter.drawText(
            QRectF(area.center().x(), area.bottom() + 6, area.width() / 2, 20),
            Qt.AlignmentFlag.AlignRight,
            str(self.quantiles.q95),
        )
        painter.drawText(
            QRectF(0, self.height() - 22, self.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            self.unit,
        )
        painter.end()


class FiveQuantileInput(QWidget):
    """No wizard or sorting: all five editable values form one forecast."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.decimal_places = 0
        self.value_constraint = NumericValueConstraint.CONTINUOUS
        self.unit = ""
        self.inputs: dict[int, QLineEdit] = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        grid = QGridLayout()
        for row, (title, levels) in enumerate(
            (("90% interval", (5, 95)), ("Median", (50,)), ("50% interval", (25, 75)))
        ):
            heading = QLabel(title, self)
            apply_text_role(heading, TextRole.LABEL)
            grid.addWidget(heading, row * 2, 0, 1, 2)
            for col, level in enumerate(levels):
                field = QLineEdit(self)
                field.setObjectName(f"quantile{level:02}Input")
                field.setAccessibleName(
                    f"{level}th percentile"
                    if level != 50
                    else "Median (50th percentile)"
                )
                field.setPlaceholderText(f"{level}th percentile")
                field.textChanged.connect(self.update_preview)
                grid.addWidget(field, row * 2 + 1, col, 1, 2 if len(levels) == 1 else 1)
                self.inputs[level] = field
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.preview = QuantileCDF(self)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.PlainText)
        self.summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.preview)
        layout.addWidget(self.summary)
        self.update_preview()

    def values(self) -> dict[int, str]:
        return {level: field.text() for level, field in self.inputs.items()}

    def set_definition(
        self, unit: str, decimal_places: int, constraint: NumericValueConstraint
    ) -> None:
        self.unit, self.decimal_places, self.value_constraint = (
            unit,
            decimal_places,
            constraint,
        )
        self.update_preview()

    def set_quantiles(self, quantiles: FiveQuantiles) -> None:
        for level, value in zip(QUANTILE_LEVELS, quantiles.values, strict=True):
            self.inputs[level].setText(str(value))

    def clear(self) -> None:
        for field in self.inputs.values():
            field.clear()

    def update_preview(self) -> None:
        try:
            definition = QuantileDefinition(
                self.unit, self.decimal_places, self.value_constraint
            )
            quantiles = FiveQuantiles.from_values(self.values(), self.decimal_places)
            definition.validate_quantiles(quantiles)
        except PredictionValidationError:
            self.preview.set_forecast(None, self.unit)
            self.preview.hide()
            self.summary.hide()
            return
        self.preview.set_forecast(quantiles, self.unit)
        self.summary.setText(
            quantile_summary(quantiles, self.unit)
            + "\nDots are your five percentiles; dashed lines interpolate between them only. Ties form jumps. No outer-tail shape is assumed."
        )
        self.preview.show()
        self.summary.show()
