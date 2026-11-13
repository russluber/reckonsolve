"""Identity-scoped desktop date presentation; canonical instants stay untouched."""

import re
from datetime import date, datetime
from enum import StrEnum

from PySide6.QtCore import QDateTime, QTimeZone
from PySide6.QtWidgets import QDateEdit, QDateTimeEdit, QTimeEdit, QWidget


class DateFormat(StrEnum):
    DAY_FIRST = "DD-MM-YYYY"
    MONTH_FIRST = "MM-DD-YYYY"
    YEAR_FIRST = "YYYY-MM-DD"

    @property
    def python_pattern(self) -> str:
        return {
            self.DAY_FIRST: "%d-%m-%Y",
            self.MONTH_FIRST: "%m-%d-%Y",
            self.YEAR_FIRST: "%Y-%m-%d",
        }[self]

    @property
    def qt_pattern(self) -> str:
        return self.value.replace("DD", "dd").replace("YYYY", "yyyy")


def date_format_for(widget: QWidget | None = None) -> DateFormat:
    while widget is not None:
        value = getattr(widget, "display_date_format", None)
        if value is not None:
            return DateFormat(value)
        widget = widget.parentWidget()
    return DateFormat.YEAR_FIRST


def date_context(widget: QWidget | None = None) -> tuple[DateFormat, str, int]:
    now = QDateTime.currentDateTime()
    return (
        date_format_for(widget),
        bytes(QTimeZone.systemTimeZoneId()).decode("utf-8"),
        now.offsetFromUtc(),
    )


def format_date(value: date | datetime | None, widget: QWidget | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.astimezone().date()
    return value.strftime(date_format_for(widget).python_pattern)


def format_datetime(
    value: datetime, widget: QWidget | None = None, *, include_offset: bool = False
) -> str:
    local = value.astimezone()
    text = f"{format_date(local.date(), widget)}, {local.strftime('%I:%M %p')}"
    if include_offset:
        offset = local.strftime("%z")
        text += f" UTC{offset[:3]}:{offset[3:]}"
    return text


def format_reported_time(value, widget: QWidget | None = None) -> str:
    """Documentary wall time retains its own reported offset, never Windows time."""
    if value is None:
        return "Not reported"
    text = f"{format_date(value.wall_time.date(), widget)}, {value.wall_time.strftime('%I:%M %p')}"
    if value.offset_minutes is not None:
        offset = value.offset_minutes
        text += f" UTC{'+' if offset >= 0 else '-'}{abs(offset) // 60:02}:{abs(offset) % 60:02}"
    return text + (" (approximate)" if value.approximate else "")


def format_exact_datetime(value: datetime, widget: QWidget | None = None) -> str:
    local = value.astimezone()
    text = f"{format_date(local.date(), widget)}, {local.strftime('%H:%M:%S')}"
    if local.microsecond:
        text += f".{local.microsecond:06}"
    offset = local.strftime("%z")
    return text + f" UTC{offset[:3]}:{offset[3:]}"


def input_date_format(widget: QWidget, suffix: str = "") -> str:
    return date_format_for(widget).qt_pattern + suffix


def update_date_inputs(widget: QWidget) -> None:
    """Change presentation only, retaining native values and time precision."""
    inputs = widget.findChildren(QDateTimeEdit)
    if isinstance(widget, QDateTimeEdit):
        inputs.insert(0, widget)
    for editor in inputs:
        if isinstance(editor, QTimeEdit):
            continue
        suffix = ""
        if not isinstance(editor, QDateEdit):
            match = re.search(r"\s+[hH].*", editor.displayFormat())
            suffix = match.group(0) if match else " HH:mm"
        editor.setDisplayFormat(input_date_format(editor, suffix))


def windows_zone_description() -> str:
    now = QDateTime.currentDateTime()
    zone = QTimeZone.systemTimeZone()
    seconds = now.offsetFromUtc()
    minutes = abs(seconds) // 60
    return (
        f"Follow Windows · {zone.displayName(now)} · "
        f"UTC{'+' if seconds >= 0 else '-'}{minutes // 60:02}:{minutes % 60:02}"
    )
