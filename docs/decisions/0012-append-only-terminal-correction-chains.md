# 0012: Preserve terminal corrections as append-only snapshot chains

- Status: Accepted
- Date: 2026-08-26

## Context

ADR 0005 made Binary and Numeric Resolutions and Invalidations immutable terminal decisions. v0.4 must allow an honestly mistaken outcome, factual note, Postmortem, or invalidation reason to be corrected without erasing what was first recorded. Outcome corrections also change scoring, so the stored history must make the effective value unambiguous while retaining the original resolution time and captured scoring revision.

The correction path must support both forecast types, exact fixed-precision Numeric actual values, multiple corrections, independent application instances, later Postmortems, and a future portable export. It must not turn Reckonsolve into a generic event-sourcing system or relax the one-way terminal lifecycle.

## Decision

Schema version 13 retains the existing terminal tables unchanged and adds three type-specific append-only correction chains: `resolution_corrections`, `numeric_resolution_corrections`, and `invalidation_reason_corrections`. Binary and Numeric Resolution corrections each store a complete before/after snapshot of every correctable type-appropriate field, explicit changed-field flags, a contiguous per-Resolution sequence, a canonical UTC correction time, and an explanation whenever the outcome or actual value changes. Invalidation corrections store the complete before/after reason snapshot with the same sequence and time discipline.

Binary and Numeric corrections use separate tables because their outcome representations and parent Resolution tables already have distinct exact constraints. This avoids a polymorphic table dominated by mutually exclusive nullable columns while keeping both chains semantically identical at the domain and application boundaries.

Database constraints and triggers require each snapshot to continue the currently effective values, require contiguous sequence numbers, require a score-affecting correction reason, and reject update, replacement, or direct child deletion while the Prediction exists. Composite foreign keys preserve Prediction ownership. Normal parent cascade remains available only at the database boundary.

The application carries the correction identifier that was current when the caller reviewed the terminal history. The repository rechecks it inside `BEGIN IMMEDIATE`, derives the effective record by replaying the complete snapshot chain, rejects no-ops, and appends exactly one correction. The original terminal timestamp and Resolution scoring-revision reference are never replaced. Ordinary analytics use the latest effective outcome or actual value once while retaining the original resolution-time ordering.

One shared `postmortem_completions` table stores the timestamped fact behind **Skip Postmortem**. Insert guards require a Resolved Prediction with a blank effective Postmortem. A later Postmortem correction remains allowed and does not erase the completion fact.

Milestone 26 exposes these rules through domain, application, and persistence operations but deliberately adds no desktop or CLI mutation control. Desktop correction presentation belongs to Milestone 27, Needs Postmortem presentation belongs to Milestone 30, and relational export format version 3 plus CLI read support belong to Milestone 31.

## Consequences

- Original terminal facts remain independently recoverable after any number of corrections.
- Effective terminal values are deterministic and can drive scoring without adding another scoring observation or changing the captured forecast.
- Stale dialogs or competing processes cannot branch or silently overwrite a correction chain.
- Numeric outcomes remain signed scaled integers at the immutable Prediction precision.
- The migration adds four small tables, three ownership indexes, and integrity triggers; this is more schema than in-place editing but makes historical correctness enforceable below the UI.
- Complete SQLite backup automatically includes the new records. The existing format-version-two CSV export intentionally remains unchanged until the version-three work in Milestone 31.

## Alternatives considered

### Update the original terminal row and keep only an audit message

Rejected because the database would no longer contain the original facts as authoritative structured data, and an incomplete audit message could not deterministically reconstruct scoring history.

### Store only replacement values rather than before/after snapshots

Rejected because a stale or malformed chain would be harder to detect. Complete snapshots let both application replay and database triggers prove that every correction continues the effective record the user reviewed.

### Use one polymorphic Resolution-correction table

Rejected because Binary outcomes and exact Numeric actual values belong to different parent tables and require mutually exclusive constraints. Separate type-specific tables keep invalid combinations unrepresentable without changing the shared domain semantics.

### Introduce one generic lifecycle-event or audit table

Rejected because Reckonsolve has only three concrete terminal correction concepts. A general event store would add indirection and speculative infrastructure without improving the required workflows.

### Model later Postmortems as Journal entries

Rejected because a Postmortem is one versioned reflection attached to a Resolution, while a Journal entry is a preterminal assertion anchored to the forecast current at its original time.
