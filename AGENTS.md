# Repository Instructions

## Start Here

- Read `docs/product-spec.md` in full before planning or implementing product behavior.
- Treat `docs/product-spec.md` as the source of truth for product scope, terminology, invariants, acceptance criteria, and implementation milestones.
- Read `docs/architecture.md` before changing system structure or dependency boundaries, and keep it aligned with the implementation.
- Treat this file as the source of truth for how to work in the repository.
- If a request conflicts with `docs/product-spec.md`, identify the conflict and ask the user whether the specification should change. Do not silently reinterpret the specification.
- If an implementation choice is listed as unresolved in `docs/product-spec.md`, do not bury an arbitrary decision in code. Surface the choice when its milestone requires it.

## Product Summary

This project is a personal, local-first forecasting journal for Windows. It is a fresh successor to Predlog, not an extension of the Predlog CLI codebase.

The application lets one user create binary and numeric probabilistic predictions, record reasoning, revise beliefs without rewriting history, resolve outcomes, and study calibration.

The governing product rule is:

> Let the user change their mind freely, but never let the application rewrite the fact that they used to think something else.

## Current Release Scope

The completed source release is v0.6.0. Its contract and Milestones 39 through 45, including Milestone 42A, are defined in Section 34 of `docs/product-spec.md` and are complete. Preserve its presentation-only boundary over schema version 15.

The v0.7.0 contract is approved for staged implementation in Section 35 of `docs/product-spec.md`, with accepted supporting rationale in the three v0.7 design documents linked there. Milestones 46 through 54 and M54A are implemented. M54B (legacy retirement) is implemented; M55 follows M54B and is unimplemented. Work on only the milestone or coherent slice the user explicitly authorizes; approving a specification or plan is not authorization to implement it.

The user-approved 2026-09-20 amendment in Section 35.3 supersedes earlier promises in this file and the design documents to maintain legacy support indefinitely. M54B removes legacy Binary and interval-v1 Numeric runtime workflows, preserve all existing v0.7 history, and refuse legacy-only or mixed databases without conversion, deletion, or partial loading. Keep shared mathematics, storage, and migration infrastructure required by supported models. Do not restore the retired runtime paths. The historical milestone descriptions below explain the current implementation and its earlier obligations; they must not cause a later agent to restore retired features after M54B. Any live test-data purge or reset requires separate explicit approval and validated targets; the approved plan is not that approval.

The v0.1 baseline includes:

- binary Yes/No forecasts;
- optional rationale and prediction metadata;
- immutable forecast revisions;
- journal entries;
- a chronological timeline;
- probability-history visualization;
- Open, Locked, Resolved, and Invalid lifecycle behavior;
- Dashboard, New Prediction, Prediction Detail, Predictions, Analytics, and Settings screens;
- tags, search, and filtering;
- Needs Attention and Ready to Resolve surfacing;
- Brier score, calibration, and clearly labeled Brier performance over time;
- backup and CSV export; and
- visual identity, development-data isolation, and a private Windows frozen-build validation.

v0.2 adds:

- one central numeric prediction interval per immutable revision;
- signed, exact, fixed-precision quantities with a stable unit;
- a required median estimate and 1% through 99% confidence;
- type-aware creation, revision, journal, timeline, visualization, lifecycle, resolution, browsing, attention, and analytics behavior;
- Forecast Reviews that retain an unchanged Binary or Numeric forecast without creating a fake revision; and
- type-aware backup, CSV export, migration, and private-build hardening.

Milestones 13 through 20 in `docs/product-spec.md` are historical completed work. Preserve shared history guarantees, but their legacy model workflows have been retired by M54B.

v0.3 adds:

- paired `reckonsolve-cli` and `reckonsolve-cli-dev` source commands, plus their `rsc` and `rscd` executable shortcuts, sharing their matching GUI database identities;
- standard-library command parsing with no new production dependency;
- type-aware, side-effect-free `list` with combined Question/status/type/tag filters and attention indicators;
- type-aware `show` with exact current detail, terminal facts, timeline, Journal correction history, Reviews, and Definition history;
- interactive `create binary` and `create numeric` workflows using the existing atomic application operations;
- GUI-matching defaults of 50% Binary probability, zero Numeric decimal places, and 80% Numeric confidence;
- optional initial rationale, metadata, dates, and tags with cancellation and validation guaranteed not to create partial history;
- type-aware interactive `revise`, `journal`, and `review` commands that display current context and reuse the existing immutable-history, lifecycle, deadline, anchor, freshness, and optimistic-concurrency operations;
- intentionally single-line CLI rationale, Journal, and Review-note prompts without restricting multiline desktop or canonical stored text; and
- confirmed type-aware `resolve`, `invalidate`, and guarded `delete` commands that preserve exact scoring-revision capture, Numeric precision, Invalid exclusion, one-way terminal state, and untouched-Open deletion rules;
- CLI backup and format-version-two CSV export through the existing verified transfer operations; and
- cross-interface hardening for simultaneous reads, sequential writes, lock/stale-context failures, restart, migration, and stable/development isolation.

Milestones 21 through 25 in `docs/product-spec.md` are complete. Preserve the shared application-operation and canonical SQLite boundaries rather than adding direct CLI SQL or a synchronization subsystem. Treat any post-v0.3 feature work as a new explicitly authorized milestone or coherent vertical slice.

v0.4 adds schema-version-13 append-only terminal corrections and Postmortem completion; confirmed desktop correction and later-Postmortem workflows; type-aware resolved-prediction scorecards; filtered initial-versus-final feedback; the Resolved-only Needs Postmortem queue and Skip completion; historically complete CLI `show`; format-version-three relational CSV export; and migration, backup, cross-interface, and private-build hardening. Milestones 26 through 31 are complete. Preserve original terminal records, timestamps, scoring-revision capture, and one-observation-per-Prediction scoring throughout.

v0.5 adds schema-version-14 rebuildable SQLite FTS5 search; explainable desktop and CLI retrieval across current and optional superseded text; rich archive filters and deterministic sorting; schema-version-15 dynamic Saved Views; transactional tag rename, merge, and deletion; explicit search repair; and migration, relevance, backup, recovery, cross-interface, and private-build hardening. Milestones 32 through 38 are complete. Preserve canonical-history authority, grouped source provenance, stable tag references, dynamic rather than stored Saved View membership, and repairable derived search state.

v0.6 Milestone 39 adds one UI-only, palette-aware visual-system boundary with shared semantic colors, native-font typography, spacing, radii, interaction/focus/disabled states, action roles, text badges, persistent-message treatments, and restrained motion limits. New Prediction and Forecast Review are its representative page and dialog; palette changes refresh both semantic styling and local Lucide icons. Preserve this centralized presentation boundary during Milestones 40 through 45; do not scatter widget-local colors/fonts, import domain/data behavior into it, add a theme framework, or persist visual state in canonical SQLite.

v0.6 Milestone 40 adds the application-shell hierarchy: New Prediction is a prominent action; Dashboard, Predictions, and Analytics are permanent primary destinations; Settings is a bottom utility; and Prediction Detail is contextual with a source-aware return path. Expanded/icon-only compact sidebar mode and safe normal-window geometry/maximized state are stored outside SQLite in identity-scoped presentation settings. Preserve in-memory Predictions query, filter, Saved View, result, selection, and scroll context when returning from Detail; keep hidden compact labels available through accessible names and tooltips; never restore a minimized window or unsafe off-screen geometry.

v0.6 Milestone 41 adds shared page headers, raised content panels, textual count/status badges, explicit empty states, and persistent message regions to Dashboard and Settings. Dashboard rows remain type-aware and now expose overlapping attention labels visibly; Settings retains selectable recovery facts and persistent backup/export destinations and failures. A shell-level notification host carries only routine, already-verifiable acknowledgments without page reflow, pauses around interaction and modal dialogs, coalesces repeats, and never participates in an application transaction. Preserve this success/persistent-error/decision boundary during later presentation milestones.

v0.6 Milestone 42 applies that shared presentation grammar to Binary and Numeric creation, Detail, and every existing focused dialog. Creation keeps its minimum fields visually primary and optional details collapsed. Detail consistently separates identity/current forecast, routine forecast work, secondary lifecycle/destructive actions, optional metadata, terminal facts, causal timeline, and type-specific history charts; empty optional metadata and collapsed correction/definition history retain their earlier behavior. Dialogs share headings, labels, reviewed-context surfaces, persistent inline errors, and primary/secondary actions without changing validation, concurrency, lifecycle, confirmation, or atomic-save behavior. Preserve selectable user-authored/history text and the distinction among Forecast revisions, Journal entries, and Forecast Reviews.

v0.6 Milestone 42A completes Numeric Edit Details parity through the established type-neutral metadata transaction and a shared type-aware dialog. Numeric users can edit Question, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags in every lifecycle while unit and precision remain visible immutable context. Preserve tailored protected-field confirmations, Definition history, atomic tag/search maintenance, and stale-version safety while keeping Numeric forecast history, freshness, terminal facts, and scoring unchanged. The slice adds no schema migration or CLI metadata command.

v0.6 Milestone 43 applies the shared page, panel, action, badge, and persistent-message grammar to Predictions and tag management. Search, two-column Common filters, compact Detailed filters, and Saved View controls appear in that stable order inside a controls pane sized to fit without scrolling at the normal maximized workspace; the pane remains independently scrollable when space is genuinely constrained. In the narrow stacked layout, wheel movement over a closed archive dropdown or date editor scrolls that pane without silently changing or focusing a filter; an opened dropdown retains its normal scrolling behavior, and deliberate click or keyboard focus remains available. Detailed tag filtering uses searchable available-tag completion, reveals available unselected tags when its empty field is engaged, and represents selections as removable wrapping chips while preserving the established multi-tag All/Any query. Results remain independently visible beside the controls at normal widths, the splitter enforces useful minimum widths for both panes, and they stack at narrow widths. Archive and search rows share a type-aware Question/forecast/lifecycle/tag/date hierarchy; entering Predictions leaves the primary Search field neutral, while a mouse click or keyboard activation opens Detail without automatic initial selection. Preserve every v0.5 query, ranking, provenance, Saved View, tag-transaction, repair, and matched-context rule.

v0.6 Milestone 44 completes the presentation rollout in Analytics and cross-application keyboard/accessibility behavior. Analytics keeps its v0.5 observation, calculation, filter, and nonvisual-summary facts inside responsive shared panels, with side-by-side plot/table pairs at normal widths and stacked pairs when narrow. Guarded global shortcuts perform only navigation, explicit Search/Question focus, sidebar toggling, and contextual Back, and remain suppressed during active editing or modal decisions. Preserve visible focus, logical tab order, accessible descriptions, local tooltips, and text alternatives without moving analytical rules into widgets.

v0.6 Milestone 45 closes the source release without a migration or product expansion. Automated compatibility coverage snapshots every schema-version-15 application and derived row around presentation-only use. The relocated private build verifies packaged styles/icons, safe shell defaults, expanded/compact navigation, all primary screens, both Detail types, shortcuts, responsive sizes, search, backup, repair, restart, and unchanged canonical data. `tools/run_visual_review.py` supplies disposable empty, representative, and long-text profiles for the recorded human palette/scaling/layout matrix without opening either real user database.

v0.7 Milestone 46 adds schema version 16 and a presentation-independent prospective-contract foundation. Every existing and currently creatable Prediction receives an explicit immutable legacy model/scoring identity; no legacy record receives a fabricated exact Deadline, effective Resolution time, quantile, trajectory, or new score. Pure domain values validate timezone-aware exact instants, `T > t0`, strictly monotonic pre-Deadline revisions, `C = min(R, T)`, and closed cohort dispatch. The schema reserves new-model exact Resolution facts and type-specific append-only effective-time correction chains, but no GUI or CLI workflow creates a new-model Prediction until its complete vertical slice. Preserve ADRs 0014 and 0015, the linked Rulebook, and this legacy/new boundary during Milestones 47 through 55.

v0.7 uses the two supported forecasting contracts below; M54B supersedes its initial legacy-compatibility promise. Every new Binary or Numeric Prediction receives a durable model/scoring identity, a mandatory exact immutable Forecast Deadline, and separate effective-resolution and recorded-at instants. New Binary Predictions use duration-weighted Trajectory Brier with Binary-only neutral truncation after early resolution. New Numeric Predictions use the fixed q05/q25/q50/q75/q95 model, exact WIS, calibration-first feedback, and continuous-style or whole-number semantics. Every archive containing a pre-v0.7 Prediction is refused without conversion, deletion, or partial loading; never infer exact times, quantiles, trajectories, or new scores for it.

Do not implement other Later features unless the user explicitly changes the scope in `docs/product-spec.md`.

v0.7 Milestone 47 switches public GUI/application/CLI Binary creation to the trajectory contract with an explicit immutable exact Deadline; Numeric creation remains legacy interval-v1. New Binary revision and Review commits recheck the clock after obtaining transaction access, and the exact Deadline governs Detail, Dashboard, archive/search status, and deletion. Deadline display is read-only in metadata editing; local calendar archive filters use its local date without changing the committed instant. Keep the private legacy fixture seed out of all normal creation entry points. CSV format 3 rejects new-model databases until M55 rather than silently omitting contract facts. Complete SQLite backup remains available. Preserve this export guard until its replacement slice is implemented.

v0.7 Milestone 48 completes trajectory Binary Resolution, effective-time corrections, and individual scorecards across desktop and CLI. `analytics/trajectory.py` derives exact microsecond-duration segments and Fraction-valued scores from one canonical history snapshot; no score, neutral revision, or replacement scoring-revision pointer is persisted. For this cohort only, the original captured revision ID is recording context, not scoring authority. Resolution samples recorded-at under transaction; `use recording time` uses that same sample. Corrections may change outcome, text, or effective time but never recorded-at; outcome/time changes require a reason, and effective time cannot exceed original recorded-at. Schema 17 adds a read-only Binary correction union and search/Postmortem integration without rewriting either correction chain. Timeline exclusions and explicit `R <= t0` no-score states preserve all history. Trajectory records are excluded from legacy aggregate analytics until M49 supplies their separate view. Preserve ADR 0017 and the exact legacy/new scoring boundary.

v0.7 Milestone 49 adds separate trajectory Binary aggregate analytics without a migration. Complete trajectory inputs are read with the legacy sources in one SQLite snapshot, individual paths reuse the exact M48 scorer, and each eligible resolved Prediction contributes one equal vote to mean Trajectory Brier regardless of window duration. Early-versus-Deadline counts, mean Active Forecast Fraction, Initial/Final/Hold-initial means, and Updating Gain directions are explicitly diagnostic; Updating Gain is mechanical hindsight, not causal evidence. Final-probability calibration uses one last standing probability strictly before the effective cutoff and is never labeled trajectory calibration; neutral truncation creates no observation. Legacy Binary aggregates remain visibly and mathematically separate, while Forecast type and tag filters cover both cohorts. Invalid and `R <= t0` records contribute no score or calibration observation.

v0.7 Milestone 50 adds schema 18 and the internal five-quantile Numeric foundation without switching public creation. `numeric_quantile_definitions` fixes the value constraint, and `numeric_quantile_revisions` stores all five exact scaled values in one immutable row. Shared Journals, Reviews, and Numeric Resolutions have an explicit quantile-revision anchor, with one model-appropriate reference enforced by ownership and current-revision guards. Preserve every legacy interval row and anchor. `domain/quantiles.py` validates ordering, ties, fixed precision, integrality, and complete changed replacements; `analytics/quantiles.py` derives Fraction-valued WIS, decomposition, strict effective-cutoff selection, and Initial/Final/Delta WIS for one Prediction only. Search and causal timeline foundation reads preserve quantile anchors. Public GUI/CLI Numeric creation remains interval-v1 until M51; terminal workflows remain M52. Preserve ADR 0018 and the CSV format-3 guard until M55.

v0.7 Milestone 51 switches public Numeric creation to five-quantile v2 with an explicit value constraint and permanent exact Deadline. Desktop and CLI share complete changed revisions, retained-forecast Reviews, anchored Journals/corrections, immutable-definition metadata context, and model-aware archive/search/attention reads. The native central CDF interpolates only between elicited anchors and has an exact text alternative. Keep legacy interval creation private to fixtures and preserve legacy editors/history/lifecycle. New-model Numeric Resolution remains explicitly unavailable until M52; schema 18, full SQLite backup, and the CSV-3 guard are unchanged.

v0.7 Milestone 52 completes individual five-quantile Numeric Resolution, desktop corrections, and desktop/CLI WIS scorecards without a migration. Recording samples time under the write transaction, validates exact precision/integrality, and retains the current quantile anchor only as audit context. Analytics reads contract, definition, complete revisions, and effective terminal history in one snapshot and selects strictly before `min(R, T)`; `R <= t0` remains explicitly unscored. Actual-value/time changes require an explanation and append to the existing quantile correction chain, never changing recorded-at. Search, archive terminal dates, and Postmortem completion use current effective facts. Keep raw WIS and Delta within one Prediction, legacy aggregates separate, five-quantile aggregate calibration staged until M53, and the CSV-3 guard intact until M55.

v0.7 Milestone 53 adds five-quantile Numeric aggregate calibration without a migration. All four cohort sources are read in one SQLite snapshot; new Numeric observations reuse the individual strict-cutoff scorer and effective corrected actual value exactly once. Continuous-style and whole-number groups remain separate: five inclusive frequencies with pointwise 95% Wilson intervals versus strict/inclusive tie bands, plus inclusive 50%/90% outcome balances and median ties. Initial-versus-Final feedback counts only eligible revised pairs by exact WIS direction; sequence-one final forecasts are separately unrevised. Never add raw WIS/Delta averages, synthetic confidence bins, interpolated CDF observations, or Numeric trajectory metrics. Preserve legacy analytics, shared type/tag/exact-unit filtering, schema 18, and the CSV-3 guard until M55.

v0.7 Milestone 54 hardens four-cohort desktop/CLI parity without a migration. Startup and cohort-filtered archive, Dashboard, search, and aggregate reads reject unsupported or mismatched model/scoring identities rather than silently dropping records. Both launchers report unsupported database contracts clearly. Numeric CLI detail and mutation context expose the scoring identity, and Numeric prompts retain immutable unit, precision, and value-constraint context. Independent-connection tests cover all four cohorts, exact offset input, read-only retrieval, dynamic Saved Views, tag transactions, effective/superseded corrected text, repair, stale edits, and lock-at-commit rollback. No CLI metadata/correction command, synchronization subsystem, or score calculation was added. Preserve schema 18 and the CSV-3 guard until M55.

M54A is the user-authorized pre-M55 Analytics presentation/documentation slice, extended by feedback to resolved Prediction Detail scorecards. The Trajectory Binary summary uses flat, top-aligned Score, Timing, and Updating groups rather than nested metric cards; narrow layouts stack without changing any statistic. Individual scorecards use grouped selectable facts and contextual help; Numeric draws the final scored 50%/90% intervals, median, and effective actual on a shared scale with exact text alongside it. `docs/analytics-guide.md` is the human-facing interpretation guide, with worked examples, cohort boundaries, tie/uncertainty cautions, and actionable review habits. Keep explanations there rather than adding a long tutorial inside Analytics. This slice adds no calculation, schema, cohort, or CLI behavior; M55 remains separately authorized work.

M54B retires legacy runtime behavior under ADR 0019 without a new schema version or canonical rewrite. The application accepts supported v0.7-only archives and staged supported Binary schema-16/17 upgrades, but refuses legacy-only, mixed, missing-identity, unknown, or mismatched inputs before migration/repair/write. Tests and disposable tooling must use explicit supported contracts; historical raw fixtures exist only for refusal/migration-infrastructure tests. Shared exact math, storage, and historical SQL remain; legacy editors/calculators must not be reintroduced to make an old test pass. CSV format 3 stays guarded until M55. No live database purge is authorized. Earlier milestone descriptions in this file are historical, not a second runtime support contract.

## Technology Direction

- Use Python managed by `uv`.
- Build the desktop interface with PySide6.
- Use SQLite as the canonical data store.
- Target native Windows development and eventual packaging; v0.5 does not require a normal installer, separately packaged CLI executable, or public binary distribution.
- Keep core behavior fully functional offline.
- Keep the architecture proportionate to a single-user local desktop application.
- Do not add an ORM, migration framework, GUI framework, charting library, packaging system, or other production dependency casually. Prefer existing dependencies; when a new dependency is necessary, explain the need and tradeoff.
- Do not introduce a web server, browser frontend, REST API, GraphQL API, hosted service, authentication system, or cloud database.

## Architecture Boundaries

- Keep presentation code thin. Widgets, dialogs, and CLI commands should invoke application/domain operations rather than contain persistence or scoring rules.
- Keep domain rules independently testable without launching the GUI.
- Isolate SQLite access behind a clear data-access boundary.
- Keep analytics code separate from presentation code.
- Prefer straightforward modules and explicit data flow over speculative abstractions, plugin systems, service containers, or infrastructure for hypothetical scale.
- Avoid circular dependencies. Lower-level domain and data modules must not depend on PySide6 UI modules.
- Store runtime data outside the source tree in an appropriate per-user application-data location.
- Never use a real user database in automated tests.

## Non-Negotiable Domain Invariants

### Forecast history

- A saved Binary or Numeric ForecastRevision is immutable.
- A binary probability change or numeric interval/median/confidence change always appends a new revision; it never updates an earlier revision in place.
- Type-specific forecast values belong to the immutable revision, not as the sole canonical value on `Prediction`.
- The current forecast is derived from the latest valid eligible type-appropriate revision.
- Creating a prediction and its first revision is atomic.
- Opening or cancelling a revision form must not create a revision.
- Numeric revisions contain exactly q05/q25/q50/q75/q95; arbitrary-confidence interval-v1 revisions are retired.
- Numeric values use an exact base-ten representation at the Prediction's immutable unit and precision; canonical storage must not use binary floating-point.
- Every new v0.7 Prediction has an immutable stored model identity and scoring-contract identity; application version and `metadata_version` are not substitutes.
- Every new v0.7 Forecast Deadline is an exact immutable instant strictly after the first revision. New-model revisions are system-timestamped, strictly ordered, and rejected at or after that Deadline.
- Every new v0.7 Numeric revision contains exactly q05, q25, q50, q75, and q95 with `q05 <= q25 <= q50 <= q75 <= q95`. Equality is valid; crossing is rejected without silent sorting.

### Journal entries

- A journal entry records reasoning or evidence without changing Binary or Numeric forecast values.
- Adding a journal entry must not create a forecast revision.
- A journal entry records which forecast revision was current when it was created.
- A journal entry does not reset the Needs Attention clock.

### Lifecycle

- Forecast Deadline and Expected Resolution are separate concepts.
- Open predictions accept type-appropriate forecast revisions and journal entries.
- Locked predictions reject normal type-appropriate forecast revisions but accept journal entries.
- Resolved and Invalid predictions reject normal forecast revisions.
- Invalid predictions remain in history and are excluded from scoring.
- Ready to Resolve and Needs Attention are attention classifications, not additional canonical lifecycle states.
- Staleness may change how a prediction is displayed, but it must never alter its forecast values.
- New v0.7 Resolutions distinguish effective resolution time from immutable recorded-at. Scoring uses the effective instant and an audited effective-time correction may change scoring selection without rewriting any ForecastRevision.

### Scoring

- Ordinary scoring uses exactly one final eligible type-appropriate forecast revision per resolved prediction.
- Never treat every revision as an independent resolved forecast.
- Exclude unresolved and Invalid predictions from all scoring and calibration calculations.
- Binary forecasts use Brier and binary calibration behavior.
- Numeric forecasts use five-quantile WIS and the continuous-style/whole-number calibration contract in Section 35; Section 30 describes retired behavior.
- Unitless numeric containment calibration may combine units; raw numeric errors, widths, and interval scores must not be aggregated across unlike units.
- Test scoring selection rules separately from chart rendering.
- Binary Trajectory Brier applies only to its explicit v0.7 cohort, uses exact standing durations and the fixed initial-to-Deadline denominator, and uses 0.25 neutral truncation only after early effective resolution.
- Numeric five-quantile WIS applies only to its explicit v0.7 cohort and uses the final revision strictly before `min(effective_resolution_at, Forecast Deadline)`. It has no neutral truncation or Numeric trajectory score.
- Never average legacy and new-model scores silently. Never average raw WIS or WIS improvement across heterogeneous Numeric questions merely because their unit labels match.

### Deletion and data integrity

- Prefer Invalid over deletion once a prediction has meaningful history.
- Never silently erase legitimate historical records.
- Deletion and terminal lifecycle changes must be transactional and must not leave orphaned rows.
- Database migrations must preserve existing user data and be testable.

## UX Guardrails

- Do not restore legacy editors or partial loading of unsupported archives. Only the current trajectory Binary and five-quantile Numeric workflows are supported.
- New v0.7 Binary creation requires Question, Probability, and Forecast Deadline. New Numeric creation requires Question, unit, precision, value constraint, q05, q25, q50, q75, q95, and Forecast Deadline.
- Rationale, Background, Resolution Criteria, Expected Resolution, and tags remain optional. Exact Forecast Deadline is required and immutable.
- Do not force the user to enter boilerplate Resolution Criteria for self-evident questions.
- Keep Question and the type-appropriate forecast values visually primary during creation.
- Favor a calm desktop-journal interface over a dense trading or enterprise dashboard.
- Make the current type-appropriate forecast and lifecycle state immediately legible.
- Hide or de-emphasize empty optional sections.
- Use plain language and avoid false precision.
- Confirm destructive or historically consequential actions.
- Preserve keyboard-friendly workflows where practical.

## Working Method

- Work on one specification milestone or one coherent vertical slice at a time.
- Before editing, inspect the relevant code, tests, current Git status, and applicable part of `docs/product-spec.md`.
- For a complex or ambiguous task, propose a short plan before implementation.
- Prefer the smallest complete change that produces user-visible value and preserves the architecture.
- Do not refactor unrelated code as part of a focused feature or fix.
- Do not modify `docs/product-spec.md` unless the user explicitly asks to change the product specification.
- When implementation reveals a consequential product ambiguity, stop and ask rather than expanding scope.
- Preserve existing user changes in a dirty working tree.
- Do not commit, tag, push, publish a release, or rewrite Git history unless the user explicitly asks.

### UI/UX milestone collaboration

For v0.6 visual-system and application-shell work, and for later presentation-heavy work unless the user directs otherwise, use this feedback loop:

1. Before implementing a milestone, summarize the intended visible changes in plain language and surface any consequential unresolved choices. Do not begin a broad visual rollout while its basic direction remains undecided.
2. Implement one complete, usable slice and run the narrow relevant automated checks. Preserve existing product behavior unless the applicable specification explicitly changes it.
3. Give the user a focused manual checklist for `uv run reckonsolve-dev`. Explain what should look or behave differently, what must remain unchanged, and which edge states deserve attention.
4. Treat the user's visual judgment as an acceptance input that automated tests cannot replace. Screenshots and informal reactions such as **I like**, **This feels wrong**, and **I'm unsure about** are sufficient; translate them into concrete implementation changes.
5. Make agreed visual tuning and rerun relevant checks before asking the user to commit the milestone. Do not defer known spacing, hierarchy, legibility, or interaction problems merely because the underlying operation works.
6. After the user accepts the slice, report the final verification and provide a working commit message. The user remains responsible for adding, committing, and pushing unless they explicitly ask otherwise.

Milestone 39 is the visual-language checkpoint. Establish and obtain feedback on representative colors, spacing, typography, surfaces, button roles, and focus treatment before propagating that language throughout the application. Milestones 40 and 42 require especially deliberate user feedback because they change the navigation shell and the core creation/Detail experience. Milestone 43 requires careful regression feedback because it restyles the already successful search and archive workflow. Settle major taste and hierarchy questions during Milestones 39 through 44; Milestone 45 is release hardening and should not be the first point at which a broad redesign is evaluated.

Use the development identity and development database for these manual iterations. Never ask the user to expose or risk the stable personal database merely to evaluate a visual change. Routine tuning of padding, color intensity, typography, or control weight does not require a product-specification edit when it remains inside the approved contract. A requested change to navigation meaning, workflow, persistence, history, or other product behavior does require explicit authorization and an aligned `docs/product-spec.md` update before implementation.

## Python and Code Quality

- Use the Python version pinned by the repository.
- Manage dependencies and commands through `uv`; do not maintain a parallel `requirements.txt` unless explicitly required.
- Commit `uv.lock` whenever an intentional dependency change modifies it.
- Use type hints for new application and domain code.
- Prefer small functions and explicit names over clever compression.
- Keep business rules out of Qt signal handlers.
- Use `pathlib` for filesystem paths.
- Centralize time acquisition so time-dependent behavior can be tested deterministically.
- Avoid global mutable application state.
- Handle expected user-facing failures with clear messages; do not suppress unexpected exceptions silently.

## Testing

- Add or update tests for every behavior change.
- Every bug fix should include a regression test when practical.
- Test domain and analytics behavior without the GUI when possible.
- Use `pytest-qt` for behavior that genuinely requires Qt interaction.
- Use temporary directories and temporary SQLite databases in tests.
- Do not rely on network access, the user's clock, or the user's local application data.
- Prioritize tests for immutable revisions, transactions, lifecycle boundaries, scoring selection, date-based attention rules, migrations, backup consistency, and persistence across restart.
- Cover edge cases described in `docs/product-spec.md`, including a single revision, repeated equal probabilities, inclusive numeric bounds, exact signed decimals, missing optional dates, and boundary-time transitions.

Once the corresponding tools are configured in the repository, use these standard checks:

```text
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Run the narrowest relevant tests during iteration, then the full suite before declaring a milestone complete.

## Documentation

- Keep `README.md` focused on what the application is and how a human installs, runs, tests, and packages it.
- Keep durable product decisions in `docs/product-spec.md`.
- Keep implemented system structure and dependency direction current in `docs/architecture.md`.
- Record consequential technical decisions in `docs/decisions/` when the reasoning will matter later; follow `docs/decisions/README.md`.
- Update documentation when setup commands, architecture, persistence behavior, or user-visible behavior changes.
- Do not create documentation that merely repeats the code or duplicates large portions of `docs/product-spec.md`.

## Repository Hygiene

- Do not commit `.venv/`, caches, build output, packaged executables, local databases, backups, exports, logs, or other generated runtime data.
- Do commit source code, tests, migration files, documentation, configuration, and `uv.lock`.
- Never store secrets or machine-specific absolute paths in tracked files.
- Keep sample or fixture databases clearly separated from real application data.
- Avoid destructive Git or filesystem commands unless the user explicitly requests them and the exact target has been verified.

## Definition of Done

A change is complete only when:

1. it satisfies the requested behavior and the relevant `docs/product-spec.md` acceptance criteria;
2. product invariants remain intact;
3. relevant automated tests pass;
4. the full test suite passes when feasible;
5. lint and formatting checks pass once configured;
6. database changes include a safe migration and migration tests when applicable;
7. the user-visible workflow has been exercised end to end when practical;
8. documentation is updated where behavior or setup changed; and
9. the final report states what changed, how it was verified, and any remaining limitation or decision.

## Prohibited Scope Expansion

Unless explicitly authorized through a change to `docs/product-spec.md`, do not add:

- accounts, authentication, profiles, or multiple users;
- cloud sync, hosted storage, or required network access;
- social sharing, comments, groups, leaderboards, tournaments, or crowd forecasts;
- web/PWA architecture or an application API;
- multiple Numeric intervals or quantiles beyond the fixed v0.7 q05/q25/q50/q75/q95 model, arbitrary quantile sets, complete parametric distributions or invented outer tails, automatic unit conversion, multiple-choice, date-distribution, or conditional forecasts;
- full Forecast Review sessions or anti-anchoring review modes beyond the explicit v0.2 Review record;
- Collections, structured Sources/Evidence, attachments, or prediction graphs;
- notifications or automatic reminders;
- log loss, Expected Calibration Error, probability bias, or advanced revision analytics;
- automatic probability decay; or
- infrastructure designed only for hypothetical future scale.
