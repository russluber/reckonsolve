"""Individual WIS presentation; all calculations come from the analytics boundary."""

from fractions import Fraction

from PySide6.QtWidgets import QGroupBox, QVBoxLayout, QWidget

from reckonsolve.analytics.quantiles import QuantileScorecard
from reckonsolve.quantile_display import exact_score_text, quantile_scorecard_lines
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.scorecard_chart import ScoredIntervalsChart
from reckonsolve.ui.scorecard_components import ScoreGroup, ScoreGroups, score_label
from reckonsolve.ui.visual_system import Spacing, TextRole


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
        # Keep the shared CLI/nonvisual facts authoritative, but do not render its
        # prose as the desktop's expanded layout.
        for index, text in enumerate(lines):
            if index < 3 or text.startswith(("Scoring facts", "Revisions excluded")):
                label = score_label(
                    text,
                    self,
                    role=TextRole.FORECAST
                    if text.startswith("WIS:")
                    else TextRole.BODY,
                )
                label.setObjectName(f"numericWISFact{index}")
                self.body_layout.addWidget(label)
        if card.final is None:
            return

        assert card.initial is not None and card.delta_wis is not None
        assert card.definition is not None and card.scoring_revision is not None
        details = QGroupBox("WIS Breakdown", self)
        details.setAccessibleName("WIS breakdown and initial/final comparison")
        details.setObjectName("numericWISDetails")
        details.setCheckable(True)
        details.setChecked(False)
        contents = QWidget(details)
        detail_layout = QVBoxLayout(contents)
        detail_layout.setSpacing(int(Spacing.SECTION))
        group_layout = QVBoxLayout(details)
        group_layout.addWidget(contents)
        details.toggled.connect(contents.setVisible)
        contents.hide()
        detail_layout.addWidget(
            score_label(
                "Final Forecast and Outcome", contents, role=TextRole.SECTION_TITLE
            )
        )
        detail_layout.addWidget(ScoredIntervalsChart(card, contents))
        detail_layout.addWidget(
            score_label(
                f"Scale: {card.definition.unit} · Bands: inclusive intervals · Vertical tick: median · Diamond: actual",
                contents,
                role=TextRole.SECONDARY,
            )
        )
        unit = card.definition.unit

        def quantity(value: Fraction) -> str:
            return f"{exact_score_text(value)} {unit}"

        comparison = ScoreGroup("Initial vs Final", contents)
        comparison.add_fact(
            "Initial WIS", quantity(card.initial.wis), name="individualInitialWIS"
        )
        comparison.add_fact(
            "Final WIS", quantity(card.final.wis), name="individualFinalWIS"
        )
        direction = (
            "Better"
            if card.delta_wis > 0
            else "Worse"
            if card.delta_wis < 0
            else "Equal"
        )
        comparison.add_fact(
            "Delta WIS",
            f"{quantity(card.delta_wis)} · {direction}",
            name="individualDeltaWIS",
            help_text="Initial minus final: positive means the final forecast scored better. This is hindsight within one Prediction, not causal skill or a cross-question score.",
        )
        median = ScoreGroup("Median", contents)
        median.add_fact(
            "Estimate",
            f"{card.scoring_revision.quantiles.q50} {unit}",
            name="scoredMedian",
        )
        median.add_fact("Actual", f"{card.actual_value} {unit}", name="scoredActual")
        median.add_fact(
            "Absolute error",
            quantity(card.final.median_absolute_error),
            name="individualMedianError",
        )
        median.add_fact(
            "Signed miss",
            quantity(card.final.signed_median_miss),
            name="individualMedianMiss",
            help_text="Actual minus median: positive means the actual was above the estimate; negative means below.",
        )
        median.add_fact(
            "WIS contribution",
            quantity(card.final.median_contribution),
            name="individualMedianContribution",
            help_text="Median weighted contribution to WIS: absolute error divided by five.",
        )
        detail_layout.addWidget(ScoreGroups((comparison, median), contents))

        intervals = []
        q = card.scoring_revision.quantiles
        for level, low, high, interval, contribution in (
            (
                50,
                q.q25,
                q.q75,
                card.final.interval_50,
                card.final.interval_50_contribution,
            ),
            (
                90,
                q.q05,
                q.q95,
                card.final.interval_90,
                card.final.interval_90_contribution,
            ),
        ):
            group = ScoreGroup(f"{level}% Interval", contents)
            group.add_fact(
                "Range", f"{low} to {high} {unit}", name=f"scoredInterval{level}Range"
            )
            group.add_fact(
                "Actual position",
                interval.outcome_location.capitalize(),
                name=f"scoredInterval{level}Position",
            )
            group.add_fact(
                "Width", quantity(interval.width), name=f"scoredInterval{level}Width"
            )
            group.add_fact(
                "Outside distance",
                quantity(interval.miss_distance),
                name=f"scoredInterval{level}Miss",
                help_text="Distance beyond the nearest endpoint; zero inside or exactly on an endpoint.",
            )
            group.add_fact(
                "Interval score",
                quantity(interval.score),
                name=f"scoredInterval{level}Score",
            )
            group.add_fact(
                "WIS contribution",
                quantity(contribution),
                name=f"scoredInterval{level}Contribution",
                help_text="This interval's weighted contribution, including the 2.5 denominator. The two interval contributions plus the median contribution sum to WIS.",
            )
            intervals.append(group)
        detail_layout.addWidget(ScoreGroups(tuple(intervals), contents))
        self.body_layout.addWidget(details)
