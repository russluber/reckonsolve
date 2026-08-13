from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, tzinfo
from math import isfinite

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QFont
from pytestqt.qtbot import QtBot

from reckonsolve.ui.probability_history_chart import (
    ProbabilityHistoryChart,
    ProbabilityHistorySample,
    calculate_chart_geometry,
)

START = datetime(2026, 8, 13, 19, 30, tzinfo=UTC)
PLOT = QRectF(10.0, 20.0, 200.0, 100.0)


@dataclass(frozen=True, slots=True)
class Revision:
    revision_id: int
    sequence: int
    probability_percent: int
    created_at: datetime
    rationale: str | None = None


class NoOffsetTimezone(tzinfo):
    """A tzinfo object that does not make its datetime genuinely aware."""

    def utcoffset(self, value: datetime | None) -> None:
        return None

    def dst(self, value: datetime | None) -> None:
        return None

    def tzname(self, value: datetime | None) -> str:
        return "No offset"


def _sample(
    sequence: int,
    probability: int,
    *,
    instant: datetime | None = None,
) -> ProbabilityHistorySample:
    return ProbabilityHistorySample(
        revision_id=sequence,
        sequence=sequence,
        probability_percent=probability,
        created_at=START if instant is None else instant,
    )


def test_one_revision_is_centered_at_its_exact_probability() -> None:
    geometry = calculate_chart_geometry((_sample(1, 37),), PLOT)

    assert len(geometry.markers) == 1
    assert geometry.markers[0].coordinate.x == pytest.approx(PLOT.center().x())
    assert geometry.markers[0].coordinate.y == pytest.approx(83.0)
    assert geometry.step_vertices == (geometry.markers[0].coordinate,)
    assert geometry.earliest_instant == START
    assert geometry.latest_instant == START


@pytest.mark.parametrize(
    "instant",
    [
        START.replace(tzinfo=None),
        START.replace(tzinfo=NoOffsetTimezone()),
    ],
)
def test_revision_timestamps_must_be_genuinely_timezone_aware(
    instant: datetime,
) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        calculate_chart_geometry((_sample(1, 37, instant=instant),), PLOT)


def test_fixed_probability_scale_maps_endpoints_without_clipping_geometry() -> None:
    samples = (
        _sample(1, 0, instant=START),
        _sample(2, 37, instant=START + timedelta(hours=1)),
        _sample(3, 100, instant=START + timedelta(hours=2)),
    )

    geometry = calculate_chart_geometry(samples, PLOT)

    assert [marker.coordinate.y for marker in geometry.markers] == pytest.approx(
        [PLOT.bottom(), 83.0, PLOT.top()]
    )
    assert [marker.coordinate.x for marker in geometry.markers] == pytest.approx(
        [PLOT.left(), PLOT.center().x(), PLOT.right()]
    )


def test_elapsed_time_spacing_is_proportional() -> None:
    samples = (
        _sample(1, 60, instant=START),
        _sample(2, 50, instant=START + timedelta(days=1)),
        _sample(3, 40, instant=START + timedelta(days=4)),
    )

    geometry = calculate_chart_geometry(samples, PLOT)

    assert [marker.coordinate.x for marker in geometry.markers] == pytest.approx(
        [10.0, 60.0, 210.0]
    )


def test_equal_timestamps_share_x_and_step_vertically_in_sequence_order() -> None:
    samples = (_sample(1, 60), _sample(2, 40), _sample(3, 60))

    geometry = calculate_chart_geometry(samples, PLOT)

    assert [marker.sample.sequence for marker in geometry.markers] == [1, 2, 3]
    assert [marker.coordinate.x for marker in geometry.markers] == pytest.approx(
        [PLOT.center().x()] * 3
    )
    assert [(vertex.x, vertex.y) for vertex in geometry.step_vertices] == [
        (110.0, 60.0),
        (110.0, 60.0),
        (110.0, 80.0),
        (110.0, 80.0),
        (110.0, 60.0),
    ]


def test_regressing_clock_keeps_sequence_connection_and_literal_time_position() -> None:
    samples = (
        _sample(1, 60, instant=START),
        _sample(2, 40, instant=START + timedelta(hours=2)),
        _sample(3, 70, instant=START + timedelta(hours=1)),
    )

    geometry = calculate_chart_geometry(samples, PLOT)

    assert [marker.sample.sequence for marker in geometry.markers] == [1, 2, 3]
    assert [marker.coordinate.x for marker in geometry.markers] == pytest.approx(
        [10.0, 210.0, 110.0]
    )
    assert geometry.step_vertices[-1] == geometry.markers[-1].coordinate


def test_step_after_path_holds_old_probability_until_each_revision() -> None:
    samples = (
        _sample(1, 60, instant=START),
        _sample(2, 40, instant=START + timedelta(hours=1)),
        _sample(3, 60, instant=START + timedelta(hours=2)),
    )

    geometry = calculate_chart_geometry(samples, PLOT)

    assert len(geometry.markers) == 3
    assert len(geometry.step_vertices) == 5
    assert [(vertex.x, vertex.y) for vertex in geometry.step_vertices] == [
        (10.0, 60.0),
        (110.0, 60.0),
        (110.0, 80.0),
        (210.0, 80.0),
        (210.0, 60.0),
    ]


def test_many_revisions_remain_finite_bounded_and_undownsampled() -> None:
    samples = tuple(
        _sample(
            sequence,
            sequence % 101,
            instant=START + timedelta(minutes=sequence),
        )
        for sequence in range(1, 1001)
    )

    geometry = calculate_chart_geometry(samples, PLOT)

    assert len(geometry.markers) == 1000
    assert len(geometry.step_vertices) == 1999
    assert all(
        isfinite(marker.coordinate.x)
        and isfinite(marker.coordinate.y)
        and PLOT.left() <= marker.coordinate.x <= PLOT.right()
        and PLOT.top() <= marker.coordinate.y <= PLOT.bottom()
        for marker in geometry.markers
    )


def test_widget_sorts_by_sequence_updates_accessibility_and_repaints(
    qtbot: QtBot,
) -> None:
    chart = ProbabilityHistoryChart()
    qtbot.addWidget(chart)
    chart.resize(700, 280)
    revisions = (
        Revision(2, 2, 40, START + timedelta(days=1), "Changed"),
        Revision(1, 1, 60, START, "Initial"),
        Revision(3, 3, 60, START + timedelta(days=2), "Returned"),
    )

    chart.set_revisions(revisions)
    chart.show()
    qtbot.waitExposed(chart)

    assert chart.revision_count == 3
    assert [sample.sequence for sample in chart.samples] == [1, 2, 3]
    assert [sample.probability_percent for sample in chart.samples] == [60, 40, 60]
    assert chart.accessibleName() == "Probability history chart"
    assert "3 forecast revisions" in chart.accessibleDescription()
    assert "current forecast 60%" in chart.accessibleDescription()
    assert "Timeline" in chart.accessibleDescription()
    assert not chart.grab().isNull()

    chart.resize(360, 220)
    assert not chart.grab().isNull()
    chart.clear()
    assert chart.revision_count == 0
    assert "No forecast revisions" in chart.accessibleDescription()


def test_widget_grows_margins_for_large_fonts_and_tracks_timeline_availability(
    qtbot: QtBot,
) -> None:
    chart = ProbabilityHistoryChart()
    qtbot.addWidget(chart)
    ordinary_minimum = chart.minimumSizeHint()
    large_font = QFont(chart.font())
    large_font.setPointSize(24)

    chart.setFont(large_font)
    enlarged_minimum = chart.minimumSizeHint()
    chart.resize(enlarged_minimum)
    chart.set_revisions(
        (
            Revision(1, 1, 0, START),
            Revision(2, 2, 100, START + timedelta(days=1)),
        )
    )
    chart.set_timeline_available(False)
    chart.show()
    qtbot.waitExposed(chart)

    assert enlarged_minimum.width() > ordinary_minimum.width()
    assert enlarged_minimum.height() > ordinary_minimum.height()
    assert chart._plot_rect().height() >= (
        chart.fontMetrics().horizontalAdvance("Probability") + 11.0
    )
    assert "currently unavailable" in chart.accessibleDescription()
    assert not chart.grab().isNull()

    chart.set_timeline_available(True)
    assert "listed in the Timeline" in chart.accessibleDescription()
