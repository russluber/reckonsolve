"""Current-model replacements for the retired final-v1/interval-v1 GUI checks."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtWidgets import QLabel

from reckonsolve.app import create_runtime
from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.domain.predictions import BinaryOutcome, PredictionType
from reckonsolve.domain.quantiles import NumericValueConstraint
from reckonsolve.ui.analytics_screen import AnalyticsScreen


@dataclass
class Clock:
    instant: datetime = datetime(2026, 9, 20, 10, tzinfo=UTC)

    def now(self):
        return self.instant


def context(prediction):
    return {
        "expected_revision_id": (
            prediction.current_revision_id
            if hasattr(prediction, "current_revision_id")
            else prediction.current_revision.revision_id
        ),
        "expected_metadata_version": prediction.metadata_version,
    }


def test_both_models_render_filter_and_keep_exact_scores_after_gui_restart(
    qtbot, tmp_path
):
    path = tmp_path / "supported.sqlite3"
    runtime = create_runtime(database_path=path)
    qtbot.addWidget(runtime.window)
    clock = Clock()
    operations = PredictionOperations(runtime.database, clock)
    deadline = clock.instant + timedelta(hours=2)
    binaries = [
        operations.create_prediction(
            "Will it happen?", probability, forecast_deadline=deadline, tags=(tag,)
        )
        for probability, tag in ((70, "Work"), (20, "Personal"))
    ]
    numerics = [
        operations.create_numeric_prediction(
            "How many?",
            unit,
            0,
            {5: 1, 25: 2, 50: 3, 75: 4, 95: 5},
            value_constraint=constraint,
            forecast_deadline=deadline,
            tags=(tag,),
        )
        for unit, tag, constraint in (
            ("days", "Work", NumericValueConstraint.CONTINUOUS),
            ("items", "Personal", NumericValueConstraint.WHOLE_NUMBER),
        )
    ]
    clock.instant = deadline
    for prediction, outcome in zip(
        binaries, (BinaryOutcome.YES, BinaryOutcome.NO), strict=True
    ):
        operations.resolve_prediction(
            prediction.prediction_id,
            outcome,
            use_recorded_time=True,
            **context(prediction),
        )
    for prediction in numerics:
        operations.resolve_numeric_prediction(
            prediction.prediction_id, 3, use_recorded_time=True, **context(prediction)
        )
    expected = operations.get_forecast_analytics()
    runtime.close()

    reopened = create_runtime(database_path=path)
    qtbot.addWidget(reopened.window)
    reopened.window.show()
    reopened.window.navigate_to("Analytics")
    screen = reopened.window.findChild(AnalyticsScreen)
    assert screen is not None
    assert screen._loaded_snapshot == expected
    assert screen.findChild(QLabel, "trajectoryAnalyticsScoredCount").text() == "2"
    assert screen.findChild(QLabel, "analyticsMeanTrajectoryBrier").text() == "0.065"
    assert "2 eligible" in screen.quantile_content.summary.text()
    assert sum(item.count for item in screen.trajectory_calibration_chart.bins) == 2
    screen.tag_filter.setCurrentIndex(screen.tag_filter.findData("Work"))
    assert screen.findChild(QLabel, "analyticsMeanTrajectoryBrier").text() == "0.090"
    assert "1 eligible" in screen.quantile_content.summary.text()
    screen.type_filter.setCurrentIndex(
        screen.type_filter.findData(PredictionType.NUMERIC.value)
    )
    assert screen.unit_filter.isEnabled()
    screen.unit_filter.setCurrentIndex(screen.unit_filter.findData("days"))
    assert screen._loaded_snapshot.quantile_numeric.scored_prediction_count == 1
    assert screen.trajectory_summary.isHidden()
    reopened.close()


@pytest.mark.parametrize("after_load", [False, True])
def test_current_analytics_errors_never_replace_a_loaded_snapshot(
    qtbot, tmp_path, monkeypatch, after_load
):
    runtime = create_runtime(database_path=tmp_path / "errors.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database, Clock())
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    if after_load:
        screen.refresh()
    before = screen._loaded_snapshot

    def fail(**kwargs):
        raise ApplicationError("Injected read failure")

    monkeypatch.setattr(operations, "get_forecast_analytics", fail)
    screen.refresh()
    assert "Injected read failure" in screen.error_label.text()
    assert screen._loaded_snapshot is before
    runtime.close()
