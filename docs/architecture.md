# Reckonsolve Architecture

Status: v0.6 implementation in progress through Milestone 40
Last reviewed: 2026-09-03

This document describes how Reckonsolve is structured from the completed binary v0.1 baseline through the completed v0.2, v0.3, v0.4, and v0.5 source releases and the implemented v0.6 visual-system and application-shell slices. The [product specification](product-spec.md) governs product behavior, scope, terminology, and acceptance criteria. This document translates those requirements into technical boundaries without replacing them.

## 1. Current implementation

Milestones 26 through 31 complete the v0.4 terminal-correction, scorecard, update-feedback, Postmortem, CLI-read, portability, and private-build work. Milestones 32 through 38 complete v0.5's presentation-neutral full-text retrieval, rich archive query, dynamic Saved Views, transactional tag maintenance, CLI parity, and release hardening on schema version 15. Milestone 39 begins v0.6 without a migration: `ui/visual_system.py` resolves semantic colors from the active Qt palette, builds one inherited stylesheet, defines shared spacing/radius/motion and relative native-font roles, and assigns reusable action, surface, badge, and persistent-message properties. `MainWindow` refreshes that boundary and the existing local Lucide icons after palette changes. New Prediction and Forecast Review are the representative page and dialog; their operations, signals, layout sequence, persistence, and validation remain unchanged, while the earlier search-match cue now uses the centralized semantic selector rather than a widget-local stylesheet. Milestone 40 restructures only the application shell: New Prediction is a prominent action, Dashboard/Predictions/Analytics are the permanent primary destinations, Settings is a bottom utility, and Prediction Detail is contextual with an explicit return path. Expanded or compact sidebar mode and safe normal-window geometry/maximized state live in a separate identity-scoped INI file beside the database, never in canonical SQLite.

| Area | Current state |
|---|---|
| Project management | `uv` project with Python 3.13 pinned in `.python-version` |
| Runtime dependency | PySide6 |
| Development tools | pytest, pytest-qt, and Ruff; pinned PyInstaller exists only in the separate `packaging` dependency group |
| Python package | `src/reckonsolve/` |
| Entry points | `reckonsolve` and `python -m reckonsolve` use the stable GUI identity; `reckonsolve-dev` uses the development GUI identity; `reckonsolve-cli`/`rsc` and `reckonsolve-cli-dev`/`rscd` provide matching v0.5 source CLI search, Saved View retrieval, and existing v0.4 commands; the private frozen entry adds only its disposable build-smoke path |
| Application runtime | `ApplicationRuntime` owns the GUI application, `Database`, identity-scoped presentation settings, and `MainWindow`; `CliRuntime` owns one command's database and operations without constructing the desktop UI; both close persistence deterministically |
| UI | The six existing screen routes remain functional over one centralized palette-aware visual foundation, while the M40 shell distinguishes one creation action, three permanent primary destinations, one bottom utility, and contextual Prediction Detail; the sidebar has complete expanded and icon-only compact modes, and Detail return preserves the originating primary context without refreshing the Predictions query; selected navigation and action icons remain local, palette-aware Lucide SVGs rendered through QtSvg while visible or accessible names remain authoritative |
| Runtime path | Stable uses `%LOCALAPPDATA%\Reckonsolve`; source development uses `%LOCALAPPDATA%\Reckonsolve Dev`; each identity keeps `presentation.ini` beside its database; tests and private smoke inject explicit disposable paths |
| Persistence | One standard-library `sqlite3` connection with foreign keys enabled, a five-second busy timeout, explicit immediate transactions, and an atomic pre-commit refresh of dirty derived search documents |
| Schema | Version 15 preserves all version-14 canonical and derived search data, and adds recoverable mutable Saved View configurations with stable tag references; version 14 remains the versioned, rebuildable FTS5 search projection, vocabulary, dirty-Prediction queue, and invalidation triggers |
| Domain and application operations | Complete v0.4 behavior plus safe search parsing and snippets, explainable per-source fragments, deterministic grouped ranking, All/Any matching, corpus spelling guidance, effective/history scope, one shared status/type/multi-tag/attention/date/sort archive query consumed by both desktop and CLI, mutable Saved View configuration operations, previewed transactional tag-library operations, presentation-ready forecast and effective terminal summaries, and explicit search check/rebuild operations |
| Analytics | Exactly-once type-aware scoring selection now carries both revision-one and captured-final context; ordinary scoring, scorecards, and retrospective paired feedback all reuse the latest effective outcome and original resolution time while preserving Binary/Numeric and exact-unit boundaries |
| Automated tests | Complete v0.1-v0.5 coverage plus focused M39 visual-system coverage and M40 shell tests for hierarchy, active routes, compact-mode accessibility and persistence, contextual return without archive refresh, keyboard operation, identity isolation, and safe window-state recovery |
| Windows distribution | A private PyInstaller `onedir` build is repeatable and smoke-validated; original icon artwork, installer, signing, shortcuts, uninstall, updates, and public distribution remain deferred |

The sections below preserve the implemented boundaries and historical evolution of the completed v0.1, v0.2, and v0.3 source releases.

## 2. Target v0.1 system context

Reckonsolve is a single-process Windows desktop application for one local user. It must remain fully functional without a network connection.

```text
User
  |
  v
PySide6 desktop UI
  |
  v
Application operations
  |          |          |
  v          v          v
Domain    Analytics   SQLite data access
 rules      rules           |
                             v
                   Per-user SQLite database
```

SQLite is the canonical store. Backup files and CSV exports are outputs derived from that store; neither replaces it. There is no server, browser frontend, remote API, authentication layer, cloud database, or synchronization service.

## 3. Architectural principles

### Historical integrity first

The architecture must make the honest path the easy path. Forecast changes append immutable revisions, and Journal corrections append immutable body versions while retaining the original entry context. Current state, lifecycle classifications, timelines, and analytics are derived from preserved records rather than maintained through destructive updates.

### Thin UI, testable core

Qt widgets collect input, display state, and invoke application operations. They do not own transaction boundaries, lifecycle rules, revision selection, scoring logic, or database queries. Core behavior must be testable without constructing a `QApplication`.

### Explicit persistence boundary

All SQLite access lives behind a small, explicit data-access boundary. The rest of the application should not scatter SQL across widgets or domain code. Reckonsolve does not need an ORM or a generic repository framework.

### Deterministic behavior

Revision ordering, scoring selection, lifecycle boundaries, and attention classifications must be deterministic. Time acquisition is centralized so tests can supply a fixed clock.

### Proportionate structure

This is a local, single-user desktop application. Prefer direct calls, small modules, explicit data flow, and transaction-focused operations over dependency-injection containers, event buses, plugin systems, background services, or infrastructure for hypothetical scale.

## 4. Target v0.1 logical boundaries

### UI

The PySide6 layer owns windows, screens, dialogs, Qt models, presentation formatting, and user interaction. It may validate basic form shape for immediate feedback, but authoritative validation and state transitions belong below the UI.

The desktop keeps six named screen routes, but M40 no longer presents all six as equal destinations. Dashboard, Predictions, and Analytics are the permanent primary navigation; New Prediction is a prominent action; Settings is a bottom utility; and Prediction Detail is contextual content reached from a source and exited through an explicit Back action. Revision, journal, resolution, invalidation, deletion, and metadata editing remain focused dialogs or secondary views.

M12 keeps the native Qt/Windows visual system rather than adding a theme framework. M39 adds one palette-relative Qt stylesheet and semantic presentation helpers on top of that native base; it does not add a theme selector, external theme package, proxy style, bundled font, or custom window frame. Navigation and high-value actions use a small selected set of local Lucide 1.33.0 SVGs rendered through QtSvg in normal, disabled, and selected palette colors. Visible action text is retained, accessible names remain meaningful, and palette changes re-resolve both semantic colors and remembered button/navigation icons. Font-aware chart sizing, existing scrollable forms, keyboard-native controls, and a minimum resizable main-window size avoid fixed-pixel screen layouts. [ADR 0008](decisions/0008-private-onedir-and-local-icons.md) records the resource and private-build approach.

The Prediction Detail probability-history widget is presentation code. It projects immutable revisions onto elapsed stored time, paints the fixed probability scale and sequence-ordered step geometry, and supplies an accessibility summary. It does not select scoring observations, infer probabilities, or persist chart state. [ADR 0004](decisions/0004-native-probability-history-chart.md) records the native rendering approach.

### Application operations

This layer coordinates complete user actions. An operation validates a request, applies domain rules, opens the required transaction through the data-access boundary, and returns either a result suitable for presentation or an expected application error.

Representative operations include:

- creating a prediction and its first revision;
- appending a forecast revision;
- adding a journal entry tied to the current revision;
- recording a Forecast Review tied to the unchanged current revision;
- appending a transparent correction to an existing journal entry;
- reading immutable forecast revisions in sequence order;
- reading a unified causal timeline;
- editing permitted prediction metadata;
- resolving or invalidating a prediction;
- appending and reading terminal correction history without changing lifecycle;
- recording a deliberate blank-Postmortem completion fact;
- listing and filtering predictions;
- searching grouped Predictions through explainable current or historical text fragments;
- rebuilding the derived local search index without modifying canonical history;
- producing analytics inputs;
- deriving one resolved Prediction's type-aware scorecard from its scoring observation;
- creating a consistent backup; and
- exporting CSV data.

An operation should describe a real use case rather than expose arbitrary table-level CRUD.

### Domain

The domain layer owns concepts and rules that can be evaluated independently of Qt and SQLite, including:

- probability validation;
- current-revision selection;
- Open, Locked, Resolved, and Invalid behavior;
- revision eligibility at a forecast deadline;
- Needs Attention and Ready to Resolve classification;
- permitted state transitions; and
- errors for disallowed actions.

Domain code must not import PySide6 or open database connections.

### Data access

The data layer owns connections, schema creation, migrations, SQL, row mapping, foreign-key behavior, and transactions. It provides purpose-specific reads and writes needed by application operations.

No normal data-access operation may update or delete a saved forecast revision, Journal entry, Journal correction, terminal record, terminal correction, or Postmortem completion. Migration code is the exceptional maintenance path and must preserve legitimate history. A deliberate future deletion of a parent Prediction may cascade to its complete child history transactionally.

### Analytics

Analytics code owns scoring selection and aggregation, separate from chart rendering. Its input is candidate prediction, resolution, and revision data obtained through the data-access boundary. It constructs exactly one scoring observation for each included resolved prediction by selecting that prediction's final eligible revision according to the product specification.

The analytics boundary contains:

- final-eligible-revision selection;
- per-prediction Brier calculation;
- mean Brier calculation;
- calibration bin assignment and aggregation;
- the explicitly labeled Brier-over-time series;
- inclusive Numeric interval containment and fixed confidence-bin aggregation;
- Numeric median absolute error, interval width, and proper interval score; and
- an exact-unit guard that prevents raw quantities from being averaged across unlike units.

Analytics chart code consumes analytics results; it does not decide which forecasts count. The Prediction Detail probability-history chart is separate: it consumes every immutable revision for one Prediction through the existing application query and performs presentation-only projection.

### Platform support

Small platform-facing modules should centralize concerns such as application-data paths, time acquisition, and application startup. Platform code must not become a second domain layer.

## 5. Dependency direction

Dependencies flow inward from presentation and orchestration toward rules and explicit infrastructure adapters:

```text
UI --> Application operations --> Domain
               |
               +-------------> Data access --> SQLite
               |
               +-------------> Analytics --> Domain values
```

Key restrictions:

- Domain and analytics modules do not depend on PySide6.
- Domain modules do not depend on SQLite or data-access modules.
- Widgets do not execute SQL or calculate scores.
- Data-access modules do not import UI modules.
- Shared types must live at the lowest sensible layer, not in the UI.
- Circular imports are architecture defects, not something to mask with late imports.

The application may use concrete data-access classes directly while the program remains small. Introduce protocols or interfaces only when they improve testing or allow a real alternative implementation; do not create them mechanically for every class.

## 6. Package shape

Milestone 14 implements this package structure:

```text
src/reckonsolve/
  __init__.py          paired stable/development GUI and CLI entry-point delegates
  __main__.py          `python -m reckonsolve` entry point
  app.py               QApplication composition, runtime ownership, and startup errors
  cli.py               argparse composition, paired CLI runtime, and command dispatch
  cli_creation.py      injectable prompts and atomic Binary/Numeric M22 creation orchestration
  cli_mutations.py     M23/M24 active-forecast and terminal prompt orchestration
  cli_text.py          shared terminal-control escaping for stored plain text
  cli_transfer.py      M25 destination prompting and verified transfer presentation
  clock.py             injectable clock and canonical UTC instant conversion
  identity.py          stable and visible development application identities
  paths.py             per-user and explicitly injected database paths
  private_build_smoke.py
                       disposable frozen UI, core-loop, backup, and restart probe
  application/
    errors.py          expected user-presentable operation and concurrency errors
    predictions.py     Binary workflows plus complete staged Numeric lifecycle operations
  analytics/
    numeric.py         pure Numeric containment, error, width, and interval-score calculations
    overview.py        type-aware composition without cross-type or cross-unit scores
    scoring.py         pure exactly-once Brier, calibration, and trend calculations
  domain/
    analytics.py       captured resolved-forecast facts shared by data and analytics
    attention.py       stale-threshold validation and derived Dashboard values/rules
    browser.py         current prediction summaries and archive-query results
    predictions.py     binary and numeric prediction, revision, resolution, metadata, status, and validation values
    saved_views.py     named mutable dynamic archive-configuration values and validation
    tags.py            retained tag-library items and reviewed rename/merge/delete consequences
    transfer.py        backup/export status and result values
  data/
    __init__.py        persistence package surface
    analytics.py       one-snapshot Binary and Numeric captured-scoring-revision source
    database.py        connection ownership and transaction boundary
    migrations.py      ordered schema registry, validation, and migration runner
    numeric_predictions.py
                       Numeric Prediction, interval/Journal history, terminal records, and guarded deletion
    predictions.py     purpose-specific prediction, history, terminal, tag, and deletion persistence
    saved_views.py     mutable Saved View configurations and stable tag-reference persistence
    tags.py            transactional global tag rename, merge, deletion, and relationship counts
    terminal_history.py
                       type-aware append-only terminal corrections, completion, and effective replay
    settings.py        singleton attention and backup-status setting access
    transfer.py        verified SQLite backup and relational CSV ZIP creation
  ui/
    __init__.py        UI package surface
    analytics_charts.py
                       native Binary reliability, Numeric containment, and Brier-trend painting
    analytics_screen.py
                       separate type views plus common type/tag and Numeric-unit filters
    dashboard.py       action buckets plus attention, backup, and export settings
    icons.py           palette-aware rendering for the selected Lucide resources
    main_window.py     application-shell hierarchy, contextual routing, and screen coordination
    presentation_settings.py
                       identity-scoped disposable sidebar and safe window-state persistence
    prediction_browser.py
                       type-aware full-text search, rich archive controls, and archive navigation
    probability_history_chart.py
                       native probability-history projection and painting
    numeric_history_chart.py
                       native Numeric interval-band and median-history painting
    screens.py         Binary/Numeric creation, type-specific Detail, history, lifecycle, deletion, and metadata UI
    tag_manager.py     secondary filtered tag library and confirmed global-maintenance dialogs
    visual_system.py   centralized palette colors, stylesheet, shared visual tokens, and semantic widget-role helpers
    assets/icons/      pinned selected Lucide SVGs and their upstream license
```

The checked-in `packaging/Reckonsolve.spec` and `tools/build_windows.ps1` live outside the import package. The spec defines only the private onedir bundle and explicitly collects UI resources and notices. Generated `build/` and `dist/` trees remain ignored.

Later milestones can extend these boundaries when real behavior requires it. Empty abstractions are not added merely to complete a diagram.

Tests should live under `tests/` and generally mirror the behavior boundary they exercise rather than mirror every source file mechanically.

## 7. Application composition and startup

The package-level entry point delegates immediately to `app.py`. Startup currently:

1. sets the supplied stable or development identity before creating or reusing the `QApplication`;
2. resolves that identity's Qt `AppLocalDataLocation`, unless an explicit database path was supplied;
3. opens one long-lived SQLite connection, enables foreign keys and the busy timeout, and applies pending migrations;
4. composes `PredictionOperations` with that database and a system UTC clock;
5. composes an identity-scoped `presentation.ini` store beside the database and constructs the six-route `MainWindow` with those operations and disposable shell settings;
6. returns an `ApplicationRuntime` that owns the Qt application, database, and window; and
7. shows the window and enters the Qt event loop.

The production runner catches expected path, migration, operating-system, and SQLite startup failures and presents a fatal database error. It does not replace or silently recreate an existing database. The runner's `finally` cleanup closes the database after the Qt event loop ends or if showing the window fails; close is idempotent.

`create_runtime()` accepts both an explicit identity and database path. Normal source work uses `reckonsolve-dev`, whose title and application name are **Reckonsolve Dev**; stable entry points retain **Reckonsolve**. Because path resolution happens only after setting that identity, Qt supplies distinct per-user directories without an ad hoc environment override. M40 derives `presentation.ini` from that already-resolved directory, so sidebar and window preferences are isolated by the same stable/development identities without entering SQLite, backups, exports, or CLI behavior. No startup path copies or migrates data between those channels. Tests never discover or open either real user database. The clock and application operations are composed at this boundary rather than through global state or widget-side service lookup; later operations should follow the same pattern.

M21 adds a parallel console composition in `cli.py`. `reckonsolve-cli` selects the stable **Reckonsolve** identity, while `reckonsolve-cli-dev` selects **Reckonsolve Dev**; each then resolves the same path its matching GUI uses. One invocation opens and migrates a `Database`, constructs `PredictionOperations`, dispatches one parsed command, and closes the database in `finally`. Help and version reporting finish before runtime composition and therefore open no database. Expected application, path, migration, operating-system, and SQLite failures return a clear nonzero result without replacing existing data.

The additional `rsc` and `rscd` package scripts point to those same stable and development CLI delegates. They are executable-name conveniences rather than new identities, parsers, command surfaces, or data locations. A non-editable `uv tool install .` can expose all package scripts user-wide without making an in-progress source checkout the implementation behind the installed stable commands.

The CLI uses the standard-library `argparse` module rather than adding a production dependency. Its presentation functions consume the existing archive, Dashboard-attention, type-aware Detail, timeline, and Definition-history read models. `list` combines the same Question, derived-status, forecast-type, and tag filters as the desktop browser, then adds Needs Attention and Ready to Resolve labels from the existing Dashboard query. `show` selects Binary or Numeric detail by stable Prediction identifier and renders optional metadata, terminal facts, exact fixed-precision values, every timeline event, Journal correction history, Reviews, and Definition changes. M37 adds `search QUERY`: it maps readable CLI choices for All/Any words, historical scope, repeated tag mode, status, type, attention, local-calendar range, and sort into the existing `search_predictions` application operation, then renders one grouped result per Prediction with the existing source label and a plain safe snippet. The CLI never compiles FTS syntax or ranks fragments itself. `saved-views` lists complete dynamic configurations; `saved-view --id` or `--name` resolves one retained configuration and calls the same `search_predictions` or `browse_predictions` operation that its saved text state requires. Terminal control characters in stored free text are escaped before output; stored instants use local ISO text with their offset and microsecond precision. No CLI function executes SQL or persists presentation state.

M22 adds `cli_creation.py` as an interactive presentation helper rather than placing prompt logic in application operations. Its injectable line-oriented session asks for all required values, optionally collects initial details, and calls exactly one existing Binary or Numeric creation operation after prompt-level validation. Binary probability defaults to 50; Numeric precision and confidence default to 0 and 80. Numeric input is validated through the existing fixed-precision domain values before persistence, while the application operation remains authoritative and revalidates the complete request. EOF or Ctrl+C raises a presentation-level cancellation before any creation operation runs. Expected domain failure returns nonzero, and the existing transaction guarantees that no parent or first revision is left behind. Successful output contains the stable Prediction identifier and exact type-appropriate current forecast.

M23 adds `cli_mutations.py` for active-forecast changes. `revise`, `journal`, and `review` load one current Binary or Numeric detail, print its Question, derived lifecycle status, and exact forecast, then retain its type-appropriate revision identifier and metadata version throughout input. Revision prompts reject unchanged values before submission; Numeric fields default individually to the exact current fixed-precision values. Journal text is required, Review notes and revision rationales are optional, and these CLI prose fields deliberately accept one terminal line while the desktop and canonical model retain multiline support. The completed prompt invokes the corresponding existing operation, whose immediate transaction rechecks lifecycle, deadline, revision, and metadata context. A concurrent GUI or CLI change therefore fails visibly without attaching content to stale context or appending an unintended revision. [ADR 0011](decisions/0011-line-oriented-cli-mutations.md) records this boundary.

M24 extends that orchestration with `resolve`, `invalidate`, and `delete`. Resolution validates a Yes/No outcome or exact Numeric actual value, collects separate optional factual notes and Postmortem, explains scoring-revision capture and terminal permanence, and confirms before submitting. Invalidation explains preservation plus scoring exclusion, accepts an optional reason, and confirms. Delete rejects ineligible current state before prompting, explains permanent erasure, confirms, and passes the explicit permanent-deletion token only to the existing guarded operation. Blank or negative confirmation raises the same side-effect-free CLI cancellation used by earlier prompts. Application operations and immediate repository transactions recheck revision, metadata, lifecycle, deadline, and deletion history after the prompt, so a competing mutation or write lock returns an error without false terminal history. Canonical Numeric resolution output is formatted from the saved fixed-precision result rather than the user's raw spelling. [ADR 0005](decisions/0005-immutable-terminal-lifecycle-records.md) remains the governing terminal-record design, while [ADR 0011](decisions/0011-line-oriented-cli-mutations.md) governs CLI composition.

M25 adds `cli_transfer.py` as another presentation helper. `backup` and `export-csv` accept an optional `Path`; when absent, they query the existing data-management model only to show its timestamped filename suggestion, and a blank response accepts that filename in the current directory. The helper then invokes `create_backup` or `export_csv_bundle` exactly once and renders the canonical result. It performs no file copying, SQL, transaction control, ZIP construction, or destination installation. Expected path and artifact failures therefore retain the existing nonzero CLI boundary and atomic cleanup, while a successfully installed backup reports whether its completion timestamp was also recorded.

## 8. Persistence model

The minimum conceptual entities are defined by the product specification:

- predictions;
- forecast revisions;
- prediction definition changes;
- journal entries;
- resolutions;
- prediction invalidations;
- presentation-neutral search queries, source-classified fragments, grouped hits, and deterministic ranking;
- tags; and
- prediction-tag associations; and
- named dynamic Saved View configurations and their stable tag references.

The v0.2 Numeric foundation introduces Numeric Predictions, Numeric ForecastRevisions, and Numeric Resolutions as type-specific concepts. M16 persists an immutable Numeric Resolution with its exact realized fixed-precision value and transaction-current scoring revision; M17 consumes the current type-appropriate revision in Dashboard and archive read models without duplicating forecast state.

Milestone 1 established the migration ledger. Milestone 2 added `predictions` and `forecast_revisions`. A prediction stores identity, question, binary type, persisted lifecycle state (`open`, with terminal states used by later milestones), and UTC creation/update instants; it does not store probability. Every forecast revision stores its own 0–100 whole-number probability, UTC creation instant, and per-prediction sequence. A uniqueness constraint makes sequence deterministic, a foreign key protects ownership, and a trigger prevents in-place revision updates.

Milestone 3 migrates the database to version 3. Nullable Background and Resolution Criteria are normalized text, while Forecast Deadline and Expected Resolution are ISO calendar dates rather than instants. The supported metadata-date range is `1752-09-14` through `9999-12-31`, matching the native Qt editor; these fields model current and future forecasting workflow dates rather than historical chronology. Reusable `tags` connect through `prediction_tags`. Python `casefold()` values provide case-insensitive identity, and the first stored display spelling is retained even when a tag temporarily has no prediction associations. Commas and line breaks are excluded from labels because the v0.1 editor uses a comma-separated entry field. A constrained metadata version on each prediction provides optimistic concurrency control for whole-form edits.

Milestone 4 migrates the database to version 4 by adding a nullable normalized rationale to every forecast revision. Existing revisions receive no invented rationale. Revision identity and per-prediction sequence remain deterministic; database triggers reject direct updates, direct child deletion while the parent exists, and replacement through either an existing revision identifier or sequence. A deliberate parent-prediction deletion can still cascade transactionally. The application derives the current forecast from the highest revision sequence and reads forecast history in sequence order, even if two revisions share the same stored instant.

Milestone 5 migrates the database to version 5 with `journal_entries` and `journal_entry_corrections`. A Journal entry stores its original normalized body, original UTC timestamp, and a composite foreign-key reference to a ForecastRevision owned by the same Prediction. Insert-time guards require that reference to be the current revision and reject new entries after a persisted terminal status. Derived Locked predictions remain eligible because Locked is represented by an otherwise-open Prediction whose inclusive deadline has passed.

Journal corrections are separate immutable rows with a per-entry contiguous sequence, normalized replacement body, and UTC correction timestamp. The latest correction supplies the displayed body; the base entry and all correction rows supply the complete edit history. Database triggers reject unchanged correction bodies, sequence gaps, direct updates, direct child deletion while the parent exists, and replacement of saved entry or correction identities. Corrections do not change the entry's original timestamp or forecast anchor and remain possible after a terminal lifecycle decision. A deliberate parent-Prediction deletion can still cascade through entries and corrections.

The unified timeline is a derived read model rather than another persisted event table. Forecasts are ordered by revision sequence. Each Journal entry is placed after its anchored revision and before the next revision; multiple entries sharing one anchor retain insertion order by stable entry identifier. This causal ordering remains deterministic even when stored timestamps tie or the system clock moves backward. Stored event timestamps are still shown to the user in local time, and correcting an entry never moves it in the timeline.

Milestone 6 requires no schema change. Probability history is another derived presentation of the existing `forecast_revisions` rows returned in immutable sequence order. Each row contributes one chart marker. Stored UTC instants determine horizontal position and render in local time, while sequence determines connection order and which marker is current. Journal rows never enter this read product.

Milestone 7 migrates the database to version 6 with `resolutions` and `prediction_invalidations` following [ADR 0005](decisions/0005-immutable-terminal-lifecycle-records.md). Each table permits at most one row per Prediction. A Resolution stores a Yes/No outcome, canonical UTC resolution instant, optional factual notes and postmortem, and a composite foreign-key reference to the ForecastRevision owned by that Prediction that was current when resolution committed. That reference is the canonical scoring revision for later analytics. An Invalidation stores its canonical UTC instant and optional reason and has no scoring revision because Invalid predictions are excluded from analytics.

The released v5 application exposed no terminal transition operation. The v6 migration therefore requires every pre-upgrade Prediction to retain its normal persisted `open` state. If a database was manually altered to contain a legacy terminal status with no outcome or invalidation facts, the migration rolls back and leaves v5 data untouched rather than inventing those missing facts.

Insert guards require a nonterminal persisted Prediction and, for Resolution, the transaction-current revision. After-insert triggers couple the immutable terminal record to the persisted `resolved` or `invalid` status and use the same instant for `updated_at`. Status guards prevent terminal state without its corresponding record and prevent reopening or changing a terminal state. Terminal-row triggers reject direct update, identity replacement, and direct deletion while the parent exists; deliberate parent deletion can still cascade. Normal v0.1 operations expose no terminal correction or reopen path.

Delete eligibility is derived rather than stored. An Open Prediction is eligible only when its current revision remains sequence one, its metadata version remains one, and no Journal, Definition, or Forecast Review history exists. The application additionally derives the current deadline status, so a now-Locked record is never treated as deletable. The delete operation rechecks revision and metadata tokens plus every eligibility condition inside one immediate transaction before cascading the parent. Initial rationale, metadata, and tag associations do not by themselves make an otherwise untouched creation ineligible.

Milestone 8 migrates the database to version 7 with one `app_settings` row. Its constrained whole-number `stale_threshold_days` value defaults to 14 and is the only persisted preference needed by this slice. Dashboard membership itself remains derived and is never written back to Predictions. Keeping this setting in SQLite makes it part of normal backup/recovery state without introducing a general preference registry or platform-specific settings store.

Milestone 9 requires no schema change. The archive is a purpose-specific read model over every Prediction, its highest-sequence ForecastRevision, and associated tags. Stored terminal status remains canonical, while Locked is derived in the application against the current local calendar date before status filtering. Associated tag choices come from current `prediction_tags` relationships, so retained tag rows with no Prediction do not create empty filter choices. Results use deterministic newest-created-first order; filtering never mutates or reorders history.

Milestone 10 also requires no schema change. Resolution's immutable composite reference to its owned `scoring_revision_id` is the canonical final eligible forecast. The analytics source joins that exact row rather than every revision or a newly derived latest row, requires persisted Resolved status, and returns one observation per Resolution. Tags offered by Analytics come only from scored Predictions. Brier scores, calibration bins, and cumulative points remain derived and are never written back to SQLite. [ADR 0006](decisions/0006-fixed-calibration-and-cumulative-brier.md) records the analytical construction.

Milestone 11 migrates the database to version 8 by adding a nullable canonical UTC `last_successful_backup_at` to the singleton settings row. It records only an artifact that has already been installed successfully; cancellation and artifact failure leave the prior value intact. No export metadata or analytical copy is persisted. [ADR 0007](decisions/0007-online-backup-and-relational-csv-export.md) records the transfer approach.

Milestone 13 migrates the database to version 9 while preserving the existing binary schema and every historical row. `predictions.prediction_type` now admits `binary` and `numeric`; Numeric Predictions require an immutable unit label and decimal precision from zero through six, while Binary Predictions require both fields to remain null. Numeric interval revisions live in the parallel `numeric_forecast_revisions` table so the released binary table and its Journal and Resolution references remain untouched. Lower bound, central estimate, and upper bound are exact signed scaled integers at the parent Prediction's precision, with inclusive ordering and whole-number confidence from 1% through 99%. Type guards prevent revisions from crossing Prediction types, and the numeric table applies the same sequence, timestamp, update, direct-delete, and replacement protections as binary history. [ADR 0009](decisions/0009-scaled-integer-numeric-values.md) records the representation and migration boundary.

Milestone 14 needs no schema migration because the existing parent `predictions` columns already hold the optional Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and reusable tag associations. Numeric creation writes the parent row, complete optional initial details, normalized tags, and sequence-one interval in one `BEGIN IMMEDIATE` transaction. Numeric reads map the same canonical metadata and tags, derive the inclusive date-only Locked display state, and return the latest interval by immutable sequence. The UI selects Binary by default, then routes a successfully created Numeric Prediction to a type-specific Detail screen. That screen deliberately exposes no Numeric revise, Journal, lifecycle, archive, chart, or analytics action before its owning milestone.

Milestone 15 migrates to version 10 because the existing Journal schema could reference only a Binary ForecastRevision. The upgrade rebuilds the two Journal tables in one migration transaction, preserves every existing Binary entry and correction, and adds one nullable Numeric revision anchor with a constraint requiring exactly one type-appropriate anchor. Composite foreign keys and insert guards keep an entry owned by its Prediction and bound to that Prediction's transaction-current revision. Numeric revisions recheck their reviewed current-revision and metadata tokens, lifecycle, and changed interval inside `BEGIN IMMEDIATE`; an unchanged complete interval is rejected rather than becoming a fake revision. Numeric Detail uses the same application operations for revisions, Journals, transparent corrections, and a causal text timeline. Its native `QPainter` interval chart is presentation-only: it has one sample per immutable Numeric ForecastRevision, paints lower/upper bounds as a band and medians as a separate line, and never incorporates Journal activity.

Milestone 16 migrates to version 11 with a separate `numeric_resolutions` table. It stores the exact fixed-precision realized value, canonical UTC resolution instant, optional notes and Postmortem, and a composite reference to the Numeric ForecastRevision owned by that Prediction and current when the transaction commits. Type-aware status guards require the appropriate Binary or Numeric terminal record before changing persisted status. Numeric Resolution rows reject update, direct delete, identity replacement, and a second outcome while still permitting deliberate parent cascade. Numeric invalidation reuses the already type-neutral immutable invalidation table. Resolve, Invalid, and delete operations recheck current-revision and metadata tokens inside `BEGIN IMMEDIATE`; deletion additionally requires untouched Open state, while Locked predictions remain resolvable or invalidatable but not revisable or deletable.

Milestone 17 needs no schema migration. The Dashboard and browser use type-aware, read-only projections that join each Binary Prediction to its highest-sequence `forecast_revisions` row and each Numeric Prediction to its highest-sequence `numeric_forecast_revisions` row. Both carry a forecast-type discriminant and either the Binary probability or the complete Numeric interval/median/confidence/unit summary. Application filtering derives Locked once against one local current date, then combines question, lifecycle, forecast type, and tag predicates without mutating persisted history. Type-aware navigation reloads the selected current record and sends it to the appropriate Detail widget.

Milestone 18 also needs no schema migration. Binary `resolutions` and Numeric `numeric_resolutions` already own immutable composite references to their type-appropriate scoring revisions. The analytics repository reads both sources and their tag associations inside one SQLite transaction. Numeric fixed-precision scaled integers map back to exact `Decimal` values before pure calculations; no derived score is persisted. Containment and confidence are unitless, while raw Numeric means are emitted only after an exact stored unit label filters the source.

Milestone 19 migrates to version 12 with one `forecast_reviews` table. Exactly one nullable Binary or Numeric composite revision reference must be present, and insert guards require it to be the current revision of an Open Prediction of the matching type. Saved rows reject update, direct delete, and identity replacement while permitting deliberate parent cascade. Application operations also recheck the reviewed revision, metadata version, and derived deadline status inside `BEGIN IMMEDIATE`, preventing a Review from being attached to stale forecast or proposition context. The optional note and canonical UTC timestamp are immutable. [ADR 0010](decisions/0010-type-aware-forecast-reviews.md) records this boundary.

Milestone 26 migrates to version 13 without modifying any released terminal row. `resolution_corrections` and `numeric_resolution_corrections` retain complete before/after snapshots of every correctable type-specific Resolution field, explicit changed-field flags, a contiguous per-Resolution sequence, canonical UTC correction time, and a required explanation for an outcome or actual-value change. `invalidation_reason_corrections` applies the same snapshot and sequence discipline to the optional reason. Composite foreign keys preserve ownership; triggers require each insert to continue the current effective snapshot and reject update, replacement, sequence gaps, and direct child deletion while the parent exists.

Milestone 35 migrates to version 15 without modifying version-14 canonical records or the rebuildable search projection. `saved_views` stores one required trimmed display name, a Python-casefolded unique name key, every validated archive-control value, and no Prediction-result membership. `saved_view_tags` joins each Saved View to `tags.id`, preserving stable tag identity while the current display label is loaded on demand. Mutable Saved View create, replace-configuration, rename, and delete operations run in their own immediate transactions; they never append forecast, Journal, terminal, or analytical history, and they do not change the search projection.

Milestone 36 needs no schema migration. `data/tags.py` reads every retained `tags` row with current Prediction and Saved View counts and applies reviewed global actions inside one immediate transaction. Rename preserves the selected `tags.id`; merge unions source relationships into a selected target before removing source identities; deletion removes only the selected identity and its current joins. Database uniqueness and `INSERT OR IGNORE` retain case-insensitive identity and deduplicate many-to-one joins. Each action replays its preview inside the write transaction, advances `metadata_version` and `updated_at` once for every affected Prediction, and relies on the existing tag-association and tag-label dirty triggers to rebuild all affected search documents before commit. Stable Saved View references follow rename automatically and are explicitly retargeted or removed for merge and deletion. These preference/metadata operations append no Definition, forecast, Journal, Review, terminal, freshness, or scoring history.

`postmortem_completions` stores one immutable timestamped **Skip Postmortem** fact per Resolved Prediction. Its insert guard requires the currently effective Postmortem to be blank. A later Postmortem correction may still append without deleting that completion fact. `terminal_history.py` reads original facts and correction rows separately, then pure domain replay derives the effective value while preserving the original terminal timestamp and captured scoring revision. Application correction operations carry the latest correction identifier as their optimistic token and recheck it inside `BEGIN IMMEDIATE`. [ADR 0012](decisions/0012-append-only-terminal-correction-chains.md) records this design. M26 deliberately exposes no desktop or CLI mutation control; those workflows belong to later v0.4 milestones.

Historically consequential edits use `prediction_definition_changes` as described in [ADR 0003](decisions/0003-immutable-definition-snapshots.md). Question and Resolution Criteria confirmations address possible changes to proposition meaning and recommend a new Prediction for a materially different proposition. Forecast Deadline confirmations instead describe changes to the forecast cutoff and derived locking. One confirmed save stores one immutable row containing complete before/after snapshots of Question, Resolution Criteria, and Forecast Deadline plus a canonical UTC instant. Expected Resolution remains outside this history. The current prediction remains the canonical source for current metadata; Definition history preserves interpretive context rather than event-sourcing the prediction. Deliberate future parent deletion can cascade to its revisions, tag associations, and definition history transactionally. Later schema additions arrive with the slice that needs them.

### Canonical and derived data

Canonical facts include the prediction, every saved binary or numeric forecast revision, every immutable Forecast Review, every definition-change snapshot, every Journal entry and correction version, original immutable Resolutions and Invalidations, every terminal correction snapshot, Postmortem completion, tag relationships, and mutable Saved View configurations. Derived values normally include:

- current forecast;
- current displayed Journal body and unified timeline ordering;
- effective Resolution outcome, notes, and Postmortem;
- effective Invalidation reason;
- time-dependent Locked status;
- Needs Attention;
- Ready to Resolve;
- individual Binary and Numeric resolved-prediction scorecards;
- one-pair initial-versus-final update summaries with separate unrevised counts;
- Brier summaries; and
- calibration aggregates.

Derived values should not be stored merely for display convenience unless a demonstrated correctness or performance need justifies it.

### Runtime location

Qt's `AppLocalDataLocation`, after the application identity is set, provides the corresponding per-user directory. On Windows the stable canonical database is:

```text
%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3
```

The normal source-development command uses a visibly different identity and path:

```text
%LOCALAPPDATA%\Reckonsolve Dev\reckonsolve.sqlite3
```

The database parent directory is created when needed. There is no automatic copying, migration, or fallback between stable and development data. Backups and exports live at destinations explicitly chosen by the user. Tests and private frozen-build smoke checks always inject temporary paths and never discover or open either real user database.

## 9. Transaction boundaries

`Database` owns one standard-library SQLite connection for the application lifetime. The connection runs in autocommit mode so transaction boundaries are always explicit. Its transaction context rejects nesting, starts with `BEGIN IMMEDIATE`, commits on success, and rolls back on any exception. Foreign-key enforcement is verified when the connection opens, and a five-second busy timeout allows brief external lock contention without waiting indefinitely.

Transactions protect operations that must not leave partial history:

- Creating a prediction, all supplied initial metadata and tag associations, and its first forecast revision with optional rationale is one transaction. Initial values do not append Definition history.
- Editing metadata and tag associations, plus the definition snapshot when required, is one transaction.
- Appending a revision rechecks the reviewed current-revision and metadata-version tokens, lifecycle eligibility, deadline, and changed probability inside one immediate transaction, then inserts exactly one new row without editing prior rows.
- Adding a Journal entry rechecks the reviewed current-revision and metadata-version tokens plus persisted lifecycle eligibility inside one immediate transaction, then captures that transaction-current revision without changing forecast or prediction state.
- Recording a Forecast Review rechecks the type-appropriate current-revision and metadata-version tokens plus derived Open eligibility inside one immediate transaction, then captures the unchanged revision without modifying forecast or scoring state.
- Correcting a Journal entry rechecks its reviewed latest-correction token inside one immediate transaction and appends one changed body version. An effective no-op returns the existing entry without acquiring a new timestamp or writing.
- Resolution rechecks the reviewed type-appropriate revision and metadata version, records the Binary outcome or exact Numeric actual value plus the exact scoring revision, and persists terminal status atomically.
- Invalidation rechecks the same type-appropriate reviewed context and records terminal state, timestamp, and optional reason atomically.
- A terminal correction rechecks the reviewed latest-correction identifier, derives the transaction-current effective snapshot, rejects no-op or unexplained score-affecting changes, and appends exactly one complete before/after record without updating the original terminal row.
- Postmortem completion rechecks the latest correction identifier, Resolved state, blank effective Postmortem, and absence of an earlier completion before appending one immutable timestamped fact.
- Deletion requires explicit confirmation, rechecks untouched Open eligibility for the Prediction's forecast type, and cascades the eligible parent and its initial child state atomically.
- Updating the stale threshold validates the value and replaces the singleton setting in one transaction; it does not mutate any Prediction or history row.
- Backup uses SQLite's online backup API to capture a consistent snapshot, verifies a temporary database, atomically installs it, and only then records the successful time in the source settings.
- CSV export reads all twelve type-aware related tables inside one immediate transaction, closes that transaction, then serializes and validates a temporary ZIP before atomically installing it. It never updates canonical state.
- Saved View creation, explicit configuration replacement, rename, and deletion update only the mutable preference rows and their tag-reference rows inside one immediate transaction. Applying a Saved View only sets desktop controls and reruns the existing read-only archive query; changed controls never persist back until an explicit update action succeeds.
- Global tag rename, merge, and deletion first capture exact Prediction and Saved View relationship contexts for confirmation, then recheck those contexts in one immediate transaction. The canonical joins, retained tag identities, affected Prediction metadata tokens, and rebuildable search documents commit or roll back together; cancellation writes nothing.

Expected domain or validation failures roll back the operation and are translated into clear user-facing messages. Unexpected persistence failures are not silently swallowed.

## 10. Time and lifecycle

Terminal states—Resolved and Invalid—are persisted one-way v0.1 decisions backed by immutable terminal records. Locked is derived from the Forecast Deadline and the computer's local calendar date, so it remains correct after the application has been closed across the boundary. The deadline date is inclusive: an otherwise Open prediction becomes Locked only when the local date is later than its Forecast Deadline. Open predictions without a deadline remain Open until a terminal decision.

Open and derived Locked predictions accept new Journal entries; Resolved and Invalid predictions reject them. Forecast Reviews are stricter: only Open Predictions accept them, while Locked and terminal Predictions reject them. Transparent corrections to existing Journal entries remain allowed in every lifecycle state because they preserve the original assertion rather than create a backdated one.

Needs Attention and Ready to Resolve are derived classifications, not stored lifecycle states. They may overlap and must not mutate a forecast. Needs Attention begins when at least the configured number of complete 24-hour periods has elapsed since the later of the latest ForecastRevision or Forecast Review canonical UTC instant; the persisted default is 14 days. Journal creation and correction do not reset it. Ready to Resolve begins when the computer's local date is later than the inclusive Expected Resolution date. Terminal Predictions participate in neither classification.

System-generated instants follow [ADR 0002](decisions/0002-canonical-utc-instants.md): application operations obtain one aware instant from an injectable clock, normalize it to UTC, and the data layer stores canonical RFC 3339 text ending in `Z`. Definition, Forecast, Review, Journal, and correction history render stored instants in the computer's local time. Date-only values retain calendar semantics and are not converted between time zones.

## 11. Analytics flow

The implemented ordinary scoring pipeline is:

```text
resolved Prediction and captured type-appropriate scoring revision
  -> exclude Invalid and unresolved predictions
  -> validate exactly one observation per Prediction and Resolution
  -> Binary: pair probability with outcome -> Brier/reliability/trend
  -> Numeric: pair interval with actual -> containment/error/interval score
  -> apply forecast-type, tag, and optional exact-unit filters
  -> aggregate only type-compatible and unit-compatible measures
  -> render in the Analytics UI
```

Selection logic and calculation logic require tests independent of chart widgets. Tag filtering should constrain the observation set before aggregation. Probability-history charts use all revisions for one prediction, while scoring uses exactly one eligible revision; these are separate data products and must not share misleading selection behavior.

One read transaction returns each Binary and Numeric Resolution's captured scoring revision, latest effective outcome after its correction chain, and associated tags in original canonical resolution-time and identifier order. Pure analytics validate unique Prediction and Resolution contributions. Binary calculations map Yes to 1 and No to 0, calculate Brier on the 0-through-1 scale, use fixed `0-9%` through `90-100%` probability bands, and retain the cumulative resolution-time trend. Numeric calculations treat both interval endpoints as inclusive, reuse the same ten bands for whole-number confidence, and report actual mean confidence, observed containment, and count. Median absolute error and interval width use exact base-ten values; proper interval score applies the confidence-dependent penalty on only the missed side. A corrected outcome changes the values calculated for that one observation; it never changes its captured ForecastRevision, original Resolution time, or observation count.

The type and tag filters apply before every type-specific output. Numeric **All units** may combine unitless containment observations but produces no raw-error summary. Selecting one exact unit filters the Numeric headline, table, chart, and mean raw metrics together. The **All types** view renders Binary and Numeric sections separately, and the unit selector is available only after choosing Numeric. Native UI charts consume calculated bins and cannot select observations or calculate scores.

## 12. UI data flow

M39 adds a presentation-only layer above the existing screen coordination. `MainWindow` installs one stylesheet generated from its effective `QPalette`; palette or application-font changes rebuild semantic colors/fonts and re-render remembered Lucide icons. New and M39-converted widgets state visual intent with dynamic properties and small helpers instead of adding more embedded color declarations or screen-specific font increments. The shared boundary defines compact/ordinary/section/page spacing, control/panel radii, short motion limits governed by Qt's `SH_Widget_Animate` preference, relative native-font roles, palette-derived base/raised/input/selected surfaces, light/dark green accents, focus and disabled treatment, four action roles, text badges, and persistent message tones. It imports no domain, analytics, application, or data module, persists nothing, and does not participate in any operation or query. The boundary is an ordinary UI implementation detail rather than a new framework or architecture constraint, so M39 requires no new decision record.

`MainWindow` owns navigation and screen coordination. New Prediction keeps Question and whole-number Probability primary and places optional initial rationale, metadata, dates, and tags in a collapsed, scrollable **More details** section. One operation saves all supplied initial state atomically and navigates to Prediction Detail. Because these values establish the initial definition rather than edit an existing one, they require no metadata confirmation and append no definition-change record. An initial Forecast Deadline earlier than the current local calendar date is rejected; today is valid because the deadline is inclusive. Expected Resolution is independent and may be in the past or on either side of the deadline.

Prediction Detail displays the question, current forecast, derived status, tags, and nonempty optional metadata. It refreshes when entered so date-derived status and external edits do not remain stale across navigation. Its edit dialog refreshes the prediction before opening, accepts optional text, date-only fields, and comma-separated tags, and carries that refreshed metadata version through any confirmation prompt. An unset date is shown as blank or **Not set**, never as though today's date were stored; enabling it may seed today's date as the editable choice. Background, Expected Resolution, and tags save normally without confirmation or history. Question and Resolution Criteria changes prompt about proposition meaning and advise creating a new Prediction when the proposition changed materially. Forecast Deadline additions, changes, and removals receive tailored confirmation about the cutoff and Locked behavior, without characterizing the edit as a proposition change. A confirmed protected-field save updates metadata and tags, advances the metadata version, and appends exactly one complete definition snapshot atomically. Effective no-ops and cancelled dialogs perform no write, do not advance the version, and create no history. A version mismatch before or during the transaction rejects a stale edit for review rather than overwriting newer values.

Definition history is hidden when empty and collapsed by default when present. It shows only the protected fields that changed in each snapshot and renders the UTC change instant in local time.

For an Open prediction, **Revise Forecast** opens a side-effect-free dialog showing the reviewed current probability, a whole-number replacement probability, and optional **What changed?** rationale. The new value must differ from the current revision; returning to an older, non-current probability is valid. A successful save refreshes Current Forecast and the unified timeline, whose Forecast entries show each probability transition and any rationale as plain text. The dialog carries both the reviewed revision identifier and prediction metadata version, and the application rechecks both plus lifecycle eligibility inside the append transaction. A stale form is rejected rather than appending against a forecast or definition the user did not review. The action is disabled for derived Locked and persisted terminal states, with the application operation remaining authoritative if state changes while the dialog is open.

For an Open or Locked prediction, **Add Journal Entry** opens a side-effect-free dialog showing the reviewed forecast and accepting a required multiline body; ordinary Enter inserts a newline and Ctrl+Enter saves. It carries the reviewed current-revision and metadata-version tokens, and stale context is rejected rather than attaching reasoning to a forecast or definition the user did not review. The action is disabled for Resolved and Invalid predictions, with the application operation remaining authoritative.

Prediction Detail displays Forecast and Journal events in one causal timeline. Journal entries show their original local timestamp, current body, and **Forecast at the time**. **Correct Entry** is available in every lifecycle state and opens the latest body in a transparent correction dialog. After a changed save, the entry remains at its original timeline position, gains an **Edited** timestamp, and exposes the original plus superseded versions in a collapsed **Edit history**. No individual Journal Delete action exists. Timeline text uses plain-text rendering.

For an Open Binary Prediction, **Still at N%** opens a side-effect-free Forecast Review dialog; the Numeric equivalent is **Keep this interval**. The dialog displays the exact reviewed forecast, accepts an optional note, and carries revision and metadata tokens. A saved Review renders as a distinct plain-text timeline event with its retained context. Locked, Resolved, and Invalid Detail views disable the action. Cancel creates nothing, and success refreshes the timeline without adding a history-chart observation.

Below the timeline, Prediction Detail reuses `list_forecast_revisions` to populate a native, theme-aware probability-history widget. The chart paints exactly one marker per revision on a fixed 0% through 100% vertical scale. Actual stored instants determine elapsed horizontal position and display in local time. Revisions connect in immutable sequence order using step-after geometry, so a probability stays level until the next revision; equal instants share one horizontal position, and a regressing system clock may cause the line to travel backward rather than trigger timestamp re-sorting or synthetic offsets. A single marker receives symmetric horizontal padding. The widget's accessible summary and the exact textual Forecast entries in the timeline make the same history available without relying on the visual plot. Journal events never enter the chart.

The chart is implemented with a dedicated `QPainter` widget and the active Qt palette as recorded in [ADR 0004](decisions/0004-native-probability-history-chart.md). It introduces no external chart library, schema state, or analytics calculation.

For an Open or Locked prediction, **Resolve** opens a deliberate terminal dialog requiring Yes or No or one exact Numeric actual value and accepting optional factual Resolution notes and reflective Postmortem text. The dialog shows the reviewed scoring forecast and carries revision and metadata-version tokens. A successful transaction captures that exact transaction-current revision, persists the outcome, and refreshes Detail with outcome, local resolution time, scoring forecast, and nonempty notes. **Mark Invalid** follows the same refresh and token discipline, accepts an optional reason, and displays the preserved non-scored terminal decision. Both dialogs explain that the terminal state cannot reopen while an honest factual or text mistake can later be corrected with visible history. Terminal predictions disable both actions as well as revisions and new Journal entries; audited correction of an existing Journal entry remains available.

M27 adds **Correct Resolution** inside a Resolved Binary or Numeric terminal section and **Correct Reason** inside an Invalid section. Detail first loads the corresponding complete history through the application boundary and renders only its effective outcome, notes, Postmortem, or reason as the calm current summary. Once at least one correction exists, a collapsed correction-history group contains the original terminal snapshot and every timestamped before/after change, including any outcome-correction explanation. The correction dialog is prefilled from the effective snapshot and carries the latest correction identifier. A no-op stays inline; an outcome or actual-value change reveals its score impact and requires a short explanation; every changed proposal receives an explicit confirmation before the single application operation runs. A text-only save uses the same confirmation without imposing an extra reason. This same Resolution dialog permits an omitted Postmortem to be added later and an existing Postmortem to be corrected or cleared. Success re-queries Detail, while cancellation or an expected stale/lifecycle error leaves the reviewed dialog and canonical history intact.

M28 adds a compact **Scorecard** inside each Resolved Detail section. Binary shows the scored Yes probability, effective Yes or No outcome, individual Brier score, and a lower-is-better reminder. Numeric shows its captured interval, confidence, median, exact unit, effective actual value, inclusive containment, median absolute error, interval width, and proper interval score with lower-is-better guidance for error and interval score. The application asks analytics data access for the canonical resolved observation, then passes it to a pure type-specific projection; Detail only formats the result. A scorecard is absent for Open, Locked, and Invalid Predictions. When an effective score-affecting terminal correction exists, the refreshed card recomputes its one metric set and calls out that correction history exists without altering its original scoring revision or creating another observation.

M30 extends Dashboard with a distinct **Needs Postmortem** section outside the nonterminal attention buckets. Its type-aware query selects exactly Resolved Binary and Numeric Predictions with a blank effective Postmortem and no `postmortem_completions` row, uses the latest effective outcome or exact actual value for display, preserves original resolution-time ordering, and carries the current correction token. Each row opens current Detail or offers **Skip Postmortem**. The confirmation explains that Skip appends one immutable completion fact without changing the Resolution, score, or lifecycle; cancellation is side-effect free, and a stale correction token cannot append a completion. A successful Skip removes the row after refresh and displays a calm success message. Resolved Detail displays the timestamped skipped-completion fact independently of later Postmortem text, so adding prose later never hides that earlier decision.

**Delete** is enabled only when the refreshed Detail query reports an untouched Open prediction. It presents a permanent-action confirmation without mutating on Cancel. The confirmed operation rechecks all eligibility and concurrency facts inside its transaction. Locked or meaningful nonterminal history instead exposes **Mark Invalid**, while terminal history cannot be deleted through the normal interface. Widgets perform no SQL and own no transactions.

Dashboard refreshes at startup, whenever it is entered, and once per minute while it remains visible; the timer stops on other screens. It queries all nonterminal Predictions with their type-appropriate current ForecastRevision and latest Forecast Review instant, derives deadline status and attention against one current instant, then renders four counted sections. Open and Locked are lifecycle views; Needs Attention and Ready to Resolve are overlapping action views, so a Prediction may appear in several sections with all applicable labels intact. Each row says **Forecast last considered**, explicitly labels Binary or Numeric, shows the matching probability or interval/median/unit summary, and opens freshly queried type-appropriate Prediction Detail. Empty sections remain explicit rather than disappearing. Settings currently exposes only the persisted Needs Attention threshold; saving it immediately refreshes Dashboard without adding a general settings framework.

Predictions refreshes whenever it is entered and once per minute while visible so its Open and Locked views remain correct across local-date boundaries. Question search trims surrounding whitespace and uses Unicode-aware case-insensitive substring matching over Question only; v0.1 does not silently extend this to Background, rationales, or Journal bodies. Status choices are All, Open, Locked, Resolved, and Invalid; forecast-type choices are All types, Binary, and Numeric. The single tag filter uses stable stored display spelling. All four filters combine using logical AND. Results show a type-appropriate current forecast, derived lifecycle status, associated tags, and latest forecast time, use explicit new-database and no-match empty states, and load current type-appropriate Prediction Detail before navigation. A failed initial query is not presented as an empty archive; a failed refresh retains earlier rows only with an explicit warning.

Analytics refreshes whenever it is entered and on explicit refresh or forecast-type, tag, or unit change. **All types** keeps Binary and Numeric results in separate labeled sections. Binary retains its scored count, mean Brier, reliability table/chart, and cumulative trend. Numeric shows scored count, overall containment, a complete confidence-bin table and native containment chart, and explanatory sparse-data language. The exact-unit selector is disabled outside the Numeric view; **All units** explicitly withholds raw averages, while one unit reveals mean median absolute error, interval width, and interval score with that unit printed beside every value. Empty bins remain visible with count zero but add no chart point. Charts expose nonvisual summaries, expected read failures are not shown as zero scores, and a failed refresh retains prior results only with a warning.

M29 adds separate Binary and Numeric **Retrospective update feedback** sections beneath those ordinary scoring views. The data query joins sequence-one revision context to the Resolution's immutable captured scoring revision, and the pure analytics layer emits at most one pair per revised-and-resolved Prediction. Unrevised Resolutions are counted separately; intermediate revisions, Invalid Predictions, and unresolved Predictions never enter the paired population. Binary reports paired mean initial Brier, final Brier, and initial-minus-final improvement. Numeric reports unitless initial/final confidence and containment across units, while exact-unit selection reveals paired median error, width, narrowing, and proper interval-score comparisons. Every result follows the same forecast-type, tag, and optional exact-unit filters and carries sparse-sample and noncausal language. Effective outcome corrections recompute both sides against the corrected value but retain the original resolution time.

Settings displays the canonical database path and last successful backup time alongside the existing attention threshold. **Back Up Now** and **Export CSV Bundle** use native save dialogs with timestamped suggestions. Cancel is side-effect free. Expected path, file, SQLite, or archive failures remain visible without replacing a previous destination artifact. Backup success updates the displayed time; CSV success reports the twelve generated tables while continuing to label the ZIP as non-restorable analytical data.

A screen requests view data through an application query, renders it, and invokes a complete operation in response to user intent. After a successful mutation, the relevant view is re-queried or updated from the operation result. Widgets should not maintain an independent canonical copy of prediction state.

Dialog cancellation has no side effect. In particular, opening and closing a revision, Journal, correction, Resolution, or Invalidation dialog cannot create history or terminal state.

Expected failures—such as attempting a revision after the deadline—are shown in plain language. Unexpected exceptions should remain visible to the application error boundary during development rather than being suppressed in individual signal handlers.

## 13. Migrations and compatibility

Database evolution uses the lightweight mechanism recorded in [ADR 0001](decisions/0001-lightweight-sqlite-migrations.md). `data/migrations.py` contains an immutable, contiguous sequence of numbered and uniquely named migrations. The `schema_migrations` table records each applied version and name rather than relying on `PRAGMA user_version`.

Startup opens an explicit `BEGIN IMMEDIATE` transaction, validates the bundled registry and the database's complete recorded history, applies all pending SQL statements in order, checks foreign-key integrity, and commits. Any failure rolls back the whole pending migration set. Running startup again when nothing is pending is idempotent.

An empty database can receive the baseline. A nonempty SQLite database without Reckonsolve migration history is unrecognized and rejected. An empty, malformed, gapped, renamed, or otherwise inconsistent migration history is rejected, as is a schema version newer than the running application understands. These failures never trigger database deletion or recreation.

Each future migration must be tested against the prior schema state, preserve existing user data, and leave the database reopenable. Version 9 preserves Binary data while adding the Numeric foundation; version 10 preserves Binary Journal history while adding type-aware anchors; version 11 preserves both types and existing Binary terminal records while adding Numeric Resolution and type-aware terminal-status guards; version 12 preserves both forecast types while adding immutable type-aware Reviews; version 13 preserves every original terminal row while adding audited correction and Postmortem-completion history; version 14 preserves all version-13 data while adding only rebuildable search structures and invalidation triggers; and version 15 preserves all version-14 data while adding mutable Saved View configuration and stable tag-reference tables. Every migration has a forced-failure rollback test pinned to its preceding schema. Earlier version-specific tests remain pinned to their historical targets. Already released migrations are historical records and must not be edited. A third-party migration framework still requires a demonstrated need.

### Derived search projection

SQLite remains canonical; `prediction_search` is a contentful FTS5 projection with one row per source fragment. Each row carries its Prediction identifier, stable source classification, canonical record and optional correction/version identifiers, sequence and time context, a superseded flag, and the indexed user-authored body. The projection covers current Question, tags, Background, current Resolution Criteria, every immutable forecast rationale and Forecast Review note, effective Journal text, effective Resolution notes and Postmortem, effective Invalidation reason, and every required score-affecting correction explanation. Distinct superseded Question, Resolution Criteria, Journal, Resolution, Postmortem, and Invalidation text is retained as historical-only projection rows.

Small schema triggers add affected Prediction identifiers to `search_dirty_predictions`; they never derive or duplicate canonical text rules. The outer `Database.transaction()` deterministically replaces those Predictions' complete documents immediately before commit. Any projection exception rolls back both derived and canonical changes. Deletion projects an absent Prediction to zero rows. Startup requires FTS5, consumes a retained dirty queue, and rebuilds when the separate projection algorithm version or recorded document count is incompatible. Full integrity checking replays every canonical Prediction and compares the resulting document set; repair discards only derived rows and rebuilds them. [ADR 0013](decisions/0013-rebuildable-sqlite-fts5-search-index.md) records this boundary.

`domain/search.py` parses ordinary words and fragment-local quoted phrases without exposing raw FTS syntax, provides incremental final-token prefix matching, normalizes case and common diacritics, applies pure deterministic grouping and source-aware ranking, and derives plain snippet text plus source-indexed emphasis spans. `data/search.py` issues parameterized FTS queries, preserves current-Question literal substring behavior, derives conservative single-edit suggestions from the user's own corpus, and supplies current type-aware forecast or effective terminal summary fields without making the projection canonical. The application operation derives Locked and attention values once for each query, then applies status, type, multiple-tag All/Any, attention, and local-calendar date constraints before ranking. It reports rather than silently applies an available Any-word fallback, applies a requested deterministic non-relevance sort only after grouped hits exist, and converts repair failures into an explicit expected error. `domain/browser.py` owns reusable archive-query values, validation, matching, local-date projection, and null-last identity-stable sorting so blank browsing and full-text results cannot drift apart.

The M33/M34 Predictions UI keeps blank text on the established archive query and sends nonblank text through the shared grouped search operation after a short debounce. It exposes a multiple-selection tag list with All/Any mode, one derived attention choice, optional From/To date endpoints for a selected meaning, and every deterministic sort. Relevance is disabled without text and selected by default while text is active; Created newest is the ordinary default. It escapes every source character before applying controlled snippet emphasis, retains one accessible row per Prediction, labels historical-only hits unmistakably, and preserves previously loaded rows behind a visible warning when an expected query failure occurs. Activating a hit reloads the current Prediction through the ordinary type-aware navigation query, then expands and scrolls to its matching metadata, immutable timeline, Definition history, Journal edit history, or terminal-history context; widgets retain provenance only as transient navigation data and never query SQLite directly.

M35 adds a compact Saved View control row inside that same screen. The picker holds named configurations only; choosing one blocks intermediate control signals, restores every text, history, filter, date, attention, tag-mode, and sort control, and reruns the normal query against present data. A loaded view reports **Saved** or **Modified** by structural comparison with the current controls. **Update Saved View** is disabled unless the configuration differs, so applying or changing a control cannot silently replace a saved preference. Create, Save as new, rename, and delete call dedicated application operations; cancellation writes nothing, and delete confirms that only the preference will be removed.

M36 adds **Manage Tags** beneath the Predictions archive controls as a secondary modal workflow rather than a seventh primary screen. It lists retained tags with Prediction/Saved View counts, filters labels by case-insensitive substring, and requires row selection for rename, merge, or deletion. Rename confirmation shows old/new labels and affected Predictions; merge makes the retained target explicit and shows both affected counts; deletion warns when removing a condition may broaden a Saved View. The dialog invokes preview and mutation application operations rather than SQL, refreshes current counts only after success, and leaves the browser to reload Saved Views and ordinary query results through their established paths.

M37 leaves desktop presentation unchanged and extends only `cli.py`. The `search` parser owns command-line spelling and ISO-date parsing, while the application operation remains authoritative for query parsing, filter validation, lifecycle/attention derivation, grouping, ranking, suggestion generation, and index failures. Readable output labels explicit Any-word guidance and spelling suggestions as advice, never as an altered command. `saved-view` deliberately separates `--id` and `--name`, avoiding ambiguity for a Saved View whose display name is numeric. Both Saved View command paths are read-only and rerun configurations dynamically rather than storing or exposing fixed Prediction membership.

## 14. Backup and export

Backup and CSV export have separate implemented contracts:

- Backup produces a consistent artifact sufficient to recover the full application state.
- CSV export produces documented, portable analytical data and may use several related files to preserve historical structure honestly.

Backup uses the standard-library binding to SQLite's online backup API. It writes to a unique temporary database beside the chosen destination; runs SQLite quick, foreign-key, and schema-version checks; closes the temporary connection; then uses same-directory atomic replacement. The canonical database path, including an equivalent hard link, is rejected as a destination. Failure cleanup targets only the owned temporary file, and an existing destination remains untouched until installation succeeds. Backup copies the complete schema-version-15 database, including canonical correction/completion history, mutable Saved Views, and the disposable search projection; search can still be rebuilt solely from the copied canonical tables.

CSV export reads all sixteen format-version-three relationships in one transaction. It retains the twelve format-version-two files unchanged and adds separate Binary Resolution-correction, Numeric Resolution-correction, Invalidation-reason-correction, and Postmortem-completion files. Stable parent identifiers and contiguous correction sequences preserve every join. The included data dictionary explains effective-value replay, changed-field flags, score-affecting correction reasons, exact Numeric scaled values, and every v0.5 exclusion. Serialization, archive validation, and same-directory atomic replacement retain the prior destination-safety contract. SQLite backup remains the complete schema-version-15 recovery artifact; CSV remains analytical rather than restorative and intentionally excludes mutable Saved Views, application settings, derived search rows/state/vocabulary, query and ranking data, and hidden telemetry. Current tag identities and Prediction associations remain included.

## 15. Private Windows build

PyInstaller 6.22.2 is an exact, locked build-only dependency in the `packaging` dependency group. It is not imported by the application, included as a runtime library, or required for normal development. The checked-in spec produces a windowed `onedir` bundle, collects only the application's imported code plus selected UI resources and license notices, and deliberately supplies no invented Reckonsolve icon. `onedir` keeps the first private build inspectable and gives clearer missing-resource diagnostics than a self-extracting executable.

`tools/build_windows.ps1` synchronizes the locked group, replaces only generated PyInstaller output under ignored `build/` and `dist/` directories, and then copies the completed bundle to a unique ignored smoke directory. It launches the copied executable with an internal private-smoke argument and an offscreen Qt platform from that relocated working directory. The executable verifies that it is actually frozen, creates a disposable real v0.4 schema-version-13 database with append-only terminal history, constructs the real main window so startup migrates it through version 15 and loads every local resource, and proves FTS5 capability plus effective/history search, Saved View execution, transactional tag rename/merge/delete, an independent CLI-compatible canonical read, visible index failure, explicit repair, verified backup, and restart of both source and recovery databases. It retains the earlier Binary and Numeric revision, Review, correction, later-Postmortem, scorecard, paired-update, and Needs Postmortem coverage. The source checkout, Python interpreter, and `uv` are used to build but are not used by the smoke process.

This artifact is a development validation output, not a supported release. There is no installer, Start menu integration, shortcut ownership, uninstaller, code signature, update channel, or public download contract. [ADR 0008](decisions/0008-private-onedir-and-local-icons.md) records why this narrow build exists.

## 16. Testing strategy

The suite covers package entry points, GUI and CLI runtime composition, paths, database/migrations, clocks, domain validation, prediction operations, pure analytics and search ranking, data transfer, and Qt screens. It uses explicit temporary databases for initialization, upgrades through schema version 15, atomicity, restart, and cleanup scenarios, and pytest-qt only for GUI behavior. M3 through M25 retain their completed historical, desktop, CLI, analytics, transfer, packaging, migration, identity, concurrency, and failure-safety coverage. M26 adds pure snapshot-replay tests plus temporary-database coverage for version-12 migration, forced rollback, database immutability and sequence guards, Binary and exact Numeric corrections, score-affecting explanation requirements, text-only changes, Invalidation reasons, Postmortem completion, corrected-outcome analytics, independent-connection stale tokens, restart, and transaction rollback. M28 adds pure scorecard projections and real-database Qt rendering coverage. M29 covers revision-one/final selection, separate unrevised counts, omitted intermediate revisions, filters, unit boundaries, corrected effective outcomes, and preserved original resolution time. M30 covers queue membership, effective terminal facts, cancellation, Skip completion, stale context, later Postmortems, Detail rendering, and restart. M31 adds side-effect-free complete CLI terminal-history reads, all four format-version-three relationships and their data dictionary, schema-12 frozen migration, complete backup recovery, simultaneous reads, sequential cross-interface writes, artifact safety, and full v0.4 smoke verification. M32 adds pure safe-query and deterministic-ranking tests plus a synthetic source-priority corpus; schema-13 upgrade and forced-failure coverage; comprehensive Binary/Numeric current and superseded source projection; prefix, phrase, Unicode, punctuation, substring, All/Any, suggestion, grouping, deletion, restart, independent-connection, stable/development isolation, corruption, repair, and projection-failure rollback scenarios. M33 adds safe snippet-span and source-label tests; presentation-ready Binary/Numeric and effective corrected terminal summaries; existing archive-filter composition; desktop All/Any, history, suggestion, safe-markup, accessible-description, explicit-empty, and retained-results behavior; and exact superseded-Journal Detail navigation. M34 adds shared rich-filter composition across Binary, Numeric, Open, Resolved, Invalid, corrected terminal, missing-date, and attention records; inclusive date ranges; null-last sort behavior; relevance/default-sort behavior; and desktop multi-tag, attention, date, sort, and clear-reset controls. M35 adds mutable configuration validation, case-insensitive names, stable tag references, current-membership re-query, restart and backup recovery, identity isolation, version-14 upgrade and rollback, and saved/modified desktop workflow coverage. M36 adds retained zero-use tags, case-insensitive filtering, display-only rename, duplicate-name guidance, many-to-one Prediction/Saved View deduplication, broader-view deletion, metadata-token invalidation, search consistency, failure rollback, cancellation, restart, verified-backup recovery, independent-connection reads, and desktop confirmation coverage. M37 adds help without database startup, full-text filtering and grouped plain-text explanation, Any-word fallback, superseded-history labels, Saved View configuration listing, name/ID execution, empty and not-found paths, terminal safety, and proof that all new reads leave Prediction and Saved View data unchanged. M38 adds same-count projection mismatch recovery, explicit desktop repair, the named privacy-safe relevance corpus, the measured 2,000-Prediction/6,000-fragment completeness run, schema-13 frozen migration, effective/history search, Saved Views, tag-wide operations, independent reads, repair, backup, and recovery in the relocated executable. The recorded method and observations live in [Search evaluation](search-evaluation.md).

M39 adds focused Qt coverage for the visual boundary's centralized tokens and imports, light/dark semantic contrast, role properties, accessible names, focus and disabled selectors, native-font relativity, platform animation hint, palette-triggered style/icon refresh, and representative New Prediction/Forecast Review integration. These tests assert semantic intent rather than pixel-perfect platform rendering; manual review remains responsible for evaluating the resulting native Windows composition in both system modes.

M40 adds focused Qt and settings coverage for permanent-destination hierarchy, the prominent creation action, the bottom Settings utility, source-aware contextual Detail return, unchanged Predictions query/results/selection/scroll state on return, active-route treatment, compact-mode text completeness and accessible names, keyboard operation, stable/development preference isolation, INI corruption or write-failure tolerance, and safe recovery from removed-monitor or invalid window geometry. Window-state tests retain normal geometry and maximization but explicitly exclude minimized restoration. No test opens a real user database.

Most behavior should be verified below the GUI:

- pure unit tests for probability, lifecycle, attention, revision selection, probability-history projection, and scoring rules;
- temporary-SQLite integration tests for transactions, constraints, queries, migrations, restart persistence, and backup consistency;
- pytest-qt tests only for behavior that genuinely depends on Qt signals, widgets, navigation, or dialog cancellation; and
- application and private-build smoke tests against temporary data directories.

Tests use fixed clocks, explicit temporary paths, and representative boundary cases. The normal verification commands are:

```text
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 17. Error handling

Expected errors should use explicit application or domain error types that the UI can present without a traceback. Examples include invalid probability, missing question or Journal text, an action disallowed by lifecycle, stale forecast or metadata context, a concurrently corrected Journal entry, and a search projection that requires repair.

Unexpected exceptions should not be converted into false success or empty data. Database failures must preserve the original database and provide enough context for diagnosis without exposing unrelated local information.

## 18. Decisions intentionally deferred

The M12 resource, identity, and private-build boundary is implemented. The original application icon remains pending because its artwork must be directed or supplied by the user; the current private executable therefore retains PyInstaller's generic default rather than pretending to establish Reckonsolve's permanent mark.

A normal installer, uninstall policy, code signing, public distribution channel, and automatic updates remain Later decisions. When one becomes consequential, seek explicit user authorization before changing the product specification. Record durable technical reasoning in an [architecture decision record](decisions/README.md) when appropriate.

## 19. Evolution into v0.2

The approved v0.2 product plan adds one central numeric prediction interval per revision and explicit Forecast Reviews through Milestones 13 through 20. M20 completes the plan: Open-only immutable Reviews preserve exact Binary or Numeric forecast context and refresh Needs Attention without altering revision history, charts, or scoring; version-two relational export and complete backup/migration/private-build recovery coverage preserve those records across every supported local path. The application now covers the complete type-aware forecasting, Journal, Review, lifecycle, Dashboard, archive, analytics, and portability loop.

The architecture will continue through implemented vertical slices rather than prebuilding later scope. After each milestone, update this document to reflect actual modules, persistence behavior, and any recorded technical decisions; do not describe planned structures as already implemented.

## 20. Evolution into v0.3

The completed v0.3 plan adds a human-directed CLI companion through Milestones 21 through 25. M21 implements the shared-data foundation and read model: paired source entry points, identity-selected database composition, `--help`, `--version`, filtered `list`, and complete type-aware `show`. M22 adds interactive `create binary` and `create numeric` flows that preserve existing defaults, exactness, optional details, atomicity, and cancellation behavior. M23 adds type-aware `revise`, `journal`, and `review`, retaining existing immutable-history, forecast-anchor, freshness, lifecycle, deadline, and optimistic-concurrency semantics. M24 adds confirmed type-aware `resolve`, `invalidate`, and guarded `delete`, retaining final scoring-revision capture, exact Numeric outcomes, Invalid exclusion, one-way terminal state, and transaction-current deletion eligibility. M25 adds CLI backup and format-version-two CSV export through the existing verified transfer operations, hardens independent-connection and artifact-failure behavior, and closes the source release. Every milestone uses the existing version-12 schema and application operations, so both matching interfaces preserve one canonical history without a synchronization subsystem.

The CLI remains source-distributed through `uv`; a separately frozen executable, installer integration, noninteractive scripting API, terminal analytics, live inter-process refresh, and logo work remain outside v0.3.

## 21. Evolution into v0.4

The completed v0.4 plan spans Milestones 26 through 31. M26 implements the domain and persistence foundation: original terminal rows remain immutable; complete Binary, Numeric, and Invalidation correction snapshots append in deterministic chains; one Postmortem completion fact can be recorded; and effective replay supplies corrected outcomes to ordinary analytics without changing scoring-revision capture, resolution-time ordering, or observation count. Schema version 13 migrates the completed v0.3 database forward and remains fully recoverable through SQLite backup.

M27 exposes audited desktop correction and later-Postmortem workflows. Both type-specific Detail screens show effective terminal values and complete collapsed correction history, and their focused dialogs preserve the append-only, exactness, explanation, confirmation, and optimistic-concurrency contract. M28 adds individual Binary and Numeric scorecards that reuse the exactly-once analytics observation and visibly distinguish an effective corrected terminal value from immutable scoring context. M29 adds filtered one-pair initial-versus-final feedback with separate unrevised counts, unit-safe Numeric comparisons, corrected-outcome recomputation, and explicit retrospective/sparse-data cautions. M30 adds the Resolved-only Needs Postmortem queue and confirmed Skip completion while preserving later Postmortem eligibility and the completion fact on Detail. M31 adds historically complete CLI read parity, relational export format version 3, full portability and private-build coverage, and v0.4 source-release closure.

## 22. Evolution into v0.5

The completed v0.5 plan begins with Milestone 32's search foundation. SQLite FTS5 is a rebuildable, source-classified projection rather than canonical state. Version 14 preserves the v0.4 database, backfills all searchable current and historical text, and keeps every subsequent searchable write atomic with its projection refresh. Presentation-neutral queries accept ordinary words, local quoted phrases, final-token prefixes, current-Question substrings, explicit All/Any semantics, corpus-derived spelling guidance, and effective-versus-superseded scope. Pure ranking groups fragments into one result per Prediction and deterministically favors exact and literal current Question matches before source priority and FTS relevance.

M33 completes the first user-facing search surface. The Predictions screen now switches cleanly between the established blank-query archive and grouped explainable full-text results, while preserving type and status filtering. Safe snippets and explicit source labels explain why each Prediction matched; All/Any and spelling alternatives remain user-chosen; historical text is opt-in; and result activation uses stored provenance only to reveal the corresponding current Detail context. M34 completes rich archive retrieval with multiple-tag All/Any filtering, derived attention, optional local-calendar date ranges, deterministic sorts, and one clear-reset path shared by blank and full-text browsing. M35 adds named dynamic Saved Views, stored as a complete validated archive configuration with stable tag identifiers and no result membership. Applying one uses the same query path; configuration changes become visibly modified and persist only through explicit update. M36 adds previewed transactional tag-library maintenance that preserves stable rename identity, deliberately merges into a selected target, explicitly warns before deleting Saved View conditions, invalidates stale Prediction metadata forms, and refreshes the derived search projection inside the canonical write. M37 completes CLI retrieval parity: full-text `search` maps terminal-friendly controls to the same query and explainable grouped result model, while `saved-views` and `saved-view --id/--name` inspect and dynamically rerun existing Saved Views without adding a CLI mutation path. M38 verifies final portability, relevance, recovery, cross-interface, and private-build behavior and closes the v0.5 source release without adding semantic search, Collections, a new forecast model, an installer, signing, updates, public binaries, or logo work.

## 23. Evolution into v0.6

Milestone 39 establishes the v0.6 presentation foundation without touching schema version 15 or any forecasting behavior. One UI-only module turns the effective Qt palette and native application font into shared semantic colors, typography, spacing, radii, interaction states, focus treatment, action hierarchy, status/message treatments, and restrained motion limits. The root window owns installation and theme refresh, while screens assign intent through reusable helpers. New Prediction and Forecast Review provide the first representative page/dialog application, destructive Delete actions receive an explicit role, and matched-search focus uses the same central selector. Later v0.6 milestones can propagate these roles and compose higher-level page/shell structures without importing presentation into the domain or persisting theme state.

Milestone 40 implements the application shell while preserving every workflow and schema-version-15 boundary. New Prediction is an action rather than a peer destination; Dashboard, Predictions, and Analytics are the permanent primary routes; Settings is visually separated at the bottom; and Detail appears contextually with a Back label naming its source. Returning from Detail does not reconstruct the originating screen, which preserves the complete in-memory Predictions search, filter, Saved View, result, selection, and scroll context. The last primary route supplies the return target after creation. The sidebar can switch between complete expanded labels and complete icon-only controls with tooltips and accessible text; Qt's normal focus model remains usable in either mode.

`presentation_settings.py` keeps the sidebar choice, safe normal geometry, and maximized flag in an identity-scoped INI file beside the canonical database. Geometry restoration fits the stored normal rectangle fully within the currently available screens or falls back to a centered safe default when a monitor disappeared, dimensions are invalid, or settings are corrupt. Minimized state is never restored. Read or write failure degrades to defaults rather than blocking startup or shutdown. This disposable shell state is deliberately absent from SQLite, backup/export artifacts, search, and the CLI.
