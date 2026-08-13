# Reckonsolve Architecture

Status: Milestone 6 implemented; later forecasting workflows remain to be built
Last reviewed: 2026-08-13

This document describes how Reckonsolve is structured and how its implementation should evolve through v0.1. The [product specification](product-spec.md) governs product behavior, scope, terminology, and acceptance criteria. This document translates those requirements into technical boundaries without replacing them.

## 1. Current implementation

Milestone 6 adds a native probability-history chart to the complete creation, immutable-revision, Journal, and unified-timeline workflows. Prediction Detail now plots every immutable ForecastRevision on a fixed 0% through 100% scale against actual stored time. A sequence-ordered step line represents the probability held between revisions without turning Journal events into probability observations. Terminal lifecycle actions, browser, scoring analytics, backup, and export workflows remain to be built.

| Area | Current state |
|---|---|
| Project management | `uv` project with Python 3.13 pinned in `.python-version` |
| Runtime dependency | PySide6 |
| Development tools | pytest, pytest-qt, and Ruff |
| Python package | `src/reckonsolve/` |
| Entry points | The `reckonsolve` console script and `python -m reckonsolve` both compose the desktop application through `app.py` |
| Application runtime | `ApplicationRuntime` owns the `QApplication`, open `Database`, and `MainWindow`; startup composes concrete prediction operations and shutdown closes persistence |
| UI | Native PySide6 navigation plus functional New Prediction and Prediction Detail screens; optional initial details, metadata editing, revision entry, Journal capture and correction, Definition history, a unified timeline, and native probability-history rendering are implemented, while the other four primary screens remain explicit placeholders |
| Runtime path | Qt `AppLocalDataLocation`, which resolves on Windows to `%LOCALAPPDATA%\Reckonsolve`; tests can inject an explicit database path |
| Persistence | One standard-library `sqlite3` connection with foreign keys enabled, a five-second busy timeout, and explicit immediate transactions |
| Schema | Version 5 adds immutable Journal entries and append-only correction versions, building on protected forecast revisions, prediction metadata, tags, and definition snapshots |
| Domain and application operations | Complete atomic creation, append-only forecast revisions, ordered forecast-history reads, Journal capture and correction, deterministic unified-timeline reads, validation, derived deadline status, lifecycle enforcement, stale-context rejection, and safe metadata editing are implemented without Qt dependencies |
| Analytics | Scoring analytics are not implemented; the Prediction Detail chart is a presentation of all revisions, not an analytics aggregate |
| Automated tests | Tests cover the persistence foundation plus complete creation, immutable revisions and Journal history, causal timeline ordering, probability-history projection and rendering, lifecycle and date boundaries, concurrent submissions and corrections, metadata safety, migrations through v5, transaction rollback, Qt behavior, and restart persistence |
| Windows packaging | Not implemented; the packaging format remains undecided |

The sections below distinguish the current implementation from the boundaries still intended for later v0.1 slices.

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

The analytics boundary will contain:

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

Milestone 6 implements this package structure:

```text
src/reckonsolve/
  __init__.py          public `main()` console entry point
  __main__.py          `python -m reckonsolve` entry point
  app.py               QApplication composition, runtime ownership, and startup errors
  clock.py             injectable clock and canonical UTC instant conversion
  paths.py             per-user and explicitly injected database paths
  application/
    errors.py          expected user-presentable operation and concurrency errors
    predictions.py     creation, revision, Journal, timeline, detail, and metadata use cases
  domain/
    predictions.py     prediction, revision, Journal/timeline, metadata, status, and validation values
  data/
    __init__.py        persistence package surface
    database.py        connection ownership and transaction boundary
    migrations.py      ordered schema registry, validation, and migration runner
    predictions.py     purpose-specific prediction, revision, Journal, tag, and history persistence
  ui/
    __init__.py        UI package surface
    main_window.py     navigation and screen coordination
    probability_history_chart.py
                       native probability-history projection and painting
    screens.py         creation, Prediction Detail, revision, Journal, chart, and metadata-edit UI
```

Later milestones can extend these boundaries and add analytics when real behavior requires it. Empty abstractions are not added merely to complete a diagram.

Tests should live under `tests/` and generally mirror the behavior boundary they exercise rather than mirror every source file mechanically.

## 7. Application composition and startup

The package-level entry point delegates immediately to `app.py`. Startup currently:

1. sets the Qt application name to Reckonsolve and creates or reuses the `QApplication`;
2. resolves `%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3` through Qt's `AppLocalDataLocation`, unless an explicit database path was supplied;
3. opens one long-lived SQLite connection, enables foreign keys and the busy timeout, and applies pending migrations;
4. composes `PredictionOperations` with that database and a system UTC clock;
5. constructs the six-screen `MainWindow` with those operations;
6. returns an `ApplicationRuntime` that owns the Qt application, database, and window; and
7. shows the window and enters the Qt event loop.

The production runner catches expected path, migration, operating-system, and SQLite startup failures and presents a fatal database error. It does not replace or silently recreate an existing database. The runner's `finally` cleanup closes the database after the Qt event loop ends or if showing the window fails; close is idempotent.

`create_runtime()` accepts an explicit database path so tests never discover or open the real user database. The clock and application operations are composed at this boundary rather than through global state or widget-side service lookup; later operations should follow the same pattern.

## 8. Persistence model

The minimum conceptual entities are defined by the product specification:

- predictions;
- forecast revisions;
- prediction definition changes;
- journal entries;
- resolutions;
- tags; and
- prediction-tag associations.

Milestone 1 established the migration ledger. Milestone 2 added `predictions` and `forecast_revisions`. A prediction stores identity, question, binary type, persisted lifecycle state (`open`, with terminal states used by later milestones), and UTC creation/update instants; it does not store probability. Every forecast revision stores its own 0–100 whole-number probability, UTC creation instant, and per-prediction sequence. A uniqueness constraint makes sequence deterministic, a foreign key protects ownership, and a trigger prevents in-place revision updates.

Milestone 3 migrates the database to version 3. Nullable Background and Resolution Criteria are normalized text, while Forecast Deadline and Expected Resolution are ISO calendar dates rather than instants. The supported metadata-date range is `1752-09-14` through `9999-12-31`, matching the native Qt editor; these fields model current and future forecasting workflow dates rather than historical chronology. Reusable `tags` connect through `prediction_tags`. Python `casefold()` values provide case-insensitive identity, and the first stored display spelling is retained even when a tag temporarily has no prediction associations. Commas and line breaks are excluded from labels because the v0.1 editor uses a comma-separated entry field. A constrained metadata version on each prediction provides optimistic concurrency control for whole-form edits.

Milestone 4 migrates the database to version 4 by adding a nullable normalized rationale to every forecast revision. Existing revisions receive no invented rationale. Revision identity and per-prediction sequence remain deterministic; database triggers reject direct updates, direct child deletion while the parent exists, and replacement through either an existing revision identifier or sequence. A deliberate parent-prediction deletion can still cascade transactionally. The application derives the current forecast from the highest revision sequence and reads forecast history in sequence order, even if two revisions share the same stored instant.

Milestone 5 migrates the database to version 5 with `journal_entries` and `journal_entry_corrections`. A Journal entry stores its original normalized body, original UTC timestamp, and a composite foreign-key reference to a ForecastRevision owned by the same Prediction. Insert-time guards require that reference to be the current revision and reject new entries after a persisted terminal status. Derived Locked predictions remain eligible because Locked is represented by an otherwise-open Prediction whose inclusive deadline has passed.

Journal corrections are separate immutable rows with a per-entry contiguous sequence, normalized replacement body, and UTC correction timestamp. The latest correction supplies the displayed body; the base entry and all correction rows supply the complete edit history. Database triggers reject unchanged correction bodies, sequence gaps, direct updates, direct child deletion while the parent exists, and replacement of saved entry or correction identities. Corrections do not change the entry's original timestamp or forecast anchor and remain possible after a terminal lifecycle decision. A deliberate parent-Prediction deletion can still cascade through entries and corrections.

The unified timeline is a derived read model rather than another persisted event table. Forecasts are ordered by revision sequence. Each Journal entry is placed after its anchored revision and before the next revision; multiple entries sharing one anchor retain insertion order by stable entry identifier. This causal ordering remains deterministic even when stored timestamps tie or the system clock moves backward. Stored event timestamps are still shown to the user in local time, and correcting an entry never moves it in the timeline.

Milestone 6 requires no schema change. Probability history is another derived presentation of the existing `forecast_revisions` rows returned in immutable sequence order. Each row contributes one chart marker. Stored UTC instants determine horizontal position and render in local time, while sequence determines connection order and which marker is current. Journal rows never enter this read product.

Historically consequential edits use `prediction_definition_changes` as described in [ADR 0003](decisions/0003-immutable-definition-snapshots.md). Question and Resolution Criteria confirmations address possible changes to proposition meaning and recommend a new Prediction for a materially different proposition. Forecast Deadline confirmations instead describe changes to the forecast cutoff and derived locking. One confirmed save stores one immutable row containing complete before/after snapshots of Question, Resolution Criteria, and Forecast Deadline plus a canonical UTC instant. Expected Resolution remains outside this history. The current prediction remains the canonical source for current metadata; Definition history preserves interpretive context rather than event-sourcing the prediction. Deliberate future parent deletion can cascade to its revisions, tag associations, and definition history transactionally. Later schema additions arrive with the slice that needs them.

### Canonical and derived data

Canonical facts include the prediction, every saved forecast revision, every definition-change snapshot, every Journal entry and correction version, terminal decisions, resolutions, and tag relationships. Derived values normally include:

- current forecast;
- current displayed Journal body and unified timeline ordering;
- time-dependent Locked status;
- Needs Attention;
- Ready to Resolve;
- Brier summaries; and
- calibration aggregates.

Derived values should not be stored merely for display convenience unless a demonstrated correctness or performance need justifies it.

### Runtime location

Qt's `AppLocalDataLocation`, after the application name is set to Reckonsolve, provides the production directory. On Windows the canonical database is:

```text
%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3
```

The database parent directory is created when needed. Future backups, exports, and logs must likewise live outside the source tree in an appropriate per-user location or a destination explicitly chosen by the user. Tests always inject temporary paths and never discover or open the real user database.

## 9. Transaction boundaries

`Database` owns one standard-library SQLite connection for the application lifetime. The connection runs in autocommit mode so transaction boundaries are always explicit. Its transaction context rejects nesting, starts with `BEGIN IMMEDIATE`, commits on success, and rolls back on any exception. Foreign-key enforcement is verified when the connection opens, and a five-second busy timeout allows brief external lock contention without waiting indefinitely.

Transactions protect operations that must not leave partial history:

- Creating a prediction, all supplied initial metadata and tag associations, and its first forecast revision with optional rationale is one transaction. Initial values do not append Definition history.
- Editing metadata and tag associations, plus the definition snapshot when required, is one transaction.
- Appending a revision rechecks the reviewed current-revision and metadata-version tokens, lifecycle eligibility, deadline, and changed probability inside one immediate transaction, then inserts exactly one new row without editing prior rows.
- Adding a Journal entry rechecks the reviewed current-revision and metadata-version tokens plus persisted lifecycle eligibility inside one immediate transaction, then captures that transaction-current revision without changing forecast or prediction state.
- Correcting a Journal entry rechecks its reviewed latest-correction token inside one immediate transaction and appends one changed body version. An effective no-op returns the existing entry without acquiring a new timestamp or writing.
- Resolution records the outcome and unambiguous scoring revision atomically.
- Invalidation records terminal state, timestamp, and optional reason atomically.
- Deletion removes or rejects all related records as one deliberate operation and cannot leave orphans.
- Backup must capture a transactionally consistent SQLite state.

Expected domain or validation failures roll back the operation and are translated into clear user-facing messages. Unexpected persistence failures are not silently swallowed.

## 10. Time and lifecycle

Terminal states—Resolved and Invalid—are persisted decisions. Locked is derived from the Forecast Deadline and the computer's local calendar date, so it remains correct after the application has been closed across the boundary. The deadline date is inclusive: an otherwise Open prediction becomes Locked only when the local date is later than its Forecast Deadline. Open predictions without a deadline remain Open until a terminal decision.

Open and derived Locked predictions accept new Journal entries; Resolved and Invalid predictions reject them. Transparent corrections to existing entries remain allowed in every lifecycle state because they preserve the original assertion rather than create a backdated one.

Needs Attention and Ready to Resolve are derived classifications, not stored lifecycle states. They may overlap and must not mutate probability. In v0.1, neither adding nor correcting a Journal entry resets Needs Attention; freshness continues to use the latest ForecastRevision timestamp.

System-generated instants follow [ADR 0002](decisions/0002-canonical-utc-instants.md): application operations obtain one aware instant from an injectable clock, normalize it to UTC, and the data layer stores canonical RFC 3339 text ending in `Z`. Definition, Forecast, Journal, and correction history render stored instants in the computer's local time. Date-only values retain calendar semantics and are not converted between time zones.

## 11. Analytics flow

The ordinary scoring pipeline is:

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

## 12. UI data flow

`MainWindow` owns navigation and screen coordination. New Prediction keeps Question and whole-number Probability primary and places optional initial rationale, metadata, dates, and tags in a collapsed, scrollable **More details** section. One operation saves all supplied initial state atomically and navigates to Prediction Detail. Because these values establish the initial definition rather than edit an existing one, they require no metadata confirmation and append no definition-change record. An initial Forecast Deadline earlier than the current local calendar date is rejected; today is valid because the deadline is inclusive. Expected Resolution is independent and may be in the past or on either side of the deadline.

Prediction Detail displays the question, current forecast, derived status, tags, and nonempty optional metadata. It refreshes when entered so date-derived status and external edits do not remain stale across navigation. Its edit dialog refreshes the prediction before opening, accepts optional text, date-only fields, and comma-separated tags, and carries that refreshed metadata version through any confirmation prompt. An unset date is shown as blank or **Not set**, never as though today's date were stored; enabling it may seed today's date as the editable choice. Background, Expected Resolution, and tags save normally without confirmation or history. Question and Resolution Criteria changes prompt about proposition meaning and advise creating a new Prediction when the proposition changed materially. Forecast Deadline additions, changes, and removals receive tailored confirmation about the cutoff and Locked behavior, without characterizing the edit as a proposition change. A confirmed protected-field save updates metadata and tags, advances the metadata version, and appends exactly one complete definition snapshot atomically. Effective no-ops and cancelled dialogs perform no write, do not advance the version, and create no history. A version mismatch before or during the transaction rejects a stale edit for review rather than overwriting newer values.

Definition history is hidden when empty and collapsed by default when present. It shows only the protected fields that changed in each snapshot and renders the UTC change instant in local time.

For an Open prediction, **Revise Forecast** opens a side-effect-free dialog showing the reviewed current probability, a whole-number replacement probability, and optional **What changed?** rationale. The new value must differ from the current revision; returning to an older, non-current probability is valid. A successful save refreshes Current Forecast and the unified timeline, whose Forecast entries show each probability transition and any rationale as plain text. The dialog carries both the reviewed revision identifier and prediction metadata version, and the application rechecks both plus lifecycle eligibility inside the append transaction. A stale form is rejected rather than appending against a forecast or definition the user did not review. The action is disabled for derived Locked and persisted terminal states, with the application operation remaining authoritative if state changes while the dialog is open.

For an Open or Locked prediction, **Add Journal Entry** opens a side-effect-free dialog showing the reviewed forecast and accepting a required multiline body; ordinary Enter inserts a newline and Ctrl+Enter saves. It carries the reviewed current-revision and metadata-version tokens, and stale context is rejected rather than attaching reasoning to a forecast or definition the user did not review. The action is disabled for Resolved and Invalid predictions, with the application operation remaining authoritative.

Prediction Detail displays Forecast and Journal events in one causal timeline. Journal entries show their original local timestamp, current body, and **Forecast at the time**. **Correct Entry** is available in every lifecycle state and opens the latest body in a transparent correction dialog. After a changed save, the entry remains at its original timeline position, gains an **Edited** timestamp, and exposes the original plus superseded versions in a collapsed **Edit history**. No individual Journal Delete action exists. Timeline text uses plain-text rendering.

Below the timeline, Prediction Detail reuses `list_forecast_revisions` to populate a native, theme-aware probability-history widget. The chart paints exactly one marker per revision on a fixed 0% through 100% vertical scale. Actual stored instants determine elapsed horizontal position and display in local time. Revisions connect in immutable sequence order using step-after geometry, so a probability stays level until the next revision; equal instants share one horizontal position, and a regressing system clock may cause the line to travel backward rather than trigger timestamp re-sorting or synthetic offsets. A single marker receives symmetric horizontal padding. The widget's accessible summary and the exact textual Forecast entries in the timeline make the same history available without relying on the visual plot. Journal events never enter the chart.

The chart is implemented with a dedicated `QPainter` widget and the active Qt palette as recorded in [ADR 0004](decisions/0004-native-probability-history-chart.md). It introduces no external chart library, schema state, or analytics calculation. Resolve and Mark Invalid remain visibly disabled. Widgets perform no SQL and own no transactions.

A screen requests view data through an application query, renders it, and invokes a complete operation in response to user intent. After a successful mutation, the relevant view is re-queried or updated from the operation result. Widgets should not maintain an independent canonical copy of prediction state.

Dialog cancellation has no side effect. In particular, opening and closing a revision, Journal, or correction dialog cannot create history.

Expected failures—such as attempting a revision after the deadline—are shown in plain language. Unexpected exceptions should remain visible to the application error boundary during development rather than being suppressed in individual signal handlers.

## 13. Migrations and compatibility

Database evolution uses the lightweight mechanism recorded in [ADR 0001](decisions/0001-lightweight-sqlite-migrations.md). `data/migrations.py` contains an immutable, contiguous sequence of numbered and uniquely named migrations. The `schema_migrations` table records each applied version and name rather than relying on `PRAGMA user_version`.

Startup opens an explicit `BEGIN IMMEDIATE` transaction, validates the bundled registry and the database's complete recorded history, applies all pending SQL statements in order, checks foreign-key integrity, and commits. Any failure rolls back the whole pending migration set. Running startup again when nothing is pending is idempotent.

An empty database can receive the baseline. A nonempty SQLite database without Reckonsolve migration history is unrecognized and rejected. An empty, malformed, gapped, renamed, or otherwise inconsistent migration history is rejected, as is a schema version newer than the running application understands. These failures never trigger database deletion or recreation.

Each future migration must be tested against the prior schema state, preserve existing user data, and leave the database reopenable. The version 5 upgrade is tested from version 4 and rolls back completely if any Journal schema statement fails. Already released migrations are historical records and must not be edited. A third-party migration framework still requires a demonstrated need.

## 14. Backup and export

Backup and CSV export have separate contracts:

- Backup produces a consistent artifact sufficient to recover the full application state.
- CSV export produces documented, portable analytical data and may use several related files to preserve historical structure honestly.

The backup implementation must use a SQLite-safe snapshot approach rather than copying a potentially changing database file blindly. Export code reads through the data boundary and must not mutate canonical state.

## 15. Testing strategy

The suite covers package entry points, runtime composition, paths, database/migrations, clocks, domain validation, prediction operations, and Qt screens. It uses explicit temporary databases for initialization, upgrades through schema version 5, atomicity, restart, and cleanup scenarios, and pytest-qt only for GUI behavior. M3 coverage remains for optional-value normalization, calendar-date validation, inclusive deadline derivation, case-insensitive tag reuse, confirmation and no-op behavior, full immutable snapshots, transaction rollback, concurrency rejection, collapsed local-time history rendering, and metadata persistence. M4 adds complete-creation rollback and restart tests, initial-deadline boundaries, rationale persistence and normalization, unchanged and nonconsecutive probability behavior, immutable append and replacement protection, lifecycle enforcement, stale revision/metadata context rejection, sequence-ordered local-time history, and revision-dialog cancellation. M5 adds Journal normalization and atomic forecast capture, lifecycle boundaries, immutable correction sequences, terminal corrections, no-op and stale-form behavior, database immutability guards, causal ordering under equal or regressing clocks, unified Qt rendering, dialog cancellation, and full timeline persistence across restart. M6 adds native chart tests for one-revision layout, fixed probability endpoints, actual elapsed-time projection, sequence-ordered step geometry, equal and regressing timestamps, nonconsecutive repeated probabilities, revision-only marker selection, accessibility text, refresh behavior, and restart-backed history.

Most behavior should be verified below the GUI:

- pure unit tests for probability, lifecycle, attention, revision selection, probability-history projection, and scoring rules;
- temporary-SQLite integration tests for transactions, constraints, queries, migrations, restart persistence, and backup consistency;
- pytest-qt tests only for behavior that genuinely depends on Qt signals, widgets, navigation, or dialog cancellation; and
- a small application smoke test for startup against a temporary data directory.

Tests use fixed clocks, explicit temporary paths, and representative boundary cases. The normal verification commands are:

```text
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## 16. Error handling

Expected errors should use explicit application or domain error types that the UI can present without a traceback. Examples include invalid probability, missing question or Journal text, an action disallowed by lifecycle, stale forecast or metadata context, and a concurrently corrected Journal entry.

Unexpected exceptions should not be converted into false success or empty data. Database failures must preserve the original database and provide enough context for diagnosis without exposing unrelated local information.

## 17. Decisions intentionally deferred

The product specification lists choices that must be made at their relevant milestones. Architecture must not settle them indirectly. They include:

- visual design details;
- stale threshold default;
- calibration bins;
- cumulative versus windowed Brier trend;
- deletion restrictions after meaningful history;
- CSV layout; and
- Windows packaging format.

When one of these choices becomes consequential, seek explicit user authorization before changing the product specification. Record durable technical reasoning in an [architecture decision record](decisions/README.md) when appropriate.

## 18. Evolution beyond v0.1

Numeric forecasts and Forecast Reviews are v0.2 work. v0.1 should avoid choices that make later extension needlessly destructive, but it must not add unused tables, generalized forecast-type frameworks, review entities, or UI abstractions in anticipation of them.

The architecture evolves through implemented vertical slices. After each milestone, update this document to reflect actual modules, persistence behavior, and any recorded technical decisions.
