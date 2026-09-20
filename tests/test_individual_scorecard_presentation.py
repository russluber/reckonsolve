"""Resolved Detail presentation keeps exact, accessible scoring context."""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QGroupBox, QLabel

from reckonsolve.analytics.quantiles import QuantileScorecard, weighted_interval_score
from reckonsolve.domain.predictions import FixedPrecisionValue
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
    QuantileRevision,
)
from reckonsolve.quantile_display import exact_score_text
from reckonsolve.ui.quantile_scorecard import QuantileScorecardPanel
from reckonsolve.ui.scorecard_chart import ScoredIntervalsChart
from reckonsolve.ui.visual_system import install_visual_system


def make_card(values=(1, 3, 5, 7, 9), actual=6, precision=1):
    definition = QuantileDefinition(
        "days", precision, NumericValueConstraint.CONTINUOUS
    )
    quantiles = FiveQuantiles.from_values(
        dict(zip((5, 25, 50, 75, 95), values)), precision
    )
    actual = FixedPrecisionValue.from_value(actual, precision)
    score = weighted_interval_score(definition, quantiles, actual)
    revision = QuantileRevision(1, 1, quantiles, 1, datetime(2026, 9, 1, tzinfo=UTC))
    return QuantileScorecard(
        prediction_id=1,
        final_revision_id=1,
        excluded_revision_ids=(),
        initial=score,
        final=score,
        delta_wis=Fraction(),
        unscored_reason=None,
        definition=definition,
        actual_value=actual,
        scoring_revision=revision,
    )


@pytest.mark.parametrize(
    "values,actual",
    [
        ((1, 3, 5, 7, 9), 6),  # Inside both
        ((1, 3, 5, 7, 9), 8),  # Between inner and outer
        ((1, 3, 5, 7, 9), -2),  # Below both
        ((1, 3, 5, 7, 9), 12),  # Above both
        ((1, 3, 5, 7, 9), 9),  # Endpoint is inside
        ((3, 3, 3, 3, 3), 3),  # Degenerate intervals and tied median/actual
        ((-9, -7, -5, -3, -1), -6),
        ((10**16, 10**16 + 2, 10**16 + 4, 10**16 + 6, 10**16 + 8), 10**16 + 9),
    ],
)
def test_exact_chart_projection_and_text(qtbot, values, actual):
    card = make_card(values, actual)
    panel = QuantileScorecardPanel()
    qtbot.addWidget(panel)
    panel.set_scorecard(card)
    panel.resize(700, 900)
    panel.show()
    panel.findChild(QGroupBox).setChecked(True)
    qtbot.wait(10)
    chart = panel.findChild(ScoredIntervalsChart)
    points = chart.marker_positions()
    assert all(0 <= x <= chart.width() for x in points)
    assert list(points[:5]) == sorted(points[:5])
    if actual == values[4]:
        assert points[5] == points[4]
    if len(set(values)) == 1 and actual == values[0]:
        assert len(set(points)) == 1
    if values[-1] > values[0]:
        assert (points[1] - points[0]) / (points[4] - points[0]) == pytest.approx(
            float(Fraction(values[1] - values[0], values[4] - values[0]))
        )
    assert f"actual {card.actual_value}" in chart.accessibleDescription()
    assert (
        panel.findChild(QLabel, "scoredInterval90Position").text()
        == card.final.interval_90.outcome_location.capitalize()
    )
    assert (
        panel.findChild(QLabel, "individualFinalWIS").text()
        == f"{exact_score_text(card.final.wis)} days"
    )
    assert not chart.grab().isNull()


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("font_size", [9, 12])
def test_scorecard_resize_roundtrip_and_palette(qtbot, qapp, tmp_path, dark, font_size):
    original_palette, original_font = qapp.palette(), qapp.font()
    try:
        palette = QPalette(original_palette)
        for role in (
            QPalette.ColorRole.Window,
            QPalette.ColorRole.Base,
            QPalette.ColorRole.Button,
        ):
            palette.setColor(role, QColor("#202020" if dark else "#ffffff"))
        for role in (
            QPalette.ColorRole.WindowText,
            QPalette.ColorRole.Text,
            QPalette.ColorRole.ButtonText,
        ):
            palette.setColor(role, QColor("#ffffff" if dark else "#202020"))
        qapp.setPalette(palette)
        qapp.setFont(QFont("Segoe UI", font_size))
        panel = QuantileScorecardPanel()
        qtbot.addWidget(panel)
        install_visual_system(panel)
        panel.set_scorecard(make_card(actual=12))
        panel.findChild(QGroupBox).setChecked(True)
        panel.show()
        for width in (1300, 450, 1300):
            panel.resize(width, panel.sizeHint().height())
            qtbot.wait(20)
            panel.resize(width, panel.sizeHint().height())
            qtbot.wait(20)
            assert panel.width() == width
            for label in panel.body.findChildren(QLabel):
                if label.isVisible():
                    assert label.textFormat() == Qt.TextFormat.PlainText
                    assert (
                        label.textInteractionFlags()
                        & Qt.TextInteractionFlag.TextSelectableByMouse
                    )
                    assert label.width() <= panel.width()
            assert panel.grab().save(str(tmp_path / f"scorecard-{width}.png"))
    finally:
        qapp.setPalette(original_palette)
        qapp.setFont(original_font)


def test_corrected_and_unscored_refresh_remove_stale_graphics(qtbot):
    panel = QuantileScorecardPanel()
    qtbot.addWidget(panel)
    panel.set_scorecard(make_card())
    before = panel.findChild(ScoredIntervalsChart).accessibleDescription()
    corrected = replace(
        make_card(actual=12), scoring_facts_corrected=True, excluded_revision_ids=(2,)
    )
    panel.set_scorecard(corrected)
    assert panel.findChild(ScoredIntervalsChart).accessibleDescription() != before
    assert len(panel.findChildren(ScoredIntervalsChart)) == 1
    texts = "\n".join(label.text() for label in panel.findChildren(QLabel))
    assert "Scoring facts corrected" in texts
    assert "Revisions excluded" in texts
    panel.set_scorecard(
        replace(
            corrected,
            final=None,
            initial=None,
            scoring_revision=None,
            unscored_reason="Outcome at or before the first forecast.",
        )
    )
    assert panel.findChild(ScoredIntervalsChart) is None
    assert panel.findChild(QGroupBox) is None
    assert "Not scored" in "\n".join(
        label.text() for label in panel.findChildren(QLabel)
    )


@pytest.mark.parametrize("width", [300, 1000])
@pytest.mark.parametrize(
    "values,actual",
    [
        ((1, 3, 5, 7, 9), 12),
        ((1, 3, 5, 7, 9), 10000),
        ((3, 3, 3, 3, 3), 3),
    ],
)
def test_interval_labels_show_bounds_and_median_without_overlapping(
    qtbot, width, values, actual
):
    panel = QuantileScorecardPanel()
    qtbot.addWidget(panel)
    card = make_card(values, actual)
    chart = ScoredIntervalsChart(card, panel)
    chart.resize(width, chart.height())
    chart.show()
    panel.show()
    qtbot.wait(10)
    layout = chart.label_layout()
    for (_, labels), indices in zip(layout, ((0, 2, 4), (1, 2, 3)), strict=True):
        text = " ".join(value for value, _, _ in labels)
        for index in indices:
            assert str(FixedPrecisionValue.from_value(values[index], 1)) in text
        for index, (_, rect, _) in enumerate(labels):
            assert 0 <= rect.left() <= rect.right() <= chart.width()
            for _, other, _ in labels[index + 1 :]:
                assert not rect.intersects(other)
    assert max(rect.bottom() for _, rect, _ in layout[0][1]) < layout[1][0] - 22
    assert max(rect.bottom() for _, rect, _ in layout[1][1]) < chart.height()
    for y, labels in layout:
        actual_labels = [
            (text, rect, anchor)
            for text, rect, anchor in labels
            if anchor == chart.marker_positions()[5]
        ]
        assert len(actual_labels) == 1
        text, rect, anchor = actual_labels[0]
        assert str(card.actual_value) in text
        assert anchor == chart.marker_positions()[5]
        assert rect.top() > y + 9


def test_actual_annotation_only_for_crowded_or_coincident_labels(qtbot):
    panel = QuantileScorecardPanel()
    qtbot.addWidget(panel)
    chart = ScoredIntervalsChart(make_card(actual="7.5"), panel)
    # At a wide size, 7.5 is distinguishable from the inner upper endpoint 7.0.
    # Narrowing crowds that pair; widening must remove the extra annotation again.
    for width, annotated in ((1000, False), (300, True), (1000, False)):
        chart.resize(width, chart.height())
        _, labels = chart.label_layout()[1]
        text = next(
            text for text, _, anchor in labels if anchor == chart.marker_positions()[5]
        )
        assert text == ("7.5 (actual)" if annotated else "7.5")
    tied = ScoredIntervalsChart(make_card(actual=5), panel)
    for _, labels in tied.label_layout():
        text = next(
            text for text, _, anchor in labels if anchor == tied.marker_positions()[5]
        )
        assert text == "5.0 (median/actual)"
