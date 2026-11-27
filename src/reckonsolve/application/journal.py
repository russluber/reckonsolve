"""Assemble faithful Journal rows using shared lifecycle and scoring rules."""

from dataclasses import replace
from datetime import tzinfo

from reckonsolve.analytics.quantiles import resolved_quantile_scorecard
from reckonsolve.analytics.trajectory import trajectory_scorecard
from reckonsolve.clock import Clock, as_utc
from reckonsolve.data.database import Database
from reckonsolve.data.journal import (
    JournalPredictionMissingError,
    JournalRepository,
    JournalSource,
)
from reckonsolve.data.search_index import SearchIndexBusyError, SearchIndexError
from reckonsolve.domain.browser import (
    classify_archive_items,
    matches_archive_query,
    sort_archive_items,
)
from reckonsolve.domain.journal import (
    RECENTLY_ACTIVE,
    JournalPage,
    JournalRequest,
    JournalRow,
    JournalView,
)
from reckonsolve.domain.one_shot import OneShotSourceAction
from reckonsolve.domain.predictions import PredictionStatus
from reckonsolve.domain.search import (
    SearchFragmentHit,
    _fragment_rank_key,
    parse_search_text,
    rank_search_candidates,
)

from .errors import DatabaseBusyError, PredictionNotFoundError, SearchUnavailableError
from .read_errors import expected_database_read


class JournalOperations:
    def __init__(
        self, database: Database, clock: Clock, local_timezone: tzinfo | None = None
    ) -> None:
        self.repository = JournalRepository(database)
        self.database = database
        self.clock = clock
        self.local_timezone = local_timezone

    @expected_database_read
    def resolve_passage(self, identifier: int, document):
        try:
            return self.repository.resolve_passage(identifier, document)
        except JournalPredictionMissingError as error:
            raise PredictionNotFoundError(identifier) from error

    @expected_database_read
    def query_independently(self, request: JournalRequest) -> JournalPage:
        """Each background request owns its connection and never upgrades data."""
        reader = Database.open_readonly(
            self.database.path, migrations=self.database.migrations
        )
        try:
            return JournalOperations(reader, self.clock, self.local_timezone).query(
                request
            )
        finally:
            reader.close()

    @expected_database_read
    def query(self, request: JournalRequest) -> JournalPage:
        parsed = parse_search_text(request.text)
        now = as_utc(self.clock.now())
        try:
            source = self.repository.read(
                parsed, include_history=request.include_history
            )
        except SearchIndexBusyError as error:
            raise DatabaseBusyError(
                "The database is busy. Try again in a moment."
            ) from error
        except SearchIndexError as error:
            raise SearchUnavailableError(
                "The derived search projection needs repair before retrieving Journal results."
            ) from error
        items = classify_archive_items(
            source.browser.predictions,
            current_date=now.astimezone(self.local_timezone).date(),
            now=now,
        )
        items = tuple(
            item
            for item in items
            if (
                (
                    request.view is not JournalView.UNRESOLVED
                    or item.status in (PredictionStatus.OPEN, PredictionStatus.LOCKED)
                )
                and (
                    request.view is not JournalView.NEEDS_POSTMORTEM
                    or item.needs_postmortem
                )
                and matches_archive_query(
                    item,
                    request.filters,
                    now=now,
                    current_date=now.astimezone(self.local_timezone).date(),
                    stale_threshold_days=14,
                    local_timezone=self.local_timezone,
                )
            )
        )
        hits = ()
        if not parsed.is_blank:
            allowed = {item.prediction_id for item in items}
            hits = rank_search_candidates(
                parsed,
                request.match_mode,
                {
                    key: value
                    for key, value in source.search_predictions.items()
                    if key in allowed
                },
                source.candidates,
            )
            indexed = {item.prediction_id: item for item in items}
            items = tuple(indexed[hit.prediction.prediction_id] for hit in hits)
        total = len(items)
        if request.sort == RECENTLY_ACTIVE:
            items = tuple(
                sorted(
                    items,
                    key=lambda item: (
                        source.activity[item.prediction_id],
                        item.prediction_id,
                    ),
                    reverse=True,
                )
            )
        elif str(request.sort) != "relevance":
            items = sort_archive_items(items, request.sort)
        rows = self._rows(items[: request.limit], source)
        visible = {row.prediction.prediction_id for row in rows}
        fragments = {}
        for candidate in sorted(
            (
                candidate
                for candidate in source.candidates
                if candidate.document.prediction_id in visible
            ),
            key=_fragment_rank_key,
        ):
            fragments.setdefault(candidate.document.prediction_id, []).append(
                SearchFragmentHit(
                    candidate.document,
                    candidate.matched_clause_indexes,
                    candidate.literal_match,
                    candidate.exact_text_match,
                )
            )
        rows = tuple(
            replace(row, matches=tuple(fragments.get(row.prediction.prediction_id, ())))
            for row in rows
        )
        suggestion = None
        if not rows and not parsed.is_blank:
            try:
                suggestion = self.repository.suggest(
                    parsed, include_history=request.include_history
                )
            except SearchIndexBusyError as error:
                raise DatabaseBusyError(
                    "The database is busy. Try again in a moment."
                ) from error
            except SearchIndexError as error:
                raise SearchUnavailableError(
                    "The search projection needs repair before spelling assistance can complete."
                ) from error
        return JournalPage(request, rows, total, source.tags, parsed, suggestion)

    @staticmethod
    def _rows(items, source: JournalSource) -> tuple[JournalRow, ...]:
        binary = {
            record.revisions[0].prediction_id: record
            for record in source.trajectory.records
        }
        numeric = {
            record.revisions[0].prediction_id: record
            for record in source.numeric.records
        }
        rows = []
        for item in items:
            identifier = item.prediction_id
            row = JournalRow(
                item,
                source.activity[identifier],
                "Committed forecast",
                item.probability_percent,
                item.numeric_quantiles,
                current_question_at=source.question_dates.get(identifier),
            )
            if item.forecast_contract.is_one_shot:
                record = source.one_shots[identifier]
                labels = set()
                for correction in record.corrections:
                    if (
                        correction.source_action
                        is not OneShotSourceAction.TRANSCRIPTION
                    ):
                        continue
                    before, after = correction.before, correction.after
                    if (before.probability_percent, before.quantiles) != (
                        after.probability_percent,
                        after.quantiles,
                    ):
                        labels.add("Forecast transcription corrected")
                    if before.answer != after.answer:
                        labels.add("Answer transcription corrected")
                    if (before.forecast_reported, before.reveal_reported) != (
                        after.forecast_reported,
                        after.reveal_reported,
                    ):
                        labels.add("Reported time corrected")
                row = replace(
                    row,
                    forecast_label="Saved forecast",
                    actual=record.effective.answer,
                    correction_label=" · ".join(sorted(labels)) or None,
                )
            elif item.status is PredictionStatus.RESOLVED:
                record = binary.get(identifier) or numeric[identifier]
                effective = record.resolution_history.effective
                if identifier in binary:
                    card = trajectory_scorecard(
                        record.contract, record.revisions, record.resolution_history
                    )
                    probability = (
                        card.segments[-1].probability_percent if card.segments else None
                    )
                    quantiles = None
                    actual = effective.outcome
                    eligible = bool(card.segments)
                else:
                    card = resolved_quantile_scorecard(
                        record.contract,
                        record.definition,
                        record.revisions,
                        record.resolution_history,
                    )
                    probability = None
                    quantiles = (
                        card.scoring_revision.quantiles
                        if card.scoring_revision
                        else None
                    )
                    actual = effective.actual_value
                    eligible = card.scoring_revision is not None
                row = replace(
                    row,
                    probability_percent=probability,
                    quantiles=quantiles,
                    actual=actual,
                    forecast_label="Last scoring-eligible forecast"
                    if eligible
                    else "Unscored · No eligible forecast",
                    excluded_later_forecast=eligible
                    and bool(card.excluded_revision_ids),
                    contextual_label="Outcome known",
                    contextual_at=effective.effective_resolution_at,
                )
            elif item.status is PredictionStatus.INVALID:
                row = replace(
                    row,
                    forecast_label="Last forecast · Not scored",
                    contextual_label="Invalidated",
                    contextual_at=item.terminal_decision_at,
                )
            elif item.forecast_contract.forecast_deadline:
                row = replace(
                    row,
                    contextual_label="Forecast Deadline",
                    contextual_at=item.forecast_contract.forecast_deadline.instant,
                )
            if (
                item.forecast_contract.is_one_shot
                and item.status is PredictionStatus.INVALID
            ):
                row = replace(
                    row, forecast_label="Last forecast · Not scored", actual=None
                )
            rows.append(row)
        return tuple(rows)
