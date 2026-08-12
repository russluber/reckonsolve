import pytest

import reckonsolve.app
from reckonsolve import main


def test_package_exposes_callable_entry_point() -> None:
    assert callable(main)


def test_package_entry_point_delegates_to_gui_runner(monkeypatch) -> None:
    monkeypatch.setattr(reckonsolve.app, "run", lambda: 23)

    with pytest.raises(SystemExit) as exit_info:
        main()

    assert exit_info.value.code == 23
