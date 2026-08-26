"""Public package entry points for Reckonsolve."""


def main() -> None:
    """Run the desktop application from the installed console script."""

    from reckonsolve.app import run

    raise SystemExit(run())


def main_dev() -> None:
    """Run the visibly isolated development application."""

    from reckonsolve.app import run
    from reckonsolve.identity import DEVELOPMENT_APPLICATION

    raise SystemExit(run(identity=DEVELOPMENT_APPLICATION))


def main_cli() -> None:
    """Run the stable command-line companion."""

    from reckonsolve.cli import run

    raise SystemExit(run())


def main_cli_dev() -> None:
    """Run the command-line companion against isolated development data."""

    from reckonsolve.cli import run
    from reckonsolve.identity import DEVELOPMENT_APPLICATION

    raise SystemExit(run(identity=DEVELOPMENT_APPLICATION))
