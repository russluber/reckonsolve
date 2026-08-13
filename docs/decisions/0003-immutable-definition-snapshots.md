# 0003: Preserve definition changes as immutable snapshots

- Status: Accepted
- Date: 2026-08-12

## Context

Changing a prediction's Question or Resolution Criteria can change the proposition against which earlier forecasts were made. Adding, changing, or removing its Forecast Deadline does not itself redefine the proposition, but it changes the forecasting cutoff, derived Locked behavior, and potentially revision eligibility. Reckonsolve needs enough history to preserve both kinds of context honestly without turning every editable field into a generic audit system or making historical events the source of current prediction state.

One edit can change several protected fields at once. Recording unrelated per-field events would obscure that they were one user action, while storing only the final definition would erase the earlier context.

## Decision

Keep current metadata on `predictions` as the canonical current state. Treat Question, Resolution Criteria, and Forecast Deadline as protected fields for edit-history purposes. For each confirmed save that changes at least one protected field, append exactly one row to `prediction_definition_changes`. That row stores the prediction identifier, one canonical UTC change instant, and complete before/after snapshots of all three protected fields.

The confirmation copy reflects why each field is protected. Question and Resolution Criteria warnings explain that the proposition's meaning may change and recommend creating a new Prediction when that change is material. Forecast Deadline warnings instead explain the effects on cutoff and locking; a deadline-only change is not described as changing the proposition and does not by itself call for a new Prediction. Background, Expected Resolution, and tags remain ordinary edits that create no definition snapshot by themselves.

Each prediction carries a monotonically increasing metadata version. The edit dialog retains the version it loaded and sends that same expected version before and after any confirmation prompt. The data layer checks it again inside the write transaction, then updates prediction metadata and tag associations, advances the version once, and inserts the definition snapshot in that same transaction. A concurrent change rejects the save rather than overwriting newer metadata or associating a snapshot with the wrong prior definition. Effective no-ops neither advance the version nor append history.

Database constraints require a real difference between the snapshots. Triggers reject direct updates, replacement through an existing record identity, and direct deletion while the parent prediction still exists; a deliberate future parent deletion may cascade transactionally. Definition history is ordered by its integer record identity. Background, Expected Resolution, and tags are deliberately outside these snapshots because they neither define the proposition nor control the forecast cutoff in v0.1.

Initial creation is not a metadata edit. When Milestone 4 adds optional initial rationale, metadata, and tags to New Prediction, those values establish the first saved state, require no protected-edit confirmation, and create no definition snapshot. They persist atomically with the Prediction and first ForecastRevision, including its rationale.

## Consequences

- Each confirmed edit remains recognizable as one user action even when several protected fields change.
- Confirmation language explains the actual consequence of the field being edited rather than treating every protected field as a proposition rewrite.
- A history row is self-contained, so interpreting it does not require replaying every earlier edit.
- Current reads remain straightforward because the prediction row, not the history, is the source of current metadata.
- Snapshot values repeat some text and dates, but the volume is proportionate to a personal journal and favors historical clarity.
- Adding another protected field later requires a deliberate schema and mapping change.
- This mechanism protects prediction definitions but is not a comprehensive audit trail for ordinary metadata.

## Alternatives considered

### Generic event sourcing

Rejected because reconstructing every prediction from events would add substantial machinery and make routine current-state reads more complex without a v0.1 need.

### One record per changed field

Rejected because one save could appear as several unrelated historical actions and atomic user intent would be harder to present.

### Store only fields that changed

Rejected because sparse or dynamically shaped records complicate reconstruction and migrations. Complete snapshots keep the small protected definition explicit and self-contained.

### Overwrite metadata after confirmation without history

Rejected because confirmation alone would not preserve the definition against which earlier forecasts were made.
