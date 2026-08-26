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
