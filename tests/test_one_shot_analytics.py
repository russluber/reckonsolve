"""M59 exactly-once effective One-Shot calibration, filtering, and presentation."""

from dataclasses import replace
from datetime import UTC, timedelta
from fractions import Fraction

import pytest
from PySide6.QtWidgets import QLabel
from test_one_shot_persistence import NOW, Clock, request

from reckonsolve.analytics.one_shot_aggregate import summarize_one_shot_analytics
from reckonsolve.application.errors import ApplicationError, ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.analytics import OneShotAnalyticsSource, OneShotScoringRecord
from reckonsolve.domain.one_shot import OneShotRecord
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
    NumericValueConstraint,
    QuantileDefinition,
)
from reckonsolve.ui.analytics_screen import AnalyticsScreen


def source_item(identifier, draft=None, *, status=PredictionStatus.RESOLVED):
    draft = request() if draft is None else draft
    record = OneShotRecord(
        identifier,
        draft.contract,
        draft.definition,
        status,
        NOW,
        NOW,
        1,
        draft.values,
        draft.values,
        (),
    )
    return OneShotScoringRecord(draft.question, record, draft.tags)


def numeric_request(
    *, unit="m", whole=False, actual="0", quantiles=None, tags=("outdoors",)
):
    draft = request(numeric=True)
    return replace(
        draft,
        definition=QuantileDefinition(
            unit,
            2,
            NumericValueConstraint.WHOLE_NUMBER
            if whole
            else NumericValueConstraint.CONTINUOUS,
        ),
        values=replace(
            draft.values,
            answer=FixedPrecisionValue.from_value(actual, 2),
            quantiles=FiveQuantiles.from_values(
                quantiles or {5: -2, 25: -1, 50: 0, 75: 1, 95: 2}, 2
            ),
        ),
        tags=tags,
    )


def test_binary_bins_endpoints_exact_mean_and_empty_uncertainty():
    probabilities = (0, 9, 10, 19, 50, 89, 90, 99, 100)
    items = tuple(
        source_item(
            index,
            replace(request(), values=replace(request().values, probability_percent=p)),
        )
        for index, p in enumerate(probabilities, 1)
    )
    summary = summarize_one_shot_analytics(OneShotAnalyticsSource(items)).binary
    assert summary.resolved_count == len(probabilities)
    assert summary.mean_brier == sum(
        (Fraction(100 - p, 100) ** 2 for p in probabilities), Fraction()
    ) / len(probabilities)
    assert [b.count for b in summary.calibration_bins] == [2, 2, 0, 0, 0, 1, 0, 0, 1, 3]
    assert summary.calibration_bins[-1].mean_forecast_percent == pytest.approx(289 / 3)
    assert summary.calibration_bins[2].observed_yes_percent is None
    assert summary.observed_yes[2].wilson_95 is None
    assert summary.observed_yes[0].fraction == 1
    low, high = summary.observed_yes[0].wilson_95
    assert 0 < low < high <= 1


def test_numeric_calibration_preserves_ties_precision_constraints_and_units():
    # Equal scaled integers well above the range of exact binary floats stay equal.
    huge = "9007199254740993"
    items = (
        source_item(1, numeric_request(actual="-1")),
        source_item(2, numeric_request(unit="cm", actual="3")),
        source_item(
            3,
            numeric_request(
                unit="M",
                whole=True,
                actual=huge,
                quantiles={q: huge for q in (5, 25, 50, 75, 95)},
            ),
        ),
    )
    snapshot = summarize_one_shot_analytics(OneShotAnalyticsSource(items))
    continuous, whole = snapshot.numeric.continuous, snapshot.numeric.whole_number
    assert continuous.sample_size == 2 and whole.sample_size == 1
    assert [level.inclusive.count for level in continuous.levels] == [0, 1, 1, 1, 1]
    assert continuous.interval_50.inside.fraction == Fraction(1, 2)
    assert continuous.interval_90.above.fraction == Fraction(1, 2)
    assert all(
        level.strict.count == 0 and level.inclusive.count == 1 for level in whole.levels
    )
    assert whole.median.inside.count == 1
    assert whole.interval_50.inside.fraction == whole.interval_90.inside.fraction == 1
    assert snapshot.available_units == ("M", "cm", "m")
    selected = summarize_one_shot_analytics(
        OneShotAnalyticsSource(items), prediction_type=PredictionType.NUMERIC, unit="m"
    )
    assert selected.numeric.resolved_count == 1
    assert selected.numeric.whole_number.sample_size == 0
    assert not hasattr(snapshot.numeric, "mean_wis")


def test_duplicates_rejected_even_when_filtered_and_unanswered_invalid_excluded():
    item = source_item(1)
    with pytest.raises(ValueError, match="at most once"):
        summarize_one_shot_analytics(OneShotAnalyticsSource((item, item)), tag="absent")
    summary = summarize_one_shot_analytics(
        OneShotAnalyticsSource(
            (
                source_item(1, request(answered=False), status=PredictionStatus.OPEN),
                source_item(2, status=PredictionStatus.INVALID),
                source_item(3, request(answered=False)),
            )
        )
    )
    assert summary.binary.resolved_count == 0
    assert summary.binary.mean_brier is None
    assert not summary.available_tags
    assert all(b.count == 0 for b in summary.binary.calibration_bins)
    assert summary.numeric.continuous.levels[0].inclusive.wilson_95 is None


@pytest.fixture
def archive(tmp_path):
    database = Database.open(tmp_path / "m59.sqlite3")
    clock = Clock()
    operations = PredictionOperations(database, clock, UTC)
    yield database, clock, operations
    database.close()


def test_effective_corrections_count_once_times_are_documentary_and_reads_do_not_write(
    archive,
):
    database, clock, operations = archive
    first = operations.one_shots.create(request())
    numeric = operations.one_shots.create(numeric_request())
    pending = operations.one_shots.create(request(answered=False))
    invalid = operations.one_shots.create(request(answered=False))
    operations.one_shots.invalidate(invalid, reason="Unclear target")
    before = operations.get_one_shot_analytics()
    assert before.binary.resolved_count == before.numeric.resolved_count == 1
    clock.instant += timedelta(minutes=1)
    changed = operations.one_shots.correct(
        first,
        replace(
            first.record.effective, probability_percent=20, answer=BinaryOutcome.NO
        ),
    )
    changed_numeric = operations.one_shots.correct(
        numeric,
        replace(
            numeric.record.effective,
            answer=FixedPrecisionValue(300, 2),
            quantiles=FiveQuantiles.from_values(
                {5: -3, 25: -2, 50: -1, 75: 0, 95: 1}, 2
            ),
        ),
    )
    after = operations.get_one_shot_analytics()
    assert after.binary.resolved_count == after.numeric.resolved_count == 1
    assert after.binary.observations[0].brier == operations.one_shots.score(changed)
    assert after.numeric.observations[0].wis == operations.one_shots.score(
        changed_numeric
    )
    assert after.binary.calibration_bins[2].observed_yes_percent == 0
    assert after.binary.calibration_bins[8].count == 0
    assert after.numeric.continuous.interval_90.above.count == 1
    clock.instant += timedelta(minutes=1)
    operations.one_shots.correct(
        changed,
        replace(changed.record.effective, forecast_reported=None, reveal_reported=None),
    )
    assert operations.get_one_shot_analytics() == after
    assert first.record.original.probability_percent == 80
    assert (
        operations.one_shots.get(first.prediction_id).record.original
        == first.record.original
    )
    # Later answers use the same collection and no app-entry timing exclusion.
    operations.one_shots.add_answer(
        pending, replace(pending.record.effective, answer=BinaryOutcome.YES)
    )
    assert operations.get_one_shot_analytics().binary.resolved_count == 2
    connection = database._require_connection()
    changes = connection.total_changes
    trace = []
    connection.set_trace_callback(trace.append)
    try:
        operations.get_one_shot_analytics()
    finally:
        connection.set_trace_callback(None)
    assert connection.total_changes == changes
    assert sum(sql == "BEGIN IMMEDIATE" for sql in trace) == 1
    assert sum(sql == "COMMIT" for sql in trace) == 1


def test_independent_connection_correction_refreshes_without_changing_old_snapshot(
    archive,
):
    database, clock, operations = archive
    first = operations.one_shots.create(numeric_request())
    old = operations.get_one_shot_analytics()
    other_database = Database.open(database.path)
    try:
        other = PredictionOperations(other_database, clock, UTC)
        current = other.one_shots.get(first.prediction_id)
        other.one_shots.correct(
            current,
            replace(current.record.effective, answer=FixedPrecisionValue(-400, 2)),
        )
        refreshed = operations.get_one_shot_analytics()
        assert refreshed == other.get_one_shot_analytics()
        assert refreshed.numeric.resolved_count == old.numeric.resolved_count == 1
        assert old.numeric.continuous.median.inside.count == 1
        assert refreshed.numeric.continuous.interval_90.below.count == 1
    finally:
        other_database.close()


def test_filters_cohort_separation_and_restart(archive):
    database, clock, operations = archive
    deadline = clock.instant + timedelta(hours=1)
    binary = operations.create_prediction(
        "Future?", 70, forecast_deadline=deadline, tags=("deadline",)
    )
    numeric = operations.create_numeric_prediction(
        "Future height?",
        "m",
        2,
        {5: -2, 25: -1, 50: 0, 75: 1, 95: 2},
        value_constraint=NumericValueConstraint.CONTINUOUS,
        forecast_deadline=deadline,
    )
    clock.instant = deadline
    operations.resolve_prediction(
        binary.prediction_id,
        BinaryOutcome.YES,
        use_recorded_time=True,
        expected_revision_id=binary.current_revision_id,
        expected_metadata_version=binary.metadata_version,
    )
    operations.resolve_numeric_prediction(
        numeric.prediction_id,
        0,
        use_recorded_time=True,
        expected_revision_id=numeric.current_revision.revision_id,
        expected_metadata_version=numeric.metadata_version,
    )
    expected_deadline = operations.get_forecast_analytics()
    operations.one_shots.create(replace(request(), tags=("Field", "Binary")))
    operations.one_shots.create(numeric_request(tags=("Field",), unit="m"))
    operations.one_shots.create(numeric_request(tags=("Other",), unit="M", whole=True))
    all_shots = operations.get_one_shot_analytics()
    assert (
        all_shots.binary.resolved_count == 1 and all_shots.numeric.resolved_count == 2
    )
    assert operations.get_forecast_analytics() == expected_deadline
    assert "deadline" not in all_shots.available_tags
    filtered = operations.get_one_shot_analytics(tag=" FIELD ")
    assert filtered.binary.resolved_count == filtered.numeric.resolved_count == 1
    selected = operations.get_one_shot_analytics(
        prediction_type=PredictionType.NUMERIC, unit="M"
    )
    assert not selected.binary.observations and selected.numeric.resolved_count == 1
    assert "Binary" not in selected.available_tags
    assert not operations.get_one_shot_analytics(tag="missing").numeric.observations
    path = database.path
    database.close()
    reopened = Database.open(path)
    try:
        again = PredictionOperations(reopened, clock, UTC)
        assert again.get_one_shot_analytics() == all_shots
        assert again.get_forecast_analytics() == expected_deadline
    finally:
        reopened.close()


@pytest.mark.parametrize(
    "filters",
    [
        {"prediction_type": "numeric"},
        {"tag": 1},
        {"unit": 1},
        {"unit": "m"},
        {"prediction_type": PredictionType.BINARY, "unit": "m"},
    ],
)
def test_one_shot_filter_validation(archive, filters):
    with pytest.raises(ValidationError):
        archive[2].get_one_shot_analytics(**filters)


def test_one_shot_ui_mode_filters_corrections_and_text_alternatives(qtbot, archive):
    _, _, operations = archive
    first = operations.one_shots.create(request())
    operations.one_shots.create(numeric_request())
    operations.one_shots.create(
        numeric_request(unit="items", whole=True, tags=("Count",))
    )
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.resize(1000, 800)
    screen.show()
    screen.refresh()
    assert screen.mode_filter.currentData() == "deadline"
    assert screen.one_shot_content.isHidden()
    screen.mode_filter.setCurrentIndex(screen.mode_filter.findData("one_shot"))
    view = screen.one_shot_content
    assert (
        not view.isHidden()
        and screen.trajectory_summary.isHidden()
        and screen.quantile_content.isHidden()
    )
    assert view.mean_brier.text() == "0.040"
    assert view.binary_count.text() == "1"
    assert "2 answered" in view.numeric_summary.text()
    assert (
        view.continuous.chart.group.sample_size
        == view.whole_number.chart.group.sample_size
        == 1
    )
    assert "selectively" in view.caution.text()
    assert view.table.item(8, 4).text() != "Not available"
    assert view.table.item(0, 4).text() == "Not available"
    assert "80-89%" in view.chart.accessibleDescription()
    assert "95% Wilson" in view.continuous.table.accessibleDescription()
    operations.one_shots.correct(
        first, replace(first.record.effective, answer=BinaryOutcome.NO)
    )
    screen.refresh()
    assert view.mean_brier.text() == "0.640" and view.binary_count.text() == "1"
    screen.type_filter.setCurrentIndex(screen.type_filter.findData("numeric"))
    assert view.binary_panel.isHidden() and screen.unit_filter.isEnabled()
    screen.unit_filter.setCurrentIndex(screen.unit_filter.findData("items"))
    assert screen._loaded_snapshot.numeric.resolved_count == 1
    assert view.continuous.chart.group.sample_size == 0
    screen.tag_filter.setCurrentIndex(screen.tag_filter.findData("outdoors"))
    assert "No answered" in view.numeric_summary.text()
    # Use a valid subset again to exercise responsive chart and table layout.
    screen.tag_filter.setCurrentIndex(0)
    for width in (1200, 650):
        screen.resize(width, 800)
        qtbot.wait(20)
        assert view.whole_number.table.width() <= view.whole_number.width()
    screen.mode_filter.setCurrentIndex(screen.mode_filter.findData("deadline"))
    assert view.isHidden()
    assert screen.empty_label.isVisible()


def test_empty_one_shot_view_and_failed_mode_switch_keep_honest_context(
    qtbot, archive, monkeypatch
):
    _, _, operations = archive
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    screen.refresh()

    def fail(**kwargs):
        raise ApplicationError("Read failure")

    original = operations.get_one_shot_analytics
    monkeypatch.setattr(operations, "get_one_shot_analytics", fail)
    screen.mode_filter.setCurrentIndex(1)
    assert screen.mode_filter.currentData() == "deadline"
    assert screen.one_shot_content.isHidden()
    assert "Read failure" in screen.error_label.text()
    monkeypatch.setattr(operations, "get_one_shot_analytics", original)
    screen.mode_filter.setCurrentIndex(1)
    view = screen.one_shot_content
    assert view.binary_count.text() == "0"
    assert view.mean_brier.text() == "Not available"
    assert "No answered" in view.binary_guidance.text()
    assert view.comparison.isHidden()
    assert view.continuous.chart.group.sample_size == 0
    assert (
        "unscored"
        not in " ".join(label.text() for label in view.findChildren(QLabel)).lower()
    )
