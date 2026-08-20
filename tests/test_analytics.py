from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.analytics import (
    AnalyticsSource,
    ScoringObservation,
    brier_score,
    summarize_analytics,
)
from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.clock import format_utc
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import BinaryOutcome


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)


@pytest.mark.parametrize(
    ("probability", "outcome", "expected"),
    [
        (0, BinaryOutcome.NO, 0.0),
        (0, BinaryOutcome.YES, 1.0),
        (30, BinaryOutcome.NO, 0.09),
        (70, BinaryOutcome.YES, 0.09),
        (100, BinaryOutcome.YES, 0.0),
        (100, BinaryOutcome.NO, 1.0),
    ],
)
def test_binary_brier_score(probability, outcome, expected) -> None:
    assert brier_score(probability, outcome) == pytest.approx(expected)


@pytest.mark.parametrize("probability", [-1, 101, 50.5, True])
def test_brier_score_rejects_invalid_probability(probability) -> None:
    with pytest.raises(ValueError, match="whole number"):
        brier_score(probability, BinaryOutcome.YES)


def test_fixed_calibration_bins_cover_endpoints_and_use_actual_means() -> None:
    probabilities = (0, 9, 10, 37, 89, 90, 100)
    outcomes = (
        BinaryOutcome.NO,
        BinaryOutcome.YES,
        BinaryOutcome.YES,
        BinaryOutcome.NO,
        BinaryOutcome.YES,
        BinaryOutcome.NO,
        BinaryOutcome.YES,
    )
    source = AnalyticsSource(
        observations=tuple(
            _observation(index + 1, probability, outcome)
            for index, (probability, outcome) in enumerate(
                zip(probabilities, outcomes, strict=True)
            )
        ),
        available_tags=(),
    )

    snapshot = summarize_analytics(source)

    assert tuple(item.label for item in snapshot.calibration_bins) == (
        "0-9%",
        "10-19%",
        "20-29%",
        "30-39%",
        "40-49%",
        "50-59%",
        "60-69%",
        "70-79%",
        "80-89%",
        "90-100%",
    )
    first = snapshot.calibration_bins[0]
    assert first.count == 2
    assert first.mean_forecast_percent == pytest.approx(4.5)
    assert first.observed_yes_percent == pytest.approx(50.0)
    assert snapshot.calibration_bins[2].count == 0
    assert snapshot.calibration_bins[2].mean_forecast_percent is None
    assert snapshot.calibration_bins[2].observed_yes_percent is None
    last = snapshot.calibration_bins[-1]
    assert last.count == 2
    assert last.mean_forecast_percent == pytest.approx(95.0)
    assert last.observed_yes_percent == pytest.approx(50.0)


def test_cumulative_brier_trend_uses_resolution_time_and_stable_id_ties() -> None:
    later = _observation(
        3,
        100,
        BinaryOutcome.NO,
        resolved_at=NOW + timedelta(days=1),
    )
    tie_second = _observation(2, 50, BinaryOutcome.YES, resolved_at=NOW)
    tie_first = _observation(1, 100, BinaryOutcome.YES, resolved_at=NOW)

    snapshot = summarize_analytics(
        AnalyticsSource(
            observations=(later, tie_second, tie_first),
            available_tags=(),
        )
    )

    assert [point.resolution_id for point in snapshot.brier_trend] == [1, 2, 3]
    assert [point.individual_brier for point in snapshot.brier_trend] == pytest.approx(
        [0.0, 0.25, 1.0]
    )
    assert [
        point.cumulative_mean_brier for point in snapshot.brier_trend
    ] == pytest.approx([0.0, 0.125, 1.25 / 3])
    assert snapshot.mean_brier == pytest.approx(1.25 / 3)


def test_tag_filter_recomputes_every_view_case_insensitively() -> None:
    source = AnalyticsSource(
        observations=(
            _observation(1, 20, BinaryOutcome.NO, tags=("Work",)),
            _observation(2, 80, BinaryOutcome.YES, tags=("Personal",)),
            _observation(3, 20, BinaryOutcome.YES, tags=("WORK",)),
        ),
        available_tags=("Personal", "Work"),
    )

    snapshot = summarize_analytics(source, tag="work")

    assert snapshot.scored_prediction_count == 2
    assert snapshot.mean_brier == pytest.approx((0.04 + 0.64) / 2)
    assert sum(item.count for item in snapshot.calibration_bins) == 2
    assert len(snapshot.brier_trend) == 2
    assert snapshot.available_tags == ("Personal", "Work")


def test_analytics_rejects_duplicate_prediction_observations() -> None:
    observation = _observation(1, 50, BinaryOutcome.YES)

    with pytest.raises(ValueError, match="resolved prediction.*exactly once"):
        summarize_analytics(
            AnalyticsSource(
                observations=(observation, observation),
                available_tags=(),
            )
        )


def test_repository_scores_captured_revision_once_and_excludes_other_states(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(database, FixedClock(NOW)).create_prediction(
        "Will the scored prediction occur?",
        30,
        tags=("Scored",),
    )
    revised = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=1)),
    ).revise_forecast(
        created.prediction_id,
        70,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=2)),
    ).resolve_prediction(
        revised.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=revised.current_revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    with database.transaction() as connection:
        connection.execute(
            """
            INSERT INTO forecast_revisions (
                prediction_id,
                probability_percent,
                created_at,
                sequence,
                rationale
            )
            VALUES (?, 0, ?, 3, 'Adversarial post-resolution row')
            """,
            (
                created.prediction_id,
                format_utc(NOW + timedelta(hours=3)),
            ),
        )
    PredictionOperations(database, FixedClock(NOW)).create_prediction(
        "Will this unresolved prediction be excluded?",
        100,
        tags=("Unresolved only",),
    )
    invalid_operations = PredictionOperations(database, FixedClock(NOW))
    invalid = invalid_operations.create_prediction(
        "Will this Invalid prediction be excluded?",
        0,
        tags=("Invalid only",),
    )
    invalid_operations.invalidate_prediction(
        invalid.prediction_id,
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )

    snapshot = PredictionOperations(database, FixedClock(NOW)).get_analytics()

    assert snapshot.scored_prediction_count == 1
    scored = snapshot.scored_predictions[0]
    assert scored.observation.prediction_id == created.prediction_id
    assert scored.observation.scoring_revision_id == revised.current_revision_id
    assert scored.observation.probability_percent == 70
    assert scored.brier_score == pytest.approx(0.09)
    assert snapshot.mean_brier == pytest.approx(0.09)
    assert snapshot.available_tags == ("Scored",)
    database.close()


def test_analytics_survive_restart_and_unknown_tag_is_an_honest_empty_subset(
    tmp_path,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    first_operations = PredictionOperations(first_database, FixedClock(NOW))
    created = first_operations.create_prediction(
        "Will analytics survive restart?",
        25,
        tags=("Durability",),
    )
    first_operations.resolve_prediction(
        created.prediction_id,
        BinaryOutcome.NO,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    expected = first_operations.get_analytics(tag="DURABILITY")
    first_database.close()

    second_database = Database.open(path)
    operations = PredictionOperations(second_database, FixedClock(NOW))
    reopened = operations.get_analytics(tag="DURABILITY")
    empty = operations.get_analytics(tag="absent")

    assert reopened == expected
    assert empty.scored_prediction_count == 0
    assert empty.mean_brier is None
    assert empty.available_tags == ("Durability",)
    with pytest.raises(ValidationError) as error_info:
        operations.get_analytics(tag=123)  # type: ignore[arg-type]
    assert error_info.value.field == "tag"
    second_database.close()


def _observation(
    identifier: int,
    probability_percent: int,
    outcome: BinaryOutcome,
    *,
    resolved_at: datetime = NOW,
    tags: tuple[str, ...] = (),
) -> ScoringObservation:
    return ScoringObservation(
        prediction_id=identifier,
        question=f"Prediction {identifier}",
        resolution_id=identifier,
        resolved_at=resolved_at,
        scoring_revision_id=identifier,
        probability_percent=probability_percent,
        outcome=outcome,
        tags=tags,
    )
