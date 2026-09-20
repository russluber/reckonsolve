"""M49 equal-Prediction trajectory Binary analytics and presentation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QLabel, QWidget

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.ui.analytics_components import CompactMetricGroup
from reckonsolve.ui.analytics_screen import AnalyticsScreen
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.visual_system import install_visual_system, semantic_colors

START = datetime(2026, 9, 10, 12, tzinfo=UTC)


@dataclass
class Clock:
    instant: datetime = START

    def now(self) -> datetime:
        return self.instant


@pytest.fixture
def active(tmp_path):
    database = Database.open(tmp_path / "trajectory-analytics.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    yield clock, operations
    database.close()


def _context(prediction) -> dict[str, int]:
    return {
        "expected_revision_id": prediction.current_revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


def test_equal_prediction_mean_filters_and_legacy_boundary(active) -> None:
    clock, operations = active
    long_wrong = operations.create_prediction(
        "Long and wrong?",
        0,
        forecast_deadline=START + timedelta(days=100),
        tags=("Shared", "Long"),
    )
    short_right = operations.create_prediction(
        "Short and right?",
        100,
        forecast_deadline=START + timedelta(hours=2),
        tags=("Shared", "Short"),
    )
    legacy = operations._create_legacy_prediction(
        "Legacy stays separate?", 50, tags=("Shared",)
    )
    clock.instant = START + timedelta(days=101)
    operations.resolve_prediction(
        long_wrong.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=START + timedelta(days=100),
        **_context(long_wrong),
    )
    operations.resolve_prediction(
        short_right.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=START + timedelta(hours=2),
        **_context(short_right),
    )
    operations.resolve_prediction(
        legacy.prediction_id,
        BinaryOutcome.YES,
        **_context(legacy),
    )

    snapshot = operations.get_forecast_analytics()
    trajectory = snapshot.trajectory_binary
    assert trajectory.scored_prediction_count == 2
    assert trajectory.mean_trajectory_brier == Fraction(1, 2)
    assert trajectory.reached_deadline_count == 2
    assert trajectory.early_resolution_count == 0
    assert trajectory.mean_active_forecast_fraction == 1
    assert trajectory.final_calibration_bins[0].count == 1
    assert trajectory.final_calibration_bins[0].observed_yes_percent == 100
    assert trajectory.final_calibration_bins[9].count == 1
    assert snapshot.binary.scored_prediction_count == 1
    assert snapshot.binary.mean_brier == pytest.approx(0.25)
    assert set(snapshot.available_tags) == {"Long", "Shared", "Short"}

    filtered = operations.get_forecast_analytics(tag="long")
    assert filtered.trajectory_binary.scored_prediction_count == 1
    assert filtered.trajectory_binary.mean_trajectory_brier == 1
    assert filtered.binary.scored_prediction_count == 0
    numeric_only = operations.get_forecast_analytics(
        prediction_type=PredictionType.NUMERIC
    )
    assert numeric_only.trajectory_binary.resolved_candidate_count == 0
    assert not numeric_only.available_tags


def test_early_timing_updates_and_unscored_resolution_are_explained(active) -> None:
    clock, operations = active
    updated = operations.create_prediction(
        "Did updating help?",
        20,
        forecast_deadline=START + timedelta(hours=10),
    )
    clock.instant += timedelta(hours=2)
    updated = operations.revise_forecast(updated.prediction_id, 80, **_context(updated))
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        updated.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(updated),
    )
    clock.instant += timedelta(minutes=1)
    unscored = operations.create_prediction(
        "Already fixed?",
        50,
        forecast_deadline=clock.instant + timedelta(hours=1),
    )
    invalid = operations.create_prediction(
        "Invalid must not count?",
        99,
        forecast_deadline=clock.instant + timedelta(hours=2),
    )
    first_at = clock.instant
    clock.instant += timedelta(minutes=5)
    operations.resolve_prediction(
        unscored.prediction_id,
        BinaryOutcome.NO,
        effective_resolution_at=first_at,
        **_context(unscored),
    )
    operations.invalidate_prediction(
        invalid.prediction_id,
        reason="Question became malformed",
        **_context(invalid),
    )

    trajectory = operations.get_forecast_analytics().trajectory_binary
    assert trajectory.resolved_candidate_count == 2
    assert trajectory.scored_prediction_count == 1
    assert trajectory.unscored_prediction_count == 1
    assert trajectory.early_resolution_count == 1
    assert trajectory.reached_deadline_count == 0
    assert trajectory.mean_active_forecast_fraction == Fraction(2, 5)
    assert trajectory.positive_updating_gain_count == 1
    assert trajectory.equal_updating_gain_count == 0
    assert trajectory.negative_updating_gain_count == 0
    assert sum(item.count for item in trajectory.final_calibration_bins) == 1

    history = operations.get_binary_resolution_history(updated.prediction_id)
    clock.instant += timedelta(minutes=1)
    operations.correct_binary_resolution(
        updated.prediction_id,
        BinaryOutcome.NO,
        resolution_notes=None,
        postmortem=None,
        correction_reason="Verified the opposite outcome",
        expected_correction_id=history.current_correction_id,
    )
    corrected = operations.get_forecast_analytics().trajectory_binary
    assert corrected.scored_prediction_count == 1
    assert corrected.negative_updating_gain_count == 1
    assert corrected.positive_updating_gain_count == 0
    assert corrected.final_calibration_bins[8].observed_yes_percent == 0


def test_trajectory_analytics_screen_keeps_score_and_calibration_distinct(
    active, qtbot
) -> None:
    clock, operations = active
    prediction = operations.create_prediction(
        "Will the trajectory render?",
        70,
        forecast_deadline=START + timedelta(hours=2),
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(prediction),
    )
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.show()
    screen.refresh()

    assert screen.findChild(QLabel, "trajectoryAnalyticsScoredCount").text() == "1"
    assert screen.findChild(QLabel, "analyticsMeanTrajectoryBrier").text() == ("0.090")
    guidance = screen.findChild(QLabel, "trajectoryAnalyticsGuidance")
    assert guidance.text() == "Updates: 0 helped · 1 tied · 0 hurt"
    assert "does not prove" in guidance.toolTip()
    calibration = screen.findChild(QWidget, "trajectoryCalibrationSection")
    legacy = screen.findChild(ContentPanel, "analyticsBrierSummary")
    assert not calibration.isHidden()
    assert legacy.title_label.text() == "Legacy Binary Forecast — Final Brier"
    assert (
        "no interpolation"
        in screen.trajectory_calibration_chart.accessibleDescription()
    )


def test_analytics_guide_trajectory_worked_example(active, qtbot):
    clock, operations = active
    prediction = operations.create_prediction(
        "Guide example", 20, forecast_deadline=START + timedelta(hours=10)
    )
    clock.instant += timedelta(hours=2)
    prediction = operations.revise_forecast(
        prediction.prediction_id, 80, **_context(prediction)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        prediction.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(prediction),
    )
    result = operations.get_forecast_analytics().trajectory_binary
    assert result.mean_trajectory_brier == Fraction(286, 1000)
    assert result.mean_initial_brier == Fraction(64, 100)
    assert result.mean_final_brier == Fraction(4, 100)
    assert result.mean_hold_initial_brier == Fraction(406, 1000)
    assert result.mean_updating_gain == Fraction(12, 100)
    assert result.mean_active_forecast_fraction == Fraction(40, 100)
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.refresh()
    assert screen.trajectory_active_fraction.text() == "40%"
    assert screen.trajectory_neutral_fraction.text() == "60%"
    assert (
        "4 hours into a 10-hour window" in screen.trajectory_active_fraction.toolTip()
    )
    assert "Average Neutral Weight: 60%" == (
        screen.trajectory_neutral_fraction.accessibleName()
    )


def test_trajectory_window_shares_without_eligible_scores_are_unavailable(
    active, qtbot
):
    _, operations = active
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.refresh()
    assert screen.trajectory_active_fraction.text() == "Not available"
    assert screen.trajectory_neutral_fraction.text() == "Not available"


def test_analytics_card_titles_and_on_demand_help(active, qtbot):
    _, operations = active
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.refresh()
    panels = screen.findChildren(ContentPanel)
    assert {panel.title_label.text() for panel in panels} == {
        "Analytics View",
        "Trajectory Binary Forecast",
        "Trajectory Binary Final-Probability Calibration",
        "Legacy Binary Forecast — Final Brier",
        "Legacy Numeric Forecast — Interval-v1",
        "Legacy Binary Calibration / Reliability",
        "Legacy Cumulative Mean Final Brier by Resolution Time",
        "Legacy Numeric Containment Calibration",
        "Legacy Binary Retrospective Update Feedback",
        "Legacy Numeric Retrospective Update Feedback",
        "Five-Quantile Numeric Forecast",
        "Five-Quantile Updates — Initial versus Final",
        "Continuous-Style Calibration",
        "Whole-Number Calibration",
        "50% Interval",
        "90% Interval",
        "Median Balance",
    }
    for panel in panels:
        assert panel.supporting_label.isHidden()
        assert panel.title_label.toolTip()
        assert panel.accessibleDescription() == panel.title_label.toolTip()
    assert screen.findChild(QLabel, "analyticsIntroduction").isHidden()
    assert (
        screen.binary_update_guidance.text() == "No revised pairs match these filters."
    )
    assert (
        screen.numeric_update_guidance.text() == "No revised pairs match these filters."
    )
    assert (
        screen.quantile_content.summary.text() == "0 eligible · 0 resolved · 0 unscored"
    )
    assert (
        screen.quantile_content.update_guidance.text()
        == "0 revised pairs · 0 unrevised"
    )
    captions = {
        label.text() for label in screen.trajectory_summary.findChildren(QLabel)
    }
    assert {"Average Forecast Weight", "Average Neutral Weight"} <= captions


def test_analytics_guide_numeric_and_uncertainty_examples():
    from reckonsolve.analytics.quantile_aggregate import Proportion
    from reckonsolve.analytics.quantiles import weighted_interval_score
    from reckonsolve.domain.predictions import FixedPrecisionValue
    from reckonsolve.domain.quantiles import (
        FiveQuantiles,
        NumericValueConstraint,
        QuantileDefinition,
    )

    definition = QuantileDefinition("days", 1, NumericValueConstraint.CONTINUOUS)
    quantiles = FiveQuantiles.from_values({5: 1, 25: 3, 50: 5, 75: 7, 95: 9}, 1)
    for actual, expected in ((6, Fraction(76, 100)), (12, Fraction(516, 100))):
        assert (
            weighted_interval_score(
                definition, quantiles, FixedPrecisionValue.from_value(actual, 1)
            ).wis
            == expected
        )
    actual = FixedPrecisionValue.from_value(6, 1)
    initial = weighted_interval_score(definition, quantiles, actual)
    assert initial.signed_median_miss == 1
    assert initial.median_contribution == Fraction(20, 100)
    assert initial.interval_50_contribution == Fraction(40, 100)
    assert initial.interval_90_contribution == Fraction(16, 100)
    final = weighted_interval_score(
        definition,
        FiveQuantiles.from_values({5: 2, 25: 4, 50: 6, 75: 8, 95: 10}, 1),
        actual,
    )
    assert final.wis == Fraction(56, 100)
    assert initial.wis - final.wis == Fraction(20, 100)
    for actual, locations in (
        (6, ("inside", "inside")),
        (8, ("above", "inside")),
        (12, ("above", "above")),
    ):
        score = weighted_interval_score(
            definition, quantiles, FixedPrecisionValue.from_value(actual, 1)
        )
        assert (
            score.interval_50.outcome_location,
            score.interval_90.outcome_location,
        ) == locations

    for count, total, expected in (
        (5, 10, (23.7, 76.3)),
        (50, 100, (40.4, 59.6)),
        (500, 1000, (46.9, 53.1)),
        (15, 20, (53.1, 88.8)),
        (19, 20, (76.4, 99.1)),
    ):
        assert (
            tuple(round(100 * bound, 1) for bound in Proportion(count, total).wilson_95)
            == expected
        )


@pytest.mark.parametrize("width", [500, 1000, 1800])
@pytest.mark.parametrize("font_size", [9, 12])
@pytest.mark.parametrize("dark", [False, True])
def test_compact_trajectory_summary_geometry_and_unchanged_values(
    active, qtbot, qapp, tmp_path, width, font_size, dark
):
    clock, operations = active
    prediction = operations.create_prediction(
        "Will the compact summary remain legible?",
        70,
        forecast_deadline=START + timedelta(hours=2),
    )
    legacy = operations._create_legacy_prediction("Legacy comparison", 60)
    clock.instant += timedelta(hours=2)
    for item in (prediction, legacy):
        operations.resolve_prediction(
            item.prediction_id,
            BinaryOutcome.YES,
            **(
                {"effective_resolution_at": clock.instant} if item is prediction else {}
            ),
            **_context(item),
        )
    before = operations.get_forecast_analytics()
    original_font = qapp.font()
    original_palette = qapp.palette()
    try:
        if dark:
            palette = QPalette(original_palette)
            for role, color in (
                (QPalette.ColorRole.Window, "#202020"),
                (QPalette.ColorRole.Base, "#202020"),
                (QPalette.ColorRole.AlternateBase, "#303030"),
                (QPalette.ColorRole.WindowText, "#ffffff"),
                (QPalette.ColorRole.Text, "#ffffff"),
                (QPalette.ColorRole.ButtonText, "#ffffff"),
                (QPalette.ColorRole.Mid, "#707070"),
            ):
                palette.setColor(role, QColor(color))
            qapp.setPalette(palette)
        qapp.setFont(QFont("Segoe UI", font_size))
        screen = AnalyticsScreen(operations)
        qtbot.addWidget(screen)
        install_visual_system(screen)
        screen.resize(width, 1000)
        screen.show()
        screen.refresh()
        qtbot.wait(50)
        panel = screen.trajectory_summary
        groups = panel.findChildren(CompactMetricGroup)
        assert len(groups) == 3
        assert screen.mean_trajectory_brier.text() == "0.090"
        assert screen.trajectory_scored_count.text() == "1"
        assert (
            screen.trajectory_scored_count.font() == screen.mean_trajectory_brier.font()
        )
        colors = semantic_colors(screen.palette())
        assert screen.trajectory_scored_count.palette().color(
            QPalette.ColorRole.WindowText
        ) == QColor(colors.text)
        assert screen.mean_trajectory_brier.palette().color(
            QPalette.ColorRole.WindowText
        ) == QColor(colors.accent)
        assert screen.trajectory_deadline_count.text() == "1"
        assert screen.trajectory_active_fraction.text() == "100%"
        assert screen.trajectory_neutral_fraction.text() == "0%"
        assert screen.scroll_area.horizontalScrollBar().maximum() == 0
        for group in groups:
            for label in group.findChildren(QLabel):
                origin = label.mapTo(panel, QPoint(0, 0))
                assert panel.rect().contains(origin)
                assert panel.rect().contains(origin + label.rect().bottomRight())
        if width == 1800:
            assert panel.height() < 340
            assert (
                max(g.mapTo(panel, QPoint()).y() for g in groups)
                - min(g.mapTo(panel, QPoint()).y() for g in groups)
                < 3
            )
        else:
            assert (
                groups[0].mapTo(panel, QPoint()).y()
                < groups[1].mapTo(panel, QPoint()).y()
            )
        assert (
            screen.mean_trajectory_brier.textInteractionFlags()
            & Qt.TextInteractionFlag.TextSelectableByMouse
        )
        assert operations.get_forecast_analytics() == before
        assert screen.grab().save(
            str(tmp_path / f"trajectory-summary-{width}-{font_size}.png")
        )
    finally:
        qapp.setFont(original_font)
        qapp.setPalette(original_palette)
