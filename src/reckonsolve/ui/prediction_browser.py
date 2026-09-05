"""Searchable and filterable prediction archive."""

from __future__ import annotations

from datetime import date, datetime
from html import escape
from typing import Protocol

from PySide6.QtCore import QDate, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QHideEvent, QResizeEvent, QShowEvent, QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveQuery,
    ArchiveSort,
    ArchiveTagMatchMode,
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.predictions import PredictionStatus, PredictionType
from reckonsolve.domain.saved_views import SavedView, SavedViewConfiguration
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
from reckonsolve.ui.components import (
    ContentPanel,
    PageHeader,
    PersistentMessageLabel,
    StatusBadge,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.tag_filter_picker import TagFilterPicker
from reckonsolve.ui.tag_manager import TagManagementOperations, TagManagerDialog
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    TextRole,
    apply_action_role,
    apply_text_role,
)


class PredictionBrowserDetailSnapshot(Protocol):
    """Complete prediction data used when opening a browser result."""

    prediction_id: int


class PredictionBrowserOperations(TagManagementOperations, Protocol):
    """Application queries used by the prediction browser."""

    def browse_predictions(
        self,
        question_text: str = "",
        *,
        status: PredictionStatus | None = None,
        tag: str | None = None,
        prediction_type: PredictionType | None = None,
        tags: tuple[str, ...] = (),
        tag_match_mode: ArchiveTagMatchMode = ArchiveTagMatchMode.ALL,
        attention: ArchiveAttention | None = None,
        date_meaning: ArchiveDateMeaning = ArchiveDateMeaning.CREATED,
        date_start: date | None = None,
        date_end: date | None = None,
        sort: ArchiveSort = ArchiveSort.CREATED_NEWEST,
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
        tags: tuple[str, ...] = (),
        tag_match_mode: ArchiveTagMatchMode = ArchiveTagMatchMode.ALL,
        attention: ArchiveAttention | None = None,
        date_meaning: ArchiveDateMeaning = ArchiveDateMeaning.CREATED,
        date_start: date | None = None,
        date_end: date | None = None,
        sort: ArchiveSort = ArchiveSort.RELEVANCE,
    ) -> PredictionSearchResults:
        """Return grouped explainable full-text results."""

    def get_prediction_for_navigation(
        self,
        prediction_id: int,
    ) -> PredictionBrowserDetailSnapshot:
        """Return one current prediction for Detail navigation."""

    def list_saved_views(self) -> tuple[SavedView, ...]:
        """Return mutable archive configurations without result membership."""

    def create_saved_view(
        self, name: str, configuration: SavedViewConfiguration
    ) -> SavedView:
        """Persist one named dynamic archive configuration."""

    def update_saved_view(
        self, saved_view_id: int, configuration: SavedViewConfiguration
    ) -> SavedView:
        """Explicitly replace one Saved View configuration."""

    def rename_saved_view(self, saved_view_id: int, name: str) -> SavedView:
        """Rename one mutable Saved View."""

    def delete_saved_view(self, saved_view_id: int) -> None:
        """Delete one mutable Saved View only."""


def _control_section(
    title: str,
    supporting_text: str | None,
    object_name: str,
    parent: QWidget,
) -> tuple[QFrame, QVBoxLayout]:
    """Build one calm, labeled archive-control region."""

    section = QFrame(parent)
    section.setObjectName(object_name)
    layout = QVBoxLayout(section)
    layout.setContentsMargins(
        0,
        int(Spacing.COMPACT),
        0,
        int(Spacing.COMPACT),
    )
    layout.setSpacing(int(Spacing.CONTROL))
    title_label = QLabel(title, section)
    title_label.setTextFormat(Qt.TextFormat.PlainText)
    apply_text_role(title_label, TextRole.SECTION_TITLE)
    layout.addWidget(title_label)
    supporting_label = QLabel(supporting_text or "", section)
    supporting_label.setTextFormat(Qt.TextFormat.PlainText)
    supporting_label.setWordWrap(True)
    supporting_label.setHidden(not bool(supporting_text))
    apply_text_role(supporting_label, TextRole.SECONDARY)
    layout.addWidget(supporting_label)
    return section, layout


class _ArchiveComboBox(QComboBox):
    """Let a narrow controls pane own wheel scrolling over closed combos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._wheel_changes_enabled = True
        self._wheel_scroll_target: QScrollArea | None = None
        self._wide_focus_policy = self.focusPolicy()

    @property
    def wheel_changes_enabled(self) -> bool:
        return self._wheel_changes_enabled

    def set_wheel_changes_enabled(self, enabled: bool) -> None:
        self._wheel_changes_enabled = enabled
        self.setFocusPolicy(
            self._wide_focus_policy if enabled else Qt.FocusPolicy.StrongFocus
        )

    def set_wheel_scroll_target(self, target: QScrollArea) -> None:
        self._wheel_scroll_target = target

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._wheel_changes_enabled and not self.view().isVisible():
            if self._wheel_scroll_target is None:
                event.ignore()
                return
            forwarded_event = QWheelEvent(event)
            QApplication.sendEvent(
                self._wheel_scroll_target.viewport(),
                forwarded_event,
            )
            event.setAccepted(forwarded_event.isAccepted())
            return
        super().wheelEvent(event)


class _ArchiveDateEdit(QDateEdit):
    """Protect a narrow archive date from incidental wheel changes."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._wheel_changes_enabled = True
        self._wheel_scroll_target: QScrollArea | None = None
        self._wide_focus_policy = self.focusPolicy()

    @property
    def wheel_changes_enabled(self) -> bool:
        return self._wheel_changes_enabled

    def set_wheel_changes_enabled(self, enabled: bool) -> None:
        self._wheel_changes_enabled = enabled
        self.setFocusPolicy(
            self._wide_focus_policy if enabled else Qt.FocusPolicy.StrongFocus
        )

    def set_wheel_scroll_target(self, target: QScrollArea) -> None:
        self._wheel_scroll_target = target

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self._wheel_changes_enabled and not self.calendarWidget().isVisible():
            if self._wheel_scroll_target is None:
                event.ignore()
                return
            forwarded_event = QWheelEvent(event)
            QApplication.sendEvent(
                self._wheel_scroll_target.viewport(),
                forwarded_event,
            )
            event.setAccepted(forwarded_event.isAccepted())
            return
        super().wheelEvent(event)


class PredictionBrowserScreen(QWidget):
    """Browse every lifecycle state by question text, status, and tag."""

    _SIDE_BY_SIDE_MINIMUM_WIDTH = 1080

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
        self._saved_views: dict[int, SavedView] = {}
        self._active_saved_view_id: int | None = None
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setObjectName("predictionBrowserRefreshTimer")
        self._refresh_timer.setInterval(60_000)
        self._refresh_timer.timeout.connect(self.refresh)
        self._search_debounce = QTimer(self)
        self._search_debounce.setObjectName("predictionSearchDebounceTimer")
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(250)
        self._search_debounce.timeout.connect(self.refresh)

        header = PageHeader(
            "Predictions",
            "Search questions, reasoning, Journal entries, and outcomes, or narrow "
            "the archive with structured filters.",
            title_object_name="predictionsScreenTitle",
            supporting_object_name="predictionBrowserIntroduction",
            parent=self,
        )

        saved_view_label = QLabel("Saved View", self)
        saved_view_label.setObjectName("savedViewLabel")
        self.saved_view_picker = _ArchiveComboBox(self)
        self.saved_view_picker.setObjectName("savedViewPicker")
        self.saved_view_picker.setAccessibleName("Apply a Saved View")
        self.saved_view_picker.addItem("No Saved View", None)
        saved_view_label.setBuddy(self.saved_view_picker)
        self.saved_view_state = QLabel(self)
        self.saved_view_state.setObjectName("savedViewState")
        self.saved_view_state.setTextFormat(Qt.TextFormat.PlainText)
        self.save_current_view_button = QPushButton("Save current…", self)
        self.save_current_view_button.setObjectName("saveCurrentViewButton")
        self.save_current_view_button.setAccessibleName(
            "Save current filters as a Saved View"
        )
        apply_lucide_icon(self.save_current_view_button, LucideIcon.SAVE)
        self.save_as_new_button = QPushButton("Save as new…", self)
        self.save_as_new_button.setObjectName("saveViewAsNewButton")
        apply_lucide_icon(self.save_as_new_button, LucideIcon.CIRCLE_PLUS)
        self.update_saved_view_button = QPushButton("Update", self)
        self.update_saved_view_button.setObjectName("updateSavedViewButton")
        self.update_saved_view_button.setAccessibleName("Update selected Saved View")
        apply_lucide_icon(self.update_saved_view_button, LucideIcon.REFRESH)
        self.rename_saved_view_button = QPushButton("Rename", self)
        self.rename_saved_view_button.setObjectName("renameSavedViewButton")
        apply_lucide_icon(self.rename_saved_view_button, LucideIcon.PENCIL)
        self.delete_saved_view_button = QPushButton("Delete", self)
        self.delete_saved_view_button.setObjectName("deleteSavedViewButton")
        apply_lucide_icon(self.delete_saved_view_button, LucideIcon.TRASH)
        self.manage_tags_button = QPushButton("Manage Tags…", self)
        self.manage_tags_button.setObjectName("manageTagsButton")
        apply_lucide_icon(self.manage_tags_button, LucideIcon.SETTINGS)

        search_label = QLabel("Search", self)
        search_label.setObjectName("predictionSearchLabel")
        self.search_input = QLineEdit(self)
        self.search_input.setObjectName("predictionSearchInput")
        self.search_input.setPlaceholderText(
            'Words or a quoted phrase, such as calibration or "new evidence"'
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setAccessibleName("Search prediction history")
        search_label.setBuddy(self.search_input)

        match_label = QLabel("Words", self)
        self.match_mode = _ArchiveComboBox(self)
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
        self.status_filter = _ArchiveComboBox(self)
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
        self.type_filter = _ArchiveComboBox(self)
        self.type_filter.setObjectName("predictionTypeFilter")
        self.type_filter.setAccessibleName("Filter predictions by forecast type")
        self.type_filter.addItem("All types", None)
        self.type_filter.addItem("Binary", PredictionType.BINARY.value)
        self.type_filter.addItem("Numeric", PredictionType.NUMERIC.value)
        type_label.setBuddy(self.type_filter)

        tag_label = QLabel("Tags", self)
        self.tag_filter = TagFilterPicker(self)
        tag_label.setBuddy(self.tag_filter.search_input)

        tag_mode_label = QLabel("Tag match", self)
        self.tag_match_mode = _ArchiveComboBox(self)
        self.tag_match_mode.setObjectName("predictionTagMatchMode")
        self.tag_match_mode.addItem("All selected", ArchiveTagMatchMode.ALL.value)
        self.tag_match_mode.addItem("Any selected", ArchiveTagMatchMode.ANY.value)
        tag_mode_label.setBuddy(self.tag_match_mode)

        attention_label = QLabel("Attention", self)
        self.attention_filter = _ArchiveComboBox(self)
        self.attention_filter.setObjectName("predictionAttentionFilter")
        self.attention_filter.addItem("Any", None)
        self.attention_filter.addItem(
            "Needs Attention", ArchiveAttention.NEEDS_ATTENTION.value
        )
        self.attention_filter.addItem(
            "Ready to Resolve", ArchiveAttention.READY_TO_RESOLVE.value
        )
        self.attention_filter.addItem(
            "Needs Postmortem", ArchiveAttention.NEEDS_POSTMORTEM.value
        )
        attention_label.setBuddy(self.attention_filter)

        date_label = QLabel("Date", self)
        self.date_meaning = _ArchiveComboBox(self)
        self.date_meaning.setObjectName("predictionDateMeaning")
        self.date_meaning.addItem("Created", ArchiveDateMeaning.CREATED.value)
        self.date_meaning.addItem(
            "Forecast deadline", ArchiveDateMeaning.FORECAST_DEADLINE.value
        )
        self.date_meaning.addItem(
            "Expected resolution", ArchiveDateMeaning.EXPECTED_RESOLUTION.value
        )
        self.date_meaning.addItem(
            "Terminal decision", ArchiveDateMeaning.TERMINAL_DECISION.value
        )
        date_label.setBuddy(self.date_meaning)

        self.date_start_enabled = QCheckBox("From", self)
        self.date_start_enabled.setObjectName("predictionDateStartEnabled")
        self.date_start = self._new_date_edit("predictionDateStart")
        self.date_end_enabled = QCheckBox("To", self)
        self.date_end_enabled.setObjectName("predictionDateEndEnabled")
        self.date_end = self._new_date_edit("predictionDateEnd")

        sort_label = QLabel("Sort", self)
        self.sort_filter = _ArchiveComboBox(self)
        self.sort_filter.setObjectName("predictionSort")
        self.sort_filter.addItem("Relevance", ArchiveSort.RELEVANCE.value)
        self.sort_filter.addItem("Created (newest)", ArchiveSort.CREATED_NEWEST.value)
        self.sort_filter.addItem("Created (oldest)", ArchiveSort.CREATED_OLDEST.value)
        self.sort_filter.addItem("Question (A–Z)", ArchiveSort.QUESTION_A_TO_Z.value)
        self.sort_filter.addItem("Question (Z–A)", ArchiveSort.QUESTION_Z_TO_A.value)
        self.sort_filter.addItem(
            "Forecast considered (newest)",
            ArchiveSort.FORECAST_CONSIDERED_NEWEST.value,
        )
        self.sort_filter.addItem(
            "Forecast considered (oldest)",
            ArchiveSort.FORECAST_CONSIDERED_OLDEST.value,
        )
        self.sort_filter.addItem(
            "Expected resolution (soonest)",
            ArchiveSort.EXPECTED_RESOLUTION_SOONEST.value,
        )
        self.sort_filter.addItem(
            "Expected resolution (latest)",
            ArchiveSort.EXPECTED_RESOLUTION_LATEST.value,
        )
        self.sort_filter.addItem(
            "Terminal decision (newest)",
            ArchiveSort.TERMINAL_DECISION_NEWEST.value,
        )
        self.sort_filter.addItem(
            "Terminal decision (oldest)",
            ArchiveSort.TERMINAL_DECISION_OLDEST.value,
        )
        relevance_index = self.sort_filter.findData(ArchiveSort.RELEVANCE.value)
        relevance_item = self.sort_filter.model().item(relevance_index)
        if relevance_item is not None:
            relevance_item.setEnabled(False)
        self.sort_filter.setCurrentIndex(
            self.sort_filter.findData(ArchiveSort.CREATED_NEWEST.value)
        )
        self._sort_is_default = True
        sort_label.setBuddy(self.sort_filter)

        self.apply_button = QPushButton("Apply filters", self)
        self.apply_button.setObjectName("applyPredictionFiltersButton")
        apply_lucide_icon(self.apply_button, LucideIcon.LIST_FILTER)
        self.clear_button = QPushButton("Clear filters", self)
        self.clear_button.setObjectName("clearPredictionFiltersButton")
        apply_lucide_icon(self.clear_button, LucideIcon.ERASER)
        apply_action_role(self.apply_button, ActionRole.PRIMARY)
        apply_action_role(self.clear_button, ActionRole.QUIET)
        apply_action_role(self.save_current_view_button, ActionRole.SECONDARY)
        apply_action_role(self.save_as_new_button, ActionRole.SECONDARY)
        apply_action_role(self.update_saved_view_button, ActionRole.SECONDARY)
        apply_action_role(self.rename_saved_view_button, ActionRole.SECONDARY)
        apply_action_role(self.delete_saved_view_button, ActionRole.DESTRUCTIVE)
        apply_action_role(self.manage_tags_button, ActionRole.SECONDARY)

        for label in (
            saved_view_label,
            search_label,
            match_label,
            status_label,
            type_label,
            tag_label,
            tag_mode_label,
            attention_label,
            date_label,
            sort_label,
        ):
            apply_text_role(label, TextRole.LABEL)
        apply_text_role(self.saved_view_state, TextRole.SECONDARY)

        self.saved_view_picker.setMinimumWidth(180)
        self.search_input.setMinimumWidth(240)
        self.date_start.setMinimumWidth(118)
        self.date_end.setMinimumWidth(118)
        for compact_combo in (
            self.match_mode,
            self.status_filter,
            self.type_filter,
            self.attention_filter,
            self.sort_filter,
            self.tag_match_mode,
            self.date_meaning,
        ):
            compact_combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            compact_combo.setMinimumContentsLength(10)
        self._archive_wheel_controls = (
            self.saved_view_picker,
            self.match_mode,
            self.status_filter,
            self.type_filter,
            self.tag_match_mode,
            self.attention_filter,
            self.date_meaning,
            self.sort_filter,
            self.date_start,
            self.date_end,
        )

        filters_panel = ContentPanel(
            "Find predictions",
            "Saved views restore controls dynamically; search and filters always "
            "query the current archive.",
            content_spacing=Spacing.COMPACT,
            parent=self,
        )
        filters_panel.setObjectName("predictionBrowserFiltersPanel")

        saved_section, saved_body = _control_section(
            "Saved view",
            None,
            "predictionSavedViewsGroup",
            filters_panel.body,
        )
        saved_selection = QVBoxLayout()
        saved_selection.setSpacing(int(Spacing.COMPACT))
        saved_view_label.setHidden(True)
        saved_selection.addWidget(self.saved_view_picker)
        saved_selection.addWidget(self.saved_view_state)
        saved_body.addLayout(saved_selection)
        saved_buttons = (
            self.save_current_view_button,
            self.save_as_new_button,
            self.update_saved_view_button,
            self.rename_saved_view_button,
            self.delete_saved_view_button,
        )
        saved_button_width = max(
            148,
            *(button.sizeHint().width() for button in saved_buttons),
        )
        saved_primary_actions = QHBoxLayout()
        saved_primary_actions.setSpacing(int(Spacing.CONTROL))
        saved_primary_actions.addStretch()
        for button in (
            self.save_current_view_button,
            self.save_as_new_button,
            self.update_saved_view_button,
        ):
            button.setFixedWidth(saved_button_width)
            saved_primary_actions.addWidget(button)
        saved_primary_actions.addStretch()
        saved_body.addLayout(saved_primary_actions)
        saved_secondary_actions = QHBoxLayout()
        saved_secondary_actions.setSpacing(int(Spacing.CONTROL))
        saved_secondary_actions.addStretch()
        for button in (
            self.rename_saved_view_button,
            self.delete_saved_view_button,
        ):
            button.setFixedWidth(saved_button_width)
            saved_secondary_actions.addWidget(button)
        saved_secondary_actions.addStretch()
        saved_body.addLayout(saved_secondary_actions)

        search_section, search_body = _control_section(
            "Search",
            None,
            "predictionSearchGroup",
            filters_panel.body,
        )
        search_label.setHidden(True)
        search_body.addWidget(self.search_input)
        search_options = QHBoxLayout()
        search_options.addWidget(match_label)
        search_options.addWidget(self.match_mode)
        search_options.addWidget(self.include_history)
        search_options.addStretch()
        search_body.addLayout(search_options)
        filters_panel.body_layout.addWidget(search_section)

        common_section, common_body = _control_section(
            "Common filters",
            None,
            "predictionCommonFiltersGroup",
            filters_panel.body,
        )
        common_grid = QGridLayout()
        common_grid.setHorizontalSpacing(int(Spacing.CONTROL))
        common_grid.setVerticalSpacing(int(Spacing.CONTROL))
        common_grid.addWidget(status_label, 0, 0)
        common_grid.addWidget(attention_label, 0, 1)
        common_grid.addWidget(self.status_filter, 1, 0)
        common_grid.addWidget(self.attention_filter, 1, 1)
        common_grid.addWidget(type_label, 2, 0)
        common_grid.addWidget(sort_label, 2, 1)
        common_grid.addWidget(self.type_filter, 3, 0)
        common_grid.addWidget(self.sort_filter, 3, 1)
        common_grid.setColumnStretch(0, 1)
        common_grid.setColumnStretch(1, 1)
        common_body.addLayout(common_grid)
        common_actions = QHBoxLayout()
        common_actions.addStretch()
        common_actions.addWidget(self.clear_button)
        common_actions.addWidget(self.apply_button)
        common_body.addLayout(common_actions)
        filters_panel.body_layout.addWidget(common_section)

        detailed_section, detailed_body = _control_section(
            "Detailed filters",
            None,
            "predictionDetailedFiltersGroup",
            filters_panel.body,
        )
        tag_column = QVBoxLayout()
        tag_column.setSpacing(int(Spacing.CONTROL))
        tag_column.addWidget(tag_label)
        tag_column.addWidget(self.tag_filter)
        detailed_body.addLayout(tag_column)

        date_column = QVBoxLayout()
        date_column.setSpacing(int(Spacing.CONTROL))
        date_column.addWidget(date_label)
        date_column.addWidget(self.date_meaning)
        date_bounds = QHBoxLayout()
        date_bounds.setSpacing(int(Spacing.CONTROL))
        start_region = QWidget(detailed_section)
        start_row = QHBoxLayout(start_region)
        start_row.setContentsMargins(0, 0, 0, 0)
        start_row.setSpacing(int(Spacing.CONTROL))
        start_row.addWidget(self.date_start_enabled)
        start_row.addWidget(self.date_start, 1)
        end_region = QWidget(detailed_section)
        end_row = QHBoxLayout(end_region)
        end_row.setContentsMargins(0, 0, 0, 0)
        end_row.setSpacing(int(Spacing.CONTROL))
        end_row.addWidget(self.date_end_enabled)
        end_row.addWidget(self.date_end, 1)
        date_bounds.addWidget(start_region, 1)
        date_bounds.addWidget(end_region, 1)
        date_column.addLayout(date_bounds)
        detailed_body.addLayout(date_column)

        tag_tools = QHBoxLayout()
        tag_tools.setSpacing(int(Spacing.ORDINARY))
        tag_match_region = QWidget(detailed_section)
        tag_match_layout = QHBoxLayout(tag_match_region)
        tag_match_layout.setContentsMargins(0, 0, 0, 0)
        tag_match_layout.setSpacing(int(Spacing.CONTROL))
        tag_match_layout.addWidget(tag_mode_label)
        tag_match_layout.addWidget(self.tag_match_mode, 1)
        manage_tags_region = QWidget(detailed_section)
        manage_tags_layout = QHBoxLayout(manage_tags_region)
        manage_tags_layout.setContentsMargins(0, 0, 0, 0)
        manage_tags_layout.addStretch()
        manage_tags_layout.addWidget(self.manage_tags_button)
        manage_tags_layout.addStretch()
        tag_tools.addWidget(tag_match_region, 1)
        tag_tools.addWidget(manage_tags_region, 1)
        detailed_body.addLayout(tag_tools)
        filters_panel.body_layout.addWidget(detailed_section)
        filters_panel.body_layout.addWidget(saved_section)
        # QScrollArea expands its child to the viewport at normal window sizes.
        # Absorb that spare height below the controls so compact headings and
        # section geometry never stretch when the tag-chip row is empty.
        filters_panel.body_layout.addStretch()

        compact_buttons = (
            self.manage_tags_button,
            self.clear_button,
            self.apply_button,
        )
        for button in compact_buttons:
            button.setSizePolicy(
                QSizePolicy.Policy.Maximum,
                QSizePolicy.Policy.Fixed,
            )

        self.error_label = PersistentMessageLabel(
            accessible_name="Predictions status",
            tone=StatusTone.ERROR,
            parent=self,
        )
        self.error_label.setObjectName("predictionBrowserError")

        self.result_count_label = QLabel(self)
        self.result_count_label.setObjectName("predictionBrowserResultCount")
        self.result_count_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_count_label.setHidden(True)
        apply_text_role(self.result_count_label, TextRole.SECONDARY)

        self.results_list = QListWidget(self)
        self.results_list.setObjectName("predictionBrowserResults")
        self.results_list.setAccessibleName("Prediction search results")
        self.results_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.results_list.setAlternatingRowColors(True)
        self.results_list.setWordWrap(True)
        self.results_list.setMinimumHeight(220)

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
        apply_action_role(self.any_word_button, ActionRole.SECONDARY)
        apply_action_role(
            self.suggestion_button,
            ActionRole.SECONDARY,
            accessible_name="Use suggested search spelling",
        )

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
        apply_action_role(self.open_button, ActionRole.SECONDARY)
        self.open_button.setEnabled(False)

        actions_layout = QHBoxLayout()
        actions_layout.addWidget(self.open_button)
        actions_layout.addStretch()

        results_panel = ContentPanel(
            "Results",
            "Select with the keyboard, or open a row directly with the mouse or Enter.",
            parent=self,
        )
        results_panel.setObjectName("predictionBrowserResultsPanel")
        results_panel.setMinimumWidth(520)
        self._results_panel = results_panel
        results_panel.body_layout.addWidget(self.error_label)
        results_panel.body_layout.addWidget(self.result_count_label)
        results_panel.body_layout.addWidget(self.results_region, 1)
        results_panel.body_layout.addLayout(actions_layout)
        results_panel.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        content = QWidget(self)
        content.setObjectName("predictionBrowserContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
        )
        content_layout.setSpacing(int(Spacing.SECTION))
        content_layout.addWidget(header)

        controls_scroll = QScrollArea(self)
        controls_scroll.setObjectName("predictionBrowserControlsScrollArea")
        controls_scroll.setAccessibleName("Prediction search and filter controls")
        controls_scroll.setWidgetResizable(True)
        controls_scroll.setFrameShape(QFrame.Shape.NoFrame)
        controls_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        controls_scroll.setWidget(filters_panel)
        controls_scroll.setMinimumWidth(520)
        for wheel_control in self._archive_wheel_controls:
            wheel_control.set_wheel_scroll_target(controls_scroll)

        self._workspace_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self._workspace_splitter.setObjectName("predictionBrowserWorkspace")
        self._workspace_splitter.setAccessibleName(
            "Prediction filters and results workspace"
        )
        self._workspace_splitter.setChildrenCollapsible(False)
        self._workspace_splitter.setHandleWidth(int(Spacing.CONTROL))
        self._workspace_splitter.addWidget(controls_scroll)
        self._workspace_splitter.addWidget(results_panel)
        self._workspace_splitter.setStretchFactor(0, 0)
        self._workspace_splitter.setStretchFactor(1, 1)
        self._workspace_splitter.setSizes([540, 900])
        content_layout.addWidget(self._workspace_splitter, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(content)

        self.apply_button.clicked.connect(self.refresh)
        self.clear_button.clicked.connect(self.clear_filters)
        self.search_input.returnPressed.connect(self.refresh)
        self.search_input.textEdited.connect(self._search_text_edited)
        self.match_mode.currentIndexChanged.connect(self.refresh)
        self.include_history.toggled.connect(self.refresh)
        self.status_filter.currentIndexChanged.connect(self.refresh)
        self.type_filter.currentIndexChanged.connect(self.refresh)
        self.tag_filter.selection_changed.connect(self.refresh)
        self.tag_match_mode.currentIndexChanged.connect(self.refresh)
        self.attention_filter.currentIndexChanged.connect(self.refresh)
        self.date_meaning.currentIndexChanged.connect(self.refresh)
        self.date_start_enabled.toggled.connect(self.refresh)
        self.date_end_enabled.toggled.connect(self.refresh)
        self.date_start.dateChanged.connect(self.refresh)
        self.date_end.dateChanged.connect(self.refresh)
        self.sort_filter.currentIndexChanged.connect(self._sort_selected)
        self.saved_view_picker.currentIndexChanged.connect(self._saved_view_selected)
        self.save_current_view_button.clicked.connect(self._save_current_view)
        self.save_as_new_button.clicked.connect(self._save_as_new)
        self.update_saved_view_button.clicked.connect(self._update_active_saved_view)
        self.rename_saved_view_button.clicked.connect(self._rename_active_saved_view)
        self.delete_saved_view_button.clicked.connect(self._delete_active_saved_view)
        self.manage_tags_button.clicked.connect(self._manage_tags)
        self.results_list.currentItemChanged.connect(self._selection_changed)
        self.results_list.itemClicked.connect(self._open_item)
        self.results_list.itemActivated.connect(self._open_item)
        self.open_button.clicked.connect(self._open_current_item)
        self.any_word_button.clicked.connect(self._search_for_any_word)
        self.suggestion_button.clicked.connect(self._accept_suggestion)
        self._update_saved_view_state()

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Keep results visible beside controls, stacking only at narrow widths."""

        super().resizeEvent(event)
        orientation = (
            Qt.Orientation.Horizontal
            if event.size().width() >= self._SIDE_BY_SIDE_MINIMUM_WIDTH
            else Qt.Orientation.Vertical
        )
        for wheel_control in self._archive_wheel_controls:
            wheel_control.set_wheel_changes_enabled(
                orientation is Qt.Orientation.Horizontal
            )
        if self._workspace_splitter.orientation() == orientation:
            return
        self._workspace_splitter.setOrientation(orientation)
        available = (
            self._workspace_splitter.width()
            if orientation is Qt.Orientation.Horizontal
            else self._workspace_splitter.height()
        )
        if orientation is Qt.Orientation.Horizontal:
            controls_size = min(560, max(520, available // 3))
        else:
            controls_size = max(230, available // 2)
        self._workspace_splitter.setSizes(
            [controls_size, max(1, available - controls_size)]
        )

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
        self._sync_default_sort(bool(self.search_input.text().strip()))
        selected_tags = self._selected_tags()
        try:
            self._load_saved_views()
            snapshot = self._query()
            available_keys = {item.casefold() for item in snapshot.available_tags}
            retained_tags = tuple(
                tag for tag in selected_tags if tag.casefold() in available_keys
            )
            if retained_tags != selected_tags:
                with QSignalBlocker(self.tag_filter):
                    self._set_selected_tags(retained_tags)
                snapshot = self._query()
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
        self._update_saved_view_state()

    def _load_saved_views(self) -> None:
        """Refresh the picker without changing the active configuration."""

        views = self._operations.list_saved_views()
        self._saved_views = {view.saved_view_id: view for view in views}
        if self._active_saved_view_id not in self._saved_views:
            self._active_saved_view_id = None
        with QSignalBlocker(self.saved_view_picker):
            self.saved_view_picker.clear()
            self.saved_view_picker.addItem("No Saved View", None)
            selected_index = 0
            for view in views:
                self.saved_view_picker.addItem(view.name, view.saved_view_id)
                if view.saved_view_id == self._active_saved_view_id:
                    selected_index = self.saved_view_picker.count() - 1
            self.saved_view_picker.setCurrentIndex(selected_index)

    def _saved_view_selected(self, _index: int) -> None:
        value = self.saved_view_picker.currentData()
        if value is None:
            self._active_saved_view_id = None
            self._update_saved_view_state()
            return
        view = self._saved_views.get(int(value))
        if view is None:
            self._active_saved_view_id = None
            self._update_saved_view_state()
            return
        self._apply_saved_view(view)

    def _apply_saved_view(self, view: SavedView) -> None:
        """Replace controls, then dynamically rerun the normal archive query."""

        configuration = view.configuration
        query = configuration.archive_query
        with (
            QSignalBlocker(self.search_input),
            QSignalBlocker(self.match_mode),
            QSignalBlocker(self.include_history),
            QSignalBlocker(self.status_filter),
            QSignalBlocker(self.type_filter),
            QSignalBlocker(self.tag_filter),
            QSignalBlocker(self.tag_match_mode),
            QSignalBlocker(self.attention_filter),
            QSignalBlocker(self.date_meaning),
            QSignalBlocker(self.date_start_enabled),
            QSignalBlocker(self.date_end_enabled),
            QSignalBlocker(self.date_start),
            QSignalBlocker(self.date_end),
            QSignalBlocker(self.sort_filter),
        ):
            self.search_input.setText(configuration.search_text)
            self.match_mode.setCurrentIndex(
                self.match_mode.findData(configuration.match_mode.value)
            )
            self.include_history.setChecked(configuration.include_superseded)
            self.status_filter.setCurrentIndex(
                self.status_filter.findData(
                    None if query.status is None else query.status.value
                )
            )
            self.type_filter.setCurrentIndex(
                self.type_filter.findData(
                    None
                    if query.prediction_type is None
                    else query.prediction_type.value
                )
            )
            self._set_selected_tags(query.tags)
            self.tag_match_mode.setCurrentIndex(
                self.tag_match_mode.findData(query.tag_match_mode.value)
            )
            self.attention_filter.setCurrentIndex(
                self.attention_filter.findData(
                    None if query.attention is None else query.attention.value
                )
            )
            self.date_meaning.setCurrentIndex(
                self.date_meaning.findData(query.date_meaning.value)
            )
            self.date_start_enabled.setChecked(query.date_start is not None)
            self.date_end_enabled.setChecked(query.date_end is not None)
            if query.date_start is not None:
                self.date_start.setDate(
                    QDate(
                        query.date_start.year,
                        query.date_start.month,
                        query.date_start.day,
                    )
                )
            if query.date_end is not None:
                self.date_end.setDate(
                    QDate(query.date_end.year, query.date_end.month, query.date_end.day)
                )
            self.sort_filter.setCurrentIndex(
                self.sort_filter.findData(query.sort.value)
            )
        self._sort_is_default = False
        self._active_saved_view_id = view.saved_view_id
        self.refresh()

    def _current_saved_view_configuration(self) -> SavedViewConfiguration:
        return SavedViewConfiguration(
            search_text=self.search_input.text(),
            match_mode=self._selected_match_mode(),
            include_superseded=self.include_history.isChecked(),
            archive_query=ArchiveQuery(
                status=self._selected_status(),
                prediction_type=self._selected_prediction_type(),
                tags=self._selected_tags(),
                tag_match_mode=self._selected_tag_match_mode(),
                attention=self._selected_attention(),
                date_meaning=self._selected_date_meaning(),
                date_start=self._selected_date(
                    self.date_start_enabled, self.date_start
                ),
                date_end=self._selected_date(self.date_end_enabled, self.date_end),
                sort=self._selected_sort(),
            ),
        )

    def _save_current_view(self) -> None:
        """Name and save the current dynamic archive controls as a new view."""

        self._create_saved_view(suggested_name="")

    def _save_as_new(self) -> None:
        """Clone the current controls under an explicitly new Saved View name."""

        active = self._active_saved_view()
        self._create_saved_view(
            suggested_name="" if active is None else f"{active.name} copy"
        )

    def _create_saved_view(self, *, suggested_name: str) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "Save current view",
            "Saved View name:",
            text=suggested_name,
        )
        if not accepted:
            return
        try:
            view = self._operations.create_saved_view(
                name,
                self._current_saved_view_configuration(),
            )
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self._active_saved_view_id = view.saved_view_id
        self.refresh()

    def _update_active_saved_view(self) -> None:
        view = self._active_saved_view()
        if view is None:
            return
        try:
            updated = self._operations.update_saved_view(
                view.saved_view_id,
                self._current_saved_view_configuration(),
            )
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self._active_saved_view_id = updated.saved_view_id
        self.refresh()

    def _rename_active_saved_view(self) -> None:
        view = self._active_saved_view()
        if view is None:
            return
        name, accepted = QInputDialog.getText(
            self,
            "Rename Saved View",
            "Saved View name:",
            text=view.name,
        )
        if not accepted:
            return
        try:
            renamed = self._operations.rename_saved_view(view.saved_view_id, name)
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self._active_saved_view_id = renamed.saved_view_id
        self.refresh()

    def _delete_active_saved_view(self) -> None:
        view = self._active_saved_view()
        if view is None:
            return
        answer = QMessageBox.question(
            self,
            "Delete Saved View",
            f"Delete Saved View {view.name!r}? This does not delete Predictions.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._operations.delete_saved_view(view.saved_view_id)
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        self.error_label.setHidden(True)
        self._active_saved_view_id = None
        self.refresh()

    def _active_saved_view(self) -> SavedView | None:
        if self._active_saved_view_id is None:
            return None
        return self._saved_views.get(self._active_saved_view_id)

    def _manage_tags(self) -> None:
        """Open the secondary global tag workflow, then refresh stable references."""

        dialog = TagManagerDialog(self._operations, self)
        dialog.exec()
        if not dialog.changed:
            return
        try:
            self._load_saved_views()
        except ApplicationError as error:
            self.error_label.setText(str(error))
            self.error_label.setHidden(False)
            return
        active = self._active_saved_view()
        if active is None:
            self.refresh()
        else:
            self._apply_saved_view(active)

    def _update_saved_view_state(self) -> None:
        active = self._active_saved_view()
        if active is None:
            self.saved_view_state.clear()
            self.saved_view_state.setHidden(True)
            self.update_saved_view_button.setEnabled(False)
            self.rename_saved_view_button.setEnabled(False)
            self.delete_saved_view_button.setEnabled(False)
            return
        modified = self._current_saved_view_configuration() != active.configuration
        self.saved_view_state.setText(
            f"{active.name}: {'Modified' if modified else 'Saved'}"
        )
        self.saved_view_state.setHidden(False)
        self.update_saved_view_button.setEnabled(modified)
        self.rename_saved_view_button.setEnabled(True)
        self.delete_saved_view_button.setEnabled(True)

    def _query(self) -> PredictionBrowserSnapshot | PredictionSearchResults:
        text = self.search_input.text()
        sort = self._selected_sort()
        shared_arguments = {
            "status": self._selected_status(),
            "prediction_type": self._selected_prediction_type(),
            "tags": self._selected_tags(),
            "tag_match_mode": self._selected_tag_match_mode(),
            "attention": self._selected_attention(),
            "date_meaning": self._selected_date_meaning(),
            "date_start": self._selected_date(self.date_start_enabled, self.date_start),
            "date_end": self._selected_date(self.date_end_enabled, self.date_end),
            "sort": sort,
        }
        if text.strip():
            return self._operations.search_predictions(
                text,
                match_mode=self._selected_match_mode(),
                include_superseded=self.include_history.isChecked(),
                **shared_arguments,
            )
        return self._operations.browse_predictions(
            "",
            **shared_arguments,
        )

    def clear_filters(self) -> None:
        """Restore the unfiltered archive and query once."""

        self.search_input.clear()
        with (
            QSignalBlocker(self.status_filter),
            QSignalBlocker(self.type_filter),
            QSignalBlocker(self.tag_filter),
            QSignalBlocker(self.tag_match_mode),
            QSignalBlocker(self.attention_filter),
            QSignalBlocker(self.date_meaning),
            QSignalBlocker(self.date_start_enabled),
            QSignalBlocker(self.date_end_enabled),
            QSignalBlocker(self.date_start),
            QSignalBlocker(self.date_end),
            QSignalBlocker(self.sort_filter),
            QSignalBlocker(self.match_mode),
            QSignalBlocker(self.include_history),
        ):
            self.status_filter.setCurrentIndex(0)
            self.type_filter.setCurrentIndex(0)
            self.tag_filter.clear_selection()
            self.tag_match_mode.setCurrentIndex(0)
            self.attention_filter.setCurrentIndex(0)
            self.date_meaning.setCurrentIndex(0)
            self.date_start_enabled.setChecked(False)
            self.date_end_enabled.setChecked(False)
            self.date_start.setDate(QDate.currentDate())
            self.date_end.setDate(QDate.currentDate())
            self.sort_filter.setCurrentIndex(
                self.sort_filter.findData(ArchiveSort.CREATED_NEWEST.value)
            )
            self.match_mode.setCurrentIndex(0)
            self.include_history.setChecked(False)
        self._sort_is_default = True
        self.refresh()

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
        self._results_panel.set_count(count)

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
            # The structured row widget is the sole visual representation.  A
            # DisplayRole string would also be painted by QListWidget's default
            # delegate underneath it, causing duplicate and overlapping text.
            item = QListWidgetItem()
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
            row = self._archive_result_widget(prediction)
            item.setSizeHint(row.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, row)

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
            item = QListWidgetItem()
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
        selected_tags = self._selected_tags()
        with QSignalBlocker(self.tag_filter):
            self.tag_filter.set_available_tags(tags)
            self.tag_filter.set_selected_tags(selected_tags)

    def _selected_status(self) -> PredictionStatus | None:
        value = self.status_filter.currentData()
        return None if value is None else PredictionStatus(str(value))

    def _selected_tags(self) -> tuple[str, ...]:
        return self.tag_filter.selected_tags()

    def _set_selected_tags(self, selected_tags: tuple[str, ...]) -> None:
        self.tag_filter.set_selected_tags(selected_tags)

    def _selected_prediction_type(self) -> PredictionType | None:
        value = self.type_filter.currentData()
        return None if value is None else PredictionType(str(value))

    def _selected_match_mode(self) -> SearchMatchMode:
        return SearchMatchMode(str(self.match_mode.currentData()))

    def _selected_tag_match_mode(self) -> ArchiveTagMatchMode:
        return ArchiveTagMatchMode(str(self.tag_match_mode.currentData()))

    def _selected_attention(self) -> ArchiveAttention | None:
        value = self.attention_filter.currentData()
        return None if value is None else ArchiveAttention(str(value))

    def _selected_date_meaning(self) -> ArchiveDateMeaning:
        return ArchiveDateMeaning(str(self.date_meaning.currentData()))

    def _selected_date(self, enabled: QCheckBox, edit: QDateEdit) -> date | None:
        if not enabled.isChecked():
            return None
        selected = edit.date()
        return date(selected.year(), selected.month(), selected.day())

    def _selected_sort(self) -> ArchiveSort:
        return ArchiveSort(str(self.sort_filter.currentData()))

    def _sort_selected(self, _index: int) -> None:
        self._sort_is_default = False
        self.refresh()

    def _sync_default_sort(self, text_active: bool) -> None:
        relevance_index = self.sort_filter.findData(ArchiveSort.RELEVANCE.value)
        relevance_item = self.sort_filter.model().item(relevance_index)
        if relevance_item is not None:
            relevance_item.setEnabled(text_active)
        if not self._sort_is_default:
            if not text_active and self._selected_sort() is ArchiveSort.RELEVANCE:
                with QSignalBlocker(self.sort_filter):
                    self.sort_filter.setCurrentIndex(
                        self.sort_filter.findData(ArchiveSort.CREATED_NEWEST.value)
                    )
            return
        default = ArchiveSort.RELEVANCE if text_active else ArchiveSort.CREATED_NEWEST
        if self._selected_sort() is not default:
            with QSignalBlocker(self.sort_filter):
                self.sort_filter.setCurrentIndex(
                    self.sort_filter.findData(default.value)
                )

    @staticmethod
    def _new_date_edit(object_name: str) -> QDateEdit:
        edit = _ArchiveDateEdit()
        edit.setObjectName(object_name)
        edit.setCalendarPopup(True)
        edit.setDisplayFormat("yyyy-MM-dd")
        edit.setDateRange(QDate(1752, 9, 14), QDate(9999, 12, 31))
        edit.setDate(QDate.currentDate())
        return edit

    def _has_active_filters(self) -> bool:
        return bool(
            self.search_input.text().strip()
            or self._selected_status() is not None
            or self._selected_prediction_type() is not None
            or bool(self._selected_tags())
            or self._selected_attention() is not None
            or self.date_start_enabled.isChecked()
            or self.date_end_enabled.isChecked()
            or self._selected_date_meaning() is not ArchiveDateMeaning.CREATED
            or self._selected_sort() is not ArchiveSort.CREATED_NEWEST
        )

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self.open_button.setEnabled(current is not None)

    def _search_text_edited(self, text: str) -> None:
        self._sync_default_sort(bool(text.strip()))
        self._update_saved_view_state()
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

    def _archive_result_widget(self, prediction: PredictionBrowserItem) -> QWidget:
        row, layout = self._result_row(
            prediction,
            _forecast_value_summary(prediction),
        )
        row.setObjectName(f"predictionArchiveResult{prediction.prediction_id}")
        question = layout.itemAt(0).widget()
        if question is not None:
            question.setObjectName(
                f"predictionArchiveResultQuestion{prediction.prediction_id}"
            )
        return row

    def _search_result_widget(self, hit: PredictionSearchHit) -> QWidget:
        row, layout = self._result_row(
            hit.prediction,
            _search_value_summary(hit.prediction),
        )
        row.setObjectName(f"predictionSearchResult{hit.prediction.prediction_id}")
        first_widget = layout.itemAt(0).widget()
        if first_widget is not None:
            first_widget.setObjectName(
                f"predictionSearchResultQuestion{hit.prediction.prediction_id}"
            )

        source = QLabel(search_source_label(hit.best_match.document), row)
        source.setObjectName(
            f"predictionSearchResultSource{hit.prediction.prediction_id}"
        )
        source.setTextFormat(Qt.TextFormat.PlainText)
        apply_text_role(source, TextRole.LABEL)
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
            apply_text_role(additional, TextRole.SECONDARY)
            layout.addWidget(additional)
        return row

    def _result_row(
        self,
        prediction: PredictionBrowserItem | SearchPrediction,
        value_summary: str,
    ) -> tuple[QFrame, QVBoxLayout]:
        """Compose the common archive/search result hierarchy."""

        row = QFrame(self.results_list)
        row.setFrameShape(QFrame.Shape.NoFrame)
        row.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(row)
        layout.setContentsMargins(
            int(Spacing.ORDINARY),
            int(Spacing.CONTROL),
            int(Spacing.ORDINARY),
            int(Spacing.CONTROL),
        )
        layout.setSpacing(int(Spacing.COMPACT))

        question = QLabel(prediction.question, row)
        question.setTextFormat(Qt.TextFormat.PlainText)
        question.setWordWrap(True)
        apply_text_role(question, TextRole.SECTION_TITLE)
        layout.addWidget(question)

        badges = QHBoxLayout()
        badges.setSpacing(int(Spacing.CONTROL))
        forecast_type = StatusBadge(
            prediction.prediction_type.value.upper(),
            StatusTone.NEUTRAL,
            parent=row,
        )
        forecast_type.setObjectName(f"predictionResultType{prediction.prediction_id}")
        lifecycle = StatusBadge(
            prediction.status.value.upper(),
            _status_tone(prediction.status),
            parent=row,
        )
        lifecycle.setObjectName(f"predictionResultStatus{prediction.prediction_id}")
        badges.addWidget(forecast_type)
        badges.addWidget(lifecycle)
        badges.addStretch()
        layout.addLayout(badges)
        forecast = QLabel(value_summary, row)
        forecast.setObjectName(f"predictionResultForecast{prediction.prediction_id}")
        forecast.setTextFormat(Qt.TextFormat.PlainText)
        forecast.setWordWrap(True)
        layout.addWidget(forecast)

        if prediction.tags:
            tags = QLabel(f"Tags · {', '.join(prediction.tags)}", row)
            tags.setObjectName(f"predictionResultTags{prediction.prediction_id}")
            tags.setTextFormat(Qt.TextFormat.PlainText)
            tags.setWordWrap(True)
            apply_text_role(tags, TextRole.SECONDARY)
            layout.addWidget(tags)

        dates = QLabel(_date_context(prediction), row)
        dates.setObjectName(f"predictionResultDates{prediction.prediction_id}")
        dates.setTextFormat(Qt.TextFormat.PlainText)
        dates.setWordWrap(True)
        apply_text_role(dates, TextRole.SECONDARY)
        layout.addWidget(dates)
        return row, layout

    def _current_parsed_search_text(self) -> ParsedSearchText:
        loaded = self._loaded_snapshot
        if isinstance(loaded, PredictionSearchResults):
            return loaded.parsed_text
        raise RuntimeError("A search row requires loaded parsed search text.")

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


def _format_date(value: date) -> str:
    return value.strftime("%b %d, %Y").replace(" 0", " ")


def _status_tone(status: PredictionStatus) -> StatusTone:
    if status is PredictionStatus.OPEN:
        return StatusTone.ACCENT
    if status is PredictionStatus.RESOLVED:
        return StatusTone.SUCCESS
    if status in (PredictionStatus.LOCKED, PredictionStatus.INVALID):
        return StatusTone.WARNING
    return StatusTone.NEUTRAL


def _date_context(prediction: PredictionBrowserItem | SearchPrediction) -> str:
    parts = [f"Created {_format_local_timestamp(prediction.created_at)}"]
    if prediction.latest_revision_at is not None:
        parts.append(
            "Forecast considered "
            f"{_format_local_timestamp(prediction.latest_revision_at)}"
        )
    if prediction.expected_resolution is not None:
        parts.append(
            f"Expected resolution {_format_date(prediction.expected_resolution)}"
        )
    if prediction.terminal_decision_at is not None:
        parts.append(
            "Terminal decision "
            f"{_format_local_timestamp(prediction.terminal_decision_at)}"
        )
    return " · ".join(parts)


def _forecast_value_summary(prediction: PredictionBrowserItem) -> str:
    if prediction.prediction_type is PredictionType.BINARY:
        if prediction.probability_percent is None:
            raise ValueError("A Binary browser row requires a probability.")
        return f"Current forecast · {prediction.probability_percent}%"
    if (
        prediction.numeric_lower_bound is None
        or prediction.numeric_median_estimate is None
        or prediction.numeric_upper_bound is None
        or prediction.numeric_confidence_percent is None
        or prediction.numeric_unit is None
    ):
        raise ValueError("A Numeric browser row requires complete interval data.")
    return (
        f"Current interval · {prediction.numeric_confidence_percent}%: "
        f"{prediction.numeric_lower_bound}–{prediction.numeric_upper_bound} "
        f"{prediction.numeric_unit}; median "
        f"{prediction.numeric_median_estimate} {prediction.numeric_unit}"
    )


def _search_value_summary(prediction: SearchPrediction) -> str:
    if (
        prediction.status is PredictionStatus.RESOLVED
        and prediction.prediction_type is PredictionType.BINARY
        and prediction.binary_outcome is not None
    ):
        return f"Outcome · {prediction.binary_outcome.value.title()}"
    if (
        prediction.status is PredictionStatus.RESOLVED
        and prediction.prediction_type is PredictionType.NUMERIC
        and prediction.numeric_actual_value is not None
        and prediction.numeric_unit is not None
    ):
        return f"Actual value · {prediction.numeric_actual_value} {prediction.numeric_unit}"
    if prediction.prediction_type is PredictionType.BINARY:
        if prediction.probability_percent is None:
            raise ValueError("A Binary search result requires a probability.")
        return f"Current forecast · {prediction.probability_percent}%"
    if (
        prediction.numeric_lower_bound is None
        or prediction.numeric_median_estimate is None
        or prediction.numeric_upper_bound is None
        or prediction.numeric_confidence_percent is None
        or prediction.numeric_unit is None
    ):
        raise ValueError("A Numeric search result requires complete interval data.")
    return (
        f"Current interval · {prediction.numeric_confidence_percent}%: "
        f"{prediction.numeric_lower_bound}–{prediction.numeric_upper_bound} "
        f"{prediction.numeric_unit}; median {prediction.numeric_median_estimate} "
        f"{prediction.numeric_unit}"
    )


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
