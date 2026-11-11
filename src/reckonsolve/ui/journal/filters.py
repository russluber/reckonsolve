"""One deliberate modal draft for advanced Journal constraints."""

import re
from dataclasses import replace

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.browser import (
    ArchiveDateMeaning,
    ArchiveMode,
    ArchiveQuery,
    ArchiveTagMatchMode,
)
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.domain.predictions import (
    MAX_METADATA_DATE,
    MIN_METADATA_DATE,
    PredictionType,
)
from reckonsolve.domain.search import SearchMatchMode
from reckonsolve.ui.tag_filter_picker import TagFilterPicker
from reckonsolve.ui.visual_system import (
    ActionRole,
    StatusTone,
    apply_action_role,
    apply_message_role,
    install_visual_system,
)


class _DateInput(QDateEdit):
    def complete_date(self) -> bool:
        # QDateEdit may accept an omitted year by retaining the previous value.
        # The optional boundary is a whole explicit date, never that inference.
        raw = self.lineEdit().text()
        return (
            bool(re.search(r"\d{4}\s*$", raw))
            and self.hasAcceptableInput()
            and self.locale().toDate(raw, self.displayFormat()).isValid()
        )

    def focusOutEvent(self, event) -> None:
        raw = self.lineEdit().text()
        incomplete = not self.complete_date()
        super().focusOutEvent(event)
        if incomplete:
            self.lineEdit().setText(raw)


class JournalFiltersDialog(QDialog):
    def __init__(
        self, request: JournalRequest, tags: tuple[str, ...], parent: QWidget
    ) -> None:
        super().__init__(parent)
        self.original = request
        self.applied = request
        self.setObjectName("journalFiltersDialog")
        self.setWindowTitle("Filters")
        self.setModal(True)
        self.setMinimumWidth(460)
        form = QFormLayout()
        self.mode = self._combo(
            "Forecast mode",
            [
                ("All modes", None),
                ("Adaptive", ArchiveMode.DEADLINE),
                ("One-Shot", ArchiveMode.ONE_SHOT),
            ],
        )
        self.kind = self._combo(
            "Forecast type",
            [
                ("All types", None),
                ("Binary", PredictionType.BINARY),
                ("Numeric", PredictionType.NUMERIC),
            ],
        )
        self.mode.setCurrentIndex(self.mode.findData(request.filters.mode))
        self.kind.setCurrentIndex(self.kind.findData(request.filters.prediction_type))
        form.addRow("Mode", self.mode)
        form.addRow("Type", self.kind)
        self.tags = TagFilterPicker(self)
        self.tags.set_available_tags(tags)
        self.tags.set_selected_tags(request.filters.tags)
        self.tag_mode = self._combo(
            "Tag matching",
            [
                ("All selected tags", ArchiveTagMatchMode.ALL),
                ("Any selected tag", ArchiveTagMatchMode.ANY),
            ],
        )
        self.tag_mode.setCurrentIndex(
            self.tag_mode.findData(request.filters.tag_match_mode)
        )
        form.addRow("Tags", self.tags)
        form.addRow("Match tags", self.tag_mode)
        self.date_meaning = self._combo(
            "Date meaning",
            [
                ("Created", ArchiveDateMeaning.CREATED),
                ("Forecast Deadline", ArchiveDateMeaning.FORECAST_DEADLINE),
                ("Expected Resolution", ArchiveDateMeaning.EXPECTED_RESOLUTION),
                ("Terminal decision", ArchiveDateMeaning.TERMINAL_DECISION),
            ],
        )
        self.date_meaning.setCurrentIndex(
            self.date_meaning.findData(request.filters.date_meaning)
        )
        form.addRow("Date", self.date_meaning)
        self.date_rows = []
        for label, value in (
            ("From", request.filters.date_start),
            ("Through", request.filters.date_end),
        ):
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            enabled = QCheckBox(label, row)
            enabled.setAccessibleName(f"Use {label.lower()} date")
            enabled.setChecked(value is not None)
            editor = _DateInput(row)
            editor.setAccessibleName(f"{label} date, inclusive")
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd MMM yyyy")
            editor.setDateRange(QDate(MIN_METADATA_DATE), QDate(MAX_METADATA_DATE))
            editor.setDate(QDate(value) if value else QDate.currentDate())
            editor.setEnabled(value is not None)
            enabled.toggled.connect(editor.setEnabled)
            layout.addWidget(enabled)
            layout.addWidget(editor, 1)
            self.date_rows.append((enabled, editor))
            form.addRow(row)
        self.words = self._combo(
            "Search word matching",
            [("All words", SearchMatchMode.ALL), ("Any word", SearchMatchMode.ANY)],
        )
        self.words.setCurrentIndex(self.words.findData(request.match_mode))
        self.history = QCheckBox("Include superseded history", self)
        self.history.setChecked(request.include_history)
        form.addRow("Search options", self.words)
        form.addRow(self.history)
        self.error = QLabel("", self)
        self.error.setWordWrap(True)
        apply_message_role(
            self.error, StatusTone.ERROR, accessible_name="Filter validation error"
        )
        self.error.hide()
        clear = QPushButton("Clear filters", self)
        apply_action_role(clear, ActionRole.QUIET)
        clear.clicked.connect(self.clear)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply
        )
        buttons.rejected.connect(self.reject)
        footer = QHBoxLayout()
        footer.addWidget(clear)
        footer.addStretch()
        footer.addWidget(buttons)
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addLayout(footer)
        install_visual_system(self)

    def _combo(self, name: str, choices: list) -> QComboBox:
        combo = QComboBox(self)
        combo.setAccessibleName(name)
        for text, value in choices:
            combo.addItem(text, value)
        return combo

    def clear(self) -> None:
        for combo in (
            self.mode,
            self.kind,
            self.tag_mode,
            self.date_meaning,
            self.words,
        ):
            combo.setCurrentIndex(0)
        self.tags.clear_selection()
        for enabled, _editor in self.date_rows:
            enabled.setChecked(False)
        self.history.setChecked(False)
        self.error.hide()

    def apply(self) -> None:
        dates = []
        for enabled, editor in self.date_rows:
            if enabled.isChecked() and not editor.complete_date():
                self.error.setText(
                    "Complete each enabled date before applying filters."
                )
                self.error.show()
                editor.setFocus(Qt.FocusReason.OtherFocusReason)
                return
            dates.append(editor.date().toPython() if enabled.isChecked() else None)
        try:
            filters = ArchiveQuery(
                mode=ArchiveMode(self.mode.currentData())
                if self.mode.currentData()
                else None,
                prediction_type=PredictionType(self.kind.currentData())
                if self.kind.currentData()
                else None,
                tags=self.tags.selected_tags(),
                tag_match_mode=ArchiveTagMatchMode(self.tag_mode.currentData()),
                date_meaning=ArchiveDateMeaning(self.date_meaning.currentData())
                if any(dates)
                else ArchiveDateMeaning.CREATED,
                date_start=dates[0],
                date_end=dates[1],
            )
            self.applied = replace(
                self.original,
                filters=filters,
                match_mode=SearchMatchMode(self.words.currentData()),
                include_history=self.history.isChecked(),
            )
        except ValueError as error:
            self.error.setText(str(error))
            self.error.show()
            return
        self.accept()
