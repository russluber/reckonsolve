"""Journal controls and results; rendering, drafts and requests have own owners."""

import logging
from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import DatabaseBusyError, SearchUnavailableError
from reckonsolve.data.forecast_contracts import ForecastContractIntegrityError
from reckonsolve.data.migrations import MigrationError
from reckonsolve.domain.browser import (
    ArchiveDateMeaning,
    ArchiveSort,
    ArchiveTagMatchMode,
)
from reckonsolve.domain.journal import (
    RECENTLY_ACTIVE,
    JournalPage,
    JournalRequest,
    JournalView,
)
from reckonsolve.domain.search import SearchMatchMode
from reckonsolve.ui.components import PageHeader
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    apply_action_role,
    apply_message_role,
    apply_navigation_active,
)

from .filters import JournalFiltersDialog
from .retrieval import JournalRetrieval
from .rows import JournalCard
from .state import JournalState

SORTS = (
    ("Automatic", None),
    ("Recently active", RECENTLY_ACTIVE),
    ("Created · newest", ArchiveSort.CREATED_NEWEST),
    ("Created · oldest", ArchiveSort.CREATED_OLDEST),
    ("Question · A–Z", ArchiveSort.QUESTION_A_TO_Z),
    ("Question · Z–A", ArchiveSort.QUESTION_Z_TO_A),
    ("Last considered · newest", ArchiveSort.FORECAST_CONSIDERED_NEWEST),
    ("Last considered · oldest", ArchiveSort.FORECAST_CONSIDERED_OLDEST),
    ("Expected Resolution · soonest", ArchiveSort.EXPECTED_RESOLUTION_SOONEST),
    ("Expected Resolution · latest", ArchiveSort.EXPECTED_RESOLUTION_LATEST),
    ("Terminal decision · newest", ArchiveSort.TERMINAL_DECISION_NEWEST),
    ("Terminal decision · oldest", ArchiveSort.TERMINAL_DECISION_OLDEST),
)

logger = logging.getLogger(__name__)


class JournalScreen(QWidget):
    prediction_selected = Signal(int, object)
    repair_requested = Signal()
    archive_refused = Signal(object)

    def __init__(
        self,
        query: Callable[[JournalRequest], JournalPage],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.state = JournalState()
        self.page: JournalPage | None = None
        self.available_tags = ()
        self.cards: list[JournalCard] = []
        self.loading = False
        self.loaded_once = False
        self.text_pending = False
        self.refused = False
        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("journalScrollArea")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget(self)
        self.body = QVBoxLayout(self.content)
        self.body.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.body.setContentsMargins(*(int(Spacing.PAGE),) * 4)
        self.body.setSpacing(int(Spacing.ORDINARY))
        self.body.addWidget(PageHeader("Journal", parent=self.content))
        self.search_input = QLineEdit(self.content)
        self.search_input.setObjectName("journalSearchInput")
        self.search_input.setPlaceholderText("Search predictions")
        self.search_input.setAccessibleName("Search predictions")
        self.search_input.setClearButtonEnabled(True)
        search_row = QHBoxLayout()
        search_row.addWidget(self.search_input, 1)
        self.search_button = QPushButton("Search", self.content)
        self.search_button.setObjectName("journalSearchButton")
        apply_action_role(self.search_button, ActionRole.SECONDARY)
        search_row.addWidget(self.search_button)
        self.body.addLayout(search_row)
        views = QHBoxLayout()
        group = QButtonGroup(self)
        group.setExclusive(True)
        self.views = {}
        for title, value in (
            ("All", JournalView.ALL),
            ("Unresolved", JournalView.UNRESOLVED),
            ("Needs postmortem", JournalView.NEEDS_POSTMORTEM),
        ):
            button = QPushButton(title, self.content)
            button.setObjectName(f"journalView{value.value}")
            button.setCheckable(True)
            button.setProperty("journalQuickView", "true")
            group.addButton(button)
            apply_action_role(button, ActionRole.QUIET)
            button.clicked.connect(
                lambda _checked=False, selected=value: self._change(view=selected)
            )
            self.views[value] = button
            views.addWidget(button)
        views.addStretch()
        self.body.addLayout(views)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Sort", self.content))
        self.sort = QComboBox(self.content)
        self.sort.setObjectName("journalSort")
        self.sort.setAccessibleName("Journal sort")
        controls.addWidget(self.sort)
        self.filters_button = QPushButton("Filters", self.content)
        self.filters_button.setObjectName("journalFiltersButton")
        apply_action_role(self.filters_button, ActionRole.SECONDARY)
        controls.addWidget(self.filters_button)
        controls.addStretch()
        self.reset_button = QPushButton("Reset View", self.content)
        self.reset_button.setObjectName("resetJournalViewButton")
        apply_action_role(self.reset_button, ActionRole.QUIET)
        controls.addWidget(self.reset_button)
        self.body.addLayout(controls)
        self.chips_widget = QWidget(self.content)
        self.chips = FlowLayout(self.chips_widget)
        self.body.addWidget(self.chips_widget)
        self.count = QLabel("", self.content)
        self.count.setAccessibleName("Matching Prediction count")
        self.count.setObjectName("journalResultCount")
        self.count.hide()
        self.body.addWidget(self.count)
        self.message = QLabel("Loading Journal…", self.content)
        self.message.setObjectName("journalResultsState")
        self.message.setWordWrap(True)
        self.body.addWidget(self.message)
        self.retry = QPushButton("Try again", self.content)
        self.repair = QPushButton("Repair search", self.content)
        self.suggestion = QPushButton("Suggested search", self.content)
        for button in (self.retry, self.repair, self.suggestion):
            apply_action_role(button, ActionRole.QUIET)
            self.body.addWidget(button, alignment=Qt.AlignmentFlag.AlignLeft)
            button.hide()
        self.results = QVBoxLayout()
        self.results.setContentsMargins(0, 0, 0, 0)
        self.results.setSpacing(0)
        self.body.addLayout(self.results)
        self.more = QPushButton("Load more", self.content)
        self.more.setObjectName("journalLoadMore")
        apply_action_role(self.more, ActionRole.SECONDARY)
        self.more.hide()
        self.body.addWidget(self.more, alignment=Qt.AlignmentFlag.AlignCenter)
        self.body.addStretch()
        self.scroll.setWidget(self.content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.scroll)
        self.retrieval = JournalRetrieval(query, self)
        self.retrieval.pending.connect(self._pending)
        self.retrieval.ready.connect(self._ready)
        self.retrieval.failed.connect(self._failed)
        self.poll = QTimer(self)
        self.poll.setInterval(60_000)
        self.poll.timeout.connect(self.refresh)
        self.search_input.textChanged.connect(self._search_changed)
        self.search_input.returnPressed.connect(self.submit_search)
        self.search_button.clicked.connect(self.submit_search)
        self.sort.currentIndexChanged.connect(self._sort_changed)
        self.filters_button.clicked.connect(self.open_filters)
        self.reset_button.clicked.connect(self.reset_view)
        self.more.clicked.connect(self.load_more)
        self.retry.clicked.connect(self.refresh)
        self.repair.clicked.connect(self.repair_requested)
        self.suggestion.clicked.connect(self._accept_suggestion)
        self._sync_controls()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self.refused:
            self.poll.start()

    def hideEvent(self, event) -> None:
        self.poll.stop()
        super().hideEvent(event)

    def _change(self, **changes) -> None:
        self.text_pending = False
        self.state.change(**changes)
        self._sync_controls()
        self.refresh(restore=False)

    def _search_changed(self, text: str) -> None:
        self.state.change(text=text)
        self._sync_controls()
        # Edited text cannot leave earlier-query rows or counts actionable.
        self.retrieval.invalidate()
        self.text_pending = True
        self._pending()
        self.message.setText("Press Enter or Search to update results.")
        self.scroll.verticalScrollBar().setValue(0)
        if not text.strip():
            self.submit_search()

    def submit_search(self) -> None:
        self.text_pending = False
        self.refresh(restore=False)

    def _accept_suggestion(self) -> None:
        self.search_input.setText(self.suggestion.property("query"))
        self.submit_search()

    def _sort_changed(self) -> None:
        value = self.sort.currentData()
        self._change(
            manual_sort=(
                ArchiveSort(value) if value not in (None, RECENTLY_ACTIVE) else value
            )
        )

    def refresh(self, *, restore: bool = True) -> None:
        if self.text_pending or self.refused:
            return
        if restore and self.page is not None:
            self.capture_anchor()
        self.retrieval.request(self.state.request)

    def capture_anchor(self, *, exclude_id: int | None = None) -> None:
        position = self.scroll.verticalScrollBar().value()
        self.state.scroll_offset = position
        self.state.anchor = tuple(
            (card.prediction_id, position - card.y())
            for card in self.cards
            if card.prediction_id != exclude_id and card.y() + card.height() >= position
        )[:5]

    def _restore_anchor(self) -> None:
        positions = {card.prediction_id: card.y() for card in self.cards}
        offset = self.state.scroll_offset
        for identifier, within in self.state.anchor:
            if identifier in positions:
                offset = positions[identifier] + within
                break
        self.scroll.verticalScrollBar().setValue(max(0, offset))

    def _pending(self) -> None:
        self.loading = True
        self.count.hide()
        self.more.hide()
        for button in (self.retry, self.repair, self.suggestion):
            button.hide()
        self.message.setText(
            "Updating results…" if self.loaded_once else "Loading Journal…"
        )
        apply_message_role(
            self.message, StatusTone.NEUTRAL, accessible_name="Journal retrieval state"
        )
        self.message.show()
        self._clear_rows()

    def _clear_rows(self) -> None:
        self.cards.clear()
        while self.results.count():
            widget = self.results.takeAt(0).widget()
            if widget is not None:
                widget.setEnabled(False)
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

    def _ready(self, page: JournalPage) -> None:
        try:
            self._render_page(page)
        except Exception as error:
            # Rendering is another boundary: retain diagnostics and show failure,
            # never leave a partial actionable listing or claim zero matches.
            logger.exception("Unexpected Journal rendering failure")
            self._clear_rows()
            self._failed(error)

    def _render_page(self, page: JournalPage) -> None:
        if page.request != self.state.request:
            return
        self.loading = False
        self.loaded_once = True
        self.page = page
        self.available_tags = page.available_tags
        self._clear_rows()
        for row in page.rows:
            card = JournalCard(row, page.parsed, self._open, self.content)
            self.results.addWidget(card)
            card.show()
            self.cards.append(card)
        self.message.setVisible(not page.rows)
        if not page.rows:
            self.message.setText(
                "No predictions yet. Create one with + New."
                if not page.request.show_count and page.request.view is JournalView.ALL
                else "No predictions match this view, search, and filters."
            )
        self.count.setText(
            f"{page.total} {'Prediction' if page.total == 1 else 'Predictions'}"
        )
        self.count.setVisible(page.request.show_count)
        self.more.setVisible(page.has_more)
        if page.suggestion:
            self.suggestion.setText(f"Search for “{page.suggestion}” instead")
            self.suggestion.setProperty("query", page.suggestion)
            self.suggestion.show()
        QTimer.singleShot(0, self._restore_anchor)

    def _failed(self, error: Exception) -> None:
        self.loading = False
        self.page = None
        self.message.setText(f"Journal unavailable. {error}")
        apply_message_role(
            self.message, StatusTone.ERROR, accessible_name="Journal retrieval failure"
        )
        self.message.show()
        self.retry.setVisible(isinstance(error, DatabaseBusyError))
        self.repair.setVisible(isinstance(error, SearchUnavailableError))
        if isinstance(error, (ForecastContractIntegrityError, MigrationError)):
            self.archive_refused.emit(error)

    def block_archive(self, error: Exception) -> None:
        """An archive refusal is persistent; neither polling nor old rows recover it."""
        self.refused = True
        self.poll.stop()
        self.retrieval.invalidate()
        self.page = None
        self.loading = False
        self._clear_rows()
        self.count.hide()
        self.more.hide()
        self.message.setText(f"Journal unavailable. {error}")
        apply_message_role(
            self.message, StatusTone.ERROR, accessible_name="Journal archive refusal"
        )
        self.message.show()
        for button in (self.retry, self.repair, self.suggestion):
            button.hide()

    def _open(self, identifier: int, document) -> None:
        if self.loading or self.page is None or self.page.request != self.state.request:
            return
        self.capture_anchor(exclude_id=identifier)
        self.prediction_selected.emit(identifier, document)

    def focus_search(self) -> None:
        self.scroll.ensureWidgetVisible(self.search_input)
        self.search_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search_input.selectAll()

    def open_filters(self) -> None:
        dialog = JournalFiltersDialog(self.state.request, self.available_tags, self)
        if dialog.exec():
            self.state.request = dialog.applied
            self._change(
                filters=dialog.applied.filters,
                match_mode=dialog.applied.match_mode,
                include_history=dialog.applied.include_history,
            )

    def reset_view(self) -> None:
        self.text_pending = False
        self.state.reset()
        self._sync_controls()
        self.refresh(restore=False)

    def load_more(self) -> None:
        self.capture_anchor()
        self.state.request = replace(
            self.state.request, limit=self.state.request.limit + 60
        )
        self.refresh(restore=False)

    def _sync_controls(self) -> None:
        request = self.state.request
        with QSignalBlocker(self.search_input):
            self.search_input.setText(request.text)
        for view, button in self.views.items():
            button.setChecked(view is request.view)
            apply_navigation_active(button, view is request.view)
        with QSignalBlocker(self.sort):
            self.sort.clear()
            for label, value in SORTS:
                if value is None:
                    label = (
                        "Automatic · Relevance"
                        if request.text.strip()
                        else "Automatic · Recently active"
                    )
                self.sort.addItem(label, value)
            if request.text.strip():
                self.sort.addItem("Relevance", ArchiveSort.RELEVANCE)
            self.sort.setCurrentIndex(max(0, self.sort.findData(request.manual_sort)))
        self.chips.clear_widgets()
        filters = request.filters

        def chip(text, change):
            button = QPushButton(f"{text} ×", self.chips_widget)
            button.setAccessibleName(f"Remove {text} filter")
            apply_action_role(button, ActionRole.QUIET)
            button.clicked.connect(change)
            self.chips.addWidget(button)

        if filters.mode:
            chip(
                "One-Shot" if str(filters.mode) == "one_shot" else "Adaptive",
                lambda: self._change(filters=replace(filters, mode=None)),
            )
        if filters.prediction_type:
            chip(
                filters.prediction_type.value.title(),
                lambda: self._change(filters=replace(filters, prediction_type=None)),
            )
        if filters.tags:
            self.chips.addWidget(
                QLabel(
                    "All selected tags"
                    if filters.tag_match_mode is ArchiveTagMatchMode.ALL
                    else "Any selected tag",
                    self.chips_widget,
                )
            )
            for tag in filters.tags:

                def remove_tag(_checked=False, value=tag):
                    remaining = tuple(item for item in filters.tags if item != value)
                    self._change(
                        filters=replace(
                            filters,
                            tags=remaining,
                            tag_match_mode=filters.tag_match_mode
                            if remaining
                            else ArchiveTagMatchMode.ALL,
                        )
                    )

                chip(tag, remove_tag)
        if filters.date_start or filters.date_end:
            start = (
                filters.date_start.strftime("%d %b %Y")
                if filters.date_start
                else "Any start"
            )
            end = (
                filters.date_end.strftime("%d %b %Y") if filters.date_end else "Any end"
            )
            chip(
                f"{filters.date_meaning.value.replace('_', ' ').title()}: {start} – {end}",
                lambda: self._change(
                    filters=replace(
                        filters,
                        date_start=None,
                        date_end=None,
                        date_meaning=ArchiveDateMeaning.CREATED,
                    )
                ),
            )
        if request.match_mode is SearchMatchMode.ANY:
            chip("Any word", lambda: self._change(match_mode=SearchMatchMode.ALL))
        if request.include_history:
            chip(
                "Include superseded history",
                lambda: self._change(include_history=False),
            )
        self.chips_widget.setVisible(self.chips.count() > 0)

    def close_retrieval(self) -> None:
        self.poll.stop()
        self.retrieval.close()
