"""Type-aware Binary and Numeric scoring analytics screen."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol

from PySide6.QtCore import QEvent, QSignalBlocker, Qt
from PySide6.QtGui import QColor, QPalette, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QBoxLayout,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
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
from reckonsolve.ui.components import (
    ContentPanel,
    EmptyStateLabel,
    PageHeader,
    PersistentMessageLabel,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
    semantic_colors,
)


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


def _new_summary_metric(
    caption: str,
    *,
    value_object_name: str,
    parent: QWidget,
) -> tuple[QWidget, QLabel]:
    """Build one compact caption/value pair for an analytical headline."""

    metric = QWidget(parent)
    metric.setObjectName(f"{value_object_name}Metric")
    layout = QVBoxLayout(metric)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(int(Spacing.COMPACT))
    caption_label = QLabel(caption, metric)
    caption_label.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(caption_label, TextRole.SECONDARY)
    value = QLabel("Loading...", metric)
    value.setObjectName(value_object_name)
    value.setTextFormat(Qt.TextFormat.PlainText)
    value.setWordWrap(True)
    apply_text_role(value, TextRole.FORECAST)
    layout.addWidget(caption_label)
    layout.addWidget(value)
    return metric, value


class _ResponsiveMetricRow(QWidget):
    """Keep summary metrics horizontal until their captions would crowd."""

    def __init__(
        self,
        metrics: tuple[QWidget, ...],
        *,
        stack_below: int,
        object_name: str,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._stack_below = stack_below
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(int(Spacing.SECTION))
        for metric in metrics:
            self._layout.addWidget(metric, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        direction = (
            QBoxLayout.Direction.LeftToRight
            if event.size().width() >= self._stack_below
            else QBoxLayout.Direction.TopToBottom
        )
        if self._layout.direction() != direction:
            self._layout.setDirection(direction)


class _ResponsiveSummaryRow(QWidget):
    """Place type summaries beside each other only when both remain readable."""

    def __init__(
        self,
        binary_summary: QWidget,
        numeric_summary: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsSummaryRow")
        self._layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(int(Spacing.SECTION))
        self._layout.addWidget(binary_summary, 1)
        self._layout.addWidget(numeric_summary, 1)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        paired_minimum = max(
            720,
            self.fontMetrics().horizontalAdvance(
                "Mean interval score: Not available  Mean interval score: Not available"
            ),
        )
        direction = (
            QBoxLayout.Direction.LeftToRight
            if event.size().width() >= paired_minimum
            else QBoxLayout.Direction.TopToBottom
        )
        if self._layout.direction() != direction:
            self._layout.setDirection(direction)


class _ResponsiveChartTable(QWidget):
    """Pair a plot and its text table when both retain a useful width."""

    def __init__(
        self,
        chart: QWidget,
        table: QTableWidget,
        *,
        object_name: str,
        parent: QWidget,
    ) -> None:
        super().__init__(parent)
        self.setObjectName(object_name)
        self._chart = chart
        self._table = table
        for widget in (chart, table):
            policy = widget.sizePolicy()
            policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
            widget.setSizePolicy(policy)
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(int(Spacing.SECTION))
        self._layout.addWidget(chart)
        self._layout.addWidget(table)
        self._synchronize_surfaces()
        self._fit_table_height()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() in (
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.FontChange,
            QEvent.Type.ApplicationFontChange,
            QEvent.Type.StyleChange,
        ):
            self._synchronize_surfaces()
            self._fit_table_height()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        side_by_side = event.size().width() >= 1100
        direction = (
            QBoxLayout.Direction.LeftToRight
            if side_by_side
            else QBoxLayout.Direction.TopToBottom
        )
        if self._layout.direction() != direction:
            self._layout.setDirection(direction)
        self._layout.setStretch(0, 1 if side_by_side else 0)
        self._layout.setStretch(1, 1 if side_by_side else 0)
        self._fit_table_height()

    def _synchronize_surfaces(self) -> None:
        surface = QColor(semantic_colors(self.palette()).raised)
        for widget in (self._chart, self._table, self._table.viewport()):
            palette = widget.palette()
            palette.setColor(QPalette.ColorRole.Base, surface)
            palette.setColor(QPalette.ColorRole.AlternateBase, surface)
            widget.setPalette(palette)

    def _fit_table_height(self) -> None:
        self._table.resizeRowsToContents()
        content_height = (
            self._table.horizontalHeader().height()
            + sum(self._table.rowHeight(row) for row in range(self._table.rowCount()))
            + (2 * self._table.frameWidth())
            + 2
        )
        self._table.setFixedHeight(content_height)


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

        header = PageHeader(
            "Analytics",
            "Each resolved prediction contributes exactly one captured final "
            "forecast. Binary and Numeric scores remain separate; Invalid and "
            "unresolved predictions are excluded.",
            title_object_name="analyticsScreenTitle",
            supporting_object_name="analyticsIntroduction",
            parent=self,
        )
        header.setObjectName("analyticsPageHeader")

        filters_panel = ContentPanel(
            "Analytics view",
            "Every visible headline, table, and chart uses this same filtered "
            "set of resolved Predictions.",
            parent=self,
        )
        filters_panel.setObjectName("analyticsFiltersPanel")

        type_label = QLabel("Forecast type", filters_panel.body)
        self.type_filter = QComboBox(filters_panel.body)
        self.type_filter.setObjectName("analyticsTypeFilter")
        self.type_filter.setAccessibleName("Filter analytics by forecast type")
        self.type_filter.setAccessibleDescription(
            "Show Binary, Numeric, or both forecast models without combining "
            "their scores."
        )
        self.type_filter.addItem("All types", None)
        self.type_filter.addItem("Binary", PredictionType.BINARY.value)
        self.type_filter.addItem("Numeric", PredictionType.NUMERIC.value)
        type_label.setBuddy(self.type_filter)

        tag_label = QLabel("Tag", filters_panel.body)
        self.tag_filter = QComboBox(filters_panel.body)
        self.tag_filter.setObjectName("analyticsTagFilter")
        self.tag_filter.setAccessibleName("Filter analytics by tag")
        self.tag_filter.setAccessibleDescription(
            "Restrict every analytical result to one current tag."
        )
        self.tag_filter.addItem("All tags", None)
        tag_label.setBuddy(self.tag_filter)

        unit_label = QLabel("Numeric unit", filters_panel.body)
        self.unit_filter = QComboBox(filters_panel.body)
        self.unit_filter.setObjectName("analyticsUnitFilter")
        self.unit_filter.setAccessibleName("Filter Numeric analytics by exact unit")
        self.unit_filter.setAccessibleDescription(
            "Available only in the Numeric view. One exact unit is required for "
            "raw error, width, and interval-score averages."
        )
        self.unit_filter.addItem("All units", None)
        self.unit_filter.setEnabled(False)
        self.unit_filter.setToolTip(
            "Choose Numeric forecast type to enable exact-unit scoring."
        )
        unit_label.setBuddy(self.unit_filter)

        self.refresh_button = QPushButton("Refresh", filters_panel.body)
        self.refresh_button.setObjectName("refreshAnalyticsButton")
        self.refresh_button.setToolTip("Reload analytics from the current database")
        apply_action_role(self.refresh_button, ActionRole.QUIET)
        apply_lucide_icon(self.refresh_button, LucideIcon.REFRESH)

        for label in (type_label, tag_label, unit_label):
            apply_text_role(label, TextRole.LABEL)
        for control in (self.type_filter, self.tag_filter, self.unit_filter):
            control.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            control.setMinimumContentsLength(10)
            control.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )

        filter_layout = QGridLayout()
        filter_layout.setHorizontalSpacing(int(Spacing.ORDINARY))
        filter_layout.setVerticalSpacing(int(Spacing.COMPACT))
        for column, (label, control) in enumerate(
            (
                (type_label, self.type_filter),
                (tag_label, self.tag_filter),
                (unit_label, self.unit_filter),
            )
        ):
            filter_layout.addWidget(label, 0, column)
            filter_layout.addWidget(control, 1, column)
            filter_layout.setColumnStretch(column, 1)
        filters_panel.body_layout.addLayout(filter_layout)
        filter_actions = QHBoxLayout()
        filter_actions.addStretch()
        filter_actions.addWidget(self.refresh_button)
        filters_panel.body_layout.addLayout(filter_actions)

        self.error_label = PersistentMessageLabel(
            accessible_name="Analytics status",
            tone=StatusTone.ERROR,
            parent=self,
        )
        self.error_label.setObjectName("analyticsError")

        self.summary = self._create_binary_summary()
        self.numeric_summary = self._create_numeric_summary()

        self.summary_row = _ResponsiveSummaryRow(
            self.summary,
            self.numeric_summary,
            self,
        )

        self.empty_label = EmptyStateLabel("", parent=self)
        self.empty_label.setObjectName("analyticsEmpty")
        self.empty_label.setHidden(True)

        content = QWidget(self)
        content.setObjectName("analyticsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(int(Spacing.SECTION))
        self.binary_content = self._create_binary_content(content)
        self.numeric_content = self._create_numeric_content(content)
        self.binary_update_content = self._create_binary_update_content(content)
        self.numeric_update_content = self._create_numeric_update_content(content)
        content_layout.addWidget(self.summary_row)
        content_layout.addWidget(self.binary_content)
        content_layout.addWidget(self.numeric_content)
        content_layout.addWidget(self.binary_update_content)
        content_layout.addWidget(self.numeric_update_content)
        content_layout.addStretch()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("analyticsScrollArea")
        self.scroll_area.setAccessibleName("Analytics results")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setWidget(content)
        self.scroll_area.setHidden(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.ORDINARY))
        layout.addWidget(header)
        layout.addWidget(filters_panel)
        layout.addWidget(self.error_label)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.scroll_area, 1)

        self.setTabOrder(self.type_filter, self.tag_filter)
        self.setTabOrder(self.tag_filter, self.unit_filter)
        self.setTabOrder(self.unit_filter, self.refresh_button)

        self.type_filter.currentIndexChanged.connect(self._forecast_type_changed)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.unit_filter.currentIndexChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)

    def _create_binary_summary(self) -> ContentPanel:
        summary = ContentPanel(
            "Binary forecasts — Brier score",
            "One final captured probability per resolved Binary Prediction.",
            parent=self,
        )
        summary.setObjectName("analyticsBrierSummary")
        summary_layout = summary.body_layout
        scored_metric, self.scored_count = _new_summary_metric(
            "Scored predictions",
            value_object_name="analyticsScoredCount",
            parent=summary.body,
        )
        brier_metric, self.mean_brier = _new_summary_metric(
            "Mean Brier score",
            value_object_name="analyticsMeanBrier",
            parent=summary.body,
        )
        metrics = _ResponsiveMetricRow(
            (scored_metric, brier_metric),
            stack_below=360,
            object_name="binaryHeadlineMetrics",
            parent=summary.body,
        )
        direction = QLabel(
            "Lower is better. A perfect Binary forecast scores 0; a maximally "
            "wrong forecast scores 1.",
            summary.body,
        )
        direction.setObjectName("analyticsBrierDirection")
        direction.setWordWrap(True)
        direction.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(direction, TextRole.SECONDARY)
        summary_layout.addWidget(metrics)
        summary_layout.addWidget(direction)
        summary_layout.addStretch()
        summary.setHidden(True)
        return summary

    def _create_numeric_summary(self) -> ContentPanel:
        summary = ContentPanel(
            "Numeric forecasts",
            "Containment can combine units; raw magnitude scores cannot.",
            parent=self,
        )
        summary.setObjectName("numericAnalyticsSummary")
        summary_layout = summary.body_layout
        scored_metric, self.numeric_scored_count = _new_summary_metric(
            "Scored predictions",
            value_object_name="numericAnalyticsScoredCount",
            parent=summary.body,
        )
        containment_metric, self.numeric_containment = _new_summary_metric(
            "Outcomes contained",
            value_object_name="numericAnalyticsContainment",
            parent=summary.body,
        )
        headline_metrics = _ResponsiveMetricRow(
            (scored_metric, containment_metric),
            stack_below=360,
            object_name="numericHeadlineMetrics",
            parent=summary.body,
        )

        self.numeric_raw_scope = QLabel(summary.body)
        self.numeric_raw_scope.setObjectName("numericAnalyticsRawScope")
        self.numeric_raw_scope.setWordWrap(True)
        median_metric, self.numeric_median_error = _new_summary_metric(
            "Mean median error",
            value_object_name="numericMeanMedianAbsoluteError",
            parent=summary.body,
        )
        width_metric, self.numeric_interval_width = _new_summary_metric(
            "Mean interval width",
            value_object_name="numericMeanIntervalWidth",
            parent=summary.body,
        )
        score_metric, self.numeric_interval_score = _new_summary_metric(
            "Mean interval score",
            value_object_name="numericMeanIntervalScore",
            parent=summary.body,
        )
        self.numeric_raw_metrics = _ResponsiveMetricRow(
            (median_metric, width_metric, score_metric),
            stack_below=660,
            object_name="numericRawMetricGrid",
            parent=summary.body,
        )

        self.numeric_score_guidance = QLabel(summary.body)
        self.numeric_score_guidance.setObjectName("numericScoreGuidance")
        self.numeric_score_guidance.setWordWrap(True)
        for label in (self.numeric_raw_scope, self.numeric_score_guidance):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
        apply_text_role(self.numeric_raw_scope, TextRole.SECONDARY)
        apply_text_role(self.numeric_score_guidance, TextRole.SECONDARY)
        summary_layout.addWidget(headline_metrics)
        summary_layout.addWidget(self.numeric_raw_scope)
        summary_layout.addWidget(self.numeric_raw_metrics)
        summary_layout.addWidget(self.numeric_score_guidance)
        summary_layout.addStretch()
        summary.setHidden(True)
        return summary

    def _create_binary_content(self, parent: QWidget) -> QWidget:
        section = QWidget(parent)
        section.setObjectName("binaryAnalyticsSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(int(Spacing.SECTION))

        calibration_group = ContentPanel(
            "Calibration / reliability",
            "Calibration compares forecast probability with the observed Yes rate; "
            "the diagonal is perfect, and the table repeats the chart values.",
            parent=section,
        )
        calibration_group.setObjectName("analyticsCalibrationSection")
        calibration_layout = calibration_group.body_layout
        self.calibration_chart = CalibrationChart(calibration_group.body)
        self.calibration_table = _new_bin_table(
            calibration_group.body,
            object_name="calibrationBinTable",
            accessible_name="Calibration bins, counts, forecasts, and outcomes",
            headers=("Probability bin", "Count", "Mean forecast", "Observed Yes"),
        )
        calibration_comparison = _ResponsiveChartTable(
            self.calibration_chart,
            self.calibration_table,
            object_name="binaryCalibrationComparison",
            parent=calibration_group.body,
        )
        calibration_layout.addWidget(calibration_comparison)

        trend_group = ContentPanel(
            "Cumulative mean Brier by resolution time",
            "A descriptive running average, not proof that forecasting skill changed.",
            parent=section,
        )
        trend_group.setObjectName("analyticsBrierTrendSection")
        trend_layout = trend_group.body_layout
        trend_explanation = QLabel(
            "Each point includes every Binary Prediction resolved up to that time. "
            "Movement does not by itself prove skill improvement because forecast "
            "difficulty and composition can change.",
            trend_group.body,
        )
        trend_explanation.setObjectName("analyticsTrendExplanation")
        trend_explanation.setWordWrap(True)
        trend_explanation.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(trend_explanation, TextRole.SECONDARY)
        self.brier_trend_chart = BrierTrendChart(trend_group.body)
        trend_layout.addWidget(trend_explanation)
        trend_layout.addWidget(self.brier_trend_chart)

        section_layout.addWidget(calibration_group)
        section_layout.addWidget(trend_group)
        return section

    def _create_numeric_content(self, parent: QWidget) -> ContentPanel:
        section = ContentPanel(
            "Numeric containment calibration",
            "Containment calibration compares interval confidence with observed "
            "inclusive containment; it can combine units, small bins are sparse, "
            "and the table repeats the chart values.",
            parent=parent,
        )
        section.setObjectName("numericAnalyticsSection")
        section_layout = section.body_layout
        self.containment_chart = ContainmentCalibrationChart(section.body)
        self.containment_table = _new_bin_table(
            section.body,
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
        containment_comparison = _ResponsiveChartTable(
            self.containment_chart,
            self.containment_table,
            object_name="numericCalibrationComparison",
            parent=section.body,
        )
        section_layout.addWidget(containment_comparison)
        return section

    def _create_binary_update_content(self, parent: QWidget) -> ContentPanel:
        section = ContentPanel(
            "Binary retrospective update feedback",
            "One initial/final pair per revised-and-resolved Binary Prediction.",
            parent=parent,
        )
        section.setObjectName("binaryUpdateAnalyticsSection")
        section_layout = section.body_layout
        explanation = QLabel(
            "This compares revision 1 with the exact final scoring revision for "
            "each revised-and-resolved Binary Prediction. It is descriptive "
            "hindsight, not proof that updating caused improvement.",
            section.body,
        )
        explanation.setObjectName("binaryUpdateAnalyticsExplanation")
        explanation.setWordWrap(True)
        self.binary_update_paired_count = QLabel(section.body)
        self.binary_update_paired_count.setObjectName("binaryUpdatePairedCount")
        self.binary_update_unrevised_count = QLabel(section.body)
        self.binary_update_unrevised_count.setObjectName("binaryUpdateUnrevisedCount")
        self.binary_update_initial_brier = QLabel(section.body)
        self.binary_update_initial_brier.setObjectName("binaryUpdateInitialBrier")
        self.binary_update_final_brier = QLabel(section.body)
        self.binary_update_final_brier.setObjectName("binaryUpdateFinalBrier")
        self.binary_update_improvement = QLabel(section.body)
        self.binary_update_improvement.setObjectName("binaryUpdateImprovement")
        self.binary_update_guidance = QLabel(section.body)
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
            label.setWordWrap(True)
            section_layout.addWidget(label)
        apply_text_role(explanation, TextRole.SECONDARY)
        apply_text_role(self.binary_update_guidance, TextRole.SECONDARY)
        return section

    def _create_numeric_update_content(self, parent: QWidget) -> ContentPanel:
        section = ContentPanel(
            "Numeric retrospective update feedback",
            "One initial/final pair per revised-and-resolved Numeric Prediction.",
            parent=parent,
        )
        section.setObjectName("numericUpdateAnalyticsSection")
        section_layout = section.body_layout
        explanation = QLabel(
            "This compares revision 1 with the exact final scoring revision for "
            "each revised-and-resolved Numeric Prediction. Confidence and "
            "containment may combine units; raw comparisons require one exact unit.",
            section.body,
        )
        explanation.setObjectName("numericUpdateAnalyticsExplanation")
        explanation.setWordWrap(True)
        self.numeric_update_paired_count = QLabel(section.body)
        self.numeric_update_paired_count.setObjectName("numericUpdatePairedCount")
        self.numeric_update_unrevised_count = QLabel(section.body)
        self.numeric_update_unrevised_count.setObjectName("numericUpdateUnrevisedCount")
        self.numeric_update_initial_confidence = QLabel(section.body)
        self.numeric_update_initial_confidence.setObjectName(
            "numericUpdateInitialConfidence"
        )
        self.numeric_update_final_confidence = QLabel(section.body)
        self.numeric_update_final_confidence.setObjectName(
            "numericUpdateFinalConfidence"
        )
        self.numeric_update_initial_containment = QLabel(section.body)
        self.numeric_update_initial_containment.setObjectName(
            "numericUpdateInitialContainment"
        )
        self.numeric_update_final_containment = QLabel(section.body)
        self.numeric_update_final_containment.setObjectName(
            "numericUpdateFinalContainment"
        )
        self.numeric_update_raw_scope = QLabel(section.body)
        self.numeric_update_raw_scope.setObjectName("numericUpdateRawScope")
        self.numeric_update_raw_scope.setWordWrap(True)
        self.numeric_update_median_error = QLabel(section.body)
        self.numeric_update_median_error.setObjectName("numericUpdateMedianError")
        self.numeric_update_width = QLabel(section.body)
        self.numeric_update_width.setObjectName("numericUpdateWidth")
        self.numeric_update_interval_score = QLabel(section.body)
        self.numeric_update_interval_score.setObjectName("numericUpdateIntervalScore")
        self.numeric_update_guidance = QLabel(section.body)
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
            label.setWordWrap(True)
            section_layout.addWidget(label)
        apply_text_role(explanation, TextRole.SECONDARY)
        apply_text_role(self.numeric_update_guidance, TextRole.SECONDARY)
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
                message = f"Analytics unavailable. {error}"
                self.summary.setHidden(True)
                self.numeric_summary.setHidden(True)
                self.summary_row.setHidden(True)
                self.empty_label.setHidden(True)
                self.scroll_area.setHidden(True)
            else:
                message = (
                    "Analytics could not refresh; showing the last loaded results. "
                    f"{error}"
                )
            self.error_label.show_message(message, StatusTone.ERROR)
            return

        self.error_label.clear_message()
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
            self.summary_row.setHidden(True)
            self.scroll_area.setHidden(True)
            self.empty_label.setText(self._empty_message(snapshot.selected_type))
            self.empty_label.setHidden(False)
        else:
            self.summary_row.setHidden(False)
            self.empty_label.setHidden(True)
            self.scroll_area.setHidden(False)

    def _render_binary(self, snapshot: AnalyticsSnapshot) -> None:
        self.scored_count.setText(str(snapshot.scored_prediction_count))
        self.scored_count.setAccessibleName(
            f"Scored Binary predictions: {snapshot.scored_prediction_count}"
        )
        self.mean_brier.setText(
            "Not available"
            if snapshot.mean_brier is None
            else f"{snapshot.mean_brier:.3f}"
        )
        self.mean_brier.setAccessibleName(f"Mean Brier score: {self.mean_brier.text()}")
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
        self.numeric_scored_count.setText(str(count))
        self.numeric_scored_count.setAccessibleName(
            f"Scored Numeric predictions: {count}"
        )
        self.numeric_containment.setText(
            "Not available"
            if count == 0
            else (
                f"{contained_count} of {count} "
                f"({_format_percent(100 * contained_count / count)})"
            )
        )
        self.numeric_containment.setAccessibleName(
            f"Outcomes contained: {self.numeric_containment.text()}"
        )
        summary = snapshot.unit_summary
        if snapshot.selected_unit is None:
            self.numeric_raw_scope.setText(
                "Select Numeric and one exact unit to see magnitude scores. "
                "Unlike units are never averaged."
            )
            self._set_raw_metrics(None)
        elif summary is None:
            self.numeric_raw_scope.setText(
                f"No scored Numeric Predictions match unit: {snapshot.selected_unit}."
            )
            self._set_raw_metrics(None)
        else:
            prediction_noun = "prediction" if summary.count == 1 else "predictions"
            self.numeric_raw_scope.setText(
                f"Magnitude averages · {summary.count} scored {prediction_noun} · "
                f"{summary.unit}"
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
            for accessible_name, label in (
                ("Mean median absolute error", self.numeric_median_error),
                ("Mean interval width", self.numeric_interval_width),
                ("Mean interval score", self.numeric_interval_score),
            ):
                label.setText("Not available")
                label.setAccessibleName(f"{accessible_name}: Not available")
            self.numeric_raw_metrics.setHidden(True)
            self.numeric_score_guidance.clear()
            self.numeric_score_guidance.setHidden(True)
            return
        unit = summary.unit
        self.numeric_median_error.setText(
            f"{_format_decimal(summary.mean_median_absolute_error)} {unit}"
        )
        self.numeric_interval_width.setText(
            f"{_format_decimal(summary.mean_interval_width)} {unit}"
        )
        self.numeric_interval_score.setText(
            f"{_format_decimal(summary.mean_interval_score)} {unit}"
        )
        self.numeric_median_error.setAccessibleName(
            f"Mean median absolute error: {self.numeric_median_error.text()}"
        )
        self.numeric_interval_width.setAccessibleName(
            f"Mean interval width: {self.numeric_interval_width.text()}"
        )
        self.numeric_interval_score.setAccessibleName(
            f"Mean interval score: {self.numeric_interval_score.text()}"
        )
        self.numeric_raw_metrics.setHidden(False)
        self.numeric_score_guidance.setText(
            "Median error is the central estimate's miss. Interval score balances "
            "narrowness and misses; lower is better."
        )
        self.numeric_score_guidance.setHidden(False)

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
    table.setAccessibleDescription(
        "Ten fixed bins. Empty bins remain listed with a count of zero and no "
        "invented mean or observed value."
    )
    table.setHorizontalHeaderLabels(headers)
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    table.setAlternatingRowColors(False)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
