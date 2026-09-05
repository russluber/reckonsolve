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

The completed source release is v0.5. Its contract and Milestones 32 through 38 are defined in Section 33 of `docs/product-spec.md` and are complete. The approved v0.6 presentation release is now implemented through Milestone 43. Each remaining milestone still requires explicit authorization as one coherent vertical slice.

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

Milestones 13 through 20 in `docs/product-spec.md` are complete. Preserve the completed Binary and Numeric behavior rather than redesigning it incidentally.

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

Do not implement other Later features unless the user explicitly changes the scope in `docs/product-spec.md`.

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
- Numeric revisions require `lower <= median <= upper`, inclusive bounds, and whole-number confidence from 1% through 99%.
- Numeric values use an exact base-ten representation at the Prediction's immutable unit and precision; canonical storage must not use binary floating-point.

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

### Scoring

- Ordinary scoring uses exactly one final eligible type-appropriate forecast revision per resolved prediction.
- Never treat every revision as an independent resolved forecast.
- Exclude unresolved and Invalid predictions from all scoring and calibration calculations.
- Binary forecasts use Brier and binary calibration behavior.
- Numeric forecasts use inclusive containment calibration, median absolute error, and proper interval score as specified in Section 30.
- Unitless numeric containment calibration may combine units; raw numeric errors, widths, and interval scores must not be aggregated across unlike units.
- Test scoring selection rules separately from chart rendering.

### Deletion and data integrity

- Prefer Invalid over deletion once a prediction has meaningful history.
- Never silently erase legitimate historical records.
- Deletion and terminal lifecycle changes must be transactional and must not leave orphaned rows.
- Database migrations must preserve existing user data and be testable.

## UX Guardrails

- Creating a binary prediction requires only Question and Probability.
- Creating a numeric prediction requires Question, unit, precision, lower bound, median estimate, upper bound, and confidence; whole-number precision is the default.
- Rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags remain optional.
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
- multiple numeric intervals per revision, full numeric distributions, arbitrary quantile sets, automatic unit conversion, multiple-choice, date-distribution, or conditional forecasts;
- full Forecast Review sessions or anti-anchoring review modes beyond the explicit v0.2 Review record;
- Collections, structured Sources/Evidence, attachments, or prediction graphs;
- notifications or automatic reminders;
- log loss, Expected Calibration Error, probability bias, or advanced revision analytics;
- automatic probability decay; or
- infrastructure designed only for hypothetical future scale.
