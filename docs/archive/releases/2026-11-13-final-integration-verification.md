# Final redesign integration verification — 2026-11-13

This is the unreleased [authorized final integration pass](../../product-spec.md#3814-authorized-final-integration-pass),
based on clean public `49b6ef4` (`ux-redesign`). The four requested slice walkthroughs
remain accepted with their recorded limits. This record separates the combined audit,
new source verification and pending final integrated human acceptance. It grants no
release, installed-tool replacement or personal-data operation.

## Audit and resulting changes

The contract/source/evidence review identified a keyboard-focus gap at a screen seam.
A Question → Detail → Performance → Settings → Performance → Detail → Journal
round trip ended with no focused widget after Journal replaced its results. Background
refresh of a focused Question lost keyboard access in the same way. Three focused
regressions failed before the repair; the asynchronous new-search preservation case
already passed.

Journal now restores focus after its current-generation results and browsing anchor
are laid out. It uses the original Question when that Question remains in the useful
visible vicinity, otherwise a current nearby Question, search, or a recognized error's
retry/repair control. A record moving in the sort order is not followed to the top;
current membership is unchanged. Another action during loading keeps focus. This
bookmark is transient presentation state, not a draft manager or navigation stack.
MainWindow requests restoration on source-aware Journal returns; the Journal owner
handles result replacement. Application/data/scoring responsibilities are unchanged.

Larger-text capture inspection also reproduced clipped Numeric percentile roles after
font/style changes at unchanged width. NumericInterval now coalesces parent and child
font/style notifications and recomputes label geometry after the final metrics apply.
Direct child-font and stylesheet regressions failed before their fixes. Values, tie
groups and proportional positions stay unchanged; the scrollable page supplies room.

The specification now clearly distinguishes the implemented source contract
(schema 21/projection 3/CSV 6 and accepted desktop slices) from published v0.8.0
(schema 20/CSV 5). Existing heading anchors and protected baseline rules remain.
The guides/architecture document actual behavior; this reconciliation introduces no
new forecast, scoring, upgrade, export or location policy.

## Combined evidence map

| Contract area | Implemented/evaluated evidence carried forward | Final-pass coverage |
| --- | --- | --- |
| Journal/search/history/recency | [Journal checkpoint](2026-11-11-journal-workspace-review.md), full corpus/ranking, faithful rows, current-generation reads/counts and historical targets | Keyboard return/replacement, disappearing sole match, current nearby focus after reordered revision, new-action focus retention |
| Creation and writing guards | [Detail/creation evidence](2026-11-11-prediction-detail-verification.md), four contracts, atomic save, retained forms, contextual editors and explicit discard | Combined keyboard navigation/source return; existing focused/full regressions carried forward |
| Detail lifecycle/history | Same record covers Open/Locked/Resolved/Invalid/Waiting, exact versions, corrections, long history, Overview/revision and eligible actions | Binary/Numeric baseline captures; dynamic font/style label reflow regressions; accepted responsiveness and pane transitions remain constraints |
| Performance | [Performance/Settings checkpoint](2026-11-12-performance-settings-verification.md), independent four sections, tag/unit/report state, empty/failure/retry and report sources | Detail → report → Settings → report → original Detail round trip |
| Settings/appearance/geometry | Same record plus [relocation checkpoint](2026-11-12-journal-relocation-verification.md), central tools, visit-local results and fixed bootstrap preferences | Both palettes in entered creation and page captures; supported baseline/scaled rendering; temporary managed review profile |
| Compatibility/recovery/CLI | Schema-21/source-action/CSV-6 and attention command evidence in the first slice; checked old-path/WAL/interruption/GUI/CLI resolution in the fourth | Full-suite regression, unchanged protected modules/migrations/dependencies; no personal upgrade/move |

No protected product-rule conflict or additional consequential product choice was
identified for this implemented package. Explicit Enter/Search submission remains the
accepted response to the 2,000-Prediction corpus latency limit; automatic live text
submission and the already deferred filter scope have not been enabled. This audit
is not a claim that every possible input/device/accessibility condition was tested.

## Verification

Initial focus-integration checks: **78 passed in 93.45 seconds**, before the later
Numeric metric-reflow repair. The separate integrated
profile test passed and verified an initial **41 Predictions**, all four mode/type
pairs, long-history examples, relocation controls and complete temporary-tree cleanup.
An intermediate full suite passed 1,215 tests before the subsequently discovered
Numeric metric-reflow repair. That is not final-source evidence. Metric-change/group
checks then passed six cases. Final full suite: **1,218 passed in 452.86 seconds**, with zero failures, errors
or skips. Ruff check and format passed (316 files). Documentation checked 325 public
local links across 56 Markdown files and 293 private links across five, with no errors.
The separate preservation audit verified 87 current public-reference mirrors, stable
private identifiers/withdrawals and unchanged reference assets. Application/data/
domain/analytics code, bundled assets, migrations and dependencies are unchanged.
Both repositories’ whitespace checks passed. Later results supersede exploratory
test/fixture failures.

Actual PySide6 6.11.1 widgets were rendered with installed Segoe UI at the supported
760 × 520 logical baseline. Separate offscreen Qt processes observed device-pixel
ratios **1.0 / 1.5 / 2.0**, capturing six page compositions in both palettes (36 captures),
plus 12/15-point Numeric Detail probes (six captures). Toolbar fit was checked at every
captured composition. Representative scaled Numeric Detail, Journal and Settings
captures were inspected; generated evidence stays ignored under `build/ux-integration/`.
These simulated Qt scale factors are not a complete human Windows display-scaling,
screen-reader or native file-dialog review. Previously recorded storage/power-loss,
retrieval-latency and device limits remain applicable.

## Bounded final native review

Run `uv run python tools/run_visual_review.py integrated`. The profile combines the
existing Detail/history and four-cohort Performance fixtures inside one temporary
managed development bootstrap. All changes/preferences and any move artifacts stay
in that temporary tree if its precreated destinations are used; closing the final
window discards the profile. No normal stable/development CLI is needed.

Use the [three-part combined checklist](../../maintainer/development.md#final-integrated-review)
to inspect keyboard source returns, entered-work guards/appearance, and usable
controls at your reviewed window/scale. Carry forward the four accepted slice
walkthroughs; do not repeat them in full. Record any mismatch and the Windows scale
actually reviewed. This final human gate is **pending**. Version/tag selection,
installed snapshots, packaging and publication are later, separately authorized work.

No personal journal, applied migration, scoring algorithm, search projection,
CSV format, production dependency or private visual reference changed. The agent
performed no staging, commit, tag, push or publication.

## Reported combined journey review — 2026-11-13

At saved public `fe6a3df`, the user reported that the combined journeys were checked
and worked well, then identified eight presentation/responsiveness refinements.
That is positive functional feedback, with final visual/responsiveness acceptance
still open. The [post-review refinement record](2026-11-13-workspace-refinement-verification.md)
owns the resulting work, fresh verification and focused recheck. Earlier source
counts/captures above remain evidence for their evaluated source, not later edits.
