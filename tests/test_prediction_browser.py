from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from reckonsolve.application.errors import ValidationError
from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database
from reckonsolve.domain.predictions import (
    BinaryOutcome,
    PredictionStatus,
    PredictionType,
)


@dataclass(frozen=True)
class FixedClock:
    instant: datetime

    def now(self) -> datetime:
        return self.instant


class CountingClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant
        self.calls = 0

    def now(self) -> datetime:
        self.calls += 1
        return self.instant


NOW = datetime(2026, 8, 20, 19, 30, tzinfo=UTC)


def test_browser_lists_every_lifecycle_with_current_forecast_and_tags(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    first = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).create_prediction(
        "Will the first remain Open?",
        20,
        tags=("Economy", "Long term"),
    )
    locked = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=1)),
        local_timezone=UTC,
    ).create_prediction(
        "Will this lock tomorrow?",
        40,
        forecast_deadline=NOW.date(),
        tags=("Economy",),
    )
    resolved_operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=2)),
        local_timezone=UTC,
    )
    resolved = resolved_operations.create_prediction("Will this resolve?", 60)
    resolved_operations.resolve_prediction(
        resolved.prediction_id,
        BinaryOutcome.YES,
        expected_revision_id=resolved.current_revision_id,
        expected_metadata_version=resolved.metadata_version,
    )
    invalid_operations = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(minutes=3)),
        local_timezone=UTC,
    )
    invalid = invalid_operations.create_prediction(
        "Will this become Invalid?",
        80,
        tags=("Archive",),
    )
    invalid_operations.invalidate_prediction(
        invalid.prediction_id,
        expected_revision_id=invalid.current_revision_id,
        expected_metadata_version=invalid.metadata_version,
    )

    snapshot = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        local_timezone=UTC,
    ).browse_predictions()

    assert [item.prediction_id for item in snapshot.predictions] == [
        invalid.prediction_id,
        resolved.prediction_id,
        locked.prediction_id,
        first.prediction_id,
    ]
    assert [item.status for item in snapshot.predictions] == [
        PredictionStatus.INVALID,
        PredictionStatus.RESOLVED,
        PredictionStatus.LOCKED,
        PredictionStatus.OPEN,
    ]
    assert [item.probability_percent for item in snapshot.predictions] == [
        80,
        60,
        40,
        20,
    ]
    assert snapshot.predictions[-1].tags == ("Economy", "Long term")
    assert snapshot.available_tags == ("Archive", "Economy", "Long term")
    database.close()


def test_browser_search_is_unicode_case_insensitive_and_question_only(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), local_timezone=UTC)
    matching = operations.create_prediction(
        "Will Straße construction finish?",
        55,
        background="This background says unrelated needle.",
    )
    operations.create_prediction("Will another project finish?", 45)

    by_question = operations.browse_predictions("  STRASSE  ")
    by_background = operations.browse_predictions("needle")

    assert tuple(item.prediction_id for item in by_question.predictions) == (
        matching.prediction_id,
    )
    assert by_background.predictions == ()
    database.close()


def test_browser_combines_status_and_unicode_tag_filters_with_search(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), local_timezone=UTC)
    expected = operations.create_prediction(
        "Will policy pass this year?",
        35,
        tags=("Économie",),
    )
    operations.create_prediction(
        "Will policy pass next year?",
        65,
        tags=("Other",),
    )

    snapshot = operations.browse_predictions(
        "THIS YEAR",
        status=PredictionStatus.OPEN,
        tag="éCONOMIE",
    )
    no_match = operations.browse_predictions(
        "THIS YEAR",
        status=PredictionStatus.RESOLVED,
        tag="éCONOMIE",
    )

    assert tuple(item.prediction_id for item in snapshot.predictions) == (
        expected.prediction_id,
    )
    assert no_match.predictions == ()
    assert no_match.available_tags == ("Other", "Économie")
    database.close()


def test_browser_uses_latest_revision_and_refreshes_after_restart(tmp_path) -> None:
    database_path = tmp_path / "reckonsolve.sqlite3"
    first_database = Database.open(database_path)
    first_operations = PredictionOperations(
        first_database,
        FixedClock(NOW),
        local_timezone=UTC,
    )
    created = first_operations.create_prediction(
        "Will the browser survive restart?",
        30,
        tags=("Durability",),
    )
    first_operations = PredictionOperations(
        first_database,
        FixedClock(NOW + timedelta(hours=1)),
        local_timezone=UTC,
    )
    revised = first_operations.revise_forecast(
        created.prediction_id,
        70,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
    )
    first_database.close()

    second_database = Database.open(database_path)
    snapshot = PredictionOperations(
        second_database,
        FixedClock(NOW + timedelta(days=1)),
        local_timezone=UTC,
    ).browse_predictions(tag="durability")

    assert len(snapshot.predictions) == 1
    assert snapshot.predictions[0].probability_percent == 70
    assert snapshot.predictions[0].latest_revision_at == NOW + timedelta(hours=1)
    assert revised.current_revision_id > created.current_revision_id
    second_database.close()


def test_browser_excludes_retained_orphan_tags_from_filter_choices(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), local_timezone=UTC)
    created = operations.create_prediction("Delete this test?", 50, tags=("Orphan",))

    operations.delete_prediction(
        created.prediction_id,
        expected_revision_id=created.current_revision_id,
        expected_metadata_version=created.metadata_version,
        confirm_permanent_deletion=True,
    )
    snapshot = operations.browse_predictions()
    with database.transaction() as connection:
        retained_tags = connection.execute("SELECT display_name FROM tags").fetchall()

    assert snapshot.predictions == ()
    assert snapshot.available_tags == ()
    assert [row[0] for row in retained_tags] == ["Orphan"]
    database.close()


def test_browser_derives_lock_on_the_day_after_the_inclusive_deadline(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    created = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).create_prediction(
        "Will the status filter follow the deadline?",
        50,
        forecast_deadline=NOW.date(),
    )

    on_deadline = PredictionOperations(
        database,
        FixedClock(NOW),
        local_timezone=UTC,
    ).browse_predictions(status=PredictionStatus.OPEN)
    after_deadline = PredictionOperations(
        database,
        FixedClock(NOW + timedelta(days=1)),
        local_timezone=UTC,
    ).browse_predictions(status=PredictionStatus.LOCKED)

    assert tuple(item.prediction_id for item in on_deadline.predictions) == (
        created.prediction_id,
    )
    assert tuple(item.prediction_id for item in after_deadline.predictions) == (
        created.prediction_id,
    )
    database.close()


def test_browser_reads_the_clock_once_and_rejects_invalid_filters(tmp_path) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    clock = CountingClock(NOW)
    operations = PredictionOperations(database, clock, local_timezone=UTC)

    operations.browse_predictions()

    assert clock.calls == 1
    with pytest.raises(ValidationError) as search_error:
        operations.browse_predictions(123)  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as status_error:
        operations.browse_predictions(status="open")  # type: ignore[arg-type]
    with pytest.raises(ValidationError) as tag_error:
        operations.browse_predictions(tag=123)  # type: ignore[arg-type]
    assert search_error.value.field == "question_text"
    assert status_error.value.field == "status"
    assert tag_error.value.field == "tag"
    with pytest.raises(ValidationError) as type_error:
        operations.browse_predictions(prediction_type="numeric")  # type: ignore[arg-type]
    assert type_error.value.field == "prediction_type"
    database.close()


def test_browser_mixes_types_and_filters_numeric_without_losing_type_or_unit(
    tmp_path,
) -> None:
    database = Database.open(tmp_path / "reckonsolve.sqlite3")
    operations = PredictionOperations(database, FixedClock(NOW), local_timezone=UTC)
    binary = operations.create_prediction(
        "Will Binary remain visible?", 35, tags=("Mixed",)
    )
    numeric = operations.create_numeric_prediction(
        "How many Numeric items?",
        "items",
        0,
        2,
        5,
        9,
        90,
        tags=("Mixed", "Numbers"),
    )
    resolved_numeric = operations.create_numeric_prediction(
        "How many resolved Numeric items?",
        "items",
        0,
        1,
        2,
        3,
        80,
        tags=("Numbers",),
    )
    operations.resolve_numeric_prediction(
        resolved_numeric.prediction_id,
        2,
        expected_revision_id=resolved_numeric.current_revision.revision_id,
        expected_metadata_version=resolved_numeric.metadata_version,
    )

    all_rows = operations.browse_predictions()
    numeric_only = operations.browse_predictions(
        status=PredictionStatus.OPEN,
        tag="mixed",
        prediction_type=PredictionType.NUMERIC,
    )
    selected = operations.get_prediction_for_navigation(numeric.prediction_id)
    binary_selected = operations.get_prediction_for_navigation(binary.prediction_id)
    resolved_numeric_only = operations.browse_predictions(
        status=PredictionStatus.RESOLVED,
        prediction_type=PredictionType.NUMERIC,
    )

    assert {item.prediction_type for item in all_rows.predictions} == {
        PredictionType.BINARY,
        PredictionType.NUMERIC,
    }
    assert tuple(item.prediction_id for item in numeric_only.predictions) == (
        numeric.prediction_id,
    )
    row = numeric_only.predictions[0]
    assert row.probability_percent is None
    assert str(row.numeric_lower_bound) == "2"
    assert str(row.numeric_median_estimate) == "5"
    assert str(row.numeric_upper_bound) == "9"
    assert row.numeric_confidence_percent == 90
    assert row.numeric_unit == "items"
    assert selected.decimal_places == 0
    assert binary_selected.probability_percent == 35
    assert tuple(item.prediction_id for item in resolved_numeric_only.predictions) == (
        resolved_numeric.prediction_id,
    )
    database.close()
