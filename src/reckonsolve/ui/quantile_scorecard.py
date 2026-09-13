"""Individual WIS presentation; all calculations come from the analytics boundary."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QWidget

from reckonsolve.analytics.quantiles import QuantileScorecard
from reckonsolve.quantile_display import quantile_scorecard_lines
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.visual_system import TextRole, apply_text_role


class QuantileScorecardPanel(ContentPanel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Numeric WIS scorecard", parent=parent)
        self.setObjectName("numericQuantileScorecard")

    def set_scorecard(self, card: QuantileScorecard) -> None:
        while self.body_layout.count():
            widget = self.body_layout.takeAt(0).widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        lines = quantile_scorecard_lines(card)
        details = QGroupBox("WIS breakdown and initial/final comparison", self)
        details.setCheckable(True)
        details.setChecked(False)
        contents = QWidget(details)
        detail_layout = QVBoxLayout(contents)
        group_layout = QVBoxLayout(details)
        group_layout.addWidget(contents)
        details.toggled.connect(contents.setVisible)
        contents.hide()
        for index, text in enumerate(lines):
            label = QLabel(text, self)
            label.setObjectName(f"numericWISFact{index}")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
                | Qt.TextInteractionFlag.TextSelectableByKeyboard
            )
            apply_text_role(
                label, TextRole.FORECAST if text.startswith("WIS:") else TextRole.BODY
            )
            if index < 3 or text.startswith(("Scoring facts", "Revisions excluded")):
                self.body_layout.addWidget(label)
            else:
                detail_layout.addWidget(label)
        if card.final is not None:
            self.body_layout.addWidget(details)
        else:
            details.deleteLater()
