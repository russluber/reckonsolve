"""M53 strict selection, ties, sampling, cohort boundaries and update directions."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest
from PySide6.QtWidgets import QWidget

from reckonsolve.analytics.quantile_aggregate import (
    Proportion,
    summarize_quantile_analytics,
)
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.analytics import AnalyticsRepository
from reckonsolve.data.database import Database
from reckonsolve.domain.analytics import QuantileAnalyticsSource
from reckonsolve.domain.predictions import PredictionType
from reckonsolve.domain.quantiles import NumericValueConstraint

START = datetime(2026, 9, 12, 12, tzinfo=UTC)


@dataclass
class Clock:
    instant: datetime = START

    def now(self) -> datetime:
        return self.instant


@pytest.fixture
def active(tmp_path):
    database = Database.open(tmp_path / "quantile-analytics.sqlite3")
    clock = Clock()
    ops = PredictionOperations(database, clock, UTC)
    yield database, clock, ops
    database.close()


def context(prediction):
    return {
        "expected_revision_id": prediction.current_revision.revision_id,
        "expected_metadata_version": prediction.metadata_version,
    }


def create(
    ops,
    clock,
    *,
    values=(-10, -5, 0, 5, 10),
    whole=False,
    precision=0,
    unit="units",
    tags=(),
):
    return ops.create_numeric_prediction(
        "What is the eventual value?",
        unit,
        precision,
        dict(zip((5, 25, 50, 75, 95), values, strict=True)),
        value_constraint=NumericValueConstraint.WHOLE_NUMBER
        if whole
        else NumericValueConstraint.CONTINUOUS,
        forecast_deadline=clock.instant + timedelta(hours=4),
        tags=tags,
    )


def resolve(ops, clock, prediction, actual, *, effective=None):
    clock.instant += timedelta(minutes=10)
    return ops.resolve_numeric_prediction(
        prediction.prediction_id,
        actual,
        effective_resolution_at=effective or clock.instant,
        **context(prediction),
    )


@pytest.mark.parametrize("whole", [False, True])
def test_exact_boundaries_five_levels_and_disjoint_balances(active, whole):
    _, clock, ops = active
    for actual in (-11, -10, -5, 0, 5, 10, 11):
        prediction = create(ops, clock, whole=whole)
        resolve(ops, clock, prediction, actual)
    snapshot = ops.get_forecast_analytics().quantile_numeric
    group = snapshot.whole_number if whole else snapshot.continuous
    other = snapshot.continuous if whole else snapshot.whole_number
    assert snapshot.scored_prediction_count == group.sample_size == 7
    assert other.sample_size == 0
    assert [l.nominal_percent for l in group.levels] == [5, 25, 50, 75, 95]
    assert [l.strict.count for l in group.levels] == [1, 2, 3, 4, 5]
    assert [l.inclusive.count for l in group.levels] == [2, 3, 4, 5, 6]
    assert group.interval_50.inside == Proportion(3, 7)
    assert group.interval_90.inside == Proportion(5, 7)
    assert group.median.inside == Proportion(1, 7)
    for balance in (group.interval_50, group.interval_90, group.median):
        assert balance.below.count + balance.inside.count + balance.above.count == 7
    assert snapshot.unrevised_count == 7
    assert snapshot.better.total == snapshot.equal.total == snapshot.worse.total == 0


def test_all_quantiles_tied_whole_number_at_nonzero_precision(active):
    _, clock, ops = active
    p = create(ops, clock, values=(2, 2, 2, 2, 2), whole=True, precision=2)
    resolve(ops, clock, p, "2.00")
    group = ops.get_forecast_analytics().quantile_numeric.whole_number
    assert group.sample_size == 1
    assert all(
        l.strict.fraction == 0 and l.inclusive.fraction == 1 for l in group.levels
    )
    assert group.interval_50.inside.fraction == group.interval_90.inside.fraction == 1
    assert group.median.inside.fraction == 1


def test_signed_decimal_equality_not_rounded_through_float(active):
    _, clock, ops = active
    p = create(
        ops,
        clock,
        values=("-2.000001", "-1.000001", "-0.000001", "0.000001", "2.000001"),
        precision=6,
    )
    resolve(ops, clock, p, "-0.000001")
    group = ops.get_forecast_analytics().quantile_numeric.continuous
    assert group.median.inside.count == 1
    assert group.levels[2].strict.count == 0
    assert group.levels[2].inclusive.count == 1


def test_corrected_effective_cutoff_reselects_once_and_no_score_exclusion(active):
    db, clock, ops = active
    p = create(ops, clock)
    initial_id = p.current_revision.revision_id
    clock.instant += timedelta(hours=1)
    revision_at = clock.instant
    p = ops.revise_quantile_forecast(
        p.prediction_id, {5: 0, 25: 1, 50: 2, 75: 3, 95: 4}, **context(p)
    )
    # At an exact revision instant, that revision is excluded.
    resolve(ops, clock, p, 2, effective=revision_at)
    snapshot = ops.get_forecast_analytics().quantile_numeric
    assert snapshot.scored_predictions[0].final_revision_id == initial_id
    assert snapshot.unrevised_count == 1
    history = ops.get_numeric_resolution_history(p.prediction_id)
    clock.instant += timedelta(minutes=1)
    ops.correct_numeric_resolution(
        p.prediction_id,
        2,
        effective_resolution_at=revision_at + timedelta(microseconds=1),
        resolution_notes=None,
        postmortem=None,
        correction_reason="Use the actual event instant",
        expected_correction_id=history.current_correction_id,
    )
    snapshot = ops.get_forecast_analytics().quantile_numeric
    assert (
        snapshot.scored_predictions[0].final_revision_id
        == p.current_revision.revision_id
    )
    assert snapshot.better == Proportion(1, 1)
    assert snapshot.continuous.median.inside.count == 1
    assert snapshot.scored_predictions[0] == ops.get_prediction_scorecard(
        p.prediction_id
    )
    history = ops.get_numeric_resolution_history(p.prediction_id)
    clock.instant += timedelta(minutes=1)
    ops.correct_numeric_resolution(
        p.prediction_id,
        2,
        effective_resolution_at=START,
        correction_reason="Outcome already fixed",
        resolution_notes=None,
        postmortem=None,
        expected_correction_id=history.current_correction_id,
    )
    snapshot = ops.get_forecast_analytics().quantile_numeric
    assert snapshot.resolved_candidate_count == snapshot.unscored_prediction_count == 1
    assert snapshot.scored_prediction_count == snapshot.continuous.sample_size == 0
    assert all(l.inclusive.fraction is None for l in snapshot.continuous.levels)
    assert len(AnalyticsRepository(db).get_forecast_sources()[1].records) == 1


def test_signs_exclude_unrevised_and_never_average_even_identical_units(active):
    _, clock, ops = active
    # Same literal unit, unrelated scales, positive / zero / negative exact deltas.
    for initial, final, actual in (
        ((0, 0, 0, 0, 0), (1, 1, 1, 1, 1), 1),
        ((-1, -1, -1, -1, -1), (1, 1, 1, 1, 1), 0),
        ((0, 0, 0, 0, 0), (1000000,) * 5, 0),
    ):
        p = create(ops, clock, values=initial)
        clock.instant += timedelta(minutes=1)
        p = ops.revise_quantile_forecast(
            p.prediction_id,
            dict(zip((5, 25, 50, 75, 95), final, strict=True)),
            **context(p),
        )
        resolve(ops, clock, p, actual)
    resolve(ops, clock, create(ops, clock), 0)
    snapshot = ops.get_forecast_analytics(
        prediction_type=PredictionType.NUMERIC, unit="units"
    ).quantile_numeric
    assert snapshot.better == snapshot.equal == snapshot.worse == Proportion(1, 3)
    assert snapshot.unrevised_count == 1
    assert snapshot.scored_prediction_count == 4
    assert not any("mean" in field for field in snapshot.__dataclass_fields__)


def test_filters_invalid_open_and_restart_are_isolated(active):
    db, clock, ops = active
    for whole, unit, tag in ((False, "days", "Continuous"), (True, "Days", "Whole")):
        resolve(
            ops,
            clock,
            create(ops, clock, whole=whole, unit=unit, tags=(tag, "Shared")),
            0,
        )
    invalid = create(ops, clock, tags=("Invalid only",))
    ops.invalidate_numeric_prediction(
        invalid.prediction_id, reason="Malformed", **context(invalid)
    )

    create(ops, clock, tags=("Open only",))
    snapshot = ops.get_forecast_analytics()
    assert snapshot.quantile_numeric.scored_prediction_count == 2
    assert set(snapshot.available_tags) == {"Continuous", "Whole", "Shared"}
    assert set(snapshot.available_units) == {"Days", "days"}
    assert (
        ops.get_forecast_analytics(
            tag="wHoLe"
        ).quantile_numeric.whole_number.sample_size
        == 1
    )
    filtered = ops.get_forecast_analytics(
        prediction_type=PredictionType.NUMERIC, unit="days"
    )
    assert filtered.quantile_numeric.continuous.sample_size == 1
    assert filtered.quantile_numeric.whole_number.sample_size == 0
    assert (
        ops.get_forecast_analytics(
            prediction_type=PredictionType.BINARY
        ).quantile_numeric.scored_prediction_count
        == 0
    )
    assert (
        ops.get_forecast_analytics(
            tag="missing"
        ).quantile_numeric.scored_prediction_count
        == 0
    )
    with db.transaction() as connection:
        before = tuple(connection.iterdump())
    repeated = ops.get_forecast_analytics()
    with db.transaction() as connection:
        assert tuple(connection.iterdump()) == before
    assert repeated == snapshot
    restarted = Database.open(db.path)
    try:
        assert (
            PredictionOperations(restarted, clock, UTC).get_forecast_analytics()
            == snapshot
        )
    finally:
        restarted.close()


def test_duplicate_canonical_observation_is_rejected(active):
    db, clock, ops = active
    resolve(ops, clock, create(ops, clock), 0)
    source = AnalyticsRepository(db).get_forecast_sources()[1]
    with pytest.raises(ValueError, match="at most once"):
        summarize_quantile_analytics(QuantileAnalyticsSource(source.records * 2))
    # No implicit confidence buckets or CDF interpolation: exactly five records.
    snapshot = summarize_quantile_analytics(source)
    assert len(snapshot.continuous.levels) == 5
    assert snapshot == summarize_quantile_analytics(replace(source))


def test_wilson_small_samples_extremes_and_exact_fractions():
    assert Proportion(0, 0).fraction is None
    assert Proportion(0, 0).wilson_95 is None
    assert Proportion(1, 3).fraction == Fraction(1, 3)
    assert Proportion(0, 1).wilson_95 == pytest.approx((0, 0.7934506856))
    assert Proportion(1, 1).wilson_95 == pytest.approx((0.2065493144, 1))
    assert Proportion(5, 10).wilson_95 == pytest.approx((0.2365930905, 0.7634069095))
    with pytest.raises(ValueError):
        Proportion(2, 1)


def test_actual_correction_and_nonforecast_history_do_not_inflate_sample(active):
    db, clock, ops = active
    p = create(ops, clock, values=(0, 0, 0, 0, 0))
    clock.instant += timedelta(minutes=1)
    p = ops.revise_quantile_forecast(
        p.prediction_id, {5: 10, 25: 10, 50: 10, 75: 10, 95: 10}, **context(p)
    )
    clock.instant += timedelta(minutes=1)
    ops.add_numeric_journal_entry(
        p.prediction_id, "Evidence, not another forecast", **context(p)
    )
    clock.instant += timedelta(minutes=1)
    ops.add_numeric_forecast_review(
        p.prediction_id, note="Still unchanged", **context(p)
    )
    resolve(ops, clock, p, 10)
    before = ops.get_forecast_analytics().quantile_numeric
    assert before.better == Proportion(1, 1)
    assert before.continuous.median.inside.count == 1
    clock.instant += timedelta(minutes=1)
    history = ops.correct_numeric_resolution(
        p.prediction_id,
        0,
        resolution_notes="Corrected source",
        postmortem=None,
        correction_reason="Original source was wrong",
        expected_correction_id=None,
    )
    after = ops.get_forecast_analytics().quantile_numeric
    assert after.worse == Proportion(1, 1)
    assert after.continuous.median.below.count == 1
    assert after.scored_prediction_count == before.scored_prediction_count == 1
    assert after.scored_predictions[0].scoring_facts_corrected
    clock.instant += timedelta(minutes=1)
    ops.correct_numeric_resolution(
        p.prediction_id,
        0,
        resolution_notes="Corrected source, typo fixed",
        postmortem=None,
        expected_correction_id=history.current_correction_id,
    )
    assert ops.get_forecast_analytics().quantile_numeric == after
    assert len(AnalyticsRepository(db).get_forecast_sources()[1].records) == 1


def test_late_resolution_uses_deadline_cutoff_and_snapshot_is_single_transaction(
    active,
):
    db, clock, ops = active
    p = create(ops, clock)
    clock.instant += timedelta(hours=1)
    p = ops.revise_quantile_forecast(
        p.prediction_id, {5: 0, 25: 5, 50: 10, 75: 15, 95: 20}, **context(p)
    )
    clock.instant += timedelta(hours=6)
    resolve(ops, clock, p, 10)
    with db.transaction() as connection:
        trace = []
        connection.set_trace_callback(trace.append)
    trace.clear()
    try:
        snapshot = ops.get_forecast_analytics().quantile_numeric
    finally:
        with db.transaction() as connection:
            connection.set_trace_callback(None)
    # Trace includes the start of the cleanup transaction, after the read's COMMIT.
    commits = [index for index, sql in enumerate(trace) if sql == "COMMIT"]
    assert len(commits) == 1
    read_trace = trace[: commits[0] + 1]
    assert sum(sql.startswith("BEGIN") for sql in read_trace) == 1
    assert any("numeric_quantile_revisions" in sql for sql in read_trace)
    assert (
        snapshot.scored_predictions[0].final_revision_id
        == p.current_revision.revision_id
    )
    assert snapshot.scored_predictions[0] == ops.get_prediction_scorecard(
        p.prediction_id
    )


@pytest.fixture
def dark_desktop(qapp):
    from PySide6.QtGui import QColor, QFont, QPalette

    font, palette = qapp.font(), qapp.palette()
    qapp.setFont(QFont("Segoe UI", 9))
    dark = QPalette(palette)
    for role, color in (
        (QPalette.ColorRole.Window, "#202020"),
        (QPalette.ColorRole.Base, "#202020"),
        (QPalette.ColorRole.AlternateBase, "#303030"),
        (QPalette.ColorRole.Button, "#303030"),
        (QPalette.ColorRole.WindowText, "white"),
        (QPalette.ColorRole.Text, "white"),
        (QPalette.ColorRole.ButtonText, "white"),
        (QPalette.ColorRole.Mid, "#707070"),
    ):
        dark.setColor(role, QColor(color))
    qapp.setPalette(dark)
    yield
    qapp.setPalette(palette)
    qapp.setFont(font)


def test_unscored_only_desktop_is_explicit_and_refresh_failures_retain_snapshot(
    active,
    qtbot,
    dark_desktop,
    monkeypatch,
):
    from reckonsolve.application.errors import ApplicationError
    from reckonsolve.ui.analytics_screen import AnalyticsScreen

    _, clock, ops = active
    prediction = create(ops, clock)
    resolve(ops, clock, prediction, 0, effective=START)
    screen = AnalyticsScreen(ops)
    qtbot.addWidget(screen)
    screen.show()
    screen.refresh()
    assert screen.quantile_content.isVisible()
    assert not screen.empty_label.isVisible()
    assert "1 unscored" in screen.quantile_content.summary.text()
    assert not screen.quantile_content.continuous.pair.isVisible()
    assert screen.findChild(QWidget, "numericAnalyticsSection") is None
    previous = screen._loaded_snapshot

    def fail(**kwargs):
        raise ApplicationError("Read unavailable")

    monkeypatch.setattr(ops, "get_forecast_analytics", fail)
    screen.refresh()
    assert screen.error_label.isVisible()
    assert screen._loaded_snapshot is previous
    assert screen.quantile_content.isVisible()


@pytest.mark.parametrize("width", [1600, 650])
def test_desktop_groups_responsive_tables_filters_and_rendering(
    active, qtbot, dark_desktop, tmp_path, width, monkeypatch
):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QBoxLayout

    from reckonsolve.ui import quantile_analytics
    from reckonsolve.ui.analytics_screen import AnalyticsScreen
    from reckonsolve.ui.visual_system import install_visual_system

    axis_ticks = []
    paint_axes = quantile_analytics._paint_percent_axes

    def record_axes(*args, **kwargs):
        # Never retain QPainter: its lifetime must end with the paint event.
        axis_ticks.append(kwargs["x_ticks"])
        paint_axes(*args, **kwargs)

    monkeypatch.setattr(quantile_analytics, "_paint_percent_axes", record_axes)

    db, clock, ops = active
    for whole in (False, True):
        for actual in (-11, 0, 2, 11):
            p = create(
                ops,
                clock,
                whole=whole,
                unit="items" if whole else "days",
                tags=("Whole" if whole else "Continuous",),
            )
            resolve(ops, clock, p, actual)
    screen = AnalyticsScreen(ops)
    qtbot.addWidget(screen)
    install_visual_system(screen)
    screen.resize(width, 950)
    screen.show()
    screen.refresh()
    qtbot.wait(60)
    view = screen.quantile_content
    assert view.isVisible()
    assert not screen.empty_label.isVisible()
    assert "8 eligible" in view.summary.text()
    for key, panel in (("continuous", view.continuous), ("whole", view.whole_number)):
        screen.scroll_area.ensureWidgetVisible(panel)
        qtbot.wait(30)
        assert panel.chart.group.sample_size == 4
        assert panel.table.rowCount() == 5
        expected = (
            QBoxLayout.Direction.LeftToRight
            if width == 1600
            else QBoxLayout.Direction.TopToBottom
        )
        assert panel.pair._layout.direction() == expected
        if width == 1600:
            assert abs(panel.chart.width() - panel.table.width()) <= 2
        for table in (panel.table, *panel.balances):
            assert (
                table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            assert (
                sum(table.rowHeight(r) for r in range(table.rowCount()))
                <= table.viewport().height()
            )
            last = table.columnCount() - 1
            assert (
                table.columnViewportPosition(last) + table.columnWidth(last)
                <= table.viewport().width() + 2
            )
            assert table.accessibleDescription()
        axis_ticks.clear()
        assert panel.grab().save(str(tmp_path / f"{key}-{width}.png"))
        assert axis_ticks
        assert all(ticks == (5, 25, 50, 75, 95) for ticks in axis_ticks)
        assert "95% Wilson" in panel.chart.accessibleDescription()
    assert "not evidence" not in view.update_guidance.text()
    assert "not evidence" in view.update_guidance.toolTip()
    screen.type_filter.setCurrentIndex(
        screen.type_filter.findData(PredictionType.NUMERIC)
    )
    screen.unit_filter.setCurrentIndex(screen.unit_filter.findData("items"))
    assert screen._loaded_snapshot.quantile_numeric.whole_number.sample_size == 4
    assert screen._loaded_snapshot.quantile_numeric.continuous.sample_size == 0
    assert not view.continuous.pair.isVisible()
    screen.type_filter.setCurrentIndex(
        screen.type_filter.findData(PredictionType.BINARY)
    )
    assert not view.isVisible()
    assert screen.empty_label.isVisible()
    assert db.schema_version == 18
