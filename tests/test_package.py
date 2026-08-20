import pytest

import reckonsolve.app
from reckonsolve import main, main_dev
from reckonsolve.identity import DEVELOPMENT_APPLICATION


def test_package_exposes_callable_entry_point() -> None:
    assert callable(main)


def test_package_entry_point_delegates_to_gui_runner(monkeypatch) -> None:
    monkeypatch.setattr(reckonsolve.app, "run", lambda: 23)

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 23


def test_development_entry_point_uses_isolated_identity(monkeypatch) -> None:
    calls = []

    def fake_run(*, identity):
        calls.append(identity)
        return 29

    monkeypatch.setattr(reckonsolve.app, "run", fake_run)

    with pytest.raises(SystemExit) as exit_info:
        main_dev()

    assert exit_info.value.code == 29
    assert calls == [DEVELOPMENT_APPLICATION]
