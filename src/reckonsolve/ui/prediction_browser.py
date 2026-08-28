"""Searchable and filterable prediction archive."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Protocol

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QHideEvent, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.browser import (
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.search import (
    ParsedSearchText,
    PredictionSearchHit,
    PredictionSearchResults,
    SearchDocument,
    SearchMatchMode,
    SearchPrediction,
    build_search_snippet,
    search_source_label,
)
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

    def search_predictions(
        self,
        text: str,
        *,
        match_mode: SearchMatchMode = SearchMatchMode.ALL,
        include_superseded: bool = False,
        status: PredictionStatus | None = None,
        tag: str | None = None,
        prediction_type: PredictionType | None = None,
    ) -> PredictionSearchResults:
        """Return grouped explainable full-text results."""

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> PredictionBrowserDetailSnapshot:
        """Return one current prediction for Detail navigation."""


class PredictionBrowserScreen(QWidget):
    """Browse every lifecycle state by question text, status, and tag."""

    prediction_selected = Signal(object)
    search_result_selected = Signal(object, object)

    def __init__(
        self,
        operations: PredictionBrowserOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionsScreen")
        self._operations = operations
        self._loaded_snapshot: (
            PredictionBrowserSnapshot | PredictionSearchResults | None
        ) = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setObjectName("predictionBrowserRefreshTimer")
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._search_debounce = QTimer(self)
        self._search_debounce.setObjectName("predictionSearchDebounceTimer")
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(250)
        self._search_debounce.timeout.connect(self.refresh)

        title = QLabel("Predictions", self)
        title.setObjectName("predictionsScreenTitle")

        introduction = QLabel(
            "Search questions, reasoning, Journal entries, and outcomes, or narrow "
            "the archive by lifecycle status and tag.",
            self,
        )
        introduction.setObjectName("predictionBrowserIntroduction")
        introduction.setWordWrap(True)
        introduction.setTextFormat(Qt.TextFormat.PlainText)

        search_label = QLabel("Search", self)
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("predictionSearchInput")
        self.search_input.setPlaceholderText(
            'Words or a quoted phrase, such as calibration or "new evidence"'
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName("Search prediction history")
        search_label.setBuddy(self.search_input)

        match_label = QLabel("Words", self)
        self.match_mode = QComboBox(self)
        self.match_mode.setObjectName("predictionSearchMatchMode")
        self.match_mode.setAccessibleName("Choose how search words match")
        self.match_mode.addItem("All words", SearchMatchMode.ALL.value)
        self.match_mode.addItem("Any word", SearchMatchMode.ANY.value)
        match_label.setBuddy(self.match_mode)

        self.include_history = QCheckBox("Include superseded history", self)
        self.include_history.setObjectName("predictionSearchIncludeHistory")
        self.include_history.setToolTip(
            "Also search earlier corrected or definition text. Historical-only "
            "matches are labeled as superseded."
        )

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
        search_layout.addWidget(match_label)
        search_layout.addWidget(self.match_mode)
        search_layout.addWidget(self.include_history)

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

        self.empty_label = QLabel(self)
        self.empty_label.setObjectName("predictionBrowserEmpty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setTextFormat(Qt.TextFormat.PlainText)
        self.empty_label.setHidden(True)

        self.any_word_button = QPushButton("Search for any word", self)
        self.any_word_button.setObjectName("predictionSearchAnyWordButton")
        self.any_word_button.setHidden(True)
        self.suggestion_button = QPushButton(self)
        self.suggestion_button.setObjectName("predictionSearchSuggestionButton")
        self.suggestion_button.setHidden(True)

        guidance_layout = QHBoxLayout()
        guidance_layout.addWidget(self.any_word_button)
        guidance_layout.addWidget(self.suggestion_button)
        guidance_layout.addStretch()

        self.empty_results_page = QWidget(self)
        self.empty_results_page.setObjectName("predictionBrowserEmptyResultsPage")
        empty_results_layout = QVBoxLayout(self.empty_results_page)
        empty_results_layout.setContentsMargins(0, 0, 0, 0)
        empty_results_layout.addWidget(self.empty_label)
        empty_results_layout.addLayout(guidance_layout)
        empty_results_layout.addStretch()

        self.results_region = QStackedWidget(self)
        self.results_region.setObjectName("predictionBrowserResultsRegion")
        self.results_region.addWidget(self.results_list)
        self.results_region.addWidget(self.empty_results_page)
        self.results_region.setCurrentWidget(self.empty_results_page)

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
        layout.addWidget(self.results_region, 1)
        layout.addLayout(actions_layout)

        self.apply_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.clear_filters)
        self.search_input.returnPressed.connect(self.refresh)
        self.search_input.textEdited.connect(self._search_text_edited)
        self.match_mode.currentIndexChanged.connect(self.refresh)
        self.include_history.toggled.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.tag_filter.currentIndexChanged.connect(self.refresh)
        self.results_list.currentItemChanged.connect(self._selection_changed)
        self.results_list.itemActivated.connect(self._open_item)
        self.open_button.clicked.connect(self._open_current_item)
        self.any_word_button.clicked.connect(self._search_for_any_word)
        self.suggestion_button.clicked.connect(self._accept_suggestion)

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

        self._search_debounce.stop()
        selected_tag = self._selected_tag()
        try:
            snapshot = self._query(selected_tag)
            if selected_tag is not None and selected_tag.casefold() not in {
                item.casefold() for item in snapshot.available_tags
            }:
                with QSignalBlocker(self.tag_filter):
                    self.tag_filter.setCurrentIndex(0)
                snapshot = self._query(None)
        except ApplicationError as error:
            if self._loaded_snapshot is None:
                self.error_label.setText(f"Predictions unavailable. {error}")
                self.result_count_label.setHidden(True)
                self.empty_label.setHidden(True)
                self.results_region.setCurrentWidget(self.empty_results_page)
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

    def _query(
        self,
        selected_tag: str | None,
    ) -> PredictionBrowserSnapshot | PredictionSearchResults:
        text = self.search_input.text()
        if text.strip():
            return self._operations.search_predictions(
                text,
                match_mode=self._selected_match_mode(),
                include_superseded=self.include_history.isChecked(),
                status=self._selected_status(),
                tag=selected_tag,
                prediction_type=self._selected_prediction_type(),
            )
        return self._operations.browse_predictions(
            "",
            status=self._selected_status(),
            tag=selected_tag,
            prediction_type=self._selected_prediction_type(),
        )

    def clear_filters(self) -> None:
        """Restore the unfiltered archive and query once."""

        self.search_input.clear()
        with (
            QSignalBlocker(self.status_filter),
            QSignalBlocker(self.type_filter),
            QSignalBlocker(self.tag_filter),
            QSignalBlocker(self.match_mode),
            QSignalBlocker(self.include_history),
        ):
            self.status_filter.setCurrentIndex(0)
            self.type_filter.setCurrentIndex(0)
            self.tag_filter.setCurrentIndex(0)
            self.match_mode.setCurrentIndex(0)
            self.include_history.setChecked(False)
        self.refresh()

    def focus_search(self) -> None:
        """Put keyboard focus on question search when entering the screen."""

        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def _render(
        self,
        snapshot: PredictionBrowserSnapshot | PredictionSearchResults,
    ) -> None:
        if isinstance(snapshot, PredictionSearchResults):
            self._render_search_results(snapshot)
        else:
            self._render_archive(snapshot)

    def _prepare_results(self, count: int) -> None:
        self.results_list.clear()
        self.open_button.setEnabled(False)
        self.any_word_button.setHidden(True)
        self.suggestion_button.setHidden(True)
        noun = "prediction" if count == 1 else "predictions"
        self.result_count_label.setText(f"{count} {noun}")
        self.result_count_label.setHidden(False)

    def _render_archive(self, snapshot: PredictionBrowserSnapshot) -> None:
        self._prepare_results(len(snapshot.predictions))

        if not snapshot.predictions:
            self.results_region.setCurrentWidget(self.empty_results_page)
            self.empty_label.setText(
                "No predictions yet. Create one from New Prediction."
                if not self._has_active_filters()
                else "No predictions match the current search and filters."
            )
            self.empty_label.setHidden(False)
            return

        self.empty_label.setHidden(True)
        self.results_region.setCurrentWidget(self.results_list)
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

    def _render_search_results(self, results: PredictionSearchResults) -> None:
        self._prepare_results(len(results.hits))
        if not results.hits:
            self.results_region.setCurrentWidget(self.empty_results_page)
            if results.any_word_available:
                self.empty_label.setText(
                    "No predictions match all words. You can deliberately search "
                    "for any word instead."
                )
                self.any_word_button.setHidden(False)
            else:
                self.empty_label.setText(
                    "No predictions match the current search and filters."
                )
            if results.suggestion is not None:
                self.suggestion_button.setText(
                    f"Search for “{results.suggestion}” instead"
                )
                self.suggestion_button.setProperty(
                    "suggestedSearchText", results.suggestion
                )
                self.suggestion_button.setHidden(False)
            self.empty_label.setHidden(False)
            return

        self.empty_label.setHidden(True)
        self.results_region.setCurrentWidget(self.results_list)
        for hit in results.hits:
            item = QListWidgetItem(self._search_row_text(hit))
            item.setData(Qt.ItemDataRole.UserRole, hit.prediction.prediction_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, hit.best_match.document)
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                hit.prediction.question,
            )
            item.setData(
                Qt.ItemDataRole.AccessibleDescriptionRole,
                self._search_row_description(hit),
            )
            item.setToolTip("Open Prediction Detail at this matching context")
            row = self._search_result_widget(hit)
            item.setSizeHint(row.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, row)

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

    def _selected_match_mode(self) -> SearchMatchMode:
        return SearchMatchMode(str(self.match_mode.currentData()))

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

    def _search_text_edited(self, _text: str) -> None:
        self._search_debounce.start()

    def _search_for_any_word(self) -> None:
        index = self.match_mode.findData(SearchMatchMode.ANY.value)
        if self.match_mode.currentIndex() == index:
            self.refresh()
        else:
            self.match_mode.setCurrentIndex(index)

    def _accept_suggestion(self) -> None:
        suggestion = self.suggestion_button.property("suggestedSearchText")
        if suggestion is None:
            return
        self.search_input.setText(str(suggestion))
        self.refresh()
        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)

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
        search_document = item.data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(search_document, SearchDocument):
            self.search_result_selected.emit(prediction, search_document)
        else:
            self.prediction_selected.emit(prediction)

    def _search_result_widget(self, hit: PredictionSearchHit) -> QWidget:
        row = QFrame(self.results_list)
        row.setObjectName(f"predictionSearchResult{hit.prediction.prediction_id}")
        row.setFrameShape(QFrame.Shape.StyledPanel)
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(3)

        question = QLabel(hit.prediction.question, row)
        question.setObjectName(
            f"predictionSearchResultQuestion{hit.prediction.prediction_id}"
        )
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setWordWrap(True)
        question_font = question.font()
        question_font.setBold(True)
        question.setFont(question_font)
        layout.addWidget(question)

        summary = QLabel(_search_prediction_summary(hit.prediction), row)
        summary.setObjectName(
            f"predictionSearchResultSummary{hit.prediction.prediction_id}"
        )
        summary.setTextFormat(Qt.TextFormat.PlainText)
        summary.setWordWrap(True)
        layout.addWidget(summary)

        if hit.prediction.tags:
            tags = QLabel(f"Tags: {', '.join(hit.prediction.tags)}", row)
            tags.setTextFormat(Qt.TextFormat.PlainText)
            tags.setWordWrap(True)
            layout.addWidget(tags)

        source = QLabel(search_source_label(hit.best_match.document), row)
        source.setObjectName(
            f"predictionSearchResultSource{hit.prediction.prediction_id}"
        )
        source.setTextFormat(Qt.TextFormat.PlainText)
        source_font = source.font()
        source_font.setItalic(True)
        source.setFont(source_font)
        layout.addWidget(source)

        snippet = build_search_snippet(
            hit.best_match.document.text,
            self._current_parsed_search_text(),
        )
        snippet_label = QLabel(_snippet_html(snippet.text, snippet.match_spans), row)
        snippet_label.setObjectName(
            f"predictionSearchResultSnippet{hit.prediction.prediction_id}"
        )
        snippet_label.setTextFormat(Qt.TextFormat.RichText)
        snippet_label.setWordWrap(True)
        layout.addWidget(snippet_label)

        if hit.additional_match_count:
            noun = "source" if hit.additional_match_count == 1 else "sources"
            additional = QLabel(
                f"+{hit.additional_match_count} additional matching {noun}", row
            )
            additional.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(additional)
        return row

    def _current_parsed_search_text(self) -> ParsedSearchText:
        loaded = self._loaded_snapshot
        if isinstance(loaded, PredictionSearchResults):
            return loaded.parsed_text
        raise RuntimeError("A search row requires loaded parsed search text.")

    @staticmethod
    def _search_row_text(hit: PredictionSearchHit) -> str:
        tags = (
            ""
            if not hit.prediction.tags
            else f"\nTags: {', '.join(hit.prediction.tags)}"
        )
        additional = (
            ""
            if not hit.additional_match_count
            else f"\n+{hit.additional_match_count} additional matches"
        )
        return (
            f"{hit.prediction.question}\n"
            f"{_search_prediction_summary(hit.prediction)}{tags}\n"
            f"{search_source_label(hit.best_match.document)}\n"
            f"{hit.best_match.document.text}{additional}"
        )

    @staticmethod
    def _search_row_description(hit: PredictionSearchHit) -> str:
        history = (
            " Superseded historical text."
            if hit.best_match.document.is_superseded
            else ""
        )
        return (
            f"{_search_prediction_summary(hit.prediction)}. "
            f"{search_source_label(hit.best_match.document)}. "
            f"{hit.best_match.document.text}.{history} "
            f"{hit.additional_match_count} additional matching sources."
        )

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


def _search_prediction_summary(prediction: SearchPrediction) -> str:
    """Render current forecast context or an effective terminal result."""

    status = prediction.status.value.upper()
    if (
        prediction.status is PredictionStatus.RESOLVED
        and prediction.prediction_type is PredictionType.BINARY
        and prediction.binary_outcome is not None
    ):
        return f"BINARY  RESOLVED {prediction.binary_outcome.value.upper()}"
    if (
        prediction.status is PredictionStatus.RESOLVED
        and prediction.prediction_type is PredictionType.NUMERIC
        and prediction.numeric_actual_value is not None
        and prediction.numeric_unit is not None
    ):
        return (
            f"NUMERIC  RESOLVED {prediction.numeric_actual_value} "
            f"{prediction.numeric_unit}"
        )
    if prediction.prediction_type is PredictionType.BINARY:
        if prediction.probability_percent is None:
            raise ValueError("A Binary search result requires a probability.")
        return f"BINARY  {prediction.probability_percent}%  |  {status}"
    if (
        prediction.numeric_lower_bound is None
        or prediction.numeric_median_estimate is None
        or prediction.numeric_upper_bound is None
        or prediction.numeric_confidence_percent is None
        or prediction.numeric_unit is None
    ):
        raise ValueError("A Numeric search result requires complete interval data.")
    return (
        f"NUMERIC  {prediction.numeric_confidence_percent}% interval: "
        f"{prediction.numeric_lower_bound}–{prediction.numeric_upper_bound} "
        f"{prediction.numeric_unit}; median: {prediction.numeric_median_estimate} "
        f"{prediction.numeric_unit}  |  {status}"
    )


def _snippet_html(text: str, spans: tuple[tuple[int, int], ...]) -> str:
    """Escape every source character before adding controlled emphasis tags."""

    pieces: list[str] = []
    cursor = 0
    for start, end in spans:
        if start < cursor or end <= start or end > len(text):
            continue
        pieces.append(escape(text[cursor:start]))
        pieces.append(f"<b>{escape(text[start:end])}</b>")
        cursor = end
    pieces.append(escape(text[cursor:]))
    return "".join(pieces)
