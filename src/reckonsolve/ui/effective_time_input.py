"""Explicit effective-time choice; precision stays out of the ordinary workflow."""

from datetime import datetime

from PySide6.QtCore import QDate, QDateTime, QTime, QTimeZone
from PySide6.QtWidgets import (
    QCheckBox,
    QDateTimeEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.application.errors import ValidationError
from reckonsolve.clock import SystemClock
from reckonsolve.domain.forecast_contracts import EffectiveResolutionTime
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


class EffectiveTimeInput(QWidget):
    def __init__(
        self, parent: QWidget | None = None, current: datetime | None = None
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.setObjectName("effectiveResolutionInput")
        self._original = current
        self.use_now = QCheckBox(
            "Outcome became knowable now (use recording time)", self
        )
        self.use_now.setChecked(current is None)
        self.use_now.setVisible(current is None)
        self.editor = QDateTimeEdit(self)
        self.editor.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum
        )
        self.editor.setTimeZone(QTimeZone.utc())
        self.editor.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.editor.setCalendarPopup(True)
        self.editor.setAccessibleName("Effective resolution date and time")
        self.offset = QLineEdit(self)
        self.offset.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum
        )
        self.offset.setAccessibleName("Effective resolution UTC offset")
        self.offset.setMaximumWidth(90)
        self.precise = QCheckBox("Show seconds", self)
        local = (current or SystemClock().now()).astimezone()
        self.editor.setDateTime(
            QDateTime(
                QDate(local.year, local.month, local.day),
                QTime(
                    local.hour, local.minute, local.second, local.microsecond // 1000
                ),
                QTimeZone.utc(),
            )
        )
        offset = local.strftime("%z")
        self.offset.setText(f"{offset[:3]}:{offset[3:]}")
        self._initial_controls = (self.editor.dateTime(), self.offset.text())
        if current is not None:
            self.editor.setToolTip(
                "Saved exact instant: " + current.astimezone().isoformat(sep=" ")
            )
        label = QLabel("Effective resolution time", self)
        apply_text_role(label, TextRole.LABEL)
        label.setBuddy(self.editor)
        help_text = QLabel(
            "When the outcome first became fixed and knowable. If that was earlier, enter the source time and its UTC offset. Recorded-at is saved automatically.",
            self,
        )
        help_text.setWordWrap(True)
        apply_text_role(help_text, TextRole.SECONDARY)
        row = QHBoxLayout()
        row.addWidget(self.editor, 1)
        row.addWidget(QLabel("UTC offset", self))
        row.addWidget(self.offset)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        layout.addWidget(label)
        layout.addWidget(help_text)
        layout.addWidget(self.use_now)
        layout.addLayout(row)
        layout.addWidget(self.precise)
        self.use_now.toggled.connect(self._set_now)
        self.precise.toggled.connect(
            lambda checked: self.editor.setDisplayFormat(
                "yyyy-MM-dd HH:mm:ss.zzz" if checked else "yyyy-MM-dd HH:mm"
            )
        )
        self._set_now(self.use_now.isChecked())

    def _set_now(self, checked: bool) -> None:
        self.editor.setEnabled(not checked)
        self.offset.setEnabled(not checked)
        self.precise.setEnabled(not checked)

    def value(self) -> datetime | None:
        if self.use_now.isChecked():
            return None
        if (
            self._original is not None
            and (self.editor.dateTime(), self.offset.text()) == self._initial_controls
        ):
            return self._original
        wall = self.editor.dateTime().toString(
            "yyyy-MM-dd'T'HH:mm:ss.zzz"
            if self.precise.isChecked()
            else "yyyy-MM-dd'T'HH:mm"
        )
        offset = self.offset.text().strip()
        try:
            if (
                len(offset) != 6
                or offset[0] not in "+-"
                or offset[3] != ":"
                or not offset[1:3].isdigit()
                or not offset[4:].isdigit()
                or int(offset[1:3]) > 23
                or int(offset[4:]) > 59
            ):
                raise ValueError
            return EffectiveResolutionTime(
                datetime.fromisoformat(wall + offset)
            ).instant
        except ValueError as error:
            raise ValidationError(
                "Enter an exact effective time and a UTC offset such as -07:00.",
                field="effective_resolution_at",
            ) from error
