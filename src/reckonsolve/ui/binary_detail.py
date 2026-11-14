"""Prediction detail responsibilities extracted from the desktop composition."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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

from reckonsolve.analytics.trajectory import TrajectoryScorecard
from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.domain.predictions import (
    BinaryResolutionHistory,
    InvalidationHistory,
    PredictionStatus,
)
from reckonsolve.domain.search import SearchDocument, SearchSourceKind
from reckonsolve.forecast_display import (
    format_local_deadline,
)
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
    invalidation_exact_timing,
    invalidation_timing,
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
from reckonsolve.ui.postmortem_action import PostmortemSkipButton
from reckonsolve.ui.prediction_contracts import (
    JournalTimelineSnapshot,
    PredictionOperations,
    PredictionSnapshot,
)
from reckonsolve.ui.prediction_dialogs import (
    AddJournalEntryDialog,
    CorrectBinaryResolutionDialog,
    CorrectInvalidationReasonDialog,
    CorrectJournalEntryDialog,
    EditPredictionDetailsDialog,
    ForecastReviewDialog,
    MarkInvalidDialog,
    ResolvePredictionDialog,
    ReviseForecastDialog,
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
    _forecast_review_widget,
    _forecast_timeline_widget,
    _format_date,
    _format_local_timestamp,
    _history_content,
    _journal_entry_widget,
    _make_selectable,
    _show_binary_resolution_correction_history,
    _show_invalidation_correction_history,
    _status_tone,
)
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart
from reckonsolve.ui.reflection_editor import ReflectionEditor
from reckonsolve.ui.scorecard_components import TrajectoryScoreDetails
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


class PredictionDetailScreen(QWidget):
    """Display the current prediction definition and safe metadata editing."""

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("predictionDetailScreen")
        self._operations = operations
        self._prediction: PredictionSnapshot | None = None
        self._edit_dialog: EditPredictionDetailsDialog | None = None
        self._revision_dialog: ReviseForecastDialog | None = None
        self._journal_dialog: AddJournalEntryDialog | None = None
        self._journal_correction_dialog: CorrectJournalEntryDialog | None = None
        self._resolution_dialog: ResolvePredictionDialog | None = None
        self._invalidation_dialog: MarkInvalidDialog | None = None
        self._terminal_correction_dialog: QDialog | None = None
        self._resolution_history: BinaryResolutionHistory | None = None
        self._invalidation_history: InvalidationHistory | None = None
        self._chart_prediction_id: int | None = None

        header = PageHeader(
            "Prediction Detail",
            "Current belief, supporting context, and the complete preserved history.",
            title_object_name="predictionDetailScreenTitle",
            parent=self,
        )

        self.empty_state = EmptyStateLabel(
            "No prediction yet. Create one from New Prediction to see it here.",
            parent=self,
        )
        self.empty_state.setObjectName("predictionDetailEmptyState")
        self.empty_state.setWordWrap(True)

        self.detail_error = QLabel("", self)
        self.detail_error.setObjectName("predictionDetailError")
        self.detail_error.setTextFormat(Qt.TextFormat.PlainText)
        self.detail_error.setWordWrap(True)
        self.detail_error.setHidden(True)
        apply_message_role(
            self.detail_error,
            StatusTone.ERROR,
            accessible_name="Prediction Detail error",
        )

        self.detail_content = QWidget(self)
        self.detail_content.setObjectName("predictionDetailContent")
        detail_layout = QVBoxLayout(self.detail_content)
        detail_layout.setContentsMargins(4, 4, 12, 4)

        self.question = QLabel("", self.detail_content)
        self.question.setObjectName("predictionDetailQuestion")
        self.question.setWordWrap(True)
        self.question.setTextFormat(Qt.TextFormat.PlainText)
        _make_selectable(self.question)
        apply_text_role(self.question, TextRole.PAGE_TITLE)

        self.forecast_type = StatusBadge(
            "BINARY",
            StatusTone.NEUTRAL,
            parent=self.detail_content,
        )
        self.forecast_type.setObjectName("predictionDetailType")

        self.status = QLabel("", self.detail_content)
        self.status.setObjectName("predictionDetailStatus")
        self.status.setAccessibleName("Prediction status")
        apply_badge_role(self.status)

        self.tags = QLabel("", self.detail_content)
        self.tags.setObjectName("predictionDetailTags")
        self.tags.setWordWrap(True)
        self.tags.setTextFormat(Qt.TextFormat.PlainText)
        _make_selectable(self.tags)
        apply_text_role(self.tags, TextRole.SECONDARY)

        current_forecast_label = QLabel("Current Forecast", self.detail_content)
        current_forecast_label.setObjectName("currentForecastLabel")
        apply_text_role(current_forecast_label, TextRole.LABEL)
        self.probability = QLabel("", self.detail_content)
        self.probability.setObjectName("predictionDetailProbability")
        self.probability.setAccessibleName("Current probability")
        _make_selectable(self.probability)
        apply_text_role(self.probability, TextRole.FORECAST)

        self.edit_details_button = QPushButton("Edit Details", self.detail_content)
        self.edit_details_button.setObjectName("editPredictionDetailsButton")
        apply_action_role(self.edit_details_button, ActionRole.SECONDARY)
        apply_lucide_icon(self.edit_details_button, LucideIcon.PENCIL)
        self.edit_details_button.clicked.connect(self.open_edit_details)

        action_row = QWidget(self.detail_content)
        action_row.setObjectName("futurePredictionActions")
        action_layout = QGridLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setHorizontalSpacing(int(Spacing.CONTROL))
        action_layout.setVerticalSpacing(int(Spacing.CONTROL))
        self.revise_forecast_button = QPushButton("Revise Forecast", action_row)
        self.revise_forecast_button.setObjectName("reviseForecastButton")
        apply_action_role(self.revise_forecast_button, ActionRole.PRIMARY)
        apply_lucide_icon(self.revise_forecast_button, LucideIcon.REFRESH)
        self.revise_forecast_button.clicked.connect(self.open_revise_forecast)
        self.add_journal_entry_button = QPushButton(
            "Add Journal Entry",
            action_row,
        )
        self.add_journal_entry_button.setObjectName("addJournalEntryButton")
        apply_action_role(self.add_journal_entry_button, ActionRole.SECONDARY)
        apply_lucide_icon(self.add_journal_entry_button, LucideIcon.NOTEBOOK_PEN)
        self.add_journal_entry_button.clicked.connect(self.open_add_journal_entry)
        self.review_forecast_button = QPushButton("Still at", action_row)
        self.review_forecast_button.setObjectName("reviewForecastButton")
        apply_action_role(self.review_forecast_button, ActionRole.SECONDARY)
        self.review_forecast_button.setAccessibleName(
            "Record a Review retaining this probability"
        )
        apply_lucide_icon(self.review_forecast_button, LucideIcon.CIRCLE_CHECK)
        self.review_forecast_button.clicked.connect(self.open_forecast_review)
        self.resolve_button = QPushButton("Resolve", action_row)
        self.resolve_button.setObjectName("resolvePredictionButton")
        apply_action_role(self.resolve_button, ActionRole.SECONDARY)
        apply_lucide_icon(self.resolve_button, LucideIcon.CIRCLE_CHECK)
        self.resolve_button.clicked.connect(self.open_resolve_prediction)
        self.mark_invalid_button = QPushButton("Mark Invalid", action_row)
        self.mark_invalid_button.setObjectName("markInvalidButton")
        apply_action_role(self.mark_invalid_button, ActionRole.CAUTION)
        apply_lucide_icon(self.mark_invalid_button, LucideIcon.BAN)
        self.mark_invalid_button.clicked.connect(self.open_mark_invalid)
        self.delete_button = QPushButton("Delete", action_row)
        self.delete_button.setObjectName("deletePredictionButton")
        apply_action_role(self.delete_button, ActionRole.DESTRUCTIVE)
        apply_lucide_icon(self.delete_button, LucideIcon.TRASH)
        self.delete_button.clicked.connect(self.delete_prediction)
        _configure_detail_action_grid(
            action_layout,
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
        action_layout.addWidget(self.add_journal_entry_button, 0, 1)
        action_layout.addWidget(self.revise_forecast_button, 0, 2)
        action_layout.addWidget(self.review_forecast_button, 0, 3)
        action_layout.addWidget(self.edit_details_button, 1, 1)
        action_layout.addWidget(self.resolve_button, 1, 2)
        action_layout.addWidget(self.mark_invalid_button, 1, 3)
        action_layout.addWidget(self.delete_button, 2, 2)

        self.forecast_deadline_row, self.forecast_deadline = _detail_value_row(
            "Forecast deadline",
            "predictionDetailForecastDeadlineRow",
            "predictionDetailForecastDeadline",
            self.detail_content,
            stacked=True,
        )
        self.expected_resolution_row, self.expected_resolution = _detail_value_row(
            "Expected resolution",
            "predictionDetailExpectedResolutionRow",
            "predictionDetailExpectedResolution",
            self.detail_content,
        )
        self.background_section, self.background = _detail_text_section(
            "Background",
            "predictionDetailBackgroundSection",
            "predictionDetailBackground",
            self.detail_content,
        )
        self.resolution_criteria_section, self.resolution_criteria = (
            _detail_text_section(
                "Resolution Criteria",
                "predictionDetailResolutionCriteriaSection",
                "predictionDetailResolutionCriteria",
                self.detail_content,
            )
        )

        self.resolution_section = QGroupBox("Resolution", self.detail_content)
        self.resolution_section.setObjectName("predictionResolutionSection")
        apply_surface_role(self.resolution_section, SurfaceRole.RAISED)
        resolution_layout = QVBoxLayout(self.resolution_section)
        self.resolution_outcome = QLabel("", self.resolution_section)
        self.resolution_outcome.setObjectName("predictionResolutionOutcome")
        self.resolution_outcome.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_resolved_at = QLabel("", self.resolution_section)
        self.resolution_resolved_at.setObjectName("predictionResolvedAt")
        self.resolution_resolved_at.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_scoring_forecast = QLabel("", self.resolution_section)
        self.resolution_scoring_forecast.setObjectName(
            "predictionResolutionScoringForecast"
        )
        self.resolution_scoring_forecast.setTextFormat(Qt.TextFormat.PlainText)
        self.scorecard_section = QGroupBox("Scorecard", self.resolution_section)
        self.scorecard_section.setObjectName("predictionScorecard")
        apply_surface_role(self.scorecard_section, SurfaceRole.BASE)
        scorecard_layout = QVBoxLayout(self.scorecard_section)
        self.scorecard_forecast = QLabel("", self.scorecard_section)
        self.scorecard_forecast.setObjectName("predictionScorecardForecast")
        self.scorecard_forecast.setTextFormat(Qt.TextFormat.PlainText)
        self.scorecard_outcome = QLabel("", self.scorecard_section)
        self.scorecard_outcome.setObjectName("predictionScorecardOutcome")
        self.scorecard_outcome.setTextFormat(Qt.TextFormat.PlainText)
        self.scorecard_brier = QLabel("", self.scorecard_section)
        self.scorecard_brier.setObjectName("predictionScorecardBrier")
        self.scorecard_brier.setTextFormat(Qt.TextFormat.PlainText)
        self.scorecard_guidance = QLabel(
            "Brier score: lower is better.",
            self.scorecard_section,
        )
        self.scorecard_guidance.setObjectName("predictionScorecardGuidance")
        self.scorecard_guidance.setTextFormat(Qt.TextFormat.PlainText)
        self.scorecard_correction_notice = QLabel("", self.scorecard_section)
        self.scorecard_correction_notice.setObjectName(
            "predictionScorecardCorrectionNotice"
        )
        self.scorecard_correction_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.scorecard_correction_notice.setWordWrap(True)
        scorecard_layout.addWidget(self.scorecard_forecast)
        scorecard_layout.addWidget(self.scorecard_outcome)
        scorecard_layout.addWidget(self.scorecard_brier)
        scorecard_layout.addWidget(self.scorecard_guidance)
        scorecard_layout.addWidget(self.scorecard_correction_notice)
        self.trajectory_diagnostics = _collapsible_history_group(
            "Score details", "trajectoryDiagnostics", self.scorecard_section
        )
        self.trajectory_diagnostics.setTitle("Score details")
        self.trajectory_diagnostics.setHidden(True)
        scorecard_layout.addWidget(self.trajectory_diagnostics)
        self.resolution_notes_heading = QLabel(
            "Resolution Notes",
            self.resolution_section,
        )
        self.resolution_notes_heading.setObjectName("predictionResolutionNotesHeading")
        self.resolution_notes = QLabel("", self.resolution_section)
        self.resolution_notes.setObjectName("predictionResolutionNotes")
        self.resolution_notes.setTextFormat(Qt.TextFormat.PlainText)
        self.resolution_notes.setWordWrap(True)
        _make_selectable(self.resolution_notes)
        self.postmortem_heading = QLabel("Postmortem", self.resolution_section)
        self.postmortem_heading.setObjectName("predictionPostmortemHeading")
        self.postmortem = QLabel("", self.resolution_section)
        self.postmortem.setObjectName("predictionPostmortem")
        self.postmortem.setTextFormat(Qt.TextFormat.PlainText)
        self.postmortem.setWordWrap(True)
        _make_selectable(self.postmortem)
        self.postmortem_completion = QLabel("", self.resolution_section)
        self.postmortem_completion.setObjectName("predictionPostmortemCompletion")
        self.skip_postmortem_button = PostmortemSkipButton(
            lambda identifier, **context: self._operations.record_postmortem_skip(
                identifier, **context
            ),
            self.refresh,
            self._show_error,
            self.resolution_section,
        )
        self.skip_postmortem_button.setObjectName("skipPostmortemButton")
        self.postmortem_completion.setTextFormat(Qt.TextFormat.PlainText)
        self.postmortem_completion.setWordWrap(True)
        _make_selectable(self.postmortem_completion)
        self.correct_resolution_button = QPushButton(
            "Correct Resolution",
            self.resolution_section,
        )
        self.correct_resolution_button.setObjectName("correctResolutionButton")
        self.correct_resolution_button.setAccessibleName(
            "Correct Binary Resolution or Postmortem"
        )
        self.correct_resolution_button.setToolTip(
            "Correct the outcome or notes, or add or correct the Postmortem. "
            "The original Resolution remains in history."
        )
        apply_lucide_icon(self.correct_resolution_button, LucideIcon.PENCIL)
        self.resolution_history = _collapsible_history_group(
            "Resolution correction history",
            "resolutionCorrectionHistory",
            self.resolution_section,
        )
        resolution_layout.addWidget(self.resolution_outcome)
        resolution_layout.addWidget(self.resolution_resolved_at)
        resolution_layout.addWidget(self.resolution_scoring_forecast)
        resolution_layout.addWidget(self.scorecard_section)
        resolution_layout.addWidget(self.resolution_notes_heading)
        resolution_layout.addWidget(self.resolution_notes)
        resolution_layout.addWidget(self.postmortem_heading)
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
        self.scorecard_section.setHidden(True)
        self.postmortem_completion.setHidden(True)

        self.invalidation_section = QGroupBox("Invalid", self.detail_content)
        self.invalidation_section.setObjectName("predictionInvalidationSection")
        apply_surface_role(self.invalidation_section, SurfaceRole.RAISED)
        invalidation_layout = QVBoxLayout(self.invalidation_section)
        self.invalidated_at = QLabel("", self.invalidation_section)
        self.invalidated_at.setObjectName("predictionInvalidatedAt")
        self.invalidated_at.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason_heading = QLabel(
            "Reason",
            self.invalidation_section,
        )
        self.invalidation_reason_heading.setObjectName(
            "predictionInvalidationReasonHeading"
        )
        self.invalidation_reason = QLabel("", self.invalidation_section)
        self.invalidation_reason.setObjectName("predictionInvalidationReason")
        self.invalidation_reason.setTextFormat(Qt.TextFormat.PlainText)
        self.invalidation_reason.setWordWrap(True)
        _make_selectable(self.invalidation_reason)
        self.correct_invalidation_button = QPushButton(
            "Correct Reason",
            self.invalidation_section,
        )
        self.correct_invalidation_button.setObjectName(
            "correctInvalidationReasonButton"
        )
        self.correct_invalidation_button.setToolTip(
            "Append a correction while preserving the original Invalid reason."
        )
        apply_lucide_icon(self.correct_invalidation_button, LucideIcon.PENCIL)
        self.invalidation_history = _collapsible_history_group(
            "Invalidation correction history",
            "invalidationCorrectionHistory",
            self.invalidation_section,
        )
        invalidation_layout.addWidget(self.invalidated_at)
        invalidation_layout.addWidget(self.invalidation_reason_heading)
        invalidation_layout.addWidget(self.invalidation_reason)
        invalidation_layout.addWidget(
            self.correct_invalidation_button,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        invalidation_layout.addWidget(self.invalidation_history)
        self.invalidation_section.setHidden(True)

        self.definition_history = QGroupBox("Definition History", self.detail_content)
        self.definition_history.setObjectName("definitionHistoryGroup")
        apply_surface_role(self.definition_history, SurfaceRole.BASE)
        self.definition_history.setCheckable(True)
        self.definition_history.setChecked(False)
        self.definition_history_content = QWidget(self.definition_history)
        self.definition_history_content.setObjectName("definitionHistoryContent")
        self.definition_history_layout = QVBoxLayout(self.definition_history_content)
        history_group_layout = QVBoxLayout(self.definition_history)
        history_group_layout.addWidget(self.definition_history_content)
        self.definition_history.toggled.connect(
            self.definition_history_content.setVisible
        )
        self.definition_history_content.setHidden(True)

        timeline_label = QLabel("TIMELINE", self.detail_content)
        timeline_label.setObjectName("timelineHeading")
        self.forecast_timeline = QWidget(self.detail_content)
        self.forecast_timeline.setObjectName("forecastTimeline")
        self.forecast_timeline_layout = QVBoxLayout(self.forecast_timeline)
        self.forecast_timeline_layout.setContentsMargins(0, 0, 0, 0)
        self.timeline_placeholder = QLabel(
            "No forecast revisions are available.",
            self.detail_content,
        )
        self.timeline_placeholder.setObjectName("timelinePlaceholder")
        self.timeline_placeholder.setWordWrap(True)

        chart_label = QLabel("Probability History", self.detail_content)
        chart_label.setObjectName("probabilityHistoryHeading")
        self.probability_history_chart = ProbabilityHistoryChart(self.detail_content)
        chart_policy = self.probability_history_chart.sizePolicy()
        chart_policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
        self.probability_history_chart.setSizePolicy(chart_policy)
        self.probability_history_chart.setObjectName("probabilityHistoryChart")
        self.probability_history_chart.setHidden(True)
        self.chart_placeholder = QLabel(
            "No forecast revisions are available to chart.",
            self.detail_content,
        )
        self.chart_placeholder.setObjectName("probabilityHistoryPlaceholder")
        self.chart_placeholder.setTextFormat(Qt.TextFormat.PlainText)
        self.chart_placeholder.setWordWrap(True)
        self.chart_placeholder.setHidden(True)

        summary_panel, summary_layout = _detail_panel(
            "predictionDetailSummaryPanel",
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
        summary_layout.addWidget(current_forecast_label)
        summary_layout.addWidget(self.probability)

        action_panel, action_panel_layout = _detail_panel(
            "predictionDetailActionPanel",
            self.detail_content,
        )
        action_heading = QLabel("Forecast actions", action_panel)
        action_heading.setObjectName("predictionDetailActionHeading")
        apply_text_role(action_heading, TextRole.SECTION_TITLE)
        action_help = QLabel(
            "Revise or reconsider the forecast, record reasoning, edit details, "
            "or finish its lifecycle.",
            action_panel,
        )
        action_help.setObjectName("predictionDetailActionHelp")
        action_help.setWordWrap(True)
        action_help.setContentsMargins(0, 0, 0, int(Spacing.CONTROL))
        apply_text_role(action_help, TextRole.LABEL)
        action_panel_layout.addWidget(action_heading)
        action_panel_layout.addWidget(action_help)
        action_panel_layout.addWidget(action_row)

        self.metadata_panel, metadata_layout = _detail_panel(
            "predictionDetailMetadataPanel",
            self.detail_content,
        )
        self.metadata_empty = QLabel(
            "No additional information recorded.", self.metadata_panel
        )
        self.metadata_empty.setObjectName("binaryMetadataEmptyMessage")
        self.metadata_empty.setWordWrap(True)
        _make_selectable(self.metadata_empty)
        apply_text_role(self.metadata_empty, TextRole.SECONDARY)
        metadata_layout.addWidget(self.metadata_empty)
        metadata_layout.addWidget(self.forecast_deadline_row)
        metadata_layout.addWidget(self.expected_resolution_row)
        metadata_layout.addWidget(self.background_section)
        metadata_layout.addWidget(self.resolution_criteria_section)
        metadata_layout.addWidget(self.definition_history)

        timeline_panel, timeline_panel_layout = _detail_panel(
            "predictionDetailTimelinePanel",
            self.detail_content,
        )
        apply_text_role(timeline_label, TextRole.SECTION_TITLE)
        timeline_panel_layout.addWidget(timeline_label)
        timeline_panel_layout.addWidget(self.forecast_timeline)
        timeline_panel_layout.addWidget(self.timeline_placeholder)

        chart_panel, chart_panel_layout = _detail_panel(
            "predictionDetailHistoryPanel",
            self.detail_content,
        )
        apply_text_role(chart_label, TextRole.SECTION_TITLE)
        chart_panel_layout.addWidget(chart_label)
        chart_panel_layout.addWidget(self.probability_history_chart)
        self.contract_context = QLabel(self.detail_content)
        self.contract_context.setObjectName("binaryContractContext")
        self.contract_context.setWordWrap(True)
        self.contract_context.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        chart_panel_layout.addWidget(self.contract_context)
        chart_panel_layout.addWidget(self.chart_placeholder)
        apply_surface_role(chart_panel, SurfaceRole.CANVAS)

        self._page_header = header
        header.hide()
        apply_text_role(self.question, TextRole.QUESTION)
        current_forecast_label.setText("Current committed forecast")
        summary_layout.removeWidget(current_forecast_label)
        current_forecast_label.hide()
        self.header_timing = HeaderTiming(
            self.forecast_deadline_row, summary_panel, "Current committed forecast"
        )
        summary_layout.addWidget(self.header_timing)
        self.terminal_summary = TerminalSummary(summary_panel)
        summary_layout.addWidget(self.terminal_summary)
        action_heading.hide()
        action_help.hide()
        old_actions = action_row.layout()
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
        action_row.hide()
        action_panel_layout.addWidget(self.action_strip)
        self.timeline_order = QComboBox(timeline_panel)
        self.timeline_order.setAccessibleName("Timeline reading order")
        self.timeline_order.addItems(["Newest first", "Oldest first"])
        self.timeline_rows = TimelineRows(self.forecast_timeline_layout)
        self.timeline_order.currentIndexChanged.connect(
            lambda index: self.timeline_rows.order(descending=index == 0)
        )
        heading = timeline_panel_layout.takeAt(0).widget()
        self.scroll_area = DetailWorkspace(self.detail_content, self)
        self.scroll_area.setObjectName("predictionDetailScrollArea")
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
        self.chart_disclosure = collapse_section(
            chart_panel, "Probability History", compact=True
        )
        self.metadata_disclosure = collapse_section(
            self.metadata_panel, "More Information", compact=True
        )
        overview = [
            self.resolution_criteria_section,
            self.scorecard_section,
            self.chart_disclosure,
            self.metadata_disclosure,
        ]
        self.reading_sections = AdaptiveReadingSections(
            self.resolution_notes,
            self.postmortem,
            self.postmortem_completion,
            self.detail_content,
        )
        overview[1:1] = [
            self.reading_sections.notes,
            self.reading_sections.reflection,
            self.resolution_history,
            self.invalidation_history,
        ]
        self.scorecard_section.setTitle("Binary score details")
        apply_surface_role(self.scorecard_section, SurfaceRole.CANVAS)
        self.trajectory_diagnostics.setTitle("Timing and updating diagnostics")
        apply_action_role(self.write_postmortem_button, ActionRole.SECONDARY)
        for label in (
            self.scorecard_forecast,
            self.scorecard_outcome,
            self.scorecard_brier,
            self.scorecard_correction_notice,
        ):
            label.hide()
        self.scored_forecast_disclosure = collapse_section(
            self.resolution_scoring_forecast, "Scored Forecast Context", compact=True
        )
        self.resolution_section.layout().removeWidget(self.resolution_scoring_forecast)
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

        self.correct_resolution_button.clicked.connect(self.open_correct_resolution)
        self.correct_invalidation_button.clicked.connect(
            self.open_correct_invalidation_reason
        )

        self.show_prediction(self._operations.get_latest_prediction())

    @property
    def prediction_id(self) -> int | None:
        """Return the identifier currently presented by the screen."""
        return None if self._prediction is None else self._prediction.prediction_id

    def focus_search_match(self, document: SearchDocument) -> None:
        """Reveal and briefly emphasize a matching Binary canonical context."""

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
                    f"forecastRevision{document.source_record_id}",
                )
                or self.forecast_timeline
            )
        elif document.source_kind is SearchSourceKind.FORECAST_REVIEW:
            target = (
                self.findChild(
                    QWidget, f"forecastReviewNote{document.source_record_id}"
                )
                or self.findChild(QWidget, f"forecastReview{document.source_record_id}")
                or self.forecast_timeline
            )
        elif document.source_kind is SearchSourceKind.JOURNAL:
            target = (
                self.findChild(QWidget, f"journalEntry{document.source_record_id}")
                or self.forecast_timeline
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
                        QWidget, f"journalEntryBody{document.source_record_id}"
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
    def show_prediction(self, prediction: PredictionSnapshot | None) -> None:
        """Present a prediction or the new-database empty state."""
        self.skip_postmortem_button.set_context(None)
        self._prediction = prediction
        self._hide_error()
        if prediction is None:
            self.timeline_rows.clear()
            self.question.clear()
            self.status.clear()
            self.probability.clear()
            self.tags.clear()
            self.probability_history_chart.clear()
            self.probability_history_chart.set_timeline_available(True)
            self.probability_history_chart.setHidden(True)
            self.review_forecast_button.setEnabled(False)
            self.chart_placeholder.setText(
                "No forecast revisions are available to chart."
            )
            self.chart_placeholder.setHidden(True)
            self._chart_prediction_id = None
            self.detail_content.setHidden(True)
            self.empty_state.setHidden(False)
            self.definition_history.setHidden(True)
            self.correct_resolution_button.setEnabled(False)
            self.correct_invalidation_button.setEnabled(False)
            self._resolution_history = None
            self._invalidation_history = None
            self.resolution_section.setHidden(True)
            self.scorecard_section.setHidden(True)
            self.invalidation_section.setHidden(True)
            return

        self.question.setText(prediction.question)
        self.status.setText(prediction.status.value.upper())
        apply_badge_role(self.status, _status_tone(prediction.status))
        self.probability.setText(f"{prediction.probability_percent}%")
        self.review_forecast_button.setText(
            f"Still at {prediction.probability_percent}%"
        )
        self.review_forecast_button.setEnabled(
            prediction.status is PredictionStatus.OPEN
        )
        self.review_forecast_button.setToolTip(
            "Record deliberate reconsideration while keeping this probability."
            if prediction.status is PredictionStatus.OPEN
            else "Forecast Reviews can be recorded only while Open."
        )
        revision_allowed = prediction.status is PredictionStatus.OPEN
        self.revise_forecast_button.setEnabled(revision_allowed)
        if revision_allowed:
            self.revise_forecast_button.setToolTip(
                "Append a new probability while preserving this forecast."
            )
        else:
            self.revise_forecast_button.setToolTip(
                f"Forecast revisions are not allowed while this prediction is "
                f"{prediction.status.value}."
            )
        journal_allowed = prediction.status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        )
        self.add_journal_entry_button.setEnabled(journal_allowed)
        if journal_allowed:
            self.add_journal_entry_button.setToolTip(
                "Record evidence or reasoning without changing the forecast."
            )
        else:
            self.add_journal_entry_button.setToolTip(
                f"New Journal entries are not allowed while this prediction is "
                f"{prediction.status.value}. Existing entries can still be corrected."
            )
        terminal_action_allowed = prediction.status in (
            PredictionStatus.OPEN,
            PredictionStatus.LOCKED,
        )
        self.resolve_button.setEnabled(terminal_action_allowed)
        self.mark_invalid_button.setEnabled(terminal_action_allowed)
        if terminal_action_allowed:
            self.resolve_button.setToolTip(
                "Record a final Yes or No outcome and capture the scoring forecast."
            )
            self.mark_invalid_button.setToolTip(
                "Preserve this prediction but exclude it from scoring."
            )
        else:
            terminal_tooltip = (
                f"This prediction is already {prediction.status.value}; terminal "
                "decisions cannot be changed in v0.1."
            )
            self.resolve_button.setToolTip(terminal_tooltip)
            self.mark_invalid_button.setToolTip(terminal_tooltip)
        delete_allowed = (
            prediction.status is PredictionStatus.OPEN and prediction.deletion_allowed
        )
        self.delete_button.setEnabled(delete_allowed)
        if delete_allowed:
            self.delete_button.setToolTip(
                "Permanently delete this untouched Open prediction."
            )
        elif prediction.status is PredictionStatus.LOCKED:
            self.delete_button.setToolTip(
                "Locked predictions are preserved. Use Mark Invalid when appropriate."
            )
        elif prediction.status in (
            PredictionStatus.RESOLVED,
            PredictionStatus.INVALID,
        ):
            self.delete_button.setToolTip(
                "Terminal prediction history cannot be deleted from the normal "
                "interface."
            )
        else:
            self.delete_button.setToolTip(
                "Predictions with meaningful history are preserved. Use Mark Invalid "
                "when appropriate."
            )
        self.tags.setText("  ".join(f"#{tag}" for tag in prediction.tags))
        self.tags.setHidden(not prediction.tags)
        self._show_optional_metadata(prediction)
        self._show_terminal_information(prediction)
        self._sync_reading_actions(prediction)
        self.empty_state.setHidden(True)
        self.detail_content.setHidden(False)
        self._load_definition_history(prediction.prediction_id)
        timeline_available = self._load_timeline(prediction.prediction_id)
        self.probability_history_chart.set_timeline_available(timeline_available)
        self._load_probability_history(prediction.prediction_id)

    def refresh(self) -> None:
        """Reload the displayed prediction while retaining data on a read failure."""
        try:
            if self._prediction is None:
                prediction = self._operations.get_latest_prediction()
            else:
                prediction = self._operations.get_prediction(
                    self._prediction.prediction_id
                )
        except ApplicationError as error:
            self._show_error(f"Prediction Detail could not be refreshed. {error}")
            return
        self.show_prediction(prediction)

    def open_edit_details(self) -> None:
        """Open a prefilled metadata dialog without mutating on open or cancel."""
        if not self.workspace.prepare_task("Edit Details"):
            return
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        dialog = EditPredictionDetailsDialog(
            self._operations,
            prediction,
            self,
        )
        self._edit_dialog = dialog
        dialog.metadata_saved.connect(self.show_prediction)
        dialog.finished.connect(self._edit_dialog_finished)
        dialog.open()

    def open_revise_forecast(self) -> None:
        """Refresh eligibility, then open a side-effect-free revision dialog."""
        if not self.workspace.prepare_task("Revision"):
            return
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status is not PredictionStatus.OPEN:
            self._show_error(
                f"Forecast revisions are not allowed while this prediction is "
                f"{prediction.status.value}."
            )
            return
        dialog = ReviseForecastDialog(self._operations, prediction, self)
        self._revision_dialog = dialog
        dialog.revision_saved.connect(self.show_prediction)
        dialog.finished.connect(self._revision_dialog_finished)
        self._start_editor(dialog, "Revision")

    def open_add_journal_entry(self) -> None:
        """Refresh context, then open a side-effect-free Journal dialog."""
        if not self.workspace.prepare_task("Journal"):
            return
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            self._show_error(
                f"New Journal entries are not allowed while this prediction is "
                f"{prediction.status.value}."
            )
            return
        dialog = AddJournalEntryDialog(self._operations, prediction, self)
        self._journal_dialog = dialog
        dialog.journal_saved.connect(self._journal_saved)
        dialog.finished.connect(self._journal_dialog_finished)
        self._start_editor(dialog, "Journal")

    def open_forecast_review(self) -> None:
        """Refresh, then offer a side-effect-free Open-only Review dialog."""
        if not self.workspace.prepare_task("Review"):
            return

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status is not PredictionStatus.OPEN:
            self._show_error("Forecast Reviews can be recorded only while Open.")
            return
        dialog = ForecastReviewDialog(self._operations, prediction, self)
        dialog.review_saved.connect(self._review_saved)
        self._start_editor(dialog, "Review")

    def open_resolve_prediction(self) -> None:
        """Refresh reviewed context before opening the terminal resolution form."""
        if not self.workspace.prepare_task("Resolve"):
            return

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            self._show_error(
                f"This prediction is already {prediction.status.value} and cannot "
                "be resolved again."
            )
            return
        dialog = ResolvePredictionDialog(self._operations, prediction, self)
        self._resolution_dialog = dialog
        dialog.prediction_resolved.connect(self.show_prediction)
        dialog.finished.connect(self._resolution_dialog_finished)
        self._start_editor(dialog, "Resolve")

    def open_mark_invalid(self) -> None:
        """Refresh reviewed context before opening the terminal Invalid form."""
        if not self.workspace.prepare_task("Mark Invalid"):
            return

        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if prediction.status not in (PredictionStatus.OPEN, PredictionStatus.LOCKED):
            self._show_error(
                f"This prediction is already {prediction.status.value} and cannot "
                "be marked Invalid again."
            )
            return
        dialog = MarkInvalidDialog(self._operations, prediction, self)
        self._invalidation_dialog = dialog
        dialog.prediction_invalidated.connect(self.show_prediction)
        dialog.finished.connect(self._invalidation_dialog_finished)
        self._start_editor(dialog, "Mark Invalid")

    def open_correct_resolution(self) -> None:
        """Refresh, then correct the effective Binary Resolution append-only."""

        if not self.workspace.prepare_task("Correct Resolution"):
            return
        if self._prediction is None:
            return
        self.refresh()
        history = self._resolution_history
        if history is None:
            return
        dialog = CorrectBinaryResolutionDialog(self._operations, history, self)
        self._terminal_correction_dialog = dialog
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.finished.connect(self._terminal_correction_dialog_finished)
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
        self._terminal_correction_dialog = dialog
        dialog.correction_saved.connect(lambda _history: self.refresh())
        dialog.finished.connect(self._terminal_correction_dialog_finished)
        dialog.open()

    def delete_prediction(self) -> None:
        """Confirm and permanently delete only refreshed untouched Open state."""

        if not self.workspace.prepare_task("Delete"):
            return
        if self._prediction is None:
            return
        try:
            prediction = self._operations.get_prediction(self._prediction.prediction_id)
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(prediction)
        if (
            not prediction.deletion_allowed
            or prediction.status is not PredictionStatus.OPEN
        ):
            self._show_error(
                "Only an untouched Open prediction can be deleted. Use Mark Invalid "
                "to preserve meaningful history outside scoring."
            )
            return
        answer = QMessageBox.warning(
            self,
            "Permanently delete prediction?",
            "This permanently deletes the prediction and its initial forecast. "
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            latest = self._operations.delete_prediction(
                prediction.prediction_id,
                expected_revision_id=prediction.current_revision_id,
                expected_metadata_version=prediction.metadata_version,
                confirm_permanent_deletion=True,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.show_prediction(latest)

    def open_correct_journal_entry(self, entry: JournalTimelineSnapshot) -> None:
        """Refresh the Journal entry before opening its correction form."""
        if not self.workspace.prepare_task("Correct Journal"):
            return
        try:
            events = self._operations.list_timeline(entry.prediction_id)
        except ApplicationError as error:
            self._show_error(f"Journal entry could not be refreshed. {error}")
            return
        current_entry = next(
            (
                event
                for event in events
                if hasattr(event, "entry_id") and event.entry_id == entry.entry_id
            ),
            None,
        )
        if current_entry is None:
            self._show_error(
                "This Journal entry could not be found. Refresh Prediction Detail "
                "and try again."
            )
            return
        self._hide_error()
        dialog = CorrectJournalEntryDialog(self._operations, current_entry, self)
        self._journal_correction_dialog = dialog
        dialog.correction_saved.connect(self._journal_correction_saved)
        dialog.finished.connect(self._journal_correction_dialog_finished)
        self._start_editor(dialog, "Correct Journal")

    def _edit_dialog_finished(self, _result: int) -> None:
        self._edit_dialog = None

    def _revision_dialog_finished(self, _result: int) -> None:
        self._revision_dialog = None

    def _journal_dialog_finished(self, _result: int) -> None:
        self._journal_dialog = None

    def _journal_correction_dialog_finished(self, _result: int) -> None:
        self._journal_correction_dialog = None

    def _resolution_dialog_finished(self, _result: int) -> None:
        self._resolution_dialog = None

    def _invalidation_dialog_finished(self, _result: int) -> None:
        self._invalidation_dialog = None

    def _terminal_correction_dialog_finished(self, _result: int) -> None:
        self._terminal_correction_dialog = None

    def _journal_saved(self, _result: object) -> None:
        if self._prediction is not None:
            self.show_prediction(self._prediction)

    def _review_saved(self, _result: object) -> None:
        if self._prediction is not None:
            self.refresh()

    def _journal_correction_saved(self, _corrected: object) -> None:
        if self._prediction is None:
            return
        self.show_prediction(self._prediction)

    def _show_optional_metadata(self, prediction: PredictionSnapshot) -> None:
        contract = getattr(prediction, "forecast_contract", None)
        assert contract is not None and contract.forecast_deadline is not None
        self.forecast_type.setText("Adaptive · Binary")
        self.contract_context.setText(
            "Trajectory Binary: each standing probability belongs to the initial-to-Deadline "
            "commitment. Scoring uses when the outcome became knowable. "
            "This is probability history, not a score plot."
        )
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
        self.metadata_panel.show()

    def _show_terminal_information(self, prediction: PredictionSnapshot) -> None:
        """Render latest effective facts plus inspectable append-only history."""

        self._excluded_scoring_revision_ids: frozenset[int] = frozenset()
        self._trajectory_score: TrajectoryScorecard | None = None
        resolution = prediction.resolution
        self.resolution_section.setHidden(resolution is None)
        if resolution is not None:
            try:
                history = self._operations.get_binary_resolution_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                self._resolution_history = None
                effective = resolution
                completion = None
                self.correct_resolution_button.setEnabled(False)
                self.resolution_history.setHidden(True)
                self._show_error(f"Resolution history is unavailable. {error}")
            else:
                effective = history.effective
                completion = history.postmortem_completion
                self._resolution_history = history
                self.correct_resolution_button.setEnabled(True)
                _show_binary_resolution_correction_history(
                    self.resolution_history,
                    history,
                )
                self.skip_postmortem_button.set_context(history)
            self.resolution_outcome.setText(
                f"Outcome: {effective.outcome.value.capitalize()}"
            )
            self.resolution_resolved_at.setText(
                f"Recorded at: {exact_detail_time(resolution.resolved_at, widget=self)}"
                if effective.effective_resolution_at is None
                else f"Outcome became knowable: {exact_detail_time(effective.effective_resolution_at, widget=self)}\nRecorded at: {exact_detail_time(resolution.resolved_at, widget=self)}"
            )
            self.resolution_resolved_at.setToolTip(
                "Recorded at: "
                + resolution.resolved_at.isoformat()
                + (
                    "\nOutcome became knowable: "
                    + effective.effective_resolution_at.isoformat()
                    if effective.effective_resolution_at is not None
                    else ""
                )
            )
            self.resolution_scoring_forecast.setText(
                f"Scoring forecast: {resolution.scoring_probability_percent}% "
                f"(revision {resolution.scoring_revision_sequence})"
            )
            self.resolution_scoring_forecast.setHidden(
                effective.effective_resolution_at is not None
            )
            self.resolution_notes.setText(effective.resolution_notes or "")
            has_notes = effective.resolution_notes is not None
            self.resolution_notes_heading.setHidden(not has_notes)
            self.resolution_notes.setHidden(not has_notes)
            self.postmortem.setText(effective.postmortem or "")
            has_postmortem = effective.postmortem is not None
            self.postmortem_heading.setHidden(not has_postmortem)
            self.postmortem.setHidden(not has_postmortem)
            self.postmortem_completion.setText(
                ""
                if completion is None
                else "Postmortem completion: Skipped "
                f"{_format_local_timestamp(completion.completed_at, widget=self)}. You may still "
                "add a Postmortem later; this completion remains in history."
            )
            self.postmortem_completion.setHidden(completion is None)
            self._show_scorecard(prediction.prediction_id)
        else:
            self._resolution_history = None
            self.correct_resolution_button.setEnabled(False)
            self.resolution_history.setHidden(True)
            self.scorecard_section.setHidden(True)

        invalidation = prediction.invalidation
        self.invalidation_section.setHidden(invalidation is None)
        if invalidation is not None:
            try:
                history = self._operations.get_invalidation_history(
                    prediction.prediction_id
                )
            except ApplicationError as error:
                self._invalidation_history = None
                effective_invalidation = invalidation
                self.correct_invalidation_button.setEnabled(False)
                self.invalidation_history.setHidden(True)
                self._show_error(f"Invalidation history is unavailable. {error}")
            else:
                effective_invalidation = history.effective
                self._invalidation_history = history
                self.correct_invalidation_button.setEnabled(True)
                _show_invalidation_correction_history(
                    self.invalidation_history,
                    history,
                )
            self.invalidated_at.setText(
                f"Marked Invalid: "
                f"{_format_local_timestamp(invalidation.invalidated_at, widget=self)}"
            )
            self.invalidation_reason.setText(effective_invalidation.reason or "")
            has_reason = effective_invalidation.reason is not None
            self.invalidation_reason_heading.setHidden(not has_reason)
            self.invalidation_reason.setHidden(not has_reason)
        else:
            self._invalidation_history = None
            self.correct_invalidation_button.setEnabled(False)
            self.invalidation_history.setHidden(True)

    def _show_scorecard(self, prediction_id: int) -> None:
        try:
            scorecard = self._operations.get_prediction_scorecard(prediction_id)
        except ApplicationError as error:
            self.scorecard_section.setHidden(True)
            self._show_error(f"Scorecard is unavailable. {error}")
            return
        self.trajectory_diagnostics.setHidden(True)
        self.scorecard_forecast.setWordWrap(True)
        self.scorecard_guidance.setWordWrap(True)
        self.scorecard_brier.setWordWrap(True)
        if isinstance(scorecard, TrajectoryScorecard):
            self._trajectory_score = scorecard
            self._excluded_scoring_revision_ids = frozenset(
                scorecard.excluded_revision_ids
            )
            self.scorecard_section.setHidden(False)
            self.scorecard_outcome.setText(
                f"Effective outcome: {scorecard.outcome.value.capitalize()}"
            )
            self.scorecard_brier.setText(
                "Not scored"
                if scorecard.trajectory_brier is None
                else f"Trajectory Brier: {float(scorecard.trajectory_brier):.4f}"
            )
            apply_text_role(self.scorecard_brier, TextRole.FORECAST)
            self.scorecard_forecast.setText(
                ""
                if not scorecard.segments
                else f"Final eligible forecast: {scorecard.segments[-1].probability_percent}% (revision ID {scorecard.segments[-1].revision_id})"
            )
            self.scorecard_guidance.setText(
                scorecard.unscored_reason
                or "Lower is better. Standing durations are weighted within the original, fixed forecasting window."
            )
            notices = []
            if scorecard.scoring_facts_corrected:
                notices.append(
                    "Scoring uses corrected facts; original values remain in history."
                )
            if scorecard.excluded_revision_ids:
                notices.append(
                    "Revisions excluded by the effective cutoff remain in history: "
                    + ", ".join(map(str, scorecard.excluded_revision_ids))
                )
            self.scorecard_correction_notice.setText("\n".join(notices))
            self.scorecard_correction_notice.setHidden(not notices)
            if not scorecard.unscored_reason:
                content, layout = _history_content(self.trajectory_diagnostics)
                _clear_widget_layout(layout)
                layout.addWidget(TrajectoryScoreDetails(scorecard, content))
                self.trajectory_diagnostics.setChecked(False)
                content.setHidden(True)
                self.trajectory_diagnostics.setHidden(False)
            return
        self.scorecard_section.setHidden(True)

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
                    self.definition_history,
                )
            )
        )

    def _load_timeline(self, prediction_id: int) -> bool:
        try:
            events = self._operations.list_timeline(prediction_id)
        except ApplicationError as error:
            self.forecast_timeline.setHidden(True)
            self.timeline_placeholder.setText("Timeline could not be loaded.")
            self.timeline_placeholder.setHidden(False)
            self._show_error(str(error))
            return False

        snapshot = (
            prediction_id,
            tuple(events),
            self._resolution_history,
            self._invalidation_history,
            frozenset(self._excluded_scoring_revision_ids),
        )
        if self.timeline_rows.matches(snapshot):
            self.forecast_timeline.setHidden(not self.timeline_rows.rows)
            self.timeline_placeholder.setText("No timeline entries are available.")
            self.timeline_placeholder.setHidden(bool(self.timeline_rows.rows))
            return True
        self._sync_timing(events)
        rows = []
        for event in events:
            kind, identifier = (
                ("review", event.review_id)
                if hasattr(event, "review_id")
                else ("journal", event.entry_id)
                if hasattr(event, "entry_id")
                else ("forecast", event.revision_id)
            )
            row = self.timeline_rows.row(
                (prediction_id, kind, identifier),
                (
                    event,
                    kind == "forecast"
                    and identifier == self._prediction.current_revision_id,
                    kind == "forecast"
                    and identifier in self._excluded_scoring_revision_ids,
                ),
                lambda event=event: self._timeline_row(event),
            )
            rows.append((event.created_at, 0, row))
        rows.extend(
            terminal_timeline_rows(
                self._resolution_history,
                self._invalidation_history,
                self.forecast_timeline,
            )
        )
        self.timeline_rows.replace(
            snapshot, rows, descending=self.timeline_order.currentIndex() == 0
        )
        self.forecast_timeline.setHidden(not rows)
        self.timeline_placeholder.setText("No timeline entries are available.")
        self.timeline_placeholder.setHidden(bool(rows))
        return True

    def _timeline_row(self, event) -> QWidget:
        if hasattr(event, "review_id"):
            return _forecast_review_widget(event, self.forecast_timeline)
        if hasattr(event, "entry_id"):
            return _journal_entry_widget(
                event, self.forecast_timeline, self.open_correct_journal_entry
            )
        row = _forecast_timeline_widget(
            event,
            self.forecast_timeline,
            scoring_excluded=event.revision_id in self._excluded_scoring_revision_ids,
        )
        if event.revision_id == self._prediction.current_revision_id:
            current_marker(row)
        return row

    def _load_probability_history(self, prediction_id: int) -> None:
        """Reload chart revisions without turning a read failure into emptiness."""

        try:
            revisions = self._operations.list_forecast_revisions(prediction_id)
        except ApplicationError as error:
            has_matching_history = (
                self._chart_prediction_id == prediction_id
                and self.probability_history_chart.revision_count > 0
            )
            if has_matching_history:
                self.probability_history_chart.setHidden(False)
                self.chart_placeholder.setText(
                    "Probability history could not be refreshed. The last loaded "
                    "chart remains visible."
                )
                failure_action = "refreshed"
            else:
                self.probability_history_chart.clear()
                self.probability_history_chart.setHidden(True)
                self._chart_prediction_id = None
                self.chart_placeholder.setText(
                    "Probability history could not be loaded."
                )
                failure_action = "loaded"
            self.chart_placeholder.setHidden(False)
            self._show_error(
                f"Probability history could not be {failure_action}. {error}"
            )
            return

        self.probability_history_chart.set_revisions(revisions)
        self._chart_prediction_id = prediction_id
        has_revisions = self.probability_history_chart.revision_count > 0
        self.probability_history_chart.setHidden(not has_revisions)
        self.chart_placeholder.setText("No forecast revisions are available to chart.")
        self.chart_placeholder.setHidden(has_revisions)

    def _show_error(self, message: str) -> None:
        self.detail_error.setText(message)
        self.detail_error.setHidden(False)

    def _hide_error(self) -> None:
        self.detail_error.clear()
        self.detail_error.setHidden(True)

    def _sync_reading_actions(self, prediction) -> None:
        # These legacy groups retain backing label identities; Overview and the
        # real chronological Timeline now own all visible terminal content.
        self.resolution_section.hide()
        self.invalidation_section.hide()
        self.reading_sections.sync(prediction.status)
        for label in (
            self.scorecard_forecast,
            self.scorecard_outcome,
            self.scorecard_brier,
            self.scorecard_correction_notice,
        ):
            label.hide()
        if (
            self._trajectory_score is not None
            and self._trajectory_score.unscored_reason
        ):
            self.scorecard_section.hide()
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
        self.probability.setVisible(not terminal)
        self.header_timing.setVisible(not terminal)
        self.terminal_summary.setVisible(terminal)
        if prediction.status is PredictionStatus.RESOLVED:
            card = self._trajectory_score
            self.terminal_summary.set_facts(
                outcome=self.resolution_outcome.text(),
                score=self.scorecard_brier.text()
                if card is not None
                else "Score unavailable",
                timing=self.resolution_resolved_at.text(),
                timing_tooltip=self.resolution_resolved_at.toolTip(),
                note=(card.unscored_reason or self.scorecard_correction_notice.text())
                if card is not None
                else "The score could not be loaded. Try again before interpreting this result.",
                context=self.scorecard_forecast.text() if card is not None else "",
            )
        elif prediction.status is PredictionStatus.INVALID:
            self.terminal_summary.set_facts(
                outcome="Recorded reason",
                score="Not scored",
                timing=invalidation_timing(
                    self.invalidated_at.text(), self._invalidation_history, widget=self
                ),
                note=self.invalidation_reason.text() or "No reason recorded.",
                context=f"Last forecast: {prediction.probability_percent}%\nOriginal Forecast Deadline: {self.forecast_deadline.text()}",
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
        forecasts = [event for event in events if hasattr(event, "revision_id")]
        considered = [
            event
            for event in events
            if hasattr(event, "revision_id") or hasattr(event, "review_id")
        ]
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
        identifier = self._prediction.current_revision_id
        target = self.findChild(QWidget, "forecastRevision" + str(identifier))
        if target is not None:
            self.workspace.ensureWidgetVisible(target, 12, 12)
            target.setFocus(Qt.FocusReason.OtherFocusReason)

    def _start_editor(self, editor, kind: str) -> None:
        editor.setProperty("reviewedQuestion", self._prediction.question)
        editor.setProperty(
            "reviewedForecast", str(self._prediction.probability_percent) + "% Yes"
        )
        editor._refresh_reading = self.refresh
        self.workspace.begin_editor(editor, kind)

    def open_postmortem(self) -> None:
        if self._prediction is None or not self.workspace.prepare_task("Postmortem"):
            return
        try:
            expected = self._operations.get_binary_resolution_history(
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
