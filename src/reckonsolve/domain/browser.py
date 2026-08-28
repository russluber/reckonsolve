"""Read models and pure filtering rules for the prediction archive."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import date, datetime, tzinfo
from enum import StrEnum
from typing import Protocol

from .attention import needs_attention, ready_to_resolve
from .predictions import (
    FixedPrecisionValue,
    PredictionStatus,
    PredictionType,
    display_status,
)


class ArchiveQueryValidationError(ValueError):
    """Raised when a structured archive request is internally inconsistent."""


class ArchiveTagMatchMode(StrEnum):
    """How several selected tag labels combine for one Prediction."""

    ALL = "all"
    ANY = "any"


class ArchiveAttention(StrEnum):
    """Derived attention populations available in the archive."""

    NEEDS_ATTENTION = "needs_attention"
    READY_TO_RESOLVE = "ready_to_resolve"
    NEEDS_POSTMORTEM = "needs_postmortem"


class ArchiveDateMeaning(StrEnum):
    """The one structured date value to which an optional range applies."""

    CREATED = "created"
    FORECAST_DEADLINE = "forecast_deadline"
    EXPECTED_RESOLUTION = "expected_resolution"
    TERMINAL_DECISION = "terminal_decision"


class ArchiveSort(StrEnum):
    """Deterministic archive presentation orders."""

    RELEVANCE = "relevance"
    CREATED_NEWEST = "created_newest"
    CREATED_OLDEST = "created_oldest"
    QUESTION_A_TO_Z = "question_a_to_z"
    QUESTION_Z_TO_A = "question_z_to_a"
    FORECAST_CONSIDERED_NEWEST = "forecast_considered_newest"
    FORECAST_CONSIDERED_OLDEST = "forecast_considered_oldest"
    EXPECTED_RESOLUTION_SOONEST = "expected_resolution_soonest"
    EXPECTED_RESOLUTION_LATEST = "expected_resolution_latest"
    TERMINAL_DECISION_NEWEST = "terminal_decision_newest"
    TERMINAL_DECISION_OLDEST = "terminal_decision_oldest"


@dataclass(frozen=True, slots=True)
class ArchiveQuery:
    """Read-only structured archive constraints and presentation ordering."""

    status: PredictionStatus | None = None
    prediction_type: PredictionType | None = None
    tags: tuple[str, ...] = ()
    tag_match_mode: ArchiveTagMatchMode = ArchiveTagMatchMode.ALL
    attention: ArchiveAttention | None = None
    date_meaning: ArchiveDateMeaning = ArchiveDateMeaning.CREATED
    date_start: date | None = None
    date_end: date | None = None
    sort: ArchiveSort = ArchiveSort.CREATED_NEWEST


class _ArchiveItem(Protocol):
    prediction_id: int
    question: str
    status: PredictionStatus
    prediction_type: PredictionType
    created_at: datetime
    latest_revision_at: datetime
    forecast_deadline: date | None
    expected_resolution: date | None
    latest_review_at: datetime | None
    terminal_decision_at: datetime | None
    needs_postmortem: bool
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PredictionBrowserItem:
    """One current prediction summary shown in the archive browser."""

    prediction_id: int
    question: str
    probability_percent: int | None
    status: PredictionStatus
    created_at: datetime
    latest_revision_at: datetime
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    latest_review_at: datetime | None = None
    terminal_decision_at: datetime | None = None
    needs_postmortem: bool = False
    tags: tuple[str, ...] = ()
    prediction_type: PredictionType = PredictionType.BINARY
    numeric_lower_bound: FixedPrecisionValue | None = None
    numeric_median_estimate: FixedPrecisionValue | None = None
    numeric_upper_bound: FixedPrecisionValue | None = None
    numeric_confidence_percent: int | None = None
    numeric_unit: str | None = None


@dataclass(frozen=True, slots=True)
class PredictionBrowserSnapshot:
    """Filtered prediction summaries plus all currently associated tags."""

    predictions: tuple[PredictionBrowserItem, ...]
    available_tags: tuple[str, ...]


def validate_archive_query(query: ArchiveQuery, *, text_active: bool) -> None:
    """Reject invalid filters before any read model can claim a false result."""

    if not isinstance(query.status, (PredictionStatus, type(None))):
        raise ArchiveQueryValidationError("The prediction status filter is invalid.")
    if not isinstance(query.prediction_type, (PredictionType, type(None))):
        raise ArchiveQueryValidationError("The forecast type filter is invalid.")
    if not isinstance(query.tag_match_mode, ArchiveTagMatchMode):
        raise ArchiveQueryValidationError("The tag matching mode is invalid.")
    if not isinstance(query.attention, (ArchiveAttention, type(None))):
        raise ArchiveQueryValidationError("The attention filter is invalid.")
    if not isinstance(query.date_meaning, ArchiveDateMeaning):
        raise ArchiveQueryValidationError("The date meaning is invalid.")
    if not isinstance(query.sort, ArchiveSort):
        raise ArchiveQueryValidationError("The archive sort is invalid.")
    if not isinstance(query.tags, tuple) or any(
        not isinstance(tag, str) for tag in query.tags
    ):
        raise ArchiveQueryValidationError("Selected tags must be text labels.")
    if len({tag.strip().casefold() for tag in query.tags if tag.strip()}) != len(
        tuple(tag for tag in query.tags if tag.strip())
    ):
        raise ArchiveQueryValidationError("A tag can be selected only once.")
    if query.date_start is not None and type(query.date_start) is not date:
        raise ArchiveQueryValidationError("The start date is invalid.")
    if query.date_end is not None and type(query.date_end) is not date:
        raise ArchiveQueryValidationError("The end date is invalid.")
    if (
        query.date_start is not None
        and query.date_end is not None
        and query.date_start > query.date_end
    ):
        raise ArchiveQueryValidationError(
            "The start date must not follow the end date."
        )
    if query.sort is ArchiveSort.RELEVANCE and not text_active:
        raise ArchiveQueryValidationError(
            "Relevance sorting is available only while text search is active."
        )


def normalized_archive_tags(tags: tuple[str, ...]) -> tuple[str, ...]:
    """Return selected nonblank tag keys in their stable first-selected order."""

    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags:
        key = tag.strip().casefold()
        if key and key not in seen:
            normalized.append(key)
            seen.add(key)
    return tuple(normalized)


def classify_archive_items[TArchiveItem: _ArchiveItem](
    items: Iterable[TArchiveItem],
    *,
    current_date: date,
) -> tuple[TArchiveItem, ...]:
    """Derive one consistent date-dependent lifecycle status for the archive."""

    classified: list[TArchiveItem] = []
    for item in items:
        status = display_status(item.status, item.forecast_deadline, current_date)
        classified.append(
            replace(
                item,
                status=status,
            )
        )
    return tuple(classified)


def matches_archive_query(
    item: _ArchiveItem,
    query: ArchiveQuery,
    *,
    now: datetime,
    current_date: date,
    stale_threshold_days: int,
    local_timezone: tzinfo | None,
) -> bool:
    """Apply every structured archive filter with logical-AND semantics."""

    if query.status is not None and item.status is not query.status:
        return False
    if (
        query.prediction_type is not None
        and item.prediction_type is not query.prediction_type
    ):
        return False
    selected_tags = normalized_archive_tags(query.tags)
    item_tags = {tag.casefold() for tag in item.tags}
    if selected_tags and (
        not set(selected_tags).issubset(item_tags)
        if query.tag_match_mode is ArchiveTagMatchMode.ALL
        else not bool(set(selected_tags) & item_tags)
    ):
        return False
    if query.attention is ArchiveAttention.NEEDS_ATTENTION and not needs_attention(
        item.status,
        _forecast_considered_at(item),
        now,
        stale_threshold_days,
    ):
        return False
    if query.attention is ArchiveAttention.READY_TO_RESOLVE and not ready_to_resolve(
        item.status,
        item.expected_resolution,
        current_date,
    ):
        return False
    if (
        query.attention is ArchiveAttention.NEEDS_POSTMORTEM
        and not item.needs_postmortem
    ):
        return False
    selected_date = archive_date(item, query.date_meaning, local_timezone)
    return not (query.date_start is not None or query.date_end is not None) or not (
        selected_date is None
        or (query.date_start is not None and selected_date < query.date_start)
        or (query.date_end is not None and selected_date > query.date_end)
    )


def sort_archive_items[TArchiveItem: _ArchiveItem](
    items: Iterable[TArchiveItem],
    sort: ArchiveSort,
) -> tuple[TArchiveItem, ...]:
    """Sort archive rows with null-last values and stable identity tie-breakers."""

    listed = list(items)
    if sort is ArchiveSort.RELEVANCE:
        return tuple(listed)
    if sort is ArchiveSort.CREATED_NEWEST:
        return _sort_present(listed, lambda item: item.created_at, reverse=True)
    if sort is ArchiveSort.CREATED_OLDEST:
        return _sort_present(listed, lambda item: item.created_at, reverse=False)
    if sort is ArchiveSort.QUESTION_A_TO_Z:
        return _sort_present(
            listed, lambda item: item.question.casefold(), reverse=False
        )
    if sort is ArchiveSort.QUESTION_Z_TO_A:
        return _sort_present(
            listed, lambda item: item.question.casefold(), reverse=True
        )
    if sort is ArchiveSort.FORECAST_CONSIDERED_NEWEST:
        return _sort_present(
            listed,
            _forecast_considered_at,
            reverse=True,
        )
    if sort is ArchiveSort.FORECAST_CONSIDERED_OLDEST:
        return _sort_present(
            listed,
            _forecast_considered_at,
            reverse=False,
        )
    if sort is ArchiveSort.EXPECTED_RESOLUTION_SOONEST:
        return _sort_nullable(
            listed,
            lambda item: item.expected_resolution,
            reverse=False,
        )
    if sort is ArchiveSort.EXPECTED_RESOLUTION_LATEST:
        return _sort_nullable(
            listed,
            lambda item: item.expected_resolution,
            reverse=True,
        )
    if sort is ArchiveSort.TERMINAL_DECISION_NEWEST:
        return _sort_nullable(
            listed,
            lambda item: item.terminal_decision_at,
            reverse=True,
        )
    return _sort_nullable(
        listed,
        lambda item: item.terminal_decision_at,
        reverse=False,
    )


def archive_date(
    item: _ArchiveItem,
    meaning: ArchiveDateMeaning,
    local_timezone: tzinfo | None,
) -> date | None:
    """Return one selected date without altering date-only calendar semantics."""

    if meaning is ArchiveDateMeaning.CREATED:
        return item.created_at.astimezone(local_timezone).date()
    if meaning is ArchiveDateMeaning.FORECAST_DEADLINE:
        return item.forecast_deadline
    if meaning is ArchiveDateMeaning.EXPECTED_RESOLUTION:
        return item.expected_resolution
    return (
        None
        if item.terminal_decision_at is None
        else item.terminal_decision_at.astimezone(local_timezone).date()
    )


def _forecast_considered_at(item: _ArchiveItem) -> datetime:
    return max(
        item.latest_revision_at, item.latest_review_at or item.latest_revision_at
    )


def _sort_present[TArchiveItem: _ArchiveItem](
    items: list[TArchiveItem],
    value: Callable[[TArchiveItem], object],
    *,
    reverse: bool,
) -> tuple[TArchiveItem, ...]:
    return tuple(
        sorted(
            sorted(items, key=lambda item: item.prediction_id),
            key=value,
            reverse=reverse,
        )
    )


def _sort_nullable[TArchiveItem: _ArchiveItem](
    items: list[TArchiveItem],
    value: Callable[[TArchiveItem], object | None],
    *,
    reverse: bool,
) -> tuple[TArchiveItem, ...]:
    present = [item for item in items if value(item) is not None]
    absent = [item for item in items if value(item) is None]
    return (
        *_sort_present(present, value, reverse=reverse),
        *sorted(absent, key=lambda item: item.prediction_id),
    )
