"""Searchable and filterable prediction archive."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.browser import (
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon


class PredictionBrowserDetailSnapshot(Protocol):
    """Complete prediction data used when opening a browser result."""

    prediction_id: int


class PredictionBrowserOperations(Protocol):
    """Application queries used by the prediction browser."""

    def browse_predictions(
        self,
        question_text: str = "",
        *,
        status: PredictionStatus | None = None,
        tag: str | None = None,
        prediction_type: PredictionType | None = None,
    ) -> PredictionBrowserSnapshot:
        """Return filtered current summaries and the associated tag choices."""

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> PredictionBrowserDetailSnapshot:
        """Return one current prediction for Detail navigation."""


class PredictionBrowserScreen(QWidget):
    """Browse every lifecycle state by question text, status, and tag."""

    prediction_selected = Signal(object)

    def __init__(
        self,
        operations: PredictionBrowserOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionsScreen")
        self._operations = operations
        self._loaded_snapshot: PredictionBrowserSnapshot | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setObjectName("predictionBrowserRefreshTimer")
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh)

        title = QLabel("Predictions", self)
        title.setObjectName("predictionsScreenTitle")

        introduction = QLabel(
            "Search question text or narrow the archive by lifecycle status and tag.",
            self,
        )
        introduction.setObjectName("predictionBrowserIntroduction")
        introduction.setWordWrap(True)
        introduction.setTextFormat(Qt.TextFormat.PlainText)

        search_label = QLabel("Question", self)
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("predictionSearchInput")
        self.search_input.setPlaceholderText("Search question text")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName("Search prediction questions")
        search_label.setBuddy(self.search_input)

        status_label = QLabel("Status", self)
        self.status_filter = QComboBox(self)
        self.status_filter.setObjectName("predictionStatusFilter")
        self.status_filter.setAccessibleName("Filter predictions by status")
        self.status_filter.addItem("All", None)
        for status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
            PredictionStatus.RESOLVED,
            PredictionStatus.INVALID,
        ):
            self.status_filter.addItem(status.value.title(), status.value)
        status_label.setBuddy(self.status_filter)

        type_label = QLabel("Forecast type", self)
        self.type_filter = QComboBox(self)
        self.type_filter.setObjectName("predictionTypeFilter")
        self.type_filter.setAccessibleName("Filter predictions by forecast type")
        self.type_filter.addItem("All types", None)
        self.type_filter.addItem("Binary", PredictionType.BINARY.value)
        self.type_filter.addItem("Numeric", PredictionType.NUMERIC.value)
        type_label.setBuddy(self.type_filter)

        tag_label = QLabel("Tag", self)
        self.tag_filter = QComboBox(self)
        self.tag_filter.setObjectName("predictionTagFilter")
        self.tag_filter.setAccessibleName("Filter predictions by tag")
        self.tag_filter.addItem("All tags", None)
        tag_label.setBuddy(self.tag_filter)

        self.apply_button = QPushButton("Apply filters", self)
        self.apply_button.setObjectName("applyPredictionFiltersButton")
        apply_lucide_icon(self.apply_button, LucideIcon.LIST_FILTER)
        self.clear_button = QPushButton("Clear filters", self)
        self.clear_button.setObjectName("clearPredictionFiltersButton")
        apply_lucide_icon(self.clear_button, LucideIcon.ERASER)

        search_layout = QHBoxLayout()
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input, 1)

        filter_controls = QHBoxLayout()
        filter_controls.addWidget(status_label)
        filter_controls.addWidget(self.status_filter)
        filter_controls.addWidget(type_label)
        filter_controls.addWidget(self.type_filter)
        filter_controls.addWidget(tag_label)
        filter_controls.addWidget(self.tag_filter)
        filter_controls.addWidget(self.apply_button)
        filter_controls.addWidget(self.clear_button)
        filter_controls.addStretch()

        filters_layout = QVBoxLayout()
        filters_layout.addLayout(search_layout)
        filters_layout.addLayout(filter_controls)

        self.error_label = QLabel(self)
        self.error_label.setObjectName("predictionBrowserError")
        self.error_label.setWordWrap(True)
        self.error_label.setTextFormat(Qt.TextFormat.PlainText)
        self.error_label.setHidden(True)

        self.result_count_label = QLabel(self)
        self.result_count_label.setObjectName("predictionBrowserResultCount")
        self.result_count_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_count_label.setHidden(True)

        self.results_list = QListWidget(self)
        self.results_list.setObjectName("predictionBrowserResults")
        self.results_list.setAccessibleName("Prediction search results")
        self.results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setWordWrap(True)
        self.results_list.setHidden(True)

        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("predictionBrowserEmpty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setTextFormat(Qt.TextFormat.PlainText)
        self.empty_label.setHidden(True)

        self.open_button = QPushButton("Open selected", self)
        self.open_button.setObjectName("openSelectedPredictionButton")
        apply_lucide_icon(self.open_button, LucideIcon.ARROW_RIGHT)
        self.open_button.setEnabled(False)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self.open_button)
        actions_layout.addStretch()

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(introduction)
        layout.addLayout(filters_layout)
        layout.addWidget(self.error_label)
        layout.addWidget(self.result_count_label)
        layout.addWidget(self.results_list, 1)
        layout.addWidget(self.empty_label)
        layout.addLayout(actions_layout)

        self.apply_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.clear_filters)
        self.search_input.returnPressed.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.results_list.currentItemChanged.connect(self._selection_changed)
        self.results_list.itemActivated.connect(self._open_item)
        self.open_button.clicked.connect(self._open_current_item)

    def showEvent(self, event: QShowEvent) -> None:
        """Keep derived Locked status current while the browser remains visible."""

        super().showEvent(event)
        if not self._refresh_timer.isActive():
            self._refresh_timer.start()

    def hideEvent(self, event: QHideEvent) -> None:
        """Stop polling while another primary screen is active."""

        self._refresh_timer.stop()
        super().hideEvent(event)

    def refresh(self) -> None:
        """Reload the current filter, retaining prior rows only with a warning."""

        selected_tag = self._selected_tag()
        try:
            snapshot = self._operations.browse_predictions(
                self.search_input.text(),
                status=self._selected_status(),
                tag=selected_tag,
                prediction_type=self._selected_prediction_type(),
            )
            if selected_tag is not None and selected_tag.casefold() not in {
                item.casefold() for item in snapshot.available_tags
            }:
                with QSignalBlocker(self.tag_filter):
                    self.tag_filter.setCurrentIndex(0)
                snapshot = self._operations.browse_predictions(
                    self.search_input.text(),
                    status=self._selected_status(),
                    tag=None,
                    prediction_type=self._selected_prediction_type(),
                )
        except ApplicationError as error:
            if self._loaded_snapshot is None:
                self.error_label.setText(f"Predictions unavailable. {error}")
                self.result_count_label.setHidden(True)
                self.results_list.setHidden(True)
                self.empty_label.setHidden(True)
                self.open_button.setEnabled(False)
            else:
                self.error_label.setText(
                    "Predictions could not refresh; showing the last loaded "
                    f"results. {error}"
                )
            self.error_label.setHidden(False)
            return

        self.error_label.setHidden(True)
        self._loaded_snapshot = snapshot
        self._update_tag_choices(snapshot.available_tags)
        self._render(snapshot)

    def clear_filters(self) -> None:
        """Restore the unfiltered archive and query once."""

        self.search_input.clear()
        with (
            QSignalBlocker(self.status_filter),
            QSignalBlocker(self.type_filter),
            QSignalBlocker(self.tag_filter),
        ):
            self.status_filter.setCurrentIndex(0)
            self.type_filter.setCurrentIndex(0)
            self.tag_filter.setCurrentIndex(0)
        self.refresh()

    def focus_search(self) -> None:
        """Put keyboard focus on question search when entering the screen."""

        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _render(self, snapshot: PredictionBrowserSnapshot) -> None:
        self.results_list.clear()
        self.open_button.setEnabled(False)
        count = len(snapshot.predictions)
        noun = "prediction" if count == 1 else "predictions"
        self.result_count_label.setText(f"{count} {noun}")
        self.result_count_label.setHidden(False)

        if not snapshot.predictions:
            self.results_list.setHidden(True)
            self.empty_label.setText(
                "No predictions yet. Create one from New Prediction."
                if not self._has_active_filters()
                else "No predictions match the current search and filters."
            )
            self.empty_label.setHidden(False)
            return

        self.empty_label.setHidden(True)
        self.results_list.setHidden(False)
        for prediction in snapshot.predictions:
            item = QListWidgetItem(self._row_text(prediction))
            item.setData(Qt.ItemDataRole.UserRole, prediction.prediction_id)
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                prediction.question,
            )
            item.setData(
                Qt.ItemDataRole.AccessibleDescriptionRole,
                self._row_description(prediction),
            )
            item.setToolTip("Open Prediction Detail")
            self.results_list.addItem(item)
        self.results_list.setCurrentRow(0)

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

    def _selected_status(self) -> PredictionStatus | None:
        value = self.status_filter.currentData()
        return None if value is None else PredictionStatus(str(value))

    def _selected_tag(self) -> str | None:
        value = self.tag_filter.currentData()
        return None if value is None else str(value)

    def _selected_prediction_type(self) -> PredictionType | None:
        value = self.type_filter.currentData()
        return None if value is None else PredictionType(str(value))

    def _has_active_filters(self) -> bool:
        return bool(
            self.search_input.text().strip()
            or self._selected_status() is not None
            or self._selected_prediction_type() is not None
            or self._selected_tag() is not None
        )

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self.open_button.setEnabled(current is not None)

    def _open_current_item(self) -> None:
        current = self.results_list.currentItem()
        if current is not None:
            self._open_item(current)

    def _open_item(self, item: QListWidgetItem) -> None:
        prediction_id = int(item.data(Qt.ItemDataRole.UserRole))
        try:
            prediction = self._operations.get_prediction_for_navigation(prediction_id)
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self.prediction_selected.emit(prediction)

    @staticmethod
    def _row_text(prediction: PredictionBrowserItem) -> str:
        tags = "" if not prediction.tags else f"\nTags: {', '.join(prediction.tags)}"
        return (
            f"{prediction.question}\n"
            f"{_forecast_summary(prediction)}  |  {prediction.status.value.upper()}"
            f"{tags}\n"
            f"Forecast updated {_format_local_timestamp(prediction.latest_revision_at)}"
        )

    @staticmethod
    def _row_description(prediction: PredictionBrowserItem) -> str:
        tag_text = (
            "" if not prediction.tags else f" Tags: {', '.join(prediction.tags)}."
        )
        return (
            f"{_forecast_summary(prediction)}. "
            f"{prediction.status.value}. Forecast updated "
            f"{_format_local_timestamp(prediction.latest_revision_at)}.{tag_text}"
        )


def _format_local_timestamp(value: datetime) -> str:
    return value.astimezone().strftime("%b %d, %Y, %I:%M %p").replace(" 0", " ")


def _forecast_summary(prediction: PredictionBrowserItem) -> str:
    """Return an unambiguous compact current-forecast summary for a result."""

    if prediction.prediction_type is PredictionType.BINARY:
        if prediction.probability_percent is None:
            raise ValueError("A Binary browser row requires a probability.")
        return f"BINARY  {prediction.probability_percent}%"
    if (
        prediction.numeric_lower_bound is None
        or prediction.numeric_median_estimate is None
        or prediction.numeric_upper_bound is None
        or prediction.numeric_confidence_percent is None
        or prediction.numeric_unit is None
    ):
        raise ValueError("A Numeric browser row requires complete interval data.")
    return (
        f"NUMERIC  {prediction.numeric_confidence_percent}% interval: "
        f"{prediction.numeric_lower_bound}–{prediction.numeric_upper_bound} "
        f"{prediction.numeric_unit}; median: "
        f"{prediction.numeric_median_estimate} {prediction.numeric_unit}"
    )
