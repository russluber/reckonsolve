"""Framed Binary results using supplied analytical facts, without data operations."""

from PySide6.QtWidgets import QVBoxLayout, QWidget

from reckonsolve.analytics.trajectory import TrajectoryScorecard
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.detail_workspace import collapse_section
from reckonsolve.ui.one_shot_reading import finish_disclosure
from reckonsolve.ui.scorecard_components import (
    ReadingScoreGroup,
    TrajectoryScoreDetails,
    score_label,
)
from reckonsolve.ui.visual_system import TextRole


class BinaryScorecardPanel(ContentPanel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__("Binary Scorecard", parent=parent)
        self.setObjectName("predictionScorecard")
        self.setProperty("reckonsolveScorecard", "true")
        self.title_label.setWordWrap(True)
        self.title_label.setMinimumWidth(0)
        self.summary = QWidget(self)
        self.summary_layout = QVBoxLayout(self.summary)
        self.summary_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.addWidget(self.summary)
        content = QWidget(self)
        content.setObjectName("trajectoryDiagnosticsContent")
        self.details_layout = QVBoxLayout(content)
        self.details_layout.setContentsMargins(0, 0, 0, 0)
        self.details = finish_disclosure(
            collapse_section(content, "Timing & Updating Details", text_link=True),
            end_rule=False,
        )
        self.details.setObjectName("trajectoryDiagnostics")
        self.body_layout.addWidget(self.details)

    def set_scorecard(self, card: TrajectoryScorecard) -> None:
        for layout in (self.summary_layout, self.details_layout):
            while layout.count():
                widget = layout.takeAt(0).widget()
                if widget is not None:
                    widget.hide()
                    widget.setParent(None)
                    widget.deleteLater()
        self.details.disclosure_button.setChecked(False)
        self.details.setVisible(not card.unscored_reason)
        if card.unscored_reason:
            self.summary_layout.addWidget(score_label(card.unscored_reason, self))
            return
        probability = ReadingScoreGroup("Probability Scores", self)
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
        probability.add_fact(
            "Final Eligible Forecast",
            f"{card.segments[-1].probability_percent}% Yes",
            name="binaryFinalEligibleForecast",
            help_text="The final eligible forecast used for Final Brier; later excluded revisions stay in Timeline.",
        )
        self.summary_layout.addWidget(probability)
        context = "Lower Brier is better."
        if card.excluded_revision_ids:
            context += " Revisions at or after the scoring cutoff remain in Timeline; they are not scored."
        if card.scoring_facts_corrected:
            context += (
                " Scoring uses corrected facts; originals remain in Resolution History."
            )
        self.summary_layout.addWidget(
            score_label(context, self, role=TextRole.SECONDARY)
        )
        self.details_layout.addWidget(TrajectoryScoreDetails(card, self))
        self.details_layout.addWidget(
            score_label(
                "Updating Gain is mechanical hindsight, not proof of skill. Forecast and Neutral Weights describe the original forecasting window, not shares of the score. The neutral remainder uses loss 0.25; it adds no forecast.",
                self,
                role=TextRole.SECONDARY,
            )
        )
