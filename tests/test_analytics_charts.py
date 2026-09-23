from unittest.mock import Mock

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPalette

from reckonsolve.analytics import (
    CalibrationBin,
)
from reckonsolve.ui.analytics_charts import (
    CalibrationChart,
    _paint_percent_axes,
    calculate_calibration_markers,
)

PLOT = QRectF(10, 20, 200, 100)


@pytest.mark.parametrize("ticks", [(0, 25, 50, 75, 100), (5, 25, 50, 75, 95)])
def test_percent_axes_label_true_tick_positions_without_changing_y_axis(qapp, ticks):
    painter = Mock()
    painter.fontMetrics.return_value.height.return_value = 16
    options = {} if ticks[0] == 0 else {"x_ticks": ticks}
    _paint_percent_axes(painter, QPalette(), PLOT, x_title="X", y_title="Y", **options)
    calls = painter.drawText.call_args_list
    x_labels = [call.args for call in calls[:5]]
    assert [args[2] for args in x_labels] == [f"{tick}%" for tick in ticks]
    assert [args[0].center().x() for args in x_labels] == pytest.approx(
        [PLOT.left() + tick / 100 * PLOT.width() for tick in ticks]
    )
    y_labels = [call.args for call in calls[5:10]]
    assert [args[2] for args in y_labels] == ["0%", "25%", "50%", "75%", "100%"]
    assert [args[0].center().y() for args in y_labels] == pytest.approx(
        [PLOT.bottom() - tick / 100 * PLOT.height() for tick in (0, 25, 50, 75, 100)]
    )


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


def test_calibration_widget_renders_and_exposes_nonvisual_summary(qtbot):
    calibration = CalibrationChart(scatter=True)
    qtbot.addWidget(calibration)
    calibration.resize(640, 300)
    calibration.set_bins((CalibrationBin(20, 29, 3, 25.0, 33.333),))
    calibration.show()
    assert not calibration.grab().isNull()
    assert "20-29%: 3 scored" in calibration.accessibleDescription()
    assert "Perfect calibration is the diagonal" in calibration.accessibleDescription()


@pytest.mark.parametrize("scatter", [False, True])
@pytest.mark.parametrize("occupied_count", [0, 1, 3])
def test_calibration_scatter_has_no_connectors_and_preserves_bin_positions(
    qtbot, monkeypatch, tmp_path, scatter, occupied_count
):
    from reckonsolve.ui import analytics_charts

    lines = []
    diamonds = []

    class RecordingPainter(QPainter):
        def drawLine(self, *args):
            lines.append(1)
            super().drawLine(*args)

        def drawPolygon(self, polygon, *args):
            center = polygon.boundingRect().center()
            diamonds.append((center.x(), center.y()))
            super().drawPolygon(polygon, *args)

    monkeypatch.setattr(analytics_charts, "QPainter", RecordingPainter)
    chart = CalibrationChart(scatter=scatter)
    qtbot.addWidget(chart)
    chart.resize(640, 300)
    occupied = (
        CalibrationBin(0, 9, 4, 5.0, 0.0),
        CalibrationBin(60, 69, 10, 64.0, 40.0),
        CalibrationBin(90, 100, 6, 100.0, 100.0),
    )[:occupied_count]
    bins = (*occupied, CalibrationBin(30, 39, 0, None, None))
    chart.set_bins(bins)
    chart.show()
    qtbot.wait(10)
    lines.clear()
    diamonds.clear()
    assert chart.grab().save(
        str(tmp_path / f"calibration-{scatter}-{occupied_count}.png")
    )
    # The perfect-calibration diagonal remains; only legacy plots join bins.
    assert len(lines) == 1 + (0 if scatter else max(0, occupied_count - 1))
    expected = calculate_calibration_markers(bins, analytics_charts._plot_rect(chart))
    assert diamonds == (
        [(marker.coordinate.x, marker.coordinate.y) for marker in expected]
        if scatter
        else []
    )
    assert chart.bins == bins
    if scatter and occupied_count:
        assert "no interpolation" in chart.accessibleDescription()


@pytest.mark.parametrize("dark", [False, True])
def test_trajectory_diamonds_use_shared_semantic_accent(qtbot, monkeypatch, dark):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QPalette

    from reckonsolve.ui import analytics_charts
    from reckonsolve.ui.visual_system import semantic_colors

    brushes = []
    reference_pens = []

    class RecordingPainter(QPainter):
        def drawLine(self, *args):
            if self.pen().style() == Qt.PenStyle.DashLine:
                reference_pens.append((self.pen().color().name(), self.pen().widthF()))
            super().drawLine(*args)

        def drawPolygon(self, polygon, *args):
            brushes.append(self.brush().color().name())
            super().drawPolygon(polygon, *args)

    monkeypatch.setattr(analytics_charts, "QPainter", RecordingPainter)
    chart = CalibrationChart(scatter=True)
    qtbot.addWidget(chart)
    palette = chart.palette()
    palette.setColor(
        QPalette.ColorRole.Window, QColor("#202020" if dark else "#ffffff")
    )
    # Deliberately differ from the semantic green used by Numeric calibration.
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#008000"))
    palette.setColor(QPalette.ColorRole.Mid, QColor("#151515"))
    chart.setPalette(palette)
    chart.set_bins((CalibrationBin(60, 69, 10, 64.0, 40.0),))
    chart.resize(640, 300)
    chart.show()
    chart.grab()
    assert brushes
    assert set(brushes) == {QColor(semantic_colors(chart.palette()).accent).name()}
    assert reference_pens
    assert set(reference_pens) == {
        (QColor(semantic_colors(chart.palette()).border).name(), 1.0)
    }
