"""Four report sections; render shared analytical facts without querying or scoring."""

from fractions import Fraction

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.analytics.one_shot_aggregate import (
    OneShotBinaryAnalytics,
    OneShotNumericAnalytics,
)
from reckonsolve.analytics.quantile_aggregate import (
    OutcomeBalance,
    QuantileAnalyticsSnapshot,
    QuantileCalibrationGroup,
)
from reckonsolve.analytics.trajectory_aggregate import TrajectoryAnalyticsSnapshot
from reckonsolve.application.performance import Section, SectionResult
from reckonsolve.domain.quantiles import NumericValueConstraint
from reckonsolve.ui.analytics_charts import CalibrationChart
from reckonsolve.ui.analytics_components import AnalyticsPanel, _ResponsiveChartTable
from reckonsolve.ui.components import PersistentMessageLabel
from reckonsolve.ui.detail_workspace import collapse_section
from reckonsolve.ui.quantile_analytics import (
    QuantileCalibrationPanel,
    _fit,
    _label,
    _row,
    _table,
    proportion_text,
    uncertainty_text,
)
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
    semantic_colors,
)

TITLES = {
    Section.ADAPTIVE_BINARY: "Adaptive Binary",
    Section.ADAPTIVE_NUMERIC: "Adaptive Numeric",
    Section.ONE_SHOT_BINARY: "One-Shot Binary",
    Section.ONE_SHOT_NUMERIC: "One-Shot Numeric",
}


def score_text(value: Fraction | None, *, signed: bool = False) -> str:
    if value is None:
        return "Not available"
    return f"{float(value):+.3f}" if signed else f"{float(value):.3f}"


class ReportSection(AnalyticsPanel):
    retry_requested = Signal()

    def __init__(self, section: Section, parent: QWidget) -> None:
        super().__init__(TITLES[section], parent=parent)
        self.section = section
        self.setObjectName(f"{section}Section")
        self._root_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.body_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.status = PersistentMessageLabel(
            accessible_name=f"{TITLES[section]} status", parent=self.body
        )
        self.body_layout.addWidget(self.status)
        self.retry = QPushButton("Try again", self.body)
        apply_action_role(self.retry, ActionRole.SECONDARY)
        self.retry.clicked.connect(self.retry_requested)
        self.retry.hide()
        self.body_layout.addWidget(self.retry)
        self.results = QWidget(self.body)
        self.results_layout = QVBoxLayout(self.results)
        self.results_layout.setContentsMargins(0, 0, 0, 0)
        self.results_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.results_layout.setSpacing(int(Spacing.ORDINARY))
        self.body_layout.addWidget(self.results)

    def pending(self) -> None:
        self.results.hide()
        self.retry.hide()
        self.status.show_message("Loading current results…", StatusTone.NEUTRAL)

    def show_result(self, result: SectionResult) -> None:
        self.retry.setVisible(result.error is not None)
        self.results.setVisible(result.data is not None)
        if result.error:
            self.status.show_message(
                "This section could not load. " + result.error, StatusTone.ERROR
            )
        else:
            self.status.clear_message()
            self.render(result)

    def render(self, result: SectionResult) -> None:
        raise NotImplementedError

    def reset_disclosures(self) -> None:
        for widget in self.findChildren(QWidget):
            toggle = getattr(widget, "disclosure_button", None)
            if toggle is not None:
                toggle.setChecked(False)


class BinarySection(ReportSection):
    def __init__(self, section: Section, parent: QWidget) -> None:
        super().__init__(section, parent)
        self.adaptive = section is Section.ADAPTIVE_BINARY
        metrics = QWidget(self.results)
        metrics_layout = QHBoxLayout(metrics)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.score = QLabel(metrics)
        self.score.setWordWrap(True)
        self.score.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.score.setObjectName(
            "analyticsMeanTrajectoryBrier" if self.adaptive else "oneShotMeanBrier"
        )
        apply_text_role(self.score, TextRole.FORECAST)
        self.count = _label("", metrics)
        self.count.setObjectName(
            "trajectoryAnalyticsScoredCount" if self.adaptive else "oneShotBinaryCount"
        )
        for title, value in (
            ("Mean Trajectory Brier" if self.adaptive else "Mean Brier", self.score),
            (
                "Eligible resolved" if self.adaptive else "Answered predictions",
                self.count,
            ),
        ):
            column = QWidget(metrics)
            layout = QVBoxLayout(column)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(_label(title, column))
            layout.addWidget(value)
            metrics_layout.addWidget(column, 1, Qt.AlignmentFlag.AlignTop)
        self.results_layout.addWidget(metrics)
        self.guidance = _label("", self.results)
        self.results_layout.addWidget(self.guidance)
        title = (
            "Final-probability calibration"
            if self.adaptive
            else "Probability calibration"
        )
        self.chart_title = _label(title, self.results)
        apply_text_role(self.chart_title, TextRole.LABEL)
        self.results_layout.addWidget(self.chart_title)
        self.chart = CalibrationChart(self.results, scatter=True)
        self.chart.setObjectName(
            "trajectoryFinalCalibrationChart"
            if self.adaptive
            else "oneShotBinaryCalibrationChart"
        )
        self.chart.setMinimumHeight(240)
        self.table = _table(
            (
                "Probability\nbin",
                "Count",
                "Mean\nforecast",
                "Observed\nYes",
                "95% Wilson\nfor Yes",
            ),
            10,
            "trajectoryFinalCalibrationBinTable"
            if self.adaptive
            else "oneShotBinaryCalibrationTable",
            self.results,
        )
        self.comparison = _ResponsiveChartTable(
            self.chart,
            self.table,
            object_name="trajectoryFinalCalibrationComparison"
            if self.adaptive
            else "oneShotBinaryCalibrationComparison",
            parent=self.results,
            collapsible_table=True,
        )
        self.results_layout.addWidget(self.comparison)
        self.caveat = _label(
            "Bars show pointwise 95% Wilson intervals for observed Yes. Small bin counts mean wide uncertainty; this does not prove forecasting skill. Lower Brier is better.",
            self.results,
        )
        self.results_layout.addWidget(self.caveat)
        self.diagnostics = _label("", self.results)
        self.diagnostics_section = collapse_section(
            self.diagnostics, "Timing and updating diagnostics"
        )
        self.results_layout.addWidget(self.diagnostics_section)
        self.diagnostics_section.setVisible(self.adaptive)

    def render(self, result: SectionResult) -> None:
        data = result.data
        assert isinstance(data, (TrajectoryAnalyticsSnapshot, OneShotBinaryAnalytics))
        if isinstance(data, TrajectoryAnalyticsSnapshot):
            count = data.scored_prediction_count
            mean = data.mean_trajectory_brier
            bins = data.final_calibration_bins
            self.guidance.setText(
                f"{data.unscored_prediction_count} unscored · final probabilities are a separate diagnostic, not the trajectory score."
                if data.unscored_prediction_count
                else "One equal vote per eligible prediction. Calibration uses final probabilities; neutral truncation adds no observation."
            )
            weight = data.mean_active_forecast_fraction
            self.diagnostics.setText(
                f"Resolved before deadline: {data.early_resolution_count}\nReached deadline: {data.reached_deadline_count}\n"
                + (
                    f"Average forecast weight: {float(weight):.1%} · neutral weight: {float(1 - weight):.1%}\n"
                    if weight is not None
                    else ""
                )
                + f"Mean initial Brier: {score_text(data.mean_initial_brier)}\nMean final Brier: {score_text(data.mean_final_brier)}\nMean hold-initial trajectory: {score_text(data.mean_hold_initial_brier)}\nMean Updating Gain: {score_text(data.mean_updating_gain, signed=True)}\n"
                + f"Updating: {data.positive_updating_gain_count} helped · {data.equal_updating_gain_count} tied · {data.negative_updating_gain_count} hurt mechanically.\n"
                + "Forecast/neutral weights belong to each planned initial-to-deadline interval; neutral contribution is 0.25 after early resolution. These weights are not time spent in the app. Updating Gain is hindsight, not causal evidence."
            )
        else:
            count, mean, bins = (
                data.resolved_count,
                data.mean_brier,
                data.calibration_bins,
            )
            self.guidance.setText(
                "One observation per answered exercise. Selective entry can bias the record; include misses as well as hits."
            )
        self.score.setText(score_text(mean))
        self.count.setText(str(count))
        self.score.setAccessibleName(
            f"{TITLES[self.section]} mean score: {self.score.text()}"
        )
        self.comparison.setVisible(bool(count))
        self.chart_title.setVisible(bool(count))
        self.caveat.setVisible(bool(count))
        if not count:
            self.guidance.setText(
                "No eligible resolved predictions match this scope."
                if self.adaptive
                else "No answered One-Shot predictions match this scope."
            )
        self.chart.set_bins(
            bins, intervals=tuple(p.wilson_95 for p in result.observed_yes)
        )
        descriptions = []
        for index, (band, observed) in enumerate(
            zip(bins, result.observed_yes, strict=True)
        ):
            values = (
                band.label,
                str(band.count),
                "Not available"
                if band.mean_forecast_percent is None
                else f"{band.mean_forecast_percent:.1f}%",
                "Not available"
                if band.observed_yes_percent is None
                else f"{band.observed_yes_percent:.1f}%",
                uncertainty_text(observed),
            )
            _row(self.table, index, values)
            descriptions.append(" · ".join(values))
        self.table.setAccessibleDescription("; ".join(descriptions))
        self.chart.setAccessibleDescription(
            self.chart.accessibleDescription()
            + ". 95% Wilson uncertainty: "
            + "; ".join(descriptions)
        )
        _fit(self.table)

    def reset_disclosures(self) -> None:
        super().reset_disclosures()
        self.comparison.table_toggle.setChecked(False)


class BalanceBar(QWidget):
    """Paint existing outcome counts; the full text remains alongside the bar."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.parts = (0, 0, 0)
        self.accent_index = 1
        self.setFixedHeight(8)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        colors = semantic_colors(self.palette())
        total = sum(self.parts)
        x = 0.0
        for index, count in enumerate(self.parts):
            color = colors.accent if index == self.accent_index else colors.border
            width = self.width() * count / total if total else 0
            painter.fillRect(QRectF(x, 0, width, self.height()), QColor(color))
            x += width


class BalanceSummary(QWidget):
    def __init__(self, title: str, *, median: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.median = median
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        heading = QHBoxLayout()
        caption = _label(title, self)
        apply_text_role(caption, TextRole.LABEL)
        self.value = _label("", self)
        apply_text_role(self.value, TextRole.LABEL)
        heading.addWidget(caption, 1)
        heading.addWidget(self.value)
        layout.addLayout(heading)
        self.bar = BalanceBar(self)
        self.bar.accent_index = 0 if median else 1
        self.counts = _label("", self)
        self.uncertainty = _label("", self)
        layout.addWidget(self.bar)
        layout.addWidget(self.counts)
        layout.addWidget(self.uncertainty)

    def render(self, balance: OutcomeBalance) -> None:
        main = balance.below if self.median else balance.inside
        self.value.setText(
            f"{100 * float(main.fraction):.1f}% "
            + ("below" if self.median else "inside")
        )
        self.counts.setText(
            f"{balance.below.count} below · {balance.inside.count} "
            + ("equal" if self.median else "inside (inclusive)")
            + f" · {balance.above.count} above"
        )
        self.uncertainty.setText(
            ("Below" if self.median else "Inside")
            + ": 95% Wilson "
            + uncertainty_text(main)
        )
        self.bar.parts = (
            balance.below.count,
            balance.inside.count,
            balance.above.count,
        )
        self.bar.setAccessibleDescription(self.counts.text())
        self.bar.update()


class CalibrationSummary(QWidget):
    def __init__(self, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.ORDINARY))
        self.heading = _label(title, self)
        apply_text_role(self.heading, TextRole.LABEL)
        layout.addWidget(self.heading)
        self.values = (
            BalanceSummary("90% interval", median=False, parent=self),
            BalanceSummary("Median", median=True, parent=self),
            BalanceSummary("50% interval", median=False, parent=self),
        )
        for value in self.values:
            layout.addWidget(value)

    def render(self, group: QuantileCalibrationGroup) -> None:
        title = (
            "Whole-number"
            if group.value_constraint is NumericValueConstraint.WHOLE_NUMBER
            else "Continuous-style"
        )
        self.heading.setText(
            f"{title} · {group.sample_size} eligible"
            if group.sample_size
            else f"{title} · No eligible results"
        )
        for widget, balance in zip(
            self.values,
            (group.interval_90, group.median, group.interval_50),
            strict=True,
        ):
            widget.setVisible(bool(group.sample_size))
            if group.sample_size:
                widget.render(balance)


class NumericSection(ReportSection):
    unit_changed = Signal(object)

    def __init__(self, section: Section, parent: QWidget) -> None:
        super().__init__(section, parent)
        self.adaptive = section is Section.ADAPTIVE_NUMERIC
        heading = self.title_label.parentWidget()
        units = QWidget(heading)
        row = QHBoxLayout(units)
        row.setContentsMargins(0, 0, 0, 0)
        unit_label = _label("Unit", units)
        self.unit_filter = QComboBox(units)
        self.unit_filter.setAccessibleName(f"{TITLES[section]} exact unit")
        self.unit_filter.setObjectName(f"{section}UnitFilter")
        self.unit_filter.setMinimumContentsLength(10)
        self.unit_filter.setMaximumWidth(210)
        self.unit_filter.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.unit_filter.addItem("All units", None)
        unit_label.setBuddy(self.unit_filter)
        row.addWidget(unit_label)
        row.addWidget(self.unit_filter, 1)
        heading.layout().addWidget(units)
        self.unit_filter.currentIndexChanged.connect(
            lambda: self.unit_changed.emit(self.unit_filter.currentData())
        )
        self.summary = _label("", self.results)
        self.results_layout.addWidget(self.summary)
        self.continuous_summary = CalibrationSummary("Continuous-style", self.results)
        self.whole_summary = CalibrationSummary("Whole-number", self.results)
        self.results_layout.addWidget(self.continuous_summary)
        self.results_layout.addWidget(self.whole_summary)
        self.caveat = _label(
            "Read small samples cautiously. WIS remains an individual prediction score; raw WIS/Delta is never pooled. Whole-number ties are retained; interval coverage above nominal need not imply miscalibration.",
            self.results,
        )
        self.results_layout.addWidget(self.caveat)
        supporting = QWidget(self.results)
        layout = QVBoxLayout(supporting)
        layout.setContentsMargins(0, 0, 0, 0)
        prefix = "adaptive" if self.adaptive else "oneShot"
        self.continuous = QuantileCalibrationPanel(
            whole=False, parent=supporting, name_prefix=prefix
        )
        self.whole_number = QuantileCalibrationPanel(
            whole=True, parent=supporting, name_prefix=prefix
        )
        layout.addWidget(self.continuous)
        layout.addWidget(self.whole_number)
        self.supporting = collapse_section(
            supporting, "Percentile calibration and tables"
        )
        self.results_layout.addWidget(self.supporting)
        self.updates = _label("", self.results)
        self.update_section = collapse_section(self.updates, "Updating diagnostics")
        self.update_section.setVisible(self.adaptive)
        self.results_layout.addWidget(self.update_section)

    def render(self, result: SectionResult) -> None:
        data = result.data
        assert isinstance(data, (QuantileAnalyticsSnapshot, OneShotNumericAnalytics))
        if isinstance(data, QuantileAnalyticsSnapshot):
            self.summary.setText(
                f"{data.scored_prediction_count} eligible · {data.resolved_candidate_count} resolved · {data.unscored_prediction_count} unscored"
            )
            self.updates.setText(
                f"Better: {proportion_text(data.better)} · Equal: {proportion_text(data.equal)} · Worse: {proportion_text(data.worse)}\n{data.unrevised_count} unrevised (not counted as ties).\n"
                + "Direction only, without raw WIS/Delta averaging. Mechanical hindsight does not show that updating caused skill. Counts lose magnitude.\n"
                + "95% Wilson: better "
                + uncertainty_text(data.better)
                + "; equal "
                + uncertainty_text(data.equal)
                + "; worse "
                + uncertainty_text(data.worse)
            )
        else:
            self.summary.setText(f"{data.resolved_count} answered Numeric One-Shots")
        self.continuous_summary.render(data.continuous)
        self.whole_summary.render(data.whole_number)
        self.continuous.render(data.continuous)
        self.whole_number.render(data.whole_number)
