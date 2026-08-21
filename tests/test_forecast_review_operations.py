from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from reckonsolve.application.errors import (
    ConcurrentForecastReviewError,
    ForecastReviewNotAllowedError,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    ForecastReviewTimelineEvent,
    NumericForecastReviewTimelineEvent,
    PredictionStatus,
)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


NOW = datetime(2026, 8, 20, 18, 0, tzinfo=UTC)


def test_binary_review_retains_forecast_and_appears_in_timeline(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    prediction = operations.create_prediction("Will the review be useful?", 60)

    review = operations.add_forecast_review(
        prediction.prediction_id,
        note="I checked the evidence again.",
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )

    assert isinstance(review, ForecastReviewTimelineEvent)
    assert review.forecast_probability_percent == 60
    assert review.note == "I checked the evidence again."
    assert len(operations.list_forecast_revisions(prediction.prediction_id)) == 1
    assert operations.list_timeline(prediction.prediction_id)[-1] == review
    assert not operations.get_prediction(prediction.prediction_id).deletion_allowed
    database.close()


def test_numeric_review_retains_exact_interval_and_survives_restart(tmp_path) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    prediction = operations.create_numeric_prediction(
        "How many days?", "days", 1, "2.0", "4.0", "8.0", 80
    )

    review = operations.add_numeric_forecast_review(
        prediction.prediction_id,
        expected_revision_id=prediction.current_revision.revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    assert isinstance(review, NumericForecastReviewTimelineEvent)
    assert str(review.lower_bound) == "2.0"
    assert str(review.median_estimate) == "4.0"
    assert review.note is None
    assert (
        len(operations.list_numeric_forecast_revisions(prediction.prediction_id)) == 1
    )
    database.close()

    reopened = Database.open(path)
    timeline = PredictionOperations(
        reopened, FixedClock(NOW), UTC
    ).list_numeric_timeline(prediction.prediction_id)
    assert timeline[-1] == review
    reopened.close()


def test_binary_review_resets_attention(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created_at = NOW - timedelta(days=20)
    created_ops = PredictionOperations(database, FixedClock(created_at), UTC)
    prediction = created_ops.create_prediction("Still current?", 55)
    now_ops = PredictionOperations(database, FixedClock(NOW), UTC)
    assert now_ops.get_dashboard().needs_attention_predictions

    now_ops.add_forecast_review(
        prediction.prediction_id,
        expected_revision_id=prediction.current_revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    dashboard = now_ops.get_dashboard()
    assert not dashboard.needs_attention_predictions
    row = dashboard.open_predictions[0]
    assert row.latest_review_at == NOW
    assert row.attention_reference_at == NOW
    database.close()


def test_numeric_review_resets_type_aware_attention_reference(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    prediction = PredictionOperations(
        database,
        FixedClock(NOW - timedelta(days=20)),
        UTC,
    ).create_numeric_prediction("How many days?", "days", 0, 2, 4, 8, 80)
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    assert operations.get_dashboard().needs_attention_predictions

    operations.add_numeric_forecast_review(
        prediction.prediction_id,
        expected_revision_id=prediction.current_revision.revision_id,
        expected_metadata_version=prediction.metadata_version,
    )
    dashboard = operations.get_dashboard()
    assert not dashboard.needs_attention_predictions
    assert dashboard.open_predictions[0].attention_reference_at == NOW
    database.close()


@pytest.mark.parametrize("numeric", [False, True])
def test_review_is_rejected_after_deadline_for_both_types(tmp_path, numeric) -> None:
    database = Database.open(tmp_path / f"{numeric}.sqlite3")
    create_ops = PredictionOperations(database, FixedClock(NOW), UTC)
    if numeric:
        prediction = create_ops.create_numeric_prediction(
            "How many?",
            "days",
            0,
            1,
            2,
            3,
            80,
            forecast_deadline=date(2026, 8, 20),
        )
        revision_id = prediction.current_revision.revision_id
    else:
        prediction = create_ops.create_prediction(
            "Will it happen?", 60, forecast_deadline=date(2026, 8, 20)
        )
        revision_id = prediction.current_revision_id
    locked_ops = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        UTC,
    )

    with pytest.raises(ForecastReviewNotAllowedError) as raised:
        if numeric:
            locked_ops.add_numeric_forecast_review(
                prediction.prediction_id,
                expected_revision_id=revision_id,
                expected_metadata_version=prediction.metadata_version,
            )
        else:
            locked_ops.add_forecast_review(
                prediction.prediction_id,
                expected_revision_id=revision_id,
                expected_metadata_version=prediction.metadata_version,
            )
    assert raised.value.status is PredictionStatus.LOCKED
    database.close()


def test_review_rechecks_revision_across_independent_connections(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(path)
    second_database = Database.open(path)
    first = PredictionOperations(first_database, FixedClock(NOW), UTC)
    second = PredictionOperations(second_database, FixedClock(NOW), UTC)
    prediction = first.create_prediction("Will context stay current?", 40)
    original_add = first._repository.add_forecast_review

    def race_after_application_precheck(*args, **kwargs):
        second.revise_forecast(
            prediction.prediction_id,
            70,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
        return original_add(*args, **kwargs)

    monkeypatch.setattr(
        first._repository,
        "add_forecast_review",
        race_after_application_precheck,
    )

    with pytest.raises(ConcurrentForecastReviewError):
        first.add_forecast_review(
            prediction.prediction_id,
            expected_revision_id=prediction.current_revision_id,
            expected_metadata_version=prediction.metadata_version,
        )
    assert not any(
        isinstance(event, ForecastReviewTimelineEvent)
        for event in first.list_timeline(prediction.prediction_id)
    )
    second_database.close()
    first_database.close()


def test_terminal_predictions_reject_reviews_for_both_types(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    binary = operations.create_prediction("Will it resolve?", 60)
    operations.resolve_prediction(
        binary.prediction_id,
        outcome=BinaryOutcome.YES,
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    numeric = operations.create_numeric_prediction(
        "How many days?", "days", 0, 2, 4, 8, 80
    )
    operations.invalidate_numeric_prediction(
        numeric.prediction_id,
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )

    with pytest.raises(ForecastReviewNotAllowedError):
        operations.add_forecast_review(
            binary.prediction_id,
            expected_revision_id=binary.current_revision_id,
            expected_metadata_version=binary.metadata_version,
        )
    with pytest.raises(ForecastReviewNotAllowedError):
        operations.add_numeric_forecast_review(
            numeric.prediction_id,
            expected_revision_id=numeric.current_revision.revision_id,
            expected_metadata_version=numeric.metadata_version,
        )
    database.close()
