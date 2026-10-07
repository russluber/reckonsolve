"""One-Shot Analytics presentation; calculations arrive in a derived snapshot."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from reckonsolve.analytics.one_shot_aggregate import OneShotAnalyticsSnapshot
from reckonsolve.domain.predictions import PredictionType

from .analytics_charts import CalibrationChart
from .analytics_components import (
    AnalyticsPanel,
    CompactMetricGroup,
    _ResponsiveChartTable,
)
from .quantile_analytics import (
    QuantileCalibrationPanel,
    _fit,
    _label,
    _row,
    _table,
    uncertainty_text,
)
from .visual_system import Spacing


class OneShotAnalyticsView(QWidget):
    """One collection with distinct Binary and Numeric results and text alternatives."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("oneShotAnalytics")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.SECTION))
        self.introduction = AnalyticsPanel(
            "One-Shot Analytics",
            "One effective forecast and answer per resolved Prediction. "
            "These results are separate from Adaptive analytics.",
            parent=self,
        )
        self.caution = _label(
            "One observation per answered One-Shot. External notes rely on your record; "
            "selectively entering exercises can bias these results. Include misses as well as hits.",
            self.introduction.body,
        )
        self.caution.setObjectName("oneShotAnalyticsCaution")
        self.introduction.body_layout.addWidget(self.caution)
        layout.addWidget(self.introduction)

        self.binary_panel = AnalyticsPanel(
            "Binary One-Shot",
            "Ordinary Brier gives each answered Prediction one equal vote. Lower is better.",
            parent=self,
        )
        self.binary_panel.setObjectName("oneShotBinaryAnalytics")
        metrics = CompactMetricGroup("Score", parent=self.binary_panel.body)
        self.mean_brier = metrics.add_metric(
            "Mean Brier", "oneShotMeanBrier", primary=True
        )
        self.binary_count = metrics.add_metric(
            "Answered Predictions", "oneShotBinaryCount"
        )
        self.binary_panel.body_layout.addWidget(metrics)
        self.binary_guidance = _label("", self.binary_panel.body)
        self.binary_guidance.setObjectName("oneShotBinaryGuidance")
        self.binary_panel.body_layout.addWidget(self.binary_guidance)
        self.chart = CalibrationChart(self.binary_panel.body, scatter=True)
        self.chart.setObjectName("oneShotBinaryCalibrationChart")
        self.table = _table(
            (
                "Probability\nbin",
                "Count",
                "Mean\nforecast",
                "Observed\nYes",
                "95% Wilson\nfor Yes",
            ),
            10,
            "oneShotBinaryCalibrationTable",
            self.binary_panel.body,
        )
        self.comparison = _ResponsiveChartTable(
            self.chart,
            self.table,
            object_name="oneShotBinaryCalibrationComparison",
            parent=self.binary_panel.body,
        )
        self.binary_panel.body_layout.addWidget(self.comparison)
        self.binary_panel.set_help_text(
            "Bins are 0–9%, 10–19%, through 90–100%. Diamonds show occupied bins; "
            "empty bins have no invented means. The table gives pointwise 95% Wilson "
            "intervals for observed Yes frequency. Sparse samples are uncertain; these intervals "
            "do not measure uncertainty in mean Brier or prove forecasting skill."
        )
        layout.addWidget(self.binary_panel)

        self.numeric_panel = AnalyticsPanel(
            "Numeric One-Shot",
            "Calibration uses the five saved percentiles and inclusive 50% and 90% intervals. "
            "WIS remains an individual Prediction score; raw WIS is not averaged across questions.",
            parent=self,
        )
        self.numeric_panel.setObjectName("oneShotNumericAnalytics")
        self.numeric_summary = _label("", self.numeric_panel.body)
        self.numeric_summary.setObjectName("oneShotNumericCount")
        self.numeric_panel.body_layout.addWidget(self.numeric_summary)
        layout.addWidget(self.numeric_panel)
        self.continuous = QuantileCalibrationPanel(
            whole=False, parent=self, name_prefix="oneShot"
        )
        self.whole_number = QuantileCalibrationPanel(
            whole=True, parent=self, name_prefix="oneShot"
        )
        layout.addWidget(self.continuous)
        layout.addWidget(self.whole_number)

    def render(self, snapshot: OneShotAnalyticsSnapshot) -> None:
        show_binary = snapshot.selected_type in (None, PredictionType.BINARY)
        show_numeric = snapshot.selected_type in (None, PredictionType.NUMERIC)
        self.binary_panel.setVisible(show_binary)
        self.numeric_panel.setVisible(show_numeric)
        self.continuous.setVisible(show_numeric)
        self.whole_number.setVisible(show_numeric)
        binary = snapshot.binary
        self.binary_panel.set_count(binary.resolved_count)
        self.binary_count.setText(str(binary.resolved_count))
        self.mean_brier.setText(
            "Not available"
            if binary.mean_brier is None
            else f"{float(binary.mean_brier):.3f}"
        )
        self.mean_brier.setAccessibleName(
            f"Mean One-Shot Brier: {self.mean_brier.text()}"
        )
        self.binary_guidance.setText(
            "No answered Binary One-Shots match these filters."
            if not binary.resolved_count
            else "Small samples are uncertain. Read each bin together with its count and uncertainty."
        )
        self.comparison.setVisible(bool(binary.resolved_count))
        self.chart.set_bins(binary.calibration_bins)
        details = []
        for index, (band, observed) in enumerate(
            zip(binary.calibration_bins, binary.observed_yes, strict=True)
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
            details.append(" · ".join(values))
        self.table.setAccessibleDescription("; ".join(details))
        self.chart.setAccessibleDescription(
            self.chart.accessibleDescription()
            + ". Table uncertainty: "
            + "; ".join(details)
        )
        _fit(self.table)
        numeric = snapshot.numeric
        self.numeric_panel.set_count(numeric.resolved_count)
        self.numeric_summary.setText(
            f"{numeric.resolved_count} answered Numeric One-Shots"
            if numeric.resolved_count
            else "No answered Numeric One-Shots match these filters."
        )
        self.continuous.render(numeric.continuous)
        self.whole_number.render(numeric.whole_number)
