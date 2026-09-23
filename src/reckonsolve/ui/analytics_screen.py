"""Type-aware Binary and Numeric scoring analytics screen."""

from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from typing import Protocol

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    ForecastAnalyticsSnapshot,
    TrajectoryAnalyticsSnapshot,
)
from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.predictions import PredictionType
from reckonsolve.ui.analytics_charts import (
    CalibrationChart,
)
from reckonsolve.ui.analytics_components import (
    AnalyticsPanel,
    CompactMetricGroup,
    _ResponsiveChartTable,
    _ResponsiveMetricRow,
)
from reckonsolve.ui.components import (
    EmptyStateLabel,
    PageHeader,
    PersistentMessageLabel,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.quantile_analytics import QuantileAnalyticsView
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
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
            title_object_name="analyticsScreenTitle",
            supporting_object_name="analyticsIntroduction",
            parent=self,
        )
        header.setObjectName("analyticsPageHeader")
        header.setAccessibleDescription(
            "Scores remain separate by forecasting model. Every eligible resolved "
            "Prediction contributes once; Invalid and unresolved Predictions are excluded."
        )

        filters_panel = AnalyticsPanel(
            "Analytics View",
            "Every visible headline, table, and chart uses this same filtered "
            "set of resolved Predictions.",
            parent=self,
        )
        filters_panel.setObjectName("analyticsFiltersPanel")
        filters_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

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

        self.empty_label = EmptyStateLabel("", parent=self)
        self.empty_label.setObjectName("analyticsEmpty")
        self.empty_label.setHidden(True)
        self.empty_region = QWidget(self)
        self.empty_region.setObjectName("analyticsEmptyRegion")
        empty_layout = QVBoxLayout(self.empty_region)
        empty_layout.setContentsMargins(0, 0, 0, 0)
        empty_layout.setSpacing(0)
        empty_layout.addWidget(
            self.empty_label,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        empty_layout.addStretch()

        content = QWidget(self)
        content.setObjectName("analyticsContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(int(Spacing.SECTION))
        self.trajectory_summary = self._create_trajectory_summary(content)
        self.trajectory_content = self._create_trajectory_content(content)
        self.quantile_content = QuantileAnalyticsView(content)
        content_layout.addWidget(self.trajectory_summary)
        content_layout.addWidget(self.trajectory_content)
        content_layout.addWidget(self.quantile_content)
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
        layout.addWidget(self.empty_region, 1)
        layout.addWidget(self.scroll_area, 1)

        self.setTabOrder(self.type_filter, self.tag_filter)
        self.setTabOrder(self.tag_filter, self.unit_filter)
        self.setTabOrder(self.unit_filter, self.refresh_button)

        self.type_filter.currentIndexChanged.connect(self._forecast_type_changed)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.unit_filter.currentIndexChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)

    def _create_trajectory_summary(self, parent: QWidget) -> AnalyticsPanel:
        summary = AnalyticsPanel(
            "Trajectory Binary Forecast",
            "Time is weighted inside each fixed forecasting window; every eligible "
            "Prediction still receives one equal vote in this aggregate.",
            parent=parent,
        )
        summary.setObjectName("trajectoryAnalyticsSummary")
        score = CompactMetricGroup("Score", parent=summary.body)
        score.setObjectName("trajectoryHeadlineMetrics")
        self.mean_trajectory_brier = score.add_metric(
            "Mean Trajectory Brier", "analyticsMeanTrajectoryBrier", primary=True
        )
        self.trajectory_scored_count = score.add_metric(
            "Eligible resolved Predictions", "trajectoryAnalyticsScoredCount"
        )
        apply_text_role(self.trajectory_scored_count, TextRole.METRIC)
        timing = CompactMetricGroup("Timing", parent=summary.body)
        timing.setObjectName("trajectoryTimingMetrics")
        self.trajectory_early_count = timing.add_metric(
            "Resolved before deadline", "trajectoryEarlyResolutionCount"
        )
        self.trajectory_deadline_count = timing.add_metric(
            "Reached deadline", "trajectoryReachedDeadlineCount"
        )
        self.trajectory_active_fraction = timing.add_metric(
            "Average Forecast Weight", "trajectoryMeanActiveFraction"
        )
        self.trajectory_neutral_fraction = timing.add_metric(
            "Average Neutral Weight", "trajectoryMeanNeutralFraction"
        )
        timing_explanation = (
            "Average across eligible resolved Predictions, with one equal vote each. "
            "These are weights in the Trajectory Brier calculation, not shares of "
            "the resulting score. Weights follow the planned time from creation to Deadline. "
            "Your forecasts are scored until the outcome is fixed or the Deadline "
            "arrives. After an early outcome, the remaining time uses the neutral "
            "score of 0.25. For example, resolving 4 hours into a 10-hour window "
            "means 40% your forecasts and 60% neutral. This is not time spent in the app."
        )
        for value in (
            self.trajectory_active_fraction,
            self.trajectory_neutral_fraction,
        ):
            value.setToolTip(timing_explanation)
            value.setAccessibleDescription(timing_explanation)
        diagnostics = CompactMetricGroup("Updating", parent=summary.body)
        diagnostics.setObjectName("trajectoryDiagnosticMetrics")
        self.trajectory_initial_brier = diagnostics.add_metric(
            "Mean initial Brier", "trajectoryMeanInitialBrier"
        )
        self.trajectory_final_brier = diagnostics.add_metric(
            "Mean final Brier", "trajectoryMeanFinalBrier"
        )
        self.trajectory_hold_brier = diagnostics.add_metric(
            "Mean hold-initial trajectory", "trajectoryMeanHoldInitialBrier"
        )
        self.trajectory_updating_gain = diagnostics.add_metric(
            "Mean Updating Gain", "trajectoryMeanUpdatingGain"
        )
        metrics = _ResponsiveMetricRow(
            (score, timing, diagnostics),
            stack_below=1050,
            object_name="trajectoryCompactMetrics",
            parent=summary.body,
        )
        metrics.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        for group in (score, timing, diagnostics):
            metrics.layout().setAlignment(group, Qt.AlignmentFlag.AlignTop)
        self.trajectory_guidance = QLabel(summary.body)
        self.trajectory_guidance.setObjectName("trajectoryAnalyticsGuidance")
        self.trajectory_guidance.setTextFormat(Qt.TextFormat.PlainText)
        self.trajectory_guidance.setWordWrap(True)
        apply_text_role(self.trajectory_guidance, TextRole.SECONDARY)
        summary.body_layout.addWidget(metrics)
        summary.body_layout.addWidget(self.trajectory_guidance)
        return summary

    def _create_trajectory_content(self, parent: QWidget) -> AnalyticsPanel:
        section = AnalyticsPanel(
            "Trajectory Binary Final-Probability Calibration",
            "This diagnostic uses one final standing probability strictly before "
            "resolution or deadline. It is not trajectory calibration, and neutral "
            "truncation never creates a 50% observation.",
            parent=parent,
        )
        section.setObjectName("trajectoryCalibrationSection")
        self.trajectory_calibration_chart = CalibrationChart(section.body, scatter=True)
        self.trajectory_calibration_chart.setObjectName(
            "trajectoryFinalCalibrationChart"
        )
        self.trajectory_calibration_table = _new_bin_table(
            section.body,
            object_name="trajectoryFinalCalibrationBinTable",
            accessible_name=(
                "Trajectory Binary final probability bins, counts, forecasts, and outcomes"
            ),
            headers=("Probability bin", "Count", "Mean forecast", "Observed Yes"),
        )
        comparison = _ResponsiveChartTable(
            self.trajectory_calibration_chart,
            self.trajectory_calibration_table,
            object_name="trajectoryFinalCalibrationComparison",
            parent=section.body,
        )
        section.body_layout.addWidget(comparison)
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
                self.trajectory_summary.setHidden(True)
                self.trajectory_content.setHidden(True)
                self.empty_label.setHidden(True)
                self.empty_region.setHidden(False)
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
        self.quantile_content.setHidden(
            not show_numeric or snapshot.quantile_numeric.resolved_candidate_count == 0
        )
        if show_numeric:
            self.quantile_content.render(snapshot.quantile_numeric)
        show_trajectory = (
            show_binary and snapshot.trajectory_binary.resolved_candidate_count > 0
        )
        self.trajectory_summary.setHidden(not show_trajectory)
        self.trajectory_content.setHidden(
            not show_binary or snapshot.trajectory_binary.scored_prediction_count == 0
        )
        if show_binary:
            self._render_trajectory(snapshot.trajectory_binary)

        trajectory_count = (
            snapshot.trajectory_binary.resolved_candidate_count if show_binary else 0
        )
        quantile_count = (
            snapshot.quantile_numeric.resolved_candidate_count if show_numeric else 0
        )
        if trajectory_count == 0 and quantile_count == 0:
            self.scroll_area.setHidden(True)
            self.empty_label.setText(self._empty_message(snapshot.selected_type))
            self.empty_label.setHidden(False)
            self.empty_region.setHidden(False)
        else:
            self.empty_label.setHidden(True)
            self.empty_region.setHidden(True)
            self.scroll_area.setHidden(False)

    def _render_trajectory(self, snapshot: TrajectoryAnalyticsSnapshot) -> None:
        count = snapshot.scored_prediction_count
        self.trajectory_scored_count.setText(str(count))
        self.mean_trajectory_brier.setText(
            _optional_fraction(snapshot.mean_trajectory_brier)
        )
        self.trajectory_early_count.setText(str(snapshot.early_resolution_count))
        self.trajectory_deadline_count.setText(str(snapshot.reached_deadline_count))
        self.trajectory_active_fraction.setText(
            _optional_fraction_percent(snapshot.mean_active_forecast_fraction)
        )
        self.trajectory_neutral_fraction.setText(
            _optional_fraction_percent(
                None
                if snapshot.mean_active_forecast_fraction is None
                else 1 - snapshot.mean_active_forecast_fraction
            )
        )
        self.trajectory_initial_brier.setText(
            _optional_fraction(snapshot.mean_initial_brier)
        )
        self.trajectory_final_brier.setText(
            _optional_fraction(snapshot.mean_final_brier)
        )
        self.trajectory_hold_brier.setText(
            _optional_fraction(snapshot.mean_hold_initial_brier)
        )
        self.trajectory_updating_gain.setText(
            _optional_signed_fraction(snapshot.mean_updating_gain)
        )
        for label, accessible_name in (
            (self.trajectory_scored_count, "Eligible trajectory Binary Predictions"),
            (self.mean_trajectory_brier, "Mean Trajectory Brier"),
            (self.trajectory_early_count, "Resolved before forecast deadline"),
            (self.trajectory_deadline_count, "Reached forecast deadline"),
            (self.trajectory_active_fraction, "Average Forecast Weight"),
            (self.trajectory_neutral_fraction, "Average Neutral Weight"),
            (self.trajectory_initial_brier, "Mean initial Brier"),
            (self.trajectory_final_brier, "Mean final Brier"),
            (self.trajectory_hold_brier, "Mean hold-initial trajectory Brier"),
            (self.trajectory_updating_gain, "Mean Updating Gain"),
        ):
            label.setAccessibleName(f"{accessible_name}: {label.text()}")
        sparse = (
            "No eligible scores are available."
            if count == 0
            else (
                "One Prediction is an anecdote, not a stable performance estimate."
                if count == 1
                else (
                    "This is still a small sample; read the aggregate cautiously."
                    if count < 5
                    else "Read calibration bins cautiously when their counts are small."
                )
            )
        )
        unscored = (
            " "
            f"{snapshot.unscored_prediction_count} resolved Prediction(s) are unscored "
            "because the outcome was fixed at or before the initial forecast."
            if snapshot.unscored_prediction_count
            else ""
        )
        guidance = (
            "Lower Trajectory Brier is better. Updating Gain compares the recorded "
            "path with holding the initial probability: "
            f"{snapshot.positive_updating_gain_count} helped, "
            f"{snapshot.equal_updating_gain_count} tied, and "
            f"{snapshot.negative_updating_gain_count} hurt mechanically. "
            "This hindsight comparison does not prove that updating caused skill. "
            f"{sparse}{unscored}"
        )
        self.trajectory_guidance.setToolTip(guidance)
        self.trajectory_guidance.setAccessibleDescription(guidance)
        self.trajectory_guidance.setText(
            (
                f"Updates: {snapshot.positive_updating_gain_count} helped · "
                f"{snapshot.equal_updating_gain_count} tied · "
                f"{snapshot.negative_updating_gain_count} hurt"
                if count
                else "No eligible scores"
            )
            + (
                f" · {snapshot.unscored_prediction_count} unscored"
                if snapshot.unscored_prediction_count
                else ""
            )
        )
        self.trajectory_calibration_chart.set_bins(snapshot.final_calibration_bins)
        for row, calibration_bin in enumerate(snapshot.final_calibration_bins):
            _set_table_row(
                self.trajectory_calibration_table,
                row,
                (
                    calibration_bin.label,
                    str(calibration_bin.count),
                    _optional_percent(calibration_bin.mean_forecast_percent),
                    _optional_percent(calibration_bin.observed_yes_percent),
                ),
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


def _optional_fraction(value: Fraction | None) -> str:
    return "Not available" if value is None else f"{float(value):.3f}"


def _optional_signed_fraction(value: Fraction | None) -> str:
    return "Not available" if value is None else f"{float(value):+.3f}"


def _optional_fraction_percent(value: Fraction | None) -> str:
    return "Not available" if value is None else _format_percent(float(value) * 100)
