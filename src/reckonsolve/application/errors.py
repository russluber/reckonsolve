"""Expected errors that presentation code may show without a traceback."""


class ApplicationError(Exception):
    """Base class for expected, user-presentable application failures."""


class ValidationError(ApplicationError):
    """A user-supplied value failed authoritative validation."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field
