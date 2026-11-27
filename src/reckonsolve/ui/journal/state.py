"""Applied retrieval state, separate from an uncommitted Filters dialog."""

from dataclasses import dataclass, field, replace

from reckonsolve.domain.browser import ArchiveSort
from reckonsolve.domain.journal import JournalRequest


@dataclass(slots=True)
class JournalState:
    request: JournalRequest = field(default_factory=JournalRequest)
    anchor: tuple[tuple[int, int], ...] = ()
    scroll_offset: int = 0

    def change(self, **changes) -> None:
        if (
            "text" in changes
            and not changes["text"].strip()
            and self.request.manual_sort is ArchiveSort.RELEVANCE
        ):
            changes.setdefault("manual_sort", None)
        changes.setdefault("limit", 60)
        self.request = replace(self.request, **changes)
        self.anchor = ()
        self.scroll_offset = 0

    def reset(self) -> None:
        self.request = JournalRequest()
        self.anchor = ()
        self.scroll_offset = 0
