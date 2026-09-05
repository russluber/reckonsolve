# Changelog

All notable changes to Reckonsolve are documented here.

## Unreleased

## 0.6.0 - 2026-09-05

### Added

- A centralized, palette-aware desktop visual system with shared semantic colors, native-font roles, spacing, surfaces, badges, action hierarchy, focus treatment, disabled states, persistent messages, and local Lucide icon refresh.
- An expanded or icon-only application sidebar with a prominent New Prediction action, permanent Dashboard/Predictions/Analytics destinations, bottom Settings utility, and source-aware contextual return from Prediction Detail.
- Identity-isolated presentation settings for safe window geometry, maximized state, and sidebar mode outside canonical SQLite data.
- Shared page headers, content panels, count/status badges, empty states, and a non-reflowing shell notification host for disposable routine acknowledgments.
- Numeric Edit Details parity for Question, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags while unit and decimal precision remain immutable context.
- Searchable tag completion with removable filter chips and responsive side-by-side Predictions controls/results panes that stack when the window is narrow.
- Guarded global navigation shortcuts, a visible Settings reference, improved focus order, accessible descriptions, tooltip-backed icon-only controls, and nonvisual chart summaries.
- A recorded v0.6 visual-verification matrix and expanded private frozen-build checks for visual resources, shell modes, every primary screen, both Detail types, keyboard navigation, responsive sizes, schema-v15 preservation, search, backup, and restart.

### Changed

- New Prediction, both Prediction Detail variants, every focused forecast dialog, Dashboard, Predictions, Analytics, Settings, and tag management now use one calm, responsive presentation grammar without changing their application operations.
- Prediction Detail separates current belief, routine forecast work, lifecycle/destructive actions, optional metadata, terminal facts, causal history, and type-specific charts; long user-authored text remains selectable and wrapped.
- Predictions presents Search, Common filters, Detailed filters, and Saved Views in a compact stable order while retaining v0.5 matching, ranking, provenance, filtering, Saved View, and tag semantics.
- Analytics keeps one stable filter frame above responsive summary, calibration, performance, and update-feedback panels; plot/table pairs sit side by side at normal widths and stack at narrow widths.
- The private Windows smoke workflow now treats every schema-version-15 application and derived row as a compatibility boundary around presentation-only use.

### Release notes

- Reckonsolve v0.6 remains an offline, local-first, single-user source release. Existing v0.5 databases stay on schema version 15; no presentation migration is required.
- Presentation preferences live in an identity-specific `presentation.ini` beside the database and are intentionally excluded from SQLite backup, CSV export, CLI output, search, history, lifecycle, and analytics.
- This release does not add a Review Queue, another forecast model, a custom theme framework, logo artwork, an installer, signing, automatic updates, or public binaries.

## 0.5.0 - 2026-08-28

### Added

- Explainable, offline full-text search across Questions, tags, metadata, forecast rationales, Reviews, Journal history, and terminal text, with current-effective results by default and unmistakable opt-in superseded history.
- Ordinary-word, quoted-phrase, incremental-prefix, punctuation-safe, All/Any, and explicit one-edit spelling-suggestion behavior with one grouped result per Prediction and source-aware snippets.
- Rich archive filtering across lifecycle, forecast type, multiple tags, attention, inclusive local-calendar date meanings, and deterministic null-last sorts.
- Named dynamic Saved Views that retain complete query configurations through stable tag identities without storing result membership.
- Confirmed transactional tag rename, merge, and deletion with Prediction/Saved View counts, stale-metadata protection, and atomic search refresh.
- Matching read-only CLI `search`, `saved-views`, and `saved-view --id/--name` commands through both stable and development identities.
- An explicit Settings action that repairs the disposable search projection from canonical Prediction history.
- A named privacy-safe relevance suite, a recorded 2,000-Prediction/6,000-fragment performance corpus, and expanded private frozen-build validation.

### Changed

- Existing schema-version-13 v0.4 databases migrate through version 14's rebuildable FTS5 projection to version 15's Saved View persistence without changing canonical forecast history.
- Startup now verifies the complete search projection against canonical replay and repairs equal-sized mismatches before they can appear as false empty results.
- SQLite backup preserves Saved Views and search capability; relational CSV remains format version 3 and now documents every intentional v0.5 exclusion.
- The private Windows smoke workflow now covers schema-version-13 migration, FTS5, effective/history search, Saved Views, tag maintenance, independent canonical reads, failure reporting, repair, backup, recovery, and restart outside the source environment.

### Release notes

- Reckonsolve v0.5 remains a local-first, offline-capable, single-user source release.
- Creating a verified SQLite backup before first opening an existing v0.4 database remains recommended.
- This release does not add semantic search, Collections, another forecast model, logo artwork, a Windows installer, signing, automatic updates, public binaries, hidden query telemetry, or behavioral ranking.

## 0.4.0 - 2026-08-26

### Added

- Cross-shell `rsc` and `rscd` executable shortcuts for the stable and development CLI companions while retaining the descriptive command names.
- Milestone 26's schema-version-13 append-only foundation for Binary and Numeric Resolution corrections, Invalidation-reason corrections, and Postmortem completion facts.
- Effective terminal-history derivation with optimistic correction tokens, exact Numeric snapshots, immutable original terminal facts, and corrected-outcome selection for ordinary analytics.
- Milestone 27 desktop workflows for correcting Binary and exact Numeric Resolution facts, adding or revising a Postmortem after resolution, and correcting or clearing an Invalid reason without reopening the Prediction.
- Effective terminal summaries plus collapsed, complete original-to-current correction history on Binary and Numeric Prediction Detail.
- Milestone 28 type-aware resolved-prediction scorecards that show the captured scoring forecast, effective outcome or actual value, and individual Binary or Numeric metrics without creating another scoring observation.
- Milestone 29 retrospective initial-versus-final feedback for revised-and-resolved Binary and Numeric Predictions, with unrevised resolutions counted separately and existing type, tag, and exact-unit filters retained.
- Milestone 30 Needs Postmortem Dashboard queue for Resolved Predictions with a blank effective Postmortem and no earlier Skip fact.
- Confirmed Skip Postmortem completion that preserves resolution, score, lifecycle, and later Postmortem eligibility while remaining visible on Prediction Detail.
- Historically complete read-only CLI `show` output for original and effective terminal facts, every correction and Postmortem version, correction reasons and timestamps, and Skip completion.
- Relational CSV export format version 3 with Binary and Numeric Resolution corrections, Invalidation-reason corrections, and Postmortem-completion records.
- v0.4 portability and private-build coverage spanning schema-version-12 migration, corrected outcomes, later Postmortems, scorecards, update analytics, Needs Postmortem, backup, and restart.

### Changed

- Every terminal correction now receives a deliberate confirmation; score-affecting outcome or actual-value changes are identified explicitly and require a nonempty explanation.
- A corrected Binary outcome or Numeric actual value now recomputes its individual scorecard from the effective terminal fact while retaining the original scoring revision and resolution position.
- Binary paired feedback reports initial and final Brier plus initial-minus-final score improvement; Numeric feedback combines only unitless confidence and containment while reserving raw error, width, and interval-score comparisons for one exact unit.
- CSV export now produces a documented sixteen-file format-version-three analytical bundle while preserving every format-version-two file and relationship.

### Release notes

- Reckonsolve v0.4 remains a local-first, offline-capable, single-user source release.
- Existing v0.3 schema-version-12 databases migrate automatically to schema version 13 without replacing original terminal records. Creating a verified backup before upgrading remains recommended.
- This release does not add terminal-mutation CLI commands, a Windows installer, signing, automatic updates, public binaries, or application-logo artwork.

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
