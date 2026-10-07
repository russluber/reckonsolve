"""Tailored One-Shot input; scores are requested only for saved Detail."""

import sqlite3
from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import QDate, Qt, QTime, QTimeZone, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ApplicationError
from reckonsolve.clock import Clock, SystemClock
from reckonsolve.domain.forecast_contracts import one_shot_contract
from reckonsolve.domain.one_shot import (
    NewOneShotPrediction,
    OneShotDetail,
    OneShotValues,
    ReportedTime,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)
from reckonsolve.one_shot_display import forecast_text
from reckonsolve.reported_time import parse_reported_offset
from reckonsolve.ui.components import ContentPanel, PageHeader
from reckonsolve.ui.quantile_input import FiveQuantileInput
from reckonsolve.ui.time_input import SegmentedTimeEdit
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


def text_label(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    return label


def field(layout: QVBoxLayout, title: str, widget: QWidget) -> None:
    label = text_label(title, widget.parentWidget())
    label.setBuddy(widget)
    apply_text_role(label, TextRole.LABEL)
    widget.setAccessibleName(title)
    layout.addWidget(label)
    layout.addWidget(widget)


class ReportedTimeInput(QWidget):
    """Optional calendar/time picker carrying a wall minute without DST conversion."""

    def __init__(
        self, title: str, parent: QWidget | None = None, *, clock: Clock | None = None
    ) -> None:
        super().__init__(parent)
        self._clock = clock or SystemClock()
        self._seeded = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        heading = text_label(title + " (optional, user-reported)", self)
        apply_text_role(heading, TextRole.LABEL)
        layout.addWidget(heading)
        self.enabled = QCheckBox("Record date and time", self)
        self.enabled.setAccessibleName(title + " — record date and time")
        layout.addWidget(self.enabled)
        self.controls = QWidget(self)
        fields = QVBoxLayout(self.controls)
        fields.setContentsMargins(0, 0, 0, 0)
        fields.setSpacing(int(Spacing.CONTROL))
        pickers = QHBoxLayout()
        pickers.setSpacing(int(Spacing.ORDINARY))
        date_fields = QVBoxLayout()
        self.date = QDateEdit(self.controls)
        # The date is a wall-calendar value; no local DST conversion belongs here.
        self.date.setTimeZone(QTimeZone.utc())
        self.date.setDateRange(QDate(1, 1, 1), QDate(9999, 12, 31))
        self.date.setDisplayFormat("MMM d, yyyy")
        self.date.setCalendarPopup(True)
        self.date.setKeyboardTracking(False)
        field(date_fields, "Date", self.date)
        self.date.setAccessibleName(title + " date")
        heading.setBuddy(self.date)
        pickers.addLayout(date_fields)
        time_fields = QVBoxLayout()
        self.time = SegmentedTimeEdit(self.controls)
        field(time_fields, "Time", self.time)
        self.time.setAccessibleName(title + " time")
        pickers.addLayout(time_fields)
        pickers.addStretch()
        fields.addLayout(pickers)
        self.approximate = QCheckBox("Approximate time", self)
        fields.addWidget(self.approximate)
        self.use_offset = QCheckBox("Add UTC offset (optional)", self)
        fields.addWidget(self.use_offset)
        self.offset = QLineEdit(self)
        self.offset.setPlaceholderText("e.g. -07:00")
        self.offset.setAccessibleName(title + " optional UTC offset")
        self.offset.setMaximumWidth(150)
        fields.addWidget(self.offset)
        self.offset.hide()
        self.use_offset.toggled.connect(self.offset.setVisible)
        layout.addWidget(self.controls)
        self.controls.hide()
        self.enabled.toggled.connect(self._toggle)

    def _toggle(self, checked: bool) -> None:
        if checked and not self._seeded:
            self._set_wall(self._clock.now().astimezone())
        self.controls.setVisible(checked)

    def _set_wall(self, wall: datetime) -> None:
        self.date.setDate(QDate(wall.year, wall.month, wall.day))
        self.time.setTime(QTime(wall.hour, wall.minute))
        self._seeded = True

    def value(self) -> ReportedTime | None:
        if not self.enabled.isChecked():
            return None
        if not self.date.hasAcceptableInput() or not self.time.hasAcceptableInput():
            raise ValueError(
                "Choose a valid reported date and time, or uncheck Record date and time."
            )
        day = self.date.date()
        wall = datetime(  # noqa: DTZ001 - documentary wall time, not an instant
            day.year(),
            day.month(),
            day.day(),
            self.time.time().hour(),
            self.time.time().minute(),
        )
        offset = (
            parse_reported_offset(self.offset.text().strip())
            if self.use_offset.isChecked()
            else None
        )
        return ReportedTime(wall, self.approximate.isChecked(), offset)

    def set_value(self, value: ReportedTime | None) -> None:
        if value is not None:
            self._set_wall(value.wall_time)
        else:
            self._seeded = False
        self.enabled.setChecked(value is not None)
        self.approximate.setChecked(bool(value and value.approximate))
        offset = value.offset_minutes if value else None
        self.use_offset.setChecked(offset is not None)
        self.offset.setText(
            ""
            if offset is None
            else f"{'+' if offset >= 0 else '-'}{abs(offset) // 60:02}:{abs(offset) % 60:02}"
        )


class OneShotValueForm(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        detail: OneShotDetail | None = None,
        answer_only: bool = False,
    ) -> None:
        super().__init__(parent)
        self.detail, self.answer_only = detail, answer_only
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.ORDINARY))
        self.forecast_fields = QWidget(self)
        forecast_layout = QVBoxLayout(self.forecast_fields)
        forecast_layout.setContentsMargins(0, 0, 0, 0)
        self.type_input = QComboBox(self)
        self.type_input.addItem("Binary (Yes/No)", PredictionType.BINARY)
        self.type_input.addItem("Numeric (five quantiles)", PredictionType.NUMERIC)
        field(forecast_layout, "Forecast type", self.type_input)
        self.probability = QSpinBox(self)
        self.probability.setRange(0, 100)
        self.probability.setSuffix("% Yes")
        self.probability.setValue(50)
        self.binary_fields = QWidget(self)
        binary_layout = QVBoxLayout(self.binary_fields)
        binary_layout.setContentsMargins(0, 0, 0, 0)
        field(binary_layout, "Probability", self.probability)
        forecast_layout.addWidget(self.binary_fields)
        self.numeric_fields = QWidget(self)
        numeric_layout = QVBoxLayout(self.numeric_fields)
        numeric_layout.setContentsMargins(0, 0, 0, 0)
        self.unit = QLineEdit(self)
        self.precision = QSpinBox(self)
        self.precision.setRange(0, 6)
        self.constraint = QComboBox(self)
        self.constraint.addItem("Choose value constraint", None)
        self.constraint.addItem(
            "Decimal / continuous-style", NumericValueConstraint.CONTINUOUS
        )
        self.constraint.addItem("Whole-number", NumericValueConstraint.WHOLE_NUMBER)
        field(numeric_layout, "Unit (fixed after saving)", self.unit)
        field(numeric_layout, "Decimal places (fixed after saving)", self.precision)
        field(numeric_layout, "Value constraint (fixed after saving)", self.constraint)
        self.quantiles = FiveQuantileInput(self)
        numeric_layout.addWidget(self.quantiles)
        forecast_layout.addWidget(self.numeric_fields)
        self.forecast_time = ReportedTimeInput(
            "When did you finalize the forecast?", self
        )
        forecast_layout.addWidget(self.forecast_time)
        layout.addWidget(self.forecast_fields)
        self.has_answer = QCheckBox("Include the answer now", self)
        layout.addWidget(self.has_answer)
        self.answer_fields = QWidget(self)
        answer_layout = QVBoxLayout(self.answer_fields)
        answer_layout.setContentsMargins(0, 0, 0, 0)
        self.outcome = QComboBox(self)
        self.outcome.addItem("Choose Yes or No", None)
        self.outcome.addItem("Yes", BinaryOutcome.YES)
        self.outcome.addItem("No", BinaryOutcome.NO)
        self.actual = QLineEdit(self)
        self.actual.setPlaceholderText("Exact measured or looked-up value")
        answer_layout.addWidget(self.outcome)
        answer_layout.addWidget(self.actual)
        self.outcome.setAccessibleName("Answer: Yes or No")
        self.actual.setAccessibleName("Actual value")
        self.reveal_time = ReportedTimeInput("When did you check the answer?", self)
        answer_layout.addWidget(self.reveal_time)
        self.notes, self.postmortem = QPlainTextEdit(self), QPlainTextEdit(self)
        for title, editor in (
            ("Resolution notes (optional)", self.notes),
            ("Postmortem (optional)", self.postmortem),
        ):
            editor.setMaximumHeight(100)
            editor.setTabChangesFocus(True)
            field(answer_layout, title, editor)
        layout.addWidget(self.answer_fields)
        self.type_input.currentIndexChanged.connect(self.update_fields)
        self.has_answer.toggled.connect(self.update_fields)
        self.unit.textChanged.connect(self.update_fields)
        self.precision.valueChanged.connect(self.update_fields)
        self.constraint.currentIndexChanged.connect(self.update_fields)
        if detail:
            record, values = detail.record, detail.record.effective
            self.type_input.setCurrentIndex(1 if record.definition else 0)
            for control in (
                self.type_input,
                self.unit,
                self.precision,
                self.constraint,
            ):
                control.setEnabled(False)
            if record.definition:
                self.unit.setText(record.definition.unit)
                self.precision.setValue(record.definition.decimal_places)
                self.constraint.setCurrentIndex(
                    self.constraint.findData(record.definition.value_constraint)
                )
                for level, value in zip(
                    (5, 25, 50, 75, 95), values.quantiles.values, strict=True
                ):
                    self.quantiles.inputs[level].setText(str(value))
            else:
                self.probability.setValue(values.probability_percent)
            self.forecast_time.set_value(values.forecast_reported)
            self.has_answer.setChecked(answer_only or values.answer is not None)
            self.has_answer.setEnabled(False)
            if isinstance(values.answer, BinaryOutcome):
                self.outcome.setCurrentIndex(self.outcome.findData(values.answer))
            elif values.answer is not None:
                self.actual.setText(str(values.answer))
            self.reveal_time.set_value(values.reveal_reported)
            self.notes.setPlainText(values.resolution_notes or "")
            self.postmortem.setPlainText(values.postmortem or "")
        if answer_only:
            self.forecast_fields.hide()
            self.has_answer.hide()
        self.update_fields()

    def update_fields(self, *_args) -> None:
        numeric = (
            PredictionType(self.type_input.currentData()) is PredictionType.NUMERIC
        )
        self.numeric_fields.setVisible(numeric)
        self.binary_fields.setVisible(not numeric)
        self.outcome.setVisible(not numeric)
        self.actual.setVisible(numeric)
        self.answer_fields.setVisible(self.has_answer.isChecked())
        self.quantiles.set_definition(
            self.unit.text(),
            self.precision.value(),
            NumericValueConstraint(self.constraint.currentData())
            if self.constraint.currentData()
            else None,
        )

    def definition(self) -> QuantileDefinition | None:
        if PredictionType(self.type_input.currentData()) is PredictionType.BINARY:
            return None
        return QuantileDefinition(
            self.unit.text(),
            self.precision.value(),
            NumericValueConstraint(self.constraint.currentData())
            if self.constraint.currentData()
            else None,
        )

    def values(self) -> OneShotValues:
        definition = self.definition()
        answer = None
        if self.has_answer.isChecked():
            if definition:
                answer = FixedPrecisionValue.from_value(
                    self.actual.text(), definition.decimal_places
                )
                definition.validate_value(answer)
            else:
                answer = self.outcome.currentData()
                if answer is None:
                    raise ValueError("Choose Yes or No for the answer.")
                answer = BinaryOutcome(answer)
        answer_fields = {
            "answer": answer,
            "reveal_reported": self.reveal_time.value() if answer is not None else None,
            "resolution_notes": self.notes.toPlainText()
            if answer is not None
            else None,
            "postmortem": self.postmortem.toPlainText() if answer is not None else None,
        }
        if self.answer_only:
            return replace(self.detail.record.effective, **answer_fields)
        values = OneShotValues(
            probability_percent=self.probability.value()
            if definition is None
            else None,
            quantiles=FiveQuantiles.from_values(
                self.quantiles.values(), definition.decimal_places
            )
            if definition
            else None,
            forecast_reported=self.forecast_time.value(),
            **answer_fields,
        )
        values.validate_contract(
            one_shot_contract(PredictionType(self.type_input.currentData())), definition
        )
        return values


class OneShotCreationScreen(QWidget):
    prediction_created = Signal(object)
    cancelled = Signal()

    def __init__(self, operations, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.operations = operations
        self.setObjectName("newOneShotScreen")
        apply_surface_role(self, SurfaceRole.CANVAS)
        column = QWidget(self)
        column.setObjectName("oneShotFormColumn")
        column.setMaximumWidth(980)
        column.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.SECTION))
        header = PageHeader(
            "New One-Shot",
            "Record your final guess from before you checked an existing answer.",
            parent=self,
        )
        self.deadline_button = QPushButton("Adaptive", self)
        self.deadline_button.setObjectName("newDeadlineBasedButton")
        self.deadline_button.setToolTip(
            "Switch to a prediction with a forecast deadline and updates."
        )
        apply_action_role(self.deadline_button, ActionRole.SECONDARY)
        self.deadline_button.clicked.connect(self.cancelled)
        header.add_action(self.deadline_button)
        layout.addWidget(header)
        panel = ContentPanel("Forecast", parent=self)
        panel.setObjectName("oneShotForecastPanel")
        self.question = QLineEdit(self)
        self.question.setPlaceholderText("What did you predict?")
        field(panel.body_layout, "Question", self.question)
        self.form = OneShotValueForm(self)
        panel.body_layout.addWidget(self.form)
        self.rationale, self.background = QPlainTextEdit(self), QPlainTextEdit(self)
        for title, editor in (
            ("Background (optional)", self.background),
            ("Rationale (optional)", self.rationale),
        ):
            editor.setMaximumHeight(100)
            editor.setTabChangesFocus(True)
            field(self.form.forecast_fields.layout(), title, editor)
        self.background.setPlaceholderText(
            "What is the context, and how will you check the answer?"
        )
        self.rationale.setPlaceholderText(
            "What led you to this prediction? Note the clues, assumptions, or comparisons you used."
        )
        self.tags = QLineEdit(self)
        field(
            self.form.forecast_fields.layout(),
            "Tags (optional, comma-separated)",
            self.tags,
        )
        self.setTabOrder(self.form.forecast_time.offset, self.background)
        self.setTabOrder(self.background, self.rationale)
        self.setTabOrder(self.rationale, self.tags)
        self.setTabOrder(self.tags, self.form.has_answer)
        layout.addWidget(panel)
        self.error = text_label("", self)
        apply_message_role(
            self.error, StatusTone.ERROR, accessible_name="One-Shot creation error"
        )
        self.error.hide()
        layout.addWidget(self.error)
        self.save_button = QPushButton("Save One-Shot", self)
        apply_action_role(self.save_button, ActionRole.PRIMARY)
        layout.addWidget(self.save_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addStretch()
        content = QWidget(self)
        content.setObjectName("oneShotFormContent")
        apply_surface_role(content, SurfaceRole.CANVAS)
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(*(int(Spacing.PAGE),) * 4)
        content_layout.addWidget(column, 1, Qt.AlignmentFlag.AlignTop)
        scroll = QScrollArea(self)
        scroll.setObjectName("oneShotScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        self.save_button.clicked.connect(self.submit)

    def cancel(self) -> None:
        self.reset()
        self.cancelled.emit()

    def reset(self) -> None:
        for editor in (
            self.question,
            self.tags,
            self.form.unit,
            self.form.actual,
        ):
            editor.clear()
        for editor in (
            self.rationale,
            self.background,
            self.form.notes,
            self.form.postmortem,
        ):
            editor.clear()
        self.form.quantiles.clear()
        self.form.forecast_time.set_value(None)
        self.form.reveal_time.set_value(None)
        self.form.type_input.setCurrentIndex(0)
        self.form.probability.setValue(50)
        self.form.precision.setValue(0)
        self.form.constraint.setCurrentIndex(0)
        self.form.outcome.setCurrentIndex(0)
        self.form.has_answer.setChecked(False)
        self.error.hide()

    def submit(self) -> None:
        self.error.hide()
        try:
            request = NewOneShotPrediction(
                self.question.text(),
                one_shot_contract(PredictionType(self.form.type_input.currentData())),
                self.form.values(),
                self.form.definition(),
                self.rationale.toPlainText(),
                self.background.toPlainText(),
                tags=tuple(t.strip() for t in self.tags.text().split(",") if t.strip()),
            )
            saved = self.operations.one_shots.create(request)
        except (ApplicationError, ValueError, sqlite3.Error) as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.reset()
        self.prediction_created.emit(saved)


class OneShotEditDialog(QDialog):
    saved = Signal(object)

    def __init__(
        self,
        operations,
        detail: OneShotDetail,
        *,
        correction: bool,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.operations, self.detail, self.correction = operations, detail, correction
        self.setWindowTitle("Correct transcription" if correction else "Add answer")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setModal(True)
        self.resize(660, 650)
        layout = QVBoxLayout(self)
        layout.addWidget(text_label(detail.question, self))
        if detail.record.definition:
            definition = detail.record.definition
            layout.addWidget(
                text_label(
                    f"Unit: {definition.unit} · Decimal places: {definition.decimal_places} · {definition.value_constraint.value}",
                    self,
                )
            )
        layout.addWidget(
            text_label(
                "Correct a copied value or note. The original and every correction remain in history."
                if correction
                else "Your saved forecast: "
                + forecast_text(
                    detail.record.effective,
                    detail.record.definition.unit if detail.record.definition else "",
                ),
                self,
            )
        )
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self.form = OneShotValueForm(self, detail=detail, answer_only=not correction)
        scroll.setWidget(self.form)
        layout.addWidget(scroll)
        self.note = QLineEdit(self)
        self.note.setPlaceholderText("Correction note (optional)")
        self.note.setAccessibleName("Correction note (optional)")
        self.note.setVisible(correction)
        layout.addWidget(self.note)
        self.error = text_label("", self)
        apply_message_role(
            self.error, StatusTone.ERROR, accessible_name="One-Shot save error"
        )
        self.error.hide()
        layout.addWidget(self.error)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        apply_action_role(
            self.buttons.button(QDialogButtonBox.StandardButton.Save),
            ActionRole.PRIMARY,
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setAutoDefault(False)
        layout.addWidget(self.buttons)
        self.buttons.accepted.connect(self.submit)
        self.buttons.rejected.connect(self.reject)

    def submit(self) -> None:
        try:
            values = self.form.values()
            if self.correction and values == self.detail.record.effective:
                raise ValueError("The transcription is unchanged.")
            message = (
                "Save this transcription correction? The original values remain in history. The saved score will use the corrected forecast and answer."
                if self.correction
                else "Save this answer and mark the One-Shot Resolved? You can correct transcription mistakes later; this cannot reopen forecasting."
            )
            if (
                QMessageBox.question(
                    self,
                    self.windowTitle(),
                    message,
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                != QMessageBox.StandardButton.Save
            ):
                return
            saved = (
                self.operations.one_shots.correct(
                    self.detail, values, note=self.note.text()
                )
                if self.correction
                else self.operations.one_shots.add_answer(self.detail, values)
            )
        except (ApplicationError, ValueError, sqlite3.Error) as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.saved.emit(saved)
        self.accept()
