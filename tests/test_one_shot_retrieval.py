"""M58 retrieval and reflection across existing local read and write paths."""

import re
from dataclasses import replace
from datetime import UTC, date
from io import StringIO

import pytest
from PySide6.QtCore import QCoreApplication, QPoint, Qt
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QWidget
from supported_fixtures import create_binary
from test_one_shot_persistence import Clock, request

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.cli import create_runtime, run
from reckonsolve.data.database import Database
from reckonsolve.domain.browser import ArchiveDateMeaning, ArchiveMode, ArchiveQuery
from reckonsolve.domain.saved_views import SavedViewConfiguration
from reckonsolve.domain.search import SearchMatchMode, SearchSourceKind
from reckonsolve.identity import DEVELOPMENT_APPLICATION, STABLE_APPLICATION
from reckonsolve.ui.main_window import MainWindow
from reckonsolve.ui.screens import OneShotDetailScreen
from reckonsolve.ui.visual_system import ACTION_ROLE_PROPERTY, ActionRole


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


def test_one_shot_archive_mode_and_search_context_survive_detail_return(qtbot, journal):
    _, _, operations = journal
    operations.one_shots.create(request())
    create_binary(operations, "Deadline tree question?", 70)
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.show()
    window.navigate_to("Predictions")
    browser = window._prediction_browser_screen
    browser.mode_filter.setCurrentIndex(
        browser.mode_filter.findData(ArchiveMode.ONE_SHOT.value)
    )
    browser.search_input.setText("Tree height")
    browser.refresh()
    assert browser.results_list.count() == 1
    old_snapshot = browser._loaded_snapshot
    browser._open_item(browser.results_list.item(0))
    assert window.current_screen_name == "Prediction Detail"
    window.return_from_detail()
    assert window.current_screen_name == "Predictions"
    assert browser.mode_filter.currentData() == ArchiveMode.ONE_SHOT.value
    assert browser.search_input.text() == "Tree height"
    assert browser._loaded_snapshot is old_snapshot


def test_one_shot_result_rows_fit_badges_and_wrapped_numeric_text(qtbot, journal):
    _, _, operations = journal
    binary = operations.one_shots.create(request(answered=False))
    numeric = operations.one_shots.create(request(numeric=True))
    window = MainWindow(operations)
    qtbot.addWidget(window)
    window.resize(1200, 800)
    window.show()
    window.navigate_to("Predictions")
    results = window.findChild(QListWidget, "predictionBrowserResults")
    assert results is not None and results.count() == 2
    qtbot.wait(20)

    for width in (1200, 920):
        window.resize(width, 800)
        qtbot.wait(20)
        for prediction_id in (binary.prediction_id, numeric.prediction_id):
            item = next(
                results.item(index)
                for index in range(results.count())
                if results.item(index).data(Qt.ItemDataRole.UserRole) == prediction_id
            )
            row = results.itemWidget(item)
            assert row is not None and row.layout() is not None
            for name in (
                f"predictionResultType{prediction_id}",
                f"predictionResultStatus{prediction_id}",
            ):
                badge = row.findChild(QLabel, name)
                assert badge is not None
                assert badge.mapTo(row, QPoint(0, badge.height())).y() <= row.height()
                assert badge.contentsRect().height() >= badge.fontMetrics().height()
            extra_height = item.sizeHint().height() - row.layout().heightForWidth(
                row.width()
            )
            assert 0 <= extra_height <= 4

    numeric_forecast = window.findChild(
        QLabel, f"predictionResultForecast{numeric.prediction_id}"
    )
    assert numeric_forecast is not None
    assert numeric_forecast.text().count("\n") == 2


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


def test_saved_view_mode_round_trips_through_cli_restart_and_backup(journal, tmp_path):
    path, database, operations = journal
    deadline = create_binary(operations, "Tomorrow?", 70)
    one_shot = operations.one_shots.create(request())
    configuration = SavedViewConfiguration(
        search_text="",
        match_mode=SearchMatchMode.ALL,
        include_superseded=False,
        archive_query=ArchiveQuery(mode=ArchiveMode.ONE_SHOT),
    )
    saved = operations.create_saved_view("One-Shots", configuration)
    assert saved.configuration.archive_query.mode is ArchiveMode.ONE_SHOT
    assert operations.list_saved_views() == (saved,)
    output = StringIO()
    assert run(["saved-views"], database_path=path, stdout=output) == 0
    assert "Mode: One-Shot" in output.getvalue()
    output = StringIO()
    assert (
        run(
            ["saved-view", "--id", str(saved.saved_view_id)],
            database_path=path,
            stdout=output,
        )
        == 0
    )
    assert "Tree height?" in output.getvalue()
    assert "Tomorrow?" not in output.getvalue()

    backup = tmp_path / "mode-view-backup.sqlite3"
    database.backup_to(backup)
    recovered = Database.open(backup)
    try:
        recovered_operations = PredictionOperations(recovered, Clock(), UTC)
        assert recovered_operations.list_saved_views() == (saved,)
        assert [
            item.prediction_id
            for item in recovered_operations.browse_predictions(
                mode=saved.configuration.archive_query.mode
            ).predictions
        ] == [one_shot.prediction_id]
    finally:
        recovered.close()

    updated = operations.update_saved_view(
        saved.saved_view_id,
        replace(
            configuration,
            archive_query=ArchiveQuery(mode=ArchiveMode.DEADLINE),
        ),
    )
    assert updated.configuration.archive_query.mode is ArchiveMode.DEADLINE
    output = StringIO()
    assert (
        run(
            ["saved-view", "--name", "One-Shots"],
            database_path=path,
            stdout=output,
        )
        == 0
    )
    assert "Tomorrow?" in output.getvalue()
    assert "Tree height?" not in output.getvalue()
    assert [
        item.prediction_id
        for item in operations.browse_predictions(
            mode=updated.configuration.archive_query.mode
        ).predictions
    ] == [deadline.prediction_id]


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
