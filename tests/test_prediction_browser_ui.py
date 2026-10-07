"""Archive results, filters, responsive controls, and Saved Views."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from main_window_fakes import (
    FakePrediction,
    FakePredictionOperations,
)
from main_window_helpers import (
    _required_child,
)
from main_window_helpers import (
    operations as operations,  # noqa: PLC0414 - pytest fixture registration
)
from main_window_helpers import (
    window as window,  # noqa: PLC0414 - pytest fixture registration
)
from PySide6.QtCore import QDate, QPoint, QPointF, Qt, QTimer
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
)
from reckonsolve.domain.browser import (
    ArchiveAttention,
    ArchiveDateMeaning,
    ArchiveMode,
    ArchiveQuery,
    ArchiveSort,
    ArchiveTagMatchMode,
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.forecast_contracts import ForecastDeadline, prospective_contract
from reckonsolve.domain.predictions import (
    PredictionStatus,
    PredictionType,
)
from reckonsolve.domain.saved_views import SavedView, SavedViewConfiguration
from reckonsolve.domain.search import (
    SearchMatchMode,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.components import ContentPanel
from reckonsolve.ui.tag_filter_picker import TagFilterPicker
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    BADGE_TONE_PROPERTY,
    ActionRole,
    Radius,
    Spacing,
    StatusTone,
)


def test_prediction_browser_renders_all_results_and_filter_choices(
    qtbot: QtBot,
) -> None:
    first = PredictionBrowserItem(
        prediction_id=1,
        question="Will the archive remain calm?",
        probability_percent=35,
        status=PredictionStatus.OPEN,
        created_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
        tags=("Work",),
        forecast_contract=prospective_contract(
            PredictionType.BINARY, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    second = PredictionBrowserItem(
        prediction_id=2,
        question="<b>Will literal markup stay literal?</b>",
        probability_percent=80,
        status=PredictionStatus.RESOLVED,
        created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 20, 20, 30, tzinfo=UTC),
        tags=("Personal", "Work"),
        forecast_contract=prospective_contract(
            PredictionType.BINARY, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(second, first),
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Predictions")

    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    tag_filter = _required_child(window, TagFilterPicker, "predictionTagFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert [
        status_filter.itemText(index) for index in range(status_filter.count())
    ] == [
        "All",
        "Open",
        "Locked",
        "Resolved",
        "Invalid",
    ]
    assert list(tag_filter.available_tags()) == [
        "Personal",
        "Work",
    ]
    tag_search = _required_child(window, QLineEdit, "predictionTagSearchInput")
    assert tag_search.placeholderText() == "Search or choose a tag…"
    completer = tag_search.completer()
    assert completer is not None
    completer.setCompletionPrefix("")
    assert completer.completionCount() == 2
    tag_search.setText("pers")
    qtbot.keyPress(tag_search, Qt.Key.Key_Return)
    assert tag_filter.selected_tags() == ("Personal",)
    completer.setCompletionPrefix("")
    assert completer.completionCount() == 1
    tag_chip = _required_child(window, QPushButton, "predictionTagChip0")
    assert tag_chip.text() == "Personal  ×"
    qtbot.mouseClick(tag_chip, Qt.MouseButton.LeftButton)
    assert tag_filter.selected_tags() == ()
    completer.setCompletionPrefix("")
    assert completer.completionCount() == 2
    assert results.count() == 2
    assert results.item(0).text() == ""
    assert results.item(0).data(Qt.ItemDataRole.AccessibleTextRole) == (
        "<b>Will literal markup stay literal?</b>"
    )
    assert _required_child(window, QLabel, "predictionResultType2").text() == "BINARY"
    assert _required_child(window, QLabel, "predictionResultStatus2").text() == (
        "RESOLVED"
    )
    assert (
        _required_child(window, QLabel, "predictionResultStatus2").property(
            BADGE_TONE_PROPERTY
        )
        == StatusTone.SUCCESS.value
    )
    assert (
        "Current forecast · 80%"
        in _required_child(window, QLabel, "predictionResultForecast2").text()
    )
    dates = _required_child(window, QLabel, "predictionResultDates2").text()
    assert "Created Aug 20, 2026" in dates
    assert "Forecast deadline " in dates and " at " in dates
    assert "(permanent)" not in dates
    assert _required_child(window, QLabel, "predictionResultTags2").text() == (
        "Tags · Personal, Work"
    )
    assert _required_child(window, QLabel, "predictionBrowserResultCount").text() == (
        "2 predictions"
    )
    open_button = _required_child(window, QPushButton, "openSelectedPredictionButton")
    assert results.currentRow() == -1
    assert results.selectedItems() == []
    assert not open_button.isEnabled()

    qtbot.keyPress(results, Qt.Key.Key_Down)

    assert results.currentRow() == 0
    assert open_button.isEnabled()


def test_prediction_tag_filter_reveals_available_choices_from_empty_field(
    qtbot: QtBot,
) -> None:
    host = QWidget()
    picker = TagFilterPicker(host)
    picker.set_available_tags(("Career", "Personal", "Research"))
    outside = QLineEdit(host)
    layout = QGridLayout(host)
    layout.addWidget(picker, 0, 0)
    layout.addWidget(outside, 1, 0)
    qtbot.addWidget(host)
    host.show()
    qtbot.wait(20)

    qtbot.mouseClick(picker.search_input, Qt.MouseButton.LeftButton)

    completer = picker.search_input.completer()
    assert completer is not None
    qtbot.waitUntil(lambda: completer.popup().isVisible())
    assert completer.completionCount() == 3

    completer.popup().hide()
    outside.setFocus(Qt.FocusReason.MouseFocusReason)
    picker.search_input.setFocus(Qt.FocusReason.MouseFocusReason)
    qtbot.wait(100)
    assert not completer.popup().isVisible()

    qtbot.mouseClick(picker.search_input, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: completer.popup().isVisible())
    first_completion = completer.completionModel().index(0, 0)
    qtbot.mouseClick(
        completer.popup().viewport(),
        Qt.MouseButton.LeftButton,
        pos=completer.popup().visualRect(first_completion).center(),
    )

    qtbot.waitUntil(lambda: picker.selected_tags() == ("Career",))
    qtbot.waitUntil(lambda: picker.search_input.text() == "")
    chip = _required_child(picker, QPushButton, "predictionTagChip0")
    qtbot.mouseClick(chip, Qt.MouseButton.LeftButton)
    assert picker.selected_tags() == ()
    assert picker.search_input.hasFocus()


def test_prediction_browser_groups_controls_and_keeps_detailed_inputs_readable(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the archive controls remain readable?", 55)
    )
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(),
        available_tags=("Career", "Personal", "Research", "Travel"),
    )
    window = MainWindow(operations)
    window.resize(760, 520)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")

    scroll = _required_child(
        window,
        QScrollArea,
        "predictionBrowserControlsScrollArea",
    )
    workspace = _required_child(window, QSplitter, "predictionBrowserWorkspace")
    results_panel = _required_child(
        window,
        QFrame,
        "predictionBrowserResultsPanel",
    )
    content = _required_child(window, QWidget, "predictionBrowserContent")
    groups = [
        _required_child(window, QFrame, name)
        for name in (
            "predictionSearchGroup",
            "predictionCommonFiltersGroup",
            "predictionDetailedFiltersGroup",
            "predictionSavedViewsGroup",
        )
    ]
    group_tops = [group.mapTo(content, group.rect().topLeft()).y() for group in groups]
    assert group_tops == sorted(group_tops)
    assert workspace.orientation() is Qt.Orientation.Vertical
    assert scroll.minimumWidth() == 0
    assert results_panel.minimumWidth() == 0
    assert scroll.geometry().right() <= workspace.rect().right()
    assert results_panel.geometry().right() <= workspace.rect().right()
    assert scroll.verticalScrollBar().maximum() > 0
    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    wheel_position = status_filter.rect().center()
    narrow_wheel = QWheelEvent(
        QPointF(wheel_position),
        QPointF(status_filter.mapToGlobal(wheel_position)),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(status_filter, narrow_wheel)
    assert status_filter.currentIndex() == 0
    assert scroll.verticalScrollBar().value() > 0
    date_start = _required_child(window, QDateEdit, "predictionDateStart")
    original_start_date = date_start.date()
    scroll_after_combo = scroll.verticalScrollBar().value()
    date_wheel_position = date_start.rect().center()
    narrow_date_wheel = QWheelEvent(
        QPointF(date_wheel_position),
        QPointF(date_start.mapToGlobal(date_wheel_position)),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(date_start, narrow_date_wheel)
    assert date_start.date() == original_start_date
    assert scroll.verticalScrollBar().value() > scroll_after_combo
    for control_name in (
        "savedViewPicker",
        "predictionSearchMatchMode",
        "predictionStatusFilter",
        "predictionTypeFilter",
        "predictionModeFilter",
        "predictionTagMatchMode",
        "predictionAttentionFilter",
        "predictionDateMeaning",
        "predictionSort",
        "predictionDateStart",
        "predictionDateEnd",
    ):
        assert _required_child(window, QWidget, control_name).focusPolicy() == (
            Qt.FocusPolicy.StrongFocus
        )
    assert _required_child(window, QLabel, "predictionSearchLabel").isHidden()
    assert _required_child(window, QLabel, "savedViewLabel").isHidden()
    assert _required_child(window, QLabel, "savedViewState").isHidden()
    assert _required_child(window, QLineEdit, "predictionTagSearchInput").isVisible()
    assert _required_child(window, QDateEdit, "predictionDateStart").width() >= 118
    assert _required_child(window, QDateEdit, "predictionDateEnd").width() >= 118
    assert (
        _required_child(window, QPushButton, "applyPredictionFiltersButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.PRIMARY.value
    )
    assert (
        _required_child(window, QPushButton, "deleteSavedViewButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.DESTRUCTIVE.value
    )

    window.resize(1920, 1080)
    qtbot.waitUntil(
        lambda: workspace.orientation() is Qt.Orientation.Horizontal,
    )
    qtbot.waitUntil(lambda: scroll.verticalScrollBar().maximum() == 0)
    wide_wheel = QWheelEvent(
        QPointF(wheel_position),
        QPointF(status_filter.mapToGlobal(wheel_position)),
        QPoint(),
        QPoint(0, -120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(status_filter, wide_wheel)
    assert status_filter.currentIndex() == 1
    filters_panel = _required_child(
        window,
        ContentPanel,
        "predictionBrowserFiltersPanel",
    )
    assert filters_panel.isVisible()
    assert filters_panel.layout().spacing() == int(Spacing.COMPACT)
    heading = filters_panel.title_label.parentWidget()
    assert heading is not None
    assert heading.height() == heading.sizeHint().height()
    assert filters_panel.supporting_label.height() <= (
        2 * filters_panel.supporting_label.fontMetrics().height()
    )
    assert filters_panel.supporting_label.y() - (heading.y() + heading.height()) == int(
        Spacing.COMPACT
    )
    assert filters_panel.body.y() - (
        filters_panel.supporting_label.y() + filters_panel.supporting_label.height()
    ) == int(Spacing.COMPACT)
    assert results_panel.isVisible()
    assert results_panel.mapTo(window, results_panel.rect().topLeft()).x() > (
        filters_panel.mapTo(window, filters_panel.rect().topLeft()).x()
    )
    assert scroll.minimumWidth() == 520
    assert results_panel.minimumWidth() == 520
    tag_filter = _required_child(window, TagFilterPicker, "predictionTagFilter")
    detailed_group = _required_child(
        window,
        QFrame,
        "predictionDetailedFiltersGroup",
    )
    date_meaning = _required_child(window, QComboBox, "predictionDateMeaning")
    empty_picker_height = tag_filter.sizeHint().height()
    empty_date_top = date_meaning.mapTo(
        detailed_group,
        date_meaning.rect().topLeft(),
    ).y()
    tag_filter.select_tag("Career")
    qtbot.wait(20)
    assert tag_filter.sizeHint().height() == empty_picker_height
    assert (
        date_meaning.mapTo(detailed_group, date_meaning.rect().topLeft()).y()
        == empty_date_top
    )
    tag_filter.remove_tag("Career")
    qtbot.wait(20)
    assert tag_filter.sizeHint().height() == empty_picker_height
    assert (
        date_meaning.mapTo(detailed_group, date_meaning.rect().topLeft()).y()
        == empty_date_top
    )
    workspace.setSizes([1, 10_000])
    qtbot.waitUntil(lambda: scroll.width() >= 520)
    assert results_panel.width() >= 520
    workspace.setSizes([10_000, 1])
    qtbot.waitUntil(lambda: results_panel.width() >= 520)
    assert scroll.width() >= 520
    saved_buttons = [
        _required_child(window, QPushButton, object_name)
        for object_name in (
            "saveCurrentViewButton",
            "saveViewAsNewButton",
            "updateSavedViewButton",
            "renameSavedViewButton",
            "deleteSavedViewButton",
        )
    ]
    button_widths = [button.width() for button in saved_buttons]
    assert max(button_widths) - min(button_widths) <= 1
    assert all(button.width() >= button.sizeHint().width() for button in saved_buttons)
    assert [
        button.property("reckonsolveLucideIcon") for button in saved_buttons[:3]
    ] == ["save", "circle-plus", "refresh-cw"]
    common_filter_widths = [
        _required_child(window, QComboBox, object_name).width()
        for object_name in (
            "predictionStatusFilter",
            "predictionTypeFilter",
            "predictionAttentionFilter",
            "predictionSort",
        )
    ]
    assert max(common_filter_widths) - min(common_filter_widths) <= 1
    assert (
        _required_child(window, QPushButton, "renameSavedViewButton").property(
            ACTION_ROLE_PROPERTY
        )
        == ActionRole.SECONDARY.value
    )


def test_prediction_browser_mouse_click_opens_row_without_hover_only_action(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(7, "Open this archive row with one click", 62)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    window.resize(1200, 900)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    item = results.item(0)

    qtbot.mouseClick(
        results.viewport(),
        Qt.MouseButton.LeftButton,
        pos=results.visualItemRect(item).center(),
    )

    assert window.current_screen_name == "Prediction Detail"
    assert operations.get_calls[-1] == latest.prediction_id


def test_prediction_browser_combines_filters_and_clear_restores_archive(
    qtbot: QtBot,
) -> None:
    items = (
        PredictionBrowserItem(
            prediction_id=3,
            question="Will policy pass this year?",
            probability_percent=70,
            status=PredictionStatus.RESOLVED,
            created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            tags=("Work",),
            forecast_contract=prospective_contract(
                PredictionType.BINARY,
                ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
            ),
        ),
        PredictionBrowserItem(
            prediction_id=2,
            question="Will policy pass next year?",
            probability_percent=40,
            status=PredictionStatus.OPEN,
            created_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
            tags=("Work",),
            forecast_contract=prospective_contract(
                PredictionType.BINARY,
                ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
            ),
        ),
        PredictionBrowserItem(
            prediction_id=1,
            question="Will another issue resolve?",
            probability_percent=20,
            status=PredictionStatus.RESOLVED,
            created_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
            tags=("Personal",),
            forecast_contract=prospective_contract(
                PredictionType.BINARY,
                ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
            ),
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=items,
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    tag_filter = _required_child(window, TagFilterPicker, "predictionTagFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    search.setText("THIS YEAR")
    status_filter.setCurrentIndex(status_filter.findData("resolved"))
    tag_filter.select_tag("Work")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert results.count() == 1
    assert results.item(0).data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Will policy pass this year?"
    )
    assert operations.browser_calls[-1] == (
        "THIS YEAR",
        PredictionStatus.RESOLVED,
        None,
    )
    assert operations.archive_calls[-1][0] == ("Work",)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert search.text() == ""
    assert status_filter.currentData() is None
    assert tag_filter.selected_tags() == ()
    assert results.count() == 3
    assert operations.browser_calls[-1] == ("", None, None)


def test_prediction_browser_clears_a_filter_when_its_last_tag_is_removed(
    qtbot: QtBot,
) -> None:
    tagged = PredictionBrowserItem(
        prediction_id=1,
        question="Will an external edit remove this tag?",
        probability_percent=50,
        status=PredictionStatus.OPEN,
        created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        tags=("Temporary",),
        forecast_contract=prospective_contract(
            PredictionType.BINARY, ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC))
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(tagged,),
        available_tags=("Temporary",),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    tag_filter = _required_child(window, TagFilterPicker, "predictionTagFilter")
    tag_filter.select_tag("Temporary")

    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(replace(tagged, tags=()),),
        available_tags=(),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert tag_filter.selected_tags() == ()
    assert results.count() == 1
    assert operations.browser_calls[-2:] == [("", None, None), ("", None, None)]
    assert [call[0] for call in operations.archive_calls[-2:]] == [
        ("Temporary",),
        (),
    ]


def test_prediction_browser_sends_rich_archive_filters_and_resets_defaults(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will the rich archive controls remain clear?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=instant,
                latest_revision_at=instant,
                tags=("Blue", "Red"),
                forecast_contract=prospective_contract(
                    PredictionType.BINARY,
                    ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                ),
            ),
        ),
        available_tags=("Blue", "Green", "Red"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    tag_filter = _required_child(window, TagFilterPicker, "predictionTagFilter")
    tag_filter.select_tag("Blue")
    tag_filter.select_tag("Red")
    tag_mode = _required_child(window, QComboBox, "predictionTagMatchMode")
    tag_mode.setCurrentIndex(tag_mode.findData(ArchiveTagMatchMode.ANY.value))
    attention = _required_child(window, QComboBox, "predictionAttentionFilter")
    attention.setCurrentIndex(
        attention.findData(ArchiveAttention.NEEDS_ATTENTION.value)
    )
    date_meaning = _required_child(window, QComboBox, "predictionDateMeaning")
    date_meaning.setCurrentIndex(
        date_meaning.findData(ArchiveDateMeaning.EXPECTED_RESOLUTION.value)
    )
    date_start_enabled = _required_child(
        window, QCheckBox, "predictionDateStartEnabled"
    )
    date_start_enabled.setChecked(True)
    date_start = _required_child(window, QDateEdit, "predictionDateStart")
    date_start.setDate(QDate(2026, 8, 1))
    date_end_enabled = _required_child(window, QCheckBox, "predictionDateEndEnabled")
    date_end_enabled.setChecked(True)
    date_end = _required_child(window, QDateEdit, "predictionDateEnd")
    date_end.setDate(QDate(2026, 8, 31))
    sort = _required_child(window, QComboBox, "predictionSort")
    sort.setCurrentIndex(sort.findData(ArchiveSort.QUESTION_A_TO_Z.value))
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.archive_calls[-1] == (
        ("Blue", "Red"),
        ArchiveTagMatchMode.ANY,
        ArchiveAttention.NEEDS_ATTENTION,
        ArchiveDateMeaning.EXPECTED_RESOLUTION,
        date(2026, 8, 1),
        date(2026, 8, 31),
        ArchiveSort.QUESTION_A_TO_Z,
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert tag_filter.selected_tags() == ()
    assert tag_mode.currentData() == ArchiveTagMatchMode.ALL.value
    assert attention.currentData() is None
    assert date_meaning.currentData() == ArchiveDateMeaning.CREATED.value
    assert not date_start_enabled.isChecked()
    assert not date_end_enabled.isChecked()
    assert sort.currentData() == ArchiveSort.CREATED_NEWEST.value

    _required_child(window, QLineEdit, "predictionSearchInput").setText("rich")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )
    assert operations.archive_calls[-1][-1] is ArchiveSort.RELEVANCE


def test_prediction_browser_applies_and_explicitly_updates_dynamic_saved_views(
    qtbot: QtBot,
) -> None:
    instant = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)
    configuration = SavedViewConfiguration(
        search_text="evidence",
        match_mode=SearchMatchMode.ANY,
        include_superseded=True,
        archive_query=ArchiveQuery(
            status=PredictionStatus.OPEN,
            prediction_type=PredictionType.BINARY,
            mode=ArchiveMode.ONE_SHOT,
            tags=("Work",),
            tag_match_mode=ArchiveTagMatchMode.ALL,
            attention=None,
            date_meaning=ArchiveDateMeaning.EXPECTED_RESOLUTION,
            date_start=date(2026, 8, 1),
            date_end=date(2026, 8, 31),
            sort=ArchiveSort.RELEVANCE,
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will evidence remain in a dynamic Saved View?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=instant,
                latest_revision_at=instant,
                expected_resolution=date(2026, 8, 15),
                tags=("Work",),
                forecast_contract=prospective_contract(
                    PredictionType.BINARY,
                    ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                ),
            ),
        ),
        available_tags=("Work",),
    )
    operations.saved_views = [
        SavedView(
            saved_view_id=7,
            name="Evidence",
            normalized_name="evidence",
            configuration=configuration,
            tags=(),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    picker = _required_child(window, QComboBox, "savedViewPicker")
    picker.setCurrentIndex(picker.findData(7))

    assert _required_child(window, QLineEdit, "predictionSearchInput").text() == (
        "evidence"
    )
    assert _required_child(
        window, QComboBox, "predictionSearchMatchMode"
    ).currentData() == (SearchMatchMode.ANY.value)
    assert _required_child(
        window, QCheckBox, "predictionSearchIncludeHistory"
    ).isChecked()
    assert _required_child(
        window, QComboBox, "predictionStatusFilter"
    ).currentData() == (PredictionStatus.OPEN.value)
    assert _required_child(window, QComboBox, "predictionModeFilter").currentData() == (
        ArchiveMode.ONE_SHOT.value
    )
    assert _required_child(
        window, QComboBox, "predictionDateMeaning"
    ).currentData() == (ArchiveDateMeaning.EXPECTED_RESOLUTION.value)
    assert _required_child(window, QLabel, "savedViewState").text() == "Evidence: Saved"

    status = _required_child(window, QComboBox, "predictionStatusFilter")
    status.setCurrentIndex(status.findData(PredictionStatus.RESOLVED.value))
    update = _required_child(window, QPushButton, "updateSavedViewButton")
    assert update.isEnabled()
    assert _required_child(window, QLabel, "savedViewState").text() == (
        "Evidence: Modified"
    )

    qtbot.mouseClick(update, Qt.MouseButton.LeftButton)

    assert operations.saved_views[0].configuration.archive_query.status is (
        PredictionStatus.RESOLVED
    )
    assert operations.saved_views[0].configuration.archive_query.mode is (
        ArchiveMode.ONE_SHOT
    )
    assert _required_child(window, QLabel, "savedViewState").text() == "Evidence: Saved"


def test_prediction_browser_saved_view_creation_rename_delete_and_cancel(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Focus", True),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveCurrentViewButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [view.name for view in operations.saved_views] == ["Focus"]
    assert _required_child(window, QLabel, "savedViewState").text() == "Focus: Saved"

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Renamed", True),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "renameSavedViewButton"),
        Qt.MouseButton.LeftButton,
    )
    assert [view.name for view in operations.saved_views] == ["Renamed"]

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QInputDialog.getText",
        lambda *_args, **_kwargs: ("Ignored", False),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "saveViewAsNewButton"),
        Qt.MouseButton.LeftButton,
    )
    assert [view.name for view in operations.saved_views] == ["Renamed"]

    monkeypatch.setattr(
        "reckonsolve.ui.prediction_browser.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "deleteSavedViewButton"),
        Qt.MouseButton.LeftButton,
    )
    assert operations.saved_views == []
    saved_state = _required_child(window, QLabel, "savedViewState")
    assert saved_state.text() == ""
    assert saved_state.isHidden()


def test_prediction_browser_distinguishes_new_database_and_no_matches(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    empty = _required_child(window, QLabel, "predictionBrowserEmpty")

    assert empty.text() == "No predictions yet. Create one from New Prediction."

    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will something happen?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
                latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
                forecast_contract=prospective_contract(
                    PredictionType.BINARY,
                    ForecastDeadline(datetime(2099, 1, 1, tzinfo=UTC)),
                ),
            ),
        ),
        available_tags=(),
    )
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    search.setText("absent")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    assert empty.text() == "No predictions match the current search and filters."
    assert _required_child(window, QListWidget, "predictionBrowserResults").isHidden()


def test_prediction_browser_opens_fresh_detail_from_keyboard_activation(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Open this from the Predictions archive",
        62,
        tags=("Archive",),
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    results.itemActivated.emit(results.item(0))

    assert operations.get_calls[-1] == latest.prediction_id
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )


def test_prediction_result_rows_are_inset_from_the_rounded_frame(
    window: MainWindow,
    qtbot: QtBot,
) -> None:
    window.show()
    window.navigate_to("Predictions")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    results.setFocus()
    qtbot.waitUntil(lambda: results.viewport().width() > 0)

    viewport = results.viewport().geometry()
    inset = int(Radius.SMALL)
    assert viewport.left() >= inset
    assert viewport.top() >= inset
    assert results.width() - viewport.right() - 1 >= inset
    assert results.height() - viewport.bottom() - 1 >= inset


def test_prediction_browser_refreshes_and_reports_initial_or_stale_errors(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    operations.browser_error = ApplicationError("Archive could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    error = _required_child(window, QLabel, "predictionBrowserError")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    assert error.text() == "Predictions unavailable. Archive could not be loaded."
    assert results.isHidden()

    operations.browser_error = None
    operations.latest = FakePrediction(9, "Appeared after retry", 48)
    window.navigate_to("New Prediction")
    window.navigate_to("Predictions")
    assert results.count() == 1
    operations.browser_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Predictions")

    assert error.text() == (
        "Predictions could not refresh; showing the last loaded results. "
        "Refresh failed."
    )
    assert not results.isHidden()
    assert results.item(0).data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Appeared after retry"
    )


def test_prediction_browser_timer_runs_only_while_visible(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    timer = window.findChild(QTimer, "predictionBrowserRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    operations.latest = FakePrediction(10, "Appeared at the lock boundary", 33)
    timer.timeout.emit()
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert results.item(0).data(Qt.ItemDataRole.AccessibleTextRole) == (
        "Appeared at the lock boundary"
    )

    window.navigate_to("New Prediction")
    assert not timer.isActive()
