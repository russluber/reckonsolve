"""Prediction dialogs responsibilities extracted from the desktop composition."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDateEdit,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import (
    ApplicationError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.domain.one_shot import OneShotDetail
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    BinaryResolutionHistory,
    FixedPrecisionValue,
    InvalidationHistory,
    NumericResolutionHistory,
    PredictionValidationError,
)
from reckonsolve.domain.quantiles import QuantileTimelineEvent
from reckonsolve.forecast_display import (
    format_local_deadline,
    format_readable_local_deadline,
)
from reckonsolve.ui.components import ProbabilityPresets
from reckonsolve.ui.detail_workspace import collapse_section
from reckonsolve.ui.dialog_review import DialogReview, confirm_contextual_terminal
from reckonsolve.ui.editor_feedback import show_editor_error
from reckonsolve.ui.effective_time_input import EffectiveTimeInput
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.prediction_contracts import (
    JournalTimelineSnapshot,
    NumericPredictionSnapshot,
    PredictionOperations,
    PredictionSnapshot,
)
from reckonsolve.ui.prediction_widgets import (
    _confirm_terminal_correction,
    _create_optional_date_controls,
    _date_input_row,
    _dialog_error_label,
    _EffectiveTimeDialog,
    _make_selectable,
    _MultilineSubmitKeyFilter,
    _normalized_optional_text,
    _numeric_forecast_text,
    _optional_date,
    _parse_tags,
    _save_cancel_buttons,
    _StyledDialog,
)
from reckonsolve.ui.quantile_input import FiveQuantileInput
from reckonsolve.ui.revision_fields import align_numeric_revision
from reckonsolve.ui.visual_system import (
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


class EditPredictionDetailsDialog(_StyledDialog):
    """Edit stable prediction metadata through one complete application operation."""

    metadata_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot | NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("editPredictionDetailsDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Edit Prediction Details")
        self.setModal(True)
        self.resize(620, 600)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._original_question = prediction.question
        self._original_criteria = prediction.resolution_criteria
        self._baseline_metadata_version = prediction.metadata_version

        title = QLabel("Edit Prediction Details", self)
        title.setObjectName("editPredictionDetailsTitle")

        self.numeric_definition_context = QLabel("", self)
        self.numeric_definition_context.setObjectName("editNumericDefinitionContext")
        self.numeric_definition_context.setTextFormat(Qt.TextFormat.PlainText)
        self.numeric_definition_context.setWordWrap(True)
        self.numeric_definition_context.setAccessibleName(
            "Immutable Numeric Prediction definition"
        )
        _make_selectable(self.numeric_definition_context)
        apply_surface_role(
            self.numeric_definition_context,
            SurfaceRole.BASE,
        )
        if hasattr(prediction, "unit") and hasattr(prediction, "decimal_places"):
            decimal_label = (
                "decimal place" if prediction.decimal_places == 1 else "decimal places"
            )
            self.numeric_definition_context.setText(
                "Numeric definition (fixed after creation)\n"
                f"Unit: {prediction.unit}\n"
                f"Precision: {prediction.decimal_places} {decimal_label}"
                f"\nValue constraint: {prediction.value_constraint.value}"
            )
        else:
            self.numeric_definition_context.setHidden(True)

        question_label = QLabel("Question", self)
        self.question_input = QLineEdit(prediction.question, self)
        self.question_input.setObjectName("editQuestionInput")
        self.question_input.setAccessibleName("Question")
        question_label.setBuddy(self.question_input)

        background_label = QLabel("Background (optional)", self)
        self.background_input = QPlainTextEdit(self)
        self.background_input.setObjectName("editBackgroundInput")
        self.background_input.setAccessibleName("Background")
        self.background_input.setPlainText(prediction.background or "")
        self.background_input.setMaximumHeight(110)
        self.background_input.setTabChangesFocus(True)
        background_label.setBuddy(self.background_input)

        criteria_label = QLabel("Resolution Criteria (optional)", self)
        self.resolution_criteria_input = QPlainTextEdit(self)
        self.resolution_criteria_input.setObjectName("editResolutionCriteriaInput")
        self.resolution_criteria_input.setAccessibleName("Resolution criteria")
        self.resolution_criteria_input.setPlainText(
            prediction.resolution_criteria or ""
        )
        self.resolution_criteria_input.setMaximumHeight(110)
        self.resolution_criteria_input.setTabChangesFocus(True)
        criteria_label.setBuddy(self.resolution_criteria_input)

        self.expected_resolution_toggle, self.expected_resolution_input = (
            self._create_optional_date_input(
                "Expected resolution",
                "editExpectedResolutionToggle",
                "editExpectedResolutionInput",
                prediction.expected_resolution,
            )
        )

        tags_label = QLabel("Tags (optional, comma-separated)", self)
        self.tags_input = QLineEdit(", ".join(prediction.tags), self)
        self.tags_input.setObjectName("editTagsInput")
        self.tags_input.setAccessibleName("Tags")
        tags_label.setBuddy(self.tags_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("editDetailsError")
        self.form_error.setAccessibleName("Edit details error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("editDetailsButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("savePredictionDetailsButton")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.SAVE)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelPredictionDetailsButton")

        contract = getattr(prediction, "forecast_contract", None)
        self.exact_deadline_context = QLabel(self)
        self.exact_deadline_context.setWordWrap(True)
        self.exact_deadline_context.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        assert contract is not None
        if contract.is_one_shot:
            self.exact_deadline_context.hide()
            self.question_input.setPlaceholderText("What did you predict?")
            self.background_input.setPlaceholderText(
                "What is the context, and how will you check the answer?"
            )
            # Earlier One-Shots may already contain separate criteria. Retain
            # those facts and their existing protected editing/history behavior.
            criteria_label.setVisible(bool(prediction.resolution_criteria))
            self.resolution_criteria_input.setVisible(
                bool(prediction.resolution_criteria)
            )
            if isinstance(prediction, OneShotDetail) and prediction.record.definition:
                definition = prediction.record.definition
                self.numeric_definition_context.setText(
                    f"Numeric definition (fixed after creation)\nUnit: {definition.unit}\nDecimal places: {definition.decimal_places}\nValue constraint: {definition.value_constraint.value}"
                )
                self.numeric_definition_context.show()
        else:
            self.exact_deadline_context.setText(
                "Forecast deadline: "
                + format_readable_local_deadline(contract.forecast_deadline.instant)
            )
            self.exact_deadline_context.setToolTip(
                "Exact, fixed deadline: "
                + format_local_deadline(contract.forecast_deadline.instant)
            )
        expected_resolution_row = _date_input_row(
            self.expected_resolution_toggle,
            self.expected_resolution_input,
        )
        expected_resolution_row.setVisible(not contract.is_one_shot)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(self.numeric_definition_context)
        layout.addWidget(question_label)
        layout.addWidget(self.question_input)
        layout.addWidget(background_label)
        layout.addWidget(self.background_input)
        layout.addWidget(criteria_label)
        layout.addWidget(self.resolution_criteria_input)
        layout.addWidget(self.exact_deadline_context)
        layout.addWidget(expected_resolution_row)
        layout.addWidget(tags_label)
        layout.addWidget(self.tags_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.setTabOrder(self.question_input, self.background_input)
        self.setTabOrder(self.background_input, self.resolution_criteria_input)
        self.setTabOrder(
            self.resolution_criteria_input,
            self.expected_resolution_toggle,
        )
        self.setTabOrder(
            self.expected_resolution_toggle,
            self.expected_resolution_input,
        )
        self.setTabOrder(self.expected_resolution_input, self.tags_input)
        self.setTabOrder(self.tags_input, save_button)
        self.review = DialogReview(self, self.buttons)
        self.question_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Save once, asking for confirmation only when the operation requires it."""
        self._hide_error()
        confirmed = self.review.active and self.review.consent_matches()
        try:
            prediction = self._save(confirm_meaning_change=confirmed)
        except MeaningChangeConfirmationRequired:
            self.review.show(
                "Review Definition change\n\nOriginal Question:\n"
                + self._original_question
                + "\n\nProposed Question:\n"
                + self.question_input.text()
                + "\n\nOriginal criteria:\n"
                + (self._original_criteria or "Not recorded")
                + "\n\nProposed criteria:\n"
                + (self.resolution_criteria_input.toPlainText() or "Not recorded")
                + "\n\nThis appends a Definition snapshot; earlier wording remains in history. "
                "Clarify the existing meaning only. For a materially different target or checking method, mark Invalid and create a new prediction.",
                "Confirm Definition change",
            )
            return
        except ApplicationError as error:
            self._show_error(str(error))
            return

        self.metadata_saved.emit(prediction)
        self.accept()

    def _save(
        self,
        *,
        confirm_meaning_change: bool,
    ) -> PredictionSnapshot | NumericPredictionSnapshot:
        return self._operations.update_metadata(
            self._prediction_id,
            question=self.question_input.text(),
            background=self.background_input.toPlainText(),
            resolution_criteria=self.resolution_criteria_input.toPlainText(),
            forecast_deadline=None,
            expected_resolution=_optional_date(
                self.expected_resolution_toggle,
                self.expected_resolution_input,
            ),
            tags=_parse_tags(self.tags_input.text()),
            expected_metadata_version=self._baseline_metadata_version,
            confirm_meaning_change=confirm_meaning_change,
        )

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)

    def _create_optional_date_input(
        self,
        label: str,
        toggle_name: str,
        input_name: str,
        value: date | None,
    ) -> tuple[QCheckBox, QDateEdit]:
        return _create_optional_date_controls(
            self,
            label,
            toggle_name,
            input_name,
            value,
        )


class ReviseForecastDialog(_StyledDialog):
    """Collect a new probability and append exactly one forecast revision."""

    revision_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("reviseForecastDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Revise Forecast")
        self.setModal(True)
        self.resize(520, 390)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Revise Forecast", self)
        title.setObjectName("reviseForecastTitle")

        current_heading = QLabel("Current forecast", self)
        self.current_probability = QLabel(
            f"{prediction.probability_percent}%",
            self,
        )
        self.current_probability.setObjectName("reviseCurrentProbability")
        self.current_probability.setAccessibleName("Current forecast")
        current_font = QFont(self.current_probability.font())
        current_font.setBold(True)
        current_font.setPointSize(current_font.pointSize() + 3)
        self.current_probability.setFont(current_font)

        probability_label = QLabel("New forecast", self)
        self.probability_input = QSpinBox(self)
        self.probability_input.setObjectName("revisionProbabilityInput")
        self.probability_input.setAccessibleName("New forecast probability")
        self.probability_input.setRange(0, 100)
        self.probability_input.setSuffix("%")
        self.probability_input.setValue(prediction.probability_percent)
        probability_label.setBuddy(self.probability_input)

        shortcuts = ProbabilityPresets(
            self.probability_input, self, name_prefix="revisionProbability", wrap=True
        )

        self.endpoint_note = QLabel(
            "0% and 100% express absolute certainty.",
            self,
        )
        self.endpoint_note.setObjectName("revisionProbabilityEndpointNote")
        self.endpoint_note.setWordWrap(True)

        rationale_label = QLabel("What changed? (optional)", self)
        rationale_helper_text = (
            "This explanation stays attached to the new forecast. To record a "
            "thought without changing probability, add a Journal entry."
        )
        rationale_helper = QLabel(rationale_helper_text, self)
        rationale_helper.setObjectName("revisionRationaleHelper")
        rationale_helper.setTextFormat(Qt.TextFormat.PlainText)
        rationale_helper.setWordWrap(True)
        self.rationale_input = QPlainTextEdit(self)
        self.rationale_input.setObjectName("revisionRationaleInput")
        self.rationale_input.setAccessibleName("What changed")
        self.rationale_input.setAccessibleDescription(rationale_helper_text)
        self.rationale_input.setMaximumHeight(110)
        self.rationale_input.setTabChangesFocus(True)
        rationale_label.setBuddy(self.rationale_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("reviseForecastError")
        self.form_error.setAccessibleName("Revise forecast error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("reviseForecastButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("saveForecastRevisionButton")
        save_button.setText("Save Revision")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.SAVE)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelForecastRevisionButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(current_heading)
        layout.addWidget(self.current_probability)
        contract = getattr(prediction, "forecast_contract", None)
        if contract is not None:
            deadline_note = QLabel(
                "Forecast deadline: "
                + format_readable_local_deadline(contract.forecast_deadline.instant),
                self,
            )
            deadline_note.setWordWrap(True)
            deadline_note.setObjectName("revisionExactDeadline")
            deadline_note.setToolTip(
                "Exact, fixed deadline: "
                + format_local_deadline(contract.forecast_deadline.instant)
            )
            apply_text_role(deadline_note, TextRole.SECONDARY)
            layout.addWidget(deadline_note)
        layout.addSpacing(8)
        layout.addWidget(probability_label)
        layout.addWidget(self.probability_input)
        layout.addWidget(shortcuts)
        layout.addWidget(self.endpoint_note)
        layout.addWidget(rationale_label)
        layout.addWidget(self.rationale_input)
        layout.addWidget(rationale_helper)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.setTabOrder(self.probability_input, self.rationale_input)
        self.setTabOrder(self.rationale_input, save_button)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.probability_input.valueChanged.connect(self._update_endpoint_note)
        self._update_endpoint_note(self.probability_input.value())
        self.probability_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.probability_input.selectAll()

    def submit(self) -> None:
        """Invoke the append operation; expected failures remain in the dialog."""
        self._hide_error()
        try:
            prediction = self._operations.revise_forecast(
                self._prediction_id,
                self.probability_input.value(),
                rationale=self.rationale_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            show_editor_error(self, error, self.form_error)
            return
        self.revision_saved.emit(prediction)
        self.accept()

    def _update_endpoint_note(self, probability: int) -> None:
        self.endpoint_note.setHidden(probability not in (0, 100))

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class ReviseQuantileForecastDialog(_StyledDialog):
    """Edit a complete prospective Numeric forecast without changing its definition."""

    revision_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("reviseQuantileForecastDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Revise Numeric Forecast")
        self.setModal(True)
        self.resize(620, 730)
        self._operations, self._prediction = operations, prediction
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(scroll)
        layout = QVBoxLayout(content)
        title = QLabel("Revise Numeric Forecast", content)
        title.setWordWrap(True)
        apply_text_role(title, TextRole.PAGE_TITLE)
        layout.addWidget(title)
        context = QLabel(
            "Change any values; saving appends all five percentiles. Equal adjacent values are valid.\nForecast deadline: "
            + format_readable_local_deadline(
                prediction.forecast_contract.forecast_deadline.instant
            ),
            content,
        )
        context.setWordWrap(True)
        context.setToolTip(
            "Exact, fixed deadline: "
            + format_local_deadline(
                prediction.forecast_contract.forecast_deadline.instant
            )
        )
        layout.addWidget(context)
        self.quantile_input = FiveQuantileInput(content)
        self.quantile_input.set_definition(
            prediction.unit, prediction.decimal_places, prediction.value_constraint
        )
        self.quantile_input.set_quantiles(prediction.current_revision.quantiles)
        align_numeric_revision(
            self.quantile_input, prediction.current_revision.quantiles
        )
        layout.addWidget(self.quantile_input)
        layout.addWidget(QLabel("What changed? (optional)", content))
        self.rationale_input = QPlainTextEdit(content)
        self.rationale_input.setAccessibleName("Optional reason for forecast revision")
        self.rationale_input.setMaximumHeight(100)
        self.rationale_input.setTabChangesFocus(True)
        layout.addWidget(self.rationale_input)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.form_error = _dialog_error_label("reviseQuantileError", self)
        outer.addWidget(self.form_error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        save = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setText("Save Forecast Revision")
        apply_action_role(save, ActionRole.PRIMARY)
        apply_lucide_icon(save, LucideIcon.SAVE)
        apply_action_role(
            self.buttons.button(QDialogButtonBox.StandardButton.Cancel),
            ActionRole.SECONDARY,
        )
        outer.addWidget(self.buttons)

    def submit(self) -> None:
        try:
            saved = self._operations.revise_quantile_forecast(
                self._prediction.prediction_id,
                self.quantile_input.values(),
                expected_revision_id=self._prediction.current_revision.revision_id,
                expected_metadata_version=self._prediction.metadata_version,
                rationale=self.rationale_input.toPlainText(),
            )
        except ApplicationError as error:
            show_editor_error(self, error, self.form_error)
            return
        self.revision_saved.emit(saved)
        self.accept()


class AddNumericJournalEntryDialog(_StyledDialog):
    """Append reasoning while preserving the current numeric interval."""

    journal_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("addNumericJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Add Journal Entry")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version
        title = QLabel("Add Journal Entry", self)
        context = QLabel(
            f"Forecast at the time: {_numeric_forecast_text(prediction.current_revision, prediction.unit)}",
            self,
        )
        context.setObjectName("numericJournalForecastAtTime")
        context.setTextFormat(Qt.TextFormat.PlainText)
        context.setWordWrap(True)
        body_label = QLabel("Journal entry", self)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("numericJournalEntryBodyInput")
        self.body_input.setAccessibleName("Journal entry")
        self.body_input.setTabChangesFocus(True)
        body_label.setBuddy(self.body_input)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("addNumericJournalEntryError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericJournalEntryButton")
        save.setText("Add Entry")
        apply_lucide_icon(save, LucideIcon.SAVE)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(context)
        layout.addWidget(body_label)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        self._hide_error()
        if not self.body_input.toPlainText().strip():
            self._show_error("Write a Journal entry before saving.")
            return
        try:
            entry = self._operations.add_numeric_journal_entry(
                self._prediction_id,
                self.body_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.journal_saved.emit(entry)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class ResolveNumericPredictionDialog(_StyledDialog):
    """Record one exact, immutable Numeric outcome and scoring interval."""

    prediction_resolved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("resolveNumericPredictionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Resolve Numeric Prediction")
        self.setModal(True)
        self.resize(580, 520)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version
        self.effective_time = EffectiveTimeInput(self)

        title = QLabel("Resolve Numeric Prediction", self)
        explanation = QLabel(
            "Resolution is a one-way terminal decision. WIS uses the last forecast strictly before the earlier of the effective outcome time and Deadline, not necessarily the latest displayed forecast. Earlier facts and later corrections remain in history.",
            self,
        )
        explanation.setObjectName("resolveNumericPredictionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        reviewed = QLabel(
            f"Scoring forecast: {_numeric_forecast_text(prediction.current_revision, prediction.unit)} "
            f"(revision {prediction.current_revision.sequence})",
            self,
        )
        reviewed.setObjectName("resolveNumericScoringForecast")
        if self.effective_time is not None:
            reviewed.setText(
                f"Reviewed current forecast: {_numeric_forecast_text(prediction.current_revision, prediction.unit)} (revision {prediction.current_revision.sequence})\nValue constraint: {prediction.value_constraint.value}"
            )
        reviewed.setTextFormat(Qt.TextFormat.PlainText)
        reviewed.setWordWrap(True)
        actual_label = QLabel(f"Actual value ({prediction.unit})", self)
        self.actual_value_input = QLineEdit(self)
        self.actual_value_input.setObjectName("numericResolutionActualValueInput")
        self.actual_value_input.setAccessibleName(f"Actual value in {prediction.unit}")
        actual_label.setBuddy(self.actual_value_input)
        notes_label = QLabel("Resolution notes (optional)", self)
        self.resolution_notes_input = QPlainTextEdit(self)
        self.resolution_notes_input.setObjectName("numericResolutionNotesInput")
        self.resolution_notes_input.setMaximumHeight(100)
        self.resolution_notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.resolution_notes_input)
        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("numericResolutionPostmortemInput")
        self.postmortem_input.setMaximumHeight(100)
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("resolveNumericPredictionError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericResolutionButton")
        save.setText("Resolve Prediction")
        apply_lucide_icon(save, LucideIcon.CIRCLE_CHECK)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "cancelNumericResolutionButton"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reviewed)
        layout.addSpacing(8)
        layout.addWidget(actual_label)
        layout.addWidget(self.actual_value_input)
        if self.effective_time is not None:
            layout.addWidget(self.effective_time)
        layout.addWidget(notes_label)
        layout.addWidget(self.resolution_notes_input)
        postmortem_label.hide()
        layout.addWidget(
            collapse_section(self.postmortem_input, "Postmortem (optional)")
        )
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.actual_value_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        self.form_error.setHidden(True)
        try:
            if not confirm_contextual_terminal(
                self,
                "Resolve",
                "Actual value: "
                + self.actual_value_input.text()
                + "\nOutcome known: "
                + (
                    "At the actual save time"
                    if self.effective_time is None
                    or self.effective_time.use_now.isChecked()
                    else str(self.effective_time.value())
                ),
            ):
                return
            prediction = self._operations.resolve_numeric_prediction(
                self._prediction_id,
                self.actual_value_input.text(),
                resolution_notes=self.resolution_notes_input.toPlainText(),
                postmortem=self.postmortem_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
                **(
                    {}
                    if self.effective_time is None
                    else {
                        "effective_resolution_at": self.effective_time.value(),
                        "use_recorded_time": self.effective_time.use_now.isChecked(),
                    }
                ),
            )
        except ApplicationError as error:
            self.form_error.setText(str(error))
            self.form_error.setHidden(False)
            return
        self.prediction_resolved.emit(prediction)
        self.accept()


class MarkNumericPredictionInvalidDialog(_StyledDialog):
    """Record one immutable Numeric Invalid decision and optional reason."""

    prediction_invalidated = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("markNumericPredictionInvalidDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Mark Numeric Prediction Invalid")
        self.setModal(True)
        self.resize(560, 360)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision.revision_id
        self._expected_metadata_version = prediction.metadata_version
        title = QLabel("Mark Numeric Prediction Invalid", self)
        explanation = QLabel(
            "Invalid preserves this prediction and its complete history but "
            "excludes it from scoring. The terminal decision cannot be reopened; "
            "its reason can later be corrected with visible history.",
            self,
        )
        explanation.setObjectName("markNumericInvalidExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        reason_label = QLabel("Reason (optional)", self)
        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setObjectName("numericInvalidationReasonInput")
        self.reason_input.setTabChangesFocus(True)
        reason_label.setBuddy(self.reason_input)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("markNumericPredictionInvalidError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericInvalidationButton")
        save.setText("Mark Invalid")
        apply_lucide_icon(save, LucideIcon.BAN)
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setObjectName(
            "cancelNumericInvalidationButton"
        )
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        self.form_error.setHidden(True)
        try:
            if not confirm_contextual_terminal(
                self,
                "Mark Invalid",
                "Not scored.\nReason: "
                + (self.reason_input.toPlainText() or "Not recorded"),
            ):
                return
            prediction = self._operations.invalidate_numeric_prediction(
                self._prediction_id,
                reason=self.reason_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self.form_error.setText(str(error))
            self.form_error.setHidden(False)
            return
        self.prediction_invalidated.emit(prediction)
        self.accept()


class CorrectBinaryResolutionDialog(_EffectiveTimeDialog):
    """Append one confirmed Binary Resolution correction snapshot."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        history: BinaryResolutionHistory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctBinaryResolutionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Resolution")
        self.setModal(True)
        self.resize(600, 620)
        self._operations = operations
        self._prediction_id = history.original.prediction_id
        self._expected_correction_id = history.current_correction_id
        self._current = history.effective
        self.effective_time = (
            EffectiveTimeInput(self, self._current.effective_resolution_at)
            if self._current.effective_resolution_at is not None
            else None
        )

        title = QLabel("Correct Resolution", self)
        explanation = QLabel(
            "This appends a transparent correction. The original Resolution, "
            "resolution time, scoring forecast, and every earlier correction "
            "remain in history.",
            self,
        )
        explanation.setObjectName("binaryResolutionCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        if self.effective_time is not None:
            explanation.setText(
                "Append a correction without changing recorded-at or any earlier history. Correcting effective time may change which forecasts are scored."
            )

        outcome_label = QLabel("Effective outcome", self)
        self.outcome_yes = QRadioButton("Yes", self)
        self.outcome_yes.setObjectName("correctResolutionOutcomeYes")
        self.outcome_no = QRadioButton("No", self)
        self.outcome_no.setObjectName("correctResolutionOutcomeNo")
        if self._current.outcome is BinaryOutcome.YES:
            self.outcome_yes.setChecked(True)
        else:
            self.outcome_no.setChecked(True)
        outcome_row = QWidget(self)
        outcome_layout = QHBoxLayout(outcome_row)
        outcome_layout.setContentsMargins(0, 0, 0, 0)
        outcome_layout.addWidget(self.outcome_yes)
        outcome_layout.addWidget(self.outcome_no)
        outcome_layout.addStretch()

        self.score_change_notice = QLabel(
            "Changing the outcome changes this Prediction's Brier score and "
            "calibration result. A correction explanation is required.",
            self,
        )
        self.score_change_notice.setObjectName("binaryResolutionScoreChangeNotice")
        self.score_change_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.score_change_notice.setWordWrap(True)
        if self.effective_time is not None:
            self.score_change_notice.setText(
                "Changing the outcome or effective time recomputes trajectory scoring and final forecast selection. An explanation is required."
            )

        notes_label = QLabel("Resolution notes (optional)", self)
        self.notes_input = QPlainTextEdit(self)
        self.notes_input.setObjectName("correctResolutionNotesInput")
        self.notes_input.setPlainText(self._current.resolution_notes or "")
        self.notes_input.setMaximumHeight(110)
        self.notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.notes_input)

        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("correctResolutionPostmortemInput")
        self.postmortem_input.setPlainText(self._current.postmortem or "")
        self.postmortem_input.setMaximumHeight(110)
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)

        reason_label = QLabel("Correction explanation", self)
        self.reason_input = QLineEdit(self)
        self.reason_input.setObjectName("binaryOutcomeCorrectionReasonInput")
        self.reason_input.setPlaceholderText(
            "Required only when changing Yes to No or No to Yes"
        )
        if self.effective_time is not None:
            self.reason_input.setPlaceholderText(
                "Required when changing outcome or effective time"
            )
        reason_label.setBuddy(self.reason_input)

        self.form_error = _dialog_error_label(
            "correctBinaryResolutionError",
            self,
        )
        self.buttons = _save_cancel_buttons(
            "saveBinaryResolutionCorrectionButton",
            "Save Correction",
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addSpacing(8)
        layout.addWidget(outcome_label)
        layout.addWidget(outcome_row)
        if self.effective_time is not None:
            layout.addWidget(self.effective_time)
        layout.addWidget(self.score_change_notice)
        layout.addWidget(notes_label)
        layout.addWidget(self.notes_input)
        layout.addWidget(postmortem_label)
        layout.addWidget(self.postmortem_input)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.outcome_yes.toggled.connect(self._update_score_change_notice)
        self.outcome_no.toggled.connect(self._update_score_change_notice)
        if self.effective_time is not None:
            self.effective_time.editor.dateTimeChanged.connect(
                self._update_score_change_notice
            )
            self.effective_time.offset.textChanged.connect(
                self._update_score_change_notice
            )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._update_score_change_notice()

    def submit(self) -> None:
        self.form_error.setHidden(True)
        outcome = (
            BinaryOutcome.YES if self.outcome_yes.isChecked() else BinaryOutcome.NO
        )
        notes = _normalized_optional_text(self.notes_input.toPlainText())
        postmortem = _normalized_optional_text(self.postmortem_input.toPlainText())
        correction_reason = _normalized_optional_text(self.reason_input.text())
        outcome_changed = outcome is not self._current.outcome
        try:
            effective_at = (
                None if self.effective_time is None else self.effective_time.value()
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        time_changed = effective_at != self._current.effective_resolution_at
        if (
            outcome is self._current.outcome
            and notes == self._current.resolution_notes
            and postmortem == self._current.postmortem
            and not time_changed
        ):
            self._show_error(
                "Change the outcome, notes, Postmortem, or effective time before saving."
                if self.effective_time is not None
                else "Change the outcome, notes, or Postmortem before saving."
            )
            return
        if (outcome_changed or time_changed) and correction_reason is None:
            self._show_error(
                "Explain why the outcome or effective time is being corrected."
            )
            self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        reflection_only = (
            bool(postmortem)
            and postmortem != self._current.postmortem
            and not outcome_changed
            and not time_changed
            and notes == self._current.resolution_notes
        )
        if not reflection_only and not _confirm_terminal_correction(
            self, score_affecting=outcome_changed or time_changed
        ):
            return
        try:
            history = self._operations.correct_binary_resolution(
                self._prediction_id,
                outcome,
                resolution_notes=notes,
                postmortem=postmortem,
                correction_reason=correction_reason,
                expected_correction_id=self._expected_correction_id,
                **(
                    {"effective_resolution_at": effective_at}
                    if self.effective_time is not None
                    else {}
                ),
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(history)
        self.accept()

    def _update_score_change_notice(self) -> None:
        selected = (
            BinaryOutcome.YES if self.outcome_yes.isChecked() else BinaryOutcome.NO
        )
        try:
            time_changed = (
                self.effective_time is not None
                and self.effective_time.value() != self._current.effective_resolution_at
            )
        except ApplicationError:
            time_changed = True
        self.score_change_notice.setHidden(
            selected is self._current.outcome and not time_changed
        )

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)


class CorrectNumericResolutionDialog(_EffectiveTimeDialog):
    """Append one confirmed exact Numeric Resolution correction snapshot."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: NumericPredictionSnapshot,
        history: NumericResolutionHistory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctNumericResolutionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Numeric Resolution")
        self.setModal(True)
        self.resize(600, 620)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._unit = prediction.unit
        self._decimal_places = prediction.decimal_places
        self._expected_correction_id = history.current_correction_id
        self._current = history.effective
        self.effective_time = EffectiveTimeInput(
            self, self._current.effective_resolution_at
        )

        title = QLabel("Correct Numeric Resolution", self)
        explanation = QLabel(
            "This appends a transparent correction. Original actual value, effective time, recorded-at, and all forecast history remain intact. Correcting effective time can change which forecast is scored; recorded-at cannot change.",
            self,
        )
        explanation.setObjectName("numericResolutionCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        actual_label = QLabel(f"Effective actual value ({prediction.unit})", self)
        self.actual_value_input = QLineEdit(self)
        self.actual_value_input.setObjectName("correctNumericActualValueInput")
        self.actual_value_input.setText(str(self._current.actual_value))
        actual_label.setBuddy(self.actual_value_input)
        self.score_change_notice = QLabel(
            "Changing the actual value changes containment, error, and interval "
            "score results. A correction explanation is required.",
            self,
        )
        self.score_change_notice.setObjectName("numericResolutionScoreChangeNotice")
        if self.effective_time is not None:
            self.score_change_notice.setText(
                "Changing actual value or effective time can change WIS, scoring selection, and eligibility. An explanation is required."
            )
        self.score_change_notice.setTextFormat(Qt.TextFormat.PlainText)
        self.score_change_notice.setWordWrap(True)

        notes_label = QLabel("Resolution notes (optional)", self)
        self.notes_input = QPlainTextEdit(self)
        self.notes_input.setObjectName("correctNumericResolutionNotesInput")
        self.notes_input.setPlainText(self._current.resolution_notes or "")
        self.notes_input.setMaximumHeight(110)
        self.notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.notes_input)

        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("correctNumericResolutionPostmortemInput")
        self.postmortem_input.setPlainText(self._current.postmortem or "")
        self.postmortem_input.setMaximumHeight(110)
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)

        reason_label = QLabel("Correction explanation", self)
        self.reason_input = QLineEdit(self)
        self.reason_input.setObjectName("numericOutcomeCorrectionReasonInput")
        self.reason_input.setPlaceholderText(
            "Required when changing actual value or effective time"
            if self.effective_time is not None
            else "Required only when changing the actual value"
        )
        reason_label.setBuddy(self.reason_input)

        self.form_error = _dialog_error_label(
            "correctNumericResolutionError",
            self,
        )
        self.buttons = _save_cancel_buttons(
            "saveNumericResolutionCorrectionButton",
            "Save Correction",
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addSpacing(8)
        layout.addWidget(actual_label)
        layout.addWidget(self.actual_value_input)
        layout.addWidget(self.score_change_notice)
        if self.effective_time is not None:
            layout.addWidget(self.effective_time)
        layout.addWidget(notes_label)
        layout.addWidget(self.notes_input)
        layout.addWidget(postmortem_label)
        layout.addWidget(self.postmortem_input)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.actual_value_input.textChanged.connect(self._update_score_change_notice)
        if self.effective_time is not None:
            self.effective_time.editor.dateTimeChanged.connect(
                self._update_score_change_notice
            )
            self.effective_time.offset.textChanged.connect(
                self._update_score_change_notice
            )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._update_score_change_notice()

    def submit(self) -> None:
        self.form_error.setHidden(True)
        try:
            actual_value = FixedPrecisionValue.from_value(
                self.actual_value_input.text(),
                self._decimal_places,
                field="actual_value",
            )
        except PredictionValidationError as error:
            self._show_error(str(error))
            return
        notes = _normalized_optional_text(self.notes_input.toPlainText())
        postmortem = _normalized_optional_text(self.postmortem_input.toPlainText())
        correction_reason = _normalized_optional_text(self.reason_input.text())
        actual_changed = actual_value != self._current.actual_value
        try:
            effective_time = (
                self.effective_time.value() if self.effective_time is not None else None
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        time_changed = effective_time != self._current.effective_resolution_at
        if (
            not actual_changed
            and not time_changed
            and notes == self._current.resolution_notes
            and postmortem == self._current.postmortem
        ):
            self._show_error(
                "Change the actual value, Resolution notes, or Postmortem before "
                "saving."
            )
            return
        if (actual_changed or time_changed) and correction_reason is None:
            self._show_error(
                "Explain why the actual value or effective resolution time is being corrected."
            )
            self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        reflection_only = (
            bool(postmortem)
            and postmortem != self._current.postmortem
            and not actual_changed
            and not time_changed
            and notes == self._current.resolution_notes
        )
        if not reflection_only and not _confirm_terminal_correction(
            self, score_affecting=actual_changed or time_changed
        ):
            return
        try:
            history = self._operations.correct_numeric_resolution(
                self._prediction_id,
                self.actual_value_input.text(),
                resolution_notes=notes,
                postmortem=postmortem,
                correction_reason=correction_reason,
                expected_correction_id=self._expected_correction_id,
                effective_resolution_at=effective_time,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(history)
        self.accept()

    def _update_score_change_notice(self) -> None:
        try:
            proposed = FixedPrecisionValue.from_value(
                self.actual_value_input.text(),
                self._decimal_places,
                field="actual_value",
            )
        except PredictionValidationError:
            self.score_change_notice.setHidden(False)
            self._fit_time_form()
            return
        try:
            time_changed = (
                self.effective_time is not None
                and self.effective_time.value() != self._current.effective_resolution_at
            )
        except ApplicationError:
            time_changed = True
        self.score_change_notice.setHidden(
            proposed == self._current.actual_value and not time_changed
        )
        self._fit_time_form()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)
        self._fit_time_form()


class CorrectInvalidationReasonDialog(_StyledDialog):
    """Append one confirmed Invalidation-reason correction."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        history: InvalidationHistory,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctInvalidationReasonDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Invalid Reason")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = history.original.prediction_id
        self._expected_correction_id = history.current_correction_id
        self._current_reason = history.effective.reason

        title = QLabel("Correct Invalid Reason", self)
        explanation = QLabel(
            "This appends a transparent correction. The Prediction remains "
            "Invalid, and its original reason, invalidation time, and every "
            "earlier correction remain in history.",
            self,
        )
        explanation.setObjectName("invalidationReasonCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        reason_label = QLabel("Effective reason (optional)", self)
        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setObjectName("correctInvalidationReasonInput")
        self.reason_input.setPlainText(self._current_reason or "")
        self.reason_input.setTabChangesFocus(True)
        reason_label.setBuddy(self.reason_input)
        self.form_error = _dialog_error_label(
            "correctInvalidationReasonError",
            self,
        )
        self.buttons = _save_cancel_buttons(
            "saveInvalidationReasonCorrectionButton",
            "Save Correction",
            self,
        )

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)

    def submit(self) -> None:
        self.form_error.setHidden(True)
        reason = _normalized_optional_text(self.reason_input.toPlainText())
        if reason == self._current_reason:
            self._show_error("Change or clear the Invalid reason before saving.")
            return
        if not _confirm_terminal_correction(self, score_affecting=False):
            return
        try:
            history = self._operations.correct_invalidation_reason(
                self._prediction_id,
                reason,
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(history)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)


class CorrectNumericJournalEntryDialog(_StyledDialog):
    """Append a transparent correction to a Numeric Journal entry."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        entry: QuantileTimelineEvent,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctNumericJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Journal Entry")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = entry.prediction_id
        self._entry_id = entry.entry_id
        self._expected_correction_id = entry.current_correction_id
        title = QLabel("Edit / Correct Journal Entry", self)
        explanation = QLabel(
            "Saving records a transparent correction. Earlier versions remain in history.",
            self,
        )
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("correctNumericJournalEntryBodyInput")
        self.body_input.setPlainText(entry.body)
        self.body_input.setTabChangesFocus(True)
        self.form_error = QLabel("", self)
        self.form_error.setObjectName("correctNumericJournalEntryError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveNumericJournalCorrectionButton")
        save.setText("Save Correction")
        apply_lucide_icon(save, LucideIcon.SAVE)
        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(buttons)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.body_input.selectAll()

    def submit(self) -> None:
        self._hide_error()
        if not self.body_input.toPlainText().strip():
            self._show_error("Write the corrected Journal entry before saving.")
            return
        try:
            correction = self._operations.correct_numeric_journal_entry(
                self._prediction_id,
                self._entry_id,
                self.body_input.toPlainText(),
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(correction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class ForecastReviewDialog(_StyledDialog):
    """Record deliberate reconsideration without changing the forecast."""

    review_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot | NumericPredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("forecastReviewDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(True)
        self.resize(540, 330)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_metadata_version = prediction.metadata_version
        self._is_numeric = hasattr(prediction, "current_revision")
        if self._is_numeric:
            numeric = prediction
            revision = numeric.current_revision
            self._expected_revision_id = revision.revision_id
            action_text = "Keep current forecast"
            context_text = _numeric_forecast_text(revision, numeric.unit)
            contract = numeric.forecast_contract
        else:
            binary = prediction
            self._expected_revision_id = binary.current_revision_id
            action_text = f"Still at {binary.probability_percent}%"
            context_text = f"{binary.probability_percent}%"
            contract = getattr(binary, "forecast_contract", None)
        if contract is not None:
            context_text += "\nForecast deadline: " + format_readable_local_deadline(
                contract.forecast_deadline.instant
            )
        self.setWindowTitle(action_text)

        title = QLabel(action_text, self)
        title.setObjectName("forecastReviewTitle")
        apply_text_role(title, TextRole.SECTION_TITLE)
        explanation = QLabel(
            "Record that you deliberately reconsidered this forecast and chose to "
            "keep it unchanged.",
            self,
        )
        explanation.setObjectName("forecastReviewExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)
        apply_text_role(explanation, TextRole.SECONDARY)
        context = QLabel(context_text, self)
        context.setObjectName("forecastReviewContext")
        context.setTextFormat(Qt.TextFormat.PlainText)
        if contract is not None:
            context.setToolTip(
                "Exact, fixed deadline: "
                + format_local_deadline(contract.forecast_deadline.instant)
            )
        context.setWordWrap(True)
        apply_text_role(context, TextRole.FORECAST)
        apply_surface_role(context, SurfaceRole.SELECTED)

        note_label = QLabel("Review note (optional)", self)
        self.note_input = QPlainTextEdit(self)
        self.note_input.setObjectName("forecastReviewNoteInput")
        self.note_input.setAccessibleName("Optional Forecast Review note")
        self.note_input.setPlaceholderText(
            "What did you reconsider before retaining this forecast?"
        )
        self.note_input.setTabChangesFocus(True)
        note_label.setBuddy(self.note_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("forecastReviewError")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        apply_message_role(
            self.form_error,
            StatusTone.ERROR,
            accessible_name="Forecast Review error",
        )
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save.setObjectName("saveForecastReviewButton")
        save.setText("Save Review")
        save.setDefault(True)
        apply_action_role(save, ActionRole.PRIMARY)
        apply_lucide_icon(save, LucideIcon.SAVE)
        cancel = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel.setObjectName("cancelForecastReviewButton")
        apply_action_role(cancel, ActionRole.SECONDARY)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(context)
        layout.addSpacing(int(Spacing.CONTROL))
        layout.addWidget(note_label)
        layout.addWidget(self.note_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.note_input.installEventFilter(self._submit_key_filter)

    def submit(self) -> None:
        """Save one immutable Review while retaining expected failures inline."""

        self.form_error.setHidden(True)
        kwargs = {
            "note": self.note_input.toPlainText(),
            "expected_revision_id": self._expected_revision_id,
            "expected_metadata_version": self._expected_metadata_version,
        }
        try:
            if self._is_numeric:
                review = self._operations.add_numeric_forecast_review(
                    self._prediction_id,
                    **kwargs,
                )
            else:
                review = self._operations.add_forecast_review(
                    self._prediction_id,
                    **kwargs,
                )
        except ApplicationError as error:
            self.form_error.setText(str(error))
            self.form_error.setHidden(False)
            return
        self.review_saved.emit(review)
        self.accept()


class AddJournalEntryDialog(_StyledDialog):
    """Append reasoning without changing the current forecast."""

    journal_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("addJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Add Journal Entry")
        self.setModal(True)
        self.resize(560, 390)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Add Journal Entry", self)
        title.setObjectName("addJournalEntryTitle")

        context_heading = QLabel("Forecast at the time", self)
        self.forecast_probability = QLabel(
            f"{prediction.probability_percent}%",
            self,
        )
        self.forecast_probability.setObjectName("journalForecastAtTime")
        self.forecast_probability.setAccessibleName("Forecast at the time")
        context_font = QFont(self.forecast_probability.font())
        context_font.setBold(True)
        context_font.setPointSize(context_font.pointSize() + 2)
        self.forecast_probability.setFont(context_font)

        body_label = QLabel("Journal entry", self)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("journalEntryBodyInput")
        self.body_input.setAccessibleName("Journal entry")
        self.body_input.setPlaceholderText(
            "Record new evidence, reasoning, or a thought that does not change "
            "the forecast."
        )
        self.body_input.setTabChangesFocus(True)
        body_label.setBuddy(self.body_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("addJournalEntryError")
        self.form_error.setAccessibleName("Add journal entry error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("addJournalEntryButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("saveJournalEntryButton")
        save_button.setText("Save Journal Entry")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.SAVE)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelJournalEntryButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(context_heading)
        layout.addWidget(self.forecast_probability)
        layout.addSpacing(8)
        layout.addWidget(body_label)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.setTabOrder(self.body_input, save_button)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def showEvent(self, event: QShowEvent) -> None:
        """Put keyboard focus in the entry body after the modal is shown."""
        super().showEvent(event)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Append one entry; expected failures remain editable in the dialog."""
        self._hide_error()
        body = self.body_input.toPlainText()
        if not body.strip():
            self._show_error("Write a journal entry before saving.")
            self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        try:
            journal_entry = self._operations.add_journal_entry(
                self._prediction_id,
                body,
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.journal_saved.emit(journal_entry)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class CorrectJournalEntryDialog(_StyledDialog):
    """Append a visible correction while retaining every prior Journal body."""

    correction_saved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        entry: JournalTimelineSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("correctJournalEntryDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Correct Journal Entry")
        self.setModal(True)
        self.resize(560, 420)
        self._operations = operations
        self._prediction_id = entry.prediction_id
        self._entry_id = entry.entry_id
        self._expected_correction_id = entry.current_correction_id

        title = QLabel("Edit / Correct Journal Entry", self)
        title.setObjectName("correctJournalEntryTitle")

        explanation = QLabel(
            "Saving records a transparent correction. The original and every "
            "earlier version remain in Edit history.",
            self,
        )
        explanation.setObjectName("journalCorrectionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        context = QLabel(
            f"Forecast at the time: {entry.forecast_probability_percent}%",
            self,
        )
        context.setObjectName("correctionForecastAtTime")
        context.setTextFormat(Qt.TextFormat.PlainText)

        body_label = QLabel("Corrected journal entry", self)
        self.body_input = QPlainTextEdit(self)
        self.body_input.setObjectName("correctJournalEntryBodyInput")
        self.body_input.setAccessibleName("Corrected journal entry")
        self.body_input.setPlainText(entry.body)
        self.body_input.setTabChangesFocus(True)
        body_label.setBuddy(self.body_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("correctJournalEntryError")
        self.form_error.setAccessibleName("Correct journal entry error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("correctJournalEntryButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("saveJournalCorrectionButton")
        save_button.setText("Save Correction")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.SAVE)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelJournalCorrectionButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(context)
        layout.addSpacing(8)
        layout.addWidget(body_label)
        layout.addWidget(self.body_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self.setTabOrder(self.body_input, save_button)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.body_input.installEventFilter(self._submit_key_filter)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.body_input.selectAll()

    def showEvent(self, event: QShowEvent) -> None:
        """Focus and select the displayed latest body when shown."""
        super().showEvent(event)
        self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.body_input.selectAll()

    def submit(self) -> None:
        """Append one correction; never replace the displayed entry in place."""
        self._hide_error()
        body = self.body_input.toPlainText()
        if not body.strip():
            self._show_error("Write the corrected journal entry before saving.")
            self.body_input.setFocus(Qt.FocusReason.ShortcutFocusReason)
            return
        try:
            correction = self._operations.correct_journal_entry(
                self._prediction_id,
                self._entry_id,
                body,
                expected_correction_id=self._expected_correction_id,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.correction_saved.emit(correction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class ResolvePredictionDialog(_EffectiveTimeDialog):
    """Record one deliberate Yes/No terminal outcome."""

    prediction_resolved = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("resolvePredictionDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Resolve Prediction")
        self.setModal(True)
        self.resize(570, 520)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Resolve Prediction", self)
        title.setObjectName("resolvePredictionTitle")
        explanation = QLabel(
            "Resolution records a final Yes/No outcome and the current forecast "
            "for scoring. The terminal decision cannot be reopened; an honest "
            "mistake in its facts can later be corrected with visible history.",
            self,
        )
        explanation.setObjectName("resolvePredictionExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        reviewed = QLabel(
            f"Scoring forecast: {prediction.probability_percent}% "
            f"(revision {prediction.current_revision_sequence})",
            self,
        )
        reviewed.setObjectName("resolveScoringForecast")
        reviewed.setTextFormat(Qt.TextFormat.PlainText)

        contract = getattr(prediction, "forecast_contract", None)
        self.effective_time = None
        if contract is not None:
            self.effective_time = EffectiveTimeInput(self)
            explanation.setText(
                "Record Yes/No and when the outcome became fixed and knowable. Scoring uses that effective time; recorded-at is automatic. Resolution is final, with audited factual corrections available later."
            )
            reviewed.setText(
                f"Current forecast: {prediction.probability_percent}% (revision {prediction.current_revision_sequence}). Trajectory scoring excludes revisions at or after the effective cutoff."
            )
            reviewed.setWordWrap(True)

        outcome_label = QLabel("Outcome", self)
        self.outcome_yes = QRadioButton("Yes", self)
        self.outcome_yes.setObjectName("resolutionOutcomeYes")
        self.outcome_no = QRadioButton("No", self)
        self.outcome_no.setObjectName("resolutionOutcomeNo")
        outcome_row = QWidget(self)
        outcome_layout = QHBoxLayout(outcome_row)
        outcome_layout.setContentsMargins(0, 0, 0, 0)
        outcome_layout.addWidget(self.outcome_yes)
        outcome_layout.addWidget(self.outcome_no)
        outcome_layout.addStretch()

        notes_label = QLabel("Resolution notes (optional)", self)
        self.notes_input = QPlainTextEdit(self)
        self.notes_input.setObjectName("resolutionNotesInput")
        self.notes_input.setAccessibleName("Resolution notes")
        self.notes_input.setPlaceholderText(
            "Record the factual source or evidence that determined the outcome."
        )
        self.notes_input.setTabChangesFocus(True)
        notes_label.setBuddy(self.notes_input)

        postmortem_label = QLabel("Postmortem (optional)", self)
        self.postmortem_input = QPlainTextEdit(self)
        self.postmortem_input.setObjectName("resolutionPostmortemInput")
        self.postmortem_input.setAccessibleName("Postmortem")
        self.postmortem_input.setPlaceholderText(
            "Reflect on what your reasoning or updates got right or wrong."
        )
        self.postmortem_input.setTabChangesFocus(True)
        postmortem_label.setBuddy(self.postmortem_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("resolvePredictionError")
        self.form_error.setAccessibleName("Resolve prediction error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("resolvePredictionButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("confirmResolvePredictionButton")
        save_button.setText("Resolve")
        save_button.setEnabled(False)
        apply_lucide_icon(save_button, LucideIcon.CIRCLE_CHECK)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelResolvePredictionButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addWidget(reviewed)
        if self.effective_time is not None:
            layout.addWidget(self.effective_time)
        layout.addSpacing(8)
        layout.addWidget(outcome_label)
        layout.addWidget(outcome_row)
        layout.addWidget(notes_label)
        layout.addWidget(self.notes_input, 1)
        postmortem_label.hide()
        layout.addWidget(
            collapse_section(self.postmortem_input, "Postmortem (optional)")
        )
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.outcome_yes.toggled.connect(
            lambda _checked: save_button.setEnabled(
                self.outcome_yes.isChecked() or self.outcome_no.isChecked()
            )
        )
        self.outcome_no.toggled.connect(
            lambda _checked: save_button.setEnabled(
                self.outcome_yes.isChecked() or self.outcome_no.isChecked()
            )
        )
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.notes_input.installEventFilter(self._submit_key_filter)
        self.postmortem_input.installEventFilter(self._submit_key_filter)
        self.setTabOrder(self.outcome_yes, self.outcome_no)
        self.setTabOrder(self.outcome_no, self.notes_input)
        self.setTabOrder(self.notes_input, self.postmortem_input)
        self.setTabOrder(self.postmortem_input, save_button)
        self.outcome_yes.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Save exactly one selected outcome; expected failures remain visible."""

        self._hide_error()
        if self.outcome_yes.isChecked():
            outcome = BinaryOutcome.YES
        elif self.outcome_no.isChecked():
            outcome = BinaryOutcome.NO
        else:
            self._show_error("Choose Yes or No before resolving this prediction.")
            return
        try:
            timing = (
                {}
                if self.effective_time is None
                else {
                    "effective_resolution_at": self.effective_time.value(),
                    "use_recorded_time": self.effective_time.use_now.isChecked(),
                }
            )
            if not confirm_contextual_terminal(
                self,
                "Resolve",
                "Outcome: "
                + outcome.value
                + "\nOutcome known: "
                + (
                    "At the actual save time"
                    if not timing or timing.get("use_recorded_time")
                    else str(timing["effective_resolution_at"])
                ),
            ):
                return
            prediction = self._operations.resolve_prediction(
                self._prediction_id,
                outcome,
                resolution_notes=self.notes_input.toPlainText(),
                postmortem=self.postmortem_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
                **timing,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.prediction_resolved.emit(prediction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)


class MarkInvalidDialog(_StyledDialog):
    """Record one deliberate terminal Invalid decision."""

    prediction_invalidated = Signal(object)

    def __init__(
        self,
        operations: PredictionOperations,
        prediction: PredictionSnapshot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("markInvalidDialog")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setWindowTitle("Mark Prediction Invalid")
        self.setModal(True)
        self.resize(560, 360)
        self._operations = operations
        self._prediction_id = prediction.prediction_id
        self._expected_revision_id = prediction.current_revision_id
        self._expected_metadata_version = prediction.metadata_version

        title = QLabel("Mark Prediction Invalid", self)
        title.setObjectName("markInvalidTitle")
        explanation = QLabel(
            "Invalid keeps the prediction and its complete history but excludes it "
            "from scoring. The terminal decision cannot be reopened; its reason "
            "can later be corrected with visible history.",
            self,
        )
        explanation.setObjectName("markInvalidExplanation")
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        explanation.setWordWrap(True)

        reason_label = QLabel("Reason (optional)", self)
        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setObjectName("invalidationReasonInput")
        self.reason_input.setAccessibleName("Invalidation reason")
        self.reason_input.setPlaceholderText(
            "For example: the event was cancelled or the criteria became unresolvable."
        )
        self.reason_input.setTabChangesFocus(True)
        reason_label.setBuddy(self.reason_input)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("markInvalidError")
        self.form_error.setAccessibleName("Mark invalid error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        self.buttons.setObjectName("markInvalidButtons")
        save_button = self.buttons.button(QDialogButtonBox.StandardButton.Save)
        save_button.setObjectName("confirmMarkInvalidButton")
        save_button.setText("Mark Invalid")
        save_button.setDefault(True)
        apply_lucide_icon(save_button, LucideIcon.BAN)
        cancel_button = self.buttons.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_button.setObjectName("cancelMarkInvalidButton")

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(explanation)
        layout.addSpacing(8)
        layout.addWidget(reason_label)
        layout.addWidget(self.reason_input, 1)
        layout.addWidget(self.form_error)
        layout.addWidget(self.buttons)

        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)
        self._submit_key_filter = _MultilineSubmitKeyFilter(self.submit, self)
        self.reason_input.installEventFilter(self._submit_key_filter)
        self.setTabOrder(self.reason_input, save_button)
        self.reason_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Save one Invalid record; expected failures remain editable."""

        self._hide_error()
        try:
            if not confirm_contextual_terminal(
                self,
                "Mark Invalid",
                "Not scored.\nReason: "
                + (self.reason_input.toPlainText() or "Not recorded"),
            ):
                return
            prediction = self._operations.invalidate_prediction(
                self._prediction_id,
                reason=self.reason_input.toPlainText(),
                expected_revision_id=self._expected_revision_id,
                expected_metadata_version=self._expected_metadata_version,
            )
        except ApplicationError as error:
            self._show_error(str(error))
            return
        self.prediction_invalidated.emit(prediction)
        self.accept()

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)
