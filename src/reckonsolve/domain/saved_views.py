"""Mutable, dynamic archive-query preferences for the Predictions screen."""

from dataclasses import dataclass

from .browser import ArchiveQuery, validate_archive_query
from .search import SearchMatchMode, SearchQuery


class SavedViewValidationError(ValueError):
    """A Saved View name or configuration is not valid."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True, slots=True)
class SavedViewTag:
    """One stable tag reference plus its current display label."""

    tag_id: int
    display_name: str


@dataclass(frozen=True, slots=True)
class SavedViewConfiguration:
    """Every read-only archive control retained by a Saved View."""

    search_text: str
    match_mode: SearchMatchMode
    include_superseded: bool
    archive_query: ArchiveQuery

    def __post_init__(self) -> None:
        try:
            search = SearchQuery(
                self.search_text,
                self.match_mode,
                self.include_superseded,
            )
            validate_archive_query(
                self.archive_query,
                text_active=bool(search.text.strip()),
            )
        except ValueError as error:
            field = getattr(error, "field", "configuration")
            raise SavedViewValidationError(str(error), field=field) from error


@dataclass(frozen=True, slots=True)
class SavedView:
    """A named dynamic query, never a stored Prediction-result snapshot."""

    saved_view_id: int
    name: str
    normalized_name: str
    configuration: SavedViewConfiguration
    tags: tuple[SavedViewTag, ...]


def normalize_saved_view_name(value: str) -> tuple[str, str]:
    """Validate a display name while deriving stable case-insensitive identity."""

    if not isinstance(value, str):
        raise SavedViewValidationError("Saved View name must be text.", field="name")
    name = value.strip()
    if not name:
        raise SavedViewValidationError("Saved View name is required.", field="name")
    if "\x00" in name:
        raise SavedViewValidationError(
            "Saved View name cannot contain a null character.", field="name"
        )
    return name, name.casefold()
