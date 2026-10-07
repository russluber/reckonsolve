# Architecture Decision Records

This directory stores concise architecture decision records (ADRs) for technical choices whose reasoning will matter after the immediate change is complete.

Product scope, behavior, and durable product decisions belong in the [product specification](../product-spec.md). Current implemented structure belongs in [the architecture document](../architecture.md). An ADR explains why a consequential technical approach was selected among realistic alternatives.

## When to add a record

Write an ADR when a decision:

- changes a system boundary or dependency direction;
- selects a persistence, migration, time, charting, or packaging approach;
- adds a production dependency with meaningful tradeoffs;
- establishes a convention that later work must preserve; or
- would otherwise force a future maintainer to rediscover important context.

Do not add an ADR for routine implementation details, easily reversible local choices, or decisions already explained adequately by the product specification.

## File naming

Use a four-digit sequence and a short lowercase description:

```text
0001-short-decision-title.md
0002-next-decision-title.md
```

Numbers are never reused, even when a record is superseded.

## Record format

Each record should use this structure:

```markdown
# NNNN: Decision title

- Status: Proposed | Accepted | Superseded
- Date: YYYY-MM-DD
- Supersedes: optional ADR link

## Context

What problem or constraint required a decision?

## Decision

What was selected?

## Consequences

What becomes easier, harder, or constrained as a result?

## Alternatives considered

Which realistic alternatives were rejected, and why?
```

Update an ADR's status when it is replaced; preserve the original reasoning rather than rewriting history.

## Records

Records retain the reasoning accepted at their original dates. The current product
specification governs their applicability; an Accepted label does not preserve an old
release's entire runtime support set. Use the scope notes below when following an
earlier record.

- [0001: Use lightweight transactional SQLite migrations](0001-lightweight-sqlite-migrations.md) — Accepted 2026-08-12
- [0002: Store instants as canonical UTC text](0002-canonical-utc-instants.md) — Accepted 2026-08-12
- [0003: Preserve definition changes as immutable snapshots](0003-immutable-definition-snapshots.md) — Accepted 2026-08-12
- [0004: Render probability history with a native Qt widget](0004-native-probability-history-chart.md) — Accepted 2026-08-13
- [0005: Preserve terminal lifecycle decisions as immutable records](0005-immutable-terminal-lifecycle-records.md) — Accepted 2026-08-20
- [0006: Use fixed calibration bins and cumulative Brier performance](0006-fixed-calibration-and-cumulative-brier.md) — Accepted 2026-08-20
- [0007: Use online SQLite backup and relational CSV export](0007-online-backup-and-relational-csv-export.md) — Accepted 2026-08-20
- [0008: Use selected local icons and a private onedir build](0008-private-onedir-and-local-icons.md) — Accepted 2026-08-20
- [0009: Store fixed-precision numeric values as scaled integers](0009-scaled-integer-numeric-values.md) — Accepted 2026-08-20
- [0010: Preserve type-aware Forecast Reviews as immutable revision anchors](0010-type-aware-forecast-reviews.md) — Accepted 2026-08-20
- [0011: Keep CLI mutations line-oriented and route them through application operations](0011-line-oriented-cli-mutations.md) — Accepted 2026-08-25
- [0012: Preserve terminal corrections as append-only snapshot chains](0012-append-only-terminal-correction-chains.md) — Accepted 2026-08-26
- [0013: Use a rebuildable SQLite FTS5 search projection](0013-rebuildable-sqlite-fts5-search-index.md) — Accepted 2026-08-27
- [0014: Store immutable forecast-model and scoring-contract identities](0014-store-immutable-forecast-contract-identities.md) — Accepted 2026-09-09
- [0015: Store prospective forecasting and resolution instants without backfilling legacy history](0015-store-prospective-exact-forecast-times.md) — Accepted 2026-09-09
- [0016: Validate active commit times under transaction](0016-validate-active-commit-times-under-transaction.md) — Accepted 2026-09-10
- [0017: Derive trajectory scores from immutable history and effective terminal facts](0017-derive-trajectory-scores-from-terminal-facts.md) — Accepted 2026-09-10
- [0018: Store complete five-quantile revisions with explicit shared-history anchors](0018-five-quantile-revisions-and-shared-anchors.md) — Accepted 2026-09-11
- [0019: Retire legacy runtime without rebuilding supported history](0019-retire-legacy-runtime-without-rebuilding-history.md) — Accepted 2026-09-20
- [0020: Resolve local deadlines without silent clock changes](0020-resolve-local-deadlines-explicitly.md) — Accepted 2026-09-22
- [0021: Preserve One-Shot originals with separate transcription snapshots](0021-one-shot-originals-and-transcription-snapshots.md) — Accepted 2026-09-26

## Current applicability

| Records | What remains current / what changed |
| --- | --- |
| 0001–0003 | Transactional migrations, canonical UTC event instants, and protected Definition history remain. Adaptive exact Deadlines are now immutable under 0014–0015; One-Shot reports are documentary under 0021. |
| 0004 | Native history rendering remains for Adaptive. Strict event ordering follows 0016; One-Shot has no updating path. |
| 0005 | Immutable one-way terminal records remain. A captured revision is audit context; Adaptive scoring selection follows 0017–0018, and One-Shot uses effective snapshots under 0021. |
| 0006 | Fixed Binary calibration bins and one observation per Prediction remain. Retired final-only runtime analytics are superseded by 0017, 0019, and 0021; modes keep separate denominators. |
| 0007–0008 | Online backup, relational analytical export, local icons, and private builds remain. Current CSV is format 5; old format descriptions are release history. |
| 0009 | Exact scaled integers remain; the single chosen-confidence interval model is retired by 0018–0019. |
| 0010–0012 | Adaptive unchanged-forecast Reviews, shared CLI operations, and append-only terminal corrections remain. Quantile anchors follow 0018; One-Shot excludes Reviews and adds transcription snapshots under 0021. |
| 0013 | Canonical authority and rebuildable FTS5 remain; current projection is version 3 with One-Shot provenance. |
| 0014–0016 | Immutable identities and transaction-time exact forecasting checks remain for Adaptive. The supported matrix excludes retired identities under 0019 and includes two One-Shot pairs under 0021. |
| 0017–0018 | Current Adaptive trajectory/WIS selection, exact mathematics, quantile storage, and shared anchors. Do not restore historical coexistence promises. |
| 0019–0020 | Current refusal-before-mutation boundary and explicit local Deadline resolution. |
| 0021 | Current One-Shot originals, documentary reports, append-only correction replay, and pure individual Brier/WIS. |

These notes narrow the scope of earlier reasoning without rewriting the records. When
a future decision replaces one completely, mark it Superseded and link its successor.
