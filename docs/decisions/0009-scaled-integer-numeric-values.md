# 0009: Store fixed-precision numeric values as scaled integers

- Status: Accepted
- Date: 2026-08-20

## Context

Milestone 13 introduces signed numeric prediction intervals without weakening the completed binary schema. A Numeric Prediction fixes one decimal precision for its lifetime, and every lower bound, median estimate, upper bound, and eventual actual outcome must round-trip exactly. SQLite has no fixed-precision decimal storage class. Its `REAL` values are binary floating-point, while free-form decimal text makes ordering and constraints needlessly fragile.

The existing `forecast_revisions` table has a required binary probability and is referenced by Binary Journal and Resolution history. Turning it into one nullable catch-all table would require a broad parent/child-table rewrite and make invalid combinations representable before Numeric Journal and lifecycle slices exist.

## Decision

Numeric precision is a whole number from zero through six decimal places, with zero as the product default. A Numeric Prediction stores its immutable unit label and precision. Each numeric forecast value is stored in `numeric_forecast_revisions` as a signed SQLite `INTEGER` scaled by `10 ** precision`. Domain code converts plain decimal input through Python's standard-library `Decimal`, rejects floats, values with excess nonzero precision, non-finite values, and scaled magnitudes above `999999999999999999`, then retains the scaled integer as its exact canonical value.

Schema version 9 keeps binary `forecast_revisions` unchanged and adds the type-specific numeric revision table. Type guards prevent a binary revision from belonging to a Numeric Prediction and vice versa. Numeric rows enforce `lower <= median <= upper`, confidence from 1 through 99, canonical UTC timestamps, deterministic per-Prediction sequence, and the same update/delete/replacement protections as binary revisions. Parent-Prediction deletion may still cascade deliberately.

Expanding the old binary-only `predictions.prediction_type` constraint uses transactional column rename/add/drop operations rather than dropping and reconstructing the parent table. Existing rows acquire the new `binary` default with null numeric definition fields. The whole migration remains one rollback-safe migration transaction.

## Consequences

- Decimal values round-trip exactly without a production dependency or binary floating-point drift.
- Integer ordering and interval constraints remain simple and authoritative in SQLite.
- The maximum natural-unit magnitude depends on precision: precision zero supports 18 integer digits, while precision six supports 12 integer digits plus six fractional digits. This is ample for the intended personal quantities while leaving all stored values and endpoint differences inside signed 64-bit capacity.
- Unit and precision cannot be changed after creation. Reckonsolve does not infer or convert units.
- Binary persistence and its historical foreign keys remain untouched. Later Numeric Journal and Resolution milestones must reference `numeric_forecast_revisions` explicitly rather than pretending the two revision tables are interchangeable.
- Presentation code must format the scaled value using the Prediction's precision; it must not pass the value through `float`.

## Alternatives considered

### SQLite `REAL`

Rejected because binary floating-point cannot fulfill the exact base-ten round-trip contract and can create surprising equality and boundary behavior.

### Canonical decimal text

Rejected because exact text is possible but numerical ordering, range checks, and interval constraints become more complex and easier to implement inconsistently.

### One nullable polymorphic revision table

Rejected because the released binary table requires probability and already anchors immutable child history. Rebuilding it would broaden migration risk, while nullable probability/bounds or sentinel values would make incoherent revisions representable.

### Arbitrary precision or a decimal database dependency

Rejected because zero through six decimal places and an 18-digit scaled range cover the approved use case. Arbitrary precision would add storage, validation, UI, and analytics complexity without a demonstrated need.
