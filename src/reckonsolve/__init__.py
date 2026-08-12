"""Public package entry points for Reckonsolve."""


def main() -> None:
    """Run the desktop application from the installed console script."""

    from reckonsolve.app import run

    raise SystemExit(run())
