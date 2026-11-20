"""Organized supporting readouts for a saved One-Shot Numeric score."""

from fractions import Fraction

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QVBoxLayout, QWidget

from reckonsolve.analytics.quantiles import WISScore
from reckonsolve.quantile_display import exact_score_text
from reckonsolve.ui.one_shot import text_label
from reckonsolve.ui.one_shot_reading import OneShotReadingSection
from reckonsolve.ui.visual_system import Spacing, TextRole, apply_text_role


def score_breakdown(score: WISScore, unit: str, parent: QWidget) -> QWidget:
    """Display supplied exact terms; never recalculate or pool scores in the UI."""
    body = QWidget(parent)
    body.setObjectName("oneShotScoreBreakdown")
    column = QVBoxLayout(body)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(0)

    def quantity(value: Fraction) -> str:
        return exact_score_text(value) + (" " + unit if unit else "")

    def group(
        title: str, rows: tuple[tuple[str, str], ...], *, end_rule: bool = True
    ) -> OneShotReadingSection:
        section = OneShotReadingSection(title, body, end_rule=end_rule)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(int(Spacing.GROUP))
        grid.setVerticalSpacing(int(Spacing.CONTROL))
        grid.setColumnStretch(1, 1)
        for index, (name, value) in enumerate(rows):
            label = text_label(name, section)
            label.setMinimumWidth(0)
            apply_text_role(label, TextRole.DETAIL_TIME)
            text = text_label(value, section)
            text.setMinimumWidth(0)
            text.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            apply_text_role(text, TextRole.DETAIL_TEXT)
            grid.addWidget(label, index, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(text, index, 1)
        section.body_layout.addLayout(grid)
        column.addWidget(section)
        return section

    group(
        "Contributions to WIS",
        (
            ("Median", quantity(score.median_contribution)),
            ("50% interval", quantity(score.interval_50_contribution)),
            ("90% interval", quantity(score.interval_90_contribution)),
        ),
    )
    median = group(
        "Median Error",
        (
            ("Absolute error", quantity(score.median_absolute_error)),
            ("Signed miss", quantity(score.signed_median_miss)),
        ),
    )
    explanation = text_label("Signed miss is actual minus median.", median)
    apply_text_role(explanation, TextRole.DETAIL_TIME)
    median.body_layout.addWidget(explanation)
    for coverage, interval in ((50, score.interval_50), (90, score.interval_90)):
        group(
            f"{coverage}% Interval",
            (
                ("Actual", interval.outcome_location.capitalize() + " interval"),
                ("Width", quantity(interval.width)),
                ("Miss distance", quantity(interval.miss_distance)),
                ("Interval score", quantity(interval.score)),
            ),
            end_rule=coverage != 90,
        )
    return body
