"""Merge anchored history without treating event kinds as chronological blocks."""

from collections import deque
from collections.abc import Callable, Iterable
from itertools import groupby

from .predictions import NumericTimelineEvent, TimelineEvent
from .quantiles import QuantileTimelineEvent


def order_timeline[T: TimelineEvent | NumericTimelineEvent | QuantileTimelineEvent](
    events: Iterable[T], *, key: Callable[[T], tuple[int, int, int]]
) -> tuple[T, ...]:
    """Preserve revision anchors and per-kind save order, merging by exact time.

    Keys contain revision sequence, kind (forecast=0, journal=1, review=2),
    and stable identifier. A regressed clock cannot move a Journal before its
    anchor or reverse same-kind insertion order. Across kinds, timestamps choose
    the next available event; ties use kind and identifier deterministically.
    """
    ordered: list[T] = []
    for _, anchored in groupby(sorted(events, key=key), lambda event: key(event)[0]):
        streams = {
            kind: deque(group)
            for kind, group in groupby(anchored, lambda event: key(event)[1])
        }
        ordered.extend(streams.pop(0, ()))
        while streams:
            kind = min(
                streams,
                key=lambda kind: (streams[kind][0].created_at, key(streams[kind][0])),
            )
            ordered.append(streams[kind].popleft())
            if not streams[kind]:
                del streams[kind]
    return tuple(ordered)
