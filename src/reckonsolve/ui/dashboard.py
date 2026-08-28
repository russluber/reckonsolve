"""Action-oriented Dashboard and its minimal attention setting."""

from __future__ import annotations

from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QStandardPaths, Qt, QTimer, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.attention import (
    MAX_STALE_THRESHOLD_DAYS,
    MIN_STALE_THRESHOLD_DAYS,
    DashboardPrediction,
    DashboardSnapshot,
    NeedsPostmortemPrediction,
)
from reckonsolve.domain.predictions import PostmortemCompletion, PredictionType
from reckonsolve.domain.transfer import (
    BackupResult,
    CsvExportResult,
    DataManagementStatus,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon


class DashboardPredictionSnapshot(Protocol):
    """A complete prediction returned when opening a Dashboard row."""

    prediction_id: int


class DashboardOperations(Protocol):
    """Application queries used by the Dashboard."""

    def get_dashboard(self) -> DashboardSnapshot:
        """Return the current overlapping Dashboard buckets."""

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> DashboardPredictionSnapshot:
        """Return one current prediction for Detail navigation."""

    def record_postmortem_skip(
        self,
        prediction_id: int,
        *,
        expected_correction_id: int | None,
    ) -> PostmortemCompletion:
        """Record one deliberate completion for a blank Resolved Postmortem."""


class AttentionSettingsOperations(Protocol):
    """Application operations used by the focused Settings screen."""

    def get_stale_threshold_days(self) -> int:
        """Return the persisted threshold."""

    def set_stale_threshold_days(self, value: int) -> int:
        """Persist a validated threshold."""

    def get_data_management_status(self) -> DataManagementStatus:
        """Return recovery status and suggested destination names."""

    def create_backup(self, destination: Path) -> BackupResult:
        """Create a complete SQLite recovery artifact."""

    def export_csv_bundle(self, destination: Path) -> CsvExportResult:
        """Create a documented relational CSV ZIP."""

    def repair_search_index(self) -> None:
        """Rebuild the disposable search projection from canonical history."""


class DashboardScreen(QWidget):
    """Surface nonterminal predictions in overlapping action buckets."""

    prediction_selected = Signal(object)

    def __init__(
        self,
        operations: DashboardOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardScreen")
        self._operations = operations
        self._loaded_snapshot: DashboardSnapshot | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setObjectName("dashboardRefreshTimer")
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh)

        title = QLabel("Dashboard", self)
        title.setObjectName("dashboardScreenTitle")

        introduction = QLabel(
            "Your active Binary and Numeric forecasts, with attention signals "
            "derived from the latest forecast revision.",
            self,
        )
        introduction.setObjectName("dashboardIntroduction")
        introduction.setWordWrap(True)
        introduction.setTextFormat(Qt.TextFormat.PlainText)

        self.error_label = QLabel(self)
        self.error_label.setObjectName("dashboardError")
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.setHidden(True)

        self.status_label = QLabel(self)
        self.status_label.setObjectName("dashboardStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setHidden(True)

        self.threshold_label = QLabel(self)
        self.threshold_label.setObjectName("dashboardThreshold")
        self.threshold_label.setTextFormat(Qt.TextFormat.PlainText)

        content = QWidget(self)
        content.setObjectName("dashboardContent")
        content_layout = QVBoxLayout(content)
        self._sections: dict[str, tuple[QGroupBox, QVBoxLayout, str]] = {}
        for key, title_text, empty_text in (
            ("open", "Open", "No open predictions."),
            (
                "needsAttention",
                "Needs Attention",
                "No forecasts currently need attention.",
            ),
            (
                "readyToResolve",
                "Ready to Resolve",
                "Nothing is ready to resolve.",
            ),
            ("locked", "Locked", "No locked predictions."),
            (
                "needsPostmortem",
                "Needs Postmortem",
                "No Resolved Predictions need a Postmortem decision.",
            ),
        ):
            group = QGroupBox(content)
            group.setObjectName(f"dashboard{key[0].upper()}{key[1:]}Section")
            group_layout = QVBoxLayout(group)
            self._sections[key] = (group, group_layout, empty_text)
            group.setProperty("baseTitle", title_text)
            content_layout.addWidget(group)
        content_layout.addStretch()

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("dashboardScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(content)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(introduction)
        layout.addWidget(self.error_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self.threshold_label)
        layout.addWidget(self.scroll_area, 1)

        self._render_empty_sections()

    def showEvent(self, event: QShowEvent) -> None:
        """Keep elapsed-time and local-date classifications current while visible."""

        super().showEvent(event)
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        """Avoid polling persistence while another primary screen is active."""

        self._refresh_timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        """Re-query buckets, retaining prior rows only with an explicit warning."""

        self.status_label.setHidden(True)
        try:
            snapshot = self._operations.get_dashboard()
        except ApplicationError as error:
            if self._loaded_snapshot is None:
                self.error_label.setText(f"Dashboard unavailable. {error}")
                self.threshold_label.setHidden(True)
                self.scroll_area.setHidden(True)
            else:
                self.error_label.setText(
                    f"Dashboard could not refresh; showing the last loaded "
                    f"results. {error}"
                )
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self.threshold_label.setHidden(False)
        self.scroll_area.setHidden(False)
        self._loaded_snapshot = snapshot
        self.threshold_label.setText(
            f"Needs Attention threshold: {snapshot.stale_threshold_days} days"
        )
        self._render_section("open", snapshot.open_predictions)
        self._render_section(
            "needsAttention",
            snapshot.needs_attention_predictions,
        )
        self._render_section(
            "readyToResolve",
            snapshot.ready_to_resolve_predictions,
        )
        self._render_section("locked", snapshot.locked_predictions)
        self._render_needs_postmortem_section(snapshot.needs_postmortem_predictions)

    def _render_empty_sections(self) -> None:
        for key in self._sections:
            self._render_section(key, ())
        self.threshold_label.setText("Needs Attention threshold: loading...")

    def _render_section(
        self,
        key: str,
        predictions: tuple[DashboardPrediction, ...],
    ) -> None:
        group, layout, empty_text = self._sections[key]
        self._clear_layout(layout)
        group.setTitle(f"{group.property('baseTitle')} ({len(predictions)})")
        if not predictions:
            empty = QLabel(empty_text, group)
            empty.setObjectName(f"dashboard{key[0].upper()}{key[1:]}Empty")
            empty.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(empty)
            return
        for prediction in predictions:
            button = QPushButton(
                self._row_text(prediction).replace("&", "&&"),
                group,
            )
            button.setObjectName(
                f"dashboard{key[0].upper()}{key[1:]}Prediction"
                f"{prediction.prediction_id}"
            )
            button.setToolTip("Open Prediction Detail")
            button.setAccessibleName(prediction.question)
            button.setAccessibleDescription(self._row_description(prediction))
            apply_lucide_icon(button, LucideIcon.ARROW_RIGHT, size=16)
            button.clicked.connect(
                partial(self._open_prediction, prediction.prediction_id)
            )
            layout.addWidget(button)

    def _render_needs_postmortem_section(
        self,
        predictions: tuple[NeedsPostmortemPrediction, ...],
    ) -> None:
        """Render optional Resolved reflection work without lifecycle badges."""

        key = "needsPostmortem"
        group, layout, empty_text = self._sections[key]
        self._clear_layout(layout)
        group.setTitle(f"{group.property('baseTitle')} ({len(predictions)})")
        if not predictions:
            empty = QLabel(empty_text, group)
            empty.setObjectName("dashboardNeedsPostmortemEmpty")
            empty.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(empty)
            return
        explanation = QLabel(
            "Optional reflection after resolution. Skip records that you consider "
            "the Postmortem complete without prose; it does not change the outcome, "
            "score, or lifecycle.",
            group,
        )
        explanation.setObjectName("dashboardNeedsPostmortemExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        for prediction in predictions:
            row = QWidget(group)
            row.setObjectName(f"dashboardNeedsPostmortemRow{prediction.prediction_id}")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            open_button = QPushButton(
                self._postmortem_row_text(prediction).replace("&", "&&"),
                row,
            )
            open_button.setObjectName(
                f"dashboardNeedsPostmortemPrediction{prediction.prediction_id}"
            )
            open_button.setToolTip("Open Prediction Detail")
            open_button.setAccessibleName(prediction.question)
            open_button.setAccessibleDescription(
                self._postmortem_row_description(prediction)
            )
            apply_lucide_icon(open_button, LucideIcon.ARROW_RIGHT, size=16)
            open_button.clicked.connect(
                partial(self._open_prediction, prediction.prediction_id)
            )
            skip_button = QPushButton("Skip Postmortem", row)
            skip_button.setObjectName(
                f"skipPostmortemPrediction{prediction.prediction_id}"
            )
            skip_button.setToolTip(
                "Record that reflection is complete without writing a Postmortem."
            )
            skip_button.setAccessibleName(f"Skip Postmortem for {prediction.question}")
            apply_lucide_icon(skip_button, LucideIcon.CIRCLE_CHECK)
            skip_button.clicked.connect(partial(self._skip_postmortem, prediction))
            row_layout.addWidget(open_button, 1)
            row_layout.addWidget(skip_button)
            layout.addWidget(row)

    def _open_prediction(self, prediction_id: int) -> None:
        try:
            prediction = self._operations.get_prediction_for_navigation(prediction_id)
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self.prediction_selected.emit(prediction)

    def _skip_postmortem(self, prediction: NeedsPostmortemPrediction) -> None:
        answer = QMessageBox.warning(
            self,
            "Skip Postmortem?",
            "This records that you deliberately consider reflection complete "
            "without writing a Postmortem. It does not change the Resolution, "
            "score, or lifecycle. You may still add a Postmortem later; this "
            "completion remains in history.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._operations.record_postmortem_skip(
                prediction.prediction_id,
                expected_correction_id=prediction.current_correction_id,
            )
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.refresh()
        self.status_label.setText(
            "Postmortem skipped. You can still add one later; the completion "
            "remains in history."
        )
        self.status_label.setHidden(False)

    @staticmethod
    def _row_text(prediction: DashboardPrediction) -> str:
        badges = [prediction.status.value.upper()]
        if prediction.needs_attention:
            badges.append("NEEDS ATTENTION")
        if prediction.ready_to_resolve:
            badges.append("READY TO RESOLVE")
        return (
            f"{prediction.question}\n"
            f"{_forecast_summary(prediction)}  |  {'  |  '.join(badges)}\n"
            "Forecast last considered "
            f"{_format_local_timestamp(prediction.attention_reference_at)}"
        )

    @staticmethod
    def _row_description(prediction: DashboardPrediction) -> str:
        classifications = [prediction.status.value]
        if prediction.needs_attention:
            classifications.append("needs attention")
        if prediction.ready_to_resolve:
            classifications.append("ready to resolve")
        return (
            f"{_forecast_summary(prediction)}. "
            f"{', '.join(classifications)}. Forecast last considered "
            f"{_format_local_timestamp(prediction.attention_reference_at)}."
        )

    @staticmethod
    def _postmortem_row_text(prediction: NeedsPostmortemPrediction) -> str:
        return (
            f"{prediction.question}\n"
            f"{_postmortem_outcome_summary(prediction)}  |  "
            f"RESOLVED\nResolved {_format_local_timestamp(prediction.resolved_at)}"
        )

    @staticmethod
    def _postmortem_row_description(prediction: NeedsPostmortemPrediction) -> str:
        return (
            f"{_postmortem_outcome_summary(prediction)}. Resolved "
            f"{_format_local_timestamp(prediction.resolved_at)}. Needs an optional "
            "Postmortem decision."
        )

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while (item := layout.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


class AttentionSettingsScreen(QWidget):
    """Expose the small set of v0.1 attention and data-management controls."""

    threshold_changed = Signal(int)

    def __init__(
        self,
        operations: AttentionSettingsOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsScreen")
        self._operations = operations
        self._suggested_backup_filename = "reckonsolve-backup.sqlite3"
        self._suggested_export_filename = "reckonsolve-export.zip"

        title = QLabel("Settings", self)
        title.setObjectName("settingsScreenTitle")

        attention_group = QGroupBox("Needs Attention", self)
        attention_layout = QVBoxLayout(attention_group)
        description = QLabel(
            "A nonterminal forecast needs attention after this many complete "
            "24-hour days without a forecast revision. Journal entries do not "
            "reset it.",
            attention_group,
        )
        description.setObjectName("staleThresholdDescription")
        description.setWordWrap(True)
        description.setTextFormat(Qt.TextFormat.PlainText)

        self.threshold_input = QSpinBox(attention_group)
        self.threshold_input.setObjectName("staleThresholdInput")
        self.threshold_input.setRange(
            MIN_STALE_THRESHOLD_DAYS,
            MAX_STALE_THRESHOLD_DAYS,
        )
        self.threshold_input.setSuffix(" days")
        self.threshold_input.setAccessibleName("Needs Attention threshold in days")

        self.save_button = QPushButton("Save threshold", attention_group)
        self.save_button.setObjectName("saveStaleThresholdButton")
        apply_lucide_icon(self.save_button, LucideIcon.SAVE)
        self.save_button.clicked.connect(self._save)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.threshold_input)
        control_layout.addWidget(self.save_button)
        control_layout.addStretch()

        self.status_label = QLabel(attention_group)
        self.status_label.setObjectName("staleThresholdStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setHidden(True)

        attention_layout.addWidget(description)
        attention_layout.addLayout(control_layout)
        attention_layout.addWidget(self.status_label)

        data_group = QGroupBox("Data and recovery", self)
        data_layout = QVBoxLayout(data_group)
        data_description = QLabel(
            "A SQLite backup can restore the complete application. A CSV bundle "
            "is a portable analytical export and cannot restore Reckonsolve.",
            data_group,
        )
        data_description.setObjectName("dataManagementDescription")
        data_description.setWordWrap(True)
        data_description.setTextFormat(Qt.TextFormat.PlainText)

        self.database_path_label = QLabel("Database: loading...", data_group)
        self.database_path_label.setObjectName("databaseLocation")
        self.database_path_label.setWordWrap(True)
        self.database_path_label.setTextFormat(Qt.TextFormat.PlainText)
        self.database_path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.last_backup_label = QLabel(
            "Last successful backup: loading...",
            data_group,
        )
        self.last_backup_label.setObjectName("lastSuccessfulBackup")
        self.last_backup_label.setTextFormat(Qt.TextFormat.PlainText)

        self.backup_button = QPushButton("Back Up Now", data_group)
        self.backup_button.setObjectName("backUpNowButton")
        apply_lucide_icon(self.backup_button, LucideIcon.DATABASE_BACKUP)
        self.backup_button.clicked.connect(self._back_up_now)
        self.export_button = QPushButton("Export CSV Bundle", data_group)
        self.export_button.setObjectName("exportCsvBundleButton")
        apply_lucide_icon(self.export_button, LucideIcon.FILE_ARCHIVE)
        self.export_button.clicked.connect(self._export_csv_bundle)
        self.repair_search_button = QPushButton("Repair Search Index", data_group)
        self.repair_search_button.setObjectName("repairSearchIndexButton")
        apply_lucide_icon(self.repair_search_button, LucideIcon.REFRESH)
        self.repair_search_button.clicked.connect(self._repair_search_index)
        action_layout = QHBoxLayout()
        action_layout.addWidget(self.backup_button)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.repair_search_button)
        action_layout.addStretch()

        self.data_status_label = QLabel(data_group)
        self.data_status_label.setObjectName("dataManagementStatus")
        self.data_status_label.setWordWrap(True)
        self.data_status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.data_status_label.setHidden(True)

        data_layout.addWidget(data_description)
        data_layout.addWidget(self.database_path_label)
        data_layout.addWidget(self.last_backup_label)
        data_layout.addLayout(action_layout)
        data_layout.addWidget(self.data_status_label)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(attention_group)
        layout.addWidget(data_group)
        layout.addStretch()

    def refresh(self) -> None:
        """Load persisted attention and recovery status when Settings is entered."""

        try:
            value = self._operations.get_stale_threshold_days()
        except ApplicationError as error:
            self.threshold_input.setEnabled(False)
            self.save_button.setEnabled(False)
            self._show_status(str(error))
        else:
            self.threshold_input.setEnabled(True)
            self.save_button.setEnabled(True)
            self.threshold_input.setValue(value)
            self.status_label.setHidden(True)
        try:
            status = self._operations.get_data_management_status()
        except ApplicationError as error:
            self._show_data_status(str(error))
            return
        self._suggested_backup_filename = status.suggested_backup_filename
        self._suggested_export_filename = status.suggested_export_filename
        self.database_path_label.setText(f"Database: {status.database_path}")
        self._show_last_backup(status.last_successful_backup_at)
        self.data_status_label.setHidden(True)

    def _save(self) -> None:
        try:
            value = self._operations.set_stale_threshold_days(
                self.threshold_input.value()
            )
        except ApplicationError as error:
            self._show_status(str(error))
            return
        self._show_status(f"Saved. Dashboard now uses {value} days.")
        self.threshold_changed.emit(value)

    def _back_up_now(self) -> None:
        destination = self._choose_destination(
            title="Create Reckonsolve Backup",
            suggested_filename=self._suggested_backup_filename,
            file_filter="SQLite database (*.sqlite3);;All files (*)",
            default_suffix=".sqlite3",
        )
        if destination is None:
            return
        try:
            result = self._operations.create_backup(destination)
        except ApplicationError as error:
            self._show_data_status(str(error))
            return
        self._show_last_backup(result.completed_at)
        message = f"Backup created: {result.destination}"
        if not result.last_successful_time_recorded:
            message += (
                " The file is usable, but its successful time could not be "
                "recorded in Settings."
            )
        self._show_data_status(message)

    def _export_csv_bundle(self) -> None:
        destination = self._choose_destination(
            title="Export Reckonsolve CSV Bundle",
            suggested_filename=self._suggested_export_filename,
            file_filter="ZIP archive (*.zip);;All files (*)",
            default_suffix=".zip",
        )
        if destination is None:
            return
        try:
            result = self._operations.export_csv_bundle(destination)
        except ApplicationError as error:
            self._show_data_status(str(error))
            return
        self._show_data_status(
            f"Exported {result.csv_file_count} CSV files: {result.destination}"
        )

    def _repair_search_index(self) -> None:
        """Explicitly recreate only derived search data from canonical history."""

        try:
            self._operations.repair_search_index()
        except ApplicationError as error:
            self._show_data_status(str(error))
            return
        self._show_data_status(
            "Search index repaired from canonical Prediction history."
        )

    def _choose_destination(
        self,
        *,
        title: str,
        suggested_filename: str,
        file_filter: str,
        default_suffix: str,
    ) -> Path | None:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        initial_path = (
            Path(documents) / suggested_filename
            if documents
            else Path(suggested_filename)
        )
        selected, _selected_filter = QFileDialog.getSaveFileName(
            self,
            title,
            str(initial_path),
            file_filter,
        )
        if not selected:
            return None
        destination = Path(selected)
        return (
            destination
            if destination.suffix
            else destination.with_suffix(default_suffix)
        )

    def _show_last_backup(self, value: datetime | None) -> None:
        self.last_backup_label.setText(
            "Last successful backup: Not yet"
            if value is None
            else f"Last successful backup: {_format_local_timestamp(value)}"
        )

    def _show_data_status(self, message: str) -> None:
        self.data_status_label.setText(message)
        self.data_status_label.setHidden(False)

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setHidden(False)


def _format_local_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")


def _postmortem_outcome_summary(prediction: NeedsPostmortemPrediction) -> str:
    """Return the type-aware effective terminal fact for one queue row."""

    if prediction.prediction_type is PredictionType.BINARY:
        if prediction.binary_outcome is None:
            raise ValueError("A Binary Postmortem row requires an outcome.")
        return f"BINARY | Outcome: {prediction.binary_outcome.value.capitalize()}"
    if prediction.numeric_actual_value is None or prediction.numeric_unit is None:
        raise ValueError("A Numeric Postmortem row requires an exact actual value.")
    return (
        f"NUMERIC | Actual: {prediction.numeric_actual_value} {prediction.numeric_unit}"
    )


def _forecast_summary(prediction: DashboardPrediction) -> str:
    """Return an unambiguous compact current-forecast summary for a row."""

    if prediction.prediction_type is PredictionType.BINARY:
        if prediction.probability_percent is None:
            raise ValueError("A Binary Dashboard row requires a probability.")
        return f"BINARY  {prediction.probability_percent}%"
    if (
        prediction.numeric_lower_bound is None
        or prediction.numeric_median_estimate is None
        or prediction.numeric_upper_bound is None
        or prediction.numeric_confidence_percent is None
        or prediction.numeric_unit is None
    ):
        raise ValueError("A Numeric Dashboard row requires complete interval data.")
    return (
        f"NUMERIC  {prediction.numeric_confidence_percent}% interval: "
        f"{prediction.numeric_lower_bound}–{prediction.numeric_upper_bound} "
        f"{prediction.numeric_unit}; median: "
        f"{prediction.numeric_median_estimate} {prediction.numeric_unit}"
    )
