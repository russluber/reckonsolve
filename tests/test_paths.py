from pathlib import Path

from reckonsolve.paths import DATABASE_FILENAME, resolve_database_path


def test_explicit_database_path_is_used_unchanged(tmp_path) -> None:
    explicit_path = tmp_path / "chosen.sqlite3"

    assert resolve_database_path(explicit_path) == explicit_path


def test_injected_application_data_directory_gets_stable_filename(tmp_path) -> None:
    app_data_directory = Path(tmp_path) / "Reckonsolve"

    assert (
        resolve_database_path(app_data_directory=app_data_directory)
        == app_data_directory / DATABASE_FILENAME
    )
