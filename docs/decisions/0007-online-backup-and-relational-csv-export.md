# 0007: Use online SQLite backup and relational CSV export

- Status: Accepted
- Date: 2026-08-20

## Context

Milestone 11 must produce two artifacts with different promises. A backup must recover the complete local application state. CSV must make prediction data portable for inspection and analysis without claiming that a flat text format can restore SQLite constraints and relational behavior. Both workflows run while Reckonsolve owns a live database connection and must not corrupt the source or destroy an earlier destination after a partial failure.

A direct filesystem copy can capture an inconsistent SQLite file when transactions or journal state are active. One flattened CSV would either discard repeated Forecast, Journal, correction, and definition history or duplicate current Prediction data ambiguously. Adding a third-party transfer dependency would be disproportionate because Python and SQLite already provide the needed primitives.

## Decision

Backup uses Python's binding to the [SQLite online backup API](https://www.sqlite.org/backup.html), which produces a consistent snapshot of a live source. The operation writes a uniquely named temporary database in the selected destination directory, verifies SQLite quick check, foreign keys, and Reckonsolve schema version, closes it, and atomically replaces the selected destination. It rejects the canonical database itself, including an equivalent hard link. Only after installation succeeds does schema version 8 persist the canonical UTC last-successful-backup time.

CSV export reads all source tables inside one explicit transaction, then closes the transaction before serialization. Format version 1 wrote nine UTF-8-with-BOM, fully quoted CSV files with CRLF rows for the Binary historical relationships. M20 extends the same relational design to format version 2 with twelve files: Predictions, Binary ForecastRevisions, Numeric ForecastRevisions, definition changes, Journal entries, Journal corrections, Forecast Reviews, Binary Resolutions, Numeric Resolutions, Invalidations, tags, and Prediction-tag links. Stable identifiers retain relational joins. The Numeric files preserve signed scaled integers and rely on each parent Prediction's exported fixed precision rather than converting values through binary floating point. An included README is the data dictionary and explains nulls, time/date semantics, type-appropriate current-value derivation, scoring-revision selection, and spreadsheet treatment of formula-like free text.

The ZIP is written, reopened, checked for exact membership and corrupt entries, and atomically installed through a same-directory temporary file. CSV export does not persist export state, include application settings, or claim restoration capability. Both implementations use only `sqlite3`, `csv`, `zipfile`, and other Python standard-library facilities.

## Consequences

- Backup remains correct if the database is open and avoids dependence on SQLite journal mode or sidecar-file copying.
- A failed backup or export leaves an existing destination untouched until a complete replacement is ready.
- The SQLite artifact is the recovery contract; the CSV ZIP remains intentionally analytical.
- Every Binary and Numeric historical one-to-many relationship is available without one enormous duplicated table.
- Consumers must join CSV files by documented identifiers and derive current type-appropriate Forecast or Journal text according to the README.
- The last backup time requires a small schema migration, while CSV export requires no persisted state.
- Exporting all rows into memory is proportionate to a personal local journal; a demonstrated scale problem would justify streaming from a dedicated consistent read connection later.

## Alternatives considered

### Copy the live database file

Rejected because a blind file copy is not the SQLite consistency contract and can mishandle transaction or journal state.

### Use `VACUUM INTO`

Rejected because the online backup API directly expresses snapshot recovery, is exposed by Python's supported `sqlite3` interface, and avoids coupling this feature to SQL filename quoting or vacuum behavior.

### Export one flattened CSV

Rejected because ForecastRevisions, Journal corrections, definition changes, terminal records, and tags have independent multiplicity and identity. Flattening would erase or ambiguously duplicate history.

### Export an uncompressed directory

Rejected because a single selected ZIP keeps all related tables and their data dictionary together while remaining easy to extract with standard tools.

### Store CSV exports or analytical summaries in SQLite

Rejected because exports are derived artifacts. Persisting them would add synchronization and migration risk without improving canonical history.
