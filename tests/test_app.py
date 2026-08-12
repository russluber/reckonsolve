from typing import cast

import pytest
from PySide6.QtWidgets import QApplication, QMainWindow

import reckonsolve.app
from reckonsolve.app import APPLICATION_NAME, ApplicationRuntime, create_runtime
from reckonsolve.data.database import Database
from reckonsolve.data.migrations import MigrationError


def test_application_runtime_reopens_same_database(qtbot, tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"

    first_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(first_runtime.window)
    first_runtime.window.show()
    assert first_runtime.window.isVisible()
    assert first_runtime.database.schema_version == 1
    first_runtime.close()

    second_runtime = create_runtime(database_path=database_path)
    qtbot.addWidget(second_runtime.window)
    second_runtime.window.show()
    assert second_runtime.window.windowTitle() == APPLICATION_NAME
    assert second_runtime.database.schema_version == 1
    second_runtime.close()


def test_runtime_closes_database_when_window_close_fails(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    class FailingWindow:
        def close(self) -> None:
            raise RuntimeError("window close failed")

    runtime = ApplicationRuntime(
        qt_app=cast(QApplication, object()),
        database=database,
        window=cast(QMainWindow, FailingWindow()),
    )

    with pytest.raises(RuntimeError, match="window close failed"):
        runtime.close()

    assert not database.is_open


def test_run_closes_runtime_when_show_fails(monkeypatch, tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")

    class FailingWindow:
        close_called = False

        def show(self) -> None:
            raise RuntimeError("window show failed")

        def close(self) -> None:
            self.close_called = True

    window = FailingWindow()
    runtime = ApplicationRuntime(
        qt_app=cast(QApplication, object()),
        database=database,
        window=cast(QMainWindow, window),
    )
    monkeypatch.setattr(reckonsolve.app, "create_runtime", lambda **_kwargs: runtime)

    with pytest.raises(RuntimeError, match="window show failed"):
        reckonsolve.app.run([])

    assert window.close_called
    assert not database.is_open


def test_run_reports_expected_database_startup_failure(monkeypatch, qtbot) -> None:
    def fail_to_create_runtime(**_kwargs) -> None:
        raise MigrationError("unrecognized database")

    shown_errors: list[tuple[str, str]] = []

    def record_error(_parent, title: str, message: str) -> None:
        shown_errors.append((title, message))

    monkeypatch.setattr(reckonsolve.app, "create_runtime", fail_to_create_runtime)
    monkeypatch.setattr(reckonsolve.app.QMessageBox, "critical", record_error)

    assert reckonsolve.app.run([]) == 1
    assert shown_errors == [
        (
            "Reckonsolve could not start",
            (
                "Reckonsolve could not open its database. No existing data was "
                "replaced.\n\nunrecognized database"
            ),
        )
    ]
