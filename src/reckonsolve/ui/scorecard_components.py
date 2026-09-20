"""Small, selectable presentation groups for individual resolved forecasts."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QBoxLayout,
    QGridLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from reckonsolve.analytics.trajectory import TrajectoryScorecard
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


def score_label(
    text: str, parent: QWidget, *, role: TextRole = TextRole.BODY, help_text: str = ""
) -> QLabel:
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    label.setMinimumWidth(0)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.TextSelectableByMouse
        | Qt.TextInteractionFlag.TextSelectableByKeyboard
    )
    label.setToolTip(help_text)
    label.setAccessibleDescription(help_text)
    apply_text_role(label, role)
    return label


class ScoreGroup(QWidget):
    """Flat caption/value rows; explanations stay in accessible contextual help."""

    def __init__(self, title: str, parent: QWidget) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(Spacing.CONTROL))
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(score_label(title, self, role=TextRole.SECTION_TITLE))
        self.rows = QGridLayout()
        self.rows.setColumnStretch(0, 1)
        self.rows.setColumnStretch(1, 1)
        self.rows.setHorizontalSpacing(int(Spacing.ORDINARY))
        self.rows.setVerticalSpacing(int(Spacing.CONTROL))
        layout.addLayout(self.rows)

    def add_fact(
        self, caption: str, value: str, *, name: str, help_text: str = ""
    ) -> None:
        row = self.rows.rowCount()
        label = score_label(caption, self, role=TextRole.SECONDARY, help_text=help_text)
        fact = score_label(value, self, role=TextRole.LABEL, help_text=help_text)
        fact.setObjectName(name)
        fact.setAccessibleName(f"{caption}: {value}")
        fact.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        self.rows.addWidget(label, row, 0)
        self.rows.addWidget(fact, row, 1)


class ScoreGroups(QWidget):
    """Equal-width groups when roomy, top-aligned vertical groups when narrow."""

    def __init__(self, groups: tuple[QWidget, ...], parent: QWidget) -> None:
        super().__init__(parent)
        self._groups = groups
        # A horizontal pass must not pin the enclosing scroll page at that width
        # and prevent the next resize from reaching the stacking breakpoint.
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._layout = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(int(Spacing.SECTION))
        for group in groups:
            self._layout.addWidget(group)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        # Scale the breakpoint with native text, not just display pixels.
        threshold = len(self._groups) * max(
            240, self.fontMetrics().horizontalAdvance("M") * 27
        )
        horizontal = event.size().width() >= threshold
        self._layout.setDirection(
            QBoxLayout.Direction.LeftToRight
            if horizontal
            else QBoxLayout.Direction.TopToBottom
        )
        for index in range(len(self._groups)):
            self._layout.setStretch(index, 1 if horizontal else 0)


class TrajectoryScoreDetails(ScoreGroups):
    def __init__(self, card: TrajectoryScorecard, parent: QWidget) -> None:
        probability = ScoreGroup("Probability Scores", parent)
        updating = ScoreGroup("Updating", parent)
        timing = ScoreGroup("Timing", parent)
        super().__init__((probability, updating, timing), parent)
        self.setObjectName("trajectoryScoreDetails")
        for caption, name, value in (
            ("Initial Brier", "individualInitialBrier", card.initial_brier),
            ("Final Brier", "individualFinalBrier", card.final_brier),
        ):
            probability.add_fact(
                caption,
                f"{float(value):.4f}",
                name=name,
                help_text="One probability scored against the effective outcome. Lower is better.",
            )
        updating.add_fact(
            "Hold-initial Trajectory Brier",
            f"{float(card.hold_initial_brier):.4f}",
            name="individualHoldInitialBrier",
            help_text="The trajectory score if the first probability had stood throughout eligible forecasting time.",
        )
        updating.add_fact(
            "Actual Trajectory Brier",
            f"{float(card.trajectory_brier):.4f}",
            name="individualTrajectoryBrier",
        )
        direction = (
            "Helped"
            if card.updating_gain > 0
            else "Hurt"
            if card.updating_gain < 0
            else "Tied"
        )
        updating.add_fact(
            "Updating Gain",
            f"{float(card.updating_gain):+.4f} · {direction}",
            name="individualUpdatingGain",
            help_text="Hold-initial minus actual Trajectory Brier. This is mechanical hindsight, not proof of forecasting skill.",
        )
        timing.add_fact(
            "Forecast Weight",
            f"{float(card.active_forecast_fraction):.1%}",
            name="individualForecastWeight",
            help_text="Active Forecast Fraction: the share of this Prediction's planned window using your standing forecasts. Not an average or a share of the resulting score.",
        )
        timing.add_fact(
            "Neutral Weight",
            f"{float(1 - card.active_forecast_fraction):.1%}",
            name="individualNeutralWeight",
            help_text="The remaining share after early effective resolution uses neutral loss 0.25. No forecast is added.",
        )
