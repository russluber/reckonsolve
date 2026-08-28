"""Domain values for deliberate global tag-library maintenance."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TagLibraryItem:
    """One retained reusable tag and its current relationship counts."""

    tag_id: int
    display_name: str
    normalized_name: str
    prediction_count: int
    saved_view_count: int


@dataclass(frozen=True, slots=True)
class TagManagementContext:
    """The exact tag relationships reviewed before a global mutation."""

    item: TagLibraryItem
    prediction_ids: tuple[int, ...]
    saved_view_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class TagRenamePreview:
    """A validated rename plus the exact state shown for confirmation."""

    context: TagManagementContext
    proposed_display_name: str
    proposed_normalized_name: str

    @property
    def prediction_count(self) -> int:
        return len(self.context.prediction_ids)


@dataclass(frozen=True, slots=True)
class TagMergePreview:
    """A validated many-to-one merge plus its reviewed relationship state."""

    source_contexts: tuple[TagManagementContext, ...]
    target_context: TagManagementContext
    affected_prediction_ids: tuple[int, ...]
    affected_saved_view_ids: tuple[int, ...]

    @property
    def source_tags(self) -> tuple[TagLibraryItem, ...]:
        return tuple(context.item for context in self.source_contexts)

    @property
    def target_tag(self) -> TagLibraryItem:
        return self.target_context.item

    @property
    def prediction_count(self) -> int:
        return len(self.affected_prediction_ids)

    @property
    def saved_view_count(self) -> int:
        return len(self.affected_saved_view_ids)


@dataclass(frozen=True, slots=True)
class TagDeletePreview:
    """A retained tag and every relationship its deletion will remove."""

    context: TagManagementContext

    @property
    def tag(self) -> TagLibraryItem:
        return self.context.item

    @property
    def prediction_count(self) -> int:
        return len(self.context.prediction_ids)

    @property
    def saved_view_count(self) -> int:
        return len(self.context.saved_view_ids)
