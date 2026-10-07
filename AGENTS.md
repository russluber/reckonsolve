# Repository instructions

## Start here

- Read docs/product-spec.md in full before planning or implementing product behavior. It is authoritative for scope, terminology, invariants, acceptance criteria, and unresolved choices.
- Read docs/architecture.md before changing structure or dependency boundaries, and keep it aligned with implementation.
- This file governs how to work in the repository. User instructions take precedence.
- If a request conflicts with the specification, identify the conflict and ask whether it should change. Do not silently reinterpret it or bury an unresolved product choice in code.
- Work only on the explicitly authorized milestone or coherent slice. Approval of a plan/specification is not implementation authorization.

## Current product boundary

Reckonsolve v0.8.0 is a single-user, local-first Windows forecasting journal. M1-M60 are completed history, preserved in docs/archive/. New work requires separate authorization. Adaptive is the default; One-Shot is an additional mode within Binary/Numeric types.

- Preserve schema 20, the four closed model/scoring pairs, and canonical deadline/one_shot mode keys. Adaptive is the presentation name; CLI --mode deadline remains an alias for --mode adaptive.
- Refuse any archive containing a retired Binary-final or interval-v1 Numeric record, including mixed archives, before migration/repair/write. Missing, unknown, and mismatched identities are also refused without conversion, deletion, or partial loading.
- Preserve supported v0.7 history and staged supported schema-16/17 Binary upgrades. Historical SQL/shared storage are not permission to restore retired runtime workflows.
- Schema 19 owns One-Shot originals, reported times, and transcription snapshots under ADR 0021. Schema 20 adds only nullable, constrained dynamic Saved View mode persistence; existing views retain All modes.
- Search projection 3 is derived and repairable. CSV format 5 covers all four contracts; SQLite backup is complete recovery. CSV is analytical, not restorable.
- Live test-data purge, database reset, or bulk removal needs separate explicit approval and verified targets. No product plan or documentation cleanup grants that permission.

## Architecture and technology

- Use the pinned Python version and uv; keep uv.lock aligned with intentional dependency changes.
- Use PySide6 and standard-library SQLite; keep core behavior fully offline.
- Widgets and CLI invoke shared application operations. Keep validation, lifecycle, scoring, transactions, and persistence out of signal handlers and renderers.
- Domain and analytics remain independently testable without Qt; lower layers do not import UI modules. Isolate SQL behind the data boundary.
- Prefer straightforward modules, explicit data flow, type hints, pathlib, injected time, and clear expected-error handling. Avoid circular imports/global mutable state; never silently suppress unexpected exceptions.
- Do not casually add an ORM, migration/theme/chart framework, production dependency, cloud database, server, web frontend, API, or infrastructure for hypothetical scale. Explain a demonstrated need and obtain scope authorization where required.
- Runtime data lives outside source. Stable and development GUI/CLI identities remain isolated; tests never open either real user database.

## History and scoring safeguards

The governing rule is: let the user change their mind freely, but never rewrite the fact that they used to think something else.

- Saved forecasts, Reviews, Journal originals/corrections, Definition snapshots, terminal facts/corrections, and Postmortem completions are immutable. Initial creation and optional One-Shot answer are atomic.
- Adaptive belief changes append complete changed revisions. Reviews retain the forecast; Journals change neither forecast nor freshness. Cancel/no-op/invalid/stale/lock failures create no partial history.
- Numeric values use exact scaled base-ten quantities at immutable unit/precision/value constraint. Every forecast has exactly q05/q25/q50/q75/q95, ordered with ties allowed; never silently sort or round.
- Adaptive exact Deadline is immutable, after sequence one; revisions are system-timestamped, strictly ordered, and before Deadline. Reviews also stop there. Use transaction-time clock validation; never fabricate elapsed time.
- Adaptive Resolution separates immutable recorded-at from effective R, which cannot exceed original recorded-at. Cutoff is min(R,T); R<=t0 is unscored. Audited outcome/value/time corrections require explanations and never rewrite revisions.
- Binary Trajectory Brier uses exact standing durations and fixed initial-to-Deadline denominator, with Binary-only 0.25 neutral truncation after early resolution. Neutral truncation creates no forecast. Updating Gain is mechanical hindsight, not causal evidence.
- Adaptive Numeric WIS selects the last revision strictly before cutoff; there is no Numeric trajectory or neutral score. Preserve strict/inclusive whole-number ties, continuous-style calibration, and uncertainty.
- One-Shot has one original forecast and no Deadline, ordinary revision/Review, cutoff selection, updating attention, or trajectory metrics. Optional reported wall minutes are documentary, separate from app timestamps, and never gate or alter scores.
- One-Shot transcription corrections append complete snapshots, preserving originals and later-answer replay. Score pure Brier/WIS on effective corrected facts; count exactly one answered observation per Prediction.
- Unresolved/Invalid records never score. Modes never share score/calibration denominators. Do not pool raw WIS/Delta, even with matching unit labels.
- New Journals are nonterminal-only; body corrections remain transparent after terminal decisions, retaining original anchor and Timeline position. Current body appears once with collapsed history and matched-version search navigation.
- Terminal decisions are one-way. Postmortem/Skip are optional, preserved reflection/completion facts. Prefer Invalid over Delete; deletion is confirmed and transactionally restricted to untouched Open creation mistakes.

## UX and collaboration

- Keep Question and forecast inputs primary. Optional prose stays optional; do not force boilerplate criteria or timestamp evidence.
- Preserve the shared visual system, source-aware Back, archive context, safe geometry, accessible labels/focus/keyboard flow, selectable history, responsive layouts, and text alternatives for charts.
- Keep modes visually symmetric with reciprocal top-right actions. One-Shot language omits updating/deadline concepts.
- Use plain language and human-readable dates without changing canonical precision. Confirm destructive/historically consequential actions.
- For presentation work, implement a coherent slice, run focused checks, and give the user a focused manual checklist using development/disposable data. Human visual judgment is an acceptance input; fix agreed tuning before closing the slice.
- No stable personal data is needed to evaluate presentation. Routine visual tuning inside approved behavior does not require a spec change; workflow/persistence/meaning changes do.

## Working method

- Inspect Git status, relevant implementation/tests, and applicable spec sections before editing. Preserve user changes in a dirty tree.
- Prefer the smallest complete change preserving architecture. Do not refactor unrelated code.
- Modify product scope only when the user explicitly authorizes it. Surface consequential ambiguity rather than expanding scope.
- Do not commit, tag, push, publish, or rewrite Git history unless explicitly asked. The user owns those steps otherwise.
- Use the feedback loop for UI work; report changes, verification, and remaining limits clearly. Provide a commit message when requested or when closing an accepted implementation milestone.

## Verification

- Add/update meaningful tests for behavior changes and practical regression cases. Prefer pure domain/analytics tests; use pytest-qt for actual Qt behavior.
- Use temporary directories/databases and controlled clocks. Do not rely on network, personal data, or the user's clock.
- Cover history, atomic rollback, lifecycle/cutoff boundaries, exact signed quantities, ties, corrections, migrations/refusal, search, backup/export, restart, and independent connections.
- Run narrow checks during iteration and the full suite before closing an implementation milestone. Documentation-only changes need link/reference and diff checks; they do not require a new UI acceptance round or redundant runtime tests.

```text
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

See docs/maintainer/development.md for disposable visual profiles and private packaging, and docs/maintainer/release-checklist.md for source publication. Definition of done: authorized behavior/spec acceptance satisfied, invariants intact, relevant verification passed, safe migrations covered where applicable, documentation aligned, and final report states practical limits.

## Documentation

### Placement and authority

Before adding or moving documentation, read [the documentation index](docs/README.md) and the existing reference for that topic. Update its established home instead of creating a competing guide.

| Location | Responsibility |
| --- | --- |
| [README.md](README.md) | Short product introduction, installation/run commands, compatibility/recovery summary, and links. |
| [docs/README.md](docs/README.md) | User and maintainer reading paths; update when adding, moving, or retiring an indexed document. |
| [User guide](docs/guides/user-guide.md) | Desktop workflows, data locations, recovery, score/chart interpretation, uncertainty, worked examples, and review habits. |
| [CLI guide](docs/guides/cli-guide.md) | Terminal workflows, command examples, and GUI/CLI boundaries. |
| [Forecasting guide](docs/guides/forecasting-guide.md) | Admissibility, question formulation, and detailed Adaptive/One-Shot forecasting rules. |
| [Product specification](docs/product-spec.md) | Authoritative scope, invariants, acceptance criteria, unresolved choices, and active authorized plans. |
| [Architecture](docs/architecture.md) | Current implemented modules, dependency direction, persistence, and transaction boundaries. |
| [docs/decisions/](docs/decisions/README.md) | Consequential technical reasoning and current applicability/supersession notes. |
| [docs/maintainer/](docs/README.md#maintaining-reckonsolve) | Repeatable development, testing, search evaluation, release procedures, and detailed design references. |
| [docs/archive/](docs/archive/README.md) | Completed plans, earlier contracts, dated validation/acceptance, and historical drafts. |
| [CHANGELOG.md](CHANGELOG.md) | Maintained release summaries used to prepare GitHub release notes. |

AGENTS.md contains working policy and essential safeguards. Link to the spec for detailed product rules and the archive for release history. Keep the authoritative spec/architecture/ADR paths stable. Maintain user-facing guides in docs/guides/ with versionless filenames; versioned design/archive filenames identify their historical origins and do not require renaming for each app release.

### Writing and updating

- Update the affected guide when user behavior or commands change, the spec when an authorized product decision changes, and architecture when implemented structure changes. A documentation edit must not silently authorize a feature or override the spec.
- Link to the owning reference instead of copying its full rules or tutorial. Keep user instructions task-oriented and in plain language; keep detailed mathematics/design rationale in their established references.
- Keep the forecasting Rulebook and One-Shot rules in the forecasting guide, and analytics interpretation in the user guide. Link to their sections rather than recreating standalone Rulebook or Analytics guides.
- Document the actual interface: use current labels and valid command flags, distinguish Adaptive/One-Shot where their rules differ, and keep stable/development data identities explicit in examples.
- Separate proposed, implemented, manually accepted, and published status. Never describe a plan as shipped or old test evidence as verification of later edits. Avoid conversational debugging diaries and unverified test counts in current guides.
- Add a new guide only for a distinct audience or task that existing docs cannot reasonably cover. Do not add a docs framework, generated copies, or additional policy files without a demonstrated need.

### Current guidance and historical records

- Keep active plans with the governing specification. On completion, preserve any continuing requirements there and move historical planning/acceptance detail into the archive with a link. Completed milestones are not a new work queue or permission to implement.
- Keep architecture focused on the current system. Preserve important earlier reasoning in ADRs or clearly labeled archive records; do not rebuild chronological milestone appendices in active docs.
- Archive records must identify their version or stage and explain their historical scope. Retain relevant evidence and limits, including checks that preceded final changes. Avoid creating another full snapshot of active docs for routine edits; Git already retains file history.
- Preserve ADR reasoning. For partial supersession, update the applicability notes in the ADR index; for a fully replaced decision, mark it Superseded and link its successor. Historical compatibility promises never restore retired runtime support.
- Use CHANGELOG.md as the maintained release summary and prepare published notes from it. Keep reusable release steps in [the release checklist](docs/maintainer/release-checklist.md); put completed checklists and dated results in the archive. Historical note drafts are not parallel maintained release summaries.
- Keep an unpublished entry Unreleased until publication is verified; use the actual publication date in UTC and remove stale candidate/pending wording from current guides after release. Publication remains separately authorized.
- Archive files remain public and tracked on GitHub. Keep personal notes, generated audit reports, and runtime artifacts untracked. Rewriting Git history to remove previously published material requires separate explicit authorization.

### Documentation verification

- Check relative file links and heading anchors in changed documents and incoming references when moving/renaming files or headings. Use `rg` to find obsolete references, including bare/backticked paths that a Markdown-link check would miss.
- Verify new or changed command examples against parser/help output or disposable fixtures. State when verification only checked syntax; do not execute data-changing examples against either personal database.
- Review Markdown structure, readable headings, tables, and blank lines before lists. Use repository-relative links in tracked docs; avoid machine-specific absolute paths.
- Run `git diff --check` and inspect the diff for intended changes. Documentation-only edits need targeted link/reference/example checks; run runtime tests only when executable behavior changes or a concrete verification risk requires them.

## Repository hygiene

### File placement

Before creating any file, choose its established home. Extend an existing file when it already owns the topic, and follow the current package boundaries and documentation placement rules above.

| Material | Home |
| --- | --- |
| Application code, bundled resources, and migrations | The appropriate existing package under `src/reckonsolve/`. |
| Tests and reusable test fixtures/helpers | `tests/`. |
| Reusable development, evaluation, and release tools | `tools/`. |
| User instructions and explanations | Existing guides in `docs/guides/`. |
| Reusable development/release checklists and procedures | The appropriate existing document in `docs/maintainer/`; detailed design references belong in `docs/maintainer/design/`. |
| Active implementation plans and acceptance criteria | `docs/product-spec.md`. |
| Consequential technical decisions | `docs/decisions/`. |
| Completed release checklists and dated acceptance/validation evidence | `docs/archive/releases/`; other historical documentation belongs in `docs/archive/`. |
| Temporary reports, logs, screenshots, scratch scripts, and disposable test data/exports | Ignored `build/<task>/` or a system temporary directory; keep these untracked. |
| Persistent application data | The identity-scoped per-user application-data locations outside the repository, as defined by the architecture. |

Keep the repository root for established project entry points, configuration, README/CHANGELOG, repository policy, and root licenses/notices. Do not create task-specific checklists, reports, logs, or temporary folders there. Existing tools may retain their standard cache/build locations. When a distinct new document is justified, place it in the owning documentation directory and update the documentation index.

### Tracking and cleanup

- Commit source, tests, immutable migrations, docs, configuration, licenses/notices, and uv.lock. Do not commit environments, caches, bundles, databases, backups, exports, logs, secrets, machine-specific paths, or personal audit notes.
- Preserve root and bundled licenses/attribution records in their established locations; documentation cleanup must not remove required notices.
- Verify exact targets before destructive operations; avoid destructive Git/filesystem commands without explicit authorization.

## Outside current scope

Without an explicitly authorized specification change, do not add accounts/multiple users, cloud/social/mobile clients, synchronization, hosted/web/API architecture, extra forecast types/quantiles/distributions, automatic unit conversion, structured evidence/attachments/Collections/graphs, reminders, automatic probability decay, advanced scores, full review-session/anti-anchoring modes, import/conversion, public packaging/updaters, or speculative infrastructure.
