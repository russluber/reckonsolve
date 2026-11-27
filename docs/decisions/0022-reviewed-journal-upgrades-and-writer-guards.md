# 0022: Protect Journal upgrades with verified recovery and persistent writer guards

- Status: Accepted for the authorized first redesign slice; native acceptance pending
- Date: 2026-11-10

## Context

The [first redesign slice](../product-spec.md#3810-authorized-first-implementation-slice)
retires Saved Views and distinguishes deliberate One-Shot reflection from transcription
repair. An already-open older GUI or CLI must not write into the upgraded journal.
An ordinary live-file copy is insufficient when committed pages are in SQLite's WAL.
Retired, unknown or inconsistent forecasting contracts must be refused before any
recovery/migration mutation, including in mixed archives.

## Decision

Keep migrations 1–20 unchanged. Schema 21 removes `saved_views` and `saved_view_tags`
and adds immutable One-Shot correction `source_action`, constrained to `transcription`
or `postmortem`. Existing rows default to `transcription`; never infer their intent.
The dedicated Postmortem operation and SQL/domain guards permit reflection-only changes
on answered records and preserve complete original/correction replay. CSV format 6
adds this discriminator to `one_shot_corrections.csv`; SQLite remains complete recovery.

`data/upgrade.py` owns the transition:

1. Admit an already-current archive through a checked read transaction. For pending
   upgrades, acquire `BEGIN EXCLUSIVE` and revalidate history and the whole archive.
2. Serialize the protected source connection to a uniquely named sibling
   `.pre-upgrade-<unique>.sqlite3` file, including committed WAL pages. Flush/fsync,
   verify SQLite integrity, foreign keys, migration/contract history and image equality.
3. If Saved View configurations exist, show their count and the verified recovery
   location before asking for confirmation. CLI opening refuses this review-dependent
   transition and directs the user to the desktop. Cancellation retains the source
   and verified recovery. An unverified partial copy is removed only at its unique path.
4. Apply the ordered migration and install writer guards in that same transaction.
   Failure rolls back; a verified recovery remains available after later failure.

Schema 21 installs `BEFORE INSERT/UPDATE/DELETE` guards on every ordinary application
table. Each current connection registers `reckonsolve_writer_version()`; guards require
version 21. An already-open older connection has no function, so even cached statements
refuse after SQLite reloads the changed schema. FTS virtual/shadow tables cannot carry
ordinary triggers; older repair transactions also update guarded state and roll back.
These are compatibility guards, not a security boundary against deliberately authored
SQL or DDL. Normal current-version transactions retain SQLite's ordinary concurrency.

`data/database.py` also supplies read-only worker connections. Admission, whole-archive
validation and Journal facts share one read snapshot, with no migration or repair from
the worker. Validated One-Shot replay is reused only within that snapshot. Identified
busy/locked reads become temporary application errors; archive refusals and unexpected
faults keep their distinct meaning. Save responses affected by this slice are assembled
before commit so a later independent read cannot turn success into an apparent failure.

## Consequences

Recovery needs enough writable space beside the source. A blocking reader in rollback
mode may prevent upgrade exclusion; that failure leaves the source untouched. WAL
readers can retain their old read snapshot while writers are excluded. Process
interruption relies on SQLite transaction recovery, without another journal-location
descriptor, coordination service or production dependency.

The public/private repositories and installed tool snapshots remain separate. This
technical choice grants no permission to upgrade personal data, replace an installed
tool, relocate a journal, package a release or publish source.

Disposable tests cover cancellation, protection/DDL failure, interrupted migration,
rollback/WAL exclusion, cached stale writers, guarded table operations and supported
history/recovery. Human Windows appearance, scaling and workflow acceptance remains
separate from those automated checks.

## Alternatives

- Copying the main database file can omit committed WAL content.
- Checking the schema only at startup leaves an already-open older writer active.
- Application-only consent does not exclude another process during backup and DDL.
- An external lock service or location-marker system adds coordination without
  replacing the required SQLite transaction and stale-writer protection.
