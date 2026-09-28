"""Documentary time input shared by presentations, without time-zone inference."""

import re


def parse_reported_offset(text: str) -> int:
    if not re.fullmatch(r"[+-]\d{2}:\d{2}", text):
        raise ValueError("Use an offset such as +05:30 or -07:00.")
    hours, minutes = int(text[1:3]), int(text[4:])
    if hours > 23 or minutes > 59:
        raise ValueError("UTC offset is outside the supported range.")
    return (hours * 60 + minutes) * (-1 if text[0] == "-" else 1)
