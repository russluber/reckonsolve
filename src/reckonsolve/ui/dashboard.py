"""Action-oriented Dashboard and its minimal attention setting."""

from __future__ import annotations

from datetime import datetime
from functools import partial
from typing import Protocol

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
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
)


class DashboardPredictionSnapshot(Protocol):
    """A complete prediction returned when opening a Dashboard row."""

    prediction_id: int


class DashboardOperations(Protocol):
    """Application queries used by the Dashboard."""

    def get_dashboard(self) -> DashboardSnapshot:
        """Return the current overlapping Dashboard buckets."""

    def get_prediction(self, prediction_id: int) -> DashboardPredictionSnapshot:
        """Return one current prediction for Detail navigation."""


class AttentionSettingsOperations(Protocol):
    """Application operations used by the minimal M8 Settings control."""

    def get_stale_threshold_days(self) -> int:
        """Return the persisted threshold."""

    def set_stale_threshold_days(self, value: int) -> int:
        """Persist a validated threshold."""


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
            "Your active forecasts, with attention signals derived from the latest "
            "forecast revision.",
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
            button.clicked.connect(
                partial(self._open_prediction, prediction.prediction_id)
            )
            layout.addWidget(button)

    def _open_prediction(self, prediction_id: int) -> None:
        try:
            prediction = self._operations.get_prediction(prediction_id)
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self.prediction_selected.emit(prediction)

    @staticmethod
    def _row_text(prediction: DashboardPrediction) -> str:
        badges = [prediction.status.value.upper()]
        if prediction.needs_attention:
            badges.append("NEEDS ATTENTION")
        if prediction.ready_to_resolve:
            badges.append("READY TO RESOLVE")
        return (
            f"{prediction.question}\n"
            f"{prediction.probability_percent}%  |  {'  |  '.join(badges)}\n"
            f"Forecast last updated {_format_local_timestamp(prediction.latest_revision_at)}"
        )

    @staticmethod
    def _row_description(prediction: DashboardPrediction) -> str:
        classifications = [prediction.status.value]
        if prediction.needs_attention:
            classifications.append("needs attention")
        if prediction.ready_to_resolve:
            classifications.append("ready to resolve")
        return (
            f"{prediction.probability_percent} percent. "
            f"{', '.join(classifications)}. Forecast last updated "
            f"{_format_local_timestamp(prediction.latest_revision_at)}."
        )

    @staticmethod
    def _clear_layout(layout: QVBoxLayout) -> None:
        while (item := layout.takeAt(0)) is not None:
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()


class AttentionSettingsScreen(QWidget):
    """Expose the one persisted preference required by Milestone 8."""

    threshold_changed = Signal(int)

    def __init__(
        self,
        operations: AttentionSettingsOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsScreen")
        self._operations = operations

        title = QLabel("Settings", self)
        title.setObjectName("settingsScreenTitle")

        description = QLabel(
            "A nonterminal forecast needs attention after this many complete "
            "24-hour days without a forecast revision. Journal entries do not "
            "reset it.",
            self,
        )
        description.setObjectName("staleThresholdDescription")
        description.setWordWrap(True)
        description.setTextFormat(Qt.TextFormat.PlainText)

        self.threshold_input = QSpinBox(self)
        self.threshold_input.setObjectName("staleThresholdInput")
        self.threshold_input.setRange(
            MIN_STALE_THRESHOLD_DAYS,
            MAX_STALE_THRESHOLD_DAYS,
        )
        self.threshold_input.setSuffix(" days")
        self.threshold_input.setAccessibleName("Needs Attention threshold in days")

        self.save_button = QPushButton("Save threshold", self)
        self.save_button.setObjectName("saveStaleThresholdButton")
        self.save_button.clicked.connect(self._save)

        control_layout = QHBoxLayout()
        control_layout.addWidget(self.threshold_input)
        control_layout.addWidget(self.save_button)
        control_layout.addStretch()

        self.status_label = QLabel(self)
        self.status_label.setObjectName("staleThresholdStatus")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setHidden(True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(control_layout)
        layout.addWidget(self.status_label)
        layout.addStretch()

    def refresh(self) -> None:
        """Load the persisted threshold whenever Settings is entered."""

        try:
            value = self._operations.get_stale_threshold_days()
        except ApplicationError as error:
            self.threshold_input.setEnabled(False)
            self.save_button.setEnabled(False)
            self._show_status(str(error))
            return
        self.threshold_input.setEnabled(True)
        self.save_button.setEnabled(True)
        self.threshold_input.setValue(value)
        self.status_label.setHidden(True)

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

    def _show_status(self, message: str) -> None:
        self.status_label.setText(message)
        self.status_label.setHidden(False)


def _format_local_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")
