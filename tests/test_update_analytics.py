from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QComboBox, QLabel, QWidget

from reckonsolve.analytics import (
    AnalyticsSource,
    NumericAnalyticsSource,
    NumericScoringObservation,
    ScoringObservation,
    summarize_binary_updates,
    summarize_numeric_updates,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionType,
)
from reckonsolve.ui.main_window import MainWindow

NOW = datetime(2026, 8, 27, 9, tzinfo=UTC)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


def test_binary_updates_pair_only_distinct_initial_and_final_revisions() -> None:
    revised = ScoringObservation(
        prediction_id=1,
        question="Will the revision help?",
        resolution_id=1,
        resolved_at=NOW,
        scoring_revision_id=3,
        probability_percent=80,
        outcome=BinaryOutcome.YES,
        tags=("Work",),
        initial_revision_id=1,
        initial_probability_percent=20,
    )
    unrevised = ScoringObservation(
        prediction_id=2,
        question="Will this remain unrevised?",
        resolution_id=2,
        resolved_at=NOW + timedelta(hours=1),
        scoring_revision_id=4,
        probability_percent=60,
        outcome=BinaryOutcome.YES,
        tags=("Work",),
    )

    snapshot = summarize_binary_updates(
        AnalyticsSource(
            observations=(revised, unrevised),
            available_tags=("Work",),
        ),
        tag="work",
    )

    assert snapshot.paired_count == 1
    assert snapshot.unrevised_count == 1
    assert snapshot.mean_initial_brier == pytest.approx(0.64)
    assert snapshot.mean_final_brier == pytest.approx(0.04)
    assert snapshot.mean_score_improvement == pytest.approx(0.60)
    assert snapshot.pairs[0].initial_revision_id == 1
    assert snapshot.pairs[0].final_revision_id == 3
    assert snapshot.pairs[0].resolved_at == NOW


def test_numeric_updates_combine_only_unitless_feedback_across_units() -> None:
    days = _numeric_observation(
        1,
        unit="days",
        initial=("0", "5", "10", 80),
        final=("4", "5", "6", 60),
        actual="6",
        tags=("Plans",),
    )
    dollars = _numeric_observation(
        2,
        unit="USD",
        initial=("100", "150", "200", 80),
        final=("140", "160", "180", 70),
        actual="220",
        tags=("Plans",),
    )
    unrevised = _numeric_observation(
        3,
        unit="days",
        initial=("1", "2", "3", 80),
        final=("1", "2", "3", 80),
        actual="2",
        revised=False,
        tags=("Plans",),
    )
    source = NumericAnalyticsSource(
        observations=(days, dollars, unrevised),
        available_tags=("Plans",),
        available_units=("days", "USD"),
    )

    all_units = summarize_numeric_updates(source, tag="plans")
    days_only = summarize_numeric_updates(source, tag="PLANS", unit="days")

    assert all_units.paired_count == 2
    assert all_units.unrevised_count == 1
    assert all_units.initial_contained_count == 1
    assert all_units.final_contained_count == 1
    assert all_units.mean_initial_confidence_percent == Decimal(80)
    assert all_units.mean_final_confidence_percent == Decimal(65)
    assert all_units.unit_summary is None
    assert days_only.paired_count == 1
    assert days_only.unrevised_count == 1
    assert days_only.unit_summary is not None
    assert days_only.unit_summary.unit == "days"
    assert days_only.unit_summary.mean_initial_interval_width == Decimal(10)
    assert days_only.unit_summary.mean_final_interval_width == Decimal(2)
    assert days_only.unit_summary.mean_narrowing == Decimal(8)
    assert days_only.unit_summary.mean_initial_interval_score == Decimal(10)
    assert days_only.unit_summary.mean_final_interval_score == Decimal(2)
    assert days_only.unit_summary.mean_interval_score_improvement == Decimal(8)


def test_repository_uses_revision_one_captured_final_and_corrected_outcome(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(database, FixedClock(NOW), UTC).create_prediction(
        "Will the final forecast improve?",
        20,
        tags=("Learning",),
    )
    middle = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=1)),
        UTC,
    ).revise_forecast(
        created.prediction_id,
        50,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    final = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=2)),
        UTC,
    ).revise_forecast(
        created.prediction_id,
        80,
        expected_revision_id=middle.current_revision_id,
        expected_metadata_version=middle.metadata_version,
    )
    resolved_at = NOW + timedelta(hours=1)
    PredictionOperations(database, FixedClock(resolved_at), UTC).resolve_prediction(
        final.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=final.current_revision_id,
        expected_metadata_version=final.metadata_version,
    )
    corrections = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=3)),
        UTC,
    )
    corrections.correct_binary_resolution(
        final.prediction_id,
        BinaryOutcome.NO,
        resolution_notes=None,
        postmortem=None,
        correction_reason="The initially published outcome was reversed.",
        expected_correction_id=None,
    )
    unrevised = corrections.create_prediction(
        "Will this stay unrevised?",
        40,
        tags=("Learning",),
    )
    corrections.resolve_prediction(
        unrevised.prediction_id,
        BinaryOutcome.NO,
        expected_revision_id=unrevised.current_revision_id,
        expected_metadata_version=unrevised.metadata_version,
    )
    corrections.create_prediction("Will this stay open?", 90)

    snapshot = corrections.get_forecast_analytics(
        prediction_type=PredictionType.BINARY,
        tag="learning",
    )

    assert snapshot.binary_updates.paired_count == 1
    assert snapshot.binary_updates.unrevised_count == 1
    pair = snapshot.binary_updates.pairs[0]
    assert pair.initial_revision_id == created.current_revision_id
    assert pair.final_revision_id == final.current_revision_id
    assert pair.initial_probability_percent == 20
    assert pair.final_probability_percent == 80
    assert pair.initial_brier == pytest.approx(0.04)
    assert pair.final_brier == pytest.approx(0.64)
    assert pair.score_improvement == pytest.approx(-0.60)
    assert pair.resolved_at == resolved_at
    database.close()


def test_numeric_update_feedback_renders_with_existing_filters(qtbot, tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(
        database,
        FixedClock(NOW),
        UTC,
    ).create_numeric_prediction(
        "How many days will this take?",
        "days",
        0,
        0,
        5,
        10,
        80,
        tags=("Work",),
    )
    revised = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=1)),
        UTC,
    ).revise_numeric_forecast(
        created.prediction_id,
        4,
        5,
        6,
        60,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=2)),
        UTC,
    ).resolve_numeric_prediction(
        revised.prediction_id,
        6,
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    operations = PredictionOperations(database, FixedClock(NOW), UTC)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Analytics")

    type_filter = _child(window, QComboBox, "analyticsTypeFilter")
    type_filter.setCurrentIndex(type_filter.findData(PredictionType.NUMERIC.value))
    unit_filter = _child(window, QComboBox, "analyticsUnitFilter")
    unit_filter.setCurrentIndex(unit_filter.findData("days"))

    assert _child(window, QLabel, "numericUpdatePairedCount").text() == (
        "Revised-and-resolved pairs: 1"
    )
    assert _child(window, QLabel, "numericUpdateUnrevisedCount").text().endswith("0")
    assert (
        _child(window, QLabel, "numericUpdateInitialConfidence").text().endswith("80%")
    )
    assert _child(window, QLabel, "numericUpdateFinalConfidence").text().endswith("60%")
    assert (
        _child(window, QLabel, "numericUpdateInitialContainment")
        .text()
        .endswith("1 of 1 (100%)")
    )
    assert (
        _child(window, QLabel, "numericUpdateFinalContainment")
        .text()
        .endswith("1 of 1 (100%)")
    )
    assert (
        "10 to 2 days"
        in _child(
            window,
            QLabel,
            "numericUpdateWidth",
        ).text()
    )
    assert (
        "Positive is better"
        in _child(
            window,
            QLabel,
            "numericUpdateIntervalScore",
        ).text()
    )
    assert (
        "sparse paired samples"
        in _child(
            window,
            QLabel,
            "numericUpdateGuidance",
        )
        .text()
        .lower()
    )
    window.close()
    database.close()


def test_numeric_update_metrics_recompute_from_corrected_actual_value(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(
        database,
        FixedClock(NOW),
        UTC,
    ).create_numeric_prediction(
        "How many units will be observed?",
        "units",
        0,
        0,
        5,
        10,
        80,
    )
    revised = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(hours=1)),
        UTC,
    ).revise_numeric_forecast(
        created.prediction_id,
        4,
        5,
        6,
        60,
        expected_revision_id=created.current_revision.revision_id,
        expected_metadata_version=created.metadata_version,
    )
    resolved_at = NOW + timedelta(hours=2)
    PredictionOperations(
        database,
        FixedClock(resolved_at),
        UTC,
    ).resolve_numeric_prediction(
        revised.prediction_id,
        6,
        expected_revision_id=revised.current_revision.revision_id,
        expected_metadata_version=revised.metadata_version,
    )
    operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        UTC,
    )
    operations.correct_numeric_resolution(
        revised.prediction_id,
        12,
        resolution_notes=None,
        postmortem=None,
        correction_reason="The final measurement replaced the provisional value.",
        expected_correction_id=None,
    )

    snapshot = operations.get_forecast_analytics(
        prediction_type=PredictionType.NUMERIC,
        unit="units",
    )

    assert snapshot.numeric_updates.paired_count == 1
    pair = snapshot.numeric_updates.pairs[0]
    assert pair.resolved_at == resolved_at
    assert pair.initial_contained is False
    assert pair.final_contained is False
    assert pair.initial_interval_score == Decimal(30)
    assert pair.final_interval_score == Decimal(32)
    assert snapshot.numeric_updates.unit_summary is not None
    assert (
        snapshot.numeric_updates.unit_summary.mean_interval_score_improvement
        == Decimal(-2)
    )
    assert snapshot.numeric.scored_prediction_count == 1
    database.close()


def _numeric_observation(
    identifier: int,
    *,
    unit: str,
    initial: tuple[str, str, str, int],
    final: tuple[str, str, str, int],
    actual: str,
    revised: bool = True,
    tags: tuple[str, ...] = (),
) -> NumericScoringObservation:
    initial_id = identifier * 10
    final_id = initial_id + 2 if revised else initial_id
    return NumericScoringObservation(
        prediction_id=identifier,
        question=f"Numeric {identifier}",
        resolution_id=identifier,
        resolved_at=NOW + timedelta(minutes=identifier),
        scoring_revision_id=final_id,
        unit=unit,
        lower_bound=FixedPrecisionValue.from_value(final[0], 0),
        median_estimate=FixedPrecisionValue.from_value(final[1], 0),
        upper_bound=FixedPrecisionValue.from_value(final[2], 0),
        confidence_percent=final[3],
        actual_value=FixedPrecisionValue.from_value(actual, 0),
        tags=tags,
        initial_revision_id=initial_id,
        initial_lower_bound=FixedPrecisionValue.from_value(initial[0], 0),
        initial_median_estimate=FixedPrecisionValue.from_value(initial[1], 0),
        initial_upper_bound=FixedPrecisionValue.from_value(initial[2], 0),
        initial_confidence_percent=initial[3],
    )


def _child(parent: QWidget, widget_type, name: str):
    child = parent.findChild(widget_type, name)
    assert child is not None, name
    return child
