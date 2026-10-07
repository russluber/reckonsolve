# Historical search benchmarks

Dated synthetic measurements retained from the search evaluation document. They are not cross-machine performance guarantees and do not imply One-Shot benchmark coverage. See the current [evaluation method](../maintainer/search-evaluation.md); v0.8 measurements and their Adaptive-only corpus limit are in [the validation record](releases/v0.8-validation.md#search-evaluation).

The v0.5 release run on 2026-08-28 used Python 3.13.5 and SQLite 3.47.1 with 2,000 Predictions and 6,000 derived fragments. Five timed repetitions produced:

| Scenario | Median retrieval | Complete results |
| --- | ---: | ---: |
| Unique remembered token | 32.961 ms | 1 |
| Broad two-word archive query | 187.837 ms | 2,000 |
| One cohort tag | 37.503 ms | 80 |
| No result, including suggestion check | 89.755 ms | 0 |

Building the corpus took 29.143 seconds; that one-time fixture construction is not an interactive retrieval measurement. The observed query results were complete and perceptibly immediate at a corpus deliberately larger than expected ordinary personal use. A future visibly sluggish or incomplete case should be reduced to a privacy-safe regression scenario before ranking or matching rules change.

The unchanged search contract was rerun for the v0.6 release candidate on 2026-09-05 using Python 3.13.5 and SQLite 3.47.1 with the same 2,000 Predictions, 6,000 derived fragments, and five timed repetitions:

| Scenario | Median retrieval | Complete results |
| --- | ---: | ---: |
| Unique remembered token | 32.551 ms | 1 |
| Broad two-word archive query | 185.502 ms | 2,000 |
| One cohort tag | 37.847 ms | 80 |
| No result, including suggestion check | 86.094 ms | 0 |

The v0.6 corpus build took 28.847 seconds. Every expected result remained complete, and retrieval stayed consistent with the recorded v0.5 baseline; the presentation release introduced no search-semantic or performance regression in this synthetic evidence.

The v0.7 candidate run on 2026-09-23 uses supported trajectory Binary creation rather than the retired test-only Binary helper. Python 3.13.5 and SQLite 3.47.1 produced 2,000 Predictions and 6,000 derived fragments. Five timed repetitions yielded:

| Scenario | Median retrieval | Complete results |
| --- | ---: | ---: |
| Unique remembered token | 43.001 ms | 1 |
| Broad two-word archive query | 231.492 ms | 2,000 |
| One cohort tag | 49.339 ms | 80 |
| No result, including suggestion check | 101.901 ms | 0 |

Corpus creation took 34.769 seconds. All expected results were complete. The timings are somewhat higher than earlier release runs, but remain well below a second on this deliberately large local corpus; they are observations, not a cross-machine service guarantee. A 100-Prediction disposable evaluation is now an automated smoke check so the benchmark cannot silently return to a retired creation path.
