"""Journal requests and display-ready facts, independent of Qt and storage."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from .browser import (
    ArchiveQuery,
    ArchiveSort,
    PredictionBrowserItem,
    validate_archive_query,
)
from .predictions import BinaryOutcome, FixedPrecisionValue
from .quantiles import FiveQuantiles
from .search import ParsedSearchText, SearchFragmentHit, SearchMatchMode


class JournalView(StrEnum):
    ALL = "all"
    UNRESOLVED = "unresolved"
    NEEDS_POSTMORTEM = "needs_postmortem"


RECENTLY_ACTIVE = "recently_active"


@dataclass(frozen=True, slots=True)
class JournalRequest:
    text: str = ""
    view: JournalView = JournalView.ALL
    filters: ArchiveQuery = field(default_factory=ArchiveQuery)
    match_mode: SearchMatchMode = SearchMatchMode.ALL
    include_history: bool = False
    manual_sort: ArchiveSort | str | None = None
    limit: int = 60

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not isinstance(self.view, JournalView):
            raise TypeError("The Journal request is invalid.")
        validate_archive_query(self.filters, text_active=bool(self.text.strip()))
        if self.filters.status is not None or self.filters.attention is not None:
            raise ValueError("Use the Journal quick views for its task scope.")
        if (
            not isinstance(self.match_mode, SearchMatchMode)
            or type(self.include_history) is not bool
        ):
            raise ValueError("The search options are invalid.")
        if self.manual_sort is not None and self.manual_sort != RECENTLY_ACTIVE:
            if not isinstance(self.manual_sort, ArchiveSort):
                raise ValueError("The Journal sort is invalid.")
            if self.manual_sort is ArchiveSort.RELEVANCE and not self.text.strip():
                raise ValueError("Relevance requires search text.")
        if type(self.limit) is not int or self.limit < 1:
            raise ValueError("The Journal loading limit is invalid.")

    @property
    def sort(self) -> ArchiveSort | str:
        return self.manual_sort or (
            ArchiveSort.RELEVANCE if self.text.strip() else RECENTLY_ACTIVE
        )

    @property
    def show_count(self) -> bool:
        return bool(
            self.text.strip()
            or self.filters != ArchiveQuery()
            or self.match_mode is not SearchMatchMode.ALL
            or self.include_history
        )


@dataclass(frozen=True, slots=True)
class JournalRow:
    prediction: PredictionBrowserItem
    last_active: datetime
    forecast_label: str
    probability_percent: int | None
    quantiles: FiveQuantiles | None
    actual: BinaryOutcome | FixedPrecisionValue | None = None
    contextual_label: str | None = None
    contextual_at: datetime | None = None
    excluded_later_forecast: bool = False
    correction_label: str | None = None
    matches: tuple[SearchFragmentHit, ...] = ()
    current_question_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class JournalPage:
    request: JournalRequest
    rows: tuple[JournalRow, ...]
    total: int
    available_tags: tuple[str, ...]
    parsed: ParsedSearchText
    suggestion: str | None = None

    @property
    def has_more(self) -> bool:
        return len(self.rows) < self.total
