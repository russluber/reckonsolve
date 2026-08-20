# 0005: Preserve terminal lifecycle decisions as immutable records

- Status: Accepted
- Date: 2026-08-20

## Context

Resolved and Invalid are durable decisions, not transient display classifications. A Resolution must retain a Yes/No outcome, provenance, reflection, and exactly one forecast for later scoring. An Invalidation must preserve when and why a prediction left the scorable set. Storing only a status string would lose those facts, while deriving the scoring forecast later from timestamps would be vulnerable to equal or regressing clocks and to future changes in selection logic.

The application also needs to prevent two windows or processes from resolving and invalidating the same Prediction differently. Terminal actions must remain atomic with their status transition and must not introduce a casual outcome-toggle mechanism.

## Decision

Store Resolutions and Invalidations in separate one-to-one child tables. Each row has its own stable identity and canonical UTC instant. A Resolution stores a composite foreign-key reference to the ForecastRevision owned by the same Prediction that was current inside the resolution transaction. That immutable reference is the canonical scoring revision. An Invalidation stores no scoring reference because Invalid predictions are excluded from scoring.

Both application operations carry the reviewed current-revision identifier and prediction metadata version. The repository rechecks those tokens and nonterminal status inside `BEGIN IMMEDIATE` before inserting a terminal row. Database insert guards repeat the lifecycle and ownership checks. After-insert triggers set the matching persisted terminal status and `updated_at` from the terminal row's instant, so the record and status change are one SQLite statement inside one application transaction.

Terminal status cannot be set without its corresponding record and cannot return to Open or switch to the other terminal state. Triggers reject direct terminal-row updates, replacement, and direct deletion while the parent exists. A deliberate parent deletion can still cascade transactionally at the database boundary, although the normal v0.1 application never permits deletion of terminal history.

Because the released v5 application had no terminal action, migration v6 accepts the normal persisted `open` rows and refuses a manually altered legacy terminal status for which no honest outcome or invalidation facts exist. That failure rolls the migration back and preserves the v5 database rather than fabricating terminal history.

Delete eligibility remains a derived query fact rather than another lifecycle state. The guarded delete operation uses the same optimistic tokens and transaction boundary, then rechecks the product specification's untouched-Open criteria before deleting the parent.

## Consequences

- Later analytics can consume one explicit outcome and one unambiguous scoring revision per resolved Prediction.
- Equal timestamps, clock regression, and subsequent metadata changes cannot silently change which forecast was captured for scoring.
- Resolution and Invalidation are mutually exclusive and historically stable.
- Optional notes, Postmortem text, and invalidation reason remain attached to the decision that created them.
- Correcting a mistaken terminal decision requires a future explicitly designed history-preserving workflow and migration; v0.1 cannot overwrite it.
- The schema uses two small tables and several integrity triggers, which is more verbose than nullable columns but keeps distinct facts and constraints legible.

## Alternatives considered

### Store nullable terminal fields on `predictions`

Rejected because outcome, scoring context, invalidation reason, and their different constraints would accumulate unrelated nullable columns on the mutable current-state row. Separate records make terminal identity and immutability explicit.

### Derive the scoring revision only when analytics runs

Rejected because timestamp ordering is not the canonical revision order and the system clock can tie or move backward. Capturing the transaction-current revision at resolution directly preserves what the user resolved against.

### Permit in-place outcome or reason correction

Rejected for v0.1 because it would rewrite a consequential historical decision. A future correction flow needs explicit audit semantics rather than a normal update operation.

### Use one generic lifecycle-event table

Rejected because Resolution and Invalidation have different required facts, and v0.1 has no need for a generalized event-sourcing layer.
