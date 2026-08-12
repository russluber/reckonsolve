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

No architecture decisions have been recorded yet.
