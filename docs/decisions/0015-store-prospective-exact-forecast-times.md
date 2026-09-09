# 0015: Store prospective forecasting and resolution instants without backfilling legacy history

- Status: Accepted
- Date: 2026-09-09
- Supersedes: none; extends [ADR 0002](0002-canonical-utc-instants.md) and [ADR 0012](0012-append-only-terminal-correction-chains.md)

## Context

Trajectory Brier and five-quantile WIS need an exact immutable Forecast Deadline and the exact effective instant at which an outcome became fixed and ascertainable. The existing optional Forecast Deadline is editable date-only metadata. Existing Binary and Numeric Resolution timestamps record when the terminal action was entered, not necessarily when the outcome became knowable. Treating either legacy fact as the new meaning would invent history and can select or weight the wrong ForecastRevision.

The correction model must also allow one later confirmation to change the effective time, the outcome, or both while retaining one contiguous before/after audit record. Existing legacy correction tables cannot add a time-only change without weakening their released no-op constraints.

## Decision

New-model Forecast Deadlines use the `forecast_deadline_at` field of the immutable forecast-contract row. New domain values accept only timezone-aware Python `datetime` instances, normalize them to UTC, and preserve the canonical microsecond `Z` storage form established by ADR 0002. `ForecastingWindow` requires `T > t0`, rejects a new revision time unless it is strictly later than the previous revision and strictly before `T`, and derives the scoring cutoff as `C = min(R, T)`. `ResolutionTiming` keeps the user-confirmed effective time separate from the system-generated recorded-at instant and requires `R <= recorded_at`.

Schema version 16 adds nullable `effective_resolution_at` columns to the existing Binary and Numeric Resolution tables. Null means the Resolution belongs to a legacy contract and has no defensible prospective effective-time fact; it never means “use `resolved_at`.” A new-model Resolution must supply the exact value, while `resolved_at` retains its immutable recorded-at and terminal-ordering meaning.

Prospective Binary and Numeric corrections use `binary_trajectory_resolution_corrections` and `numeric_quantile_resolution_corrections`. Each is a type-specific append-only full snapshot chain containing before/after effective times alongside the type-appropriate outcome, factual notes, and Postmortem. Changed-field flags, a contiguous sequence, current-snapshot guards, immutable rows, and a required explanation for any score-affecting outcome or time change preserve ADR 0012's discipline. The original Resolution and recorded-at remain unchanged. The released legacy correction tables are restricted to legacy contracts and remain structurally and behaviorally intact.

Milestone 46 supplies persistence and pure domain rules only. No public creation, revision, Resolution, correction, scoring, or Qt workflow can yet create or act on a new-model Prediction. Those complete vertical paths belong to later v0.7 milestones.

## Consequences

- Delayed Resolution entry cannot silently change a new-model scoring cutoff.
- Existing Resolutions retain null effective time rather than receiving a guessed midnight, Deadline, or recorded-at value.
- Clock regression and exact-Deadline boundary failures can be tested without Qt or SQLite.
- Later Binary and Numeric correction dialogs can append one record for a combined effective-time and outcome correction.
- The schema adds two empty prospective correction tables before their workflows are exposed; this is deliberate foundation rather than user-visible partial behavior.
- Old and new terminal correction readers must dispatch by stored forecast contract once the new workflows arrive.

## Alternatives considered

### Reinterpret legacy `resolved_at` as effective resolution time

Rejected because it records data entry and may be hours or days after the outcome became known. Reinterpretation would fabricate scoring history.

### Convert the date-only legacy Forecast Deadline to local or UTC midnight

Rejected because neither the time nor the intended time zone was committed. Any conversion would create false precision and could change eligibility.

### Add effective-time fields to the released legacy correction tables

Rejected because their existing table-level no-op constraints do not count a time-only change. Rebuilding them would expose legacy history to unnecessary migration risk and blur the cohort boundary.

### Store effective-time corrections in a separate time-only log

Rejected because one user correction that changes both outcome and effective time would be split across two audit records and could become internally inconsistent.
