"""Prediction detail responsibilities extracted from the desktop composition."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.analytics.quantiles import QuantileScorecard
from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.domain.predictions import (
    InvalidationHistory,
    NumericResolutionHistory,
    PredictionStatus,
)
from reckonsolve.domain.quantiles import FiveQuantiles, QuantileTimelineEvent
from reckonsolve.domain.search import SearchDocument, SearchSourceKind
from reckonsolve.forecast_display import (
    format_local_deadline,
)
from reckonsolve.quantile_display import quantile_scorecard_lines
from reckonsolve.ui.components import (
    EmptyStateLabel,
    PageHeader,
    StatusBadge,
)
from reckonsolve.ui.date_display import format_date
from reckonsolve.ui.detail_reading import (
    TerminalSummary,
    criteria_reader,
    current_marker,
    interval_text,
    interval_transition_text,
    invalidation_exact_timing,
    invalidation_timing,
    progressive_body,
    quiet_event,
    reading_refresh,
    timeline_controls,
)
from reckonsolve.ui.detail_sections import (
    AdaptiveReadingSections,
    TimelineRows,
    terminal_timeline_rows,
)
from reckonsolve.ui.detail_workspace import (
    DetailWorkspace,
    HeaderTiming,
    collapse_section,
    exact_detail_time,
)
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.numeric_interval import NumericInterval
from reckonsolve.ui.postmortem_action import PostmortemSkipButton
from reckonsolve.ui.prediction_contracts import (
    NumericPredictionSnapshot,
    PredictionOperations,
)
from reckonsolve.ui.prediction_dialogs import (
    AddNumericJournalEntryDialog,
    CorrectInvalidationReasonDialog,
    CorrectNumericJournalEntryDialog,
    CorrectNumericResolutionDialog,
    EditPredictionDetailsDialog,
    ForecastReviewDialog,
    MarkNumericPredictionInvalidDialog,
    ResolveNumericPredictionDialog,
    ReviseQuantileForecastDialog,
)
from reckonsolve.ui.prediction_widgets import (
    _clear_widget_layout,
    _collapsible_history_group,
    _configure_detail_action_grid,
    _definition_change_widget,
    _detail_panel,
    _detail_text_section,
    _detail_value_row,
    _focus_search_widget,
    _format_date,
    _format_local_timestamp,
    _journal_edit_history_widget,
    _make_selectable,
    _numeric_forecast_text,
    _show_invalidation_correction_history,
    _show_numeric_resolution_correction_history,
    _status_tone,
)
from reckonsolve.ui.quantile_input import QuantileCDF
from reckonsolve.ui.quantile_scorecard import QuantileScorecardPanel
from reckonsolve.ui.reflection_editor import ReflectionEditor
from reckonsolve.ui.visual_system import (
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_badge_role,
    apply_message_role,
    apply_surface_role,
    apply_text_role,
)


class NumericPredictionDetailScreen(QWidget):
    """Present and extend the current Numeric Prediction's honest history."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("numericPredictionDetailScreen")
        self._operations = operations
        self._prediction: NumericPredictionSnapshot | None = None
        self._edit_dialog: EditPredictionDetailsDialog | None = None
        self._resolution_history: NumericResolutionHistory | None = None
        self._invalidation_history: InvalidationHistory | None = None

        header = PageHeader(
            "Prediction Detail",
            "Current belief, supporting context, and the complete preserved history.",
            title_object_name="numericPredictionDetailScreenTitle",
            parent=self,
        )

        self.empty_state = EmptyStateLabel(
            "No Numeric Prediction has been created yet.",
            parent=self,
        )
        self.empty_state.setObjectName("numericPredictionDetailEmptyState")
        self.empty_state.setWordWrap(True)

        self.detail_error = QLabel("", self)
        self.detail_error.setObjectName("numericPredictionDetailError")
        self.detail_error.setAccessibleName("Numeric Prediction Detail error")
        self.detail_error.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_error.setWordWrap(True)
        self.detail_error.setHidden(True)
        apply_message_role(
            self.detail_error,
            StatusTone.ERROR,
            accessible_name="Numeric Prediction Detail error",
        )

        self.detail_content = QWidget(self)
        self.detail_content.setObjectName("numericPredictionDetailContent")
        detail_layout = QVBoxLayout(self.detail_content)
        detail_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.question = QLabel("", self.detail_content)
        self.question.setObjectName("numericPredictionQuestion")
        self.question.setTextFormat(Qt.TextFormat.PlainText)
        self.question.setWordWrap(True)
        _make_selectable(self.question)
        apply_text_role(self.question, TextRole.PAGE_TITLE)

        self.tags = QLabel("", self.detail_content)
        self.tags.setObjectName("numericPredictionTags")
        self.tags.setTextFormat(Qt.TextFormat.PlainText)
        self.tags.setWordWrap(True)
        _make_selectable(self.tags)
        apply_text_role(self.tags, TextRole.SECONDARY)

        self.forecast_type = StatusBadge(
            "Adaptive · Numeric",
            StatusTone.NEUTRAL,
            parent=self.detail_content,
        )
        self.forecast_type.setObjectName("numericPredictionType")

        self.status = QLabel("", self.detail_content)
        self.status.setObjectName("numericPredictionStatus")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setAccessibleName("Prediction status")
        apply_badge_role(self.status)

        forecast_label = QLabel("Current Forecast", self.detail_content)
        forecast_label.setObjectName("numericCurrentForecastLabel")
        apply_text_role(forecast_label, TextRole.LABEL)

        self.interval = QLabel("", self.detail_content)
        self.interval.setObjectName("numericCurrentInterval")
        self.interval.setTextFormat(Qt.TextFormat.PlainText)
        self.interval.setWordWrap(True)
        _make_selectable(self.interval)
        apply_text_role(self.interval, TextRole.FORECAST)

        self.median = QLabel("", self.detail_content)
        self.median.setObjectName("numericCurrentMedian")
        self.median.setTextFormat(Qt.TextFormat.PlainText)
        self.median.setWordWrap(True)
        _make_selectable(self.median)
        apply_text_role(self.median, TextRole.LABEL)

        self.unit_row, self.unit = _detail_value_row(
            "Unit",
            "numericUnitRow",
            "numericUnitValue",
            self.detail_content,
            stacked=True,
        )
        self.precision_row, self.precision = _detail_value_row(
            "Decimal Places",
            "numericPrecisionRow",
            "numericPrecisionValue",
            self.detail_content,
            stacked=True,
        )
        self.definition_summary = QWidget(self.detail_content)
        self.definition_summary.setObjectName("numericDefinitionSummary")
        definition_layout = QGridLayout(self.definition_summary)
        definition_layout.setContentsMargins(0, 0, 0, 0)
        definition_layout.setHorizontalSpacing(int(Spacing.SECTION))
        for column, field in enumerate((self.unit_row, self.precision_row)):
            definition_layout.addWidget(field, 0, column, Qt.AlignmentFlag.AlignTop)
            definition_layout.setColumnStretch(column, 1)
            for label in field.findChildren(QLabel):
                label.setWordWrap(True)
                label.setMinimumWidth(0)
                policy = label.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                label.setSizePolicy(policy)
        self.forecast_deadline_row, self.forecast_deadline = _detail_value_row(
            "Forecast deadline",
            "numericForecastDeadlineRow",
            "numericForecastDeadlineValue",
            self.detail_content,
            stacked=True,
        )
        self.expected_resolution_row, self.expected_resolution = _detail_value_row(
            "Expected resolution",
            "numericExpectedResolutionRow",
            "numericExpectedResolutionValue",
            self.detail_content,
        )
        self.background_section, self.background = _detail_text_section(
            "Background",
            "numericBackgroundSection",
            "numericBackgroundValue",
            self.detail_content,
        )
        self.resolution_criteria_section, self.resolution_criteria = (
            _detail_text_section(
                "Resolution Criteria",
                "numericResolutionCriteriaSection",
                "numericResolutionCriteriaValue",
                self.detail_content,
            )
        )
        self.rationale_section, self.rationale = _detail_text_section(
            "Initial Rationale",
            "numericInitialRationaleSection",
            "numericInitialRationaleValue",
            self.detail_content,
        )

        actions = QWidget(self.detail_content)
        actions.setObjectName("numericPredictionActions")
        actions_layout = QGridLayout(actions)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setHorizontalSpacing(int(Spacing.CONTROL))
        actions_layout.setVerticalSpacing(int(Spacing.CONTROL))
        self.revise_forecast_button = QPushButton("Revise Interval", actions)
        self.revise_forecast_button.setObjectName("reviseNumericForecastButton")
        self.revise_forecast_button.setAccessibleName("Revise numeric interval")
        apply_lucide_icon(self.revise_forecast_button, LucideIcon.PENCIL)
        self.add_journal_entry_button = QPushButton("Add Journal Entry", actions)
        self.add_journal_entry_button.setObjectName("addNumericJournalEntryButton")
        self.add_journal_entry_button.setAccessibleName("Add Numeric Journal entry")
        apply_lucide_icon(self.add_journal_entry_button, LucideIcon.CIRCLE_PLUS)
        self.review_forecast_button = QPushButton("Keep this interval", actions)
        self.review_forecast_button.setObjectName("reviewNumericForecastButton")
        self.review_forecast_button.setAccessibleName(
            "Record a Review retaining this numeric interval"
        )
        apply_lucide_icon(self.review_forecast_button, LucideIcon.CIRCLE_CHECK)
        self.edit_details_button = QPushButton("Edit Details", actions)
        self.edit_details_button.setObjectName("editNumericPredictionDetailsButton")
        self.edit_details_button.setAccessibleName("Edit Numeric Prediction details")
        apply_action_role(self.edit_details_button, ActionRole.SECONDARY)
        apply_lucide_icon(self.edit_details_button, LucideIcon.PENCIL)
        self.resolve_button = QPushButton("Resolve", actions)
        self.resolve_button.setObjectName("resolveNumericPredictionButton")
        apply_lucide_icon(self.resolve_button, LucideIcon.CIRCLE_CHECK)
        self.mark_invalid_button = QPushButton("Mark Invalid", actions)
        self.mark_invalid_button.setObjectName("markNumericPredictionInvalidButton")
        apply_lucide_icon(self.mark_invalid_button, LucideIcon.BAN)
        self.delete_button = QPushButton("Delete", actions)
        self.delete_button.setObjectName("deleteNumericPredictionButton")
        apply_action_role(self.delete_button, ActionRole.DESTRUCTIVE)
        apply_lucide_icon(self.delete_button, LucideIcon.TRASH)
        apply_action_role(self.revise_forecast_button, ActionRole.PRIMARY)
        apply_action_role(self.add_journal_entry_button, ActionRole.SECONDARY)
        apply_action_role(self.review_forecast_button, ActionRole.SECONDARY)
        apply_action_role(self.resolve_button, ActionRole.SECONDARY)
        apply_action_role(self.mark_invalid_button, ActionRole.CAUTION)
        _configure_detail_action_grid(
            actions_layout,
            (
                self.revise_forecast_button,
                self.add_journal_entry_button,
                self.review_forecast_button,
                self.edit_details_button,
                self.resolve_button,
                self.mark_invalid_button,
                self.delete_button,
            ),
        )
        actions_layout.addWidget(self.add_journal_entry_button, 0, 1)
        actions_layout.addWidget(self.revise_forecast_button, 0, 2)
        actions_layout.addWidget(self.review_forecast_button, 0, 3)
        actions_layout.addWidget(self.edit_details_button, 1, 1)
        actions_layout.addWidget(self.resolve_button, 1, 2)
        actions_layout.addWidget(self.mark_invalid_button, 1, 3)
        actions_layout.addWidget(self.delete_button, 2, 2)

        self.resolution_section = QGroupBox("Resolved", self.detail_content)
        self.resolution_section.setObjectName("numericResolutionSection")
        apply_surface_role(self.resolution_section, SurfaceRole.RAISED)
        resolution_layout = QVBoxLayout(self.resolution_section)
        self.resolution_actual = QLabel("", self.resolution_section)
        self.resolution_actual.setObjectName("numericResolutionActualValue")
        self.resolution_actual.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_time = QLabel("", self.resolution_section)
        self.resolution_time.setObjectName("numericResolutionTime")
        self.resolution_time.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_scoring = QLabel("", self.resolution_section)
        self.resolution_scoring.setObjectName("numericResolutionScoringForecast")
        self.resolution_scoring.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_scoring.setWordWrap(True)
        self.resolution_notes = QLabel("", self.resolution_section)
        self.resolution_notes.setObjectName("numericResolutionNotes")
        self.resolution_notes.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_notes.setWordWrap(True)
        _make_selectable(self.resolution_notes)
        self.postmortem = QLabel("", self.resolution_section)
        self.postmortem.setObjectName("numericResolutionPostmortem")
        self.postmortem.setTextFormat(Qt.TextFormat.PlainText)
        self.postmortem.setWordWrap(True)
        _make_selectable(self.postmortem)
        self.postmortem_completion = QLabel("", self.resolution_section)
        self.postmortem_completion.setObjectName("numericPostmortemCompletion")
        self.skip_postmortem_button = PostmortemSkipButton(
            lambda identifier, **context: self._operations.record_postmortem_skip(
                identifier, **context
            ),
            self.refresh,
            self._show_error,
            self.resolution_section,
        )
        self.skip_postmortem_button.setObjectName("numericSkipPostmortemButton")
        self.postmortem_completion.setTextFormat(Qt.TextFormat.PlainText)
        self.postmortem_completion.setWordWrap(True)
        _make_selectable(self.postmortem_completion)
        self.correct_resolution_button = QPushButton(
            "Correct Resolution",
            self.resolution_section,
        )
        self.correct_resolution_button.setObjectName("correctNumericResolutionButton")
        self.correct_resolution_button.setAccessibleName(
            "Correct Numeric Resolution or Postmortem"
        )
        self.correct_resolution_button.setToolTip(
            "Correct the actual value or notes, or add or correct the Postmortem. "
            "The original Resolution remains in history."
        )
        apply_lucide_icon(self.correct_resolution_button, LucideIcon.PENCIL)
        self.resolution_history = _collapsible_history_group(
            "Resolution correction history",
            "numericResolutionCorrectionHistory",
            self.resolution_section,
        )
        resolution_layout.addWidget(self.resolution_actual)
        resolution_layout.addWidget(self.resolution_time)
        resolution_layout.addWidget(self.resolution_scoring)
        self.quantile_scorecard = QuantileScorecardPanel(self.resolution_section)
        self.quantile_scorecard.hide()
        self._quantile_score: QuantileScorecard | None = None
        resolution_layout.addWidget(self.quantile_scorecard)
        resolution_layout.addWidget(self.resolution_notes)
        resolution_layout.addWidget(self.postmortem)
        resolution_layout.addWidget(self.postmortem_completion)
        self.write_postmortem_button = QPushButton(
            "Write Postmortem", self.resolution_section
        )
        apply_action_role(self.write_postmortem_button, ActionRole.QUIET)
        self.write_postmortem_button.clicked.connect(self.open_postmortem)
        reflection_actions = QWidget(self.resolution_section)
        reflection_row = QHBoxLayout(reflection_actions)
        reflection_row.setContentsMargins(0, 0, 0, 0)
        reflection_row.addWidget(self.write_postmortem_button)
        reflection_row.addWidget(self.skip_postmortem_button)
        reflection_row.addStretch()
        resolution_layout.addWidget(reflection_actions)
        resolution_layout.addWidget(
            self.correct_resolution_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        resolution_layout.addWidget(self.resolution_history)
        self.resolution_section.setHidden(True)
        self.quantile_scorecard.setHidden(True)
        self.postmortem_completion.setHidden(True)

        self.invalidation_section = QGroupBox("Invalid", self.detail_content)
        self.invalidation_section.setObjectName("numericInvalidationSection")
        apply_surface_role(self.invalidation_section, SurfaceRole.RAISED)
        invalidation_layout = QVBoxLayout(self.invalidation_section)
        self.invalidation_time = QLabel("", self.invalidation_section)
        self.invalidation_time.setObjectName("numericInvalidationTime")
        self.invalidation_time.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason = QLabel("", self.invalidation_section)
        self.invalidation_reason.setObjectName("numericInvalidationReason")
        self.invalidation_reason.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason.setWordWrap(True)
        _make_selectable(self.invalidation_reason)
        self.correct_invalidation_button = QPushButton(
            "Correct Reason",
            self.invalidation_section,
        )
        self.correct_invalidation_button.setObjectName(
            "correctNumericInvalidationReasonButton"
        )
        self.correct_invalidation_button.setToolTip(
            "Append a correction while preserving the original Invalid reason."
        )
        apply_lucide_icon(self.correct_invalidation_button, LucideIcon.PENCIL)
        self.invalidation_history = _collapsible_history_group(
            "Invalidation correction history",
            "numericInvalidationCorrectionHistory",
            self.invalidation_section,
        )
        invalidation_layout.addWidget(self.invalidation_time)
        invalidation_layout.addWidget(self.invalidation_reason)
        invalidation_layout.addWidget(
            self.correct_invalidation_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        invalidation_layout.addWidget(self.invalidation_history)
        self.invalidation_section.setHidden(True)

        self.definition_history = QGroupBox("Definition History", self.detail_content)
        self.definition_history.setObjectName("numericDefinitionHistoryGroup")
        apply_surface_role(self.definition_history, SurfaceRole.BASE)
        self.definition_history.setCheckable(True)
        self.definition_history.setChecked(False)
        self.definition_history_content = QWidget(self.definition_history)
        self.definition_history_content.setObjectName("numericDefinitionHistoryContent")
        self.definition_history_layout = QVBoxLayout(self.definition_history_content)
        definition_group_layout = QVBoxLayout(self.definition_history)
        definition_group_layout.addWidget(self.definition_history_content)
        self.definition_history.toggled.connect(
            self.definition_history_content.setVisible
        )
        self.definition_history_content.setHidden(True)
        self.definition_history.setHidden(True)

        history_label = QLabel("Interval History", self.detail_content)
        history_label.setObjectName("numericHistoryLabel")
        history_label.setWordWrap(True)
        history_font = QFont(history_label.font())
        history_font.setBold(True)
        history_label.setFont(history_font)
        self.history_error = QLabel("", self.detail_content)
        self.history_error.setObjectName("numericHistoryError")
        self.history_error.setTextFormat(Qt.TextFormat.PlainText)
        self.history_error.setWordWrap(True)
        self.history_error.setHidden(True)
        apply_message_role(
            self.history_error,
            StatusTone.ERROR,
            accessible_name="Numeric interval history error",
        )
        self.quantile_cdf = QuantileCDF(self.detail_content)
        chart_policy = self.quantile_cdf.sizePolicy()
        chart_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        self.quantile_cdf.setSizePolicy(chart_policy)
        self.quantile_cdf.hide()
        self.quantile_cdf_summary = QLabel(self.detail_content)
        self.quantile_cdf_summary.setWordWrap(True)
        _make_selectable(self.quantile_cdf_summary)
        self.quantile_cdf_summary.hide()
        self.numeric_history_label = history_label

        timeline_label = QLabel("TIMELINE", self.detail_content)
        timeline_label.setObjectName("numericTimelineLabel")
        timeline_font = QFont(timeline_label.font())
        timeline_font.setBold(True)
        timeline_label.setFont(timeline_font)
        self.timeline_error = QLabel("", self.detail_content)
        self.timeline_error.setObjectName("numericTimelineError")
        self.timeline_error.setTextFormat(Qt.TextFormat.PlainText)
        self.timeline_error.setWordWrap(True)
        self.timeline_error.setHidden(True)
        apply_message_role(
            self.timeline_error,
            StatusTone.ERROR,
            accessible_name="Numeric timeline error",
        )
        self.timeline_content = QWidget(self.detail_content)
        self.timeline_content.setObjectName("numericTimelineContent")
        self.timeline_layout = QVBoxLayout(self.timeline_content)
        self.timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_layout.setSpacing(8)

        summary_panel, summary_layout = _detail_panel(
            "numericPredictionSummaryPanel",
            self.detail_content,
        )
        identity_row = QWidget(summary_panel)
        identity_layout = QHBoxLayout(identity_row)
        identity_layout.setContentsMargins(0, 0, 0, 0)
        identity_layout.setSpacing(int(Spacing.CONTROL))
        identity_layout.addWidget(self.forecast_type)
        identity_layout.addWidget(self.status)
        identity_layout.addStretch()
        summary_layout.addWidget(identity_row)
        summary_layout.addWidget(self.question)
        summary_layout.addWidget(self.tags)
        summary_layout.addSpacing(int(Spacing.CONTROL))
        summary_layout.addWidget(forecast_label)
        summary_layout.addWidget(self.interval)
        summary_layout.addWidget(self.median)

        action_panel, action_panel_layout = _detail_panel(
            "numericPredictionActionPanel",
            self.detail_content,
        )
        action_heading = QLabel("Forecast actions", action_panel)
        action_heading.setObjectName("numericPredictionActionHeading")
        apply_text_role(action_heading, TextRole.SECTION_TITLE)
        action_help = QLabel(
            "Revise or reconsider the forecast, record reasoning, or finish its lifecycle.",
            action_panel,
        )
        action_help.setObjectName("numericPredictionActionHelp")
        action_help.setWordWrap(True)
        action_help.setContentsMargins(0, 0, 0, int(Spacing.CONTROL))
        apply_text_role(action_help, TextRole.LABEL)
        action_panel_layout.addWidget(action_heading)
        action_panel_layout.addWidget(action_help)
        action_panel_layout.addWidget(actions)

        self.metadata_panel, metadata_layout = _detail_panel(
            "numericPredictionMetadataPanel",
            self.detail_content,
        )
        self.metadata_empty = QLabel(
            "No additional information recorded.", self.metadata_panel
        )
        self.metadata_empty.setObjectName("numericMetadataEmptyMessage")
        self.metadata_empty.setWordWrap(True)
        _make_selectable(self.metadata_empty)
        apply_text_role(self.metadata_empty, TextRole.SECONDARY)
        metadata_layout.addWidget(self.metadata_empty)
        metadata_layout.addWidget(self.forecast_deadline_row)
        metadata_layout.addWidget(self.expected_resolution_row)
        metadata_layout.addWidget(self.background_section)
        metadata_layout.addWidget(self.resolution_criteria_section)
        metadata_layout.addWidget(self.rationale_section)
        metadata_layout.addWidget(self.definition_history)

        timeline_panel, timeline_panel_layout = _detail_panel(
            "numericPredictionTimelinePanel",
            self.detail_content,
        )
        apply_text_role(timeline_label, TextRole.SECTION_TITLE)
        timeline_panel_layout.addWidget(timeline_label)
        timeline_panel_layout.addWidget(self.timeline_error)
        timeline_panel_layout.addWidget(self.timeline_content)

        history_panel, history_panel_layout = _detail_panel(
            "numericPredictionHistoryPanel",
            self.detail_content,
        )
        apply_text_role(history_label, TextRole.SECTION_TITLE)
        history_panel_layout.addWidget(history_label)
        history_panel_layout.addWidget(self.history_error)
        history_panel_layout.addWidget(self.quantile_cdf)
        history_panel_layout.addWidget(self.quantile_cdf_summary)
        apply_surface_role(history_panel, SurfaceRole.CANVAS)

        self._page_header = header
        header.hide()
        apply_text_role(self.question, TextRole.QUESTION)
        self.forecast_heading = forecast_label
        forecast_label.setText("Current committed forecast")
        self.interval_display = NumericInterval(summary_panel)
        summary_layout.removeWidget(self.interval)
        summary_layout.removeWidget(self.median)
        self.interval.hide()
        self.median.hide()
        summary_layout.addWidget(self.interval_display)
        self.numeric_history_label.setText("Current distribution")
        self.header_timing = HeaderTiming(
            self.forecast_deadline_row,
            summary_panel,
            "90% interval · 50% interval · Median",
        )
        summary_layout.addWidget(self.header_timing)
        self.terminal_summary = TerminalSummary(summary_panel)
        summary_layout.addWidget(self.terminal_summary)
        action_heading.hide()
        action_help.hide()
        old_actions = actions.layout()
        while old_actions.count():
            old_actions.takeAt(0)
        self.action_strip = QWidget(action_panel)
        self.action_strip.setProperty("reckonsolveDetailActions", "true")
        strip = FlowLayout(self.action_strip)
        for button in (
            self.revise_forecast_button,
            self.add_journal_entry_button,
            self.review_forecast_button,
            self.resolve_button,
            self.write_postmortem_button,
            self.skip_postmortem_button,
        ):
            button.setParent(self.action_strip)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            strip.addWidget(button)
        self.more_button = QPushButton("More", self.action_strip)
        apply_action_role(self.more_button, ActionRole.SECONDARY)
        self.more_menu = QMenu(self.more_button)
        self.more_actions = []
        for button in (
            self.edit_details_button,
            self.correct_resolution_button,
            self.correct_invalidation_button,
            self.mark_invalid_button,
            self.delete_button,
        ):
            button.hide()
            action = self.more_menu.addAction(button.text(), button.click)
            self.more_actions.append((action, button))
        self.more_button.setMenu(self.more_menu)
        strip.addWidget(self.more_button)
        self.current_revision_button = QPushButton("Current Revision", timeline_panel)
        self.current_revision_button.setObjectName("jumpToCurrentRevisionButton")
        self.current_revision_button.setAccessibleName("Jump to Current Revision")
        self.current_revision_button.clicked.connect(self._jump_current_revision)
        actions.hide()
        action_panel_layout.addWidget(self.action_strip)
        self.timeline_order = QComboBox(timeline_panel)
        self.timeline_order.setAccessibleName("Timeline reading order")
        self.timeline_order.addItems(["Newest first", "Oldest first"])
        self.timeline_rows = TimelineRows(self.timeline_layout)
        self.timeline_order.currentIndexChanged.connect(
            lambda index: self.timeline_rows.order(descending=index == 0)
        )
        heading = timeline_panel_layout.takeAt(0).widget()
        self.scroll_area = DetailWorkspace(self.detail_content, self)
        self.scroll_area.setObjectName("numericPredictionDetailScrollArea")
        self.workspace = self.scroll_area
        self.workspace.set_timeline_controls(
            timeline_controls(
                heading,
                self.current_revision_button,
                self.timeline_order,
                self.detail_content,
            )
        )
        self.skip_postmortem_button.before_skip = lambda: self.workspace.confirm_exit(
            "skip Postmortem"
        )
        self.criteria_read_button = criteria_reader(
            self.resolution_criteria_section, self.resolution_criteria
        )
        self.reading_sections = AdaptiveReadingSections(
            self.resolution_notes,
            self.postmortem,
            self.postmortem_completion,
            self.detail_content,
        )
        self.distribution_disclosure = collapse_section(
            history_panel, "Latest Committed Distribution", compact=True
        )
        self.metadata_disclosure = collapse_section(
            self.metadata_panel, "More Information", compact=True
        )
        apply_action_role(self.write_postmortem_button, ActionRole.SECONDARY)
        overview = [
            self.resolution_criteria_section,
            self.definition_summary,
            self.reading_sections.notes,
            self.reading_sections.reflection,
            self.quantile_scorecard,
            self.resolution_history,
            self.invalidation_history,
            self.distribution_disclosure,
            self.metadata_disclosure,
        ]
        self.scored_forecast_disclosure = collapse_section(
            self.resolution_scoring, "Scored Forecast Context", compact=True
        )
        self.resolution_section.layout().removeWidget(self.resolution_scoring)
        self.resolution_section.layout().addWidget(self.scored_forecast_disclosure)
        for panel in (summary_panel, action_panel, timeline_panel, self.metadata_panel):
            apply_surface_role(panel, SurfaceRole.CANVAS)
        overview.insert(0, QLabel("Overview", self))
        self.overview_heading = overview[0]
        apply_text_role(overview[0], TextRole.SECTION_TITLE)
        self.workspace.compose(
            summary_panel,
            action_panel,
            [timeline_panel],
            overview,
        )
        self.locked_explanation = QLabel(
            "Forecast Deadline passed. Revisions and Reviews are closed; the remaining actions are available.",
            summary_panel,
        )
        self.locked_explanation.setWordWrap(True)
        summary_layout.addWidget(self.locked_explanation)
        self.locked_explanation.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(header)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.detail_error)
        layout.addWidget(self.scroll_area, 1)

        self.show_prediction(None)
        self.revise_forecast_button.clicked.connect(self.open_revise_forecast)
        self.add_journal_entry_button.clicked.connect(self.open_add_journal_entry)
        self.review_forecast_button.clicked.connect(self.open_forecast_review)
        self.edit_details_button.clicked.connect(self.open_edit_details)
        self.resolve_button.clicked.connect(self.open_resolve_prediction)
        self.mark_invalid_button.clicked.connect(self.open_mark_invalid)
        self.delete_button.clicked.connect(self.delete_prediction)
        self.correct_resolution_button.clicked.connect(self.open_correct_resolution)
        self.correct_invalidation_button.clicked.connect(
            self.open_correct_invalidation_reason
        )

    @property
    def prediction_id(self) -> int | None:
        """Return the Numeric Prediction currently presented by the screen."""

        return None if self._prediction is None else self._prediction.prediction_id

    def focus_search_match(self, document: SearchDocument) -> None:
        """Reveal and briefly emphasize a matching Numeric canonical context."""

        if self.prediction_id != document.prediction_id:
            return
        target: QWidget
        if document.is_superseded and document.source_kind in {
            SearchSourceKind.QUESTION,
            SearchSourceKind.RESOLUTION_CRITERIA,
        }:
            self.definition_history.setChecked(True)
            target = (
                self.findChild(QWidget, f"definitionChange{document.source_record_id}")
                or self.definition_history
            )
        elif document.source_kind is SearchSourceKind.QUESTION:
            target = self.question
        elif document.source_kind is SearchSourceKind.TAG:
            target = self.tags
        elif document.source_kind is SearchSourceKind.BACKGROUND:
            target = self.background_section
        elif document.source_kind is SearchSourceKind.RESOLUTION_CRITERIA:
            target = self.resolution_criteria_section
        elif document.source_kind is SearchSourceKind.FORECAST_RATIONALE:
            target = (
                self.findChild(
                    QWidget,
                    f"numericTimelineForecast{document.source_record_id}",
                )
                or self.timeline_content
            )
        elif document.source_kind is SearchSourceKind.FORECAST_REVIEW:
            target = (
                self.findChild(
                    QWidget, f"numericTimelineBodyReview{document.source_record_id}"
                )
                or self.findChild(
                    QWidget,
                    f"numericTimelineReview{document.source_record_id}",
                )
                or self.timeline_content
            )
        elif document.source_kind is SearchSourceKind.JOURNAL:
            target = (
                self.findChild(
                    QWidget,
                    f"numericTimelineJournal{document.source_record_id}",
                )
                or self.timeline_content
            )
            if document.is_superseded:
                history = target.findChild(
                    QGroupBox,
                    f"journalEntryEditHistory{document.source_record_id}",
                )
                if history is not None:
                    history.setChecked(True)
                    version_target_name = (
                        f"journalEntryOriginalBody{document.source_record_id}"
                        if document.source_version_id is None
                        else f"journalCorrectionBody{document.source_version_id}"
                    )
                    target = history.findChild(QWidget, version_target_name) or history
            else:
                target = (
                    target.findChild(
                        QWidget,
                        f"numericTimelineBodyJournal{document.source_record_id}",
                    )
                    or target
                )
        elif document.source_kind in {
            SearchSourceKind.RESOLUTION_NOTES,
            SearchSourceKind.POSTMORTEM,
            SearchSourceKind.OUTCOME_CORRECTION_REASON,
        }:
            if (
                document.is_superseded
                or document.source_kind is SearchSourceKind.OUTCOME_CORRECTION_REASON
            ):
                self.resolution_history.setChecked(True)
                target = self.resolution_history
            elif document.source_kind is SearchSourceKind.POSTMORTEM:
                target = self.postmortem
            else:
                target = self.resolution_notes
        else:
            if document.is_superseded:
                self.invalidation_history.setChecked(True)
                target = self.invalidation_history
            else:
                target = self.terminal_summary.note
        _focus_search_widget(self.scroll_area, target)

    @reading_refresh
    def show_prediction(self, prediction: NumericPredictionSnapshot | None) -> None:
        """Present one Numeric Prediction or the honest empty state."""

        self.skip_postmortem_button.set_context(None)
        self._prediction = prediction
        self._hide_error()
        if prediction is None:
            self.question.clear()
            self.tags.clear()
            self.status.clear()
            self.interval.clear()
            self.median.clear()
            self.history_error.setHidden(True)
            self._clear_timeline()
            self.timeline_error.setHidden(True)
            self.revise_forecast_button.setEnabled(False)
            self.add_journal_entry_button.setEnabled(False)
            self.review_forecast_button.setEnabled(False)
            self.resolve_button.setEnabled(False)
            self.mark_invalid_button.setEnabled(False)
            self.delete_button.setEnabled(False)
            self.correct_resolution_button.setEnabled(False)
            self.correct_invalidation_button.setEnabled(False)
            self._resolution_history = None
            self._invalidation_history = None
            self.resolution_section.setHidden(True)
            self.quantile_scorecard.setHidden(True)
            self.invalidation_section.setHidden(True)
            self.definition_history.setHidden(True)
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            return

        revision = prediction.current_revision
        self.question.setText(prediction.question)
        self.tags.setText("  ".join(f"#{tag}" for tag in prediction.tags))
        self.tags.setHidden(not prediction.tags)
        self.status.setText(prediction.status.value.upper())
        apply_badge_role(self.status, _status_tone(prediction.status))
        q = revision.quantiles
        self.interval_display.set_forecast(q, prediction.unit)
        self.forecast_heading.setText("Current committed forecast · " + prediction.unit)
        self.interval.setText(f"90% interval: {q.q05} to {q.q95} {prediction.unit}")
        self.median.setText(
            f"Median: {q.q50} {prediction.unit}\n50% interval: {q.q25} to {q.q75} {prediction.unit}\nFive-quantile model · {prediction.value_constraint.value}"
        )
        self.revise_forecast_button.setText("Revise Forecast")
        self.review_forecast_button.setText("Keep Forecast")
        self.review_forecast_button.setAccessibleName(
            "Record a Review retaining all five current percentiles"
        )
        self.review_forecast_button.setToolTip(
            self.review_forecast_button.accessibleName()
        )
        self.revise_forecast_button.setAccessibleName(
            "Revise all five numeric percentiles"
        )
        self.unit.setText(prediction.unit)
        self.precision.setText(str(prediction.decimal_places))
        self.precision.setAccessibleName(f"Decimal places: {prediction.decimal_places}")
        self._show_optional_metadata(prediction)
        self.rationale.setText(revision.rationale or "")
        self.rationale_section.setHidden(not revision.rationale)
        self.revise_forecast_button.setEnabled(
            prediction.status is PredictionStatus.OPEN
        )
        self.add_journal_entry_button.setEnabled(
            prediction.status in (PredictionStatus.OPEN, PredictionStatus.LOCKED)
        )
        self.review_forecast_button.setEnabled(
            prediction.status is PredictionStatus.OPEN
        )
        self.review_forecast_button.setToolTip(
            "Record deliberate reconsideration while keeping this forecast unchanged."
            if prediction.status is PredictionStatus.OPEN
            else "Forecast Reviews can be recorded only while Open."
        )
        terminal_allowed = prediction.status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        )
        self.resolve_button.setEnabled(terminal_allowed)
        self.resolve_button.setToolTip(
            "Record the actual outcome and effective resolution time."
        )
        self.mark_invalid_button.setEnabled(terminal_allowed)
        self.delete_button.setEnabled(
            prediction.status is PredictionStatus.OPEN and prediction.deletion_allowed
        )
        self._show_terminal_information(prediction)
        self._sync_reading_actions(prediction)
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)
        self._load_history(prediction.prediction_id)
        self._load_timeline(prediction.prediction_id)
        self._load_definition_history(prediction.prediction_id)

    def refresh(self) -> None:
        """Reload the presented Numeric Prediction without hiding prior data on error."""

        try:
            prediction = (
                self._operations.get_latest_numeric_prediction()
                if self._prediction is None
                else self._operations.get_numeric_prediction(
                    self._prediction.prediction_id
                )
            )
        except ApplicationError as error:
            self._show_error(
                f"Numeric Prediction Detail could not be refreshed. {error}"
            )
            return
        self.show_prediction(prediction)

    def _show_optional_metadata(self, prediction: NumericPredictionSnapshot) -> None:
        self.forecast_deadline.setText(
            _format_date(prediction.forecast_deadline, widget=self)
        )
        self.forecast_deadline_row.setHidden(prediction.forecast_deadline is None)
        contract = getattr(prediction, "forecast_contract", None)
        if contract is not None:
            self.forecast_deadline.setText(
                exact_detail_time(contract.forecast_deadline.instant, widget=self)
            )
            self.forecast_deadline.setToolTip(
                "Exact, fixed deadline: "
                + format_local_deadline(contract.forecast_deadline.instant)
            )
            self.forecast_deadline_row.show()
        self.expected_resolution.setText(
            _format_date(prediction.expected_resolution, widget=self)
        )
        self.expected_resolution_row.setHidden(prediction.expected_resolution is None)
        self.background.setText(prediction.background or "")
        self.background_section.setHidden(not prediction.background)
        self.resolution_criteria.setText(prediction.resolution_criteria or "")
        self.resolution_criteria_section.setHidden(not prediction.resolution_criteria)

    def _show_terminal_information(
        self,
        prediction: NumericPredictionSnapshot,
    ) -> None:
        self.quantile_scorecard.hide()
        self._quantile_score = None
        resolution = prediction.resolution
        if resolution is None:
            self._resolution_history = None
            self.correct_resolution_button.setEnabled(False)
            self.resolution_history.setHidden(True)
            self.resolution_section.setHidden(True)
            self.quantile_scorecard.setHidden(True)
        else:
            try:
                history = self._operations.get_numeric_resolution_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                effective = resolution
                completion = None
                self._resolution_history = None
                self.correct_resolution_button.setEnabled(False)
                self.resolution_history.setHidden(True)
                self._show_error(f"Resolution history is unavailable. {error}")
            else:
                effective = history.effective
                completion = history.postmortem_completion
                self._resolution_history = history
                self.correct_resolution_button.setEnabled(True)
                _show_numeric_resolution_correction_history(
                    self.resolution_history,
                    history,
                    prediction.unit,
                )
                self.skip_postmortem_button.set_context(history)
            self.resolution_actual.setText(
                f"Actual value: {effective.actual_value} {prediction.unit}"
            )
            self.resolution_time.setText(
                f"Effective resolution: {exact_detail_time(effective.effective_resolution_at, widget=self)}\n"
                f"Recorded at: {exact_detail_time(resolution.resolved_at, widget=self)}"
            )
            self.resolution_time.setToolTip(
                f"Effective: {effective.effective_resolution_at.isoformat()}\nRecorded: {resolution.resolved_at.isoformat()}"
            )
            self.resolution_scoring.setText(
                "Scoring uses the last revision strictly before the earlier of effective resolution and the permanent Deadline."
            )
            self.resolution_notes.setText(effective.resolution_notes or "")
            self.resolution_notes.setHidden(not effective.resolution_notes)
            self.postmortem.setText(effective.postmortem or "")
            self.postmortem.setHidden(not effective.postmortem)
            self.postmortem_completion.setText(
                ""
                if completion is None
                else "Postmortem completion: Skipped "
                f"{_format_local_timestamp(completion.completed_at, widget=self)}. You may still "
                "add a Postmortem later; this completion remains in history."
            )
            self.postmortem_completion.setHidden(completion is None)
            self.resolution_section.setHidden(False)
            self._show_scorecard(prediction.prediction_id)
        invalidation = prediction.invalidation
        if invalidation is None:
            self._invalidation_history = None
            self.correct_invalidation_button.setEnabled(False)
            self.invalidation_history.setHidden(True)
            self.invalidation_section.setHidden(True)
        else:
            try:
                invalidation_history = self._operations.get_invalidation_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                effective_invalidation = invalidation
                self._invalidation_history = None
                self.correct_invalidation_button.setEnabled(False)
                self.invalidation_history.setHidden(True)
                self._show_error(f"Invalidation history is unavailable. {error}")
            else:
                effective_invalidation = invalidation_history.effective
                self._invalidation_history = invalidation_history
                self.correct_invalidation_button.setEnabled(True)
                _show_invalidation_correction_history(
                    self.invalidation_history,
                    invalidation_history,
                )
            self.invalidation_time.setText(
                f"Marked Invalid {_format_local_timestamp(invalidation.invalidated_at, widget=self)}"
            )
            self.invalidation_reason.setText(
                ""
                if not effective_invalidation.reason
                else f"Reason: {effective_invalidation.reason}"
            )
            self.invalidation_reason.setHidden(not effective_invalidation.reason)
            self.invalidation_section.setHidden(False)

    def _show_scorecard(self, prediction_id: int) -> None:
        try:
            scorecard = self._operations.get_prediction_scorecard(prediction_id)
        except ApplicationError as error:
            self.quantile_scorecard.setHidden(True)
            self._show_error(f"Scorecard is unavailable. {error}")
            return
        if isinstance(scorecard, QuantileScorecard):
            self._quantile_score = scorecard
            self.quantile_scorecard.hide()
            self.quantile_scorecard.set_scorecard(scorecard, primary_facts=False)
            self.quantile_scorecard.show()
            return
        self.quantile_scorecard.hide()

    def _show_error(self, message: str) -> None:
        self.detail_error.setText(message)
        self.detail_error.setHidden(False)

    def _hide_error(self) -> None:
        self.detail_error.clear()
        self.detail_error.setHidden(True)

    def _load_history(self, prediction_id: int) -> None:
        try:
            revisions = self._operations.list_numeric_forecast_revisions(prediction_id)
        except ApplicationError as error:
            self.history_error.setText(
                f"Numeric interval history is unavailable. {error}"
            )
            self.history_error.setHidden(False)
            return
        self.quantile_cdf.show()
        self.quantile_cdf_summary.show()
        self.numeric_history_label.setText(
            "Latest committed distribution"
            if self._prediction.status
            in (PredictionStatus.RESOLVED, PredictionStatus.INVALID)
            else "Current committed distribution"
        )
        self.quantile_cdf.set_forecast(revisions[-1].quantiles, self._prediction.unit)
        self.quantile_cdf_summary.setText(
            self.quantile_cdf.accessibleDescription()
            + "\nEvery earlier forecast remains in the timeline below its original timestamp."
        )
        card = self._quantile_score
        if card is not None and card.final_revision_id != revisions[-1].revision_id:
            self.quantile_cdf_summary.setText(
                (
                    "No forecast qualified for scoring. "
                    if card.final_revision_id is None
                    else "This is not the forecast used for scoring. "
                )
                + "It is the latest committed distribution.\n"
                + self.quantile_cdf_summary.text()
            )
        self.history_error.setHidden(True)

    def _load_timeline(self, prediction_id: int) -> None:
        try:
            events = self._operations.list_numeric_timeline(prediction_id)
        except ApplicationError as error:
            self.timeline_error.setText(f"Numeric timeline is unavailable. {error}")
            self.timeline_error.setHidden(False)
            return
        snapshot = (
            prediction_id,
            tuple(events),
            self._resolution_history,
            self._invalidation_history,
            self._prediction.unit,
        )
        if self.timeline_rows.matches(snapshot):
            self.timeline_error.hide()
            return
        self._sync_timing(events)
        forecasts = {
            event.revision.sequence: event.revision.quantiles
            for event in events
            if event.kind == "forecast"
        }
        rows = []
        for event in events:
            previous = (
                forecasts.get(event.revision.sequence - 1)
                if event.kind == "forecast"
                else None
            )
            rows.append(
                (
                    event.created_at,
                    0,
                    self.timeline_rows.row(
                        (prediction_id, event.kind, event.record_id),
                        (
                            event,
                            previous,
                            self._prediction.unit,
                            event.kind == "forecast"
                            and event.record_id
                            == self._prediction.current_revision.revision_id,
                            event.kind == "forecast"
                            and self._quantile_score is not None
                            and event.record_id
                            in self._quantile_score.excluded_revision_ids,
                        ),
                        lambda event=event, previous=previous: (
                            self._quantile_timeline_row(event, previous)
                        ),
                    ),
                )
            )
        rows.extend(
            terminal_timeline_rows(
                self._resolution_history,
                self._invalidation_history,
                self.timeline_content,
                unit=self._prediction.unit,
            )
        )
        self.timeline_rows.replace(
            snapshot, rows, descending=self.timeline_order.currentIndex() == 0
        )
        if not rows:
            empty = QLabel("No Numeric ForecastRevisions have been recorded.")
            empty.setObjectName("numericTimelineEmptyState")
            empty.setTextFormat(Qt.TextFormat.PlainText)
            self.timeline_layout.addWidget(empty)
        self.timeline_error.setHidden(True)

    def _quantile_timeline_row(
        self, event: QuantileTimelineEvent, previous: FiveQuantiles | None = None
    ) -> QWidget:
        frame = QFrame(self.timeline_content)
        frame.setObjectName(f"numericTimeline{event.kind.title()}{event.record_id}")
        apply_surface_role(frame, SurfaceRole.BASE)
        layout = QVBoxLayout(frame)
        timestamp = QLabel(
            _format_local_timestamp(event.created_at, widget=self), frame
        )
        timestamp.setTextFormat(Qt.TextFormat.PlainText)
        timestamp.setToolTip(event.created_at.isoformat())
        _make_selectable(timestamp)
        layout.addWidget(timestamp)
        kind = {
            "forecast": "FORECAST",
            "journal": "JOURNAL",
            "review": "REVIEW — FORECAST RETAINED",
        }[event.kind]
        text = QLabel(
            f"{kind}\n{interval_transition_text(previous, event.revision.quantiles, self._prediction.unit) if previous is not None else interval_text(event.revision.quantiles, self._prediction.unit)}\n{event.text or ''}",
            frame,
        )
        text.setWordWrap(True)
        text.setObjectName(f"numericTimelineBody{event.kind.title()}{event.record_id}")
        text.setTextFormat(Qt.TextFormat.PlainText)
        _make_selectable(text)
        layout.addWidget(progressive_body(text) if event.kind != "forecast" else text)
        if (
            event.kind == "forecast"
            and event.record_id == self._prediction.current_revision.revision_id
        ):
            current_marker(frame)
        elif event.kind != "forecast":
            quiet_event(frame)
        if (
            event.kind == "forecast"
            and self._quantile_score is not None
            and event.record_id in self._quantile_score.excluded_revision_ids
        ):
            excluded = QLabel(
                "Excluded from scoring: at or after the effective cutoff. Preserved history.",
                frame,
            )
            excluded.setWordWrap(True)
            excluded.setObjectName(f"numericForecastExcluded{event.record_id}")
            apply_text_role(excluded, TextRole.SECONDARY)
            layout.addWidget(excluded)
        if event.kind == "journal":
            if event.corrections:
                edited = QLabel(
                    "Edited "
                    + _format_local_timestamp(
                        event.corrections[-1].corrected_at, widget=self
                    ),
                    frame,
                )
                edited.setTextFormat(Qt.TextFormat.PlainText)
                _make_selectable(edited)
                layout.addWidget(edited)
                layout.addWidget(_journal_edit_history_widget(event, frame))
            button = QPushButton("Correct Entry", frame)
            apply_action_role(button, ActionRole.QUIET)
            apply_lucide_icon(button, LucideIcon.PENCIL)
            button.clicked.connect(lambda: self.open_correct_journal_entry(event))
            layout.addWidget(button, 0, Qt.AlignmentFlag.AlignCenter)
        return frame

    def _load_definition_history(self, prediction_id: int) -> None:
        try:
            changes = self._operations.list_definition_changes(prediction_id)
        except ApplicationError as error:
            self.definition_history.setHidden(True)
            self.metadata_empty.setText("Definition history is unavailable.")
            self.metadata_empty.show()
            self._show_error(str(error))
            return

        _clear_widget_layout(self.definition_history_layout)
        for change in changes:
            self.definition_history_layout.addWidget(
                _definition_change_widget(change, self.definition_history_content)
            )
        self.definition_history.setChecked(False)
        self.definition_history_content.setHidden(True)
        self.definition_history.setHidden(not changes)
        if changes:
            self.metadata_panel.setHidden(False)
        self.metadata_empty.setText("No additional information recorded.")
        self.metadata_empty.setVisible(
            all(
                section.isHidden()
                for section in (
                    self.expected_resolution_row,
                    self.background_section,
                    self.rationale_section,
                    self.definition_history,
                )
            )
        )

    def _clear_timeline(self) -> None:
        self.timeline_rows.clear()

    def open_revise_forecast(self) -> None:
        if not self.workspace.prepare_task("Revision"):
            return
        if self._prediction is None:
            return
        self.refresh()
        if (
            self._prediction is None
            or self._prediction.status is not PredictionStatus.OPEN
        ):
            return
        dialog = ReviseQuantileForecastDialog(self._operations, self._prediction, self)
        dialog.revision_saved.connect(self.show_prediction)
        self._start_editor(dialog, "Revision")

    def open_edit_details(self) -> None:
        """Open a prefilled type-aware metadata dialog for this Numeric Prediction."""

        if not self.workspace.prepare_task("Edit Details"):
            return
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_numeric_prediction(
                self._prediction.prediction_id
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        dialog = EditPredictionDetailsDialog(self._operations, prediction, self)
        self._edit_dialog = dialog
        dialog.metadata_saved.connect(self.show_prediction)
        dialog.finished.connect(self._edit_dialog_finished)
        dialog.open()

    def _edit_dialog_finished(self, _result: int) -> None:
        self._edit_dialog = None

    def open_add_journal_entry(self) -> None:
        if not self.workspace.prepare_task("Journal"):
            return
        if self._prediction is None:
            return
        self.refresh()
        if self._prediction is None or self._prediction.status not in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        ):
            return
        dialog = AddNumericJournalEntryDialog(self._operations, self._prediction, self)
        dialog.journal_saved.connect(lambda _entry: self.refresh())
        self._start_editor(dialog, "Journal")

    def open_forecast_review(self) -> None:
        """Refresh, then offer a side-effect-free Open-only Review dialog."""
        if not self.workspace.prepare_task("Review"):
            return

        if self._prediction is None:
            return
        self.refresh()
        if (
            self._prediction is None
            or self._prediction.status is not PredictionStatus.OPEN
        ):
            self._show_error("Forecast Reviews can be recorded only while Open.")
            return
        dialog = ForecastReviewDialog(self._operations, self._prediction, self)
        dialog.review_saved.connect(lambda _review: self.refresh())
        self._start_editor(dialog, "Review")

    def open_resolve_prediction(self) -> None:
        """Refresh reviewed Numeric context before opening terminal resolution."""
        if not self.workspace.prepare_task("Resolve"):
            return

        if self._prediction is None:
            return
        self.refresh()
        if self._prediction is None or self._prediction.status not in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        ):
            return
        dialog = ResolveNumericPredictionDialog(
            self._operations,
            self._prediction,
            self,
        )
        dialog.prediction_resolved.connect(self.show_prediction)
        self._start_editor(dialog, "Resolve")

    def open_mark_invalid(self) -> None:
        """Refresh reviewed Numeric context before opening terminal invalidation."""
        if not self.workspace.prepare_task("Mark Invalid"):
            return

        if self._prediction is None:
            return
        self.refresh()
        if self._prediction is None or self._prediction.status not in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        ):
            return
        dialog = MarkNumericPredictionInvalidDialog(
            self._operations,
            self._prediction,
            self,
        )
        dialog.prediction_invalidated.connect(self.show_prediction)
        self._start_editor(dialog, "Mark Invalid")

    def delete_prediction(self) -> None:
        """Confirm permanent deletion of refreshed untouched Numeric state."""

        if not self.workspace.prepare_task("Delete"):
            return
        if self._prediction is None:
            return
        self.refresh()
        prediction = self._prediction
        if (
            prediction is None
            or prediction.status is not PredictionStatus.OPEN
            or not prediction.deletion_allowed
        ):
            self._show_error(
                "Only an untouched Open prediction can be deleted. Use Mark "
                "Invalid to preserve meaningful history outside scoring."
            )
            return
        answer = QMessageBox.warning(
            self,
            "Permanently delete Numeric Prediction?",
            "This permanently deletes the Numeric Prediction and its initial "
            "interval. This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            latest = self._operations.delete_numeric_prediction(
                prediction.prediction_id,
                expected_revision_id=prediction.current_revision.revision_id,
                expected_metadata_version=prediction.metadata_version,
                confirm_permanent_deletion=True,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(latest)

    def open_correct_journal_entry(self, entry: QuantileTimelineEvent) -> None:
        if not self.workspace.prepare_task("Correct Journal"):
            return
        dialog = CorrectNumericJournalEntryDialog(self._operations, entry, self)
        dialog.correction_saved.connect(lambda _entry: self.refresh())
        self._start_editor(dialog, "Correct Journal")

    def open_correct_resolution(self) -> None:
        """Refresh, then correct the effective Numeric Resolution append-only."""

        if not self.workspace.prepare_task("Correct Resolution"):
            return
        if self._prediction is None:
            return
        self.refresh()
        history = self._resolution_history
        prediction = self._prediction
        if history is None or prediction is None:
            return
        dialog = CorrectNumericResolutionDialog(
            self._operations,
            prediction,
            history,
            self,
        )
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.open()

    def open_correct_invalidation_reason(self) -> None:
        """Refresh, then correct the effective Invalid reason append-only."""

        if not self.workspace.prepare_task("Correct Invalid reason"):
            return
        if self._prediction is None:
            return
        self.refresh()
        history = self._invalidation_history
        if history is None:
            return
        dialog = CorrectInvalidationReasonDialog(
            self._operations,
            history,
            self,
        )
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.open()

    def _sync_reading_actions(self, prediction) -> None:
        self.resolution_section.hide()
        self.invalidation_section.hide()
        self.reading_sections.sync(prediction.status)
        self.overview_heading.setText(
            "ARCHIVAL CONTEXT"
            if prediction.status is PredictionStatus.INVALID
            else "OVERVIEW"
        )
        self.workspace.set_reading_context(
            self.overview_heading,
            terminal=prediction.status
            in (PredictionStatus.RESOLVED, PredictionStatus.INVALID),
        )
        terminal = prediction.status in (
            PredictionStatus.RESOLVED,
            PredictionStatus.INVALID,
        )
        for widget in (
            self.interval_display,
            self.forecast_heading,
            self.header_timing,
        ):
            widget.setVisible(not terminal)
        self.terminal_summary.setVisible(terminal)
        if prediction.status is PredictionStatus.RESOLVED:
            card = self._quantile_score
            facts = quantile_scorecard_lines(card) if card is not None else ()
            notices = [
                line
                for line in facts
                if line.startswith(("Scoring facts", "Revisions excluded"))
            ]
            if card is not None and card.unscored_reason:
                notices.insert(0, card.unscored_reason)
            self.terminal_summary.set_facts(
                outcome=self.resolution_actual.text(),
                score=facts[1] if facts else "Score unavailable",
                timing=self.resolution_time.text(),
                timing_tooltip=self.resolution_time.toolTip(),
                note="\n".join(notices)
                if card is not None
                else "The score could not be loaded. Try again before interpreting this result.",
                context=facts[2] if card is not None and card.final is not None else "",
            )
        elif prediction.status is PredictionStatus.INVALID:
            self.terminal_summary.set_facts(
                outcome="Recorded reason",
                score="Not scored",
                timing=invalidation_timing(
                    self.invalidation_time.text(),
                    self._invalidation_history,
                    widget=self,
                ),
                note=self.invalidation_reason.text() or "No reason recorded.",
                context=interval_text(
                    prediction.current_revision.quantiles, prediction.unit
                )
                + f"\nOriginal Forecast Deadline: {self.forecast_deadline.text()}",
                context_title="Last forecast · Not scored",
                timing_tooltip=invalidation_exact_timing(self._invalidation_history),
            )
        self.write_postmortem_button.setVisible(
            prediction.status is PredictionStatus.RESOLVED
        )
        self.write_postmortem_button.setText(
            "Edit Postmortem" if self.postmortem.text().strip() else "Write Postmortem"
        )
        for button in (
            self.revise_forecast_button,
            self.review_forecast_button,
            self.add_journal_entry_button,
            self.resolve_button,
        ):
            button.setVisible(button.isEnabled())
        for action, button in self.more_actions:
            action.setVisible(button.isEnabled())
        self.locked_explanation.setVisible(prediction.status is PredictionStatus.LOCKED)
        self.resolution_criteria_section.show()
        self.criteria_read_button.setVisible(
            len(prediction.resolution_criteria or "") > 450
        )
        self.resolution_criteria.setText(
            prediction.resolution_criteria or "No resolution criteria recorded."
        )

    def _sync_timing(self, events) -> None:
        forecasts = [event for event in events if event.kind == "forecast"]
        considered = [event for event in events if event.kind in ("forecast", "review")]
        revised = max(
            (event.created_at for event in forecasts),
            default=self._prediction.created_at,
        )
        last = max((event.created_at for event in considered), default=revised)
        self.header_timing.activity.setText(
            "Last revised: "
            + format_date(revised, self)
            + " · Last considered: "
            + format_date(last, self)
        )

    def _jump_current_revision(self) -> None:
        if self._prediction is None:
            return
        identifier = self._prediction.current_revision.revision_id
        target = self.findChild(QWidget, "numericTimelineForecast" + str(identifier))
        if target is not None:
            self.workspace.ensureWidgetVisible(target, 12, 12)
            target.setFocus(Qt.FocusReason.OtherFocusReason)

    def _start_editor(self, editor, kind: str) -> None:
        editor.setProperty("reviewedQuestion", self._prediction.question)
        editor.setProperty(
            "reviewedForecast",
            _numeric_forecast_text(
                self._prediction.current_revision, self._prediction.unit
            ),
        )
        editor._refresh_reading = self.refresh
        self.workspace.begin_editor(editor, kind)

    def open_postmortem(self) -> None:
        if self._prediction is None or not self.workspace.prepare_task("Postmortem"):
            return
        try:
            expected = self._operations.get_numeric_resolution_history(
                self.prediction_id
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        editor = ReflectionEditor(
            expected.effective.postmortem,
            lambda body, clear, reason: save_postmortem(
                self._operations,
                expected,
                body,
                confirm_clear=clear,
                correction_reason=reason,
            ),
            self,
        )
        editor.saved.connect(lambda _result: self.refresh())
        self._start_editor(editor, "Postmortem")
