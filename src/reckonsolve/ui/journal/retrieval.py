"""Journal binding for the shared coalesced read coordinator."""

from reckonsolve.domain.journal import JournalPage, JournalRequest
from reckonsolve.ui.read_requests import ReadRequests


class JournalRetrieval(ReadRequests[JournalRequest, JournalPage]):
    pass
