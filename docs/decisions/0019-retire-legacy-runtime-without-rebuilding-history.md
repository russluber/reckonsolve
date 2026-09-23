# 0019: Retire legacy runtime without rebuilding supported history

- Status: Accepted
- Date: 2026-09-20
- Supersedes: the ongoing legacy-runtime support policy in [0014](0014-store-immutable-forecast-contract-identities.md), not its immutable identity design

## Context

The approved M54B amendment ends support for Binary final-v1 and Numeric
interval-v1. It does not authorize deleting records or converting an old forecast
into a trajectory or five quantiles. Existing v0.7 history must remain usable.

Many older structures are still necessary: Binary revisions, common Journals and
Reviews, Numeric unit/precision, Resolution recording anchors, Definition history,
tags, Saved Views, and append-only correction relationships. Dropping every old
table would require rebuilding shared foreign keys and triggers without changing
any supported product behavior.

## Decision

Keep schema 18 and the immutable historical migration registry. Remove retired
runtime dispatch rather than rebuilding supported databases or renaming shared
storage. An empty retained historical table is not a supported forecasting model.

The compatibility gate inspects the entire database under the migration or
application transaction, before pending migration statements, search repair, or
normal work. It rejects any retired Prediction, irrespective of lifecycle or
filters. Missing, mismatched, and unknown identities fail closed. Transactions
also validate their result before derived search refresh and commit. This catches
an unsupported record introduced after startup and rolls back a lower-level
attempt to introduce one. Backups validate the captured snapshot before installing
the destination; they never produce a selectively filtered recovery file.

| Input | Supported behavior |
|---|---|
| Fresh empty file | Build the full schema, create only trajectory Binary and five-quantile Numeric |
| Valid empty historical schema 1–15 | Apply the recorded pending migrations; no forecast identity is invented |
| Any Prediction without stored identity, including populated schema 2–15 | Refuse unchanged; retain for compatible earlier software |
| Schema 16 or 17 with only valid trajectory Binary | Apply pending historical migrations, preserving exact facts and anchors |
| Schema 18 with only valid current models | Reopen in place; no migration or data reset |
| Any schema with a retired Prediction, alone or mixed | Refuse the whole database unchanged |
| Unknown/mismatched/missing identity, malformed migration history, newer schema | Refuse explicitly; no guessed identity, repair, or replacement |
| SQLite backup | Apply the same rules as any database, regardless of filename |

Five-quantile storage starts at schema 18. A purported five-quantile contract in an
earlier schema lacks its required definition/revision and is not a valid staged
v0.7 archive. No valid earlier trajectory history needs a lossy conversion.

### Dependency inventory

- Keep `data/migrations.py`, M48/M50 migration builders, shared Binary revision and
  history tables, exact-time contract validation, and the existing derived-index
  rebuild mechanism. Never edit an applied migration to remove its old tables.
- Keep trajectory and quantile scorers, calibration bin math used by trajectory
  diagnostics, and fixed-precision values. Ordinary Brier remains a current
  diagnostic, not a reason to retain the old final-only scoring application.
- Remove legacy application fixture factories, interval-v1 revision/lifecycle
  repositories, interval editor/history presentation, final-only scorecards,
  aggregate source loaders/sections, and CLI interval prompts/rendering branches.
- Simplify archive, Dashboard, search, and terminal projections to current models;
  retain common Definition, Journal, Review, terminal-correction, tag, Saved View,
  attention, and optimistic-concurrency rules.
- Retarget visual/private-build fixtures and still-relevant regression tests to
  explicit current-model forecasts. Only compatibility/refusal fixtures may seed
  retired rows, using historical SQL in tests rather than a production factory.

## Consequences

Supported data stays in place. The compatibility break may deliberately prevent
launching a development database containing old test records. Cleanup is a
separate user-authorized operation, not a side effect of startup or installation.
M54B does not inspect either real user database or add a reset command.

The CSV-format-3 guard remains until separately authorized M55 replaces it with
format 4. Complete SQLite backup remains the recovery mechanism for supported
archives. Removing old behavior requires updating fixtures and assertions, not
weakening shared-history or concurrency coverage to make the suite pass.

## Alternatives considered

- Hiding old cards leaves a second forecasting system and does not implement
  retirement.
- Automatically deleting/converting old records violates the approved refusal
  policy and cannot preserve their meaning.
- Recreating all tables would risk supported history and add a migration solely
  for tidiness. A later demonstrated storage need can justify a new versioned
  migration; M54B has no such need.
