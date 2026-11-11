"""Prediction detail responsibilities extracted from the desktop composition."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.reflection import save_postmortem
from reckonsolve.domain.one_shot import (
    OneShotDetail,
    OneShotJournal,
    OneShotSourceAction,
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
from reckonsolve.ui.components import (
    ContentPanel,
)
from reckonsolve.ui.contextual_forms import BodyEditor
from reckonsolve.ui.detail_workspace import DetailWorkspace, collapse_section
from reckonsolve.ui.layouts import FlowLayout
from reckonsolve.ui.numeric_interval import NumericInterval
from reckonsolve.ui.one_shot import OneShotEditDialog, text_label
from reckonsolve.ui.prediction_dialogs import (
    CorrectInvalidationReasonDialog,
    EditPredictionDetailsDialog,
)
from reckonsolve.ui.prediction_widgets import (
    _collapsible_history_group,
    _definition_change_widget,
    _focus_search_widget,
    _format_local_timestamp,
    _history_content,
    _one_shot_journal_timeline_widget,
)
from reckonsolve.ui.reflection_editor import ReflectionEditor
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    ActionRole,
    StatusTone,
    SurfaceRole,
    TextRole,
    apply_action_role,
    apply_message_role,
    apply_surface_role,
    apply_text_role,
)


class OneShotDetailScreen(QWidget):
    """One saved guess with a separate original and correction history."""

    def __init__(self, operations, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._operations = operations
        self._prediction: OneShotDetail | None = None
        self._dialog = None
        self.content = QWidget(self)
        self.content_layout = QVBoxLayout(self.content)
        self.workspace = DetailWorkspace(self.content, self)
        self.workspace.single_column = True
        self.workspace.task_closed.connect(self._restore_reflection_actions)
        self.workspace.tabs.hide()
        self.scroll = self.workspace
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scroll)

    def show_prediction(self, detail: OneShotDetail | None) -> None:
        self._prediction = detail
        self.workspace.clear_reading()
        if detail is None:
            self.content_layout.addWidget(text_label("The One-Shot was deleted.", self))
            return
        record = detail.record
        unit = record.definition.unit if record.definition else ""
        summary = QWidget(self)
        header = QVBoxLayout(summary)
        header.setContentsMargins(0, 0, 0, 0)
        self.question = text_label(detail.question, summary)
        self.question.setObjectName("oneShotQuestion")
        apply_text_role(self.question, TextRole.QUESTION)
        header.addWidget(self.question)
        header.addWidget(
            text_label(
                f"{record.contract.prediction_type.value.capitalize()} · One-Shot · {status_text(detail)}",
                summary,
            )
        )
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
        self.forecast = text_label(forecast_text(record.effective, unit), summary)
        self.forecast.setObjectName("oneShotForecast")
        apply_text_role(self.forecast, TextRole.FORECAST)
        if record.effective.quantiles is not None:
            self.interval = NumericInterval(summary)
            self.interval.set_forecast(record.effective.quantiles, unit)
            header.addWidget(self.interval)
            self.forecast.hide()
            header.addWidget(
                text_label(
                    "90% interval · 50% interval · Median"
                    + (f" · {unit}" if unit else ""),
                    summary,
                )
            )
        else:
            header.addWidget(self.forecast)
        header.addWidget(
            text_label(
                "Saved One-Shot forecast",
                summary,
            )
        )
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
        self.journal_button = QPushButton("Journal", action_panel)
        self.journal_button.setVisible(detail.status is PredictionStatus.OPEN)
        self.journal_button.clicked.connect(self.open_journal)
        actions.addWidget(self.answer_button)
        actions.addWidget(self.journal_button)
        self.more_button = QPushButton("More", action_panel)
        menu = QMenu(self.more_button)
        self.correct_button = menu.addAction(
            "Correct transcription", lambda: self.open_values(correction=True)
        )
        self.edit_button = menu.addAction("Edit Details", self.open_metadata)
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
            else "Waiting for answer"
            if detail.status is PredictionStatus.OPEN
            else "Invalid · Not scored",
            parent=self,
        )
        self.results.setObjectName("oneShotResults")
        if detail.invalidation_history:
            invalid = detail.invalidation_history
            self.results.body_layout.addWidget(
                text_label(
                    f"Invalidated: {_format_local_timestamp(invalid.original.invalidated_at)}\nReason: {invalid.effective.reason or 'Not supplied'}",
                    self,
                )
            )
            if invalid.corrections:
                self.results.body_layout.addWidget(
                    text_label(
                        "Reason corrected: "
                        + _format_local_timestamp(invalid.corrections[-1].corrected_at)
                        + " · Original decision date unchanged",
                        self,
                    )
                )
            correct_reason = QPushButton("Correct Invalid reason", self)
            correct_reason.clicked.connect(self.correct_invalid_reason)
            self.results.body_layout.addWidget(correct_reason)
        else:
            answer_text = next(
                (
                    line
                    for line in values_lines(record.effective, unit)
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
        lines = score_lines(self._operations.one_shots.score(detail), unit)
        if lines:
            score = text_label(lines[0], self)
            apply_text_role(score, TextRole.FORECAST)
            self.scorecard.body_layout.addWidget(score)
            if len(lines) > 1:
                self.scorecard.body_layout.addWidget(
                    collapse_section(
                        text_label("\n".join(lines[1:]), self), "Score breakdown"
                    )
                )
            if record.corrections:
                self.scorecard.body_layout.addWidget(
                    text_label(
                        "Uses effective corrected facts. Originals remain available below.",
                        self,
                    )
                )
        else:
            self.scorecard.hide()
        if detail.status is PredictionStatus.RESOLVED:
            pair = QWidget(self)
            pair_row = QHBoxLayout(pair)
            pair_row.setContentsMargins(0, 0, 0, 0)
            self.results.body_layout.removeWidget(self.answer_result)
            pair_row.addWidget(self.answer_result, 1)
            pair_row.addWidget(self.scorecard, 1)
            self.results.body_layout.addWidget(pair)
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

        self.reflection = ContentPanel("Postmortem", parent=self)
        self.reflection.setVisible(detail.status is PredictionStatus.RESOLVED)
        if record.effective.postmortem:
            self.reflection.body_layout.addWidget(
                text_label(record.effective.postmortem, self)
            )
        self.add_postmortem_button = QPushButton(
            "Edit Postmortem" if record.effective.postmortem else "Write Postmortem",
            self,
        )
        self.add_postmortem_button.clicked.connect(self.add_postmortem)
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
        if detail.postmortem_completion:
            self.reflection.body_layout.addWidget(
                text_label(
                    "Postmortem skipped: "
                    + _format_local_timestamp(
                        detail.postmortem_completion.completed_at
                    ),
                    self,
                )
            )
        self.journals = ContentPanel("Journal entries", parent=self)
        self.journals.setObjectName("oneShotJournalEntries")
        if not detail.journals:
            self.journals.body_layout.addWidget(text_label("No Journal entries.", self))
        self._show_timeline(detail)
        timeline = self.recorded_timeline

        facts = ContentPanel("Recorded facts", parent=self)
        facts.setObjectName("oneShotRecordedFacts")
        facts.body_layout.addWidget(
            text_label(
                "\n".join(
                    line
                    for line in values_lines(record.effective, unit)[1:]
                    if "(user-reported)" in line
                ),
                self,
            )
        )
        facts.body_layout.addWidget(
            text_label(
                "Entered in Reckonsolve: "
                + _format_local_timestamp(record.recorded_at),
                self,
            )
        )
        if record.answer_recorded_at:
            facts.body_layout.addWidget(
                text_label(
                    "Answer entered in Reckonsolve: "
                    + _format_local_timestamp(record.answer_recorded_at),
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
                panel.body_layout.addWidget(text_label(str(value), self))
                overview.append(panel)
        history = _collapsible_history_group(
            "Original facts and transcription corrections",
            "oneShotCorrectionHistory",
            self,
        )
        _, body = _history_content(history)
        history.show()
        body.addWidget(
            text_label(
                "Original saved facts\n"
                + "\n".join(values_lines(record.original, unit)),
                self,
            )
        )
        for correction in record.corrections:
            body.addWidget(
                text_label(
                    f"Correction {correction.sequence} · {_format_local_timestamp(correction.corrected_at)}\nBefore\n"
                    + "\n".join(values_lines(correction.before, unit))
                    + "\nAfter\n"
                    + "\n".join(values_lines(correction.after, unit))
                    + (f"\nNote: {correction.note}" if correction.note else ""),
                    self,
                )
            )
        overview.append(history)
        if detail.definition_changes:
            definitions = _collapsible_history_group(
                "Definition history", "oneShotDefinitionHistory", self
            )
            _, body = _history_content(definitions)
            definitions.show()
            for change in detail.definition_changes:
                body.addWidget(_definition_change_widget(change, self))
            overview.append(definitions)
        for panel in [
            self.results,
            self.scorecard,
            self.reflection,
            self.journals,
            facts,
            *overview[1:],
        ]:
            apply_surface_role(panel, SurfaceRole.CANVAS)
        extras = [widget for widget in overview if widget not in (facts, history)]
        self.workspace.compose(
            summary,
            action_panel,
            [
                self.results,
                self.reflection,
                history,
                *extras,
                self.journals,
                collapse_section(facts, "Reported times and recorded facts"),
                collapse_section(timeline, "Recorded history"),
            ],
            [],
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
                    + "\n".join(values_lines(record.original, unit)[2:]),
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
                    f"Transcription correction {correction.sequence}\n"
                    + "\n".join(values_lines(correction.after, unit))
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
            timestamp = text_label(_format_local_timestamp(occurred_at), card)
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
                "Mark reflection complete without writing a Postmortem? This decision remains in history.",
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
        # The surrounding section supplies the single visible heading.
        editor.findChild(QLabel).hide()

    def _restore_reflection_actions(self, kind: str) -> None:
        if kind != "Postmortem" or self._prediction is None:
            return
        resolved = self._prediction.status is PredictionStatus.RESOLVED
        self.add_postmortem_button.setVisible(resolved)
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
            "Correct transcription" if correction else "Add Answer"
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
