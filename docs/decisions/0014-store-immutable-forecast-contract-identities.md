# 0014: Store immutable forecast-model and scoring-contract identities

- Status: Accepted
- Date: 2026-09-09

## Context

Reckonsolve v0.7 introduces Binary trajectory forecasts and five-quantile Numeric forecasts while every earlier Binary and Numeric Prediction must retain its creation-era editor, lifecycle, and scoring behavior for life. Table population, application version, `metadata_version`, and the presence of a date-only legacy Deadline cannot reliably identify those cohorts. Guessing would eventually permit an old Prediction to be edited or scored under rules it never committed to.

The first v0.7 migration therefore needs to identify every existing record explicitly without modifying its established tables or fabricating new forecast values.

## Decision

Schema version 16 adds `prediction_forecast_contracts`, an immutable one-to-one child of `predictions`. It stores a closed forecast-model identifier, its matching scoring-contract identifier, and the prospective exact Forecast Deadline when that model requires one. The accepted pairs are:

- `binary-final-v1` with `binary-final-brier-v1`;
- `binary-trajectory-v1` with `binary-trajectory-brier-v1`;
- `numeric-interval-v1` with `numeric-interval-score-v1`; and
- `numeric-quantiles-5-v2` with `numeric-wis-v1`.

The migration classifies every existing Binary Prediction as `binary-final-v1` and every existing Numeric Prediction as `numeric-interval-v1`. Both receive their matching legacy scoring identity and a null prospective exact Deadline. This is a mechanical creation-era boundary, not a retrospective judgment about forecast quality.

Current GUI and CLI creation operations continue assigning those legacy identities during Milestone 46. They do not expose a model selector or the new models. Milestones 47 and 51 will switch each public creation flow only when its complete type-specific vertical workflow exists. Thereafter, reads, mutations, rendering, and analytics dispatch from the stored contract. Missing, unknown, or crossed identities are integrity errors and never invite inference from other rows.

The contract table is separate from `predictions` so the released parent table does not need a risky rebuild merely to add non-null conditional identities. Database constraints admit only approved pairs, require exact Deadlines only for prospective models, enforce forecast-type compatibility, and reject updates or direct child deletion while the Prediction exists. Normal application creation inserts the contract in the same transaction as the Prediction and sequence-one revision.

## Consequences

- Legacy and new cohorts remain mechanically distinguishable after any number of future releases.
- Existing Prediction, revision, search, analytics, and export rows are untouched by the migration.
- A future model change requires a new explicit identity and prospective creation boundary rather than reusing a vague version flag.
- Application code must treat a missing contract row as corruption or incompatible data, even though SQLite cannot enforce total one-to-one child participation without rebuilding the released parent table.
- Complete SQLite backup automatically carries the identity table. The analytical CSV remains unchanged until Milestone 54 adds its version-four cohort fields.

## Alternatives considered

### Infer the model from forecast-revision table population

Rejected because future migrations, partially written data, or shared fields could make inference ambiguous. The specification requires identity to be durable rather than reconstructed.

### Reuse `prediction_type`, `metadata_version`, or application version

Rejected because each describes a different concern. Binary has two scoring models, Numeric has two representation models, metadata edits are unrelated, and application upgrades do not change an existing Prediction's contract.

### Rebuild `predictions` with new non-null columns

Rejected for this additive foundation because the table is referenced by the complete application history. A constrained one-to-one child adds the same semantic identity with much lower migration risk.

### Convert old Predictions to the new models

Rejected because no exact Deadline, Binary standing trajectory, or Numeric quantiles can be recovered honestly from legacy records.
