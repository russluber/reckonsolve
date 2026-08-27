"""Type-aware Binary and Numeric scoring analytics screen."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.analytics import (
    AnalyticsSnapshot,
    BinaryUpdateAnalyticsSnapshot,
    ForecastAnalyticsSnapshot,
    NumericAnalyticsSnapshot,
    NumericUnitSummary,
    NumericUnitUpdateSummary,
    NumericUpdateAnalyticsSnapshot,
)
from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.predictions import PredictionType
from reckonsolve.ui.analytics_charts import (
    BrierTrendChart,
    CalibrationChart,
    ContainmentCalibrationChart,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon


class AnalyticsOperations(Protocol):
    """Application query used by the aggregate Analytics screen."""

    def get_forecast_analytics(
        self,
        *,
        prediction_type: PredictionType | None = None,
        tag: str | None = None,
        unit: str | None = None,
    ) -> ForecastAnalyticsSnapshot:
        """Return separate type-aware views for one common filter subset."""


class AnalyticsScreen(QWidget):
    """Display Binary scoring and Numeric interval performance separately."""

    def __init__(
        self,
        operations: AnalyticsOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsScreen")
        self._operations = operations
        self._loaded_snapshot: ForecastAnalyticsSnapshot | None = None

        title = QLabel("Analytics", self)
        title.setObjectName("analyticsScreenTitle")

        introduction = QLabel(
            "Each resolved prediction contributes exactly one captured final "
            "forecast. Binary and Numeric scores remain separate; Invalid and "
            "unresolved predictions are excluded.",
            self,
        )
        introduction.setObjectName("analyticsIntroduction")
        introduction.setWordWrap(True)
        introduction.setTextFormat(Qt.TextFormat.PlainText)

        type_label = QLabel("Forecast type", self)
        self.type_filter = QComboBox(self)
        self.type_filter.setObjectName("analyticsTypeFilter")
        self.type_filter.setAccessibleName("Filter analytics by forecast type")
        self.type_filter.addItem("All types", None)
        self.type_filter.addItem("Binary", PredictionType.BINARY.value)
        self.type_filter.addItem("Numeric", PredictionType.NUMERIC.value)
        type_label.setBuddy(self.type_filter)

        tag_label = QLabel("Tag", self)
        self.tag_filter = QComboBox(self)
        self.tag_filter.setObjectName("analyticsTagFilter")
        self.tag_filter.setAccessibleName("Filter analytics by tag")
        self.tag_filter.addItem("All tags", None)
        tag_label.setBuddy(self.tag_filter)

        unit_label = QLabel("Numeric unit", self)
        self.unit_filter = QComboBox(self)
        self.unit_filter.setObjectName("analyticsUnitFilter")
        self.unit_filter.setAccessibleName("Filter Numeric analytics by exact unit")
        self.unit_filter.addItem("All units", None)
        self.unit_filter.setEnabled(False)
        self.unit_filter.setToolTip(
            "Choose Numeric forecast type to enable exact-unit scoring."
        )
        unit_label.setBuddy(self.unit_filter)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("refreshAnalyticsButton")
        apply_lucide_icon(self.refresh_button, LucideIcon.REFRESH)

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(type_label)
        filter_layout.addWidget(self.type_filter)
        filter_layout.addWidget(tag_label)
        filter_layout.addWidget(self.tag_filter)
        filter_layout.addWidget(unit_label)
        filter_layout.addWidget(self.unit_filter)
        filter_layout.addWidget(self.refresh_button)
        filter_layout.addStretch()

        self.error_label = QLabel(self)
        self.error_label.setObjectName("analyticsError")
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.setHidden(True)

        self.summary = self._create_binary_summary()
        self.numeric_summary = self._create_numeric_summary()

        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("analyticsEmpty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setTextFormat(Qt.TextFormat.PlainText)
        self.empty_label.setHidden(True)

        content = QWidget(self)
        content.setObjectName("analyticsContent")
        content_layout = QVBoxLayout(content)
        self.binary_content = self._create_binary_content(content)
        self.numeric_content = self._create_numeric_content(content)
        self.binary_update_content = self._create_binary_update_content(content)
        self.numeric_update_content = self._create_numeric_update_content(content)
        content_layout.addWidget(self.binary_content)
        content_layout.addWidget(self.numeric_content)
        content_layout.addWidget(self.binary_update_content)
        content_layout.addWidget(self.numeric_update_content)
        content_layout.addStretch()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("analyticsScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(content)
        self.scroll_area.setHidden(True)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(introduction)
        layout.addLayout(filter_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(self.summary)
        layout.addWidget(self.numeric_summary)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.scroll_area, 1)

        self.type_filter.currentIndexChanged.connect(self._forecast_type_changed)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.unit_filter.currentIndexChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)

    def _create_binary_summary(self) -> QGroupBox:
        summary = QGroupBox("Binary forecasts — Brier score", self)
        summary.setObjectName("analyticsBrierSummary")
        summary_layout = QVBoxLayout(summary)
        self.scored_count = QLabel("Scored predictions: loading...", summary)
        self.scored_count.setObjectName("analyticsScoredCount")
        self.scored_count.setTextFormat(Qt.TextFormat.PlainText)
        self.mean_brier = QLabel("Mean Brier: loading...", summary)
        self.mean_brier.setObjectName("analyticsMeanBrier")
        self.mean_brier.setTextFormat(Qt.TextFormat.PlainText)
        direction = QLabel(
            "Lower is better. A perfect Binary forecast scores 0; a maximally "
            "wrong forecast scores 1.",
            summary,
        )
        direction.setObjectName("analyticsBrierDirection")
        direction.setWordWrap(True)
        direction.setTextFormat(Qt.TextFormat.PlainText)
        summary_layout.addWidget(self.scored_count)
        summary_layout.addWidget(self.mean_brier)
        summary_layout.addWidget(direction)
        summary.setHidden(True)
        return summary

    def _create_numeric_summary(self) -> QGroupBox:
        summary = QGroupBox("Numeric forecasts", self)
        summary.setObjectName("numericAnalyticsSummary")
        summary_layout = QVBoxLayout(summary)
        self.numeric_scored_count = QLabel(
            "Scored Numeric Predictions: loading...",
            summary,
        )
        self.numeric_scored_count.setObjectName("numericAnalyticsScoredCount")
        self.numeric_containment = QLabel("Contained outcomes: loading...", summary)
        self.numeric_containment.setObjectName("numericAnalyticsContainment")
        self.numeric_raw_scope = QLabel(summary)
        self.numeric_raw_scope.setObjectName("numericAnalyticsRawScope")
        self.numeric_raw_scope.setWordWrap(True)
        self.numeric_median_error = QLabel(summary)
        self.numeric_median_error.setObjectName("numericMeanMedianAbsoluteError")
        self.numeric_interval_width = QLabel(summary)
        self.numeric_interval_width.setObjectName("numericMeanIntervalWidth")
        self.numeric_interval_score = QLabel(summary)
        self.numeric_interval_score.setObjectName("numericMeanIntervalScore")
        self.numeric_score_guidance = QLabel(
            "Median absolute error measures the central estimate's miss. Interval "
            "width measures range breadth. Interval score balances narrowness and "
            "miss penalties; lower is better.",
            summary,
        )
        self.numeric_score_guidance.setObjectName("numericScoreGuidance")
        self.numeric_score_guidance.setWordWrap(True)
        for label in (
            self.numeric_scored_count,
            self.numeric_containment,
            self.numeric_raw_scope,
            self.numeric_median_error,
            self.numeric_interval_width,
            self.numeric_interval_score,
            self.numeric_score_guidance,
        ):
            label.setTextFormat(Qt.TextFormat.PlainText)
            summary_layout.addWidget(label)
        summary.setHidden(True)
        return summary

    def _create_binary_content(self, parent: QWidget) -> QGroupBox:
        section = QGroupBox("Binary calibration and performance", parent)
        section.setObjectName("binaryAnalyticsSection")
        section_layout = QVBoxLayout(section)

        calibration_group = QGroupBox("Calibration / reliability", section)
        calibration_group.setObjectName("analyticsCalibrationSection")
        calibration_layout = QVBoxLayout(calibration_group)
        explanation = QLabel(
            "The diagonal is perfect calibration. Points use each occupied "
            "bin's actual mean forecast and observed Yes frequency.",
            calibration_group,
        )
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        self.calibration_chart = CalibrationChart(calibration_group)
        self.calibration_table = _new_bin_table(
            calibration_group,
            object_name="calibrationBinTable",
            accessible_name="Calibration bins, counts, forecasts, and outcomes",
            headers=("Probability bin", "Count", "Mean forecast", "Observed Yes"),
        )
        calibration_layout.addWidget(explanation)
        calibration_layout.addWidget(self.calibration_chart)
        calibration_layout.addWidget(self.calibration_table)

        trend_group = QGroupBox("Cumulative mean Brier by resolution time", section)
        trend_group.setObjectName("analyticsBrierTrendSection")
        trend_layout = QVBoxLayout(trend_group)
        trend_explanation = QLabel(
            "Each point includes every Binary Prediction resolved up to that time. "
            "Movement does not by itself prove skill improvement because forecast "
            "difficulty and composition can change.",
            trend_group,
        )
        trend_explanation.setObjectName("analyticsTrendExplanation")
        trend_explanation.setWordWrap(True)
        trend_explanation.setTextFormat(Qt.TextFormat.PlainText)
        self.brier_trend_chart = BrierTrendChart(trend_group)
        trend_layout.addWidget(trend_explanation)
        trend_layout.addWidget(self.brier_trend_chart)

        section_layout.addWidget(calibration_group)
        section_layout.addWidget(trend_group)
        return section

    def _create_numeric_content(self, parent: QWidget) -> QGroupBox:
        section = QGroupBox("Numeric containment calibration", parent)
        section.setObjectName("numericAnalyticsSection")
        section_layout = QVBoxLayout(section)
        explanation = QLabel(
            "Containment asks whether the actual value fell inside the inclusive "
            "interval. Confidence and containment are unitless, so this calibration "
            "may combine units. Treat small bin counts as sparse evidence.",
            section,
        )
        explanation.setObjectName("numericCalibrationExplanation")
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        self.containment_chart = ContainmentCalibrationChart(section)
        self.containment_table = _new_bin_table(
            section,
            object_name="containmentCalibrationBinTable",
            accessible_name=(
                "Numeric confidence bins, counts, mean confidence, and containment"
            ),
            headers=(
                "Confidence bin",
                "Count",
                "Mean confidence",
                "Observed containment",
            ),
        )
        section_layout.addWidget(explanation)
        section_layout.addWidget(self.containment_chart)
        section_layout.addWidget(self.containment_table)
        return section

    def _create_binary_update_content(self, parent: QWidget) -> QGroupBox:
        section = QGroupBox("Binary retrospective update feedback", parent)
        section.setObjectName("binaryUpdateAnalyticsSection")
        section_layout = QVBoxLayout(section)
        explanation = QLabel(
            "This compares revision 1 with the exact final scoring revision for "
            "each revised-and-resolved Binary Prediction. It is descriptive "
            "hindsight, not proof that updating caused improvement.",
            section,
        )
        explanation.setObjectName("binaryUpdateAnalyticsExplanation")
        explanation.setWordWrap(True)
        self.binary_update_paired_count = QLabel(section)
        self.binary_update_paired_count.setObjectName("binaryUpdatePairedCount")
        self.binary_update_unrevised_count = QLabel(section)
        self.binary_update_unrevised_count.setObjectName("binaryUpdateUnrevisedCount")
        self.binary_update_initial_brier = QLabel(section)
        self.binary_update_initial_brier.setObjectName("binaryUpdateInitialBrier")
        self.binary_update_final_brier = QLabel(section)
        self.binary_update_final_brier.setObjectName("binaryUpdateFinalBrier")
        self.binary_update_improvement = QLabel(section)
        self.binary_update_improvement.setObjectName("binaryUpdateImprovement")
        self.binary_update_guidance = QLabel(section)
        self.binary_update_guidance.setObjectName("binaryUpdateGuidance")
        self.binary_update_guidance.setWordWrap(True)
        for label in (
            explanation,
            self.binary_update_paired_count,
            self.binary_update_unrevised_count,
            self.binary_update_initial_brier,
            self.binary_update_final_brier,
            self.binary_update_improvement,
            self.binary_update_guidance,
        ):
            label.setTextFormat(Qt.TextFormat.PlainText)
            section_layout.addWidget(label)
        return section

    def _create_numeric_update_content(self, parent: QWidget) -> QGroupBox:
        section = QGroupBox("Numeric retrospective update feedback", parent)
        section.setObjectName("numericUpdateAnalyticsSection")
        section_layout = QVBoxLayout(section)
        explanation = QLabel(
            "This compares revision 1 with the exact final scoring revision for "
            "each revised-and-resolved Numeric Prediction. Confidence and "
            "containment may combine units; raw comparisons require one exact unit.",
            section,
        )
        explanation.setObjectName("numericUpdateAnalyticsExplanation")
        explanation.setWordWrap(True)
        self.numeric_update_paired_count = QLabel(section)
        self.numeric_update_paired_count.setObjectName("numericUpdatePairedCount")
        self.numeric_update_unrevised_count = QLabel(section)
        self.numeric_update_unrevised_count.setObjectName("numericUpdateUnrevisedCount")
        self.numeric_update_initial_confidence = QLabel(section)
        self.numeric_update_initial_confidence.setObjectName(
            "numericUpdateInitialConfidence"
        )
        self.numeric_update_final_confidence = QLabel(section)
        self.numeric_update_final_confidence.setObjectName(
            "numericUpdateFinalConfidence"
        )
        self.numeric_update_initial_containment = QLabel(section)
        self.numeric_update_initial_containment.setObjectName(
            "numericUpdateInitialContainment"
        )
        self.numeric_update_final_containment = QLabel(section)
        self.numeric_update_final_containment.setObjectName(
            "numericUpdateFinalContainment"
        )
        self.numeric_update_raw_scope = QLabel(section)
        self.numeric_update_raw_scope.setObjectName("numericUpdateRawScope")
        self.numeric_update_raw_scope.setWordWrap(True)
        self.numeric_update_median_error = QLabel(section)
        self.numeric_update_median_error.setObjectName("numericUpdateMedianError")
        self.numeric_update_width = QLabel(section)
        self.numeric_update_width.setObjectName("numericUpdateWidth")
        self.numeric_update_interval_score = QLabel(section)
        self.numeric_update_interval_score.setObjectName("numericUpdateIntervalScore")
        self.numeric_update_guidance = QLabel(section)
        self.numeric_update_guidance.setObjectName("numericUpdateGuidance")
        self.numeric_update_guidance.setWordWrap(True)
        for label in (
            explanation,
            self.numeric_update_paired_count,
            self.numeric_update_unrevised_count,
            self.numeric_update_initial_confidence,
            self.numeric_update_final_confidence,
            self.numeric_update_initial_containment,
            self.numeric_update_final_containment,
            self.numeric_update_raw_scope,
            self.numeric_update_median_error,
            self.numeric_update_width,
            self.numeric_update_interval_score,
            self.numeric_update_guidance,
        ):
            label.setTextFormat(Qt.TextFormat.PlainText)
            section_layout.addWidget(label)
        return section

    def refresh(self) -> None:
        """Reload one coherent analytical subset and preserve honest error state."""

        prediction_type = self._selected_type()
        selected_tag = self._selected_tag()
        selected_unit = self._selected_unit()
        try:
            snapshot = self._operations.get_forecast_analytics(
                prediction_type=prediction_type,
                tag=selected_tag,
                unit=selected_unit,
            )
            if selected_tag is not None and selected_tag.casefold() not in {
                item.casefold() for item in snapshot.available_tags
            }:
                with QSignalBlocker(self.tag_filter):
                    self.tag_filter.setCurrentIndex(0)
                snapshot = self._operations.get_forecast_analytics(
                    prediction_type=prediction_type,
                    tag=None,
                    unit=selected_unit,
                )
            if (
                selected_unit is not None
                and selected_unit not in snapshot.available_units
            ):
                with QSignalBlocker(self.unit_filter):
                    self.unit_filter.setCurrentIndex(0)
                snapshot = self._operations.get_forecast_analytics(
                    prediction_type=prediction_type,
                    tag=self._selected_tag(),
                    unit=None,
                )
        except ApplicationError as error:
            if self._loaded_snapshot is None:
                self.error_label.setText(f"Analytics unavailable. {error}")
                self.summary.setHidden(True)
                self.numeric_summary.setHidden(True)
                self.empty_label.setHidden(True)
                self.scroll_area.setHidden(True)
            else:
                self.error_label.setText(
                    "Analytics could not refresh; showing the last loaded results. "
                    f"{error}"
                )
            self.error_label.setHidden(False)
            return

        self.error_label.setHidden(True)
        self._loaded_snapshot = snapshot
        self._update_tag_choices(snapshot.available_tags)
        self._update_unit_choices(snapshot.available_units)
        self._render(snapshot)

    def _forecast_type_changed(self) -> None:
        numeric_selected = self._selected_type() is PredictionType.NUMERIC
        with QSignalBlocker(self.unit_filter):
            if not numeric_selected:
                self.unit_filter.setCurrentIndex(0)
            self.unit_filter.setEnabled(numeric_selected)
        self.refresh()

    def _render(self, snapshot: ForecastAnalyticsSnapshot) -> None:
        show_binary = snapshot.selected_type in (None, PredictionType.BINARY)
        show_numeric = snapshot.selected_type in (None, PredictionType.NUMERIC)
        self.summary.setHidden(not show_binary)
        self.numeric_summary.setHidden(not show_numeric)
        self.binary_content.setHidden(not show_binary)
        self.numeric_content.setHidden(not show_numeric)
        self.binary_update_content.setHidden(not show_binary)
        self.numeric_update_content.setHidden(not show_numeric)
        if show_binary:
            self._render_binary(snapshot.binary)
            self._render_binary_updates(snapshot.binary_updates)
        if show_numeric:
            self._render_numeric(snapshot.numeric)
            self._render_numeric_updates(snapshot.numeric_updates)

        count = (snapshot.binary.scored_prediction_count if show_binary else 0) + (
            snapshot.numeric.scored_prediction_count if show_numeric else 0
        )
        if count == 0:
            self.scroll_area.setHidden(True)
            self.empty_label.setText(self._empty_message(snapshot.selected_type))
            self.empty_label.setHidden(False)
        else:
            self.empty_label.setHidden(True)
            self.scroll_area.setHidden(False)

    def _render_binary(self, snapshot: AnalyticsSnapshot) -> None:
        self.scored_count.setText(
            f"Scored predictions: {snapshot.scored_prediction_count}"
        )
        self.mean_brier.setText(
            "Mean Brier: Not available"
            if snapshot.mean_brier is None
            else f"Mean Brier: {snapshot.mean_brier:.3f}"
        )
        self.calibration_chart.set_bins(snapshot.calibration_bins)
        self.brier_trend_chart.set_points(snapshot.brier_trend)
        for row, calibration_bin in enumerate(snapshot.calibration_bins):
            _set_table_row(
                self.calibration_table,
                row,
                (
                    calibration_bin.label,
                    str(calibration_bin.count),
                    _optional_percent(calibration_bin.mean_forecast_percent),
                    _optional_percent(calibration_bin.observed_yes_percent),
                ),
            )

    def _render_numeric(self, snapshot: NumericAnalyticsSnapshot) -> None:
        count = snapshot.scored_prediction_count
        contained_count = sum(item.contained for item in snapshot.scored_predictions)
        self.numeric_scored_count.setText(f"Scored Numeric Predictions: {count}")
        self.numeric_containment.setText(
            "Contained outcomes: Not available"
            if count == 0
            else (
                f"Contained outcomes: {contained_count} of {count} "
                f"({_format_percent(100 * contained_count / count)})"
            )
        )
        summary = snapshot.unit_summary
        if snapshot.selected_unit is None:
            self.numeric_raw_scope.setText(
                "Choose Numeric forecast type and one exact unit to compare median "
                "error, interval width, and interval score. Reckonsolve will not "
                "average unlike units."
            )
            self._set_raw_metrics(None)
        elif summary is None:
            self.numeric_raw_scope.setText(
                f"No scored Numeric Predictions match unit: {snapshot.selected_unit}."
            )
            self._set_raw_metrics(None)
        else:
            self.numeric_raw_scope.setText(
                f"Raw averages below use {summary.count} scored Prediction(s) with "
                f"the exact unit: {summary.unit}. Lower interval score is better."
            )
            self._set_raw_metrics(summary)

        self.containment_chart.set_bins(snapshot.calibration_bins)
        for row, calibration_bin in enumerate(snapshot.calibration_bins):
            _set_table_row(
                self.containment_table,
                row,
                (
                    calibration_bin.label,
                    str(calibration_bin.count),
                    _optional_percent(calibration_bin.mean_confidence_percent),
                    _optional_percent(calibration_bin.observed_containment_percent),
                ),
            )

    def _set_raw_metrics(self, summary: NumericUnitSummary | None) -> None:
        if summary is None:
            self.numeric_median_error.setText(
                "Mean median absolute error: Not available"
            )
            self.numeric_interval_width.setText("Mean interval width: Not available")
            self.numeric_interval_score.setText("Mean interval score: Not available")
            return
        unit = summary.unit
        self.numeric_median_error.setText(
            "Mean median absolute error: "
            f"{_format_decimal(summary.mean_median_absolute_error)} {unit}"
        )
        self.numeric_interval_width.setText(
            f"Mean interval width: {_format_decimal(summary.mean_interval_width)} {unit}"
        )
        self.numeric_interval_score.setText(
            "Mean interval score: "
            f"{_format_decimal(summary.mean_interval_score)} {unit}"
        )

    def _render_binary_updates(
        self,
        snapshot: BinaryUpdateAnalyticsSnapshot,
    ) -> None:
        count = snapshot.paired_count
        self.binary_update_paired_count.setText(f"Revised-and-resolved pairs: {count}")
        self.binary_update_unrevised_count.setText(
            f"Unrevised Resolved Predictions (reported separately): "
            f"{snapshot.unrevised_count}"
        )
        self.binary_update_initial_brier.setText(
            f"Mean initial Brier: {_optional_brier(snapshot.mean_initial_brier)}"
        )
        self.binary_update_final_brier.setText(
            f"Mean final Brier: {_optional_brier(snapshot.mean_final_brier)}"
        )
        self.binary_update_improvement.setText(
            "Mean score improvement (initial minus final): "
            f"{_optional_signed_float(snapshot.mean_score_improvement)}"
        )
        self.binary_update_guidance.setText(_update_guidance(count, "Brier"))

    def _render_numeric_updates(
        self,
        snapshot: NumericUpdateAnalyticsSnapshot,
    ) -> None:
        count = snapshot.paired_count
        self.numeric_update_paired_count.setText(f"Revised-and-resolved pairs: {count}")
        self.numeric_update_unrevised_count.setText(
            f"Unrevised Resolved Predictions (reported separately): "
            f"{snapshot.unrevised_count}"
        )
        self.numeric_update_initial_confidence.setText(
            "Mean initial confidence: "
            f"{_optional_percent(snapshot.mean_initial_confidence_percent)}"
        )
        self.numeric_update_final_confidence.setText(
            "Mean final confidence: "
            f"{_optional_percent(snapshot.mean_final_confidence_percent)}"
        )
        self.numeric_update_initial_containment.setText(
            "Initial intervals contained the outcome: "
            f"{_containment_count(snapshot.initial_contained_count, count)}"
        )
        self.numeric_update_final_containment.setText(
            "Final intervals contained the outcome: "
            f"{_containment_count(snapshot.final_contained_count, count)}"
        )
        unit_summary = snapshot.unit_summary
        if self._selected_unit() is None:
            self.numeric_update_raw_scope.setText(
                "Choose one exact Numeric unit to compare median error, interval "
                "width, and proper interval score. Unlike units are never averaged."
            )
            self._set_numeric_update_raw_metrics(None)
        elif unit_summary is None:
            self.numeric_update_raw_scope.setText(
                f"No revised-and-resolved pairs match unit: {self._selected_unit()}."
            )
            self._set_numeric_update_raw_metrics(None)
        else:
            self.numeric_update_raw_scope.setText(
                f"Raw comparisons use {unit_summary.count} pair(s) with the exact "
                f"unit: {unit_summary.unit}."
            )
            self._set_numeric_update_raw_metrics(unit_summary)
        self.numeric_update_guidance.setText(_update_guidance(count, "Numeric"))

    def _set_numeric_update_raw_metrics(
        self,
        summary: NumericUnitUpdateSummary | None,
    ) -> None:
        if summary is None:
            self.numeric_update_median_error.setText(
                "Mean median error, initial to final: Not available"
            )
            self.numeric_update_width.setText(
                "Mean interval width, initial to final: Not available"
            )
            self.numeric_update_interval_score.setText(
                "Mean interval score, initial to final: Not available"
            )
            return
        unit = summary.unit
        self.numeric_update_median_error.setText(
            "Mean median error, initial to final: "
            f"{_format_decimal(summary.mean_initial_median_absolute_error)} to "
            f"{_format_decimal(summary.mean_final_median_absolute_error)} {unit}; "
            "reduction (initial minus final): "
            f"{_format_signed_decimal(summary.mean_median_error_reduction)} {unit}"
        )
        self.numeric_update_width.setText(
            "Mean interval width, initial to final: "
            f"{_format_decimal(summary.mean_initial_interval_width)} to "
            f"{_format_decimal(summary.mean_final_interval_width)} {unit}; "
            "narrowing (initial minus final): "
            f"{_format_signed_decimal(summary.mean_narrowing)} {unit}. "
            "Narrower is not automatically better."
        )
        self.numeric_update_interval_score.setText(
            "Mean interval score, initial to final: "
            f"{_format_decimal(summary.mean_initial_interval_score)} to "
            f"{_format_decimal(summary.mean_final_interval_score)} {unit}; "
            "improvement (initial minus final): "
            f"{_format_signed_decimal(summary.mean_interval_score_improvement)} "
            f"{unit}. Positive is better."
        )

    def _empty_message(self, prediction_type: PredictionType | None) -> str:
        if self._selected_tag() is not None:
            return "No scored predictions match these filters."
        if prediction_type is PredictionType.BINARY:
            return "No scored Binary Predictions yet. Resolve one to begin analytics."
        if prediction_type is PredictionType.NUMERIC:
            return "No scored Numeric Predictions yet. Resolve one to begin analytics."
        return "No scored predictions yet. Resolve a prediction to begin analytics."

    def _update_tag_choices(self, tags: tuple[str, ...]) -> None:
        selected = self._selected_tag()
        selected_key = None if selected is None else selected.casefold()
        with QSignalBlocker(self.tag_filter):
            self.tag_filter.clear()
            self.tag_filter.addItem("All tags", None)
            selected_index = 0
            for display_name in tags:
                self.tag_filter.addItem(display_name, display_name)
                if display_name.casefold() == selected_key:
                    selected_index = self.tag_filter.count() - 1
            self.tag_filter.setCurrentIndex(selected_index)

    def _update_unit_choices(self, units: tuple[str, ...]) -> None:
        selected = self._selected_unit()
        with QSignalBlocker(self.unit_filter):
            self.unit_filter.clear()
            self.unit_filter.addItem("All units", None)
            selected_index = 0
            for unit in units:
                self.unit_filter.addItem(unit, unit)
                if unit == selected:
                    selected_index = self.unit_filter.count() - 1
            self.unit_filter.setCurrentIndex(selected_index)

    def _selected_type(self) -> PredictionType | None:
        value = self.type_filter.currentData()
        return None if value is None else PredictionType(str(value))

    def _selected_tag(self) -> str | None:
        value = self.tag_filter.currentData()
        return None if value is None else str(value)

    def _selected_unit(self) -> str | None:
        value = self.unit_filter.currentData()
        return None if value is None else str(value)


def _new_bin_table(
    parent: QWidget,
    *,
    object_name: str,
    accessible_name: str,
    headers: tuple[str, str, str, str],
) -> QTableWidget:
    table = QTableWidget(10, 4, parent)
    table.setObjectName(object_name)
    table.setAccessibleName(accessible_name)
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.verticalHeader().setVisible(False)
    header = table.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    header.setStretchLastSection(True)
    return table


def _set_table_row(
    table: QTableWidget,
    row: int,
    values: tuple[str, str, str, str],
) -> None:
    for column, value in enumerate(values):
        item = QTableWidgetItem(value)
        if column in (1, 2, 3):
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(row, column, item)


def _optional_percent(value: Decimal | float | None) -> str:
    return "Not available" if value is None else _format_percent(value)


def _format_percent(value: Decimal | float) -> str:
    return f"{float(value):.1f}".rstrip("0").rstrip(".") + "%"


def _format_decimal(value: Decimal) -> str:
    if value == value.to_integral():
        return format(value.quantize(Decimal(1)), "f")
    return format(value.quantize(Decimal("0.001")), "f").rstrip("0").rstrip(".")


def _optional_brier(value: float | None) -> str:
    return "Not available" if value is None else f"{value:.3f}"


def _optional_signed_float(value: float | None) -> str:
    return "Not available" if value is None else f"{value:+.3f}"


def _format_signed_decimal(value: Decimal) -> str:
    formatted = _format_decimal(abs(value))
    if value > 0:
        return f"+{formatted}"
    if value < 0:
        return f"-{formatted}"
    return "0"


def _containment_count(contained_count: int, pair_count: int) -> str:
    if pair_count == 0:
        return "Not available"
    return (
        f"{contained_count} of {pair_count} "
        f"({_format_percent(100 * contained_count / pair_count)})"
    )


def _update_guidance(pair_count: int, score_name: str) -> str:
    if pair_count == 0:
        return (
            "No revised-and-resolved pairs match these filters. Unrevised "
            "Predictions remain visible in the separate count above."
        )
    direction = (
        "Positive score improvement means the final forecast had a lower score. "
        if score_name == "Brier"
        else "Containment alone is not calibration or proof of better forecasting. "
    )
    return (
        direction
        + "Sparse paired samples can be noisy; treat the comparison as tentative "
        "personal feedback. "
        + "It does not show that updating caused the difference or predict future "
        "performance."
    )
