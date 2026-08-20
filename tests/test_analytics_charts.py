from datetime import UTC, datetime, timedelta

import pytest
from PySide6.QtCore import QRectF

from reckonsolve.analytics import BrierTrendPoint, CalibrationBin
from reckonsolve.ui.analytics_charts import (
    BrierTrendChart,
    CalibrationChart,
    calculate_brier_trend_markers,
    calculate_calibration_markers,
)

NOW = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
PLOT = QRectF(10, 20, 200, 100)


def test_calibration_geometry_uses_actual_means_and_omits_empty_bins() -> None:
    bins = (
        CalibrationBin(0, 9, 2, 4.5, 50.0),
        CalibrationBin(10, 19, 0, None, None),
        CalibrationBin(90, 100, 1, 100.0, 0.0),
    )

    markers = calculate_calibration_markers(bins, PLOT)

    assert len(markers) == 2
    assert markers[0].coordinate.x == pytest.approx(19.0)
    assert markers[0].coordinate.y == pytest.approx(70.0)
    assert markers[1].coordinate.x == pytest.approx(210.0)
    assert markers[1].coordinate.y == pytest.approx(120.0)


def test_calibration_geometry_rejects_incomplete_occupied_bin() -> None:
    with pytest.raises(ValueError, match="require both means"):
        calculate_calibration_markers(
            (CalibrationBin(0, 9, 1, None, 0.0),),
            PLOT,
        )


def test_brier_trend_uses_actual_resolution_time_and_fixed_zero_one_scale() -> None:
    points = (
        _trend_point(3, NOW + timedelta(days=3), 0.75),
        _trend_point(1, NOW, 0.0),
        _trend_point(2, NOW + timedelta(days=1), 0.25),
    )

    markers = calculate_brier_trend_markers(points, PLOT)

    assert [marker.point.resolution_id for marker in markers] == [1, 2, 3]
    assert [marker.coordinate.x for marker in markers] == pytest.approx(
        [10.0, 10.0 + 200 / 3, 210.0]
    )
    assert [marker.coordinate.y for marker in markers] == pytest.approx(
        [120.0, 95.0, 45.0]
    )


def test_one_or_equal_time_trend_centers_real_points_without_fake_offsets() -> None:
    first = _trend_point(1, NOW, 0.2)
    second = _trend_point(2, NOW, 0.4)

    markers = calculate_brier_trend_markers((second, first), PLOT)

    assert [marker.point.resolution_id for marker in markers] == [1, 2]
    assert [marker.coordinate.x for marker in markers] == [110.0, 110.0]


def test_analytics_widgets_render_and_expose_nonvisual_summaries(qtbot) -> None:
    calibration = CalibrationChart()
    trend = BrierTrendChart()
    qtbot.addWidget(calibration)
    qtbot.addWidget(trend)
    calibration.resize(640, 300)
    trend.resize(640, 300)
    calibration.set_bins((CalibrationBin(20, 29, 3, 25.0, 33.333),))
    trend.set_points((_trend_point(1, NOW, 0.125),))
    calibration.show()
    trend.show()

    assert not calibration.grab().isNull()
    assert not trend.grab().isNull()
    assert "20-29%: 3 scored" in calibration.accessibleDescription()
    assert "Perfect calibration is the diagonal" in calibration.accessibleDescription()
    assert "after 1 scored, 0.125" in trend.accessibleDescription()


def _trend_point(
    identifier: int,
    resolved_at: datetime,
    cumulative_mean: float,
) -> BrierTrendPoint:
    return BrierTrendPoint(
        resolution_id=identifier,
        prediction_id=identifier,
        resolved_at=resolved_at,
        scored_count=identifier,
        individual_brier=cumulative_mean,
        cumulative_mean_brier=cumulative_mean,
    )
