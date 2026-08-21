# Changelog

All notable changes to Reckonsolve are documented here.

## Unreleased

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
