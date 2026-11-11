# Journal/workspace checkpoint review — 2026-11-11

This records the first unreleased redesign slice at source commit `671d50c`,
following the earlier implementation and typography/appearance checkpoints.
It records the requested user walkthrough and automated evidence, with the
limits below. It is not a release or acceptance of the complete redesign.

Current requirements: [product specification](../../product-spec.md#3810-authorized-first-implementation-slice).
Current structure: [architecture](../../architecture.md).
Repeatable review procedure: [disposable visual profiles](../../maintainer/development.md#disposable-visual-review).

## Reported user review

The user evaluated injected disposable profiles and reported these checks passed:

- Journal browsing, readable and clickable Questions, and five-value Numeric rows.
- Enter/Search submission, invalidation of prior results while editing, and empty search results.
- Filters Apply/Cancel, retained constraints, and Reset View.
- Prediction Detail return to Journal and Performance/Settings source returns.
- Light/dark switching and window resizing in the requested representative walkthrough.
- Entered work retained across Adaptive/One-Shot creation switches; Keep editing versus whole-task discard and return to the original Detail.
- Ordinary Adaptive creation returning to Journal, with subsequent creation inputs cleared.
- Answered One-Shot creation opening answered Detail, with subsequent creation inputs cleared.
- Empty Journal presentation and its New action.

The user then accepted the requested refinements: aligned, larger Question
headings; more responsive appearance switching; matching 10–90 Binary creation
presets in both modes; and a fully readable New label. The final two refinements
were rechecked and accepted on 2026-11-11.

## Automated evidence

The final source suite passed **1,096 tests in 226.21 seconds**, with no failures,
errors or skips. The code tested is now committed at `671d50c`; this record and
status updates are documentation only and do not constitute a new runtime run.
Ruff check/format, public documentation links and whitespace checks passed.

Coverage includes controlled-clock and independent-connection history/scoring
regressions, checked Journal snapshots, source/version navigation, creation
guards, One-Shot preset retention without saving, and focused/unfocused New
label geometry in both palettes and larger fonts. Disposable native SQLite
tests cover reviewed recovery, rollback/WAL exclusion, cached older writers,
cancelled/failed/interrupted upgrades and supported four-contract history.
Applied migrations 1–20 remain identical to the pre-slice source.

Qt captures used actual widgets rendered offscreen with installed Windows fonts.
They informed tuning and supplement the user's native review. Temporary databases,
preferences, captures, logs and XML results remain untracked.

## Limits and remaining integration

The requested walkthrough is accepted; it is not exhaustive manual coverage of
every lifecycle, historical passage, error, input method or Windows scale.
The complete 100%/150%/200% Windows matrix and broader content/draft/history cases
remain explicit criteria for the affected screen slices and final integration.
Passing earlier evidence must not be attributed to later screen changes.

The 2,000-Prediction corpus retained full matching counts and bounded rows, but
the automatic-search latency budget was not met. Explicit Enter/Search submission
is the adopted behavior. Earlier timings and offscreen appearance timings do not
promise a particular native response time.

Creation, Detail, Performance and Settings retain their scoped integration bodies;
their remaining redesign requirements are not claimed complete here. Schema 21,
search projection 3 and CSV format 6 describe the unreleased working tree; the
published v0.8.0 baseline remains separate. No personal journal was used as a
fixture, upgraded or relocated, and no installed-tool replacement, packaging,
release, commit or push was performed by the agent during verification.
