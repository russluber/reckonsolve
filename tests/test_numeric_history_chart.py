"""Focused presentation tests for the native Numeric interval-history chart."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from PySide6.QtGui import QColor, QPalette

from reckonsolve.domain.predictions import FixedPrecisionValue
from reckonsolve.ui.numeric_history_chart import NumericHistoryChart
from reckonsolve.ui.visual_system import semantic_colors


@dataclass(frozen=True, slots=True)
class Revision:
    revision_id: int
    sequence: int
    lower_bound: FixedPrecisionValue
    median_estimate: FixedPrecisionValue
    upper_bound: FixedPrecisionValue
    confidence_percent: int
    created_at: datetime


def _revision(
    sequence: int,
    *,
    created_at: datetime,
    lower: str = "3.0",
    median: str = "7.0",
    upper: str = "21.0",
) -> Revision:
    return Revision(
        revision_id=sequence,
        sequence=sequence,
        lower_bound=FixedPrecisionValue.from_value(lower, 1),
        median_estimate=FixedPrecisionValue.from_value(median, 1),
        upper_bound=FixedPrecisionValue.from_value(upper, 1),
        confidence_percent=80,
        created_at=created_at,
    )


def test_numeric_chart_renders_one_interval_and_describes_it(qtbot) -> None:
    chart = NumericHistoryChart()
    qtbot.addWidget(chart)
    chart.resize(640, 280)
    chart.show()
    chart.set_revisions((_revision(1, created_at=datetime(2026, 8, 21, tzinfo=UTC)),))

    assert chart.samples[0].lower_bound == 3.0
    assert chart.samples[0].median_estimate == 7.0
    assert "Revision 1" in chart.accessibleDescription()
    assert not chart.grab().isNull()


def test_numeric_chart_draws_readable_axes_and_interval_in_dark_mode(qtbot) -> None:
    chart = NumericHistoryChart()
    palette = QPalette()
    for role, value in (
        (QPalette.ColorRole.Window, "#171a18"),
        (QPalette.ColorRole.Base, "#202421"),
        (QPalette.ColorRole.AlternateBase, "#ffffff"),
        (QPalette.ColorRole.WindowText, "#edf3ef"),
        (QPalette.ColorRole.Text, "#edf3ef"),
        (QPalette.ColorRole.Mid, "#505852"),
    ):
        palette.setColor(role, QColor(value))
    chart.setPalette(palette)
    qtbot.addWidget(chart)
    chart.resize(640, 280)
    chart.set_revisions((_revision(1, created_at=datetime(2026, 8, 21, tzinfo=UTC)),))
    chart.show()

    image = chart.grab().toImage()
    plot_rect = chart._plot_rect()
    axis_pixels = 0
    for x in range(max(0, int(plot_rect.left()))):
        for y in range(image.height()):
            if image.pixelColor(x, y).lightnessF() > 0.7:
                axis_pixels += 1

    colors = semantic_colors(palette)
    assert colors.is_dark
    assert axis_pixels > 20
    assert image.pixelColor(
        int(plot_rect.center().x()), int(plot_rect.top())
    ).name() in {
        colors.accent,
        colors.text,
    }


def test_numeric_chart_uses_revision_sequence_when_instants_tie_or_regress(
    qtbot,
) -> None:
    chart = NumericHistoryChart()
    qtbot.addWidget(chart)
    chart.resize(640, 280)
    chart.show()
    instant = datetime(2026, 8, 21, 12, tzinfo=UTC)
    chart.set_revisions(
        (
            _revision(3, created_at=instant - timedelta(hours=1), median="9.0"),
            _revision(1, created_at=instant, median="5.0"),
            _revision(2, created_at=instant, median="7.0"),
        )
    )

    assert [sample.sequence for sample in chart.samples] == [1, 2, 3]
    assert [sample.median_estimate for sample in chart.samples] == [5.0, 7.0, 9.0]
    assert not chart.grab().isNull()
