"""Presentation of fixed-level Numeric calibration; all statistics arrive derived."""

from PySide6.QtCore import QEvent, QPointF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.analytics.quantile_aggregate import (
    Proportion,
    QuantileAnalyticsSnapshot,
    QuantileCalibrationGroup,
)
from reckonsolve.domain.quantiles import NumericValueConstraint

from .analytics_charts import _paint_percent_axes, _plot_rect
from .analytics_components import (
    _new_update_metric,
    _ResponsiveChartTable,
    _ResponsiveMetricRow,
)
from .components import ContentPanel
from .visual_system import Spacing, TextRole, apply_text_role, semantic_colors


def proportion_text(value: Proportion) -> str:
    if value.fraction is None:
        return "No observations"
    return f"{value.count}/{value.total} · {float(value.fraction) * 100:.1f}%"


def uncertainty_text(value: Proportion) -> str:
    interval = value.wilson_95
    return (
        "Not available"
        if interval is None
        else (f"{100 * interval[0]:.1f}–{100 * interval[1]:.1f}%")
    )


def _label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    apply_text_role(label, TextRole.SECONDARY)
    return label


class _CalibrationTable(QTableWidget):
    """Keep the complete text alternative on its enclosing raised surface."""

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
        ):
            self.synchronize_surface()
            _fit(self)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        _fit(self)

    def synchronize_surface(self) -> None:
        palette = self.palette()
        surface = QColor(semantic_colors(palette).raised)
        if palette.color(QPalette.ColorRole.Base) != surface:
            palette.setColor(QPalette.ColorRole.Base, surface)
            palette.setColor(QPalette.ColorRole.AlternateBase, surface)
            self.setPalette(palette)


def _table(
    headers: tuple[str, ...], rows: int, name: str, parent: QWidget
) -> QTableWidget:
    table = _CalibrationTable(rows, len(headers), parent)
    table.synchronize_surface()
    table.setObjectName(name)
    table.setAccessibleName(name)
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.verticalHeader().hide()
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    return table


def _row(table: QTableWidget, row: int, values: tuple[str, ...]) -> None:
    for column, text in enumerate(values):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setToolTip(text)
        table.setItem(row, column, item)


def _fit(table: QTableWidget) -> None:
    table.resizeRowsToContents()
    table.setFixedHeight(
        table.horizontalHeader().height()
        + sum(table.rowHeight(r) for r in range(table.rowCount()))
        + 2 * table.frameWidth()
        + 2
    )


class QuantileCalibrationChart(QWidget):
    """Five elicited levels only; tie bands are not confidence intervals."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.group: QuantileCalibrationGroup | None = None
        self.setAccessibleName("Five-quantile calibration plot")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumHeight(260)

    def sizeHint(self) -> QSize:
        return QSize(550, 280)

    def set_group(self, group: QuantileCalibrationGroup) -> None:
        self.group = group
        whole = group.value_constraint is NumericValueConstraint.WHOLE_NUMBER
        facts = []
        for level in group.levels:
            text = f"{level.nominal_percent}%: at or below {proportion_text(level.inclusive)}; 95% Wilson {uncertainty_text(level.inclusive)}"
            if whole:
                text += f"; strictly below {proportion_text(level.strict)}; 95% Wilson {uncertainty_text(level.strict)}"
            facts.append(text)
        self.setAccessibleDescription(
            f"N={group.sample_size}. "
            + (
                "Whole-number tie bands. "
                if whole
                else "Continuous-style frequencies. "
            )
            + "; ".join(facts)
        )
        self.update()

    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = semantic_colors(self.palette())
        painter.fillRect(self.rect(), QColor(colors.raised))
        plot = _plot_rect(self)
        _paint_percent_axes(
            painter,
            self.palette(),
            plot,
            x_title="Nominal percentile",
            y_title="Observed frequency",
        )
        pen = QPen(QColor(colors.border), 1)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(plot.bottomLeft(), plot.topRight())
        if self.group is None or not self.group.sample_size:
            return
        whole = self.group.value_constraint is NumericValueConstraint.WHOLE_NUMBER
        accent = QColor(colors.accent)
        for level in self.group.levels:
            x = plot.left() + level.nominal_percent / 100 * plot.width()

            def point(fraction: float, x: float = x) -> QPointF:
                return QPointF(x, plot.bottom() - fraction * plot.height())

            if whole:
                low, high = (
                    float(level.strict.fraction),
                    float(level.inclusive.fraction),
                )
                painter.setPen(QPen(accent, 5))
                painter.drawLine(point(low), point(high))
                painter.setPen(QPen(accent, 2))
                painter.setBrush(QColor(colors.raised))
                painter.drawEllipse(point(low), 4, 4)
                painter.setBrush(accent)
                painter.drawEllipse(point(high), 4, 4)
            else:
                low, high = level.inclusive.wilson_95
                painter.setPen(QPen(accent, 1.5))
                painter.drawLine(point(low), point(high))
                for endpoint in (low, high):
                    p = point(endpoint)
                    painter.drawLine(QPointF(x - 4, p.y()), QPointF(x + 4, p.y()))
                painter.setBrush(accent)
                painter.drawEllipse(point(float(level.inclusive.fraction)), 4, 4)


class _CalibrationPanel(ContentPanel):
    def __init__(self, *, whole: bool, parent: QWidget) -> None:
        self.whole = whole
        name = "wholeNumber" if whole else "continuous"
        super().__init__(
            "Whole-number calibration" if whole else "Continuous-style calibration",
            "Open dot: actual < percentile; filled dot: actual ≤ percentile. The connecting band preserves ties."
            if whole
            else "Actual ≤ percentile at the five elicited levels. Bars show 95% Wilson uncertainty; the diagonal is the reference.",
            parent=parent,
        )
        self.setObjectName(f"{name}QuantileCalibration")
        self.sample = _label("", self.body)
        self.body_layout.addWidget(self.sample)
        self.chart = QuantileCalibrationChart(self.body)
        self.table = _table(
            ("Nominal", "Actual < q\n95% Wilson", "Actual ≤ q\n95% Wilson")
            if whole
            else ("Nominal", "Actual ≤ q", "95% Wilson"),
            5,
            f"{name}QuantileCalibrationTable",
            self.body,
        )
        self.pair = _ResponsiveChartTable(
            self.chart,
            self.table,
            object_name=f"{name}QuantileComparison",
            parent=self.body,
        )
        self.body_layout.addWidget(self.pair)
        self.balances: list[QTableWidget] = []
        panels = []
        for title, key in (
            ("50% interval", "50"),
            ("90% interval", "90"),
            ("Median balance", "median"),
        ):
            panel = ContentPanel(title, parent=self.body)
            table = _table(
                ("Outcome", "Count · %", "95% Wilson"),
                3,
                f"{name}Balance{key}",
                panel.body,
            )
            panel.body_layout.addWidget(table)
            self.balances.append(table)
            panels.append(panel)
        self.balance_row = _ResponsiveMetricRow(
            tuple(panels),
            stack_below=1150,
            object_name=f"{name}OutcomeBalances",
            parent=self.body,
        )
        self.body_layout.addWidget(self.balance_row)
        self.guidance = _label(
            "The nominal percentile can lie anywhere within the tie band, allowing for sampling variation; the band shows ties, not uncertainty. "
            "Whole-number ties can put closed-interval coverage above 50% or 90% without implying miscalibration. Median ties are retained."
            if whole
            else "Reference below / inside / above: 25% / 50% / 25% for the 50% interval; 5% / 90% / 5% for the 90% interval. Median below / above is approximately 50% / 50% when ties are negligible.",
            self.body,
        )
        self.body_layout.addWidget(self.guidance)

    def render(self, group: QuantileCalibrationGroup) -> None:
        self.set_count(group.sample_size)
        self.sample.setText(
            f"N = {group.sample_size} eligible resolved Predictions. Small samples are uncertain; these are descriptive, pointwise 95% intervals, not proof of skill."
            if group.sample_size
            else "No eligible resolved Predictions in this measurement group for the current filters."
        )
        self.pair.setVisible(bool(group.sample_size))
        self.balance_row.setVisible(bool(group.sample_size))
        self.guidance.setVisible(bool(group.sample_size))
        self.chart.set_group(group)
        for index, level in enumerate(group.levels):
            values = (
                (
                    f"{level.nominal_percent}%",
                    f"{proportion_text(level.strict)}\n{uncertainty_text(level.strict)}",
                    f"{proportion_text(level.inclusive)}\n{uncertainty_text(level.inclusive)}",
                )
                if self.whole
                else (
                    f"{level.nominal_percent}%",
                    proportion_text(level.inclusive),
                    uncertainty_text(level.inclusive),
                )
            )
            _row(self.table, index, values)
        self.table.setAccessibleDescription(self.chart.accessibleDescription())
        _fit(self.table)
        for index, (table, balance) in enumerate(
            zip(
                self.balances,
                (group.interval_50, group.interval_90, group.median),
                strict=True,
            )
        ):
            labels = ("Below", "Equal" if index == 2 else "Inside (inclusive)", "Above")
            details = []
            for row, (label, value) in enumerate(
                zip(labels, (balance.below, balance.inside, balance.above), strict=True)
            ):
                values = (label, proportion_text(value), uncertainty_text(value))
                _row(table, row, values)
                details.append(" · ".join(values))
            table.setAccessibleDescription("; ".join(details))
            _fit(table)


class QuantileAnalyticsView(QWidget):
    """Separate continuous and discrete calibration with scale-free update signs."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("quantileNumericAnalytics")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.SECTION))
        summary = ContentPanel(
            "Five-quantile Numeric forecasts",
            "One final eligible forecast per resolved Prediction. Calibration can combine units; raw WIS cannot be averaged across unrelated questions.",
            parent=self,
        )
        self.summary = _label("", summary.body)
        summary.body_layout.addWidget(self.summary)
        self.continuous = _CalibrationPanel(whole=False, parent=self)
        self.whole_number = _CalibrationPanel(whole=True, parent=self)
        updates = ContentPanel(
            "Five-quantile updates — initial versus final",
            "One pair per eligible revised-and-resolved Prediction; direction only, without averaging raw WIS or ΔWIS.",
            parent=self,
        )
        self.update_values = []
        cards = []
        for label, key in (
            ("Better · lower final WIS", "better"),
            ("Equal WIS", "equal"),
            ("Worse · higher final WIS", "worse"),
        ):
            card, value = _new_update_metric(
                label,
                value_object_name=f"quantileUpdate{key.title()}",
                parent=updates.body,
            )
            cards.append(card)
            self.update_values.append(value)
        updates.body_layout.addWidget(
            _ResponsiveMetricRow(
                tuple(cards),
                stack_below=850,
                object_name="quantileUpdateDirections",
                parent=updates.body,
            )
        )
        self.update_guidance = _label("", updates.body)
        updates.body_layout.addWidget(self.update_guidance)
        for widget in (summary, self.continuous, self.whole_number, updates):
            layout.addWidget(widget)

    def render(self, snapshot: QuantileAnalyticsSnapshot) -> None:
        self.summary.setText(
            f"{snapshot.scored_prediction_count} eligible · {snapshot.resolved_candidate_count} resolved · "
            f"{snapshot.unscored_prediction_count} unscored (outcome fixed at or before the first forecast). "
            "Invalid, unresolved, and legacy interval forecasts are excluded."
        )
        self.continuous.render(snapshot.continuous)
        self.whole_number.render(snapshot.whole_number)
        for label, value in zip(
            self.update_values,
            (snapshot.better, snapshot.equal, snapshot.worse),
            strict=True,
        ):
            label.setText(proportion_text(value))
            label.setAccessibleDescription(
                f"{proportion_text(value)}; 95% Wilson {uncertainty_text(value)}"
            )
        self.update_guidance.setText(
            f"{snapshot.better.total} eligible revised pairs; {snapshot.unrevised_count} with no eligible revision after the initial forecast (not counted as ties). "
            "This is mechanical hindsight, not evidence that updating caused improvement. Counts lose magnitude and are not a universal skill score."
        )
