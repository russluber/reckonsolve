# Changelog

All notable changes to Reckonsolve are documented here.

## Unreleased

### Added

- Cross-shell `rsc` and `rscd` executable shortcuts for the stable and development CLI companions while retaining the descriptive command names.
- Milestone 26's schema-version-13 append-only foundation for Binary and Numeric Resolution corrections, Invalidation-reason corrections, and Postmortem completion facts.
- Effective terminal-history derivation with optimistic correction tokens, exact Numeric snapshots, immutable original terminal facts, and corrected-outcome selection for ordinary analytics.
- Milestone 27 desktop workflows for correcting Binary and exact Numeric Resolution facts, adding or revising a Postmortem after resolution, and correcting or clearing an Invalid reason without reopening the Prediction.
- Effective terminal summaries plus collapsed, complete original-to-current correction history on Binary and Numeric Prediction Detail.

### Changed

- Every terminal correction now receives a deliberate confirmation; score-affecting outcome or actual-value changes are identified explicitly and require a nonempty explanation.

## 0.3.0 - 2026-08-25

### Added

- Paired `reckonsolve-cli` and `reckonsolve-cli-dev` source commands that use the same stable or development SQLite database as their matching desktop command.
- Human-readable `list` and `show` commands with type-aware forecasts, combined filters, attention indicators, terminal facts, and complete exact textual history.
- Interactive Binary and Numeric creation, revision, Journal, Forecast Review, Resolution, Invalidation, and guarded deletion workflows routed through the existing application operations.
- CLI creation of complete verified SQLite backups and documented format-version-two relational CSV ZIP exports.

### Changed

- Reckonsolve can now complete the forecasting loop through either matching interface without a synchronization subsystem, server, or second canonical store.
- CLI prose entry is intentionally line-oriented for rapid capture; the desktop interface and canonical stored text retain multiline support.
- Cross-interface coverage now exercises simultaneous reads, sequential writes, stale-context rejection, bounded write-lock failure, restart, migration, and stable/development isolation.

### Release notes

- Reckonsolve v0.3 remains a local-first, offline-capable, single-user source release.
- The CLI is run through the `uv`-managed source environment. This release does not add a separately frozen CLI executable, installer integration, signing, public binaries, live inter-process refresh, or a scripting-stability contract.
- Existing v0.2 schema-version-12 databases require no schema change and are shared directly by the matching GUI and CLI identity. Creating a verified backup before upgrading remains recommended.

## 0.2.0 - 2026-08-20

### Added

- Binary predictions with immutable probability revisions from 0% through 100%.
- Numeric predictions using exact signed fixed-precision central prediction intervals, a required median estimate, and confidence from 1% through 99%.
- Optional revision rationales, prediction metadata, date-only forecasting fields, and reusable tags.
- Journal entries with exact forecast-at-the-time context and transparent correction history.
- Open-only Forecast Reviews that retain the current Binary or Numeric forecast without fabricating a revision.
- Type-aware unified timelines plus Binary probability-history and Numeric interval-history charts.
- Open, Locked, Resolved, and Invalid lifecycle workflows with guarded deletion of untouched records.
- Needs Attention and Ready to Resolve classifications, a type-aware Dashboard, and a searchable Predictions browser.
- Binary Brier, calibration, and cumulative-performance analytics.
- Numeric containment calibration, median absolute error, interval width, and proper interval score analytics.
- Verified online SQLite backup and a documented twelve-file relational CSV export.
- Isolated development data, selected local Lucide icons, and a private frozen Windows smoke build.

### Changed

- Needs Attention uses the later of the latest eligible forecast revision or Open-state Forecast Review; Journal activity remains excluded.
- CSV export format version 2 preserves Binary and Numeric revisions, Resolutions, Forecast Reviews, Journal history, lifecycle records, and tag relationships.

### Release notes

- Reckonsolve remains a local-first, offline-capable, single-user Windows application.
- This is a source release. It does not provide a supported installer, signed public executable, update channel, or final application artwork.
- Existing v0.1-shaped databases migrate automatically through the complete v0.2 schema. Creating a verified backup before upgrading remains recommended.
