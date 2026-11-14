"""Prediction detail responsibilities extracted from the desktop composition."""

from __future__ import annotations

from datetime import date, datetime
from fractions import Fraction

from PySide6.QtWidgets import (
    QFrame,
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

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.domain.one_shot import (
    OneShotDetail,
    OneShotJournal,
    OneShotSourceAction,
    OneShotValues,
)
from reckonsolve.domain.predictions import (
    PredictionStatus,
)
from reckonsolve.domain.search import SearchDocument, SearchSourceKind
from reckonsolve.one_shot_display import (
    forecast_text,
    score_lines,
    status_text,
    values_lines,
)
from reckonsolve.quantile_display import exact_score_text
from reckonsolve.ui.components import (
    ContentPanel,
    StatusBadge,
)
from reckonsolve.ui.contextual_forms import BodyEditor
from reckonsolve.ui.date_display import format_date, format_reported_time
from reckonsolve.ui.detail_reading import (
    TerminalSummary,
    invalidation_exact_timing,
    invalidation_timing,
)
from reckonsolve.ui.detail_workspace import DetailWorkspace, collapse_section
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.numeric_interval import NumericInterval
from reckonsolve.ui.one_shot import OneShotEditDialog, text_label
from reckonsolve.ui.prediction_dialogs import (
    CorrectInvalidationReasonDialog,
    EditPredictionDetailsDialog,
)
from reckonsolve.ui.prediction_widgets import (
    _definition_change_widget,
    _focus_search_widget,
    _format_local_timestamp,
    _one_shot_journal_timeline_widget,
)
from reckonsolve.ui.reflection_editor import ReflectionEditor
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    ActionRole,
    Spacing,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_message_role,
    apply_surface_role,
    apply_text_role,
)


def _snapshot_widget(
    title: str, values: OneShotValues, unit: str, parent: QWidget
) -> QWidget:
    """Keep a complete immutable snapshot together with readable internal spacing."""
    block = QWidget(parent)
    column = QVBoxLayout(block)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(int(Spacing.COMPACT))
    heading = text_label(title, block)
    apply_text_role(heading, TextRole.LABEL)
    column.addWidget(heading)
    facts = text_label(
        "\n".join(
            values_lines(
                values,
                unit,
                reported_formatter=lambda reported: format_reported_time(
                    reported, block
                ),
            )
        ),
        block,
    )
    column.addWidget(facts)
    return block


class OneShotDetailScreen(QWidget):
    """One saved guess with a separate original and correction history."""

    def __init__(self, operations, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._operations = operations
        self._prediction: OneShotDetail | None = None
        self.interval: NumericInterval | None = None
        self.terminal_summary: TerminalSummary | None = None
        self._dialog = None
        self.content = QWidget(self)
        self.content_layout = QVBoxLayout(self.content)
        self.workspace = DetailWorkspace(self.content, self)
        self.workspace.task_closed.connect(self._restore_reflection_actions)
        self.scroll = self.workspace
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def show_prediction(self, detail: OneShotDetail | None) -> None:
        self._prediction = detail
        self.interval = None
        self.terminal_summary = None
        self.workspace.clear_reading()
        if detail is None:
            self.content_layout.addWidget(text_label("The One-Shot was deleted.", self))
            return
        record = detail.record
        unit = record.definition.unit if record.definition else ""
        summary = QWidget(self)
        header = QVBoxLayout(summary)
        header.setContentsMargins(0, 0, 0, 0)
        badges = QWidget(summary)
        badge_row = QHBoxLayout(badges)
        badge_row.setContentsMargins(0, 0, 0, 0)
        badge_row.addWidget(
            StatusBadge(
                f"One-Shot · {record.contract.prediction_type.value.title()}",
                StatusTone.NEUTRAL,
                parent=badges,
            )
        )
        badge_row.addWidget(
            StatusBadge(
                "Answer Pending"
                if detail.status is PredictionStatus.OPEN
                else status_text(detail),
                StatusTone.SUCCESS
                if detail.status is PredictionStatus.RESOLVED
                else StatusTone.CAUTION
                if detail.status is PredictionStatus.INVALID
                else StatusTone.WARNING,
                parent=badges,
            )
        )
        badge_row.addStretch()
        header.addWidget(badges)
        self.question = text_label(detail.question, summary)
        self.question.setObjectName("oneShotQuestion")
        apply_text_role(self.question, TextRole.QUESTION)
        header.addWidget(self.question)
        transcription = [
            item
            for item in record.corrections
            if item.source_action is OneShotSourceAction.TRANSCRIPTION
        ]
        if transcription:
            header.addWidget(
                text_label(
                    "Transcription corrected · Effective recorded facts", summary
                )
            )
        forecast_summary = QWidget(summary)
        forecast_layout = QVBoxLayout(forecast_summary)
        forecast_layout.setContentsMargins(0, 0, 0, 0)
        self.forecast = text_label(
            forecast_text(record.effective, unit), forecast_summary
        )
        self.forecast.setObjectName("oneShotForecast")
        apply_text_role(self.forecast, TextRole.FORECAST)
        if record.effective.quantiles is not None:
            self.interval = NumericInterval(forecast_summary)
            self.interval.set_forecast(record.effective.quantiles, unit)
            forecast_layout.addWidget(self.interval)
            self.forecast.hide()
            forecast_layout.addWidget(
                text_label(
                    "90% interval · 50% interval · Median"
                    + (f" · {unit}" if unit else ""),
                    forecast_summary,
                )
            )
        else:
            forecast_layout.addWidget(self.forecast)
        forecast_layout.addWidget(
            text_label(
                "Saved One-Shot Forecast",
                forecast_summary,
            )
        )
        header.addWidget(forecast_summary)
        if detail.invalidation_history is not None:
            invalid = detail.invalidation_history
            forecast_summary.hide()
            self.terminal_summary = TerminalSummary(summary)
            timing = invalidation_timing(
                "Marked Invalid: "
                + _format_local_timestamp(invalid.original.invalidated_at, widget=self),
                invalid,
                widget=self,
            )
            self.terminal_summary.set_facts(
                outcome="Recorded reason",
                score="Not scored",
                timing=timing,
                note=invalid.effective.reason or "No reason recorded.",
                context=forecast_text(record.effective, unit),
                context_title="Last forecast · Not scored",
                timing_tooltip=invalidation_exact_timing(invalid),
            )
            header.addWidget(self.terminal_summary)
        if detail.tags:
            self.tags = text_label("  ".join(f"#{t}" for t in detail.tags), summary)
            self.tags.setObjectName("oneShotTags")
            header.addWidget(self.tags)
        action_panel = QWidget(self)
        actions = FlowLayout(action_panel)
        self.answer_button = QPushButton("Add Answer", action_panel)
        self.answer_button.setVisible(detail.status is PredictionStatus.OPEN)
        apply_action_role(self.answer_button, ActionRole.PRIMARY)
        self.answer_button.clicked.connect(lambda: self.open_values(correction=False))
        self.journal_button = QPushButton("Add Journal Entry", action_panel)
        self.journal_button.setVisible(detail.status is PredictionStatus.OPEN)
        self.journal_button.clicked.connect(self.open_journal)
        actions.addWidget(self.answer_button)
        actions.addWidget(self.journal_button)
        self.more_button = QPushButton("More", action_panel)
        menu = QMenu(self.more_button)
        self.correct_button = menu.addAction(
            "Correct Transcription", lambda: self.open_values(correction=True)
        )
        self.edit_button = menu.addAction("Edit Details", self.open_metadata)
        self.later_postmortem_action = menu.addAction(
            "Write Postmortem", self.add_postmortem
        )
        self.later_postmortem_action.setVisible(
            detail.status is PredictionStatus.RESOLVED
            and detail.postmortem_completion is not None
            and not record.effective.postmortem
        )
        self.invalid_reason_action = menu.addAction(
            "Correct Invalid reason", self.correct_invalid_reason
        )
        self.invalid_reason_action.setVisible(detail.status is PredictionStatus.INVALID)
        self.invalid_button = menu.addAction("Mark Invalid", self.invalidate)
        self.invalid_button.setProperty(ACTION_ROLE_PROPERTY, ActionRole.CAUTION.value)
        self.invalid_button.setVisible(detail.status is PredictionStatus.OPEN)
        self.delete_button = menu.addAction("Delete", self.delete)
        self.delete_button.setProperty(
            ACTION_ROLE_PROPERTY, ActionRole.DESTRUCTIVE.value
        )
        self.delete_button.setVisible(detail.deletion_allowed)
        self.more_button.setMenu(menu)
        actions.addWidget(self.more_button)
        self.error = text_label("", action_panel)
        apply_message_role(
            self.error, StatusTone.ERROR, accessible_name="One-Shot Detail error"
        )
        self.error.hide()
        actions.addWidget(self.error)

        self.results = ContentPanel(
            "Results"
            if detail.status is PredictionStatus.RESOLVED
            else "Answer Pending"
            if detail.status is PredictionStatus.OPEN
            else "Invalid · Not scored",
            parent=self,
        )
        self.results.setObjectName("oneShotResults")
        if detail.invalidation_history:
            invalid = detail.invalidation_history
            self.results.body_layout.addWidget(
                text_label(
                    f"Invalidated: {_format_local_timestamp(invalid.original.invalidated_at, widget=self)}\nReason: {invalid.effective.reason or 'Not supplied'}",
                    self,
                )
            )
            if invalid.corrections:
                self.results.body_layout.addWidget(
                    text_label(
                        "Reason corrected: "
                        + _format_local_timestamp(
                            invalid.corrections[-1].corrected_at, widget=self
                        )
                        + " · Original decision date unchanged",
                        self,
                    )
                )
            # The header owns current reason/timing; original and corrected
            # versions remain in recorded history, with repair under More.
            self.results.hide()
        else:
            answer_text = next(
                (
                    line
                    for line in values_lines(
                        record.effective,
                        unit,
                        reported_formatter=lambda reported: format_reported_time(
                            reported, self
                        ),
                    )
                    if line.startswith("Answer:")
                ),
                "Add the answer after you have checked it.",
            )
            self.answer_result = text_label(answer_text, self)
            apply_text_role(
                self.answer_result,
                TextRole.FORECAST
                if detail.status is PredictionStatus.RESOLVED
                else TextRole.BODY,
            )
            self.results.body_layout.addWidget(self.answer_result)
        self.scorecard = ContentPanel("Scorecard", parent=self.results)
        self.scorecard.setObjectName("oneShotScorecard")
        saved_score = self._operations.one_shots.score(detail)
        lines = score_lines(saved_score, unit)
        if lines:
            numeric_score = not isinstance(saved_score, Fraction)
            self.scorecard.title_label.setText(
                "Weighted Interval Score (WIS)" if numeric_score else "Brier Score"
            )
            self.scorecard.title_label.setWordWrap(True)
            self.scorecard.title_label.setSizePolicy(
                QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
            )
            self.scorecard.title_label.parentWidget().layout().setStretch(0, 1)
            self.score_value = text_label(
                exact_score_text(saved_score.wis if numeric_score else saved_score)
                + (f" {unit}" if numeric_score and unit else ""),
                self.scorecard,
            )
            self.score_value.setObjectName("oneShotScoreValue")
            apply_text_role(self.score_value, TextRole.PAGE_TITLE)
            self.scorecard.body_layout.addWidget(self.score_value)
            self.scorecard.body_layout.addWidget(
                text_label("Lower is better.", self.scorecard)
            )
            if len(lines) > 1:
                self.scorecard.body_layout.addWidget(
                    collapse_section(
                        text_label("\n".join(lines[1:]), self),
                        "Score Breakdown",
                        compact=True,
                    )
                )
            if transcription:
                self.scorecard.body_layout.addWidget(
                    text_label(
                        "Uses effective corrected facts. Originals remain available below.",
                        self,
                    )
                )
        else:
            self.scorecard.hide()
        if detail.status is PredictionStatus.RESOLVED:
            self.results.body_layout.removeWidget(self.answer_result)
            self.answer_panel = ContentPanel("Checked Answer", parent=self.results)
            apply_surface_role(self.answer_panel, SurfaceRole.CANVAS)
            self.answer_result.setAccessibleName(self.answer_result.text())
            self.answer_result.setText(
                self.answer_result.text().removeprefix("Answer: ")
            )
            self.answer_panel.body_layout.addWidget(self.answer_result)
            self.results.body_layout.addWidget(self.answer_panel)
            self.results.body_layout.addWidget(self.scorecard)
            if record.effective.resolution_notes:
                self.results.body_layout.addWidget(
                    text_label(
                        "Resolution notes: " + record.effective.resolution_notes, self
                    )
                )
            if transcription and transcription[-1].note:
                self.results.body_layout.addWidget(
                    text_label("Correction note: " + transcription[-1].note, self)
                )

        self.reflection = ContentPanel("POSTMORTEM", parent=self)
        self.reflection.setObjectName("oneShotPostmortem")
        self.reflection.setVisible(detail.status is PredictionStatus.RESOLVED)
        self.reflection_copy = QWidget(self.reflection)
        reflection_copy_layout = QVBoxLayout(self.reflection_copy)
        reflection_copy_layout.setContentsMargins(0, 0, 0, 0)
        self.reflection.body_layout.addWidget(self.reflection_copy)
        if record.effective.postmortem:
            reflection_copy_layout.addWidget(
                text_label(record.effective.postmortem, self)
            )
        elif detail.postmortem_completion is None:
            reflection_copy_layout.addWidget(
                text_label(
                    "Optional reflection on what you learned from this result.", self
                )
            )
        if detail.postmortem_completion:
            completion = text_label(
                (
                    "Previously Skipped · "
                    if record.effective.postmortem
                    else "Postmortem Skipped · "
                )
                + _format_local_timestamp(
                    detail.postmortem_completion.completed_at, widget=self
                ),
                self,
            )
            completion.setObjectName("oneShotPostmortemCompletion")
            reflection_copy_layout.addWidget(completion)
            if not record.effective.postmortem:
                reflection_copy_layout.addWidget(
                    text_label("Marked complete. You can write later from More.", self)
                )
        self.add_postmortem_button = QPushButton(
            "Edit Postmortem" if record.effective.postmortem else "Write Postmortem",
            self,
        )
        self.add_postmortem_button.clicked.connect(self.add_postmortem)
        self.add_postmortem_button.setVisible(
            bool(record.effective.postmortem) or detail.postmortem_completion is None
        )
        reflection_actions = QWidget(self)
        reflection_row = QHBoxLayout(reflection_actions)
        reflection_row.setContentsMargins(0, 0, 0, 0)
        reflection_row.addWidget(self.add_postmortem_button)
        self.skip_postmortem_button = QPushButton("Skip", self)
        self.skip_postmortem_button.setVisible(
            not record.effective.postmortem and detail.postmortem_completion is None
        )
        self.skip_postmortem_button.clicked.connect(self.skip_postmortem)
        apply_action_role(self.skip_postmortem_button, ActionRole.QUIET)
        reflection_row.addWidget(self.skip_postmortem_button)
        reflection_row.addStretch()
        self.reflection.body_layout.addWidget(reflection_actions)
        self.journals = ContentPanel("JOURNAL ENTRIES", parent=self)
        self.journals.setObjectName("oneShotJournalEntries")
        if not detail.journals:
            self.journals.body_layout.addWidget(text_label("No Journal entries.", self))
        self._show_timeline(detail)
        timeline = self.recorded_timeline

        facts = ContentPanel("Recorded Facts", parent=self)
        facts.setObjectName("oneShotRecordedFacts")
        facts.body_layout.addWidget(
            text_label(
                "\n".join(
                    line
                    for line in values_lines(
                        record.effective,
                        unit,
                        reported_formatter=lambda reported: format_reported_time(
                            reported, self
                        ),
                    )[1:]
                    if "(user-reported)" in line
                ),
                self,
            )
        )
        facts.body_layout.addWidget(
            text_label(
                "Entered in Reckonsolve: "
                + _format_local_timestamp(record.recorded_at, widget=self),
                self,
            )
        )
        if record.answer_recorded_at:
            facts.body_layout.addWidget(
                text_label(
                    "Answer entered in Reckonsolve: "
                    + _format_local_timestamp(record.answer_recorded_at, widget=self),
                    self,
                )
            )
        if record.definition:
            facts.body_layout.addWidget(
                text_label(
                    f"Unit: {unit} · Decimal places: {record.definition.decimal_places} · {record.definition.value_constraint.value}",
                    self,
                )
            )
        overview = [facts]
        for title, value in (
            ("Background", detail.background),
            ("Rationale", detail.rationale),
            ("Resolution Criteria", detail.resolution_criteria),
            ("Expected resolution", detail.expected_resolution),
        ):
            if value:
                panel = ContentPanel(title, parent=self)
                panel.setObjectName(
                    {
                        "Rationale": "oneShotRationale",
                        "Background": "oneShotBackground",
                        "Resolution Criteria": "oneShotResolutionCriteria",
                    }.get(title, "oneShotOptionalMetadata")
                )
                panel.body_layout.addWidget(
                    text_label(
                        format_date(value, self)
                        if isinstance(value, date)
                        else str(value),
                        self,
                    )
                )
                overview.append(panel)
        history = ContentPanel("", parent=self)
        history.title_label.hide()
        history.setObjectName("oneShotCorrectionHistory")
        body = history.body_layout
        body.setSpacing(int(Spacing.SECTION))
        body.addWidget(
            _snapshot_widget("Original Saved Facts", record.original, unit, history)
        )
        for correction in record.corrections:
            entry = QWidget(history)
            entry_layout = QVBoxLayout(entry)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(int(Spacing.ORDINARY))
            heading = text_label(
                f"{'Postmortem Update' if correction.source_action is OneShotSourceAction.POSTMORTEM else 'Transcription Correction'} {correction.sequence}",
                entry,
            )
            apply_text_role(heading, TextRole.LABEL)
            entry_layout.addWidget(heading)
            entry_layout.addWidget(
                text_label(
                    _format_local_timestamp(correction.corrected_at, widget=self), entry
                )
            )
            entry_layout.addWidget(
                _snapshot_widget("Before", correction.before, unit, entry)
            )
            entry_layout.addWidget(
                _snapshot_widget("After", correction.after, unit, entry)
            )
            if correction.note:
                entry_layout.addWidget(text_label("Note: " + correction.note, entry))
            body.addWidget(entry)
        history_disclosure = collapse_section(
            history, "Originals & Corrections", compact=True
        )
        overview.append(history_disclosure)
        if detail.definition_changes:
            definitions = ContentPanel("", parent=self)
            definitions.title_label.hide()
            definitions.setObjectName("oneShotDefinitionHistory")
            body = definitions.body_layout
            for change in detail.definition_changes:
                body.addWidget(_definition_change_widget(change, self))
            overview.append(
                collapse_section(definitions, "Definition History", compact=True)
            )
        for panel in [
            self.results,
            self.scorecard,
            self.reflection,
            self.journals,
            facts,
            *overview[1:],
        ]:
            apply_surface_role(panel, SurfaceRole.CANVAS)
        if detail.status is PredictionStatus.RESOLVED:
            self.results.title_label.hide()
            apply_surface_role(self.scorecard, SurfaceRole.RAISED)
            self.answer_panel.layout().setContentsMargins(0, 0, 0, 0)
        for panel in (self.results, self.reflection, self.journals):
            panel.layout().setContentsMargins(0, 0, 0, 0)
        for panel in (facts, history):
            apply_surface_role(panel, SurfaceRole.RAISED)
            panel.title_label.parentWidget().hide()
            for label in panel.findChildren(QLabel):
                # Let prose grow vertically inside the panel's padded width.
                policy = label.sizePolicy()
                policy.setHorizontalPolicy(QSizePolicy.Policy.Ignored)
                label.setSizePolicy(policy)
                label.setMinimumWidth(0)
        extras = [
            widget for widget in overview if widget not in (facts, history_disclosure)
        ]
        self.overview_heading = text_label(
            "ARCHIVAL CONTEXT"
            if detail.status is PredictionStatus.INVALID
            else "OVERVIEW",
            self,
        )
        apply_text_role(self.overview_heading, TextRole.SECTION_TITLE)
        reading_heading = text_label(
            "ARCHIVAL RECORD"
            if detail.status is PredictionStatus.INVALID
            else "RESULTS"
            if detail.status is PredictionStatus.RESOLVED
            else "JOURNAL & RECORD",
            self,
        )
        apply_text_role(reading_heading, TextRole.SECTION_TITLE)
        self.workspace.compose(
            summary,
            action_panel,
            [
                reading_heading,
                *(
                    [self.results]
                    if detail.status is not PredictionStatus.INVALID
                    else []
                ),
                self.reflection,
                self.journals,
                collapse_section(timeline, "Recorded History", compact=True),
            ],
            [
                self.overview_heading,
                *extras,
                collapse_section(facts, "Times & Recorded Facts", compact=True),
                history_disclosure,
            ],
        )
        self.workspace.set_reading_context(
            self.overview_heading,
            terminal=detail.status
            in (PredictionStatus.RESOLVED, PredictionStatus.INVALID),
        )
        if self.workspace.inline and self.workspace.editor is not None:
            self.reflection.body_layout.addWidget(self.workspace.editor)
            self.workspace.editor.show()

    def _show_timeline(self, detail: OneShotDetail) -> None:
        """Present app-recorded actions in causal order, separate from reported times."""

        record = detail.record
        unit = record.definition.unit if record.definition else ""
        events: list[
            tuple[
                datetime,
                int,
                str | OneShotJournal,
                tuple[tuple[SearchSourceKind, int | None, int | None], ...],
            ]
        ] = []
        self._search_targets: dict[
            tuple[SearchSourceKind, int | None, int | None], QWidget
        ] = {}
        events.append(
            (
                record.recorded_at,
                0,
                "Forecast entered in Reckonsolve: "
                + forecast_text(record.original, unit)
                + (f"\nRationale: {detail.rationale}" if detail.rationale else ""),
                ((SearchSourceKind.FORECAST_RATIONALE, None, None),),
            )
        )
        if record.answer_recorded_at:
            events.append(
                (
                    record.answer_recorded_at,
                    1,
                    "Answer entered in Reckonsolve: "
                    + "\n".join(
                        values_lines(
                            record.original,
                            unit,
                            reported_formatter=lambda reported: format_reported_time(
                                reported, self
                            ),
                        )[2:]
                    ),
                    (
                        (SearchSourceKind.RESOLUTION_NOTES, None, None),
                        (SearchSourceKind.POSTMORTEM, None, None),
                    ),
                )
            )
        for correction in record.corrections:
            events.append(
                (
                    correction.corrected_at,
                    2,
                    f"{'Postmortem update' if correction.source_action is OneShotSourceAction.POSTMORTEM else 'Transcription correction'} {correction.sequence}\n"
                    + "\n".join(
                        values_lines(
                            correction.after,
                            unit,
                            reported_formatter=lambda reported: format_reported_time(
                                reported, self
                            ),
                        )
                    )
                    + (f"\nNote: {correction.note}" if correction.note else ""),
                    (
                        (
                            SearchSourceKind.RESOLUTION_NOTES,
                            None,
                            correction.correction_id,
                        ),
                        (SearchSourceKind.POSTMORTEM, None, correction.correction_id),
                        (
                            SearchSourceKind.ONE_SHOT_CORRECTION_NOTE,
                            correction.correction_id,
                            None,
                        ),
                    ),
                )
            )
        for change in detail.definition_changes:
            changed_text = []
            if "question" in change.changed_fields:
                changed_text.append(
                    f"Question before: {change.old_question}\nQuestion after: {change.new_question}"
                )
            if "resolution_criteria" in change.changed_fields:
                changed_text.append(
                    "Resolution Criteria before: "
                    + (change.old_resolution_criteria or "Not supplied")
                    + "\nResolution Criteria after: "
                    + (change.new_resolution_criteria or "Not supplied")
                )
            events.append(
                (
                    change.changed_at,
                    3,
                    "Definition clarified\n" + "\n".join(changed_text),
                    (
                        (SearchSourceKind.QUESTION, change.change_id, None),
                        (SearchSourceKind.RESOLUTION_CRITERIA, change.change_id, None),
                    ),
                )
            )
        for journal in detail.journals:
            events.append(
                (
                    journal.created_at,
                    4,
                    journal,
                    (),
                )
            )
        if detail.invalidation_history:
            invalidation = detail.invalidation_history
            events.append(
                (
                    invalidation.original.invalidated_at,
                    6,
                    "Marked Invalid: "
                    + (invalidation.original.reason or "No reason supplied"),
                    ((SearchSourceKind.INVALIDATION_REASON, None, None),),
                )
            )
            for correction in invalidation.corrections:
                events.append(
                    (
                        correction.corrected_at,
                        7,
                        "Invalidation reason corrected: "
                        + (correction.new_reason or "No reason supplied"),
                        (
                            (
                                SearchSourceKind.INVALIDATION_REASON,
                                None,
                                correction.correction_id,
                            ),
                        ),
                    )
                )
        if detail.postmortem_completion:
            events.append(
                (
                    detail.postmortem_completion.completed_at,
                    8,
                    "Postmortem deliberately skipped",
                    (),
                )
            )
        timeline = ContentPanel("Timeline", parent=self)
        self.recorded_timeline = timeline
        timeline.setObjectName("oneShotTimeline")
        for index, (occurred_at, _, body, keys) in enumerate(
            sorted(events, key=lambda event: (event[0], event[1]))
        ):
            if isinstance(body, OneShotJournal):
                card = _one_shot_journal_timeline_widget(
                    body, timeline, self.correct_journal
                )
                self.journals.body_layout.addWidget(card)
                current_body = card.findChild(
                    QLabel, f"oneShotJournalBody{body.entry_id}"
                )
                current_key = (
                    SearchSourceKind.JOURNAL,
                    body.entry_id,
                    body.current_correction_id,
                )
                self._search_targets[current_key] = current_body or card
                if body.corrections:
                    self._search_targets[
                        (SearchSourceKind.JOURNAL, body.entry_id, None)
                    ] = (
                        card.findChild(
                            QLabel, f"journalEntryOriginalBody{body.entry_id}"
                        )
                        or card
                    )
                    for correction in body.corrections[:-1]:
                        self._search_targets[
                            (
                                SearchSourceKind.JOURNAL,
                                body.entry_id,
                                correction.correction_id,
                            )
                        ] = (
                            card.findChild(
                                QLabel,
                                f"journalCorrectionBody{correction.correction_id}",
                            )
                            or card
                        )
                continue
            card = QFrame(timeline)
            card.setFrameShape(QFrame.Shape.StyledPanel)
            apply_surface_role(card, SurfaceRole.BASE)
            card_layout = QVBoxLayout(card)
            timestamp = text_label(
                _format_local_timestamp(occurred_at, widget=self), card
            )
            apply_text_role(timestamp, TextRole.SECONDARY)
            card_layout.addWidget(timestamp)
            label = text_label(body, card)
            label.setObjectName(f"oneShotTimelineEvent{index}")
            card_layout.addWidget(label)
            timeline.body_layout.addWidget(card)
            for key in keys:
                self._search_targets[key] = label
        self.content_layout.addWidget(timeline)

    def focus_search_match(self, document: SearchDocument) -> None:
        if (
            self._prediction is None
            or self._prediction.prediction_id != document.prediction_id
        ):
            return
        kind = document.source_kind
        if (
            kind is SearchSourceKind.INVALIDATION_REASON
            and not document.is_superseded
            and self._prediction.invalidation_history is not None
        ):
            _focus_search_widget(self.scroll, self.terminal_summary.note)
            return
        target = self._search_targets.get(
            (kind, document.source_record_id, document.source_version_id)
        ) or self._search_targets.get((kind, None, document.source_version_id))
        if target is None:
            target = {
                SearchSourceKind.QUESTION: self.question,
                SearchSourceKind.TAG: getattr(self, "tags", self.question),
                SearchSourceKind.BACKGROUND: self.findChild(
                    QWidget, "oneShotBackground"
                ),
                SearchSourceKind.RESOLUTION_CRITERIA: self.findChild(
                    QWidget, "oneShotResolutionCriteria"
                ),
                SearchSourceKind.FORECAST_RATIONALE: self.findChild(
                    QWidget, "oneShotRationale"
                ),
            }.get(kind)
        if target is None:
            target = self.findChild(QWidget, "oneShotTimeline") or self.question
        if kind is SearchSourceKind.JOURNAL and document.is_superseded:
            history = self.findChild(
                QGroupBox, f"journalEntryEditHistory{document.source_record_id}"
            )
            if history is not None:
                history.setChecked(True)
        _focus_search_widget(self.scroll, target)

    def correct_journal(self, entry_id: int) -> None:
        if self._prediction is None or not self.workspace.prepare_task(
            "Journal correction"
        ):
            return
        try:
            current = self._operations.one_shots.get(self._prediction.prediction_id)
            entry = next(item for item in current.journals if item.entry_id == entry_id)
        except (ApplicationError, StopIteration) as error:
            self.error.setText(str(error) or "The Journal entry is unavailable.")
            self.error.show()
            return
        editor = BodyEditor(
            "Correct Journal entry",
            entry.body,
            lambda body: self._operations.one_shots.correct_journal(
                current,
                entry_id,
                body,
                expected_correction_id=entry.current_correction_id,
            ),
            self,
        )
        editor.saved.connect(self.show_prediction)
        self.workspace.begin_editor(editor, "Journal correction")

    def skip_postmortem(self) -> None:
        if self._prediction is None:
            return
        if not self.workspace.confirm_exit("skip Postmortem"):
            return
        if (
            QMessageBox.question(
                self,
                "Skip Postmortem?",
                "Mark reflection complete without writing a Postmortem? "
                "This decision remains in history. You can write later from More.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.show_prediction(
                self._operations.one_shots.skip_postmortem(self._prediction)
            )
        except ApplicationError as error:
            self.error.setText(str(error))
            self.error.show()

    def add_postmortem(self) -> None:
        if self._prediction is None or not self.workspace.prepare_task("Postmortem"):
            return
        current = self._prediction
        editor = ReflectionEditor(
            current.record.effective.postmortem,
            lambda body, clear, reason: save_postmortem(
                self._operations,
                current,
                body,
                confirm_clear=clear,
                correction_reason=reason,
            ),
            self,
        )
        editor.saved.connect(self.show_prediction)
        self.workspace.begin_inline_editor(editor, self.reflection)
        self.add_postmortem_button.hide()
        self.skip_postmortem_button.hide()
        self.later_postmortem_action.setVisible(False)
        self.reflection_copy.hide()
        # The surrounding section supplies the single visible heading.
        editor.findChild(QLabel).hide()

    def _restore_reflection_actions(self, kind: str) -> None:
        if kind != "Postmortem" or self._prediction is None:
            return
        resolved = self._prediction.status is PredictionStatus.RESOLVED
        has_body = bool(self._prediction.record.effective.postmortem)
        skipped = self._prediction.postmortem_completion is not None
        self.reflection_copy.show()
        self.add_postmortem_button.setVisible(resolved and (has_body or not skipped))
        self.later_postmortem_action.setVisible(resolved and skipped and not has_body)
        self.skip_postmortem_button.setVisible(
            resolved
            and not self._prediction.record.effective.postmortem
            and self._prediction.postmortem_completion is None
        )

    def refresh(self) -> None:
        if self._prediction is not None:
            try:
                self.show_prediction(
                    self._operations.one_shots.get(self._prediction.prediction_id)
                )
            except ApplicationError as error:
                self.error.setText(str(error))
                self.error.show()

    def open_values(self, *, correction: bool) -> None:
        if not self.workspace.prepare_task(
            "Correct Transcription" if correction else "Add Answer"
        ):
            return
        self._dialog = OneShotEditDialog(
            self._operations, self._prediction, correction=correction, parent=self
        )
        self._dialog.saved.connect(self.show_prediction)
        self._dialog.open()

    def open_metadata(self) -> None:
        if not self.workspace.prepare_task("Edit Details"):
            return
        self._dialog = EditPredictionDetailsDialog(
            self._operations, self._prediction, self
        )
        self._dialog.metadata_saved.connect(self.show_prediction)
        self._dialog.open()

    def correct_invalid_reason(self) -> None:
        if self._prediction is None or self._prediction.invalidation_history is None:
            return
        self._dialog = CorrectInvalidationReasonDialog(
            self._operations, self._prediction.invalidation_history, self
        )
        self._dialog.correction_saved.connect(lambda _history: self.refresh())
        self._dialog.open()

    def open_journal(self) -> None:
        if self._prediction is None or not self.workspace.prepare_task("Journal"):
            return
        current = self._prediction
        editor = BodyEditor(
            "Add Journal entry",
            "",
            lambda body: self._operations.one_shots.add_journal(current, body),
            self,
        )
        editor.saved.connect(self.show_prediction)
        self.workspace.begin_editor(editor, "Journal")

    def invalidate(self) -> None:
        if self._prediction is None or not self.workspace.prepare_task("Mark Invalid"):
            return
        current = self._prediction
        editor = BodyEditor(
            "Mark Invalid",
            "",
            lambda reason: self._operations.one_shots.invalidate(
                current, reason=reason
            ),
            self,
            terminal=True,
        )
        editor.setProperty("reviewedQuestion", current.question)
        editor.setProperty(
            "reviewedForecast",
            forecast_text(
                current.record.effective,
                current.record.definition.unit if current.record.definition else "",
            ),
        )
        editor.saved.connect(self.show_prediction)
        self.workspace.begin_editor(editor, "Mark Invalid")

    def delete(self) -> None:
        if not self.workspace.prepare_task("Delete"):
            return
        if (
            QMessageBox.warning(
                self,
                "Delete One-Shot",
                "Permanently delete this untouched One-Shot?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._operations.one_shots.delete(self._prediction, confirmed=True)
            self.show_prediction(None)
        except ApplicationError as error:
            self.error.setText(str(error))
            self.error.show()
