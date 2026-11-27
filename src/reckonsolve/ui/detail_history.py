"""Reading context for committed forecast charts, separate from scoring and storage."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.domain.quantiles import FiveQuantiles
from reckonsolve.ui.components import SectionRule
from reckonsolve.ui.one_shot_reading import OneShotReadingSection as ReadingSection
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


def organize_metadata(sections: tuple[tuple[QWidget, QLabel], ...]) -> None:
    """Give existing optional facts a reading hierarchy without replacing targets."""
    for section, value in sections:
        column = section.layout()
        assert isinstance(column, QBoxLayout)
        column.setDirection(QBoxLayout.Direction.TopToBottom)
        column.setContentsMargins(0, int(Spacing.ORDINARY), 0, 0)
        column.setSpacing(int(Spacing.CONTROL))
        heading = column.itemAt(0).widget()
        assert isinstance(heading, QLabel)
        heading.setText(heading.text().rstrip(":"))
        heading.setWordWrap(True)
        heading.setMinimumWidth(0)
        apply_text_role(heading, TextRole.DETAIL_EVENT)
        value.setWordWrap(True)
        value.setMinimumWidth(0)
        value.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        apply_text_role(value, TextRole.DETAIL_TEXT)
        column.addSpacing(int(Spacing.ORDINARY))
        column.addWidget(SectionRule(section))


def _text(value: str, parent: QWidget, *, secondary: bool = False) -> QLabel:
    label = QLabel(value, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    apply_text_role(label, TextRole.DETAIL_TIME if secondary else TextRole.DETAIL_TEXT)
    return label


def _facts(
    section: ReadingSection, rows: tuple[tuple[str, str], ...]
) -> dict[str, QLabel]:
    grid = QGridLayout()
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(int(Spacing.GROUP))
    grid.setVerticalSpacing(int(Spacing.CONTROL))
    grid.setColumnStretch(1, 1)
    values = {}
    for index, (name, content) in enumerate(rows):
        caption = _text(name, section, secondary=True)
        caption.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        value = _text(content, section)
        values[name] = value
        grid.addWidget(caption, index, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(value, index, 1)
    section.body_layout.addLayout(grid)
    return values


def binary_history_information(parent: QWidget) -> QWidget:
    body = QWidget(parent)
    body.setObjectName("probabilityHistoryInformation")
    column = QVBoxLayout(body)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)
    reading = ReadingSection("How to Read", body)
    _facts(
        reading,
        (
            ("Step line", "Standing probability between saved revisions"),
            ("Open circles", "Earlier committed forecasts"),
            ("Filled circle", "Latest committed forecast"),
        ),
    )
    column.addWidget(reading)
    return body


class DistributionInformation(QWidget):
    """Organize supplied exact values, interpolation limits and scoring context."""

    def __init__(self, context: QLabel, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("distributionInformation")
        column = QVBoxLayout(self)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        forecast = ReadingSection("Exact Forecast", self)
        self.values = _facts(
            forecast, (("90% interval", ""), ("Median", ""), ("50% interval", ""))
        )
        column.addWidget(forecast)
        reading = ReadingSection("How to Read", self)
        reading.body_layout.addWidget(
            _text(
                "Markers are the elicited percentiles. Dashed segments interpolate only between them; outer tails are unspecified. Equal values form vertical jumps.",
                reading,
            )
        )
        column.addWidget(reading)
        self.context_section = ReadingSection("History & Scoring", self)
        self.context = context
        apply_text_role(context, TextRole.DETAIL_TEXT)
        self.context_section.body_layout.addWidget(context)
        context.show()
        # Read the latest-versus-scored qualification before the exact values.
        column.insertWidget(0, self.context_section)
        self.hide()

    def set_forecast(self, quantiles: FiveQuantiles, unit: str, context: str) -> None:
        suffix = " " + unit if unit else ""
        self.values["90% interval"].setText(
            f"{quantiles.q05} to {quantiles.q95}{suffix}"
        )
        self.values["Median"].setText(f"{quantiles.q50}{suffix}")
        self.values["50% interval"].setText(
            f"{quantiles.q25} to {quantiles.q75}{suffix}"
        )
        # The actual label is owned by the screen so existing context access
        # remains explicit; this component performs no forecast selection.
        self.context.setText(context)
        self.context_section.setVisible(bool(context))
        self.show()
