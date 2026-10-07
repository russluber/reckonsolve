# Numeric forecasting planning history

These are historical excerpts from the accepted v0.7 design, retaining original section numbers. They preserve release assumptions, persistence proposals, migration/compatibility promises, and acceptance/planning material removed from the maintained scoring reference. Remaining mathematical rules are maintained in [Numeric scoring](../../maintainer/design/numeric-scoring.md); this is not a second current contract.

The legacy-coexistence/editor promises below were superseded by [ADR 0019](../../decisions/0019-retire-legacy-runtime-without-rebuilding-history.md) and the [current specification](../../product-spec.md#353-durable-model-and-cohort-identity). They do not authorize retired runtime workflows, import/conversion, cleanup, or new implementation. One-Shot follows its separate [current contract](../../product-spec.md#36-one-shot-prediction-contract). Original references to section numbers describe the original design's organization.

## 2. Design Goals

The v0.7.0 Numeric model should:

- Represent meaningful distributional uncertainty rather than only one chosen confidence interval
- Use one fixed elicitation contract for every new Numeric prediction
- Preserve complete immutable forecast revision history
- Score only probabilistic statements the user actually supplied
- Reward calibration and sharpness through a proper scoring rule
- Keep raw score interpretation honest across heterogeneous units and scales
- Support global scale-free calibration diagnostics
- Preserve exact base-ten user values without float-induced alteration
- Share the new immutable Forecast Deadline and effective-resolution lifecycle with Binary
- Keep interpolation visually useful but epistemically subordinate to elicited quantiles
- Preserve legacy Numeric predictions without inventing missing beliefs
- Remain future-compatible with richer quantile grids without exposing them in v0.7.0
- Remain understandable to a single user rather than optimizing for tournament or leaderboard use

## 3. Non-Goals

The v0.7.0 Numeric design does **not** implement:

- Numeric trajectory scoring
- Neutral truncation for Numeric scores
- A universal cross-question normalized Numeric skill score
- A global mean raw WIS across heterogeneous Numeric predictions
- Full parametric distribution fitting
- Invented outer-tail shapes beyond the elicited 5th and 95th percentiles
- Mandatory lower or upper domain bounds
- Arbitrary user-selected confidence levels
- Arbitrary user-selected quantile levels
- A separate date-distribution forecast type
- A separate discrete PMF editor
- A full probability density function whose tails integrate to one
- PIT histograms based on an invented full CDF
- Competitive rankings, leaderboards, or multi-user aggregation

These may be addressed separately in later versions.

## 34. Numeric Forecast Entry UX

The UI should present the five values in semantic human-facing groups:

```text
90% interval   [ lower ] to [ upper ]
50% interval   [ lower ] to [ upper ]
Median         [ value ]
```

The exact spatial arrangement may visually nest the 50% interval inside the 90% interval.

All five fields remain editable in any order.

Do not implement a mandatory sequential elicitation wizard.

### 34.1 Helper text

For continuous-style targets, concise helper text may say:

**90% interval**
> About 5% of your probability lies below the lower bound and 5% above the upper bound.

**Median**
> Half your probability lies below this value and half above.

**50% interval**
> About 25% lies below the lower bound and 25% above the upper bound.

For whole-number targets, helper text should acknowledge that endpoint ties can make closed-interval coverage larger than the nominal percentage.

## 35. Elicitation and Preview

Reckonsolve should not force one cognitive ordering.

The Forecasting Rulebook may recommend a default outside-in technique:

> 90% interval → median → 50% interval

but the UI must permit any entry order.

To reduce curve-shaping/anchoring:

- Do not require the user to manipulate a fitted distribution directly
- Prefer entering the five quantiles first
- Once all five values are valid, the UI may reveal the implied-distribution preview before commit
- The user may revise values after inspecting the preview

The graph is feedback about the entered quantiles, not the primary input mechanism.

## 36. Revision UX

When revising:

- Prepopulate all five current quantiles
- Allow editing any subset
- Commit one complete immutable replacement revision
- Preserve rationale
- Reject unchanged five-quantile revisions
- Use Forecast Review to retain the current distribution

The user should not need to reconstruct all five values from memory.

## 39. CDF and Density Views

The CDF is the authoritative implied-distribution visualization because quantiles map directly to cumulative probability levels.

A density-style view may be offered as secondary presentation.

For distinct quantile intervals under linear CDF interpolation, the implied density between anchors is piecewise constant.

If a density view is shown:

- Label it as implied/interpolated
- Preserve visible quantile anchors
- Handle repeated quantiles as point-mass jumps
- Do not draw unsupported outer tails as though they were fully specified

A complete full-support PDF is outside v0.7.0.

## 41. Resolution UX

Resolution should collect:

- Exact actual value
- Effective resolution time
- Optional Resolution Notes
- Optional Postmortem

The Prediction's unit and precision remain fixed.

The UI should separately preserve the automatic `recorded_at` timestamp.

If an objective source provides an exact time, the user should enter or confirm that time.

## 44. Legacy Numeric Model

The v0.6.0 Numeric model is a different forecast contract.

Conceptually:

$$
\text{interval-v1}=(L,M,U,c)
$$

where $c$ is a user-selected confidence percentage.

The v0.7.0 model is:

$$
\text{quantiles-5-v2}=(q_5,q_{25},q_{50},q_{75},q_{95}).
$$

These must have a hard cohort boundary.

### 44.1 Existing predictions remain legacy

Every Numeric Prediction created before the v0.7.0 five-quantile contract remains `interval-v1` for its entire lifetime.

This includes still-Open legacy predictions.

Their later revisions continue to use the legacy interval model until Resolved or Invalid.

### 44.2 New predictions use v2 only

After v0.7.0 ships, ordinary new Numeric creation exposes only `quantiles-5-v2`.

Do not provide a user-facing model selector.

The legacy model exists only for historical compatibility and completion of already-created predictions.

### 44.3 No inferred conversion

Do not invent missing quantiles.

An old 90% interval may imply $q_5$, $q_{50}$, and $q_{95}$, but it does not provide $q_{25}$ or $q_{75}$.

An old 80% interval provides different outer quantiles entirely.

Never synthesize quartiles by interpolation, parametric fitting, or midpoint assumptions.

### 44.4 No mixed scoring

Legacy interval scores and v0.7.0 WIS must not be averaged or presented as one common score.

Legacy forecasts do not enter v0.7.0 five-quantile calibration analytics.

## 45. Legacy Transition Convenience

A convenience action may eventually offer:

> Create new v2 prediction from this definition

It may copy non-forecast definition data such as question, background, Resolution Criteria, unit, precision, and tags.

It must not copy or infer five forecast quantiles from a legacy interval.

The user must explicitly enter the new v2 forecast.

This convenience is optional and not required for v0.7.0 completion.

## 46. Forecast-Model Versioning

Prediction model identity must be durable and explicit.

Conceptually use a field such as:

```text
numeric_model = interval_v1
```

or:

```text
numeric_model = quantiles_5_v2
```

The exact enum names may differ.

The identity belongs at the Prediction level because a Prediction's forecast contract is fixed for its lifetime.

Do not overload existing optimistic-concurrency metadata such as `metadata_version` to mean forecast-model version.

## 47. Scoring-Contract Versioning

The scoring implementation should also have a durable semantic version or identifier, conceptually:

```text
numeric_scoring_model = wis_5q_v1
```

This permits future scoring evolution without silently changing the meaning of historical records.

Derived score rows may be cached, but the canonical facts remain:

- Forecast revision
- Resolution
- Model/scoring contract identity

Scores must be reproducible from those facts.

## 48. Persistence Architecture

The v0.6.0 repository currently stores legacy revisions in a `numeric_forecast_revisions` shape containing lower, median, upper, confidence percentage, sequence, created-at, and rationale.

Those fields have legacy meaning and should continue to mean exactly that.

Do not repurpose legacy lower/upper fields as $q_5$/$q_{95}$ and then bolt quartiles onto the old schema.

### 48.1 Recommended v2 storage shape

Prefer a clean v2 revision representation plus generic quantile storage.

Conceptually:

```text
numeric_quantile_revisions
    revision_id
    prediction_id
    sequence
    created_at
    rationale

numeric_revision_quantiles
    revision_id
    quantile_level
    scaled_value
```

Each v0.7.0 revision has exactly five quantile rows for:

```text
0.05
0.25
0.50
0.75
0.95
```

The exact table and column names are not normative.

The semantic requirements are.

### 48.2 Why generic quantile storage

v0.7.0 UX requires exactly five quantiles.

Generic persistence avoids permanently encoding five levels into the schema and leaves room for future richer quantile grids.

The domain layer must still validate that a v0.7.0 revision contains exactly the required five levels.

## 49. Export and Import

Any durable export/import representation must include enough model identity to distinguish legacy `interval-v1` from v0.7.0 `quantiles-5-v2`.

v2 exports must preserve:

- Quantile levels
- Exact quantile values
- Unit
- Precision
- Revision sequence
- Immutable timestamps
- Forecast Deadline
- Expected Resolution
- Effective resolution time
- Recorded resolution time
- Resolution corrections
- Model/scoring contract identifiers where applicable

Do not rely on application version alone to infer the model.

## 50. Shared Lifecycle With Binary

New v0.7.0 Binary and Numeric predictions share:

- Mandatory Forecast Deadline
- Exact timezone-aware Forecast Deadline
- Immutable Forecast Deadline
- Optional editable Expected Resolution
- Immutable system-generated forecast revision timestamps
- No backdating
- Lock at Forecast Deadline
- Separate effective resolution time and recorded-at
- Invalid as unscored
- Append-only resolution corrections
- Hard legacy cohort boundaries

The scoring rules differ.

### Binary

Primary score:

> Trajectory Brier

with Binary neutral truncation for early resolution.

### Numeric

Primary score:

> Final-scoring-revision WIS

with no Numeric neutral truncation and no Numeric trajectory score in v0.7.0.

Do not force artificial symmetry where the scoring theory differs.

## 52. Current-Code Migration Principles

The current v0.6.0 implementation already has useful foundations that should be preserved:

- `PredictionType.NUMERIC`
- Exact `FixedPrecisionValue`
- Prediction-level unit
- Prediction-level decimal precision
- Immutable Numeric revision sequencing
- Numeric Resolution and correction concepts
- Append-only historical philosophy

v0.7.0 migration should:

- Add explicit Numeric forecast-model identity
- Mark all existing Numeric Predictions as legacy interval-v1
- Add clean v2 quantile persistence
- Preserve legacy revision rows unchanged
- Introduce exact timestamp Forecast Deadline semantics prospectively
- Add effective resolution timestamp support
- Preserve recorded-at audit facts
- Update UI creation so new Numeric means v2 only
- Keep still-open legacy predictions on the legacy editor
- Keep legacy analytics separate
- Update import/export contracts
- Add deterministic migration tests

Do not invent exact Forecast Deadline times or effective-resolution timestamps for legacy scoring history.

## 53. Analytics Cohort Eligibility

A resolved Numeric Prediction enters the canonical v0.7.0 Numeric analytics cohort only if:

- It uses `quantiles-5-v2`
- It has a valid final scoring revision before $C=\min(R,T)$
- It has a valid finite realized value
- It is Resolved rather than Invalid
- Its scoring contract is recognized as eligible

Each eligible Prediction contributes one Prediction-level observation.

No duration-based aggregate weight is used.

## 54. Implementation Invariants

Codex should treat the following as hard invariants unless a later accepted design explicitly supersedes them:

- Every new v0.7.0 Numeric Prediction uses exactly $q_5,q_{25},q_{50},q_{75},q_{95}$
- Newly created Numeric predictions do not expose the legacy confidence selector
- A Numeric model is fixed for a Prediction's lifetime
- Existing pre-v0.7 Numeric predictions remain legacy interval-v1
- Every v2 revision is complete and immutable
- Quantiles satisfy $q_5\le q_{25}\le q_{50}\le q_{75}\le q_{95}$
- Equal quantiles are allowed
- Crossed quantiles are rejected and never auto-sorted
- Numeric values preserve exact fixed-precision semantics
- Unit and scoring-critical quantity definition do not change after commitment
- Every new v2 Prediction has one mandatory immutable exact Forecast Deadline
- Expected Resolution has no scoring effect
- Forecast revisions cannot be user-backdated
- Revisions and Reviews are rejected at or after Forecast Deadline
- `effective_resolution_at` is distinct from `recorded_at`
- The final scoring revision is the latest valid revision strictly before $\min(R,T)$
- A post-effective-resolution revision remains audit history but never scores
- WIS uses only the elicited five quantiles
- Interpolation never changes WIS
- WIS is lower-is-better and unit/scale dependent
- No global raw-WIS aggregate is published across heterogeneous Numeric predictions
- Initial-to-final WIS comparison is within-Prediction only
- Every eligible resolved v2 Prediction contributes one calibration observation
- Whole-number calibration preserves ties and uses discrete-aware bounds
- Invalid Predictions do not score
- Legacy interval-v1 and v2 analytics are never silently mixed
- Numeric trajectory scoring is outside v0.7.0
- No Numeric neutral truncation is invented

## 55. Acceptance Criteria for v0.7.0

### Creation

- A new Numeric Prediction cannot be created without all five required quantiles
- A new Numeric Prediction cannot be created without a Forecast Deadline
- Forecast Deadline is later than the initial forecast timestamp
- Forecast Deadline resolves to one exact timezone-aware instant
- Unit is required
- Precision/value-type constraints are enforced
- No confidence selector appears for new v2 creation
- Prediction and first v2 revision are created atomically

### Validation

- Ordered distinct quantiles are accepted
- Repeated quantiles are accepted
- Crossed quantiles are rejected
- Crossed quantiles are not silently sorted
- Whole-number predictions reject non-whole-number forecast/resolution values
- Exact decimal values round-trip without float alteration
- NaN and infinities are impossible domain values

### Revision

- Revision form prepopulates all five standing quantiles
- A changed subset commits one complete new revision
- An unchanged revision is rejected or redirected to Review semantics
- Revision timestamps are immutable and system-generated
- Revisions cannot be backdated
- Revisions at or after Forecast Deadline are rejected

### Review and Journal

- Forecast Review does not create a v2 revision
- Review does not change scoring
- Journal does not change scoring
- Review wording no longer assumes one interval

### Lifecycle

- New v2 Prediction locks exactly at Forecast Deadline if nonterminal
- Resolution remains possible after Deadline
- Invalidation remains possible after Deadline
- Effective resolution time and recorded-at remain separate
- A revision later discovered to be post-effective-resolution is excluded from scoring but preserved in history

### WIS

- 50% interval score matches the specified formula
- 90% interval score matches the specified formula
- WIS matches the specified fixed-weight formula
- Equivalent average-five-quantile-score tests pass
- Boundary outcomes incur zero outside-interval distance penalty
- Zero-width intervals score correctly
- Score uses exact stored values rather than rendered rounded text
- WIS retains target unit in presentation

### Scoring revision selection

- Early resolution selects the last revision before effective resolution
- Late resolution selects the last revision before Forecast Deadline
- Resolution exactly at Deadline selects the last revision strictly before Deadline
- A revision exactly at Deadline is rejected
- A revision after effective resolution but before recorded-at is not the scoring revision
- Correction to effective resolution time can change final scoring revision deterministically

### Updating diagnostics

- Initial WIS uses sequence-one revision
- Final WIS uses the final scoring revision
- $\Delta \operatorname{WIS}=\operatorname{WIS}_{\text{initial}}-\operatorname{WIS}_{\text{final}}$
- Positive and negative sign interpretation is correct
- Raw $\Delta \operatorname{WIS}$ is not averaged across heterogeneous targets

### Calibration

- Each eligible resolved v2 Prediction contributes exactly one observation
- Continuous-style quantile calibration uses the five fixed levels
- No synthetic 10%-through-90% Numeric buckets are generated
- 50% and 90% below/inside/above summaries are correct
- Whole-number calibration retains equality/tie information
- Discrete quantile calibration computes both `< q` and `≤ q` empirical frequencies
- Sample size is displayed
- Invalid and legacy predictions are excluded from v2 calibration

### Visualization

- Distinct quantiles produce piecewise-linear CDF interpolation between q5 and q95
- Repeated quantiles render without division-by-zero and as vertical probability jumps
- Elicited quantile anchors are visually distinguishable from interpolation
- Outer 5% tails are not given invented complete shapes
- Interpolation does not affect WIS
- Resolved view can mark the realized value

### Legacy and migration

- Every existing Numeric Prediction is marked interval-v1
- Existing legacy revision values remain semantically unchanged
- Open legacy predictions continue to use the legacy revision editor
- New predictions use v2 only
- Missing legacy quantiles are never inferred
- Legacy interval scores are not recomputed as v2 WIS
- Legacy predictions do not enter v2 calibration
- Model identity survives export/import
- Migration is idempotent and regression-tested

### Corrections

- Actual-value correction recomputes WIS and calibration without rewriting forecast history
- Effective-resolution-time correction is audited and can change final revision selection
- Recorded-at remains immutable audit history

## 56. Suggested v0.7.0 Planning Order

This document specifies semantics rather than exact class names or migration numbers.

A reasonable implementation sequence is:

1. Introduce shared exact immutable Forecast Deadline semantics
2. Introduce `effective_resolution_at` versus `recorded_at`
3. Add explicit forecast-model identity separate from optimistic-concurrency metadata
4. Mark existing Numeric Predictions as legacy interval-v1
5. Add v2 five-quantile domain objects and validation
6. Add clean v2 quantile persistence
7. Update Numeric creation and revision application services
8. Update Numeric UI to the fixed 90% interval + median + 50% interval form
9. Implement pure WIS and quantile-score functions with comprehensive tests
10. Implement final-scoring-revision selection using $\min(R,T)$
11. Update Numeric Resolution and correction flows
12. Add individual resolved Numeric scorecard
13. Add implied-CDF visualization with repeated-quantile handling
14. Add v2 global calibration analytics, including discrete-aware ties
15. Add initial-versus-final WIS diagnostics
16. Keep legacy editor/scoring paths operational for existing predictions
17. Update CLI, search, CSV/export/import, and saved-view contracts as required
18. Update README, product specification, architecture documentation, and ADRs
19. Run migration/regression verification against the existing database
20. Leave Numeric trajectory scoring explicitly unimplemented

Repository-specific code structure should follow the actual v0.7.0 planning state rather than mechanically mirroring this section.

## 57. Relationship to the Forecasting Rulebook

The Forecasting Rulebook governs user behavior:

- What Numeric questions are admissible
- How the target quantity should be defined
- How agency and intervention policies work
- How the five quantiles should be understood
- How Forecast Deadline should be chosen
- Why Forecast Deadline is immutable
- When a prediction should become Invalid

This document governs software semantics:

- Which five quantiles are required
- How they are validated and stored
- Which revision is scored
- Exact WIS formula
- Calibration cohort construction
- Discrete tie handling
- Implied-CDF interpolation
- Legacy boundary and migration
- UI and lifecycle invariants

The Rulebook should remain readable without implementation knowledge.

This document should remain precise enough for Codex to implement and test.

## 59. Summary Contract

The intended v0.7.0 Numeric contract is:

> Every new Numeric Prediction forecasts one precisely defined scalar quantity in one immutable unit using five quantiles: the 5th, 25th, 50th, 75th, and 95th percentiles. The user interface presents these as a 90% central interval, a median, and a 50% central interval, with no confidence selector and no legacy-model choice. Every committed revision is a complete immutable five-quantile statement. Quantiles may be equal but may not cross. The Prediction has a mandatory immutable exact Forecast Deadline and uses a separate effective resolution timestamp. The final scoring revision is the latest valid revision strictly before the earlier of effective resolution and the Forecast Deadline. Resolved v2 forecasts receive standard five-quantile WIS using the median, 50% interval, and 90% interval. WIS scores only the elicited quantiles, retains target unit and scale, and is not globally averaged across heterogeneous personal Numeric questions. Global Numeric analytics are calibration-first: five quantile levels, 50% and 90% interval behavior, median balance, sample size, and sampling uncertainty, with discrete-aware tie semantics for whole-number outcomes. The implied central CDF uses transparent piecewise-linear interpolation between distinct quantiles, vertical jumps for repeated quantiles, and no invented outer-tail shape. Legacy user-selected-confidence Numeric predictions remain a hard separate cohort for their entire lifetime and are never silently converted, rescored, or mixed with the v2 calibration record. Numeric trajectory scoring is deliberately deferred beyond v0.7.0.
