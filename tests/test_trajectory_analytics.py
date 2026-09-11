"""M49 equal-Prediction trajectory Binary analytics and presentation."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from PySide6.QtWidgets import QLabel, QWidget

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.ui.analytics_screen import AnalyticsScreen
from reckonsolve.ui.components import ContentPanel

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
    guidance = screen.findChild(QLabel, "trajectoryAnalyticsGuidance").text()
    assert "does not prove" in guidance
    calibration = screen.findChild(QWidget, "trajectoryCalibrationSection")
    legacy = screen.findChild(ContentPanel, "analyticsBrierSummary")
    assert not calibration.isHidden()
    assert legacy.title_label.text() == "Legacy Binary forecasts — final Brier"
