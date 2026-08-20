"""Focused Brier and calibration analytics screen."""

from __future__ import annotations

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

from reckonsolve.analytics import AnalyticsSnapshot
from reckonsolve.application.errors import ApplicationError
from reckonsolve.ui.analytics_charts import BrierTrendChart, CalibrationChart


class AnalyticsOperations(Protocol):
    """Application query used by the aggregate Analytics screen."""

    def get_analytics(self, *, tag: str | None = None) -> AnalyticsSnapshot:
        """Return all scoring views for one common subset."""


class AnalyticsScreen(QWidget):
    """Display exactly-once Brier, calibration, and cumulative performance."""

    def __init__(
        self,
        operations: AnalyticsOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("analyticsScreen")
        self._operations = operations
        self._loaded_snapshot: AnalyticsSnapshot | None = None

        title = QLabel("Analytics", self)
        title.setObjectName("analyticsScreenTitle")

        introduction = QLabel(
            "Each resolved prediction contributes exactly one captured final "
            "forecast. Invalid and unresolved predictions are excluded.",
            self,
        )
        introduction.setObjectName("analyticsIntroduction")
        introduction.setWordWrap(True)
        introduction.setTextFormat(Qt.TextFormat.PlainText)

        tag_label = QLabel("Tag", self)
        self.tag_filter = QComboBox(self)
        self.tag_filter.setObjectName("analyticsTagFilter")
        self.tag_filter.setAccessibleName("Filter analytics by tag")
        self.tag_filter.addItem("All tags", None)
        tag_label.setBuddy(self.tag_filter)
        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.setObjectName("refreshAnalyticsButton")

        filter_layout = QHBoxLayout()
        filter_layout.addWidget(tag_label)
        filter_layout.addWidget(self.tag_filter)
        filter_layout.addWidget(self.refresh_button)
        filter_layout.addStretch()

        self.error_label = QLabel(self)
        self.error_label.setObjectName("analyticsError")
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.setHidden(True)

        summary = QGroupBox("Brier score", self)
        summary.setObjectName("analyticsBrierSummary")
        summary_layout = QVBoxLayout(summary)
        self.scored_count = QLabel("Scored predictions: loading...", summary)
        self.scored_count.setObjectName("analyticsScoredCount")
        self.scored_count.setTextFormat(Qt.TextFormat.PlainText)
        self.mean_brier = QLabel("Mean Brier: loading...", summary)
        self.mean_brier.setObjectName("analyticsMeanBrier")
        self.mean_brier.setTextFormat(Qt.TextFormat.PlainText)
        lower_is_better = QLabel(
            "Lower is better. A perfect forecast scores 0; a maximally wrong "
            "forecast scores 1.",
            summary,
        )
        lower_is_better.setObjectName("analyticsBrierDirection")
        lower_is_better.setWordWrap(True)
        lower_is_better.setTextFormat(Qt.TextFormat.PlainText)
        summary_layout.addWidget(self.scored_count)
        summary_layout.addWidget(self.mean_brier)
        summary_layout.addWidget(lower_is_better)
        summary.setHidden(True)
        self.summary = summary

        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("analyticsEmpty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setTextFormat(Qt.TextFormat.PlainText)
        self.empty_label.setHidden(True)

        content = QWidget(self)
        content.setObjectName("analyticsContent")
        content_layout = QVBoxLayout(content)

        calibration_group = QGroupBox("Calibration / reliability", content)
        calibration_group.setObjectName("analyticsCalibrationSection")
        calibration_layout = QVBoxLayout(calibration_group)
        calibration_explanation = QLabel(
            "The diagonal is perfect calibration. Points use each occupied "
            "bin's actual mean forecast and observed Yes frequency.",
            calibration_group,
        )
        calibration_explanation.setWordWrap(True)
        calibration_explanation.setTextFormat(Qt.TextFormat.PlainText)
        self.calibration_chart = CalibrationChart(calibration_group)
        self.calibration_table = QTableWidget(10, 4, calibration_group)
        self.calibration_table.setObjectName("calibrationBinTable")
        self.calibration_table.setAccessibleName(
            "Calibration bins, counts, forecasts, and outcomes"
        )
        self.calibration_table.setHorizontalHeaderLabels(
            ("Probability bin", "Count", "Mean forecast", "Observed Yes")
        )
        self.calibration_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.calibration_table.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.calibration_table.verticalHeader().setVisible(False)
        header = self.calibration_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        calibration_layout.addWidget(calibration_explanation)
        calibration_layout.addWidget(self.calibration_chart)
        calibration_layout.addWidget(self.calibration_table)

        trend_group = QGroupBox(
            "Cumulative mean Brier by resolution time",
            content,
        )
        trend_group.setObjectName("analyticsBrierTrendSection")
        trend_layout = QVBoxLayout(trend_group)
        trend_explanation = QLabel(
            "Each point includes every prediction resolved up to that time. "
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

        content_layout.addWidget(calibration_group)
        content_layout.addWidget(trend_group)
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
        layout.addWidget(summary)
        layout.addWidget(self.empty_label)
        layout.addWidget(self.scroll_area, 1)

        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.refresh_button.clicked.connect(self.refresh)

    def refresh(self) -> None:
        """Reload one coherent analytical subset and preserve honest error state."""

        selected_tag = self._selected_tag()
        try:
            snapshot = self._operations.get_analytics(tag=selected_tag)
            if selected_tag is not None and selected_tag.casefold() not in {
                item.casefold() for item in snapshot.available_tags
            }:
                with QSignalBlocker(self.tag_filter):
                    self.tag_filter.setCurrentIndex(0)
                snapshot = self._operations.get_analytics(tag=None)
        except ApplicationError as error:
            if self._loaded_snapshot is None:
                self.error_label.setText(f"Analytics unavailable. {error}")
                self.summary.setHidden(True)
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
        self._render(snapshot)

    def _render(self, snapshot: AnalyticsSnapshot) -> None:
        count = snapshot.scored_prediction_count
        self.summary.setHidden(False)
        self.scored_count.setText(f"Scored predictions: {count}")
        self.mean_brier.setText(
            "Mean Brier: Not available"
            if snapshot.mean_brier is None
            else f"Mean Brier: {snapshot.mean_brier:.3f}"
        )
        self.calibration_chart.set_bins(snapshot.calibration_bins)
        self.brier_trend_chart.set_points(snapshot.brier_trend)
        self._render_calibration_table(snapshot)

        if count == 0:
            self.scroll_area.setHidden(True)
            self.empty_label.setText(
                "No scored predictions yet. Resolve a prediction to begin analytics."
                if self._selected_tag() is None
                else "No scored predictions match this tag."
            )
            self.empty_label.setHidden(False)
        else:
            self.empty_label.setHidden(True)
            self.scroll_area.setHidden(False)

    def _render_calibration_table(self, snapshot: AnalyticsSnapshot) -> None:
        for row, calibration_bin in enumerate(snapshot.calibration_bins):
            values = (
                calibration_bin.label,
                str(calibration_bin.count),
                (
                    "Not available"
                    if calibration_bin.mean_forecast_percent is None
                    else _format_percent(calibration_bin.mean_forecast_percent)
                ),
                (
                    "Not available"
                    if calibration_bin.observed_yes_percent is None
                    else _format_percent(calibration_bin.observed_yes_percent)
                ),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 2, 3):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.calibration_table.setItem(row, column, item)

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

    def _selected_tag(self) -> str | None:
        value = self.tag_filter.currentData()
        return None if value is None else str(value)


def _format_percent(value: float) -> str:
    return f"{value:.1f}".rstrip("0").rstrip(".") + "%"
