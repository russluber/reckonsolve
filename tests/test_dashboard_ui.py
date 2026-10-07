"""Dashboard attention cards, refresh, and type-aware navigation."""

from __future__ import annotations

from datetime import UTC, date, datetime

from main_window_fakes import (
    FakeNumericPrediction,
    FakeNumericRevision,
    FakePrediction,
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QListWidget,
    QPushButton,
)
from pytestqt.qtbot import QtBot

from reckonsolve.domain.attention import DashboardPrediction, DashboardSnapshot
from reckonsolve.domain.browser import (
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.forecast_contracts import ForecastDeadline, prospective_contract
from reckonsolve.domain.predictions import (
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.quantiles import (
    FiveQuantiles,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel


def test_type_aware_dashboard_and_browser_render_and_open_numeric_detail(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    numeric_revision = FakeNumericRevision(
        revision_id=20,
        prediction_id=2,
        quantiles=FiveQuantiles.from_values(
            {5: "2.0", 25: "3.0", 50: "4.0", 75: "6.0", 95: "8.0"}, 1
        ),
        sequence=1,
        created_at=instant,
    )
    numeric = FakeNumericPrediction(
        prediction_id=2,
        question="How many Numeric days?",
        unit="days",
        decimal_places=1,
        status=PredictionStatus.OPEN,
        created_at=instant,
        updated_at=instant,
        current_revision=numeric_revision,
        tags=("Numbers",),
    )
    binary = PredictionBrowserItem(
        prediction_id=1,
        question="Will Binary remain visible?",
        probability_percent=60,
        status=PredictionStatus.OPEN,
        created_at=instant,
        latest_revision_at=instant,
        forecast_contract=prospective_contract(
            PredictionType.BINARY, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    numeric_item = PredictionBrowserItem(
        prediction_id=numeric.prediction_id,
        question=numeric.question,
        probability_percent=None,
        status=numeric.status,
        created_at=instant,
        latest_revision_at=instant,
        tags=numeric.tags,
        prediction_type=PredictionType.NUMERIC,
        numeric_quantiles=numeric_revision.quantiles,
        numeric_unit=numeric.unit,
        forecast_contract=prospective_contract(
            PredictionType.NUMERIC, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    operations = FakePredictionOperations()
    operations.numeric_latest = numeric
    operations.numeric_revisions = [numeric_revision]
    operations.dashboard_snapshot = DashboardSnapshot(
        stale_threshold_days=14,
        open_predictions=(
            DashboardPrediction(
                prediction_id=numeric.prediction_id,
                question=numeric.question,
                probability_percent=None,
                status=numeric.status,
                latest_revision_at=instant,
                prediction_type=PredictionType.NUMERIC,
                numeric_quantiles=numeric_revision.quantiles,
                numeric_unit=numeric.unit,
                forecast_contract=prospective_contract(
                    PredictionType.NUMERIC,
                    ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                ),
            ),
        ),
        needs_attention_predictions=(),
        ready_to_resolve_predictions=(),
        locked_predictions=(),
    )
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(binary, numeric_item),
        available_tags=("Numbers",),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dashboard_row = _required_child(window, QPushButton, "dashboardOpenPrediction2")
    assert "Five-quantile" in dashboard_row.text()
    assert "90% interval: 2.0 to 8.0 days; median: 4.0 days" in dashboard_row.text()
    numeric_deadline = _required_child(dashboard_row, QLabel, "dashboardRowDeadline")
    assert numeric_deadline.text().startswith("Forecast deadline: ")
    assert " at " in numeric_deadline.text()
    qtbot.mouseClick(dashboard_row, Qt.MouseButton.LeftButton)
    assert window.current_screen_name == "Prediction Detail"
    numeric_detail_deadline = _required_child(
        window, QLabel, "numericForecastDeadlineValue"
    )
    assert " at " in numeric_detail_deadline.text()
    assert "(permanent)" not in numeric_detail_deadline.text()
    assert "Exact, fixed deadline:" in numeric_detail_deadline.toolTip()
    assert numeric_detail_deadline.wordWrap()
    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        numeric.question
    )

    window.navigate_to("Predictions")
    type_filter = _required_child(window, QComboBox, "predictionTypeFilter")
    type_filter.setCurrentIndex(type_filter.findData(PredictionType.NUMERIC.value))
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.count() == 1
    assert (
        _required_child(
            window,
            QLabel,
            f"predictionResultType{numeric.prediction_id}",
        ).text()
        == "NUMERIC"
    )
    assert (
        _required_child(
            window,
            QLabel,
            f"predictionResultForecast{numeric.prediction_id}",
        ).text()
        == "90% interval: 2.0 to 8.0 days\nMedian: 4.0 days\n50% interval: 3.0 to 6.0 days"
    )
    assert operations.browser_type_calls[-1] is PredictionType.NUMERIC

    results.itemActivated.emit(results.item(0))
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "numericPredictionQuestion").text() == (
        numeric.question
    )

    window.navigate_to("Predictions")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )
    assert type_filter.currentData() is None
    assert _required_child(window, QListWidget, "predictionBrowserResults").count() == 2
    assert operations.browser_type_calls[-1] is None


def test_dashboard_renders_overlapping_buckets_without_losing_classifications(
    qtbot: QtBot,
) -> None:
    open_prediction = DashboardPrediction(
        prediction_id=1,
        question="Fresh open forecast",
        probability_percent=45,
        status=PredictionStatus.OPEN,
        latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
        forecast_contract=prospective_contract(
            PredictionType.BINARY, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    overlap = DashboardPrediction(
        prediction_id=7,
        question="<b>Literal locked forecast</b>",
        probability_percent=70,
        status=PredictionStatus.LOCKED,
        latest_revision_at=datetime(2026, 8, 1, 19, 30, tzinfo=UTC),
        forecast_deadline=date(2026, 8, 10),
        expected_resolution=date(2026, 8, 15),
        needs_attention=True,
        ready_to_resolve=True,
        forecast_contract=prospective_contract(
            PredictionType.BINARY, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    operations = FakePredictionOperations()
    operations.dashboard_snapshot = DashboardSnapshot(
        stale_threshold_days=14,
        open_predictions=(open_prediction,),
        needs_attention_predictions=(overlap,),
        ready_to_resolve_predictions=(overlap,),
        locked_predictions=(overlap,),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name, title in (
        ("dashboardOpenSection", "Open"),
        ("dashboardNeedsAttentionSection", "Needs Attention"),
        ("dashboardReadyToResolveSection", "Ready to Resolve"),
        ("dashboardLockedSection", "Locked"),
    ):
        panel = _required_child(window, ContentPanel, object_name)
        assert panel.title_label.text() == title
        assert panel.count_badge.text() == "1"
    for object_name in (
        "dashboardNeedsAttentionPrediction7",
        "dashboardReadyToResolvePrediction7",
        "dashboardLockedPrediction7",
    ):
        row = _required_child(window, QPushButton, object_name)
        assert "<b>Literal locked forecast</b>" in row.text()
        assert "70%" in row.text()
        assert "needs attention" in row.accessibleDescription()
        assert "ready to resolve" in row.accessibleDescription()
        question = _required_child(row, QLabel, "dashboardRowQuestion")
        summary = _required_child(row, QLabel, "dashboardRowForecast")
        deadline = _required_child(row, QLabel, "dashboardRowDeadline")
        assert question.textFormat() is Qt.TextFormat.PlainText
        assert question.wordWrap()
        assert summary.text() == "BINARY · 70% Yes"
        assert deadline.text().startswith("Forecast deadline: ")
        assert " at " in deadline.text()
        assert "(permanent)" not in row.text()
        badges = {badge.text() for badge in row.findChildren(QLabel) if badge.text()}
        assert "LOCKED" in badges
        assert "NEEDS ATTENTION" in badges
        assert "READY TO RESOLVE" in badges
    assert _required_child(window, QLabel, "dashboardThreshold").text() == (
        "Needs Attention threshold: 14 days"
    )
    assert (
        "one Prediction may appear in more than one section"
        in _required_child(
            window,
            QLabel,
            "dashboardIntroduction",
        ).text()
    )


def test_dashboard_row_opens_fresh_prediction_detail(qtbot: QtBot) -> None:
    latest = FakePrediction(7, "Open this from Dashboard", 55)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)

    row = _required_child(window, QPushButton, "dashboardOpenPrediction7")
    qtbot.mouseClick(row, Qt.MouseButton.LeftButton)

    assert operations.get_calls[-1] == 7
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )


def test_dashboard_refreshes_when_reentered(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    initial_calls = operations.dashboard_calls
    first_empty = _required_child(window, QLabel, "dashboardOpenEmpty")
    assert first_empty.text() == "No open predictions."

    operations.latest = FakePrediction(8, "Appeared while away", 35)
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")

    assert operations.dashboard_calls == initial_calls + 1
    assert (
        "Appeared while away"
        in _required_child(
            window,
            QPushButton,
            "dashboardOpenPrediction8",
        ).text()
    )


def test_dashboard_refresh_timer_runs_only_while_visible(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    timer = window.findChild(QTimer, "dashboardRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    operations.latest = FakePrediction(9, "Appeared at a time boundary", 48)
    timer.timeout.emit()
    assert (
        "Appeared at a time boundary"
        in _required_child(
            window,
            QPushButton,
            "dashboardOpenPrediction9",
        ).text()
    )

    window.navigate_to("New Prediction")
    assert not timer.isActive()
    window.navigate_to("Dashboard")
    assert timer.isActive()
