# Binary trajectory planning history

These are historical excerpts from the accepted v0.7 design, retaining original section numbers. They preserve release assumptions, persistence proposals, migration/compatibility promises, and acceptance/planning material removed from the maintained scoring reference. Remaining mathematical rules are maintained in [Binary scoring](../../maintainer/design/binary-scoring.md); this is not a second current contract.

The legacy-coexistence/editor promises below were superseded by [ADR 0019](../../decisions/0019-retire-legacy-runtime-without-rebuilding-history.md) and the [current specification](../../product-spec.md#353-durable-model-and-cohort-identity). They do not authorize retired runtime workflows, import/conversion, cleanup, or new implementation. One-Shot follows its separate [current contract](../../product-spec.md#36-one-shot-prediction-contract). Original references to section numbers describe the original design's organization.

## 2. Design Goals

The Binary trajectory model should:
- Preserve the complete immutable forecast history
- Reward accurate probabilistic judgment through time
- Allow and encourage evidence-based updating
- Prevent late revisions from erasing earlier standing beliefs
- Prevent outcome timing from retroactively changing temporal weights
- Prevent deadline editing from changing scoring weights after the trajectory begins
- Keep each Prediction equally weighted in aggregate analytics regardless of its duration
- Preserve Brier score as the primary Binary scoring rule
- Keep the score understandable to a single user
- Distinguish factual resolution time from data-entry time
- Remain compatible with Reckonsolve's append-only historical philosophy

## 3. Non-Goals

This design does not specify:
- Numeric trajectory scoring; v0.7.0 Numeric uses final-scoring-revision WIS under the separate Numeric design
- Any neutral-truncation rule for Numeric forecasts
- Trajectory calibration weighting
- A switch from Brier score to logarithmic score
- Competitive ranking
- Leaderboards
- Multi-user aggregation
- Forecast weighting based on importance or difficulty
- Retroactive trajectory scoring for legacy predictions

These may be addressed separately.

## 20. Resolution Data Model Implication

The current concept of one Resolution timestamp is insufficient for exact trajectory scoring if that timestamp means only when the user recorded the Resolution.

The v0.7.0 Resolution model should distinguish at least:

```text
effective_resolution_at
recorded_at
```

### effective_resolution_at

Meaning:
> Earliest defensible timestamp at which the outcome became fixed and ascertainable under the Resolution Criteria.

Scoring-relevant.

### recorded_at

Meaning:
> Timestamp at which the user actually entered the Resolution into Reckonsolve.

Audit-relevant.

These fields must not be silently conflated.

## 21. Forecast Deadline Data Model Implication

The current date-only Forecast Deadline must evolve to an exact timezone-aware timestamp.

The implementation should preserve:
- Exact instant
- Local display semantics
- Timezone-safe duration calculations

Database storage should use a canonical timezone-safe representation.

UI defaults may reduce entry friction but must resolve to one exact immutable instant before creation is committed.

## 22. Expected Resolution Data Model Implication

Expected Resolution remains nonbinding metadata.

It may remain editable.

Its editing history may continue to follow whatever metadata-history policy Reckonsolve chooses.

It must never:
- Change $T$
- Change $R$
- Change trajectory duration
- Change scoring weights
- Unlock a Prediction
- Extend forecasting

## 24. User Interface Implications

Forecast Deadline should move from optional secondary metadata to a prominent required creation field.

The interface should clearly distinguish:

**Expected Resolution**
> When do you currently think you will know the answer?

**Forecast Deadline**
> What is the latest point at which this forecast should still accept updates?

Helpful creation guidance should discourage:
- Deadlines set merely equal to the modal expected resolution
- Extremely short cutoffs that unnecessarily prevent updating
- Extremely distant safety buffers
- Choosing a deadline based on desired scoring behavior

The interface should communicate that Forecast Deadline is immutable once the initial forecast is committed.

## 25. Resolution User Interface Implications

Resolution should collect or derive the effective resolution timestamp.

The UI should make clear:
> Effective resolution time = when the outcome became knowable under the Resolution Criteria.

Reckonsolve should separately preserve the automatic recorded-at timestamp.

When an objective source provides an exact timestamp, the user should enter or confirm that timestamp.

If the effective time is uncertain, the user should follow the Resolution Criteria or documented convention rather than optimize the scoring result.

## 30. Legacy Prediction Policy

Predictions created before the new trajectory contract should not automatically receive reconstructed Trajectory Brier scores.

Legacy Predictions were created under different semantics:
- Forecast Deadline may have been optional
- Forecast Deadline may have been date-only
- Forecast Deadline may have been editable
- The user did not commit under the new immutable-window scoring contract
- Effective resolution time may not exist as a separate fact

Recommended policy:
> Only Predictions created under the new trajectory-scoring contract are trajectory-score eligible.

Legacy Resolved Predictions may retain legacy final-revision analytics for historical continuity.

The UI should clearly distinguish legacy scoring from trajectory scoring if both remain visible.

Do not silently mix them in one aggregate mean.

## 31. Migration Principles

The v0.7.0 implementation should:
- Add a schema capability/version marker for trajectory-eligible Predictions
- Preserve all existing legacy records without reinterpretation
- Migrate Forecast Deadline storage carefully rather than inventing arbitrary exact times for scored legacy history
- Add effective resolution timestamp support prospectively
- Keep original recorded timestamps immutable
- Avoid silently converting legacy final scores into trajectory scores

Exact migration mechanics must be planned against the repository state at implementation time.

## 34. Acceptance Criteria for v0.7.0

The v0.7.0 implementation should not be considered complete until tests demonstrate at least the following.

### Creation
- A trajectory-eligible Binary Prediction cannot be created without a Forecast Deadline
- Forecast Deadline must be later than the initial forecast timestamp
- Forecast Deadline resolves to one exact timezone-aware instant
- Expected Resolution remains distinguishable from Forecast Deadline

### Immutability
- Forecast Deadline cannot be changed after creation
- Forecast revisions cannot be backdated
- Forecast Reviews do not create scoring revisions

### Lifecycle
- Prediction locks exactly at the Forecast Deadline if still nonterminal
- Revisions and Forecast Reviews are rejected at or after the deadline
- Resolution remains possible after the deadline
- Invalidation remains possible according to lifecycle rules

### Ordinary trajectory
- Multiple revisions produce the expected duration-weighted Brier result
- Sub-day revision intervals are weighted by actual elapsed duration
- Timezone conversion does not change elapsed scoring duration

### Early resolution
- Effective resolution before Forecast Deadline stops actual forecast weighting
- The remaining interval contributes neutral 0.25 Brier
- The predetermined denominator remains unchanged
- No synthetic 50% ForecastRevision is stored

### Late resolution
- Resolution after Forecast Deadline does not add scoring duration
- The last standing forecast scores only through Forecast Deadline

### Diagnostics
- Initial Brier uses the initial ForecastRevision
- Final Brier uses the final standing forecast before $\min(R,T)$
- Hold-initial uses the same predetermined window and truncation semantics
- Updating Gain equals hold-initial minus actual Trajectory Brier
- Active Forecast Fraction is calculated correctly

### Aggregation
- Each eligible Resolved Prediction contributes one Trajectory Brier
- Long-duration Predictions do not receive extra aggregate weight
- Invalid Predictions are excluded
- Legacy and trajectory scores are not silently averaged together

### Corrections
- Outcome correction recomputes the score without rewriting forecast history
- Effective-resolution-time correction is audited and recomputes truncation
- If corrected effective resolution time moves before a later revision, that later revision remains audit history but is excluded from scoring
- Recorded-at remains immutable audit history

## 35. Suggested v0.7.0 Planning Order

This document should guide milestone planning rather than dictate exact code structure.

A reasonable implementation sequence is:
1. Introduce the new immutable Forecast Deadline timestamp semantics
2. Separate Expected Resolution behavior from Forecast Deadline behavior
3. Add effective-resolution-time versus recorded-at semantics
4. Mark new Predictions as trajectory-score eligible
5. Implement a pure Binary trajectory-scoring domain function
6. Add comprehensive trajectory tests before changing Analytics
7. Update individual Resolved Binary scorecards
8. Update aggregate Binary performance analytics to use Trajectory Brier for eligible Predictions
9. Add Initial Brier, Final Brier, Updating Gain, and Active Forecast Fraction diagnostics
10. Define explicit legacy presentation behavior
11. Update CLI and CSV/export contracts as required
12. Update product specification, architecture documentation, and ADRs
13. Perform migration and regression verification against existing v0.6 behavior
14. Design trajectory calibration separately
15. Keep Numeric trajectory scoring explicitly deferred; use the separate v0.7.0 Numeric Forecasting Design for five-quantile final-revision WIS

Repository-specific classes, schema versions, migration numbers, and UI components should be chosen against the implementation state at v0.7.0 planning time.

Do not overload existing optimistic-concurrency metadata such as `metadata_version` to mean forecast-model or scoring-contract version. The trajectory-eligibility/model marker must have its own durable semantic identity.

## 36. Relationship to the Forecasting Rulebook

The forecasting rulebook governs the user's epistemic behavior:
- What questions are admissible
- How agency should be constrained
- How Resolution Criteria should be written
- How Forecast Deadline should be chosen
- Why Forecast Deadline is fixed
- When a Prediction should become Invalid

This document governs software semantics:
- What timestamps must exist
- Which timestamps affect scoring
- How ForecastRevisions partition time
- How Brier contributions are weighted
- How early resolution is truncated
- Which diagnostics are computed
- How aggregate analytics are formed
- What legacy behavior must not be silently rewritten

The two documents should remain separate.

The rulebook should be readable without implementation knowledge.

The trajectory design should be precise enough for milestone planning and implementation.

## 37. Summary Contract

The intended Binary trajectory contract is:
> A Binary forecast begins with an initial committed probability and a mandatory immutable Forecast Deadline. Every changed probability remains standing from its immutable commit timestamp until the next revision, the effective resolution time, or the Forecast Deadline. The predetermined scoring denominator always runs from initial commitment through the fixed Forecast Deadline. Ordinary standing intervals receive Brier loss. If the outcome becomes known early, the remaining predetermined time receives neutral Brier loss of 0.25 without creating a synthetic forecast. If resolution occurs after the deadline, no post-deadline time is scored. The resulting duration-weighted Trajectory Brier is the primary Binary score. Initial Brier, Final Brier, Updating Gain, and Active Forecast Fraction remain diagnostics. Every eligible Prediction contributes one Prediction-level Trajectory Brier to aggregate performance. Invalid Predictions do not score. Legacy Predictions are not silently retrofitted into the new contract.
