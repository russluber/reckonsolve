"""Measure deterministic search completeness on disposable synthetic data."""

from __future__ import annotations

import argparse
import platform
import sqlite3
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from reckonsolve.application.predictions import PredictionOperations
from reckonsolve.data.database import Database


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build a privacy-safe temporary search corpus and report observed "
            "retrieval times without imposing a cross-machine timing threshold."
        )
    )
    parser.add_argument(
        "--size",
        type=int,
        default=2_000,
        help="Number of synthetic Predictions to create (default: 2000).",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=5,
        help="Timed repetitions per query after one warm-up (default: 5).",
    )
    arguments = parser.parse_args()
    if arguments.size < 100:
        parser.error("--size must be at least 100")
    if arguments.repetitions < 1:
        parser.error("--repetitions must be positive")

    with TemporaryDirectory(prefix="reckonsolve-search-evaluation-") as directory:
        database = Database.open(Path(directory) / "evaluation.sqlite3")
        try:
            operations = PredictionOperations(database)
            started = perf_counter()
            prediction_ids = []
            for index in range(arguments.size):
                created = operations.create_prediction(
                    (
                        f"Will synthetic archive item {index:05d} reach marker "
                        f"memory{index:05d}?"
                    ),
                    index % 101,
                    rationale=(
                        f"Synthetic rationale for cohort {index % 25:02d} and "
                        f"batch {index % 10:02d}."
                    ),
                    tags=(f"Cohort-{index % 25:02d}",),
                )
                prediction_ids.append(created.prediction_id)
            build_seconds = perf_counter() - started
            database.check_search_index()

            with database.transaction() as connection:
                document_count = int(
                    connection.execute(
                        "SELECT COUNT(*) FROM prediction_search"
                    ).fetchone()[0]
                )

            target_index = arguments.size // 2
            target_id = prediction_ids[target_index]
            expected_cohort_count = sum(
                1 for index in range(arguments.size) if index % 25 == 7
            )
            cases = (
                (
                    "unique memory",
                    f"memory{target_index:05d}",
                    1,
                    target_id,
                ),
                ("broad archive", "synthetic archive", arguments.size, None),
                ("tag cohort", '"Cohort-07"', expected_cohort_count, None),
                ("no result", "nonexistentmemorytoken", 0, None),
            )

            observations: list[tuple[str, float, int]] = []
            for label, query, expected_count, expected_first in cases:
                operations.search_predictions(query)
                timings: list[float] = []
                result = None
                for _ in range(arguments.repetitions):
                    query_started = perf_counter()
                    result = operations.search_predictions(query)
                    timings.append((perf_counter() - query_started) * 1_000)
                if result is None or len(result.hits) != expected_count:
                    raise RuntimeError(
                        f"{label!r} returned an incomplete result set: "
                        f"expected {expected_count}."
                    )
                if (
                    expected_first is not None
                    and result.hits[0].prediction.prediction_id != expected_first
                ):
                    raise RuntimeError(
                        f"{label!r} did not rank its exact target first."
                    )
                observations.append((label, median(timings), expected_count))

            print("Reckonsolve synthetic search evaluation")
            print(f"Python: {platform.python_version()}")
            print(f"SQLite: {sqlite3.sqlite_version}")
            print(f"Predictions: {arguments.size}")
            print(f"Derived search documents: {document_count}")
            print(f"Corpus build: {build_seconds:.3f} seconds")
            for label, milliseconds, result_count in observations:
                print(
                    f"{label}: {milliseconds:.3f} ms median; "
                    f"{result_count} complete results"
                )
        finally:
            database.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
