# Reckonsolve Architecture

Status: Milestone 13 numeric domain and persistence foundation complete
Last reviewed: 2026-08-20

This document describes how Reckonsolve is structured and how its implementation evolves from the completed binary v0.1 baseline through v0.2. The [product specification](product-spec.md) governs product behavior, scope, terminology, and acceptance criteria. This document translates those requirements into technical boundaries without replacing them.

## 1. Current implementation

Milestone 13 adds an independently testable Numeric Prediction model and schema-version-9 persistence boundary without changing the completed Binary Prediction workflows. Exact signed decimal values use a bounded fixed-precision scaled-integer representation, and numeric interval revisions are stored separately from binary forecast revisions. Numeric application operations and UI are deliberately absent until Milestone 14, so the running application remains honestly binary-only. The M12 private build and resource layer remain intact; original user-directed application artwork and normal public distribution remain deferred.

| Area | Current state |
|---|---|
| Project management | `uv` project with Python 3.13 pinned in `.python-version` |
| Runtime dependency | PySide6 |
| Development tools | pytest, pytest-qt, and Ruff; pinned PyInstaller exists only in the separate `packaging` dependency group |
| Python package | `src/reckonsolve/` |
| Entry points | `reckonsolve` and `python -m reckonsolve` use the stable identity; `reckonsolve-dev` uses the visibly separate development identity; the private frozen entry adds only its disposable build-smoke path |
| Application runtime | `ApplicationRuntime` owns the `QApplication`, open `Database`, and `MainWindow`; startup composes concrete prediction operations and shutdown closes persistence |
| UI | All six primary screens are functional; selected navigation and action icons are local, palette-aware Lucide SVGs rendered through QtSvg while visible text and accessible names remain authoritative |
| Runtime path | Stable uses `%LOCALAPPDATA%\Reckonsolve`; source development uses `%LOCALAPPDATA%\Reckonsolve Dev`; tests and private smoke inject explicit disposable paths |
| Persistence | One standard-library `sqlite3` connection with foreign keys enabled, a five-second busy timeout, and explicit immediate transactions |
| Schema | Version 9 preserves all binary tables and adds Numeric Prediction definition fields plus immutable numeric interval revisions |
| Domain and application operations | Complete binary workflows plus independently testable numeric definition, revision, and resolution values; numeric application operations remain Milestone 14 work |
| Analytics | Exactly-once scoring selection, binary Brier, fixed-bin calibration, and cumulative resolution-time aggregation are implemented as pure calculations behind a read-only data source |
| Automated tests | Existing product coverage plus exact signed numeric values, interval/confidence constraints, schema-v9 migration, rollback, immutability, and binary-data preservation |
| Windows distribution | A private PyInstaller `onedir` build is repeatable and smoke-validated; original icon artwork, installer, signing, shortcuts, uninstall, updates, and public distribution remain deferred |

The sections below distinguish the completed v0.1 application from the v0.2 boundaries implemented or still planned.

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

The six primary screens are Dashboard, New Prediction, Prediction Detail, Predictions, Analytics, and Settings. Revision, journal, resolution, invalidation, deletion, and metadata editing can remain focused dialogs or secondary views.

M12 keeps the native Qt/Windows visual system rather than adding a theme framework. Navigation and high-value actions use a small selected set of local Lucide 1.33.0 SVGs rendered through QtSvg in normal, disabled, and selected palette colors. Visible action text is retained, accessible names remain meaningful, and palette changes re-render remembered button and navigation icons. Font-aware chart sizing, existing scrollable forms, keyboard-native controls, and a minimum resizable main-window size provide conservative polish without fixed-pixel screen layouts. [ADR 0008](decisions/0008-private-onedir-and-local-icons.md) records the resource and private-build approach.

The Prediction Detail probability-history widget is presentation code. It projects immutable revisions onto elapsed stored time, paints the fixed probability scale and sequence-ordered step geometry, and supplies an accessibility summary. It does not select scoring observations, infer probabilities, or persist chart state. [ADR 0004](decisions/0004-native-probability-history-chart.md) records the native rendering approach.

### Application operations

This layer coordinates complete user actions. An operation validates a request, applies domain rules, opens the required transaction through the data-access boundary, and returns either a result suitable for presentation or an expected application error.

Representative operations include:

- creating a prediction and its first revision;
- appending a forecast revision;
- adding a journal entry tied to the current revision;
- appending a transparent correction to an existing journal entry;
- reading immutable forecast revisions in sequence order;
- reading a unified causal timeline;
- editing permitted prediction metadata;
- resolving or invalidating a prediction;
- listing and filtering predictions;
- producing analytics inputs;
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

No normal data-access operation may update or delete a saved forecast revision, Journal entry, or Journal correction. Migration code is the exceptional maintenance path and must preserve legitimate history. A deliberate future deletion of a parent Prediction may cascade to its complete child history transactionally.

### Analytics

Analytics code owns scoring selection and aggregation, separate from chart rendering. Its input is candidate prediction, resolution, and revision data obtained through the data-access boundary. It constructs exactly one scoring observation for each included resolved prediction by selecting that prediction's final eligible revision according to the product specification.

The analytics boundary contains:

- final-eligible-revision selection;
- per-prediction Brier calculation;
- mean Brier calculation;
- calibration bin assignment and aggregation; and
- the explicitly labeled Brier-over-time series.

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

Milestone 13 implements this package structure:

```text
src/reckonsolve/
  __init__.py          stable `main()` and isolated-development `main_dev()` entry points
  __main__.py          `python -m reckonsolve` entry point
  app.py               QApplication composition, runtime ownership, and startup errors
  clock.py             injectable clock and canonical UTC instant conversion
  identity.py          stable and visible development application identities
  paths.py             per-user and explicitly injected database paths
  private_build_smoke.py
                       disposable frozen UI, core-loop, backup, and restart probe
  application/
    errors.py          expected user-presentable operation and concurrency errors
    predictions.py     prediction workflows and read-use-case orchestration
  analytics/
    scoring.py         pure exactly-once Brier, calibration, and trend calculations
  domain/
    analytics.py       captured resolved-forecast facts shared by data and analytics
    attention.py       stale-threshold validation and derived Dashboard values/rules
    browser.py         current prediction summaries and archive-query results
    predictions.py     binary and numeric prediction, revision, resolution, metadata, status, and validation values
    transfer.py        backup/export status and result values
  data/
    __init__.py        persistence package surface
    analytics.py       read-only captured-scoring-revision source
    database.py        connection ownership and transaction boundary
    migrations.py      ordered schema registry, validation, and migration runner
    numeric_predictions.py
                       numeric Prediction and interval-revision persistence
    predictions.py     purpose-specific prediction, history, terminal, tag, and deletion persistence
    settings.py        singleton attention and backup-status setting access
    transfer.py        verified SQLite backup and relational CSV ZIP creation
  ui/
    __init__.py        UI package surface
    analytics_charts.py
                       native reliability and cumulative Brier painting
    analytics_screen.py
                       summary, common tag filter, bin table, and charts
    dashboard.py       action buckets plus attention, backup, and export settings
    icons.py           palette-aware rendering for the selected Lucide resources
    main_window.py     navigation and screen coordination
    prediction_browser.py
                       question search, status/tag filters, and archive navigation
    probability_history_chart.py
                       native probability-history projection and painting
    screens.py         creation, Prediction Detail, history, lifecycle, deletion, and metadata UI
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
5. constructs the six-screen `MainWindow` with those operations;
6. returns an `ApplicationRuntime` that owns the Qt application, database, and window; and
7. shows the window and enters the Qt event loop.

The production runner catches expected path, migration, operating-system, and SQLite startup failures and presents a fatal database error. It does not replace or silently recreate an existing database. The runner's `finally` cleanup closes the database after the Qt event loop ends or if showing the window fails; close is idempotent.

`create_runtime()` accepts both an explicit identity and database path. Normal source work uses `reckonsolve-dev`, whose title and application name are **Reckonsolve Dev**; stable entry points retain **Reckonsolve**. Because path resolution happens only after setting that identity, Qt supplies distinct per-user directories without an ad hoc environment override. No startup path copies or migrates data between those channels. Tests never discover or open either real user database. The clock and application operations are composed at this boundary rather than through global state or widget-side service lookup; later operations should follow the same pattern.

## 8. Persistence model

The minimum conceptual entities are defined by the product specification:

- predictions;
- forecast revisions;
- prediction definition changes;
- journal entries;
- resolutions;
- prediction invalidations;
- tags; and
- prediction-tag associations.

The v0.2 numeric foundation additionally introduces Numeric Predictions, Numeric ForecastRevisions, and Numeric Resolutions as type-specific concepts. A Numeric Resolution is currently a domain value only; its persistence and lifecycle operations belong to a later numeric milestone.

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

Delete eligibility is derived rather than stored. An Open Prediction is eligible only when its current revision remains sequence one, its metadata version remains one, and neither Journal nor Definition history exists. The application additionally derives the current deadline status, so a now-Locked record is never treated as deletable. The delete operation rechecks revision and metadata tokens plus every eligibility condition inside one immediate transaction before cascading the parent. Initial rationale, metadata, and tag associations do not by themselves make an otherwise untouched creation ineligible.

Milestone 8 migrates the database to version 7 with one `app_settings` row. Its constrained whole-number `stale_threshold_days` value defaults to 14 and is the only persisted preference needed by this slice. Dashboard membership itself remains derived and is never written back to Predictions. Keeping this setting in SQLite makes it part of normal backup/recovery state without introducing a general preference registry or platform-specific settings store.

Milestone 9 requires no schema change. The archive is a purpose-specific read model over every Prediction, its highest-sequence ForecastRevision, and associated tags. Stored terminal status remains canonical, while Locked is derived in the application against the current local calendar date before status filtering. Associated tag choices come from current `prediction_tags` relationships, so retained tag rows with no Prediction do not create empty filter choices. Results use deterministic newest-created-first order; filtering never mutates or reorders history.

Milestone 10 also requires no schema change. Resolution's immutable composite reference to its owned `scoring_revision_id` is the canonical final eligible forecast. The analytics source joins that exact row rather than every revision or a newly derived latest row, requires persisted Resolved status, and returns one observation per Resolution. Tags offered by Analytics come only from scored Predictions. Brier scores, calibration bins, and cumulative points remain derived and are never written back to SQLite. [ADR 0006](decisions/0006-fixed-calibration-and-cumulative-brier.md) records the analytical construction.

Milestone 11 migrates the database to version 8 by adding a nullable canonical UTC `last_successful_backup_at` to the singleton settings row. It records only an artifact that has already been installed successfully; cancellation and artifact failure leave the prior value intact. No export metadata or analytical copy is persisted. [ADR 0007](decisions/0007-online-backup-and-relational-csv-export.md) records the transfer approach.

Milestone 13 migrates the database to version 9 while preserving the existing binary schema and every historical row. `predictions.prediction_type` now admits `binary` and `numeric`; Numeric Predictions require an immutable unit label and decimal precision from zero through six, while Binary Predictions require both fields to remain null. Numeric interval revisions live in the parallel `numeric_forecast_revisions` table so the released binary table and its Journal and Resolution references remain untouched. Lower bound, central estimate, and upper bound are exact signed scaled integers at the parent Prediction's precision, with inclusive ordering and whole-number confidence from 1% through 99%. Type guards prevent revisions from crossing Prediction types, and the numeric table applies the same sequence, timestamp, update, direct-delete, and replacement protections as binary history. [ADR 0009](decisions/0009-scaled-integer-numeric-values.md) records the representation and migration boundary.

Historically consequential edits use `prediction_definition_changes` as described in [ADR 0003](decisions/0003-immutable-definition-snapshots.md). Question and Resolution Criteria confirmations address possible changes to proposition meaning and recommend a new Prediction for a materially different proposition. Forecast Deadline confirmations instead describe changes to the forecast cutoff and derived locking. One confirmed save stores one immutable row containing complete before/after snapshots of Question, Resolution Criteria, and Forecast Deadline plus a canonical UTC instant. Expected Resolution remains outside this history. The current prediction remains the canonical source for current metadata; Definition history preserves interpretive context rather than event-sourcing the prediction. Deliberate future parent deletion can cascade to its revisions, tag associations, and definition history transactionally. Later schema additions arrive with the slice that needs them.

### Canonical and derived data

Canonical facts include the prediction, every saved binary or numeric forecast revision, every definition-change snapshot, every Journal entry and correction version, immutable Resolutions and Invalidations, and tag relationships. Derived values normally include:

- current forecast;
- current displayed Journal body and unified timeline ordering;
- time-dependent Locked status;
- Needs Attention;
- Ready to Resolve;
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
- Correcting a Journal entry rechecks its reviewed latest-correction token inside one immediate transaction and appends one changed body version. An effective no-op returns the existing entry without acquiring a new timestamp or writing.
- Resolution rechecks the reviewed revision and metadata version, records the outcome and exact scoring revision, and persists terminal status atomically.
- Invalidation rechecks the same reviewed context and records terminal state, timestamp, and optional reason atomically.
- Deletion requires explicit confirmation, rechecks untouched Open eligibility, and cascades the eligible parent and its initial child state atomically.
- Updating the stale threshold validates the value and replaces the singleton setting in one transaction; it does not mutate any Prediction or history row.
- Backup uses SQLite's online backup API to capture a consistent snapshot, verifies a temporary database, atomically installs it, and only then records the successful time in the source settings.
- CSV export reads all nine related tables inside one immediate transaction, closes that transaction, then serializes and validates a temporary ZIP before atomically installing it. It never updates canonical state.

Expected domain or validation failures roll back the operation and are translated into clear user-facing messages. Unexpected persistence failures are not silently swallowed.

## 10. Time and lifecycle

Terminal states—Resolved and Invalid—are persisted one-way v0.1 decisions backed by immutable terminal records. Locked is derived from the Forecast Deadline and the computer's local calendar date, so it remains correct after the application has been closed across the boundary. The deadline date is inclusive: an otherwise Open prediction becomes Locked only when the local date is later than its Forecast Deadline. Open predictions without a deadline remain Open until a terminal decision.

Open and derived Locked predictions accept new Journal entries; Resolved and Invalid predictions reject them. Transparent corrections to existing entries remain allowed in every lifecycle state because they preserve the original assertion rather than create a backdated one.

Needs Attention and Ready to Resolve are derived classifications, not stored lifecycle states. They may overlap and must not mutate probability. Needs Attention begins when at least the configured number of complete 24-hour periods has elapsed since the latest ForecastRevision's canonical UTC instant; the persisted v0.1 default is 14 days. Neither adding nor correcting a Journal entry resets it. Ready to Resolve begins when the computer's local date is later than the inclusive Expected Resolution date. Terminal Predictions participate in neither classification.

System-generated instants follow [ADR 0002](decisions/0002-canonical-utc-instants.md): application operations obtain one aware instant from an injectable clock, normalize it to UTC, and the data layer stores canonical RFC 3339 text ending in `Z`. Definition, Forecast, Journal, and correction history render stored instants in the computer's local time. Date-only values retain calendar semantics and are not converted between time zones.

## 11. Analytics flow

The implemented ordinary scoring pipeline is:

```text
candidate prediction, resolution, and revision data
  -> exclude Invalid and unresolved predictions
  -> select one final eligible revision per prediction
  -> pair probability with binary outcome
  -> calculate Brier and calibration observations
  -> aggregate for summaries and time series
  -> render in the Analytics UI
```

Selection logic and calculation logic require tests independent of chart widgets. Tag filtering should constrain the observation set before aggregation. Probability-history charts use all revisions for one prediction, while scoring uses exactly one eligible revision; these are separate data products and must not share misleading selection behavior.

The source query returns each Resolution's captured scoring revision and associated tags in canonical resolution-time and identifier order. Pure analytics code validates unique Prediction and Resolution contributions, maps Yes to 1 and No to 0, calculates binary Brier on the 0-through-1 scale, applies the tag subset, and builds all outputs from that common filtered set. Calibration uses fixed `0-9%` through `90-100%` bands; occupied points use actual forecast means and observed Yes frequencies. The trend is the cumulative mean at each resolution. UI charts consume these results and cannot change selection or aggregation.

## 12. UI data flow

`MainWindow` owns navigation and screen coordination. New Prediction keeps Question and whole-number Probability primary and places optional initial rationale, metadata, dates, and tags in a collapsed, scrollable **More details** section. One operation saves all supplied initial state atomically and navigates to Prediction Detail. Because these values establish the initial definition rather than edit an existing one, they require no metadata confirmation and append no definition-change record. An initial Forecast Deadline earlier than the current local calendar date is rejected; today is valid because the deadline is inclusive. Expected Resolution is independent and may be in the past or on either side of the deadline.

Prediction Detail displays the question, current forecast, derived status, tags, and nonempty optional metadata. It refreshes when entered so date-derived status and external edits do not remain stale across navigation. Its edit dialog refreshes the prediction before opening, accepts optional text, date-only fields, and comma-separated tags, and carries that refreshed metadata version through any confirmation prompt. An unset date is shown as blank or **Not set**, never as though today's date were stored; enabling it may seed today's date as the editable choice. Background, Expected Resolution, and tags save normally without confirmation or history. Question and Resolution Criteria changes prompt about proposition meaning and advise creating a new Prediction when the proposition changed materially. Forecast Deadline additions, changes, and removals receive tailored confirmation about the cutoff and Locked behavior, without characterizing the edit as a proposition change. A confirmed protected-field save updates metadata and tags, advances the metadata version, and appends exactly one complete definition snapshot atomically. Effective no-ops and cancelled dialogs perform no write, do not advance the version, and create no history. A version mismatch before or during the transaction rejects a stale edit for review rather than overwriting newer values.

Definition history is hidden when empty and collapsed by default when present. It shows only the protected fields that changed in each snapshot and renders the UTC change instant in local time.

For an Open prediction, **Revise Forecast** opens a side-effect-free dialog showing the reviewed current probability, a whole-number replacement probability, and optional **What changed?** rationale. The new value must differ from the current revision; returning to an older, non-current probability is valid. A successful save refreshes Current Forecast and the unified timeline, whose Forecast entries show each probability transition and any rationale as plain text. The dialog carries both the reviewed revision identifier and prediction metadata version, and the application rechecks both plus lifecycle eligibility inside the append transaction. A stale form is rejected rather than appending against a forecast or definition the user did not review. The action is disabled for derived Locked and persisted terminal states, with the application operation remaining authoritative if state changes while the dialog is open.

For an Open or Locked prediction, **Add Journal Entry** opens a side-effect-free dialog showing the reviewed forecast and accepting a required multiline body; ordinary Enter inserts a newline and Ctrl+Enter saves. It carries the reviewed current-revision and metadata-version tokens, and stale context is rejected rather than attaching reasoning to a forecast or definition the user did not review. The action is disabled for Resolved and Invalid predictions, with the application operation remaining authoritative.

Prediction Detail displays Forecast and Journal events in one causal timeline. Journal entries show their original local timestamp, current body, and **Forecast at the time**. **Correct Entry** is available in every lifecycle state and opens the latest body in a transparent correction dialog. After a changed save, the entry remains at its original timeline position, gains an **Edited** timestamp, and exposes the original plus superseded versions in a collapsed **Edit history**. No individual Journal Delete action exists. Timeline text uses plain-text rendering.

Below the timeline, Prediction Detail reuses `list_forecast_revisions` to populate a native, theme-aware probability-history widget. The chart paints exactly one marker per revision on a fixed 0% through 100% vertical scale. Actual stored instants determine elapsed horizontal position and display in local time. Revisions connect in immutable sequence order using step-after geometry, so a probability stays level until the next revision; equal instants share one horizontal position, and a regressing system clock may cause the line to travel backward rather than trigger timestamp re-sorting or synthetic offsets. A single marker receives symmetric horizontal padding. The widget's accessible summary and the exact textual Forecast entries in the timeline make the same history available without relying on the visual plot. Journal events never enter the chart.

The chart is implemented with a dedicated `QPainter` widget and the active Qt palette as recorded in [ADR 0004](decisions/0004-native-probability-history-chart.md). It introduces no external chart library, schema state, or analytics calculation.

For an Open or Locked prediction, **Resolve** opens a deliberate terminal dialog requiring Yes or No and accepting optional factual Resolution notes and reflective Postmortem text. The dialog shows the reviewed scoring forecast and carries revision and metadata-version tokens. A successful transaction captures that exact transaction-current revision, persists the outcome, and refreshes Detail with outcome, local resolution time, scoring forecast, and nonempty notes. **Mark Invalid** follows the same refresh and token discipline, accepts an optional reason, and displays the preserved non-scored terminal decision. Both dialogs explain that v0.1 provides no reopen or correction flow. Terminal predictions disable both actions as well as revisions and new Journal entries; audited correction of an existing Journal entry remains available.

**Delete** is enabled only when the refreshed Detail query reports an untouched Open prediction. It presents a permanent-action confirmation without mutating on Cancel. The confirmed operation rechecks all eligibility and concurrency facts inside its transaction. Locked or meaningful nonterminal history instead exposes **Mark Invalid**, while terminal history cannot be deleted through the normal interface. Widgets perform no SQL and own no transactions.

Dashboard refreshes at startup, whenever it is entered, and once per minute while it remains visible; the timer stops on other screens. It queries all nonterminal Predictions with their current ForecastRevision, derives deadline status and attention against one current instant, then renders four counted sections. Open and Locked are lifecycle views; Needs Attention and Ready to Resolve are overlapping action views, so a Prediction may appear in several sections with all applicable labels intact. Each row says **Forecast last updated**, shows the current probability, and opens freshly queried Prediction Detail. Empty sections remain explicit rather than disappearing. Settings currently exposes only the persisted Needs Attention threshold; saving it immediately refreshes Dashboard without adding a general settings framework.

Predictions refreshes whenever it is entered and once per minute while visible so its Open and Locked views remain correct across local-date boundaries. Question search trims surrounding whitespace and uses Unicode-aware case-insensitive substring matching over Question only; v0.1 does not silently extend this to Background, rationales, or Journal bodies. Status choices are All, Open, Locked, Resolved, and Invalid. The single tag filter uses stable stored display spelling and combines with search and status using logical AND. Results show current probability, derived lifecycle status, associated tags, and latest forecast time, use explicit new-database and no-match empty states, and load current Prediction Detail before navigation. A failed initial query is not presented as an empty archive; a failed refresh retains earlier rows only with an explicit warning.

Analytics refreshes whenever it is entered and on explicit refresh or tag change. Its scored count, mean Brier, reliability diagram, complete ten-row bin table, and cumulative trend always represent one common subset. Empty bins remain visible in the table with count zero but add no chart point. Both charts expose nonvisual summaries; the table makes calibration sparsity directly accessible. Empty All and empty filtered states are distinct, expected read failures are not shown as zero scores, and a failed refresh retains prior results only with a warning. Labels say lower Brier is better and explicitly avoid treating cumulative movement as proof of skill improvement.

Settings displays the canonical database path and last successful backup time alongside the existing attention threshold. **Back Up Now** and **Export CSV Bundle** use native save dialogs with timestamped suggestions. Cancel is side-effect free. Expected path, file, SQLite, or archive failures remain visible without replacing a previous destination artifact. Backup success updates the displayed time; CSV success reports the nine generated tables while continuing to label the ZIP as non-restorable analytical data.

A screen requests view data through an application query, renders it, and invokes a complete operation in response to user intent. After a successful mutation, the relevant view is re-queried or updated from the operation result. Widgets should not maintain an independent canonical copy of prediction state.

Dialog cancellation has no side effect. In particular, opening and closing a revision, Journal, correction, Resolution, or Invalidation dialog cannot create history or terminal state.

Expected failures—such as attempting a revision after the deadline—are shown in plain language. Unexpected exceptions should remain visible to the application error boundary during development rather than being suppressed in individual signal handlers.

## 13. Migrations and compatibility

Database evolution uses the lightweight mechanism recorded in [ADR 0001](decisions/0001-lightweight-sqlite-migrations.md). `data/migrations.py` contains an immutable, contiguous sequence of numbered and uniquely named migrations. The `schema_migrations` table records each applied version and name rather than relying on `PRAGMA user_version`.

Startup opens an explicit `BEGIN IMMEDIATE` transaction, validates the bundled registry and the database's complete recorded history, applies all pending SQL statements in order, checks foreign-key integrity, and commits. Any failure rolls back the whole pending migration set. Running startup again when nothing is pending is idempotent.

An empty database can receive the baseline. A nonempty SQLite database without Reckonsolve migration history is unrecognized and rejected. An empty, malformed, gapped, renamed, or otherwise inconsistent migration history is rejected, as is a schema version newer than the running application understands. These failures never trigger database deletion or recreation.

Each future migration must be tested against the prior schema state, preserve existing user data, and leave the database reopenable. The version 9 upgrade is tested from version 8 with an existing Binary Prediction and revision history, preserves the binary query path, adds no invented numeric rows, and rolls back completely if the type-column or numeric-table migration fails. Earlier version-specific migration tests remain pinned to their historical targets, including the version 7-to-8 backup-setting checks. Already released migrations are historical records and must not be edited. A third-party migration framework still requires a demonstrated need.

## 14. Backup and export

Backup and CSV export have separate implemented contracts:

- Backup produces a consistent artifact sufficient to recover the full application state.
- CSV export produces documented, portable analytical data and may use several related files to preserve historical structure honestly.

Backup uses the standard-library binding to SQLite's online backup API. It writes to a unique temporary database beside the chosen destination; runs SQLite quick, foreign-key, and schema-version checks; closes the temporary connection; then uses same-directory atomic replacement. The canonical database path, including an equivalent hard link, is rejected as a destination. Failure cleanup targets only the owned temporary file, and an existing destination remains untouched until installation succeeds.

CSV export reads canonical rows in one transaction and then uses the standard-library `csv` and `zipfile` modules. Its nine files mirror the historical relationships through stable identifiers rather than flattening one-to-many records. CSV uses UTF-8 with a byte-order mark, CRLF rows, and quoted fields; `README.txt` documents columns, joins, blank nulls, UTC instants, ISO dates, derivation rules, and spreadsheet handling of formula-like free text. The ZIP follows the same temporary-write, validation, and atomic-install discipline as backup. Neither workflow adds a production dependency.

## 15. Private Windows build

PyInstaller 6.22.2 is an exact, locked build-only dependency in the `packaging` dependency group. It is not imported by the application, included as a runtime library, or required for normal development. The checked-in spec produces a windowed `onedir` bundle, collects only the application's imported code plus selected UI resources and license notices, and deliberately supplies no invented Reckonsolve icon. `onedir` keeps the first private build inspectable and gives clearer missing-resource diagnostics than a self-extracting executable.

`tools/build_windows.ps1` synchronizes the locked group, replaces only generated PyInstaller output under ignored `build/` and `dist/` directories, and then copies the completed bundle to a unique ignored smoke directory. It launches the copied executable with an internal private-smoke argument and an offscreen Qt platform from that relocated working directory. The executable verifies that it is actually frozen, creates a disposable database at the immediately previous schema with seed data, constructs the real main window so startup migrates that data and every local resource is loaded, creates and revises another Prediction, appends a Journal entry, creates a verified backup, closes, and reopens both source and backup databases. The source checkout, Python interpreter, and `uv` are used to build but are not used by the smoke process.

This artifact is a development validation output, not a supported release. There is no installer, Start menu integration, shortcut ownership, uninstaller, code signature, update channel, or public download contract. [ADR 0008](decisions/0008-private-onedir-and-local-icons.md) records why this narrow build exists.

## 16. Testing strategy

The suite covers package entry points, runtime composition, paths, database/migrations, clocks, domain validation, prediction operations, pure analytics, data transfer, and Qt screens. It uses explicit temporary databases for initialization, upgrades through schema version 9, atomicity, restart, and cleanup scenarios, and pytest-qt only for GUI behavior. M3 through M10 retain their historical, lifecycle, Dashboard, archive, and analytics coverage. M11 adds v7-to-v8 migration safety, complete backup recovery, SQLite integrity verification, last-success persistence, live-database destination rejection, exact ZIP membership and CSV relationships, multiline/quoted text round trips, empty exports, failed-replacement preservation, cancel/error UI behavior, and end-to-end Settings recovery after restart. M12 adds exact icon-resource inventory and version checks, palette-dependent rendering, retained text/accessibility, stable/development path separation, disposable private-smoke safety, and a real relocated frozen-executable smoke run. M13 adds exact signed fixed-precision conversion, precision and magnitude boundaries, inclusive interval validation, confidence endpoints, type-specific persistence, binary-data-preserving v8-to-v9 migration, immutable numeric revisions, creation rollback, and reopen tests without exercising real user data.

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

Expected errors should use explicit application or domain error types that the UI can present without a traceback. Examples include invalid probability, missing question or Journal text, an action disallowed by lifecycle, stale forecast or metadata context, and a concurrently corrected Journal entry.

Unexpected exceptions should not be converted into false success or empty data. Database failures must preserve the original database and provide enough context for diagnosis without exposing unrelated local information.

## 18. Decisions intentionally deferred

The M12 resource, identity, and private-build boundary is implemented. The original application icon remains pending because its artwork must be directed or supplied by the user; the current private executable therefore retains PyInstaller's generic default rather than pretending to establish Reckonsolve's permanent mark.

A normal installer, uninstall policy, code signing, public distribution channel, and automatic updates remain Later decisions. When one becomes consequential, seek explicit user authorization before changing the product specification. Record durable technical reasoning in an [architecture decision record](decisions/README.md) when appropriate.

## 19. Evolution into v0.2

The approved v0.2 product plan adds one central numeric prediction interval per revision and explicit Forecast Reviews through Milestones 13 through 20. Milestone 13 is now implemented: the schema-v9 application has exact numeric definition and revision concepts plus type-safe persistence, while its user-facing workflows intentionally remain the completed Binary application. It has no numeric application operations, numeric UI, Numeric Journal or Resolution persistence, numeric analytics, or Review entity yet.

The architecture will continue through implemented vertical slices rather than prebuilding the whole release. Milestone 14 owns the first user-visible Numeric creation, detail, and revision workflow on top of the M13 boundary. After each milestone, update this document to reflect actual modules, persistence behavior, and any recorded technical decisions; do not describe planned structures as already implemented.
