# 0001: Use lightweight transactional SQLite migrations

- Status: Accepted
- Date: 2026-08-12

## Context

Reckonsolve's SQLite database is the user's canonical historical record. Application startup must initialize a new database, upgrade an existing database predictably, and refuse unsafe or unrecognized files without replacing them. The project needs this behavior from Milestone 1, before any forecast-domain tables exist.

The application is a single-process, single-user desktop program with a small schema that will grow one vertical slice at a time. A general ORM or third-party migration framework would add another abstraction and production dependency before the project has a need for either.

## Decision

Use Python's standard-library `sqlite3` module behind a small `Database` boundary. One long-lived `Database` object is owned by the application runtime and closed during shutdown. Each connection enables foreign-key enforcement and a finite busy timeout. Writes and schema changes use explicit `BEGIN IMMEDIATE` transactions so lock acquisition and rollback behavior are deliberate.

Schema evolution is represented by an ordered in-code sequence of numbered, named SQL-statement migrations. Applied migrations are recorded in a `schema_migrations` table. Startup validates that migration history is recognized and well formed, then applies each pending migration transactionally in order. The baseline migration creates only the migration metadata; forecast-domain tables will be added by the milestones that need them.

If a database reports a newer schema, has a malformed migration table, contains gaps or unknown history, or fails during migration, startup rejects it with an error. It never deletes, recreates, or silently substitutes the database. Production startup resolves the normal per-user path, while tests inject explicit temporary database paths.

Continue using SQLite's default rollback-journal mode for now. Do not enable write-ahead logging (WAL) until a concrete concurrency or performance need justifies its extra files and backup considerations.

## Consequences

- Migration behavior remains small, explicit, reviewable, and testable without a new dependency.
- A failed migration rolls back rather than leaving a partly upgraded schema, and the original file remains available for diagnosis or recovery.
- Future schema work must add a new ordered migration and a migration test; modifying an already-applied migration is not a compatible change.
- The application deliberately refuses automatic downgrade or repair of unrecognized migration history. Recovery tooling, if later needed, must be a separate deliberate feature.
- `BEGIN IMMEDIATE` surfaces competing writers before a write operation begins. The busy timeout tolerates short-lived contention, but Reckonsolve does not promise concurrent multi-process editing.
- The application code owns a modest amount of migration-runner logic and must keep its history validation well tested.

## Alternatives considered

### ORM or third-party migration framework

Rejected for Milestone 1. Reckonsolve has one local SQLite database and no alternate persistence backend. The added dependency, conventions, and abstraction cost do not yet buy enough capability.

### SQLite `PRAGMA user_version`

Rejected as the migration ledger. It stores only one integer and provides less inspectable history than a normal table. A `schema_migrations` table can identify every applied migration and lets startup validate the complete recognized sequence.

### WAL mode

Deferred. The current single-user desktop workflow does not require its extra read/write concurrency. WAL would also introduce persistent sidecar files that backup and recovery behavior would need to account for.

### Recreate an incompatible database

Rejected because it could destroy the user's forecasting history. An unsupported or malformed database must cause a clear startup failure instead.

### Create all v0.1 domain tables in the baseline

Rejected as premature schema design. Domain tables will arrive with the vertical slices that establish and test their invariants.
