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

The application lets one user create binary probabilistic predictions, record reasoning, revise beliefs without rewriting history, resolve outcomes, and study calibration.

The governing product rule is:

> Let the user change their mind freely, but never let the application rewrite the fact that they used to think something else.

## Current Release Scope

The current target is v0.1, the minimum viable product.

v0.1 includes:

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
- Windows packaging.

Do not implement numeric forecasting or Forecast Reviews in v0.1. Both are reserved for v0.2.

Do not implement other Later features unless the user explicitly changes the scope in `docs/product-spec.md`.

## Technology Direction

- Use Python managed by `uv`.
- Build the desktop interface with PySide6.
- Use SQLite as the canonical data store.
- Target native Windows development and packaging.
- Keep core behavior fully functional offline.
- Keep the architecture proportionate to a single-user local desktop application.
- Do not add an ORM, migration framework, GUI framework, charting library, packaging system, or other production dependency casually. Prefer existing dependencies; when a new dependency is necessary, explain the need and tradeoff.
- Do not introduce a web server, browser frontend, REST API, GraphQL API, hosted service, authentication system, or cloud database.

## Architecture Boundaries

- Keep UI code thin. Widgets and dialogs should invoke application/domain operations rather than contain persistence or scoring rules.
- Keep domain rules independently testable without launching the GUI.
- Isolate SQLite access behind a clear data-access boundary.
- Keep analytics code separate from presentation code.
- Prefer straightforward modules and explicit data flow over speculative abstractions, plugin systems, service containers, or infrastructure for hypothetical scale.
- Avoid circular dependencies. Lower-level domain and data modules must not depend on PySide6 UI modules.
- Store runtime data outside the source tree in an appropriate per-user application-data location.
- Never use a real user database in automated tests.

## Non-Negotiable Domain Invariants

### Forecast history

- A saved `ForecastRevision` is immutable.
- A probability change always appends a new revision; it never updates an earlier revision in place.
- Probability belongs to `ForecastRevision`, not as the sole canonical value on `Prediction`.
- The current forecast is derived from the latest valid eligible revision.
- Creating a prediction and its first revision is atomic.
- Opening or cancelling a revision form must not create a revision.

### Journal entries

- A journal entry records reasoning or evidence without changing probability.
- Adding a journal entry must not create a forecast revision.
- A journal entry records which forecast revision was current when it was created.
- In v0.1, a journal entry does not reset the Needs Attention clock.

### Lifecycle

- Forecast Deadline and Expected Resolution are separate concepts.
- Open predictions accept forecast revisions and journal entries.
- Locked predictions reject normal forecast revisions but accept journal entries.
- Resolved and Invalid predictions reject normal forecast revisions.
- Invalid predictions remain in history and are excluded from scoring.
- Ready to Resolve and Needs Attention are attention classifications, not additional canonical lifecycle states.
- Staleness may change how a prediction is displayed, but it must never alter its probability.

### Scoring

- Ordinary scoring uses exactly one final eligible forecast revision per resolved prediction.
- Never treat every revision as an independent resolved forecast.
- Exclude unresolved and Invalid predictions from Brier and calibration calculations.
- Test scoring selection rules separately from chart rendering.

### Deletion and data integrity

- Prefer Invalid over deletion once a prediction has meaningful history.
- Never silently erase legitimate historical records.
- Deletion and terminal lifecycle changes must be transactional and must not leave orphaned rows.
- Database migrations must preserve existing user data and be testable.

## UX Guardrails

- Creating a binary prediction requires only Question and Probability.
- Rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags remain optional.
- Do not force the user to enter boilerplate Resolution Criteria for self-evident questions.
- Keep Question and Probability visually primary during creation.
- Favor a calm desktop-journal interface over a dense trading or enterprise dashboard.
- Make the current probability and lifecycle state immediately legible.
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
- Cover edge cases described in `docs/product-spec.md`, including a single revision, repeated equal probabilities, missing optional dates, and boundary-time transitions.

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
- numeric, multiple-choice, date-distribution, conditional, or full-distribution forecasts;
- Forecast Reviews or review sessions;
- Collections, structured Sources/Evidence, attachments, or prediction graphs;
- notifications or automatic reminders;
- log loss, Expected Calibration Error, probability bias, or advanced revision analytics;
- automatic probability decay; or
- infrastructure designed only for hypothetical future scale.
