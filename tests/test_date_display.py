"""GUI date preferences retain canonical facts and native entered time values."""

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from PySide6.QtCore import QDate, QDateTime, QTime, QTimeZone
from PySide6.QtWidgets import QDateTimeEdit, QWidget
from supported_fixtures import create_binary

from reckonsolve.app import create_runtime
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.ui.date_display import (
    DateFormat,
    format_date,
    format_datetime,
    format_exact_datetime,
    update_date_inputs,
)
from reckonsolve.ui.presentation_settings import (
    QtPresentationSettings,
    WindowPresentationState,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (DateFormat.DAY_FIRST, "03-02-2026"),
        (DateFormat.MONTH_FIRST, "02-03-2026"),
        (DateFormat.YEAR_FIRST, "2026-02-03"),
    ],
)
def test_date_formats_round_trip_and_keep_exact_instants(
    tmp_path, qtbot, value, expected
):
    parent = QWidget()
    parent.display_date_format = value
    qtbot.addWidget(parent)
    assert format_date(date(2026, 2, 3), parent) == expected
    instant = datetime(2026, 2, 3, 18, 30, 45, 123456, tzinfo=UTC)
    assert "UTC" not in format_datetime(instant, parent)
    assert "UTC" in format_exact_datetime(instant, parent)
    assert ".123456" in format_exact_datetime(instant, parent)
    settings = QtPresentationSettings(tmp_path / "presentation.ini")
    assert settings.save(replace(WindowPresentationState(), date_format=value))
    assert settings.load().date_format is value
    editor = QDateTimeEdit(parent)
    editor.setDisplayFormat("yyyy-MM-dd HH:mm:ss.zzz")
    editor.setDateTime(
        QDateTime(QDate(2026, 2, 3), QTime(4, 5, 6, 789), QTimeZone.systemTimeZone())
    )
    original = editor.dateTime()
    update_date_inputs(parent)
    assert editor.dateTime() == original
    assert editor.displayFormat() == value.qt_pattern + " HH:mm:ss.zzz"


def test_settings_date_order_updates_all_returned_details_and_survives_restart(
    tmp_path, qtbot
):
    path = tmp_path / "journal.sqlite3"
    runtime = create_runtime(database_path=path)
    w = runtime.window
    qtbot.addWidget(w)
    w.show()
    try:
        prediction = create_binary(w.operations, "Formatting is presentation", 65)
        before = w.operations.get_prediction_for_navigation(prediction.prediction_id)
        w._open_prediction(prediction.prediction_id)
        w.navigate_to("Settings")
        combo = w._settings_screen.date_format_input
        combo.setCurrentIndex(combo.findData(DateFormat.DAY_FIRST))
        assert w.display_date_format is DateFormat.DAY_FIRST
        assert "UTC" in w._settings_screen.time_zone_label.text()
        w.return_to_source()
        assert w._prediction_detail_screen.expected_resolution.text() in ("", "Not set")
        from PySide6.QtWidgets import QLabel

        timestamp = w._prediction_detail_screen.findChild(
            QLabel, f"forecastRevisionTimestamp{prediction.current_revision_id}"
        )
        assert timestamp.text().startswith(
            prediction.created_at.astimezone().strftime("%d-%m-%Y")
        )
        assert (
            w.operations.get_prediction_for_navigation(prediction.prediction_id)
            == before
        )
        w.return_to_source()
        qtbot.waitUntil(lambda: not w._journal_screen.loading)
        assert all(
            card.rendered_date_context[0] is DateFormat.DAY_FIRST
            for card in w._journal_screen.cards
        )
    finally:
        runtime.close()
    reopened = create_runtime(database_path=path)
    qtbot.addWidget(reopened.window)
    try:
        assert reopened.window.display_date_format is DateFormat.DAY_FIRST
        assert reopened.window.operations.journal.query(JournalRequest()).total == 1
    finally:
        reopened.close()


def test_bad_date_preference_uses_year_first(tmp_path):
    path = tmp_path / "presentation.ini"
    path.write_text("[display]\ndate_format=unknown\n", encoding="utf-8")
    assert QtPresentationSettings(path).load().date_format is DateFormat.YEAR_FIRST


@pytest.mark.parametrize("value", list(DateFormat))
def test_filter_boundaries_accept_a_complete_date_in_each_selected_order(qtbot, value):
    from reckonsolve.domain.journal import JournalRequest
    from reckonsolve.ui.journal.filters import JournalFiltersDialog

    parent = QWidget()
    parent.display_date_format = value
    qtbot.addWidget(parent)
    dialog = JournalFiltersDialog(JournalRequest(), (), parent)
    qtbot.addWidget(dialog)
    enabled, editor = dialog.date_rows[0]
    enabled.setChecked(True)
    editor.setDate(QDate(2026, 2, 3))
    assert editor.displayFormat() == value.qt_pattern
    assert editor.complete_date()
    dialog.apply()
    assert dialog.applied.filters.date_start == date(2026, 2, 3)


def test_date_order_reformats_existing_settings_receipt_without_another_backup(
    tmp_path, qtbot, monkeypatch
):
    from PySide6.QtWidgets import QFileDialog

    runtime = create_runtime(database_path=tmp_path / "journal.sqlite3")
    w = runtime.window
    qtbot.addWidget(w)
    w.show()
    w.navigate_to("Settings")
    try:
        monkeypatch.setattr(
            QFileDialog,
            "getSaveFileName",
            lambda *args: (str(tmp_path / "complete.sqlite3"), ""),
        )
        screen = w._settings_screen
        screen.backup_button.click()
        before = w.operations.get_data_management_status().last_successful_backup_at
        original = screen.backup_tool.result.text()
        screen.date_format_input.setCurrentIndex(
            screen.date_format_input.findData(DateFormat.DAY_FIRST)
        )
        assert (
            before.astimezone().strftime("%d-%m-%Y") in screen.backup_tool.result.text()
        )
        assert screen.backup_tool.result.text() != original
        assert (
            w.operations.get_data_management_status().last_successful_backup_at
            == before
        )
        w.return_to_source()
        assert screen.backup_tool.date_renderer is None
    finally:
        runtime.close()
