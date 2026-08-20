from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

import pytest
from PySide6.QtCore import QDate, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStackedWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from reckonsolve.application.errors import (
    ApplicationError,
    ConcurrentPredictionUpdateError,
    MeaningChangeConfirmationRequired,
)
from reckonsolve.domain.attention import DashboardPrediction, DashboardSnapshot
from reckonsolve.domain.browser import (
    PredictionBrowserItem,
    PredictionBrowserSnapshot,
)
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    DefinitionChange,
    PredictionStatus,
)
from reckonsolve.ui import MainWindow
from reckonsolve.ui.probability_history_chart import ProbabilityHistoryChart

EXPECTED_SCREEN_NAMES = (
    "Dashboard",
    "New Prediction",
    "Prediction Detail",
    "Predictions",
    "Analytics",
    "Settings",
)


@dataclass(frozen=True, slots=True)
class FakeResolution:
    resolution_id: int
    prediction_id: int
    outcome: BinaryOutcome
    resolved_at: datetime
    scoring_revision_id: int
    scoring_revision_sequence: int
    scoring_probability_percent: int
    resolution_notes: str | None = None
    postmortem: str | None = None


@dataclass(frozen=True, slots=True)
class FakeInvalidation:
    invalidation_id: int
    prediction_id: int
    invalidated_at: datetime
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class FakePrediction:
    prediction_id: int
    question: str
    probability_percent: int
    status: PredictionStatus = PredictionStatus.OPEN
    created_at: datetime = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    background: str | None = None
    resolution_criteria: str | None = None
    forecast_deadline: date | None = None
    expected_resolution: date | None = None
    tags: tuple[str, ...] = ()
    updated_at: datetime | None = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    metadata_version: int = 1
    current_revision_id: int = 1
    current_revision_sequence: int = 1
    current_rationale: str | None = None
    resolution: FakeResolution | None = None
    invalidation: FakeInvalidation | None = None
    deletion_allowed: bool = True


@dataclass(frozen=True, slots=True)
class FakeForecastRevision:
    revision_id: int
    prediction_id: int
    probability_percent: int
    sequence: int
    created_at: datetime
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class FakeJournalCorrection:
    correction_id: int
    body: str
    corrected_at: datetime


@dataclass(frozen=True, slots=True)
class FakeForecastTimelineEvent:
    revision_id: int
    prediction_id: int
    created_at: datetime
    sequence: int
    probability_percent: int
    previous_probability_percent: int | None
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class FakeJournalTimelineEvent:
    entry_id: int
    prediction_id: int
    created_at: datetime
    body: str
    original_body: str
    forecast_revision_id: int
    forecast_revision_sequence: int
    forecast_probability_percent: int
    current_correction_id: int | None = None
    corrections: tuple[FakeJournalCorrection, ...] = ()


@dataclass(frozen=True, slots=True)
class CreatePredictionCall:
    question: str
    probability_percent: int
    rationale: str | None
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ReviseForecastCall:
    prediction_id: int
    probability_percent: int
    rationale: str | None
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class AddJournalEntryCall:
    prediction_id: int
    body: str
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class CorrectJournalEntryCall:
    prediction_id: int
    entry_id: int
    body: str
    expected_correction_id: int | None


@dataclass(frozen=True, slots=True)
class MetadataUpdateCall:
    prediction_id: int
    question: str
    background: str | None
    resolution_criteria: str | None
    forecast_deadline: date | None
    expected_resolution: date | None
    tags: tuple[str, ...]
    expected_metadata_version: int
    confirm_meaning_change: bool


@dataclass(frozen=True, slots=True)
class ResolvePredictionCall:
    prediction_id: int
    outcome: BinaryOutcome
    resolution_notes: str | None
    postmortem: str | None
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class InvalidatePredictionCall:
    prediction_id: int
    reason: str | None
    expected_revision_id: int
    expected_metadata_version: int


@dataclass(frozen=True, slots=True)
class DeletePredictionCall:
    prediction_id: int
    expected_revision_id: int
    expected_metadata_version: int
    confirm_permanent_deletion: bool


class FakePredictionOperations:
    def __init__(self, latest: FakePrediction | None = None) -> None:
        self.latest = latest
        self.create_calls: list[CreatePredictionCall] = []
        self.create_error: ApplicationError | None = None
        self.revise_calls: list[ReviseForecastCall] = []
        self.revise_error: ApplicationError | None = None
        self.revisions: list[FakeForecastRevision] = []
        self.revision_read_calls: list[int] = []
        self.revision_read_error: ApplicationError | None = None
        if latest is not None:
            self.revisions.append(
                FakeForecastRevision(
                    revision_id=latest.current_revision_id,
                    prediction_id=latest.prediction_id,
                    probability_percent=latest.probability_percent,
                    sequence=latest.current_revision_sequence,
                    created_at=latest.created_at,
                    rationale=latest.current_rationale,
                )
            )
        self.journal_calls: list[AddJournalEntryCall] = []
        self.journal_error: ApplicationError | None = None
        self.journal_entries: list[FakeJournalTimelineEvent] = []
        self.correction_calls: list[CorrectJournalEntryCall] = []
        self.correction_error: ApplicationError | None = None
        self.timeline_error: ApplicationError | None = None
        self.get_calls: list[int] = []
        self.update_calls: list[MetadataUpdateCall] = []
        self.update_error: ApplicationError | None = None
        self.confirmation_fields: tuple[str, ...] | None = None
        self.definition_changes: tuple[DefinitionChange, ...] = ()
        self.definition_change_error: ApplicationError | None = None
        self.definition_change_calls: list[int] = []
        self.resolve_calls: list[ResolvePredictionCall] = []
        self.resolve_error: ApplicationError | None = None
        self.invalidate_calls: list[InvalidatePredictionCall] = []
        self.invalidate_error: ApplicationError | None = None
        self.delete_calls: list[DeletePredictionCall] = []
        self.delete_error: ApplicationError | None = None
        self.dashboard_snapshot: DashboardSnapshot | None = None
        self.dashboard_error: ApplicationError | None = None
        self.dashboard_calls = 0
        self.browser_snapshot: PredictionBrowserSnapshot | None = None
        self.browser_error: ApplicationError | None = None
        self.browser_calls: list[tuple[str, PredictionStatus | None, str | None]] = []
        self.stale_threshold_days = 14
        self.threshold_get_calls = 0
        self.threshold_set_calls: list[int] = []
        self.threshold_error: ApplicationError | None = None
        self.mutation_count = 0

    def create_prediction(
        self,
        question: str,
        probability_percent: int,
        *,
        rationale: str | None = None,
        background: str | None = None,
        resolution_criteria: str | None = None,
        forecast_deadline: date | None = None,
        expected_resolution: date | None = None,
        tags: tuple[str, ...] = (),
    ) -> FakePrediction:
        self.create_calls.append(
            CreatePredictionCall(
                question=question,
                probability_percent=probability_percent,
                rationale=rationale,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
            )
        )
        if self.create_error is not None:
            raise self.create_error
        prediction = FakePrediction(
            prediction_id=1,
            question=question,
            probability_percent=probability_percent,
            current_rationale=(rationale or "").strip() or None,
            background=(background or "").strip() or None,
            resolution_criteria=(resolution_criteria or "").strip() or None,
            forecast_deadline=forecast_deadline,
            expected_resolution=expected_resolution,
            tags=tags,
        )
        self.latest = prediction
        self.revisions = [
            FakeForecastRevision(
                revision_id=1,
                prediction_id=1,
                probability_percent=probability_percent,
                sequence=1,
                created_at=prediction.created_at,
                rationale=prediction.current_rationale,
            )
        ]
        return prediction

    def revise_forecast(
        self,
        prediction_id: int,
        probability_percent: int,
        *,
        rationale: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakePrediction:
        self.revise_calls.append(
            ReviseForecastCall(
                prediction_id=prediction_id,
                probability_percent=probability_percent,
                rationale=rationale,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.revise_error is not None:
            raise self.revise_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        new_revision_id = self.latest.current_revision_id + 1
        new_sequence = self.latest.current_revision_sequence + 1
        normalized_rationale = (rationale or "").strip() or None
        self.latest = replace(
            self.latest,
            probability_percent=probability_percent,
            current_revision_id=new_revision_id,
            current_revision_sequence=new_sequence,
            current_rationale=normalized_rationale,
            deletion_allowed=False,
        )
        self.revisions.append(
            FakeForecastRevision(
                revision_id=new_revision_id,
                prediction_id=prediction_id,
                probability_percent=probability_percent,
                sequence=new_sequence,
                created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
                rationale=normalized_rationale,
            )
        )
        return self.latest

    def list_forecast_revisions(
        self,
        prediction_id: int,
    ) -> tuple[FakeForecastRevision, ...]:
        self.revision_read_calls.append(prediction_id)
        if self.revision_read_error is not None:
            raise self.revision_read_error
        return tuple(
            revision
            for revision in self.revisions
            if revision.prediction_id == prediction_id
        )

    def add_journal_entry(
        self,
        prediction_id: int,
        body: str,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakeJournalTimelineEvent:
        self.journal_calls.append(
            AddJournalEntryCall(
                prediction_id=prediction_id,
                body=body,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.journal_error is not None:
            raise self.journal_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        entry = FakeJournalTimelineEvent(
            entry_id=len(self.journal_entries) + 1,
            prediction_id=prediction_id,
            created_at=datetime(2026, 8, 14, 19, 30, tzinfo=UTC),
            body=body.strip(),
            original_body=body.strip(),
            forecast_revision_id=self.latest.current_revision_id,
            forecast_revision_sequence=self.latest.current_revision_sequence,
            forecast_probability_percent=self.latest.probability_percent,
        )
        self.journal_entries.append(entry)
        self.latest = replace(self.latest, deletion_allowed=False)
        return entry

    def correct_journal_entry(
        self,
        prediction_id: int,
        entry_id: int,
        body: str,
        *,
        expected_correction_id: int | None,
    ) -> FakeJournalTimelineEvent:
        self.correction_calls.append(
            CorrectJournalEntryCall(
                prediction_id=prediction_id,
                entry_id=entry_id,
                body=body,
                expected_correction_id=expected_correction_id,
            )
        )
        if self.correction_error is not None:
            raise self.correction_error
        for index, entry in enumerate(self.journal_entries):
            if entry.prediction_id == prediction_id and entry.entry_id == entry_id:
                correction_id = (
                    sum(len(existing.corrections) for existing in self.journal_entries)
                    + 1
                )
                correction = FakeJournalCorrection(
                    correction_id=correction_id,
                    body=body.strip(),
                    corrected_at=datetime(2026, 8, 15, 19, 30, tzinfo=UTC),
                )
                updated = replace(
                    entry,
                    body=correction.body,
                    current_correction_id=correction_id,
                    corrections=(*entry.corrections, correction),
                )
                self.journal_entries[index] = updated
                return updated
        raise ApplicationError("Journal entry not found.")

    def resolve_prediction(
        self,
        prediction_id: int,
        outcome: BinaryOutcome,
        *,
        resolution_notes: str | None = None,
        postmortem: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakePrediction:
        self.resolve_calls.append(
            ResolvePredictionCall(
                prediction_id=prediction_id,
                outcome=outcome,
                resolution_notes=resolution_notes,
                postmortem=postmortem,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.resolve_error is not None:
            raise self.resolve_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        resolution = FakeResolution(
            resolution_id=1,
            prediction_id=prediction_id,
            outcome=outcome,
            resolved_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            scoring_revision_id=self.latest.current_revision_id,
            scoring_revision_sequence=self.latest.current_revision_sequence,
            scoring_probability_percent=self.latest.probability_percent,
            resolution_notes=(resolution_notes or "").strip() or None,
            postmortem=(postmortem or "").strip() or None,
        )
        self.latest = replace(
            self.latest,
            status=PredictionStatus.RESOLVED,
            resolution=resolution,
            deletion_allowed=False,
        )
        return self.latest

    def invalidate_prediction(
        self,
        prediction_id: int,
        *,
        reason: str | None = None,
        expected_revision_id: int,
        expected_metadata_version: int,
    ) -> FakePrediction:
        self.invalidate_calls.append(
            InvalidatePredictionCall(
                prediction_id=prediction_id,
                reason=reason,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
            )
        )
        if self.invalidate_error is not None:
            raise self.invalidate_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        invalidation = FakeInvalidation(
            invalidation_id=1,
            prediction_id=prediction_id,
            invalidated_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            reason=(reason or "").strip() or None,
        )
        self.latest = replace(
            self.latest,
            status=PredictionStatus.INVALID,
            invalidation=invalidation,
            deletion_allowed=False,
        )
        return self.latest

    def delete_prediction(
        self,
        prediction_id: int,
        *,
        expected_revision_id: int,
        expected_metadata_version: int,
        confirm_permanent_deletion: bool = False,
    ) -> FakePrediction | None:
        self.delete_calls.append(
            DeletePredictionCall(
                prediction_id=prediction_id,
                expected_revision_id=expected_revision_id,
                expected_metadata_version=expected_metadata_version,
                confirm_permanent_deletion=confirm_permanent_deletion,
            )
        )
        if self.delete_error is not None:
            raise self.delete_error
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        self.revisions = [
            item for item in self.revisions if item.prediction_id != prediction_id
        ]
        self.journal_entries = [
            item for item in self.journal_entries if item.prediction_id != prediction_id
        ]
        self.latest = None
        return None

    def list_timeline(
        self,
        prediction_id: int,
    ) -> tuple[FakeForecastTimelineEvent | FakeJournalTimelineEvent, ...]:
        if self.timeline_error is not None:
            raise self.timeline_error
        revisions = [
            revision
            for revision in self.revisions
            if revision.prediction_id == prediction_id
        ]
        forecast_events: list[FakeForecastTimelineEvent] = []
        previous_probability: int | None = None
        for revision in revisions:
            forecast_events.append(
                FakeForecastTimelineEvent(
                    revision_id=revision.revision_id,
                    prediction_id=revision.prediction_id,
                    created_at=revision.created_at,
                    sequence=revision.sequence,
                    probability_percent=revision.probability_percent,
                    previous_probability_percent=previous_probability,
                    rationale=revision.rationale,
                )
            )
            previous_probability = revision.probability_percent
        journal_events = [
            entry
            for entry in self.journal_entries
            if entry.prediction_id == prediction_id
        ]
        events: list[FakeForecastTimelineEvent | FakeJournalTimelineEvent] = [
            *forecast_events,
            *journal_events,
        ]
        return tuple(
            sorted(
                events,
                key=lambda event: (
                    event.forecast_revision_sequence
                    if isinstance(event, FakeJournalTimelineEvent)
                    else event.sequence,
                    1 if isinstance(event, FakeJournalTimelineEvent) else 0,
                    event.created_at,
                    event.entry_id
                    if isinstance(event, FakeJournalTimelineEvent)
                    else event.revision_id,
                ),
            )
        )

    def get_latest_prediction(self) -> FakePrediction | None:
        return self.latest

    def get_prediction(self, prediction_id: int) -> FakePrediction:
        self.get_calls.append(prediction_id)
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        return self.latest

    def update_metadata(
        self,
        prediction_id: int,
        *,
        question: str,
        background: str | None,
        resolution_criteria: str | None,
        forecast_deadline: date | None,
        expected_resolution: date | None,
        tags: tuple[str, ...],
        expected_metadata_version: int,
        confirm_meaning_change: bool = False,
    ) -> FakePrediction:
        self.update_calls.append(
            MetadataUpdateCall(
                prediction_id=prediction_id,
                question=question,
                background=background,
                resolution_criteria=resolution_criteria,
                forecast_deadline=forecast_deadline,
                expected_resolution=expected_resolution,
                tags=tags,
                expected_metadata_version=expected_metadata_version,
                confirm_meaning_change=confirm_meaning_change,
            )
        )
        if self.update_error is not None:
            raise self.update_error
        if self.confirmation_fields is not None and not confirm_meaning_change:
            raise MeaningChangeConfirmationRequired(self.confirmation_fields)
        if self.latest is None or self.latest.prediction_id != prediction_id:
            raise ApplicationError("Prediction not found.")
        if self.latest.metadata_version != expected_metadata_version:
            raise ConcurrentPredictionUpdateError(prediction_id)
        updated = replace(
            self.latest,
            question=question.strip(),
            background=(background or "").strip() or None,
            resolution_criteria=(resolution_criteria or "").strip() or None,
            forecast_deadline=forecast_deadline,
            expected_resolution=expected_resolution,
            tags=tags,
        )
        if updated != self.latest:
            self.mutation_count += 1
            updated = replace(
                updated,
                metadata_version=self.latest.metadata_version + 1,
                deletion_allowed=False,
            )
        self.latest = updated
        return self.latest

    def list_definition_changes(
        self,
        prediction_id: int,
    ) -> tuple[DefinitionChange, ...]:
        self.definition_change_calls.append(prediction_id)
        if self.definition_change_error is not None:
            raise self.definition_change_error
        return self.definition_changes

    def get_dashboard(self) -> DashboardSnapshot:
        self.dashboard_calls += 1
        if self.dashboard_error is not None:
            raise self.dashboard_error
        if self.dashboard_snapshot is not None:
            return self.dashboard_snapshot
        if self.latest is None or self.latest.status in (
            PredictionStatus.RESOLVED,
            PredictionStatus.INVALID,
        ):
            open_predictions: tuple[DashboardPrediction, ...] = ()
            locked_predictions: tuple[DashboardPrediction, ...] = ()
        else:
            prediction = DashboardPrediction(
                prediction_id=self.latest.prediction_id,
                question=self.latest.question,
                probability_percent=self.latest.probability_percent,
                status=self.latest.status,
                latest_revision_at=self.latest.created_at,
                forecast_deadline=self.latest.forecast_deadline,
                expected_resolution=self.latest.expected_resolution,
            )
            open_predictions = (
                (prediction,) if self.latest.status is PredictionStatus.OPEN else ()
            )
            locked_predictions = (
                (prediction,) if self.latest.status is PredictionStatus.LOCKED else ()
            )
        return DashboardSnapshot(
            stale_threshold_days=self.stale_threshold_days,
            open_predictions=open_predictions,
            needs_attention_predictions=(),
            ready_to_resolve_predictions=(),
            locked_predictions=locked_predictions,
        )

    def browse_predictions(
        self,
        question_text: str = "",
        *,
        status: PredictionStatus | None = None,
        tag: str | None = None,
    ) -> PredictionBrowserSnapshot:
        self.browser_calls.append((question_text, status, tag))
        if self.browser_error is not None:
            raise self.browser_error
        if self.browser_snapshot is not None:
            source = self.browser_snapshot
        elif self.latest is None:
            source = PredictionBrowserSnapshot(predictions=(), available_tags=())
        else:
            source = PredictionBrowserSnapshot(
                predictions=(
                    PredictionBrowserItem(
                        prediction_id=self.latest.prediction_id,
                        question=self.latest.question,
                        probability_percent=self.latest.probability_percent,
                        status=self.latest.status,
                        created_at=self.latest.created_at,
                        latest_revision_at=self.latest.created_at,
                        forecast_deadline=self.latest.forecast_deadline,
                        tags=self.latest.tags,
                    ),
                ),
                available_tags=tuple(
                    sorted(self.latest.tags, key=lambda item: item.casefold())
                ),
            )
        search_key = question_text.strip().casefold()
        tag_key = None if tag is None else tag.casefold()
        return replace(
            source,
            predictions=tuple(
                prediction
                for prediction in source.predictions
                if (not search_key or search_key in prediction.question.casefold())
                and (status is None or prediction.status is status)
                and (
                    tag_key is None
                    or tag_key in {item.casefold() for item in prediction.tags}
                )
            ),
        )

    def get_stale_threshold_days(self) -> int:
        self.threshold_get_calls += 1
        if self.threshold_error is not None:
            raise self.threshold_error
        return self.stale_threshold_days

    def set_stale_threshold_days(self, value: int) -> int:
        self.threshold_set_calls.append(value)
        if self.threshold_error is not None:
            raise self.threshold_error
        self.stale_threshold_days = value
        return value


@pytest.fixture
def operations() -> FakePredictionOperations:
    return FakePredictionOperations()


@pytest.fixture
def window(
    qtbot: QtBot,
    operations: FakePredictionOperations,
) -> MainWindow:
    main_window = MainWindow(operations)
    qtbot.addWidget(main_window)
    return main_window


def test_main_window_has_expected_navigation(window: MainWindow) -> None:
    navigation = _required_child(window, QListWidget, "primaryNavigation")

    assert window.windowTitle() == "Reckonsolve"
    assert window.screen_names == EXPECTED_SCREEN_NAMES
    assert (
        tuple(navigation.item(index).text() for index in range(navigation.count()))
        == EXPECTED_SCREEN_NAMES
    )
    assert window.current_screen_name == "Dashboard"
    assert navigation.currentRow() == 0


def test_main_window_navigates_to_each_primary_screen(window: MainWindow) -> None:
    screen_stack = _required_child(window, QStackedWidget, "screenStack")

    for expected_index, screen_name in enumerate(EXPECTED_SCREEN_NAMES):
        window.navigate_to(screen_name)

        assert window.current_screen_name == screen_name
        assert screen_stack.currentIndex() == expected_index


def test_unimplemented_screens_remain_honest_placeholders(window: MainWindow) -> None:
    placeholder_screens = ("Analytics",)

    for screen_name in placeholder_screens:
        window.navigate_to(screen_name)
        placeholder = _required_child(
            window,
            QLabel,
            f"{_object_name_prefix(screen_name)}ScreenPlaceholder",
        )

        assert any(word in placeholder.text() for word in ("coming", "will"))


def test_prediction_browser_renders_all_results_and_filter_choices(
    qtbot: QtBot,
) -> None:
    first = PredictionBrowserItem(
        prediction_id=1,
        question="Will the archive remain calm?",
        probability_percent=35,
        status=PredictionStatus.OPEN,
        created_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
        tags=("Work",),
    )
    second = PredictionBrowserItem(
        prediction_id=2,
        question="<b>Will literal markup stay literal?</b>",
        probability_percent=80,
        status=PredictionStatus.RESOLVED,
        created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 20, 20, 30, tzinfo=UTC),
        tags=("Personal", "Work"),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(second, first),
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    window.navigate_to("Predictions")

    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    tag_filter = _required_child(window, QComboBox, "predictionTagFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert [
        status_filter.itemText(index) for index in range(status_filter.count())
    ] == [
        "All",
        "Open",
        "Locked",
        "Resolved",
        "Invalid",
    ]
    assert [tag_filter.itemText(index) for index in range(tag_filter.count())] == [
        "All tags",
        "Personal",
        "Work",
    ]
    assert results.count() == 2
    assert "<b>Will literal markup stay literal?</b>" in results.item(0).text()
    assert "80%  |  RESOLVED" in results.item(0).text()
    assert "Tags: Personal, Work" in results.item(0).text()
    assert _required_child(window, QLabel, "predictionBrowserResultCount").text() == (
        "2 predictions"
    )


def test_prediction_browser_combines_filters_and_clear_restores_archive(
    qtbot: QtBot,
) -> None:
    items = (
        PredictionBrowserItem(
            prediction_id=3,
            question="Will policy pass this year?",
            probability_percent=70,
            status=PredictionStatus.RESOLVED,
            created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            tags=("Work",),
        ),
        PredictionBrowserItem(
            prediction_id=2,
            question="Will policy pass next year?",
            probability_percent=40,
            status=PredictionStatus.OPEN,
            created_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
            tags=("Work",),
        ),
        PredictionBrowserItem(
            prediction_id=1,
            question="Will another issue resolve?",
            probability_percent=20,
            status=PredictionStatus.RESOLVED,
            created_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
            latest_revision_at=datetime(2026, 8, 18, 19, 30, tzinfo=UTC),
            tags=("Personal",),
        ),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=items,
        available_tags=("Personal", "Work"),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    status_filter = _required_child(window, QComboBox, "predictionStatusFilter")
    tag_filter = _required_child(window, QComboBox, "predictionTagFilter")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    search.setText("THIS YEAR")
    status_filter.setCurrentIndex(status_filter.findData("resolved"))
    tag_filter.setCurrentIndex(tag_filter.findData("Work"))
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert results.count() == 1
    assert "Will policy pass this year?" in results.item(0).text()
    assert operations.browser_calls[-1] == (
        "THIS YEAR",
        PredictionStatus.RESOLVED,
        "Work",
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "clearPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    assert search.text() == ""
    assert status_filter.currentData() is None
    assert tag_filter.currentData() is None
    assert results.count() == 3
    assert operations.browser_calls[-1] == ("", None, None)


def test_prediction_browser_clears_a_filter_when_its_last_tag_is_removed(
    qtbot: QtBot,
) -> None:
    tagged = PredictionBrowserItem(
        prediction_id=1,
        question="Will an external edit remove this tag?",
        probability_percent=50,
        status=PredictionStatus.OPEN,
        created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        tags=("Temporary",),
    )
    operations = FakePredictionOperations()
    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(tagged,),
        available_tags=("Temporary",),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    tag_filter = _required_child(window, QComboBox, "predictionTagFilter")
    tag_filter.setCurrentIndex(tag_filter.findData("Temporary"))

    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(replace(tagged, tags=()),),
        available_tags=(),
    )
    qtbot.mouseClick(
        _required_child(window, QPushButton, "applyPredictionFiltersButton"),
        Qt.MouseButton.LeftButton,
    )

    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert tag_filter.currentData() is None
    assert results.count() == 1
    assert operations.browser_calls[-2:] == [
        ("", None, "Temporary"),
        ("", None, None),
    ]


def test_prediction_browser_distinguishes_new_database_and_no_matches(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    empty = _required_child(window, QLabel, "predictionBrowserEmpty")

    assert empty.text() == "No predictions yet. Create one from New Prediction."

    operations.browser_snapshot = PredictionBrowserSnapshot(
        predictions=(
            PredictionBrowserItem(
                prediction_id=1,
                question="Will something happen?",
                probability_percent=50,
                status=PredictionStatus.OPEN,
                created_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
                latest_revision_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
            ),
        ),
        available_tags=(),
    )
    search = _required_child(window, QLineEdit, "predictionSearchInput")
    search.setText("absent")
    qtbot.keyPress(search, Qt.Key.Key_Return)

    assert empty.text() == "No predictions match the current search and filters."
    assert _required_child(window, QListWidget, "predictionBrowserResults").isHidden()


def test_prediction_browser_opens_fresh_detail_from_keyboard_activation(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Open this from the Predictions archive",
        62,
        tags=("Archive",),
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    results.itemActivated.emit(results.item(0))

    assert operations.get_calls[-1] == latest.prediction_id
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )


def test_prediction_browser_refreshes_and_reports_initial_or_stale_errors(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations()
    operations.browser_error = ApplicationError("Archive could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Predictions")
    error = _required_child(window, QLabel, "predictionBrowserError")
    results = _required_child(window, QListWidget, "predictionBrowserResults")

    assert error.text() == "Predictions unavailable. Archive could not be loaded."
    assert results.isHidden()

    operations.browser_error = None
    operations.latest = FakePrediction(9, "Appeared after retry", 48)
    window.navigate_to("New Prediction")
    window.navigate_to("Predictions")
    assert results.count() == 1
    operations.browser_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Predictions")

    assert error.text() == (
        "Predictions could not refresh; showing the last loaded results. "
        "Refresh failed."
    )
    assert not results.isHidden()
    assert "Appeared after retry" in results.item(0).text()


def test_prediction_browser_timer_runs_only_while_visible(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    timer = window.findChild(QTimer, "predictionBrowserRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    operations.latest = FakePrediction(10, "Appeared at the lock boundary", 33)
    timer.timeout.emit()
    results = _required_child(window, QListWidget, "predictionBrowserResults")
    assert "Appeared at the lock boundary" in results.item(0).text()

    window.navigate_to("New Prediction")
    assert not timer.isActive()


def test_dashboard_renders_overlapping_buckets_without_losing_classifications(
    qtbot: QtBot,
) -> None:
    open_prediction = DashboardPrediction(
        prediction_id=1,
        question="Fresh open forecast",
        probability_percent=45,
        status=PredictionStatus.OPEN,
        latest_revision_at=datetime(2026, 8, 19, 19, 30, tzinfo=UTC),
    )
    overlap = DashboardPrediction(
        prediction_id=7,
        question="<b>Literal locked forecast</b>",
        probability_percent=70,
        status=PredictionStatus.LOCKED,
        latest_revision_at=datetime(2026, 8, 1, 19, 30, tzinfo=UTC),
        forecast_deadline=date(2026, 8, 10),
        expected_resolution=date(2026, 8, 15),
        needs_attention=True,
        ready_to_resolve=True,
    )
    operations = FakePredictionOperations()
    operations.dashboard_snapshot = DashboardSnapshot(
        stale_threshold_days=14,
        open_predictions=(open_prediction,),
        needs_attention_predictions=(overlap,),
        ready_to_resolve_predictions=(overlap,),
        locked_predictions=(overlap,),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QGroupBox, "dashboardOpenSection").title() == (
        "Open (1)"
    )
    assert (
        _required_child(
            window,
            QGroupBox,
            "dashboardNeedsAttentionSection",
        ).title()
        == "Needs Attention (1)"
    )
    assert (
        _required_child(
            window,
            QGroupBox,
            "dashboardReadyToResolveSection",
        ).title()
        == "Ready to Resolve (1)"
    )
    assert _required_child(window, QGroupBox, "dashboardLockedSection").title() == (
        "Locked (1)"
    )
    for object_name in (
        "dashboardNeedsAttentionPrediction7",
        "dashboardReadyToResolvePrediction7",
        "dashboardLockedPrediction7",
    ):
        row = _required_child(window, QPushButton, object_name)
        assert "<b>Literal locked forecast</b>" in row.text()
        assert "70%" in row.text()
        assert "needs attention" in row.accessibleDescription()
        assert "ready to resolve" in row.accessibleDescription()
    assert _required_child(window, QLabel, "dashboardThreshold").text() == (
        "Needs Attention threshold: 14 days"
    )


def test_dashboard_row_opens_fresh_prediction_detail(qtbot: QtBot) -> None:
    latest = FakePrediction(7, "Open this from Dashboard", 55)
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)

    row = _required_child(window, QPushButton, "dashboardOpenPrediction7")
    qtbot.mouseClick(row, Qt.MouseButton.LeftButton)

    assert operations.get_calls[-1] == 7
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )


def test_dashboard_refreshes_when_reentered(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    initial_calls = operations.dashboard_calls
    first_empty = _required_child(window, QLabel, "dashboardOpenEmpty")
    assert first_empty.text() == "No open predictions."

    operations.latest = FakePrediction(8, "Appeared while away", 35)
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")

    assert operations.dashboard_calls == initial_calls + 1
    assert (
        "Appeared while away"
        in _required_child(
            window,
            QPushButton,
            "dashboardOpenPrediction8",
        ).text()
    )


def test_dashboard_refresh_timer_runs_only_while_visible(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    timer = window.findChild(QTimer, "dashboardRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    operations.latest = FakePrediction(9, "Appeared at a time boundary", 48)
    timer.timeout.emit()
    assert (
        "Appeared at a time boundary"
        in _required_child(
            window,
            QPushButton,
            "dashboardOpenPrediction9",
        ).text()
    )

    window.navigate_to("New Prediction")
    assert not timer.isActive()
    window.navigate_to("Dashboard")
    assert timer.isActive()


def test_settings_persists_threshold_and_refreshes_dashboard(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dashboard_calls = operations.dashboard_calls

    window.navigate_to("Settings")
    threshold = _required_child(window, QSpinBox, "staleThresholdInput")
    save = _required_child(window, QPushButton, "saveStaleThresholdButton")
    assert threshold.value() == 14
    assert threshold.minimum() == 1
    assert threshold.maximum() == 9999

    threshold.setValue(30)
    qtbot.mouseClick(save, Qt.MouseButton.LeftButton)

    assert operations.threshold_set_calls == [30]
    assert operations.stale_threshold_days == 30
    assert operations.dashboard_calls == dashboard_calls + 1
    assert _required_child(window, QLabel, "staleThresholdStatus").text() == (
        "Saved. Dashboard now uses 30 days."
    )
    window.navigate_to("Dashboard")
    assert _required_child(window, QLabel, "dashboardThreshold").text() == (
        "Needs Attention threshold: 30 days"
    )


def test_dashboard_and_settings_show_expected_read_errors(qtbot: QtBot) -> None:
    operations = FakePredictionOperations()
    operations.dashboard_error = ApplicationError("Dashboard could not be loaded.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    assert _required_child(window, QLabel, "dashboardError").text() == (
        "Dashboard unavailable. Dashboard could not be loaded."
    )
    assert _required_child(window, QWidget, "dashboardScrollArea").isHidden()

    operations.dashboard_error = None
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")
    operations.dashboard_error = ApplicationError("Refresh failed.")
    window.navigate_to("New Prediction")
    window.navigate_to("Dashboard")
    assert _required_child(window, QLabel, "dashboardError").text() == (
        "Dashboard could not refresh; showing the last loaded results. Refresh failed."
    )
    assert not _required_child(window, QWidget, "dashboardScrollArea").isHidden()

    operations.threshold_error = ApplicationError("Setting could not be loaded.")
    window.navigate_to("Settings")
    assert _required_child(window, QLabel, "staleThresholdStatus").text() == (
        "Setting could not be loaded."
    )
    assert not _required_child(window, QSpinBox, "staleThresholdInput").isEnabled()
    assert not _required_child(
        window,
        QPushButton,
        "saveStaleThresholdButton",
    ).isEnabled()


def test_new_prediction_form_has_integer_probability_bounds_and_focus(
    window: MainWindow,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    probability = _required_child(window, QSpinBox, "probabilityInput")

    assert window.focusWidget() is question
    assert probability.minimum() == 0
    assert probability.maximum() == 100
    assert probability.value() == 50
    assert probability.suffix() == "%"

    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details_content = _required_child(
        window,
        QWidget,
        "newPredictionMoreDetailsContent",
    )
    assert not more_details.isChecked()
    assert more_details_content.isHidden()


def test_more_details_date_controls_are_visually_unset_until_enabled(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).setChecked(True)
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline = _required_child(
        window,
        QDateEdit,
        "initialForecastDeadlineInput",
    )

    assert not deadline_toggle.isChecked()
    assert deadline.isHidden()
    qtbot.mouseClick(deadline_toggle, Qt.MouseButton.LeftButton)
    assert deadline.isVisible()
    assert deadline.date() == QDate.currentDate()


def test_complete_creation_submits_all_optional_details_once_and_resets(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will all initial details persist?"
    )
    _required_child(window, QSpinBox, "probabilityInput").setValue(73)
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "Initial evidence"
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "Relevant background"
    )
    _required_child(
        window,
        QPlainTextEdit,
        "initialResolutionCriteriaInput",
    ).setPlainText("A published result counts.")
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialForecastDeadlineInput").setDate(
        QDate(2026, 9, 1)
    )
    expected_toggle = _required_child(
        window,
        QCheckBox,
        "initialExpectedResolutionToggle",
    )
    expected_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialExpectedResolutionInput").setDate(
        QDate(2026, 9, 15)
    )
    _required_child(window, QLineEdit, "initialTagsInput").setText(" release, desktop ")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will all initial details persist?",
            probability_percent=73,
            rationale="Initial evidence",
            background="Relevant background",
            resolution_criteria="A published result counts.",
            forecast_deadline=date(2026, 9, 1),
            expected_resolution=date(2026, 9, 15),
            tags=("release", "desktop"),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
    assert (
        _required_child(window, QLabel, "forecastRevisionRationale1").text()
        == "Initial evidence"
    )

    window.navigate_to("New Prediction")
    assert _required_child(window, QLineEdit, "questionInput").text() == ""
    assert _required_child(window, QSpinBox, "probabilityInput").value() == 50
    assert (
        _required_child(window, QPlainTextEdit, "initialRationaleInput").toPlainText()
        == ""
    )
    assert not deadline_toggle.isChecked()
    assert _required_child(
        window,
        QDateEdit,
        "initialForecastDeadlineInput",
    ).isHidden()
    assert not expected_toggle.isChecked()
    assert _required_child(window, QLineEdit, "initialTagsInput").text() == ""
    assert not _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    ).isChecked()


def test_collapsing_more_details_preserves_entered_values_for_creation(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.navigate_to("New Prediction")
    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details.setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will collapsed details remain part of the prediction?"
    )
    _required_child(window, QPlainTextEdit, "initialBackgroundInput").setPlainText(
        "Keep this context"
    )
    more_details.setChecked(False)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.create_calls[0].background == "Keep this context"


def test_creation_failure_keeps_optional_details_for_correction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.create_error = ApplicationError(
        "Forecast Deadline cannot be before today."
    )
    window.navigate_to("New Prediction")
    more_details = _required_child(
        window,
        QGroupBox,
        "newPredictionMoreDetailsGroup",
    )
    more_details.setChecked(True)
    _required_child(window, QLineEdit, "questionInput").setText(
        "Will this invalid deadline remain editable?"
    )
    _required_child(window, QPlainTextEdit, "initialRationaleInput").setPlainText(
        "Keep me"
    )
    deadline_toggle = _required_child(
        window,
        QCheckBox,
        "initialForecastDeadlineToggle",
    )
    deadline_toggle.setChecked(True)
    _required_child(window, QDateEdit, "initialForecastDeadlineInput").setDate(
        QDate(2020, 1, 1)
    )

    qtbot.mouseClick(
        _required_child(window, QPushButton, "createPredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.current_screen_name == "New Prediction"
    assert more_details.isChecked()
    assert deadline_toggle.isChecked()
    assert (
        _required_child(window, QPlainTextEdit, "initialRationaleInput").toPlainText()
        == "Keep me"
    )
    error = _required_child(window, QLabel, "predictionFormError")
    assert "before today" in error.text()
    assert not error.isHidden()


def test_probability_shortcuts_are_exactly_ten_through_ninety(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    shortcuts = _required_child(window, QWidget, "probabilityShortcuts")
    probability = _required_child(window, QSpinBox, "probabilityInput")
    buttons = shortcuts.findChildren(QPushButton)

    assert tuple(button.text() for button in buttons) == tuple(
        str(value) for value in range(10, 100, 10)
    )
    for expected, button in zip(range(10, 100, 10), buttons, strict=True):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
        assert probability.value() == expected


@pytest.mark.parametrize("endpoint", [0, 100])
def test_probability_endpoint_note_only_appears_for_absolute_certainty(
    window: MainWindow,
    endpoint: int,
) -> None:
    probability = _required_child(window, QSpinBox, "probabilityInput")
    note = _required_child(window, QLabel, "probabilityEndpointNote")

    for ordinary_probability in (1, 50, 99):
        probability.setValue(ordinary_probability)
        assert note.isHidden()

    probability.setValue(endpoint)
    assert not note.isHidden()
    assert "absolute certainty" in note.text()


def test_missing_question_is_shown_inline_without_calling_operation(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.navigate_to("New Prediction")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert not error.isHidden()
    assert "Enter a question" in error.text()
    assert operations.create_calls == []
    assert window.current_screen_name == "New Prediction"


def test_expected_application_failure_is_shown_inline(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    operations.create_error = ApplicationError("That prediction could not be saved.")
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    error = _required_child(window, QLabel, "predictionFormError")
    question.setText("Will this remain on the form?")

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert error.text() == "That prediction could not be saved."
    assert not error.isHidden()
    assert question.text() == "Will this remain on the form?"
    assert window.current_screen_name == "New Prediction"


@pytest.mark.parametrize("probability_percent", [0, 50, 100])
def test_successful_creation_accepts_probability_bounds_and_opens_detail(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
    probability_percent: int,
) -> None:
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    probability = _required_child(window, QSpinBox, "probabilityInput")
    create_button = _required_child(window, QPushButton, "createPredictionButton")
    question.setText("  Will the UI preserve history?  ")
    probability.setValue(probability_percent)

    qtbot.mouseClick(create_button, Qt.MouseButton.LeftButton)

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will the UI preserve history?",
            probability_percent=probability_percent,
            rationale="",
            background="",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Will the UI preserve history?"
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        f"{probability_percent}%"
    )
    assert question.text() == ""
    assert probability.value() == 50


def test_enter_submits_new_prediction(
    qtbot: QtBot,
    window: MainWindow,
    operations: FakePredictionOperations,
) -> None:
    window.show()
    window.navigate_to("New Prediction")
    question = _required_child(window, QLineEdit, "questionInput")
    question.setText("Will Enter submit this prediction?")

    qtbot.keyPress(question, Qt.Key.Key_Return)

    assert operations.create_calls == [
        CreatePredictionCall(
            question="Will Enter submit this prediction?",
            probability_percent=50,
            rationale="",
            background="",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=None,
            tags=(),
        )
    ]
    assert window.current_screen_name == "Prediction Detail"


def test_prediction_detail_loads_latest_prediction_at_construction(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will this survive a restart?",
        probability_percent=60,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        latest.question
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "OPEN"
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "60%"
    )
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden() is (
        False
    )
    assert _required_child(window, QLabel, "predictionDetailEmptyState").isHidden()


def test_prediction_detail_renders_locked_status(qtbot: QtBot) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Has this prediction passed its forecast deadline?",
        probability_percent=60,
        status=PredictionStatus.LOCKED,
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "LOCKED"


def test_returning_to_prediction_detail_refreshes_external_changes(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(42, "Original question", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")
    operations.get_calls.clear()
    operations.latest = replace(
        original,
        question="Externally refreshed question",
        probability_percent=45,
        status=PredictionStatus.LOCKED,
        background="Fresh context",
        metadata_version=2,
        current_revision_id=2,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            revision_id=2,
            prediction_id=42,
            probability_percent=45,
            sequence=2,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
        )
    )
    operations.revision_read_calls.clear()

    window.navigate_to("Dashboard")
    window.navigate_to("Prediction Detail")

    assert operations.get_calls == [42]
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Externally refreshed question"
    )
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "LOCKED"
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        "Fresh context"
    )
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 2
    assert [sample.probability_percent for sample in chart.samples] == [60, 45]
    assert operations.revision_read_calls == [42]


def test_prediction_detail_refresh_failure_retains_last_visible_data(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(42, "Still-visible question", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.navigate_to("Prediction Detail")
    operations.latest = None

    window.navigate_to("Dashboard")
    window.navigate_to("Prediction Detail")

    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Still-visible question"
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be refreshed" in error.text()
    assert not error.isHidden()


def test_prediction_detail_shows_present_metadata_and_hides_missing_sections(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=42,
        question="Will the release ship?",
        probability_percent=65,
        background="The implementation is nearly complete.",
        resolution_criteria="Yes if the installer is published.",
        forecast_deadline=date(2026, 9, 1),
        expected_resolution=None,
        tags=("release", "desktop"),
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "predictionDetailTags").text() == (
        "#release  #desktop"
    )
    deadline = _required_child(window, QLabel, "predictionDetailForecastDeadline")
    assert "2026" in deadline.text()
    assert not _required_child(
        window,
        QWidget,
        "predictionDetailForecastDeadlineRow",
    ).isHidden()
    assert _required_child(
        window,
        QWidget,
        "predictionDetailExpectedResolutionRow",
    ).isHidden()
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        latest.background
    )
    assert (
        _required_child(
            window,
            QLabel,
            "predictionDetailResolutionCriteria",
        ).text()
        == latest.resolution_criteria
    )


def test_prediction_detail_hides_all_empty_optional_metadata(qtbot: QtBot) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(42, "Will the view stay calm?", 65))
    )
    qtbot.addWidget(window)

    for object_name in (
        "predictionDetailTags",
        "predictionDetailForecastDeadlineRow",
        "predictionDetailExpectedResolutionRow",
        "predictionDetailBackgroundSection",
        "predictionDetailResolutionCriteriaSection",
        "definitionHistoryGroup",
    ):
        assert _required_child(window, QWidget, object_name).isHidden()


def test_prediction_detail_enables_open_lifecycle_actions(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(1, "Will this stay in scope?", 50)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    revise = _required_child(window, QPushButton, "reviseForecastButton")
    assert revise.isEnabled()
    assert "preserving" in revise.toolTip()

    journal = _required_child(window, QPushButton, "addJournalEntryButton")
    assert journal.isEnabled()
    assert "without changing" in journal.toolTip()

    for object_name in (
        "resolvePredictionButton",
        "markInvalidButton",
        "deletePredictionButton",
    ):
        button = _required_child(window, QPushButton, object_name)
        assert button.isEnabled()
        assert button.toolTip()
    assert _required_child(window, QLabel, "timelinePlaceholder").isHidden()
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    assert not chart.isHidden()
    assert _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    ).isHidden()


def test_probability_history_empty_and_load_failure_states_are_honest(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a missing chart read be described honestly?", 60)
    )
    operations.revisions.clear()
    window = MainWindow(operations)
    qtbot.addWidget(window)

    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    placeholder = _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    )
    assert chart.revision_count == 0
    assert chart.samples == ()
    assert chart.isHidden()
    assert not placeholder.isHidden()
    assert "No forecast revisions" in placeholder.text()

    operations.revision_read_error = ApplicationError("Revision read failed.")
    window.navigate_to("Prediction Detail")

    assert chart.revision_count == 0
    assert chart.isHidden()
    assert not placeholder.isHidden()
    assert "could not be loaded" in placeholder.text()
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "Revision read failed" in error.text()
    assert not error.isHidden()


def test_probability_history_refresh_failure_retains_matching_loaded_chart(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a transient read preserve visible history?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    retained_samples = chart.samples

    operations.revision_read_error = ApplicationError("Temporary read failure.")
    window.navigate_to("Prediction Detail")

    placeholder = _required_child(
        window,
        QLabel,
        "probabilityHistoryPlaceholder",
    )
    assert chart.revision_count == 1
    assert chart.samples == retained_samples
    assert not chart.isHidden()
    assert not placeholder.isHidden()
    assert "last loaded chart remains visible" in placeholder.text()
    assert (
        "Temporary read failure"
        in _required_child(
            window,
            QLabel,
            "predictionDetailError",
        ).text()
    )


def test_probability_history_accessibility_reports_timeline_read_failure(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the nonvisual equivalent stay truthful?", 60)
    )
    operations.timeline_error = ApplicationError("Timeline read failed.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )

    assert chart.revision_count == 1
    assert "currently unavailable" in chart.accessibleDescription()

    operations.timeline_error = None
    window.navigate_to("Prediction Detail")

    assert "listed in the Timeline" in chart.accessibleDescription()


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.LOCKED, PredictionStatus.RESOLVED, PredictionStatus.INVALID],
)
def test_prediction_detail_disables_revision_for_ineligible_lifecycle(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Can this forecast be revised?", 60, status=status)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    button = _required_child(window, QPushButton, "reviseForecastButton")
    assert not button.isEnabled()
    assert status.value in button.toolTip()


def test_opening_and_cancelling_revision_dialog_appends_nothing(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Will opening the editor preserve history?",
            60,
            current_revision_id=11,
            current_revision_sequence=3,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    assert _required_child(dialog, QLabel, "reviseCurrentProbability").text() == "60%"
    assert _required_child(dialog, QSpinBox, "revisionProbabilityInput").value() == 60
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == []
    assert len(operations.revisions) == 1


def test_opening_revision_refreshes_probability_and_concurrency_tokens(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(
        7,
        "Will the revision editor use fresh state?",
        60,
        metadata_version=1,
        current_revision_id=11,
        current_revision_sequence=1,
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        probability_percent=70,
        metadata_version=2,
        current_revision_id=12,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            12,
            7,
            70,
            2,
            datetime(2026, 8, 13, tzinfo=UTC),
        )
    )

    dialog = _open_revision_dialog(qtbot, window)
    assert _required_child(dialog, QLabel, "reviseCurrentProbability").text() == "70%"
    _required_child(dialog, QSpinBox, "revisionProbabilityInput").setValue(45)
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == [
        ReviseForecastCall(
            prediction_id=7,
            probability_percent=45,
            rationale="",
            expected_revision_id=12,
            expected_metadata_version=2,
        )
    ]


def test_revision_refresh_that_finds_locked_state_opens_no_dialog(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(7, "Will this lock before the dialog opens?", 60)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    operations.latest = replace(original, status=PredictionStatus.LOCKED)

    qtbot.mouseClick(
        _required_child(window, QPushButton, "reviseForecastButton"),
        Qt.MouseButton.LeftButton,
    )

    assert window.findChild(QDialog, "reviseForecastDialog") is None
    assert operations.revise_calls == []
    assert not _required_child(window, QPushButton, "reviseForecastButton").isEnabled()
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "locked" in error.text()
    assert not error.isHidden()


def test_same_probability_revision_error_stays_inline_and_open(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will an unchanged forecast be rejected?", 60)
    )
    operations.revise_error = ApplicationError(
        "The new forecast matches the current 60%. Add a journal entry instead."
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_revision_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    error = _required_child(dialog, QLabel, "reviseForecastError")
    assert "matches the current" in error.text()
    assert not error.isHidden()
    assert len(operations.revisions) == 1


def test_revision_rationale_helper_explains_when_to_use_journal(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will revision guidance clarify the Journal?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    dialog = _open_revision_dialog(qtbot, window)

    helper = _required_child(dialog, QLabel, "revisionRationaleHelper")
    assert helper.text() == (
        "This explanation stays attached to the new forecast. To record a thought "
        "without changing probability, add a Journal entry."
    )
    assert helper.textFormat() is Qt.TextFormat.PlainText
    assert helper.wordWrap()
    rationale = _required_child(dialog, QPlainTextEdit, "revisionRationaleInput")
    assert rationale.accessibleDescription() == helper.text()
    layout = dialog.layout()
    assert layout.indexOf(rationale) < layout.indexOf(helper)
    assert layout.indexOf(helper) < layout.indexOf(
        _required_child(dialog, QLabel, "reviseForecastError")
    )


@pytest.mark.parametrize("new_probability", [0, 37, 100])
def test_revision_appends_with_tokens_and_refreshes_forecast_history(
    qtbot: QtBot,
    new_probability: int,
) -> None:
    original = FakePrediction(
        7,
        "Will a revision append honestly?",
        60,
        metadata_version=4,
        current_revision_id=11,
        current_revision_sequence=3,
        current_rationale="Initial <b>reason</b>",
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    dialog = _open_revision_dialog(qtbot, window)
    _required_child(dialog, QSpinBox, "revisionProbabilityInput").setValue(
        new_probability
    )
    _required_child(dialog, QPlainTextEdit, "revisionRationaleInput").setPlainText(
        "New <i>evidence</i>"
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveForecastRevisionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.revise_calls == [
        ReviseForecastCall(
            prediction_id=7,
            probability_percent=new_probability,
            rationale="New <i>evidence</i>",
            expected_revision_id=11,
            expected_metadata_version=4,
        )
    ]
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        f"{new_probability}%"
    )
    assert (
        _required_child(window, QLabel, "forecastRevisionProbability12").text()
        == f"FORECAST  60% \N{RIGHTWARDS ARROW} {new_probability}%"
    )
    rationale = _required_child(window, QLabel, "forecastRevisionRationale12")
    assert rationale.text() == "New <i>evidence</i>"
    assert rationale.textFormat() is Qt.TextFormat.PlainText
    assert chart.revision_count == 2
    assert [sample.sequence for sample in chart.samples] == [3, 4]
    assert [sample.probability_percent for sample in chart.samples] == [
        60,
        new_probability,
    ]


def test_forecast_history_uses_previous_revision_for_nonconsecutive_return(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will the forecast return to its starting value?",
        60,
        current_revision_id=3,
        current_revision_sequence=3,
    )
    operations = FakePredictionOperations(latest)
    operations.revisions = [
        FakeForecastRevision(1, 7, 60, 1, datetime(2026, 8, 10, tzinfo=UTC)),
        FakeForecastRevision(2, 7, 40, 2, datetime(2026, 8, 11, tzinfo=UTC)),
        FakeForecastRevision(3, 7, 60, 3, datetime(2026, 8, 12, tzinfo=UTC)),
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert (
        _required_child(
            window,
            QLabel,
            "forecastRevisionProbability3",
        ).text()
        == "FORECAST  40% \N{RIGHTWARDS ARROW} 60%"
    )


def test_add_journal_entry_refreshes_context_and_cancel_has_no_effect(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(
        7,
        "Will a cancelled Journal form leave history alone?",
        60,
        metadata_version=1,
        current_revision_id=11,
        current_revision_sequence=1,
    )
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        probability_percent=70,
        metadata_version=2,
        current_revision_id=12,
        current_revision_sequence=2,
    )
    operations.revisions.append(
        FakeForecastRevision(
            revision_id=12,
            prediction_id=7,
            probability_percent=70,
            sequence=2,
            created_at=datetime(2026, 8, 13, tzinfo=UTC),
        )
    )

    dialog = _open_journal_dialog(qtbot, window)
    assert _required_child(dialog, QLabel, "journalForecastAtTime").text() == "70%"
    assert dialog.focusWidget() is _required_child(
        dialog,
        QPlainTextEdit,
        "journalEntryBodyInput",
    )
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.journal_calls == []
    assert operations.journal_entries == []


def test_blank_journal_entry_stays_inline_without_calling_operation(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will blank Journal entries be rejected?", 60)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")
    body.setPlainText("  \n ")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    error = _required_child(dialog, QLabel, "addJournalEntryError")
    assert "Write a journal entry" in error.text()
    assert not error.isHidden()
    assert operations.journal_calls == []


def test_journal_expected_error_keeps_multiline_body_and_dialog_open(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will stale Journal context be rejected?", 60)
    )
    operations.journal_error = ApplicationError(
        "This prediction changed before the Journal entry could be saved."
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")
    body.setPlainText("First line\nSecond line")

    qtbot.keyPress(body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert dialog.isVisible()
    assert body.toPlainText() == "First line\nSecond line"
    error = _required_child(dialog, QLabel, "addJournalEntryError")
    assert "changed before" in error.text()
    assert not error.isHidden()
    assert len(operations.journal_calls) == 1


def test_enter_adds_newline_and_ctrl_enter_saves_journal_with_tokens(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        7,
        "Will keyboard entry remain comfortable?",
        65,
        metadata_version=4,
        current_revision_id=11,
        current_revision_sequence=3,
    )
    operations = FakePredictionOperations(latest)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    original_samples = chart.samples
    dialog = _open_journal_dialog(qtbot, window)
    body = _required_child(dialog, QPlainTextEdit, "journalEntryBodyInput")

    qtbot.keyClicks(body, "Evidence one")
    qtbot.keyPress(body, Qt.Key.Key_Return)
    qtbot.keyClicks(body, "Evidence two")
    assert body.toPlainText() == "Evidence one\nEvidence two"
    qtbot.keyPress(body, Qt.Key.Key_Tab)
    assert dialog.focusWidget() is _required_child(
        dialog,
        QPushButton,
        "saveJournalEntryButton",
    )
    body.setFocus()
    qtbot.keyPress(body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)

    assert operations.journal_calls == [
        AddJournalEntryCall(
            prediction_id=7,
            body="Evidence one\nEvidence two",
            expected_revision_id=11,
            expected_metadata_version=4,
        )
    ]
    assert not dialog.isVisible()
    assert _required_child(window, QLabel, "predictionDetailProbability").text() == (
        "65%"
    )
    assert (
        _required_child(window, QLabel, "journalEntryBody1").text()
        == "Evidence one\nEvidence two"
    )
    assert (
        _required_child(window, QLabel, "journalEntryForecastAtTime1").text()
        == "Forecast at the time: 65%"
    )
    assert chart.revision_count == 1
    assert chart.samples == original_samples


@pytest.mark.parametrize("status", [PredictionStatus.OPEN, PredictionStatus.LOCKED])
def test_journal_creation_is_enabled_for_nonterminal_statuses(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    window = MainWindow(
        FakePredictionOperations(
            FakePrediction(7, "Can this accept a Journal entry?", 60, status=status)
        )
    )
    qtbot.addWidget(window)

    assert _required_child(window, QPushButton, "addJournalEntryButton").isEnabled()


@pytest.mark.parametrize(
    "status",
    [PredictionStatus.RESOLVED, PredictionStatus.INVALID],
)
def test_terminal_predictions_disable_new_journals_but_allow_corrections(
    qtbot: QtBot,
    status: PredictionStatus,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Can terminal history be corrected?", 60, status=status)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Original Journal text",
            original_body="Original Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    add_button = _required_child(window, QPushButton, "addJournalEntryButton")
    assert not add_button.isEnabled()
    correct_button = _required_child(
        window,
        QPushButton,
        "correctJournalEntryButton4",
    )
    assert correct_button.isEnabled()


def test_unified_timeline_renders_forecasts_and_journals_as_plain_text(
    qtbot: QtBot,
) -> None:
    markup = "<b>Literal Journal evidence</b>"
    operations = FakePredictionOperations(
        FakePrediction(7, "Will the timeline be historically honest?", 40)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=8,
            prediction_id=7,
            created_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
            body=markup,
            original_body=markup,
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=40,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QLabel, "timelineHeading").text() == "TIMELINE"
    body = _required_child(window, QLabel, "journalEntryBody8")
    assert body.text() == markup
    assert body.textFormat() is Qt.TextFormat.PlainText
    timestamp = _required_child(window, QLabel, "journalEntryTimestamp8")
    assert timestamp.text() == (
        datetime(2026, 8, 13, 19, 30, tzinfo=UTC)
        .astimezone()
        .strftime("%b %d, %Y at %H:%M %Z")
        .strip()
    )


def test_correction_cancel_and_expected_error_preserve_current_body(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will correction failures remain safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Latest text",
            original_body="Original text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
            current_correction_id=3,
            corrections=(
                FakeJournalCorrection(
                    3,
                    "Latest text",
                    datetime(2026, 8, 13, tzinfo=UTC),
                ),
            ),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    original_samples = chart.samples
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    assert body.toPlainText() == "Latest text"
    qtbot.keyPress(dialog, Qt.Key.Key_Escape)
    assert operations.correction_calls == []

    operations.correction_error = ApplicationError(
        "This Journal entry changed before the correction could be saved."
    )
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    body.setPlainText("Corrected text")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )
    assert dialog.isVisible()
    assert body.toPlainText() == "Corrected text"
    assert (
        "changed before"
        in _required_child(
            dialog,
            QLabel,
            "correctJournalEntryError",
        ).text()
    )
    assert chart.revision_count == 1
    assert chart.samples == original_samples


def test_correction_dialog_refreshes_external_edits_and_recovers_after_stale_save(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will correction retries use the latest text?", 60)
    )
    original = FakeJournalTimelineEvent(
        entry_id=4,
        prediction_id=7,
        created_at=datetime(2026, 8, 12, tzinfo=UTC),
        body="Original text",
        original_body="Original text",
        forecast_revision_id=1,
        forecast_revision_sequence=1,
        forecast_probability_percent=60,
    )
    operations.journal_entries = [original]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")

    first_external_correction = FakeJournalCorrection(
        1,
        "First external correction",
        datetime(2026, 8, 13, tzinfo=UTC),
    )
    operations.journal_entries[0] = replace(
        original,
        body=first_external_correction.body,
        current_correction_id=first_external_correction.correction_id,
        corrections=(first_external_correction,),
    )

    dialog = _click_correction_button(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    assert body.toPlainText() == "First external correction"

    second_external_correction = FakeJournalCorrection(
        2,
        "Second external correction",
        datetime(2026, 8, 14, tzinfo=UTC),
    )
    operations.journal_entries[0] = replace(
        operations.journal_entries[0],
        body=second_external_correction.body,
        current_correction_id=second_external_correction.correction_id,
        corrections=(first_external_correction, second_external_correction),
    )
    operations.correction_error = ApplicationError(
        "This Journal entry changed before the correction could be saved."
    )
    body.setPlainText("Correction from the stale dialog")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert operations.correction_calls[-1].expected_correction_id == 1
    qtbot.keyPress(dialog, Qt.Key.Key_Escape)
    operations.correction_error = None

    retry_dialog = _click_correction_button(qtbot, window, entry_id=4)
    retry_body = _required_child(
        retry_dialog,
        QPlainTextEdit,
        "correctJournalEntryBodyInput",
    )
    assert retry_body.toPlainText() == "Second external correction"
    retry_body.setPlainText("Recovered correction")
    qtbot.mouseClick(
        _required_child(retry_dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.correction_calls[-1] == CorrectJournalEntryCall(
        prediction_id=7,
        entry_id=4,
        body="Recovered correction",
        expected_correction_id=2,
    )


def test_correction_refresh_error_is_visible_and_does_not_open_dialog(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a failed refresh stay safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Journal text",
            original_body="Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    operations.timeline_error = ApplicationError("The timeline is temporarily busy.")

    qtbot.mouseClick(
        _required_child(window, QPushButton, "correctJournalEntryButton4"),
        Qt.MouseButton.LeftButton,
    )

    assert not any(
        dialog.isVisible()
        for dialog in window.findChildren(QDialog, "correctJournalEntryDialog")
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be refreshed" in error.text()
    assert "temporarily busy" in error.text()
    assert not error.isHidden()


def test_missing_journal_during_correction_refresh_is_reported_safely(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Will a missing entry stay safe?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=datetime(2026, 8, 12, tzinfo=UTC),
            body="Journal text",
            original_body="Journal text",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Prediction Detail")
    operations.journal_entries.clear()

    qtbot.mouseClick(
        _required_child(window, QPushButton, "correctJournalEntryButton4"),
        Qt.MouseButton.LeftButton,
    )

    assert not any(
        dialog.isVisible()
        for dialog in window.findChildren(QDialog, "correctJournalEntryDialog")
    )
    error = _required_child(window, QLabel, "predictionDetailError")
    assert "could not be found" in error.text()
    assert not error.isHidden()


def test_correction_displays_edited_marker_and_collapsed_plain_text_history(
    qtbot: QtBot,
) -> None:
    original_time = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations(
        FakePrediction(7, "Will corrections retain every prior body?", 60)
    )
    operations.journal_entries = [
        FakeJournalTimelineEvent(
            entry_id=4,
            prediction_id=7,
            created_at=original_time,
            body="First corrected body",
            original_body="<b>Original body</b>",
            forecast_revision_id=1,
            forecast_revision_sequence=1,
            forecast_probability_percent=60,
            current_correction_id=1,
            corrections=(
                FakeJournalCorrection(
                    correction_id=1,
                    body="First corrected body",
                    corrected_at=datetime(2026, 8, 13, 19, 30, tzinfo=UTC),
                ),
            ),
        )
    ]
    window = MainWindow(operations)
    qtbot.addWidget(window)
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 1
    dialog = _open_correction_dialog(qtbot, window, entry_id=4)
    body = _required_child(dialog, QPlainTextEdit, "correctJournalEntryBodyInput")
    body.setPlainText("<i>Corrected body</i>")
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "saveJournalCorrectionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.correction_calls == [
        CorrectJournalEntryCall(
            prediction_id=7,
            entry_id=4,
            body="<i>Corrected body</i>",
            expected_correction_id=1,
        )
    ]
    assert (
        _required_child(
            window,
            QLabel,
            "journalEntryEdited4",
        )
        .text()
        .startswith("Edited ")
    )
    assert (
        _required_child(window, QLabel, "journalEntryBody4").text()
        == "<i>Corrected body</i>"
    )
    history = _required_child(window, QGroupBox, "journalEntryEditHistory4")
    content = _required_child(window, QWidget, "journalEntryEditHistoryContent4")
    assert not history.isChecked()
    assert content.isHidden()
    history.setChecked(True)
    assert not content.isHidden()
    original = _required_child(window, QLabel, "journalEntryOriginalBody4")
    correction = _required_child(window, QLabel, "journalCorrectionBody1")
    assert original.text() == "<b>Original body</b>"
    assert correction.text() == "First corrected body"
    assert original.textFormat() is Qt.TextFormat.PlainText
    assert correction.textFormat() is Qt.TextFormat.PlainText
    assert chart.revision_count == 1
    assert (
        _required_child(window, QLabel, "journalCorrectionHeading1")
        .text()
        .startswith("Correction 1 ·")
    )


def test_edit_details_dialog_prefills_values_and_optional_date_controls(
    qtbot: QtBot,
) -> None:
    latest = FakePrediction(
        prediction_id=7,
        question="Will this dialog be prefilled?",
        probability_percent=55,
        background="Context",
        resolution_criteria="A public release counts.",
        forecast_deadline=date(2026, 9, 2),
        tags=("ui", "m3"),
    )
    window = MainWindow(FakePredictionOperations(latest))
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)

    assert _required_child(dialog, QLineEdit, "editQuestionInput").text() == (
        latest.question
    )
    assert _required_child(
        dialog, QPlainTextEdit, "editBackgroundInput"
    ).toPlainText() == ("Context")
    assert _required_child(dialog, QLineEdit, "editTagsInput").text() == "ui, m3"
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    deadline_input = _required_child(
        dialog,
        QDateEdit,
        "editForecastDeadlineInput",
    )
    assert deadline_toggle.isChecked()
    assert deadline_input.isEnabled()
    assert deadline_input.isVisible()
    assert deadline_input.date() == QDate(2026, 9, 2)
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    assert not expected_toggle.isChecked()
    assert not expected_input.isEnabled()
    assert expected_input.isHidden()
    assert deadline_input.minimumDate() == QDate(1752, 9, 14)
    assert deadline_input.maximumDate() == QDate(9999, 12, 31)


def test_unset_optional_date_is_revealed_only_when_enabled(qtbot: QtBot) -> None:
    window = MainWindow(
        FakePredictionOperations(FakePrediction(7, "Will dates stay optional?", 55))
    )
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    deadline_input = _required_child(
        dialog,
        QDateEdit,
        "editForecastDeadlineInput",
    )

    assert not deadline_toggle.isChecked()
    assert not deadline_input.isEnabled()
    assert deadline_input.isHidden()

    qtbot.keyClick(deadline_toggle, Qt.Key.Key_Space)

    assert deadline_toggle.isChecked()
    assert deadline_input.isEnabled()
    assert deadline_input.isVisible()

    qtbot.keyClick(deadline_toggle, Qt.Key.Key_Space)

    assert not deadline_toggle.isChecked()
    assert not deadline_input.isEnabled()
    assert deadline_input.isHidden()


def test_edit_details_dialog_preserves_earliest_supported_date(
    qtbot: QtBot,
) -> None:
    earliest = date(1752, 9, 14)
    window = MainWindow(
        FakePredictionOperations(
            FakePrediction(
                7, "Earliest supported deadline?", 55, forecast_deadline=earliest
            )
        )
    )
    qtbot.addWidget(window)

    dialog = _open_edit_dialog(qtbot, window)

    deadline = _required_child(dialog, QDateEdit, "editForecastDeadlineInput")
    assert deadline.date() == QDate(1752, 9, 14)
    assert deadline.isVisible()


def test_user_definition_text_is_always_rendered_as_plain_text(qtbot: QtBot) -> None:
    markup = "<b>Literal forecast wording</b>"
    operations = FakePredictionOperations(
        FakePrediction(
            prediction_id=7,
            question=markup,
            probability_percent=55,
            background="<i>Literal background</i>",
            resolution_criteria="<a href='x'>Literal criteria</a>",
            tags=("<u>tag</u>",),
        )
    )
    operations.definition_changes = (
        DefinitionChange(
            change_id=4,
            prediction_id=7,
            changed_at=datetime(2026, 8, 12, 19, 30, tzinfo=UTC),
            changed_fields=("question",),
            old_question="<em>Old literal</em>",
            new_question=markup,
            old_resolution_criteria=None,
            new_resolution_criteria=None,
            old_forecast_deadline=None,
            new_forecast_deadline=None,
        ),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name in (
        "predictionDetailQuestion",
        "predictionDetailTags",
        "predictionDetailBackground",
        "predictionDetailResolutionCriteria",
        "definitionChange4Question",
    ):
        label = _required_child(window, QLabel, object_name)
        assert label.textFormat() is Qt.TextFormat.PlainText
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == markup
    assert (
        "<em>Old literal</em>"
        in _required_child(
            window,
            QLabel,
            "definitionChange4Question",
        ).text()
    )


def test_open_edit_details_refreshes_externally_changed_prediction(
    qtbot: QtBot,
) -> None:
    original = FakePrediction(7, "Original question", 55)
    operations = FakePredictionOperations(original)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    operations.latest = replace(
        original,
        question="Externally changed question",
        background="Newer context",
        metadata_version=2,
    )

    dialog = _open_edit_dialog(qtbot, window)

    assert operations.get_calls == [7, 7]
    assert _required_child(dialog, QLineEdit, "editQuestionInput").text() == (
        "Externally changed question"
    )
    assert (
        _required_child(
            dialog,
            QPlainTextEdit,
            "editBackgroundInput",
        ).toPlainText()
        == "Newer context"
    )
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Externally changed question"
    )


def test_cancel_edit_details_does_not_call_update(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Unsaved edit")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == []
    assert operations.mutation_count == 0
    assert not dialog.isVisible()


def test_repeated_cancel_deletes_finished_edit_dialogs(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for _attempt in range(3):
        dialog = _open_edit_dialog(qtbot, window)
        qtbot.mouseClick(
            _required_child(dialog, QPushButton, "cancelPredictionDetailsButton"),
            Qt.MouseButton.LeftButton,
        )
        qtbot.waitUntil(lambda current=dialog: not current.isVisible())
        qtbot.waitUntil(
            lambda: (
                not window.findChildren(
                    QDialog,
                    "editPredictionDetailsDialog",
                )
            )
        )

    remaining = [
        dialog
        for dialog in window.findChildren(QDialog)
        if dialog.objectName() == "editPredictionDetailsDialog"
    ]
    assert remaining == []
    assert operations.update_calls == []


def test_noop_edit_closes_without_mutation(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.mutation_count == 0
    assert not dialog.isVisible()


def test_unprotected_edit_saves_without_warning_and_refreshes_detail(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: pytest.fail("Unexpected confirmation warning"),
    )
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QPlainTextEdit, "editBackgroundInput").setPlainText(
        "New background"
    )
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    expected_toggle.setChecked(True)
    expected_input.setDate(QDate(2026, 10, 20))
    _required_child(dialog, QLineEdit, "editTagsInput").setText("launch, ui")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.update_calls == [
        MetadataUpdateCall(
            prediction_id=7,
            question="Original question",
            background="New background",
            resolution_criteria="",
            forecast_deadline=None,
            expected_resolution=date(2026, 10, 20),
            tags=("launch", "ui"),
            expected_metadata_version=1,
            confirm_meaning_change=False,
        )
    ]
    assert operations.mutation_count == 1
    assert _required_child(window, QLabel, "predictionDetailBackground").text() == (
        "New background"
    )
    assert _required_child(window, QLabel, "predictionDetailTags").text() == (
        "#launch  #ui"
    )
    assert (
        "2026"
        in _required_child(
            window,
            QLabel,
            "predictionDetailExpectedResolution",
        ).text()
    )


def test_expected_resolution_only_saves_without_warning(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: pytest.fail("Unexpected confirmation warning"),
    )
    dialog = _open_edit_dialog(qtbot, window)
    expected_toggle = _required_child(
        dialog,
        QCheckBox,
        "editExpectedResolutionToggle",
    )
    expected_input = _required_child(
        dialog,
        QDateEdit,
        "editExpectedResolutionInput",
    )
    qtbot.mouseClick(expected_toggle, Qt.MouseButton.LeftButton)
    expected_input.setDate(QDate(2026, 10, 20))

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.update_calls[0].expected_resolution == date(2026, 10, 20)
    assert not operations.update_calls[0].confirm_meaning_change
    assert operations.mutation_count == 1
    assert not dialog.isVisible()


def test_expected_edit_failure_is_shown_inline(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.update_error = ApplicationError("Those details could not be saved.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    error = _required_child(dialog, QLabel, "editDetailsError")
    assert error.text() == "Those details could not be saved."
    assert not error.isHidden()
    assert dialog.isVisible()
    assert operations.mutation_count == 0


def test_deadline_only_warning_explains_locking_without_proposition_guidance(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("forecast_deadline",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def decline_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", decline_warning)
    dialog = _open_edit_dialog(qtbot, window)
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    qtbot.mouseClick(deadline_toggle, Qt.MouseButton.LeftButton)

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert operations.mutation_count == 0
    assert dialog.isVisible()
    assert warnings[0][0] == "Confirm forecast deadline change"
    assert "forecast revisions become locked" in warnings[0][1]
    assert "Definition history" in warnings[0][1]
    assert "what this prediction means" not in warnings[0][1]
    assert "new prediction" not in warnings[0][1]


def test_semantic_change_warning_decline_does_not_retry_or_mutate(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def decline_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(QMessageBox, "warning", decline_warning)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert len(operations.update_calls) == 1
    assert not operations.update_calls[0].confirm_meaning_change
    assert operations.mutation_count == 0
    assert operations.latest is not None
    assert operations.latest.question == "Original question"
    assert dialog.isVisible()
    assert warnings[0][0] == "Confirm definition change"
    assert "what this prediction means" in warnings[0][1]
    assert "create a new prediction" in warnings[0][1]
    assert "forecast revisions become locked" not in warnings[0][1]


def test_meaning_change_confirmation_retries_and_refreshes_returned_detail(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question", "forecast_deadline")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []

    def accept_warning(
        _parent: QWidget,
        title: str,
        message: str,
        _buttons: QMessageBox.StandardButton,
        _default: QMessageBox.StandardButton,
    ) -> QMessageBox.StandardButton:
        warnings.append((title, message))
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", accept_warning)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")
    deadline_toggle = _required_child(
        dialog,
        QCheckBox,
        "editForecastDeadlineToggle",
    )
    deadline_toggle.setChecked(True)
    _required_child(dialog, QDateEdit, "editForecastDeadlineInput").setDate(
        QDate(2026, 9, 30)
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [call.confirm_meaning_change for call in operations.update_calls] == [
        False,
        True,
    ]
    assert [call.expected_metadata_version for call in operations.update_calls] == [
        1,
        1,
    ]
    assert operations.mutation_count == 1
    assert _required_child(window, QLabel, "predictionDetailQuestion").text() == (
        "Changed question"
    )
    assert warnings[0][0] == "Confirm definition and deadline changes"
    assert "what this prediction means" in warnings[0][1]
    assert "create a new prediction" in warnings[0][1]
    assert "forecast revisions become locked" in warnings[0][1]
    assert "Definition history" in warnings[0][1]
    assert not dialog.isVisible()
    assert operations.definition_change_calls == [7, 7, 7, 7]


def test_stale_confirmation_retry_stays_inline_without_mutating(
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Original question", 55))
    operations.confirmation_fields = ("question",)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_edit_dialog(qtbot, window)
    _required_child(dialog, QLineEdit, "editQuestionInput").setText("Changed question")

    def make_stale(*args, **kwargs) -> QMessageBox.StandardButton:
        assert operations.latest is not None
        operations.latest = replace(
            operations.latest,
            background="Intervening edit",
            metadata_version=2,
        )
        return QMessageBox.StandardButton.Save

    monkeypatch.setattr(QMessageBox, "warning", make_stale)
    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "savePredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )

    assert [call.expected_metadata_version for call in operations.update_calls] == [
        1,
        1,
    ]
    assert operations.mutation_count == 0
    assert operations.latest is not None
    assert operations.latest.question == "Original question"
    assert operations.latest.background == "Intervening edit"
    error = _required_child(dialog, QLabel, "editDetailsError")
    assert "changed before" in error.text()
    assert not error.isHidden()
    assert dialog.isVisible()


def test_definition_history_is_collapsed_and_shows_snapshot_in_local_time(
    qtbot: QtBot,
) -> None:
    changed_at = datetime(2026, 8, 12, 19, 30, tzinfo=UTC)
    operations = FakePredictionOperations(FakePrediction(7, "Changed question", 55))
    operations.definition_changes = (
        DefinitionChange(
            change_id=3,
            prediction_id=7,
            changed_at=changed_at,
            changed_fields=(
                "question",
                "resolution_criteria",
                "forecast_deadline",
            ),
            old_question="Original question",
            new_question="Changed question",
            old_resolution_criteria=None,
            new_resolution_criteria="A public release counts.",
            old_forecast_deadline=None,
            new_forecast_deadline=date(2026, 9, 30),
        ),
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    history = _required_child(window, QGroupBox, "definitionHistoryGroup")
    content = _required_child(window, QWidget, "definitionHistoryContent")
    assert not history.isHidden()
    assert not history.isChecked()
    assert content.isHidden()
    history.setChecked(True)
    assert not content.isHidden()
    expected_timestamp = (
        changed_at.astimezone().strftime("%b %d, %Y at %H:%M %Z").strip()
    )
    assert (
        _required_child(
            history,
            QLabel,
            "definitionChangeTimestamp3",
        ).text()
        == expected_timestamp
    )
    assert (
        "Original question"
        in _required_child(
            history,
            QLabel,
            "definitionChange3Question",
        ).text()
    )
    assert (
        "Not set"
        in _required_child(
            history,
            QLabel,
            "definitionChange3ResolutionCriteria",
        ).text()
    )
    assert (
        "2026"
        in _required_child(
            history,
            QLabel,
            "definitionChange3ForecastDeadline",
        ).text()
    )


def test_prediction_detail_has_helpful_empty_state(window: MainWindow) -> None:
    window.navigate_to("Prediction Detail")

    empty_state = _required_child(window, QLabel, "predictionDetailEmptyState")
    assert not empty_state.isHidden()
    assert "Create one" in empty_state.text()
    assert _required_child(window, QWidget, "predictionDetailContent").isHidden()
    chart = _required_child(
        window,
        ProbabilityHistoryChart,
        "probabilityHistoryChart",
    )
    assert chart.revision_count == 0
    assert chart.isHidden()


def test_resolve_dialog_is_side_effect_free_until_an_outcome_is_saved(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Will it resolve?", 35))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)

    explanation = _required_child(dialog, QLabel, "resolvePredictionExplanation")
    save = _required_child(dialog, QPushButton, "confirmResolvePredictionButton")
    assert "cannot be reopened" in explanation.text()
    assert explanation.textFormat() is Qt.TextFormat.PlainText
    assert not save.isEnabled()
    assert operations.resolve_calls == []

    dialog.reject()
    assert operations.resolve_calls == []


def test_resolve_yes_saves_reviewed_context_and_renders_terminal_facts(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        7,
        "Will it resolve?",
        35,
        current_revision_id=9,
        current_revision_sequence=3,
        metadata_version=4,
        deletion_allowed=False,
    )
    operations = FakePredictionOperations(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)
    _required_child(dialog, QRadioButton, "resolutionOutcomeYes").setChecked(True)
    _required_child(dialog, QPlainTextEdit, "resolutionNotesInput").setPlainText(
        "Certified result"
    )
    _required_child(dialog, QPlainTextEdit, "resolutionPostmortemInput").setPlainText(
        "I updated too slowly."
    )

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmResolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.resolve_calls == [
        ResolvePredictionCall(
            prediction_id=7,
            outcome=BinaryOutcome.YES,
            resolution_notes="Certified result",
            postmortem="I updated too slowly.",
            expected_revision_id=9,
            expected_metadata_version=4,
        )
    ]
    assert (
        _required_child(window, QLabel, "predictionDetailStatus").text() == "RESOLVED"
    )
    section = _required_child(window, QGroupBox, "predictionResolutionSection")
    assert not section.isHidden()
    assert (
        "Yes"
        in _required_child(
            section,
            QLabel,
            "predictionResolutionOutcome",
        ).text()
    )
    assert (
        "35%"
        in _required_child(
            section,
            QLabel,
            "predictionResolutionScoringForecast",
        ).text()
    )
    assert (
        _required_child(
            section,
            QLabel,
            "predictionResolutionNotes",
        ).text()
        == "Certified result"
    )
    assert (
        _required_child(
            section,
            QLabel,
            "predictionPostmortem",
        ).text()
        == "I updated too slowly."
    )
    for object_name in (
        "reviseForecastButton",
        "addJournalEntryButton",
        "resolvePredictionButton",
        "markInvalidButton",
        "deletePredictionButton",
    ):
        assert not _required_child(window, QPushButton, object_name).isEnabled()


def test_resolve_expected_error_keeps_dialog_and_inputs_for_retry(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Will it resolve?", 35))
    operations.resolve_error = ApplicationError("The prediction changed.")
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_resolution_dialog(qtbot, window)
    _required_child(dialog, QRadioButton, "resolutionOutcomeNo").setChecked(True)
    notes = _required_child(dialog, QPlainTextEdit, "resolutionNotesInput")
    notes.setPlainText("Keep this source")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmResolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )

    assert dialog.isVisible()
    assert notes.toPlainText() == "Keep this source"
    error = _required_child(dialog, QLabel, "resolvePredictionError")
    assert "changed" in error.text()
    assert not error.isHidden()


def test_mark_invalid_saves_optional_reason_and_renders_preserved_state(
    qtbot: QtBot,
) -> None:
    prediction = FakePrediction(
        7,
        "Was this cancelled?",
        55,
        current_revision_id=4,
        metadata_version=2,
        deletion_allowed=False,
    )
    operations = FakePredictionOperations(prediction)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_invalidation_dialog(qtbot, window)
    explanation = _required_child(dialog, QLabel, "markInvalidExplanation")
    assert "excludes it from scoring" in explanation.text()
    reason = _required_child(dialog, QPlainTextEdit, "invalidationReasonInput")
    reason.setPlainText("The event was cancelled.")

    qtbot.mouseClick(
        _required_child(dialog, QPushButton, "confirmMarkInvalidButton"),
        Qt.MouseButton.LeftButton,
    )

    assert operations.invalidate_calls == [
        InvalidatePredictionCall(
            prediction_id=7,
            reason="The event was cancelled.",
            expected_revision_id=4,
            expected_metadata_version=2,
        )
    ]
    assert _required_child(window, QLabel, "predictionDetailStatus").text() == "INVALID"
    section = _required_child(window, QGroupBox, "predictionInvalidationSection")
    assert not section.isHidden()
    assert (
        _required_child(
            section,
            QLabel,
            "predictionInvalidationReason",
        ).text()
        == "The event was cancelled."
    )
    assert not _required_child(
        window, QPushButton, "deletePredictionButton"
    ).isEnabled()


def test_mark_invalid_cancel_writes_nothing(qtbot: QtBot) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Keep this Open?", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    dialog = _open_invalidation_dialog(qtbot, window)
    _required_child(dialog, QPlainTextEdit, "invalidationReasonInput").setPlainText(
        "Do not save this"
    )

    dialog.reject()

    assert operations.invalidate_calls == []
    assert operations.latest is not None
    assert operations.latest.status is PredictionStatus.OPEN


def test_locked_prediction_can_resolve_or_invalidate_but_not_revise_or_delete(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Locked question?",
            55,
            status=PredictionStatus.LOCKED,
            deletion_allowed=False,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    assert _required_child(window, QPushButton, "resolvePredictionButton").isEnabled()
    assert _required_child(window, QPushButton, "markInvalidButton").isEnabled()
    assert _required_child(window, QPushButton, "addJournalEntryButton").isEnabled()
    assert not _required_child(window, QPushButton, "reviseForecastButton").isEnabled()
    delete = _required_child(window, QPushButton, "deletePredictionButton")
    assert not delete.isEnabled()
    assert "Mark Invalid" in delete.toolTip()


def test_terminal_user_text_is_rendered_as_plain_text(qtbot: QtBot) -> None:
    resolution = FakeResolution(
        resolution_id=1,
        prediction_id=7,
        outcome=BinaryOutcome.NO,
        resolved_at=datetime(2026, 8, 20, 19, 30, tzinfo=UTC),
        scoring_revision_id=1,
        scoring_revision_sequence=1,
        scoring_probability_percent=60,
        resolution_notes="<b>literal source</b>",
        postmortem="<i>literal reflection</i>",
    )
    operations = FakePredictionOperations(
        FakePrediction(
            7,
            "Question?",
            60,
            status=PredictionStatus.RESOLVED,
            resolution=resolution,
            deletion_allowed=False,
        )
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    for object_name, expected in (
        ("predictionResolutionNotes", "<b>literal source</b>"),
        ("predictionPostmortem", "<i>literal reflection</i>"),
    ):
        label = _required_child(window, QLabel, object_name)
        assert label.textFormat() is Qt.TextFormat.PlainText
        assert label.text() == expected


def test_delete_cancel_is_side_effect_free_and_confirm_clears_detail(
    qtbot: QtBot,
    monkeypatch,
) -> None:
    operations = FakePredictionOperations(FakePrediction(7, "Duplicate?", 55))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    delete = _required_child(window, QPushButton, "deletePredictionButton")

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *_args: QMessageBox.StandardButton.Cancel,
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)
    assert operations.delete_calls == []

    monkeypatch.setattr(
        QMessageBox,
        "warning",
        # PySide may return an equal integral button value rather than the
        # identical Python enum object used in this test process.
        lambda *_args: int(QMessageBox.StandardButton.Yes),
    )
    qtbot.mouseClick(delete, Qt.MouseButton.LeftButton)

    assert operations.delete_calls == [
        DeletePredictionCall(
            prediction_id=7,
            expected_revision_id=1,
            expected_metadata_version=1,
            confirm_permanent_deletion=True,
        )
    ]
    assert not _required_child(
        window,
        QLabel,
        "predictionDetailEmptyState",
    ).isHidden()


def test_meaningful_open_prediction_disables_delete_and_guides_invalid(
    qtbot: QtBot,
) -> None:
    operations = FakePredictionOperations(
        FakePrediction(7, "Meaningful?", 55, deletion_allowed=False)
    )
    window = MainWindow(operations)
    qtbot.addWidget(window)

    delete = _required_child(window, QPushButton, "deletePredictionButton")
    assert not delete.isEnabled()
    assert "Mark Invalid" in delete.toolTip()
    assert _required_child(window, QPushButton, "markInvalidButton").isEnabled()


def test_main_window_can_be_shown_and_closed(
    qtbot: QtBot,
    window: MainWindow,
) -> None:
    window.show()
    assert window.isVisible()

    window.close()
    assert not window.isVisible()


def _required_child[WidgetType: QWidget](
    parent: QWidget,
    widget_type: type[WidgetType],
    object_name: str,
) -> WidgetType:
    child = parent.findChild(widget_type, object_name)
    assert child is not None
    return child


def _open_edit_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "editPredictionDetailsButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "editPredictionDetailsDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_revision_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "reviseForecastButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "reviseForecastDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_journal_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "addJournalEntryButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "addJournalEntryDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_resolution_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "resolvePredictionButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "resolvePredictionDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_invalidation_dialog(qtbot: QtBot, window: MainWindow) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    qtbot.mouseClick(
        _required_child(window, QPushButton, "markInvalidButton"),
        Qt.MouseButton.LeftButton,
    )
    dialog = _required_child(window, QDialog, "markInvalidDialog")
    qtbot.waitUntil(dialog.isVisible)
    return dialog


def _open_correction_dialog(
    qtbot: QtBot,
    window: MainWindow,
    *,
    entry_id: int,
) -> QDialog:
    window.show()
    window.navigate_to("Prediction Detail")
    return _click_correction_button(qtbot, window, entry_id=entry_id)


def _click_correction_button(
    qtbot: QtBot,
    window: MainWindow,
    *,
    entry_id: int,
) -> QDialog:
    qtbot.mouseClick(
        _required_child(
            window,
            QPushButton,
            f"correctJournalEntryButton{entry_id}",
        ),
        Qt.MouseButton.LeftButton,
    )
    dialogs = window.findChildren(QDialog, "correctJournalEntryDialog")
    dialog = next(
        (candidate for candidate in reversed(dialogs) if candidate.isVisible()),
        None,
    )
    assert dialog is not None
    return dialog


def _object_name_prefix(screen_name: str) -> str:
    first_word, *remaining_words = screen_name.split()
    return first_word.lower() + "".join(remaining_words)
