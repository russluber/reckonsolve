# Reckonsolve Architecture

Status: Initial architecture direction; implementation is at the project-scaffold stage  
Last reviewed: 2026-08-12

This document describes how Reckonsolve is structured and how its implementation should evolve through v0.1. The [product specification](product-spec.md) governs product behavior, scope, terminology, and acceptance criteria. This document translates those requirements into technical boundaries without replacing them.

## 1. Current implementation

The repository currently contains a packaged Python application scaffold, not a functional forecasting journal.

| Area | Current state |
|---|---|
| Project management | `uv` project with Python 3.13 pinned in `.python-version` |
| Runtime dependency | PySide6 |
| Development tools | pytest, pytest-qt, and Ruff |
| Python package | `src/reckonsolve/` |
| Entry point | `reckonsolve = "reckonsolve:main"` |
| Application behavior | A placeholder `main()` function prints a greeting |
| UI, domain, database, analytics | Not implemented yet |
| Automated tests | One package entry-point smoke test; functional tests are not implemented yet |
| Windows packaging | Not implemented; the packaging format remains undecided |

The sections below define the intended v0.1 boundaries. Module names are illustrative until the corresponding milestone creates them. As code is implemented, this section and the package map must be updated to describe reality.

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

The architecture must make the honest path the easy path. Forecast changes append immutable revisions. Current state, lifecycle classifications, and analytics are derived from preserved records rather than maintained through destructive updates.

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

### Application operations

This layer coordinates complete user actions. An operation validates a request, applies domain rules, opens the required transaction through the data-access boundary, and returns either a result suitable for presentation or an expected application error.

Representative operations include:

- creating a prediction and its first revision;
- appending a forecast revision;
- adding a journal entry tied to the current revision;
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

No normal data-access operation may update or delete a saved forecast revision. Migration code is the exceptional maintenance path and must preserve legitimate history.

### Analytics

Analytics code owns scoring selection and aggregation, separate from chart rendering. Its input is candidate prediction, resolution, and revision data obtained through the data-access boundary. It constructs exactly one scoring observation for each included resolved prediction by selecting that prediction's final eligible revision according to the product specification.

The analytics boundary will contain:

- final-eligible-revision selection;
- per-prediction Brier calculation;
- mean Brier calculation;
- calibration bin assignment and aggregation; and
- the explicitly labeled Brier-over-time series.

UI chart code consumes analytics results; it does not decide which forecasts count.

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

## 6. Expected package shape

The exact modules should emerge milestone by milestone. The expected responsibility map is:

```text
src/reckonsolve/
  __init__.py          public package surface and current console entry point
  __main__.py          optional `python -m reckonsolve` entry point
  app.py               QApplication composition and startup
  clock.py             centralized time source
  paths.py             per-user runtime paths
  domain/              entities, value objects, lifecycle rules, validation
  application/         user-facing operations and expected errors
  data/                SQLite connections, migrations, transactions, queries
  analytics/           scoring, calibration, and performance series
  ui/                  PySide6 windows, screens, dialogs, models, formatting
```

This is a map of responsibilities, not a requirement to create every package before it has code. Empty abstractions should not be added merely to match the diagram.

Tests should live under `tests/` and generally mirror the behavior boundary they exercise rather than mirror every source file mechanically.

## 7. Application composition and startup

The application entry point should remain small. At startup it will:

1. create or obtain the `QApplication`;
2. resolve the per-user application-data location;
3. open the SQLite database and enable required connection settings;
4. apply pending migrations safely;
5. construct the clock, data-access objects, and application operations;
6. construct the main window with those operations; and
7. enter the Qt event loop.

On shutdown, open resources should close cleanly. A migration or database-open failure must produce a clear error and must not fall back to replacing or silently recreating an existing user database.

Composition belongs at the application edge. Avoid global mutable application state and avoid service-locator access from widgets.

## 8. Persistence model

The minimum conceptual entities are defined by the product specification:

- predictions;
- forecast revisions;
- journal entries;
- resolutions;
- tags; and
- prediction-tag associations.

Milestone 1 establishes the initial schema and migration mechanism. Later schema additions should arrive with the vertical slice that needs them rather than creating every conceptual v0.1 table in advance. Every schema version must support deterministic ordering where relevant, foreign-key integrity, preservation of existing data, and reopening the database after restart.

### Canonical and derived data

Canonical facts include the prediction, every saved forecast revision, every journal entry, terminal decisions, resolutions, and tag relationships. Derived values normally include:

- current forecast;
- time-dependent Locked status;
- Needs Attention;
- Ready to Resolve;
- Brier summaries; and
- calibration aggregates.

Derived values should not be stored merely for display convenience unless a demonstrated correctness or performance need justifies it.

### Runtime location

The real database, backups, exports, and logs must live outside the source tree in an appropriate per-user Windows location or a destination explicitly chosen by the user. Tests always receive temporary paths and must never discover or open the real user database.

## 9. Transaction boundaries

Transactions protect operations that must not leave partial history:

- Creating a prediction and its first forecast revision is one transaction.
- Appending a revision validates eligibility and inserts exactly one new row without editing prior rows.
- Adding a journal entry captures the revision that is current within the same consistent operation.
- Resolution records the outcome and unambiguous scoring revision atomically.
- Invalidation records terminal state, timestamp, and optional reason atomically.
- Deletion removes or rejects all related records as one deliberate operation and cannot leave orphans.
- Backup must capture a transactionally consistent SQLite state.

Expected domain or validation failures roll back the operation and are translated into clear user-facing messages. Unexpected persistence failures are not silently swallowed.

## 10. Time and lifecycle

Terminal states—Resolved and Invalid—are persisted decisions. Locked is normally derived from the forecast deadline and the supplied current time, so it remains correct after the application has been closed across the boundary. Open predictions without a forecast deadline remain Open until a terminal decision.

Needs Attention and Ready to Resolve are derived classifications, not stored lifecycle states. They may overlap and must not mutate probability.

All time-dependent functions accept or obtain time through the centralized clock. The local-time-versus-UTC storage and display policy remains an open product implementation decision and must be documented when the relevant milestone resolves it.

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

A screen requests view data through an application query, renders it, and invokes a complete operation in response to user intent. After a successful mutation, the relevant view is re-queried or updated from the operation result. Widgets should not maintain an independent canonical copy of prediction state.

Dialog cancellation has no side effect. In particular, opening and closing a revision dialog cannot create a revision.

Expected failures—such as attempting a revision after the deadline—are shown in plain language. Unexpected exceptions should remain visible to the application error boundary during development rather than being suppressed in individual signal handlers.

## 13. Migrations and compatibility

Database evolution uses ordered, testable migrations and a recorded schema version. The precise lightweight mechanism will be selected during Milestone 1; adding a migration framework requires a demonstrated need.

Each migration must be tested against the prior schema state, run transactionally where SQLite permits, preserve existing user data, and leave the database reopenable. Application startup must be idempotent when no migration is pending.

## 14. Backup and export

Backup and CSV export have separate contracts:

- Backup produces a consistent artifact sufficient to recover the full application state.
- CSV export produces documented, portable analytical data and may use several related files to preserve historical structure honestly.

The backup implementation must use a SQLite-safe snapshot approach rather than copying a potentially changing database file blindly. Export code reads through the data boundary and must not mutate canonical state.

## 15. Testing strategy

Most behavior should be verified below the GUI:

- pure unit tests for probability, lifecycle, attention, revision selection, and scoring rules;
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

Expected errors should use explicit application or domain error types that the UI can present without a traceback. Examples include invalid probability, missing question text, revision disallowed by lifecycle, and resolution of an already terminal prediction.

Unexpected exceptions should not be converted into false success or empty data. Database failures must preserve the original database and provide enough context for diagnosis without exposing unrelated local information.

## 17. Decisions intentionally deferred

The product specification lists choices that must be made at their relevant milestones. Architecture must not settle them indirectly. They include:

- visual design details;
- exact probability range and input increments;
- stale threshold default;
- time storage and display strategy;
- calibration bins;
- cumulative versus windowed Brier trend;
- deletion restrictions after meaningful history;
- metadata audit behavior;
- CSV layout; and
- Windows packaging format.

When one of these choices becomes consequential, seek explicit user authorization before changing the product specification. Record durable technical reasoning in an [architecture decision record](decisions/README.md) when appropriate.

## 18. Evolution beyond v0.1

Numeric forecasts and Forecast Reviews are v0.2 work. v0.1 should avoid choices that make later extension needlessly destructive, but it must not add unused tables, generalized forecast-type frameworks, review entities, or UI abstractions in anticipation of them.

The architecture evolves through implemented vertical slices. After each milestone, update this document to reflect actual modules, persistence behavior, and any recorded technical decisions.
