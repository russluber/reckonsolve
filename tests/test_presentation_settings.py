"""Focused tests for noncanonical, identity-isolated shell preferences."""

from PySide6.QtCore import QRect

from reckonsolve.ui.presentation_settings import (
    MINIMUM_WINDOW_SIZE,
    QtPresentationSettings,
    WindowPresentationState,
    safe_window_geometry,
)


def test_qt_presentation_settings_round_trip_outside_sqlite(tmp_path) -> None:
    path = tmp_path / "stable" / "presentation.ini"
    path.parent.mkdir()
    settings = QtPresentationSettings(path)
    state = WindowPresentationState(
        sidebar_compact=True,
        normal_geometry=(120, 80, 1100, 720),
        maximized=True,
    )

    assert settings.save(state)

    assert QtPresentationSettings(path).load() == state
    assert path.is_file()
    assert not (path.parent / "reckonsolve.sqlite3").exists()


def test_stable_and_development_presentation_files_are_independent(tmp_path) -> None:
    stable = QtPresentationSettings(tmp_path / "Reckonsolve" / "presentation.ini")
    development = QtPresentationSettings(
        tmp_path / "Reckonsolve Dev" / "presentation.ini"
    )
    stable.path.parent.mkdir()
    development.path.parent.mkdir()

    assert stable.save(WindowPresentationState(sidebar_compact=True))
    assert development.save(WindowPresentationState(sidebar_compact=False))

    assert stable.load().sidebar_compact
    assert not development.load().sidebar_compact


def test_corrupt_presentation_settings_fall_back_to_safe_defaults(tmp_path) -> None:
    path = tmp_path / "presentation.ini"
    path.write_text("[window\nnormal_geometry=not,usable", encoding="utf-8")

    assert QtPresentationSettings(path).load() == WindowPresentationState()


def test_unwritable_presentation_settings_do_not_raise(tmp_path) -> None:
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("block", encoding="utf-8")
    settings = QtPresentationSettings(blocking_file / "presentation.ini")

    assert not settings.save(WindowPresentationState(sidebar_compact=True))
    assert settings.load() == WindowPresentationState()


def test_safe_window_geometry_preserves_and_fits_a_visible_saved_window() -> None:
    screens = (
        QRect(0, 0, 1920, 1040),
        QRect(-1280, 0, 1280, 1024),
    )

    unchanged = safe_window_geometry((-1200, 60, 1000, 700), screens)
    partly_visible = safe_window_geometry((1700, 80, 1000, 700), screens)

    assert unchanged == QRect(-1200, 60, 1000, 700)
    assert partly_visible == QRect(920, 80, 1000, 700)


def test_safe_window_geometry_recovers_from_removed_monitor_and_bad_size() -> None:
    screen = QRect(0, 0, 1920, 1040)

    removed_monitor = safe_window_geometry((3000, 100, 1000, 700), (screen,))
    too_small = safe_window_geometry((40, 50, 120, 90), (screen,))

    assert removed_monitor == QRect(480, 200, 960, 640)
    assert too_small.width() >= MINIMUM_WINDOW_SIZE.width()
    assert too_small.height() >= MINIMUM_WINDOW_SIZE.height()
    assert screen.contains(too_small)


def test_safe_window_geometry_has_a_fallback_when_no_screen_is_reported() -> None:
    assert safe_window_geometry((9000, 9000, 100, 100), ()) == QRect(
        100,
        100,
        960,
        640,
    )
