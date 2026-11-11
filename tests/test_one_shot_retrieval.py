"""M58 retrieval and reflection across existing local read and write paths."""

import re
from dataclasses import replace
from datetime import UTC, date
from io import StringIO

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QGroupBox, QLabel, QWidget
from supported_fixtures import create_binary
from test_one_shot_persistence import Clock, request

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import create_runtime, run
from reckonsolve.data.database import Database
from reckonsolve.domain.browser import ArchiveDateMeaning, ArchiveMode, ArchiveQuery
from reckonsolve.domain.search import SearchSourceKind
from reckonsolve.identity import DEVELOPMENT_APPLICATION, STABLE_APPLICATION
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.screens import OneShotDetailScreen
from reckonsolve.ui.visual_system import (
    ACTION_ROLE_PROPERTY,
    ActionRole,
)


@pytest.fixture
def journal(tmp_path):
    path = tmp_path / "m58.sqlite3"
    database = Database.open(path)
    operations = PredictionOperations(database, Clock(), UTC)
    yield path, database, operations
    database.close()


def test_mode_filter_and_corrected_text_are_shared_by_cli_and_desktop(journal):
    path, database, operations = journal
    deadline = create_binary(operations, "Tomorrow?", 70)
    one_shot = operations.one_shots.create(request())
    corrected = operations.one_shots.correct(
        one_shot,
        replace(one_shot.record.effective, resolution_notes="Phone software result"),
        note="Copied the phone note wrong",
    )
    assert [
        item.prediction_id
        for item in operations.browse_predictions(mode=ArchiveMode.ONE_SHOT).predictions
    ] == [corrected.prediction_id]
    assert [
        item.prediction_id
        for item in operations.browse_predictions(mode=ArchiveMode.DEADLINE).predictions
    ] == [deadline.prediction_id]
    assert not operations.browse_predictions(
        mode=ArchiveMode.ONE_SHOT,
        date_meaning=ArchiveDateMeaning.FORECAST_DEADLINE,
        date_start=date(2026, 1, 1),
    ).predictions
    for phrase, source in (
        ("Phone software result", SearchSourceKind.RESOLUTION_NOTES),
        ("Copied the phone note wrong", SearchSourceKind.ONE_SHOT_CORRECTION_NOTE),
    ):
        hit = operations.search_predictions(
            f'"{phrase}"', mode=ArchiveMode.ONE_SHOT
        ).hits[0]
        assert hit.prediction.prediction_id == corrected.prediction_id
        assert hit.best_match.document.source_kind is source
    old = operations.search_predictions("Measured", include_superseded=True)
    assert old.hits and old.hits[0].prediction.prediction_id == corrected.prediction_id
    database.check_search_index()
    database.rebuild_search_index()
    assert (
        operations.search_predictions('"Copied the phone note wrong"')
        .hits[0]
        .best_match.document.source_kind
        is SearchSourceKind.ONE_SHOT_CORRECTION_NOTE
    )
    stdout, stderr = StringIO(), StringIO()
    assert (
        run(
            ["list", "--mode", "one-shot"],
            database_path=path,
            stdout=stdout,
            stderr=stderr,
        )
        == 0
    )
    assert "Tree height?" in stdout.getvalue() and "Tomorrow?" not in stdout.getvalue()
    stdout, stderr = StringIO(), StringIO()
    assert (
        run(
            ["search", '"Copied the phone note wrong"', "--mode", "one-shot"],
            database_path=path,
            stdout=stdout,
            stderr=stderr,
        )
        == 0
    )
    assert "transcription correction note" in stdout.getvalue().lower()


@pytest.mark.parametrize("mode", ["adaptive", "deadline"])
@pytest.mark.parametrize("command", [["list"], ["search", "Tomorrow"]])
def test_adaptive_cli_mode_and_previous_alias_find_the_same_records(
    journal, mode, command
):
    path, _, operations = journal
    create_binary(operations, "Tomorrow?", 70)
    operations.one_shots.create(request())
    output, errors = StringIO(), StringIO()
    assert (
        run(
            [*command, "--mode", mode],
            database_path=path,
            stdout=output,
            stderr=errors,
        )
        == 0
    )
    assert not errors.getvalue()
    assert "Tomorrow?" in output.getvalue()
    assert "Tree height?" not in output.getvalue()


@pytest.mark.parametrize("numeric", [False, True])
def test_journal_correction_postmortem_skip_restart_and_backup(
    journal, tmp_path, numeric
):
    path, database, operations = journal
    pending = operations.one_shots.create(request(numeric=numeric, answered=False))
    journaled = operations.one_shots.add_journal(pending, "Original clue")
    corrected = operations.one_shots.correct_journal(
        journaled,
        journaled.journals[0].entry_id,
        "Corrected clue",
        expected_correction_id=None,
    )
    assert corrected.journals[0].original_body == "Original clue"
    assert corrected.journals[0].body == "Corrected clue"
    with pytest.raises(ApplicationError, match="changed"):
        operations.one_shots.correct_journal(
            journaled,
            journaled.journals[0].entry_id,
            "Third clue",
            expected_correction_id=None,
        )
    assert not operations.search_predictions("Original").hits
    assert (
        operations.search_predictions("Original", include_superseded=True)
        .hits[0]
        .best_match.document.is_superseded
    )
    answered = operations.one_shots.add_answer(
        corrected,
        replace(
            corrected.record.effective,
            answer=request(numeric=numeric).values.answer,
            reveal_reported=request(numeric=numeric).values.reveal_reported,
            resolution_notes="Measured",
        ),
    )
    assert [
        item.prediction_id
        for item in operations.get_dashboard().needs_postmortem_predictions
    ] == [answered.prediction_id]
    completion = operations.record_postmortem_skip(
        answered.prediction_id, expected_correction_id=None
    )
    assert completion.prediction_id == answered.prediction_id
    assert operations.one_shots.score(
        operations.one_shots.get(answered.prediction_id)
    ) == operations.one_shots.score(answered)
    assert not operations.get_dashboard().needs_postmortem_predictions
    with pytest.raises(ApplicationError):
        operations.one_shots.skip_postmortem(answered)
    reflected = operations.one_shots.correct(
        operations.one_shots.get(answered.prediction_id),
        replace(answered.record.effective, postmortem="I trusted a blurry photo"),
    )
    assert reflected.postmortem_completion == completion
    assert not operations.get_dashboard().needs_postmortem_predictions
    backup = tmp_path / "recovered.sqlite3"
    database.backup_to(backup)
    database.close()
    for restored in (path, backup):
        reopened = Database.open(restored)
        try:
            again = PredictionOperations(reopened, Clock(), UTC).one_shots.get(
                answered.prediction_id
            )
            assert again.journals[0].body == "Corrected clue"
            assert again.postmortem_completion == completion
            assert again.record.effective.postmortem == "I trusted a blurry photo"
            reopened.check_search_index()
        finally:
            reopened.close()
        stdout, stderr = StringIO(), StringIO()
        assert (
            run(
                ["show", str(answered.prediction_id)],
                database_path=restored,
                stdout=stdout,
                stderr=stderr,
            )
            == 0
        ), stderr.getvalue()
        assert "Original Journal: Original clue" in stdout.getvalue()
        assert "Journal correction" in stdout.getvalue()
        assert "Postmortem deliberately skipped" in stdout.getvalue()
        assert "I trusted a blurry photo" in stdout.getvalue()


def test_search_match_opens_one_shot_timeline(qtbot, journal):
    _, _, operations = journal
    saved = operations.one_shots.create(request())
    corrected = operations.one_shots.correct(
        saved,
        replace(saved.record.effective, resolution_notes="Retyped measurement"),
        note="Typo in field note",
    )
    screen = OneShotDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(corrected)
    screen.show()
    hit = operations.search_predictions('"Typo in field note"').hits[0]
    screen.focus_search_match(hit.best_match.document)
    targets = [
        label
        for label in screen.findChildren(QLabel)
        if label.objectName().startswith("oneShotTimelineEvent")
        and label.property("searchMatchEmphasis") is True
    ]
    assert len(targets) == 1
    assert "Typo in field note" in targets[0].text()


def test_one_shot_journal_scope_and_search_refresh_on_detail_return(qtbot, journal):
    _, _, operations = journal
    saved = operations.one_shots.create(request())
    create_binary(operations, "Deadline tree question?", 70)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    screen = window._journal_screen
    screen._change(text="Tree height", filters=ArchiveQuery(mode=ArchiveMode.ONE_SHOT))
    qtbot.waitUntil(lambda: not screen.loading, timeout=10000)
    assert screen.page.total == 1
    applied = screen.state.request
    screen._open(saved.prediction_id, None)
    assert window.current_screen_name == "Prediction Detail"
    window.return_from_detail()
    qtbot.waitUntil(lambda: not screen.loading, timeout=10000)
    assert window.current_screen_name == "Journal"
    assert screen.state.request == applied
    assert screen.page.total == 1


def test_one_shot_journal_rows_keep_all_exact_values_at_minimum_width(qtbot, journal):
    _, _, operations = journal
    binary = operations.one_shots.create(request(answered=False))
    numeric = operations.one_shots.create(request(numeric=True))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.resize(920, 800)
    window.show()
    screen = window._journal_screen
    qtbot.waitUntil(lambda: not screen.loading, timeout=10000)
    assert {card.prediction_id for card in screen.cards} == {
        binary.prediction_id,
        numeric.prediction_id,
    }
    assert screen.scroll.horizontalScrollBar().maximum() == 0
    card = next(
        card for card in screen.cards if card.prediction_id == numeric.prediction_id
    )
    labels = card.findChildren(QLabel)
    assert any(
        label.text() == "Waiting for answer"
        for label in screen.cards[1].findChildren(QLabel)
    )
    for value in numeric.record.effective.quantiles.values:
        assert any(label.text() == str(value) for label in labels)


def test_one_shot_journal_times_are_readable_and_invalid_is_orange(qtbot, journal):
    _, _, operations = journal
    pending = operations.one_shots.create(request(answered=False))
    screen = OneShotDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(pending)
    assert (
        screen.invalid_button.property(ACTION_ROLE_PROPERTY) == ActionRole.CAUTION.value
    )
    assert (
        screen.delete_button.property(ACTION_ROLE_PROPERTY)
        == ActionRole.DESTRUCTIVE.value
    )

    journaled = operations.one_shots.add_journal(pending, "Original field note")
    corrected = operations.one_shots.correct_journal(
        journaled,
        journaled.journals[0].entry_id,
        "Corrected field note",
        expected_correction_id=None,
    )
    screen.show_prediction(corrected)
    timeline = screen.findChild(QWidget, "oneShotTimeline")
    assert timeline is not None
    rendered = "\n".join(label.text() for label in timeline.findChildren(QLabel))
    assert " at " in rendered
    assert not re.search(r"\d{2}:\d{2}:\d{2}|\.\d{6}|[+-]\d{2}:\d{2}", rendered)


def test_one_shot_journal_timeline_shows_current_text_and_reveals_matched_history(
    qtbot, journal
):
    _, _, operations = journal
    pending = operations.one_shots.create(request(answered=False))
    first = operations.one_shots.add_journal(pending, "Original field clue")
    entry_id = first.journals[0].entry_id
    second = operations.one_shots.correct_journal(
        first, entry_id, "Intermediate field clue", expected_correction_id=None
    )
    current = operations.one_shots.correct_journal(
        second,
        entry_id,
        "Final field clue",
        expected_correction_id=second.journals[0].current_correction_id,
    )
    screen = OneShotDetailScreen(operations)
    qtbot.addWidget(screen)
    screen.show_prediction(current)
    screen.show()

    timeline = screen.findChild(QWidget, "oneShotTimeline")
    card = screen.findChild(QWidget, f"oneShotJournalEntry{entry_id}")
    history = screen.findChild(QGroupBox, f"journalEntryEditHistory{entry_id}")
    body = screen.findChild(QLabel, f"oneShotJournalBody{entry_id}")
    assert timeline is not None and card is not None and history is not None
    assert body is not None and body.text() == "Final field clue"
    assert not history.isChecked()
    assert len(timeline.findChildren(QWidget, f"oneShotJournalEntry{entry_id}")) == 1
    assert screen.findChild(QWidget, "oneShotJournal") is None

    old_hit = operations.search_predictions(
        '"Original field clue"', include_superseded=True
    ).hits[0]
    screen.focus_search_match(old_hit.best_match.document)
    original = history.findChild(QLabel, f"journalEntryOriginalBody{entry_id}")
    assert history.isChecked() and original is not None
    assert original.property("searchMatchEmphasis") is True

    intermediate_hit = operations.search_predictions(
        '"Intermediate field clue"', include_superseded=True
    ).hits[0]
    screen.focus_search_match(intermediate_hit.best_match.document)
    intermediate = history.findChild(
        QLabel,
        f"journalCorrectionBody{second.journals[0].current_correction_id}",
    )
    assert intermediate is not None
    assert intermediate.property("searchMatchEmphasis") is True

    current_hit = operations.search_predictions('"Final field clue"').hits[0]
    screen.focus_search_match(current_hit.best_match.document)
    assert body.property("searchMatchEmphasis") is True


def test_independent_connection_cannot_overwrite_journal_correction(journal):
    path, _, operations = journal
    first = operations.one_shots.add_journal(
        operations.one_shots.create(request(answered=False)), "Initial reason"
    )
    another_database = Database.open(path)
    try:
        another = PredictionOperations(another_database, Clock(), UTC)
        same_entry = another.one_shots.get(first.prediction_id)
        changed = another.one_shots.correct_journal(
            same_entry,
            same_entry.journals[0].entry_id,
            "Repaired reason",
            expected_correction_id=None,
        )
        with pytest.raises(ApplicationError, match="changed"):
            operations.one_shots.correct_journal(
                first,
                first.journals[0].entry_id,
                "Conflicting repair",
                expected_correction_id=None,
            )
        assert operations.one_shots.get(first.prediction_id) == changed
        another_database.check_search_index()
    finally:
        another_database.close()


def test_tag_rename_updates_one_shot_retrieval_and_search(journal):
    _, database, operations = journal
    created = operations.one_shots.create(request())
    tag = next(
        item for item in operations.list_tags() if item.display_name == "outdoors"
    )
    assert tag.prediction_count == 1
    operations.rename_tag(operations.preview_tag_rename(tag.tag_id, "fieldwork"))
    assert operations.one_shots.get(created.prediction_id).tags == ("fieldwork",)
    assert [
        item.prediction_id
        for item in operations.browse_predictions(tags=("fieldwork",)).predictions
    ] == [created.prediction_id]
    assert not operations.search_predictions("outdoors").hits
    assert (
        operations.search_predictions("fieldwork").hits[0].prediction.prediction_id
        == created.prediction_id
    )
    database.check_search_index()


def test_one_shot_mode_scope_survives_backup_and_restart(journal, tmp_path):
    path, database, operations = journal
    create_binary(operations, "Tomorrow?", 70)
    one_shot = operations.one_shots.create(request())
    backup = tmp_path / "mode-backup.sqlite3"
    database.backup_to(backup)
    for target in (path, backup):
        recovered = Database.open(target)
        try:
            current = PredictionOperations(recovered, Clock(), UTC)
            assert [
                item.prediction_id
                for item in current.browse_predictions(
                    mode=ArchiveMode.ONE_SHOT
                ).predictions
            ] == [one_shot.prediction_id]
        finally:
            recovered.close()


def test_one_shot_stays_in_its_stable_or_development_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "reckonsolve.paths.QStandardPaths.writableLocation",
        lambda _location: str(tmp_path / QCoreApplication.applicationName()),
    )
    development = create_runtime(identity=DEVELOPMENT_APPLICATION)
    try:
        created = development.operations.one_shots.create(request())
        assert created.prediction_id == 1
    finally:
        development.close()
    stable = create_runtime(identity=STABLE_APPLICATION)
    try:
        assert not stable.operations.browse_predictions().predictions
    finally:
        stable.close()
    reopened = create_runtime(identity=DEVELOPMENT_APPLICATION)
    try:
        assert reopened.operations.one_shots.get(1).question == "Tree height?"
    finally:
        reopened.close()
