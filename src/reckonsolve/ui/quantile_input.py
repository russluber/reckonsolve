"""Five elicited values and a presentation-only central CDF."""

from itertools import pairwise

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
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

from .visual_system import (
    Spacing,
    StatusTone,
    TextRole,
    apply_message_role,
    apply_text_role,
    semantic_colors,
)


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
        metrics = painter.fontMetrics()
        axis_width = max(1, self.width() - 65)
        unit_flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
        unit_height = metrics.boundingRect(
            QRect(0, 0, self.width(), 4096), unit_flags, self.unit
        ).height()
        endpoints = (str(self.quantiles.q05), str(self.quantiles.q95))
        separate_ticks = (
            sum(metrics.horizontalAdvance(t) for t in endpoints) + 12 > axis_width
        )
        tick_flags = Qt.TextFlag.TextWrapAnywhere
        tick_heights = [
            metrics.boundingRect(QRect(0, 0, axis_width, 4096), tick_flags, t).height()
            for t in endpoints
        ]
        ticks_height = sum(tick_heights) if separate_ticks else max(tick_heights)
        # Narrow context panes retain complete endpoint labels and long units;
        # reserve their real text height rather than painting over the plot.
        area = QRectF(
            45,
            22,
            axis_width,
            max(1, self.height() - 22 - ticks_height - unit_height - 16),
        )
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
        for index, endpoint in enumerate(endpoints):
            painter.drawText(
                QRectF(
                    area.left(),
                    area.bottom()
                    + 6
                    + (tick_heights[0] if index and separate_ticks else 0),
                    area.width(),
                    tick_heights[index],
                ),
                tick_flags
                | (
                    Qt.AlignmentFlag.AlignLeft
                    if index == 0
                    else Qt.AlignmentFlag.AlignRight
                ),
                endpoint,
            )
        painter.drawText(
            QRectF(0, self.height() - unit_height - 2, self.width(), unit_height),
            unit_flags,
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
        self.preview_enabled = True
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
        self.validation_message = QLabel(self)
        self.validation_message.setWordWrap(True)
        apply_message_role(
            self.validation_message,
            StatusTone.ERROR,
            accessible_name="Numeric forecast validation",
        )
        layout.addWidget(self.validation_message)
        self.validation_message.hide()
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

    def show_validation(self, error: Exception) -> None:
        """Place authoritative exact-value feedback beside the unchanged inputs."""
        if getattr(error, "field", "") not in (
            "quantiles",
            "value",
            "q05",
            "q25",
            "q50",
            "q75",
            "q95",
        ):
            return
        try:
            quantiles = FiveQuantiles.from_values(self.values(), self.decimal_places)
            QuantileDefinition(
                self.unit, self.decimal_places, self.value_constraint
            ).validate_quantiles(quantiles)
        except PredictionValidationError as invalid:
            self.validation_message.setText(str(invalid))
            self.validation_message.show()
            field = (
                self.inputs.get(int(invalid.field[1:]))
                if invalid.field.startswith("q") and invalid.field != "quantiles"
                else self.inputs[5]
            )
            field.setFocus(Qt.FocusReason.OtherFocusReason)
            ancestor = self.parentWidget()
            while ancestor is not None:
                if isinstance(ancestor, QScrollArea):
                    ancestor.ensureWidgetVisible(self, 12, 12)
                    break
                ancestor = ancestor.parentWidget()

    def update_preview(self) -> None:
        self.validation_message.hide()
        if not self.preview_enabled:
            self.preview.hide()
            self.summary.hide()
            return
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
