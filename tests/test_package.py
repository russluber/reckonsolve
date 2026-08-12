from reckonsolve import main


def test_package_exposes_callable_entry_point() -> None:
    assert callable(main)
