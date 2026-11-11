"""Creation screen responsibilities extracted from the desktop composition."""

from __future__ import annotations

from itertools import pairwise

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.domain.predictions import PredictionType
from reckonsolve.domain.quantiles import NumericValueConstraint
from reckonsolve.ui.components import ContentPanel, PageHeader, ProbabilityPresets
from reckonsolve.ui.exact_deadline_input import ExactDeadlineInput
from reckonsolve.ui.icons import LucideIcon, apply_lucide_icon
from reckonsolve.ui.prediction_contracts import PredictionOperations
from reckonsolve.ui.prediction_widgets import (
    _create_optional_date_controls,
    _date_input_row,
    _optional_date,
    _parse_tags,
)
from reckonsolve.ui.quantile_input import FiveQuantileInput
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


class NewPredictionScreen(QWidget):
    """Collect the minimum information needed for a binary prediction."""

    prediction_created = Signal(object)
    one_shot_requested = Signal()

    def __init__(
        self,
        operations: PredictionOperations,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("newPredictionScreen")
        apply_surface_role(self, SurfaceRole.CANVAS)
        self._operations = operations

        header = PageHeader(
            "New Prediction",
            "Capture the question first, then state the forecast you believe now.",
            title_object_name="newPredictionScreenTitle",
            supporting_object_name="newPredictionScreenSupportingText",
            parent=self,
        )
        header.title_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.one_shot_button = QPushButton("One-Shot", self)
        self.one_shot_button.setObjectName("newOneShotButton")
        apply_action_role(self.one_shot_button, ActionRole.SECONDARY)
        self.one_shot_button.setToolTip(
            "Record a final guess made before checking an already-existing answer."
        )
        self.one_shot_button.clicked.connect(self.one_shot_requested)
        header.add_action(self.one_shot_button)

        question_label = QLabel("Question", self)
        question_label.setObjectName("questionLabel")
        self._make_primary_label(question_label)

        self.question_input = QLineEdit(self)
        self.question_input.setObjectName("questionInput")
        self.question_input.setAccessibleName("Prediction question")
        self.question_input.setPlaceholderText("What do you think will happen?")
        self.question_input.setClearButtonEnabled(True)
        question_label.setBuddy(self.question_input)

        prediction_type_label = QLabel("Forecast type", self)
        prediction_type_label.setObjectName("predictionTypeLabel")
        self._make_primary_label(prediction_type_label)

        self.prediction_type_input = QComboBox(self)
        self.prediction_type_input.setObjectName("predictionTypeInput")
        self.prediction_type_input.setAccessibleName("Forecast type")
        self.prediction_type_input.addItem("Binary (yes/no)", PredictionType.BINARY)
        self.prediction_type_input.addItem(
            "Numeric (five quantiles)", PredictionType.NUMERIC
        )
        prediction_type_label.setBuddy(self.prediction_type_input)

        self.binary_forecast_fields = QWidget(self)
        self.binary_forecast_fields.setObjectName("binaryForecastFields")
        binary_fields_layout = QVBoxLayout(self.binary_forecast_fields)
        binary_fields_layout.setContentsMargins(0, 0, 0, 0)

        probability_label = QLabel("Probability", self.binary_forecast_fields)
        probability_label.setObjectName("probabilityLabel")
        self._make_primary_label(probability_label)

        self.probability_input = QSpinBox(self.binary_forecast_fields)
        self.probability_input.setObjectName("probabilityInput")
        self.probability_input.setAccessibleName("Prediction probability")
        self.probability_input.setRange(0, 100)
        self.probability_input.setSuffix("%")
        self.probability_input.setValue(50)
        probability_label.setBuddy(self.probability_input)

        shortcuts = ProbabilityPresets(
            self.probability_input, self.binary_forecast_fields
        )

        self.endpoint_note = QLabel(
            "0% and 100% express absolute certainty.",
            self.binary_forecast_fields,
        )
        self.endpoint_note.setObjectName("probabilityEndpointNote")
        self.endpoint_note.setWordWrap(True)
        apply_message_role(
            self.endpoint_note,
            StatusTone.WARNING,
            accessible_name="Absolute-certainty forecast note",
        )

        binary_fields_layout.addWidget(probability_label)
        binary_fields_layout.addWidget(self.probability_input)
        binary_fields_layout.addWidget(shortcuts)
        binary_fields_layout.addWidget(self.endpoint_note)
        self.exact_deadline = ExactDeadlineInput(self)

        self.numeric_forecast_fields = QWidget(self)
        self.numeric_forecast_fields.setObjectName("numericForecastFields")
        numeric_fields_layout = QVBoxLayout(self.numeric_forecast_fields)
        numeric_fields_layout.setContentsMargins(0, 0, 0, 0)

        unit_label = QLabel("Unit", self.numeric_forecast_fields)
        unit_label.setObjectName("numericUnitLabel")
        self._make_primary_label(unit_label)
        self.numeric_unit_input = QLineEdit(self.numeric_forecast_fields)
        self.numeric_unit_input.setObjectName("numericUnitInput")
        self.numeric_unit_input.setAccessibleName("Numeric forecast unit")
        self.numeric_unit_input.setPlaceholderText("For example: days, books, USD")
        self.numeric_unit_input.setClearButtonEnabled(True)
        unit_label.setBuddy(self.numeric_unit_input)

        precision_label = QLabel("Decimal places", self.numeric_forecast_fields)
        precision_label.setObjectName("numericPrecisionLabel")
        self._make_primary_label(precision_label)
        self.numeric_precision_input = QSpinBox(self.numeric_forecast_fields)
        self.numeric_precision_input.setObjectName("numericPrecisionInput")
        self.numeric_precision_input.setAccessibleName("Numeric decimal places")
        self.numeric_precision_input.setRange(0, 6)
        self.numeric_precision_input.setValue(0)
        precision_label.setBuddy(self.numeric_precision_input)

        self.numeric_constraint_input = QComboBox(self.numeric_forecast_fields)
        self.numeric_constraint_input.setObjectName("numericConstraintInput")
        self.numeric_constraint_input.setAccessibleName("Numeric value constraint")
        self.numeric_constraint_input.addItem("Choose value constraint", None)
        self.numeric_constraint_input.addItem(
            "Decimal / continuous-style", NumericValueConstraint.CONTINUOUS
        )
        self.numeric_constraint_input.addItem(
            "Whole-number", NumericValueConstraint.WHOLE_NUMBER
        )
        numeric_fields_layout.addWidget(unit_label)
        numeric_fields_layout.addWidget(self.numeric_unit_input)
        numeric_fields_layout.addWidget(precision_label)
        numeric_fields_layout.addWidget(self.numeric_precision_input)
        numeric_fields_layout.addWidget(
            QLabel("Value constraint (permanent)", self.numeric_forecast_fields)
        )
        numeric_fields_layout.addWidget(self.numeric_constraint_input)
        self.quantile_input = FiveQuantileInput(self.numeric_forecast_fields)
        numeric_fields_layout.addWidget(self.quantile_input)
        # Both forecast forms share one draft commitment, including Custom input.
        self.numeric_exact_deadline = self.exact_deadline

        def update_quantile_preview() -> None:
            self.quantile_input.set_definition(
                self.numeric_unit_input.text(),
                self.numeric_precision_input.value(),
                NumericValueConstraint(self.numeric_constraint_input.currentData())
                if self.numeric_constraint_input.currentData() is not None
                else None,
            )

        self.numeric_unit_input.textChanged.connect(update_quantile_preview)
        self.numeric_precision_input.valueChanged.connect(update_quantile_preview)
        self.numeric_constraint_input.currentIndexChanged.connect(
            update_quantile_preview
        )

        self.more_details = QGroupBox("More details", self)
        self.more_details.setObjectName("newPredictionMoreDetailsGroup")
        self.more_details.setCheckable(True)
        self.more_details.setChecked(False)
        apply_surface_role(self.more_details, SurfaceRole.RAISED)

        self.more_details_content = QWidget(self.more_details)
        self.more_details_content.setObjectName("newPredictionMoreDetailsContent")
        more_details_layout = QVBoxLayout(self.more_details_content)
        more_details_layout.setContentsMargins(
            int(Spacing.CONTROL),
            int(Spacing.ORDINARY),
            int(Spacing.CONTROL),
            int(Spacing.CONTROL),
        )
        more_details_layout.setSpacing(int(Spacing.CONTROL))

        rationale_label = QLabel(
            "Initial rationale (optional)", self.more_details_content
        )
        apply_text_role(rationale_label, TextRole.LABEL)
        self.rationale_input = QPlainTextEdit(self.more_details_content)
        self.rationale_input.setObjectName("initialRationaleInput")
        self.rationale_input.setAccessibleName("Initial rationale")
        self.rationale_input.setPlaceholderText("Why is this your initial forecast?")
        self.rationale_input.setMaximumHeight(100)
        self.rationale_input.setTabChangesFocus(True)
        rationale_label.setBuddy(self.rationale_input)

        background_label = QLabel("Background (optional)", self.more_details_content)
        apply_text_role(background_label, TextRole.LABEL)
        self.background_input = QPlainTextEdit(self.more_details_content)
        self.background_input.setObjectName("initialBackgroundInput")
        self.background_input.setAccessibleName("Background")
        self.background_input.setPlaceholderText(
            "What context or prior events help explain this question?"
        )
        self.background_input.setMaximumHeight(100)
        self.background_input.setTabChangesFocus(True)
        background_label.setBuddy(self.background_input)

        criteria_label = QLabel(
            "Resolution criteria (optional)",
            self.more_details_content,
        )
        apply_text_role(criteria_label, TextRole.LABEL)
        self.resolution_criteria_input = QPlainTextEdit(self.more_details_content)
        self.resolution_criteria_input.setObjectName("initialResolutionCriteriaInput")
        self.resolution_criteria_input.setAccessibleName("Resolution criteria")
        self.resolution_criteria_input.setPlaceholderText(
            "What result will settle this question, and which source will you use to check it?"
        )
        self.resolution_criteria_input.setMaximumHeight(100)
        self.resolution_criteria_input.setTabChangesFocus(True)
        criteria_label.setBuddy(self.resolution_criteria_input)

        self.expected_resolution_toggle, self.expected_resolution_input = (
            _create_optional_date_controls(
                self.more_details_content,
                "Expected resolution",
                "initialExpectedResolutionToggle",
                "initialExpectedResolutionInput",
                None,
            )
        )

        tags_label = QLabel(
            "Tags (optional, comma-separated)",
            self.more_details_content,
        )
        apply_text_role(tags_label, TextRole.LABEL)
        self.tags_input = QLineEdit(self.more_details_content)
        self.tags_input.setObjectName("initialTagsInput")
        self.tags_input.setAccessibleName("Tags")
        tags_label.setBuddy(self.tags_input)

        more_details_layout.addWidget(rationale_label)
        more_details_layout.addWidget(self.rationale_input)
        more_details_layout.addWidget(background_label)
        more_details_layout.addWidget(self.background_input)
        more_details_layout.addWidget(criteria_label)
        more_details_layout.addWidget(self.resolution_criteria_input)
        more_details_layout.addWidget(
            _date_input_row(
                self.expected_resolution_toggle,
                self.expected_resolution_input,
            )
        )
        more_details_layout.addWidget(tags_label)
        more_details_layout.addWidget(self.tags_input)

        more_details_group_layout = QVBoxLayout(self.more_details)
        more_details_group_layout.addWidget(self.more_details_content)
        self.more_details.toggled.connect(self.more_details_content.setVisible)
        self.more_details_content.setHidden(True)

        self.form_error = QLabel("", self)
        self.form_error.setObjectName("predictionFormError")
        self.form_error.setAccessibleName("Prediction form error")
        self.form_error.setTextFormat(Qt.TextFormat.PlainText)
        self.form_error.setWordWrap(True)
        self.form_error.setHidden(True)
        apply_message_role(
            self.form_error,
            StatusTone.ERROR,
            accessible_name="Prediction form error",
        )

        self.create_button = QPushButton("Create Prediction", self)
        self.create_button.setObjectName("createPredictionButton")
        self.create_button.setAccessibleName("Create prediction")
        apply_action_role(self.create_button, ActionRole.PRIMARY)
        apply_lucide_icon(self.create_button, LucideIcon.CIRCLE_PLUS)

        self.forecast_panel = ContentPanel(
            "Forecast",
            "Binary forecasts need a question, probability, and permanent exact deadline.",
            parent=self,
        )
        self.forecast_panel.setObjectName("newPredictionForecastPanel")
        core_layout = self.forecast_panel.body_layout
        core_layout.addWidget(question_label)
        core_layout.addWidget(self.question_input)
        core_layout.addSpacing(int(Spacing.ORDINARY))
        core_layout.addWidget(prediction_type_label)
        core_layout.addWidget(self.prediction_type_input)
        core_layout.addSpacing(int(Spacing.CONTROL))
        core_layout.addWidget(self.binary_forecast_fields)
        core_layout.addWidget(self.numeric_forecast_fields)
        core_layout.addSpacing(int(Spacing.CONTROL))
        core_layout.addWidget(self.exact_deadline)

        form_column = QWidget(self)
        form_column.setObjectName("newPredictionFormColumn")
        form_column.setMaximumWidth(980)
        form_column.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        column_layout = QVBoxLayout(form_column)
        column_layout.setContentsMargins(0, 0, 0, 0)
        column_layout.setSpacing(int(Spacing.SECTION))
        column_layout.addWidget(header)
        column_layout.addWidget(self.forecast_panel)
        column_layout.addWidget(self.more_details)
        column_layout.addWidget(self.form_error)
        column_layout.addWidget(
            self.create_button,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )
        column_layout.addStretch()

        form_content = QWidget(self)
        form_content.setObjectName("newPredictionFormContent")
        apply_surface_role(form_content, SurfaceRole.CANVAS)
        layout = QHBoxLayout(form_content)
        layout.setContentsMargins(
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
            int(Spacing.PAGE),
        )
        layout.addWidget(form_column, 1, Qt.AlignmentFlag.AlignTop)

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("newPredictionScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(form_content)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(scroll_area)

        self.setTabOrder(self.question_input, self.prediction_type_input)
        self.setTabOrder(self.prediction_type_input, self.probability_input)
        self.setTabOrder(self.probability_input, self.numeric_unit_input)
        self.setTabOrder(self.numeric_unit_input, self.numeric_precision_input)
        self.setTabOrder(self.numeric_precision_input, self.numeric_constraint_input)
        self.setTabOrder(self.numeric_constraint_input, self.quantile_input.inputs[5])
        self.setTabOrder(
            self.quantile_input.inputs[95], self.exact_deadline.preset_buttons[0]
        )
        deadline_controls = [
            *self.exact_deadline.preset_buttons.values(),
            self.exact_deadline.custom_button,
            self.exact_deadline.editor,
            self.exact_deadline.occurrence,
            self.exact_deadline.use_offset,
            self.exact_deadline.offset,
            self.more_details,
        ]
        for previous, following in pairwise(deadline_controls):
            self.setTabOrder(previous, following)
        self.setTabOrder(self.more_details, self.rationale_input)
        self.setTabOrder(self.rationale_input, self.background_input)
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
        self.setTabOrder(self.tags_input, self.create_button)

        self.probability_input.valueChanged.connect(self._update_endpoint_note)
        self.prediction_type_input.currentIndexChanged.connect(
            self._update_forecast_type
        )
        self.question_input.returnPressed.connect(self.submit)
        self.create_button.clicked.connect(self.submit)
        self._update_endpoint_note(self.probability_input.value())
        self._update_forecast_type(self.prediction_type_input.currentIndex())

    def focus_question(self) -> None:
        """Put keyboard focus at the start of the creation flow."""
        self.question_input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    def submit(self) -> None:
        """Validate the form shape and invoke the complete creation operation."""
        self._hide_error()
        question = self.question_input.text().strip()
        if not question:
            self._show_error("Enter a question before creating the prediction.")
            self.focus_question()
            return

        guard = getattr(self, "save_guard", None)
        if guard is not None and not guard():
            return

        try:
            details = {
                "rationale": self.rationale_input.toPlainText(),
                "background": self.background_input.toPlainText(),
                "resolution_criteria": self.resolution_criteria_input.toPlainText(),
                "expected_resolution": _optional_date(
                    self.expected_resolution_toggle,
                    self.expected_resolution_input,
                ),
                "tags": _parse_tags(self.tags_input.text()),
            }
            if self._is_numeric_type():
                details["forecast_deadline"] = self.numeric_exact_deadline.value()
                prediction = self._operations.create_numeric_prediction(
                    question,
                    self.numeric_unit_input.text(),
                    self.numeric_precision_input.value(),
                    self.quantile_input.values(),
                    value_constraint=NumericValueConstraint(
                        self.numeric_constraint_input.currentData()
                    )
                    if self.numeric_constraint_input.currentData() is not None
                    else None,
                    **details,
                )
            else:
                details["forecast_deadline"] = self.exact_deadline.value()
                prediction = self._operations.create_prediction(
                    question=question,
                    probability_percent=self.probability_input.value(),
                    **details,
                )
        except ApplicationError as error:
            self._show_error(str(error))
            if self._is_numeric_type():
                self.quantile_input.show_validation(error)
            return

        self._reset_form()
        self.prediction_created.emit(prediction)

    def _reset_form(self) -> None:
        self.question_input.clear()
        self.prediction_type_input.setCurrentIndex(0)
        self.probability_input.setValue(50)
        self.exact_deadline.reset()
        self.numeric_exact_deadline.reset()
        self.numeric_unit_input.clear()
        self.numeric_precision_input.setValue(0)
        self.quantile_input.clear()
        self.numeric_constraint_input.setCurrentIndex(0)
        self.rationale_input.clear()
        self.background_input.clear()
        self.resolution_criteria_input.clear()
        self.expected_resolution_toggle.setChecked(False)
        self.expected_resolution_input.setDate(QDate.currentDate())
        self.tags_input.clear()
        self.more_details.setChecked(False)
        self._hide_error()

    @staticmethod
    def _make_primary_label(label: QLabel) -> None:
        apply_text_role(label, TextRole.LABEL)

    def _update_endpoint_note(self, probability: int) -> None:
        self.endpoint_note.setHidden(
            self._is_numeric_type() or probability not in (0, 100)
        )

    def _update_forecast_type(self, _index: int) -> None:
        is_numeric = self._is_numeric_type()
        self.binary_forecast_fields.setHidden(is_numeric)
        self.numeric_forecast_fields.setHidden(not is_numeric)
        self.forecast_panel.supporting_label.setText(
            "Numeric forecasts need a question, unit, precision, value constraint, "
            "five percentiles, and permanent exact deadline."
            if is_numeric
            else "Binary forecasts need a question, probability, and permanent exact deadline."
        )
        self._update_endpoint_note(self.probability_input.value())

    def _is_numeric_type(self) -> bool:
        return self.prediction_type_input.currentData() == PredictionType.NUMERIC.value

    def _show_error(self, message: str) -> None:
        self.form_error.setText(message)
        self.form_error.setHidden(False)

    def _hide_error(self) -> None:
        self.form_error.clear()
        self.form_error.setHidden(True)
