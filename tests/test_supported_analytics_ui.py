"""Current-model replacements for the retired final-v1/interval-v1 GUI checks."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from performance_helpers import adaptive_binary, adaptive_numeric, loaded

from reckonsolve.app import create_runtime
from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.domain.predictions import BinaryOutcome
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
            "Will it happen?", p, forecast_deadline=deadline, tags=(t,)
        )
        for p, t in ((70, "Work"), (20, "Personal"))
    ]
    numerics = [
        operations.create_numeric_prediction(
            "How many?",
            u,
            0,
            {5: 1, 25: 2, 50: 3, 75: 4, 95: 5},
            value_constraint=c,
            forecast_deadline=deadline,
            tags=(t,),
        )
        for u, t, c in (
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
    reopened.window.navigate_to("Performance")
    screen = reopened.window._analytics_screen
    report = loaded(screen, qtbot, refresh=False)
    binary, numeric = adaptive_binary(screen), adaptive_numeric(screen)
    assert report.sections[0].data == expected.trajectory_binary
    assert report.sections[1].data == expected.quantile_numeric
    assert binary.count.text() == "2" and binary.score.text() == "0.065"
    assert "2 eligible" in numeric.summary.text()
    assert sum(b.count for b in binary.chart.bins) == 2
    work = next(t.tag_id for t in report.tags if t.display_name == "Work")
    screen.tag_filter.setCurrentIndex(screen.tag_filter.findData(work))
    loaded(screen, qtbot, refresh=False)
    assert binary.score.text() == "0.090"
    assert "1 eligible" in numeric.summary.text()
    numeric.unit_filter.setCurrentIndex(numeric.unit_filter.findData("days"))
    report = loaded(screen, qtbot, refresh=False)
    assert report.sections[1].data.scored_prediction_count == 1
    assert binary.isVisible() and numeric.isVisible()
    reopened.close()


@pytest.mark.parametrize("after_load", [False, True])
def test_current_analytics_errors_clear_stale_results(
    qtbot, tmp_path, monkeypatch, after_load
):
    runtime = create_runtime(database_path=tmp_path / "errors.sqlite3")
    qtbot.addWidget(runtime.window)
    operations = PredictionOperations(runtime.database, Clock())
    screen = AnalyticsScreen(operations)
    qtbot.addWidget(screen)
    if after_load:
        loaded(screen, qtbot)

    def fail(request):
        raise ApplicationError("Injected read failure")

    monkeypatch.setattr(operations.performance, "query_independently", fail)
    screen.refresh()
    qtbot.waitUntil(lambda: not screen.loading)
    assert "Injected read failure" in screen.message.text()
    assert screen.report is None
    assert all(s.results.isHidden() for s in screen.sections.values())
    screen.close_retrieval()
    runtime.close()
