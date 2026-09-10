"""An explicit wall-clock time and UTC offset for a permanent commitment."""

from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QTime, QTimeZone
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ValidationError
from reckonsolve.clock import SystemClock
from reckonsolve.domain.forecast_contracts import ForecastDeadline
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


class ExactDeadlineInput(QWidget):
    """Keep an unset deadline explicit; never guess a future cutoff for the user."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggle = QCheckBox("Set Forecast Deadline (required)", self)
        self.toggle.setObjectName("exactDeadlineToggle")
        self.editor = QDateTimeEdit(self)
        self.editor.setTimeZone(QTimeZone.utc())
        self.editor.setObjectName("exactDeadlineInput")
        self.editor.setAccessibleName("Forecast Deadline date and time")
        self.editor.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.editor.setCalendarPopup(True)
        self.offset = QLineEdit(self)
        self.offset.setObjectName("exactDeadlineOffset")
        self.offset.setAccessibleName("Forecast Deadline UTC offset")
        self.offset.setPlaceholderText("-07:00")
        self.offset.setMaximumWidth(90)
        row = QHBoxLayout()
        row.setSpacing(int(Spacing.CONTROL))
        row.addWidget(self.editor, 1)
        offset_label = QLabel("UTC offset", self)
        apply_text_role(offset_label, TextRole.LABEL)
        offset_label.setBuddy(self.offset)
        row.addWidget(offset_label)
        row.addWidget(self.offset)
        note = QLabel(
            "Permanent cutoff for changing your forecast, not the expected outcome "
            "date. Choose a future date and time; check the UTC offset, including "
            "daylight saving time at that date.",
            self,
        )
        note.setWordWrap(True)
        apply_text_role(note, TextRole.SECONDARY)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        layout.addWidget(self.toggle)
        layout.addLayout(row)
        layout.addWidget(note)
        self.toggle.toggled.connect(self.editor.setEnabled)
        self.toggle.toggled.connect(self.offset.setEnabled)
        self.reset()

    def reset(self) -> None:
        local = SystemClock().now().astimezone()
        # UTC is only a wall-clock carrier here. The explicit offset below,
        # not Qt's implicit local DST rules, defines the committed instant.
        self.editor.setDateTime(
            QDateTime(
                QDate(local.year, local.month, local.day),
                QTime(local.hour, local.minute),
                QTimeZone.utc(),
            )
        )
        offset = local.strftime("%z")
        self.offset.setText(f"{offset[:3]}:{offset[3:]}")
        self.toggle.setChecked(False)
        self.editor.setEnabled(False)
        self.offset.setEnabled(False)

    def value(self) -> datetime:
        if not self.toggle.isChecked():
            raise ValidationError(
                "Set an exact Forecast Deadline before creating this prediction.",
                field="forecast_deadline",
            )
        # A displayed 14:30 commits exactly 14:30:00, never hidden seconds.
        wall = self.editor.dateTime().toString("yyyy-MM-dd'T'HH:mm") + ":00"
        offset = self.offset.text().strip()
        try:
            if len(offset) != 6 or offset[0] not in "+-" or offset[3] != ":":
                raise ValueError
            if not (offset[1:3].isdigit() and offset[4:].isdigit()):
                raise ValueError
            if int(offset[1:3]) > 23 or int(offset[4:]) > 59:
                raise ValueError
            return ForecastDeadline(datetime.fromisoformat(wall + offset)).instant
        except ValueError as error:
            raise ValidationError(
                "Enter a UTC offset such as -07:00 or +00:00.",
                field="forecast_deadline",
            ) from error
