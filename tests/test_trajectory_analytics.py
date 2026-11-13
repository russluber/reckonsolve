"""M49 equal-Prediction trajectory Binary analytics and presentation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from performance_helpers import adaptive_binary, adaptive_numeric, loaded
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPalette

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.ui.analytics_screen import AnalyticsScreen
from reckonsolve.ui.appearance import appearance_palette
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.presentation_settings import (
    AppearanceMode,
    MemoryPresentationSettings,
    WindowPresentationState,
)
from reckonsolve.ui.visual_system import (
    contrast_ratio,
    install_visual_system,
    semantic_colors,
)

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


def test_equal_prediction_mean_filters_and_type_boundary(active) -> None:
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
    assert set(snapshot.available_tags) == {"Long", "Shared", "Short"}

    filtered = operations.get_forecast_analytics(tag="long")
    assert filtered.trajectory_binary.scored_prediction_count == 1
    assert filtered.trajectory_binary.mean_trajectory_brier == 1
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
):
    clock, operations = active
    p = operations.create_prediction(
        "Will the trajectory render?", 70, forecast_deadline=START + timedelta(hours=2)
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        p.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(p),
    )
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.show()
    loaded(screen, qtbot)
    section = adaptive_binary(screen)
    assert section.count.text() == "1" and section.score.text() == "0.090"
    assert "0 helped · 1 tied · 0 hurt" in section.diagnostics.text()
    assert "hindsight, not causal evidence" in section.diagnostics.text()
    assert "no interpolation" in section.chart.accessibleDescription()
    assert "95% Wilson" in section.chart.accessibleDescription()
    assert section.diagnostics_section.disclosure_button.isChecked() is False
    assert not section.comparison.isHidden()


def test_analytics_guide_trajectory_worked_example(active, qtbot):
    clock, operations = active
    p = operations.create_prediction(
        "Guide example", 20, forecast_deadline=START + timedelta(hours=10)
    )
    clock.instant += timedelta(hours=2)
    p = operations.revise_forecast(p.prediction_id, 80, **_context(p))
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        p.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(p),
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
    loaded(screen, qtbot)
    text = adaptive_binary(screen).diagnostics.text()
    assert "forecast weight: 40.0% · neutral weight: 60.0%" in text
    assert "Mean hold-initial trajectory: 0.406" in text
    assert "Mean Updating Gain: +0.120" in text


def test_trajectory_window_shares_without_eligible_scores_are_unavailable(
    active, qtbot
):
    _, operations = active
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    loaded(screen, qtbot)
    section = adaptive_binary(screen)
    assert section.score.text() == "Not available" and section.count.text() == "0"
    assert "forecast weight:" not in section.diagnostics.text()
    assert "Not available" in section.diagnostics.text()
    assert section.comparison.isHidden()


def test_analytics_card_titles_and_on_demand_help(active, qtbot):
    _, operations = active
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    loaded(screen, qtbot)
    assert [s.title_label.text() for s in screen.sections.values()] == [
        "Adaptive Binary",
        "Adaptive Numeric",
        "One-Shot Binary",
        "One-Shot Numeric",
    ]
    numeric = adaptive_numeric(screen)
    assert numeric.summary.text() == "0 eligible · 0 resolved · 0 unscored"
    assert not numeric.supporting.disclosure_button.isChecked()
    assert not numeric.update_section.disclosure_button.isChecked()
    assert "raw WIS/Delta is never pooled" in numeric.caveat.text()
    assert "No eligible results" in screen.message.text()


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
    p = operations.create_prediction(
        "Will the summary remain legible?",
        70,
        forecast_deadline=START + timedelta(hours=2),
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        p.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(p),
    )
    before = operations.get_forecast_analytics()
    original_font, original_palette = qapp.font(), qapp.palette()
    try:
        qapp.setPalette(appearance_palette(dark))
        qapp.setFont(QFont("Segoe UI", font_size))
        screen = AnalyticsScreen(operations)
        qtbot.addWidget(screen)
        install_visual_system(screen)
        screen.resize(width, 1000)
        screen.show()
        loaded(screen, qtbot)
        section = adaptive_binary(screen)
        assert section.score.text() == "0.090" and section.count.text() == "1"
        assert (
            "forecast weight: 100.0% · neutral weight: 0.0%"
            in section.diagnostics.text()
        )
        assert screen.scroll_area.horizontalScrollBar().maximum() == 0
        for label in (section.score, section.count, section.title_label):
            origin = label.mapTo(section, QPoint())
            assert section.rect().contains(origin)
            assert section.rect().contains(origin + label.rect().bottomRight())
        other = adaptive_numeric(screen)
        if section.parentWidget().width() >= 960:
            assert abs(section.y() - other.y()) < 3
        else:
            assert section.y() < other.y()
        assert (
            section.score.textInteractionFlags()
            & Qt.TextInteractionFlag.TextSelectableByMouse
        )
        assert operations.get_forecast_analytics() == before
        assert screen.grab().save(
            str(tmp_path / f"performance-{width}-{font_size}.png")
        )
    finally:
        qapp.setFont(original_font)
        qapp.setPalette(original_palette)


@pytest.mark.parametrize("initial", [AppearanceMode.LIGHT, AppearanceMode.DARK])
@pytest.mark.parametrize("width", [900, 1400])
def test_calibration_paint_tracks_repeated_appearance_changes(
    active, qtbot, qapp, initial, width
):
    clock, operations = active
    p = operations.create_prediction(
        "Will calibration stay readable?",
        70,
        forecast_deadline=START + timedelta(hours=2),
    )
    clock.instant += timedelta(hours=2)
    operations.resolve_prediction(
        p.prediction_id,
        BinaryOutcome.YES,
        effective_resolution_at=clock.instant,
        **_context(p),
    )
    before = operations.get_forecast_analytics()
    original_palette = qapp.palette()
    window = MainWindow(
        operations,
        presentation_settings=MemoryPresentationSettings(
            WindowPresentationState(appearance=initial)
        ),
    )
    qtbot.addWidget(window)
    try:
        window.resize(width, 1000)
        window.show()
        window.navigate_to("Performance")
        screen = window._analytics_screen
        report = loaded(screen, qtbot, refresh=False)
        section = adaptive_binary(screen)
        chart, table = section.chart, section.table
        section.comparison.table_toggle.setChecked(True)
        opposite = (
            AppearanceMode.DARK
            if initial is AppearanceMode.LIGHT
            else AppearanceMode.LIGHT
        )
        for mode in (initial, opposite, initial, opposite):
            window.appearance.select(mode)
            qtbot.wait(30)
            expected = QColor(
                semantic_colors(appearance_palette(mode is AppearanceMode.DARK)).raised
            )
            assert chart.grab().toImage().pixelColor(5, 5) == expected
            for widget in (chart, table, table.viewport()):
                palette = widget.palette()
                assert palette.color(QPalette.ColorRole.Base) == expected
                assert (
                    contrast_ratio(palette.color(QPalette.ColorRole.Text), expected)
                    >= 4.5
                )
            cell = table.visualItemRect(table.item(0, 3))
            assert (
                table.viewport()
                .grab()
                .toImage()
                .pixelColor(cell.right() - 4, cell.bottom() - 4)
                == expected
            )
            assert chart.bins == before.trajectory_binary.final_calibration_bins
            assert sum(int(table.item(r, 1).text()) for r in range(10)) == 1
            assert section.score.text() == "0.090"
            assert screen.report is report
        assert operations.get_forecast_analytics() == before
    finally:
        window.close()
        qapp.setPalette(original_palette)
