"""Retired routes refuse before opening data; attention remains CLI configurable."""

from io import StringIO

import pytest

from reckonsolve import cli
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database


@pytest.mark.parametrize(
    "arguments",
    (["saved-views"], ["saved-view", "--id", "1"], ["saved-view", "--name", "old"]),
)
def test_retired_cli_routes_do_not_resolve_or_open_a_database(monkeypatch, arguments):
    def refuse(**kwargs):
        raise AssertionError("Retired command reached data access")

    monkeypatch.setattr(cli, "create_runtime", refuse)
    with pytest.raises(SystemExit) as raised:
        cli.run(arguments)
    assert raised.value.code == 2


def test_attention_threshold_read_change_and_invalid_values(tmp_path, monkeypatch):
    path = tmp_path / "journal.sqlite3"
    output = StringIO()
    assert (
        cli.run(["settings", "attention-days"], database_path=path, stdout=output) == 0
    )
    assert output.getvalue() == "Review after: 14 days\n"
    assert (
        cli.run(
            ["settings", "attention-days", "--set", "21"],
            database_path=path,
            stdout=StringIO(),
        )
        == 0
    )
    database = Database.open(path)
    try:
        assert PredictionOperations(database).get_stale_threshold_days() == 21
        with database.read_snapshot() as connection:
            assert (
                connection.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
                == 0
            )
    finally:
        database.close()
    monkeypatch.setattr(
        cli, "create_runtime", lambda **kwargs: pytest.fail("Invalid input opened data")
    )
    for value in ("0", "10000", "1.5", "no"):
        with pytest.raises(SystemExit) as raised:
            cli.run(["settings", "attention-days", "--set", value])
        assert raised.value.code == 2
