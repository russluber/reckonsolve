# Reckonsolve Binary Trajectory Scoring Design

## Document Status

**Status:** Accepted implementation contract for Reckonsolve v0.7.0

**Current implementation baseline:** Reckonsolve v0.6.0 does not implement this trajectory-scoring model.

**Target release:** Reckonsolve v0.7.0 Forecasting Model Overhaul.

This document is normative for the v0.7.0 Binary trajectory-scoring implementation unless a later explicitly accepted design decision supersedes it.

This document specifies the intended Binary trajectory-scoring contract for Reckonsolve.

It is implementation-facing.

The forecasting rulebook explains what questions belong in Reckonsolve and how they should be formulated. This document explains how Reckonsolve should score a valid Binary forecast whose probability changes over time.

The separate **Reckonsolve Numeric Forecasting Design** specifies the v0.7.0 five-quantile Numeric model, final-revision Weighted Interval Score, calibration analytics, interpolation rules, and Numeric legacy boundary. Numeric trajectory scoring is deliberately not part of v0.7.0.

---

## 1. Purpose

Reckonsolve should measure the quality of the beliefs actually held throughout a forecast's predetermined lifetime.

The primary Binary score should answer:
> How accurate was my stated probability over the entire predetermined forecasting window?

The final probability alone cannot answer that question.

A forecast may spend most of its life badly estimated and become accurate only immediately before resolution. Scoring only the final revision would allow the late forecast to erase the earlier history.

The trajectory model therefore treats each committed probability as a **standing forecast** that remains in force until it is replaced, the outcome becomes effectively resolved, or the fixed Forecast Deadline is reached.

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

## 4. Core Terminology

### 4.1 Initial Forecast Time

Let:

\[
t_0
\]

be the timestamp of the first immutable ForecastRevision.

The initial Prediction and its first forecast should continue to be created atomically.

There is therefore no scored interval during which a Prediction exists without a standing probability.

### 4.2 Forecast Deadline

Let:

\[
T
\]

be the fixed Forecast Deadline.

The Forecast Deadline is:
- Mandatory for every trajectory-score-eligible Prediction
- Chosen when the initial forecast is committed
- Stored as an exact timezone-aware timestamp
- Immutable after commitment
- The last instant at which forecasting may remain active
- The endpoint of the predetermined trajectory-scoring window

The forecast is updateable on:

\[
[t_0,T)
\]

At exactly \(T\), the Prediction becomes Locked if it has not already become Resolved or Invalid.

### 4.3 Expected Resolution

Expected Resolution is separate from Forecast Deadline.

It answers:
> When do I currently expect to know the outcome?

Expected Resolution:
- Is optional metadata
- Has no scoring effect
- May be edited
- Must not change the trajectory-scoring window

### 4.4 Effective Resolution Time

Let:

\[
R
\]

be the **effective resolution timestamp**.

This is the earliest defensible timestamp at which the outcome became fixed and ascertainable under the Prediction's Resolution Criteria and source of truth.

It is not necessarily the time the user records the Resolution in Reckonsolve.

Example:

```text
Carrier delivery timestamp: 2:13 PM
User records Resolution:    8:04 PM
```

For scoring:

\[
R=2{:}13\text{ PM}
\]

### 4.5 Recorded Resolution Time

The **recorded resolution timestamp** is the immutable audit timestamp at which the Resolution was entered into Reckonsolve.

Effective resolution time and recorded resolution time must be preserved separately.

### 4.6 Active Scoring Endpoint

Define:

\[
C=\min(R,T)
\]

for a Resolved Prediction.

Actual forecast revisions contribute ordinary Brier loss only until \(C\).

### 4.7 Predetermined Scoring Duration

Define:

\[
D=T-t_0
\]

This denominator is fixed when the Prediction is created.

It must not be changed by:
- Later Forecast Deadline edits
- Early resolution
- Late resolution
- Forecast revisions
- Forecast Reviews
- Journal entries

## 5. Binary Scoring Rule

Reckonsolve should retain ordinary Binary Brier loss as the canonical Binary scoring rule.

For reported probability:

\[
p\in[0,1]
\]

and realized outcome:

\[
y\in\{0,1\}
\]

define:

\[
B(p,y)=(p-y)^2
\]

Lower is better.

The Binary Brier range remains:

\[
0\le B\le1
\]

A neutral 50% forecast has Brier loss:

\[
B(0.5,y)=0.25
\]

for either Binary outcome.

## 6. Standing Forecast Semantics

Each ForecastRevision creates a standing probability.

Suppose revisions occur at timestamps:

\[
t_0<t_1<t_2<\dots<t_k<C
\]

with probabilities:

\[
p_0,p_1,p_2,\dots,p_k
\]

Then the standing intervals are:

\[
[t_0,t_1),[t_1,t_2),\dots,[t_k,C)
\]

Each revision remains in force continuously until the next scoring-relevant event.

Reckonsolve must not discretize this history into calendar days.

Elapsed duration should be calculated from exact timestamps.

Internally, duration calculations should use normalized timezone-aware instants such as UTC.

The UI may display local time.

## 7. Events That Do Not Change the Standing Forecast

The following events must not split a scoring interval:
- Journal entry
- Journal correction
- Forecast Review
- Forecast Review note
- Metadata edit that does not alter the scoring contract
- Postmortem activity after resolution

A Forecast Review means:
> I deliberately reconsidered the current forecast and retained it.

It does not create a new probability and must therefore have zero effect on the trajectory calculation.

## 8. Forecast Revision Timing

### 8.1 Revision timestamps are system-generated

A ForecastRevision becomes effective when it is committed.

The user must not be able to backdate or forward-date a revision.

### 8.2 No retrospective belief reconstruction

If the user records an 80% forecast at 8:00 PM, Reckonsolve must not allow that probability to be marked as having stood since noon.

Trajectory scoring measures committed forecast history, not reconstructed mental history.

### 8.3 Revisions stop at Forecast Deadline

A revision with commit timestamp:

\[
t\ge T
\]

must be rejected.

The same applies to Forecast Reviews.

### 8.4 Revisions discovered to be post-resolution remain audit history but do not score

The application may not know the effective resolution time \(R\) until the user records the Resolution.

It is therefore possible for a ForecastRevision to be committed after the outcome had already become fixed and ascertainable, but before Reckonsolve knew that fact.

If a later Resolution establishes:

\[
t_{revision}\ge R
\]

that revision remains part of the immutable audit history but is excluded from scoring.

The scoring cutoff is determined by the effective facts, not by when Reckonsolve learned them.

For all scoring-relevant revision selection, use revisions with commit timestamp strictly earlier than:

\[
C=\min(R,T)
\]

A revision at or after \(C\) must never become the final scoring revision.

## 9. Fixed Forecast Deadline Contract

Forecast Deadline is part of the immutable scoring contract.

After the initial forecast is committed:
- It cannot be extended
- It cannot be shortened
- It cannot be corrected merely because the original horizon was inconvenient
- It cannot be moved because resolution is delayed
- It cannot be moved because the current forecast is favorable or unfavorable

Poor deadline selection should become learning feedback rather than rewritten history.

If external events fundamentally invalidate the question, use the existing Invalid lifecycle semantics rather than silently moving the scoring horizon.

## 10. Resolution After Forecast Deadline

If:

\[
R\ge T
\]

the Prediction receives ordinary trajectory scoring from \(t_0\) through \(T\).

No time after \(T\) enters the score.

Example:

```text
Day 0    40%
Day 4    70%
Day 10   Forecast Deadline
Day 14   Outcome becomes known: Yes
```

Brier losses are:

\[
B(0.40,1)=0.36
\]

\[
B(0.70,1)=0.09
\]

The Trajectory Brier is:

\[
\frac{4(0.36)+6(0.09)}{10}=0.198
\]

Days 10 through 14 do not participate in scoring.

The Prediction was no longer forecastable after Day 10.

It merely remained unresolved.

## 11. Early Resolution and Neutral Truncation

If:

\[
R<T
\]

the outcome becomes known before the predetermined Forecast Deadline.

Forecasting must stop at \(R\).

However, the predetermined denominator:

\[
D=T-t_0
\]

must remain unchanged.

The interval:

\[
[R,T)
\]

receives the neutral Brier contribution:

\[
0.25
\]

This is **neutral truncation**.

### 11.1 Neutral truncation is not a synthetic 50% forecast

Reckonsolve must not create or display a fake ForecastRevision at 50%.

The user did not make such a forecast.

The value 0.25 is a scoring constant used only to preserve the ex ante temporal weighting.

### 11.2 Why neutral truncation exists

Without truncation, early resolution would shrink the denominator.

Then the timing of the realized outcome could determine how heavily earlier forecasts are weighted.

The scoring window must be chosen before the outcome is known.

Early resolution stops forecasting.

It does not rewrite the predetermined scoring horizon.

## 12. Trajectory Brier Formula

Suppose the actual standing ForecastRevisions before \(C\) have durations:

\[
d_1,d_2,\dots,d_k
\]

and Brier losses:

\[
B_1,B_2,\dots,B_k
\]

Define neutral truncation duration:

\[
d_N=\begin{cases}T-R & \text{if }R<T\\0 & \text{otherwise}\end{cases}
\]

Then:

\[
\boxed{B_{\text{trajectory}}=\frac{\sum_{i=1}^{k}d_iB_i+d_N(0.25)}{T-t_0}}
\]

Lower is better.

The score remains bounded:

\[
0\le B_{\text{trajectory}}\le1
\]

## 13. Worked Early-Resolution Example

Predetermined scoring window:

```text
Day 0    40%
Day 2    70%
Day 4    Outcome becomes known: Yes
Day 10   Forecast Deadline
```

Actual Brier contributions:

\[
B(0.40,1)=0.36
\]

\[
B(0.70,1)=0.09
\]

Neutral truncation:

\[
0.25
\]

Therefore:

\[
B_{\text{trajectory}}=\frac{2(0.36)+2(0.09)+6(0.25)}{10}=0.24
\]

The four-day active forecasting portion by itself would have mean Brier:

\[
0.225
\]

The official Trajectory Brier remains:

\[
0.24
\]

because the original ten-day scoring window remains fixed.

## 14. Canonical Display Scale

Reckonsolve should continue to display raw Brier loss as the canonical Binary score.

Do not replace it in the ordinary UI with a centered transformation.

A centered form may be useful internally or explanatorily:

\[
S_B=0.25-B
\]

Under this transformation:
- Neutral 50% = 0
- Better than neutral = positive
- Worse than neutral = negative
- Truncation = 0

However, the canonical user-facing metric should remain:
> Trajectory Brier

on the familiar lower-is-better Brier scale.

## 15. Primary and Secondary Binary Metrics

### 15.1 Primary metric

**Trajectory Brier**

Question answered:
> How good were my committed beliefs over the predetermined forecasting window?

This should replace final-revision Brier as the primary Binary performance score for trajectory-eligible Predictions.

### 15.2 Initial Brier

Define:

\[
B_{\text{initial}}=B(p_0,y)
\]

Question answered:
> How good was my first committed judgment?

This remains a diagnostic.

### 15.3 Final Brier

The final forecast is the latest valid ForecastRevision whose immutable commit timestamp is strictly earlier than:

\[
C=\min(R,T)
\]

This definition remains correct even if Reckonsolve only learns \(R\) later and the audit history contains revisions committed after effective resolution.

Define:

\[
B_{\text{final}}=B(p_{\text{final}},y)
\]

Question answered:
> How good was the last probability I held while the question was still forecastable?

This remains a diagnostic.

### 15.4 Hold-Initial Counterfactual

Calculate the score that would have resulted if the initial probability had remained standing throughout the active forecasting portion.

Use the same:
- Fixed Forecast Deadline
- Effective Resolution Time
- Neutral truncation
- Predetermined denominator

Call this:

\[
B_{\text{hold-initial}}
\]

### 15.5 Updating Gain

Define:

\[
\boxed{G_{\text{update}}=B_{\text{hold-initial}}-B_{\text{trajectory}}}
\]

Interpretation:
- Positive means the actual revision path mechanically improved the trajectory score relative to never updating
- Zero means revisions had no net trajectory effect
- Negative means the revision path mechanically worsened the trajectory score

This is a mechanical counterfactual.

The UI and documentation must not claim that updating **caused** better forecasting performance.

## 16. Active Forecast Fraction

Early resolution may cause much of a predetermined window to be neutrally truncated.

Reckonsolve should expose how much of the window contained actual forecasting.

Define:

\[
F_{\text{active}}=\frac{C-t_0}{T-t_0}
\]

where:

\[
C=\min(R,T)
\]

Display this as a diagnostic such as:
> Active forecasting: 10% of scheduled window

This helps the user interpret a heavily truncated trajectory score.

It should not itself modify the score.

## 17. Aggregate Analytics Weighting

Time weighting occurs **within** each Prediction.

It must not cause long-duration Predictions to dominate aggregate analytics.

For \(N\) eligible Resolved Predictions:

\[
\boxed{\bar B_{\text{trajectory}}=\frac{1}{N}\sum_{j=1}^{N}B_{\text{trajectory},j}}
\]

Each eligible Prediction contributes exactly one Trajectory Brier to the aggregate mean.

A 100-day forecast and a 2-day forecast each contribute one Prediction-level score.

## 18. Invalid Predictions

Invalid Predictions contribute no scoring observations.

They must be excluded from:
- Trajectory Brier aggregates
- Initial Brier aggregates
- Final Brier aggregates
- Updating Gain aggregates
- Any later trajectory calibration analysis

Their immutable historical forecast record remains preserved.

This is particularly important for policy-conditioned forecasts where a material intervention-policy breach causes Invalidation.

## 19. Resolution Corrections

Reckonsolve's append-only terminal correction philosophy should remain intact.

If the effective Binary outcome is corrected:
- Preserve all original Resolution facts and corrections
- Recompute the Trajectory Brier against the latest effective outcome
- Keep the original \(t_0\)
- Keep the original immutable Forecast Deadline \(T\)
- Keep all ForecastRevision timestamps
- Do not create a new scoring window

If effective resolution time \(R\) is corrected, the correction must also be append-only and audited because changing \(R\) may change neutral truncation and therefore the Trajectory Brier.

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
- Change \(T\)
- Change \(R\)
- Change trajectory duration
- Change scoring weights
- Unlock a Prediction
- Extend forecasting

## 23. Lifecycle Implications

### Open

Before Forecast Deadline and before terminal state:
- Forecast revisions allowed
- Forecast Reviews allowed
- Journals allowed

### Locked

At or after Forecast Deadline when no terminal state exists:
- Forecast revisions rejected
- Forecast Reviews rejected
- Journals may continue under existing product rules
- Resolution remains possible
- Invalidation remains possible

### Resolved

No further forecasts.

Score using:
- Immutable forecast history
- Fixed Forecast Deadline
- Effective resolution time
- Latest effective corrected outcome

### Invalid

No score.

History remains preserved.

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

## 26. Scoring Precision

Duration weighting should use exact elapsed time at sufficient precision to avoid arbitrary day-based artifacts.

Implementation details may use:
- Integer microseconds
- Integer milliseconds
- Another exact or sufficiently precise duration representation

Avoid floating-point timestamp arithmetic where a more exact representation is practical.

Brier arithmetic may continue using ordinary numeric types appropriate to the current Binary analytics layer, provided tests establish deterministic expected results.

## 27. Boundary Conditions

### 27.1 Immediate resolution

A Prediction should normally not be created if the outcome is already known.

If effective resolution time is at or before initial forecast time, the Prediction is not a meaningful scored forecast and should not produce a trajectory score.

### 27.2 Deadline must follow creation

Require:

\[
T>t_0
\]

A zero-duration or negative-duration scoring window is invalid.

### 27.3 Resolution exactly at deadline

If:

\[
R=T
\]

there is no neutral truncation.

Actual standing forecasts score through the deadline.

### 27.4 Revision exactly at deadline

A revision committed at:

\[
t=T
\]

is rejected.

### 27.5 Resolution recorded long after effective resolution

Use \(R\), not recorded-at, for trajectory scoring.

### 27.6 Outcome corrected after scoring

Recompute from immutable source history.

Do not mutate historical ForecastRevisions.

## 28. Brier Versus Log Score Decision

Reckonsolve should retain Brier as the primary Binary score for this trajectory design.

Reasons:
- Bounded 0-to-1 loss
- Stable behavior in a relatively small personal dataset
- Existing Reckonsolve continuity
- Natural compatibility with reliability and calibration analysis
- Easy interpretation as squared probability error
- Literal 0% and 100% remain scoreable without infinite loss
- Straightforward time averaging

Log score remains a possible future advanced diagnostic.

It is not part of this trajectory implementation contract.

## 29. Calibration Is Deliberately Deferred

The existing Binary reliability/calibration view may remain as a **final-scoring-revision** diagnostic.

It should use the final valid standing probability immediately before:

\[
C=\min(R,T)
\]

and should remain conceptually separate from Trajectory Brier.

Neutral truncation is a scoring device.

It must not create synthetic 50% calibration observations.

A separate future design may determine how actual standing probability intervals contribute to trajectory calibration while preserving equal Prediction-level weighting.

Until that design exists, do not present any metric labeled **trajectory calibration**.

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

## 32. Suggested Analytics Presentation

For one eligible Resolved Binary Prediction, the v0.7.0 scorecard may show:

```text
Trajectory Brier     0.142
Initial Brier        0.250
Final Brier          0.040
Updating Gain       +0.061
Active forecasting   73%
```

Supporting explanation:
> Trajectory Brier is the time-weighted Brier loss of the probabilities that stood during the fixed forecasting window. Lower is better.

The UI should not overwhelm the user with every metric simultaneously if that harms readability.

Trajectory Brier is primary.

The rest are diagnostics.

## 33. Implementation Invariants

Codex should treat the following as hard invariants unless a later design decision explicitly supersedes them:
- Every trajectory-eligible Prediction has exactly one immutable Forecast Deadline
- Forecast Deadline is an exact timestamp
- Forecast Deadline is fixed with the initial forecast
- Forecast Deadline is never extended or shortened
- Expected Resolution has no scoring effect
- ForecastRevision timestamps are immutable and cannot be user-backdated
- A revision at or after `min(effective_resolution_at, Forecast Deadline)` is never scoring-relevant, even if it was committed before the Resolution was recorded
- A standing probability remains effective until the next scoring-relevant revision, effective resolution, or Forecast Deadline
- Journals do not affect trajectory scoring
- Forecast Reviews do not affect trajectory scoring
- Early resolution uses neutral truncation through the original Forecast Deadline
- Neutral truncation does not create synthetic ForecastRevisions
- Resolution after Forecast Deadline does not extend the scoring window
- Effective resolution time is distinct from recorded resolution time
- Invalid Predictions receive no score
- Each eligible Prediction contributes exactly one Trajectory Brier to aggregate performance
- Prediction duration does not determine aggregate weight
- Outcome corrections recompute against immutable history rather than rewriting it
- Legacy Predictions are not silently retrofitted into the new scoring contract
- Brier remains the canonical Binary score
- Trajectory calibration is outside the first implementation scope

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
- Final Brier uses the final standing forecast before \(\min(R,T)\)
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
