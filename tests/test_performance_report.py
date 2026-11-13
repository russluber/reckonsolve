"""Whole-report read boundaries and reuse of the four canonical analytical contracts."""

from dataclasses import replace
from datetime import timedelta
from sqlite3 import DatabaseError

import pytest

from reckonsolve.application.errors import ApplicationError
from reckonsolve.application.performance import PerformanceRequest, Section
from reckonsolve.domain.journal import JournalRequest
from reckonsolve.domain.predictions import PredictionType


def test_report_matches_existing_four_populations_and_is_read_only(performance_archive):
    database, operations = performance_archive
    snapshots = [
        operations.get_prediction_for_navigation(row.prediction.prediction_id)
        for row in operations.journal.query(JournalRequest()).rows
    ]
    report = operations.performance.query(PerformanceRequest())
    sections = {r.section: r for r in report.sections}
    adaptive = operations.get_forecast_analytics()
    one = operations.get_one_shot_analytics()
    assert sections[Section.ADAPTIVE_BINARY].data == adaptive.trajectory_binary
    assert sections[Section.ADAPTIVE_NUMERIC].data == adaptive.quantile_numeric
    assert sections[Section.ONE_SHOT_BINARY].data == one.binary
    assert sections[Section.ONE_SHOT_NUMERIC].data == one.numeric
    for result in (
        sections[Section.ADAPTIVE_BINARY],
        sections[Section.ONE_SHOT_BINARY],
    ):
        expected = (
            result.data.scored_prediction_count
            if result.section is Section.ADAPTIVE_BINARY
            else result.data.resolved_count
        )
        assert sum(p.total for p in result.observed_yes) == expected
    assert report == operations.performance.query_independently(PerformanceRequest())
    after = [
        operations.get_prediction_for_navigation(row.prediction.prediction_id)
        for row in operations.journal.query(JournalRequest()).rows
    ]
    assert snapshots == after
    assert not database._require_connection().in_transaction


def test_tag_and_independent_unit_scopes_preserve_exact_contracts(performance_archive):
    _, operations = performance_archive
    initial = operations.performance.query(PerformanceRequest())
    tag = next(tag for tag in initial.tags if tag.display_name == "Detail review")
    request = PerformanceRequest(tag.tag_id, "items", "items")
    report = operations.performance.query(request)
    expected = operations.get_forecast_analytics(
        prediction_type=PredictionType.NUMERIC, tag=tag.display_name, unit="items"
    )
    assert report.sections[1].data == expected.quantile_numeric
    one = operations.get_one_shot_analytics(
        prediction_type=PredictionType.NUMERIC, tag=tag.display_name, unit="items"
    )
    assert report.sections[3].data == one.numeric
    changed = operations.performance.query(
        replace(request, adaptive_unit="missing exact unit")
    )
    assert changed.sections[1].error and changed.sections[1].data is None
    for index in (0, 2, 3):
        assert changed.sections[index] == report.sections[index]
    assert changed.request.adaptive_unit == "missing exact unit"


def test_verified_tag_deletion_falls_back_and_zero_result_existing_tag_stays(
    performance_archive,
):
    _, operations = performance_archive
    operations.create_prediction(
        "Only unresolved",
        50,
        forecast_deadline=operations._clock.now() + timedelta(days=30),
        tags=("No eligible results",),
    )
    empty_tag = next(
        t for t in operations.list_tags() if t.display_name == "No eligible results"
    )
    empty_report = operations.performance.query(PerformanceRequest(empty_tag.tag_id))
    assert empty_report.effective_tag_id == empty_tag.tag_id and not empty_report.notice
    assert all(
        getattr(r.data, "scored_prediction_count", getattr(r.data, "resolved_count", 0))
        == 0
        for r in empty_report.sections
    )
    tag = next(
        tag for tag in operations.list_tags() if tag.display_name == "Detail review"
    )
    operations.rename_tag(operations.preview_tag_rename(tag.tag_id, "Renamed review"))
    report = operations.performance.query(PerformanceRequest(tag.tag_id))
    assert report.effective_tag_id == tag.tag_id and not report.notice
    operations.delete_tag(operations.preview_tag_delete(tag.tag_id))
    report = operations.performance.query(PerformanceRequest(tag.tag_id))
    assert report.effective_tag_id is None and "deleted" in report.notice


def test_isolated_analytical_failure_is_not_false_empty_or_global_failure(
    performance_archive, monkeypatch
):
    _, operations = performance_archive

    def fail(*args, **kwargs):
        raise ApplicationError("Identified section failure")

    monkeypatch.setattr(
        "reckonsolve.application.performance.summarize_quantile_analytics", fail
    )
    report = operations.performance.query(PerformanceRequest())
    assert report.sections[1].error == "Identified section failure"
    assert report.sections[1].data is None
    assert all(
        r.data is not None
        for r in (report.sections[0], report.sections[2], report.sections[3])
    )


def test_storage_failure_does_not_infer_deleted_tag_or_broaden_scope(
    performance_archive, monkeypatch
):
    _, operations = performance_archive

    def fail():
        raise DatabaseError("Read failed")

    monkeypatch.setattr(
        operations.performance.repository, "get_performance_sources", fail
    )
    with pytest.raises(DatabaseError, match="Read failed"):
        operations.performance.query(PerformanceRequest(9999, "days", "minutes"))
