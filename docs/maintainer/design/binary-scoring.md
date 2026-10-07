# Binary scoring

This maintained reference explains ordinary Brier loss, Adaptive Trajectory Brier, diagnostics, and Binary calibration. The [product specification](../../product-spec.md#35-adaptive-forecasting-contract) governs Adaptive behavior and its [One-Shot contract](../../product-spec.md#36-one-shot-prediction-contract) governs One-Shot. Storage and transactions are described in [architecture](../../architecture.md).

For practical interpretation, read [the user guide](../../guides/user-guide.md#learn-from-the-results). Question admissibility and choosing a forecasting window belong in [the forecasting guide](../../guides/forecasting-guide.md).

| Mode | Primary score | Observation selected |
| --- | --- | --- |
| Adaptive | Trajectory Brier | The committed standing probability path before the scoring cutoff. |
| One-Shot | Ordinary Brier | One effective forecast and answer after transcription corrections. |

Open/Locked Adaptive records, unanswered One-Shots, and Invalid records have no score. Each eligible answered Prediction contributes one observation within its mode; modes never share score or calibration denominators.

## Binary Scoring Rule

Ordinary Brier loss is the building block of both Binary scoring modes. The application accepts whole-number percentages from 0% through 100%; convert them to probabilities on the zero-to-one scale for scoring.

For reported probability:

$$
p\in[0,1]
$$

and realized outcome:

$$
y\in\{0,1\}
$$

define:

$$
B(p,y)=(p-y)^2
$$

Lower is better.

The Binary Brier range remains:

$$
0\le B\le1
$$

A neutral 50% forecast has Brier loss:

$$
B(0.5,y)=0.25
$$

for either Binary outcome.

## One-Shot Brier

One-Shot evaluates one probability settled before checking an existing answer. With probability $p$ and outcome $y$, its score is $B(p,y)=(p-y)^2$.

For example, a 70% Yes forecast followed by Yes scores $B(0.70,1)=0.09$. A No answer scores $B(0.70,0)=0.49$.

The score uses the effective forecast and answer after replaying transcription corrections. Originals and corrections remain inspectable. Reported forecast/reveal times and app-entry times are documentary or audit facts; none enters the score. There is no Deadline, standing path, neutral truncation, Initial/Final comparison, hold-initial counterfactual, or Updating Gain.

For $N$ eligible answered One-Shots, mean Brier is:

$$
\overline{\operatorname{Brier}}_{\text{one-shot}}=\frac{1}{N}\sum_{j=1}^{N}B(p_j,y_j).
$$

A correction replaces the effective contribution for the same Prediction; it never adds a second observation. With no eligible records, there is no mean rather than a score of zero.

## Adaptive trajectory purpose

Adaptive scoring measures the quality of the committed beliefs held throughout the predetermined forecasting window.

The primary Adaptive Binary score answers:
> How accurate was my stated probability over the entire predetermined forecasting window?

The final probability alone cannot answer that question.

A forecast may spend most of its life badly estimated and become accurate only immediately before resolution. Scoring only the final revision would allow the late forecast to erase the earlier history.

The trajectory model therefore treats each committed probability as a **standing forecast** that remains in force until it is replaced, the outcome becomes effectively resolved, or the fixed Forecast Deadline is reached.

## Adaptive time definitions

### Initial Forecast Time

Let:

$$
t_0
$$

be the timestamp of the first immutable ForecastRevision.

The initial Prediction, exact Deadline, and first forecast are created atomically.

There is therefore no scored interval during which a Prediction exists without a standing probability.

### Forecast Deadline

Let:

$$
T
$$

be the fixed Forecast Deadline.

The Forecast Deadline is:

- Mandatory for every trajectory-score-eligible Prediction
- Chosen when the initial forecast is committed
- Stored as an exact timezone-aware timestamp
- Immutable after commitment
- The last instant at which forecasting may remain active
- The endpoint of the predetermined trajectory-scoring window

The forecast is updateable on:

$$
[t_0,T)
$$

At exactly $T$, the Prediction becomes Locked if it has not already become Resolved or Invalid.

### Expected Resolution

Expected Resolution is separate from Forecast Deadline.

It answers:
> When do I currently expect to know the outcome?

Expected Resolution:

- Is optional metadata
- Has no scoring effect
- May be edited
- Must not change the trajectory-scoring window

### Effective Resolution Time

Let:

$$
R
$$

be the **effective resolution timestamp**.

This is the earliest defensible timestamp at which the outcome became fixed and ascertainable under the Prediction's Resolution Criteria and source of truth.

It is not necessarily the time the user records the Resolution in Reckonsolve.

Example:

```text
Carrier delivery timestamp: 2:13 PM
User records Resolution:    8:04 PM
```

For scoring:

$$
R=2{:}13\text{ PM}
$$

### Recorded Resolution Time

The **recorded resolution timestamp** is the immutable audit timestamp at which the Resolution was entered into Reckonsolve.

Effective resolution time and recorded resolution time are preserved separately. Effective $R$ cannot exceed the original recorded-at instant, including after correction.

### Active Scoring Endpoint

Define:

$$
C=\min(R,T)
$$

for a Resolved Prediction.

Actual forecast revisions contribute ordinary Brier loss only until $C$.

### Predetermined Scoring Duration

Define:

$$
D=T-t_0
$$

This denominator is fixed when the Prediction is created.

It must not be changed by:

- Attempts to change the committed Forecast Deadline
- Early resolution
- Late resolution
- Forecast revisions
- Forecast Reviews
- Journal entries

## Standing Forecast Semantics

Each ForecastRevision creates a standing probability.

Suppose revisions occur at timestamps:

$$
t_0<t_1<t_2<\dots<t_k<C
$$

with probabilities:

$$
p_0,p_1,p_2,\dots,p_k
$$

Then the standing intervals are:

$$
[t_0,t_1),[t_1,t_2),\dots,[t_k,C)
$$

Each revision remains in force continuously until the next scoring-relevant event.

Reckonsolve must not discretize this history into calendar days.

Elapsed duration is calculated from exact timestamps.

Duration calculations use normalized UTC instants.

The UI may display local time.

## Events That Do Not Change the Standing Forecast

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

## Forecast Revision Timing

### Revision timestamps are system-generated

A ForecastRevision becomes effective when it is committed.

Revision instants are system-generated, strictly increasing, and before the Deadline. A regressed clock rejects the save; the application never fabricates elapsed time.

### No retrospective belief reconstruction

If the user records an 80% forecast at 8:00 PM, Reckonsolve must not allow that probability to be marked as having stood since noon.

Trajectory scoring measures committed forecast history, not reconstructed mental history.

### Revisions stop at Forecast Deadline

A revision with commit timestamp:

$$
t\ge T
$$

must be rejected.

The same applies to Forecast Reviews.

### Revisions discovered to be post-resolution remain audit history but do not score

The application may not know the effective resolution time $R$ until the user records the Resolution.

It is therefore possible for a ForecastRevision to be committed after the outcome had already become fixed and ascertainable, but before Reckonsolve knew that fact.

If a later Resolution establishes:

$$
t_{\text{revision}}\ge R
$$

that revision remains part of the immutable audit history but is excluded from scoring.

The scoring cutoff is determined by the effective facts, not by when Reckonsolve learned them.

For all scoring-relevant revision selection, use revisions with commit timestamp strictly earlier than:

$$
C=\min(R,T)
$$

A revision at or after $C$ must never become the final scoring revision.

## Fixed Forecast Deadline Contract

Forecast Deadline is part of the immutable scoring contract.

After the initial forecast is committed:

- It cannot be extended
- It cannot be shortened
- It cannot be corrected merely because the original horizon was inconvenient
- It cannot be moved because resolution is delayed
- It cannot be moved because the current forecast is favorable or unfavorable

Poor deadline selection should become learning feedback rather than rewritten history.

If external events fundamentally invalidate the question, use the existing Invalid lifecycle semantics rather than silently moving the scoring horizon.

## Resolution After Forecast Deadline

If:

$$
R\ge T
$$

the Prediction receives ordinary trajectory scoring from $t_0$ through $T$.

No time after $T$ enters the score.

Example:

```text
Day 0    40%
Day 4    70%
Day 10   Forecast Deadline
Day 14   Outcome becomes known: Yes
```

Brier losses are:

$$
B(0.40,1)=0.36
$$

$$
B(0.70,1)=0.09
$$

The Trajectory Brier is:

$$
\frac{4(0.36)+6(0.09)}{10}=0.198
$$

Days 10 through 14 do not participate in scoring.

The Prediction was no longer forecastable after Day 10.

It merely remained unresolved.

## Early Resolution and Neutral Truncation

If:

$$
R<T
$$

the outcome becomes known before the predetermined Forecast Deadline.

Forecasting must stop at $R$.

However, the predetermined denominator:

$$
D=T-t_0
$$

must remain unchanged.

The interval:

$$
[R,T)
$$

receives the neutral Brier contribution:

$$
0.25
$$

This is **neutral truncation**.

### Neutral truncation is not a synthetic 50% forecast

Reckonsolve must not create or display a fake ForecastRevision at 50%.

The user did not make such a forecast.

The value 0.25 is a scoring constant used only to preserve the ex ante temporal weighting.

### Why neutral truncation exists

Without truncation, early resolution would shrink the denominator.

Then the timing of the realized outcome could determine how heavily earlier forecasts are weighted.

The scoring window must be chosen before the outcome is known.

Early resolution stops forecasting.

It does not rewrite the predetermined scoring horizon.

## Trajectory Brier Formula

Suppose the actual standing ForecastRevisions before $C$ have durations:

$$
d_1,d_2,\dots,d_k
$$

and Brier losses:

$$
B_1,B_2,\dots,B_k
$$

Define neutral truncation duration:

$$
d_N=\begin{cases}T-R & \text{if }R<T\\0 & \text{otherwise}\end{cases}
$$

Then:

$$
\boxed{B_{\text{trajectory}}=\frac{\sum_{i=1}^{k}d_iB_i+d_N(0.25)}{T-t_0}}
$$

Lower is better.

The score remains bounded:

$$
0\le B_{\text{trajectory}}\le1
$$

## Worked Early-Resolution Example

Predetermined scoring window:

```text
Day 0    40%
Day 2    70%
Day 4    Outcome becomes known: Yes
Day 10   Forecast Deadline
```

Actual Brier contributions:

$$
B(0.40,1)=0.36
$$

$$
B(0.70,1)=0.09
$$

Neutral truncation:

$$
0.25
$$

Therefore:

$$
B_{\text{trajectory}}=\frac{2(0.36)+2(0.09)+6(0.25)}{10}=0.24
$$

The four-day active forecasting portion by itself would have mean Brier:

$$
0.225
$$

The official Trajectory Brier remains:

$$
0.24
$$

because the original ten-day scoring window remains fixed.

## Canonical Display Scale

Reckonsolve displays raw Brier loss on the canonical lower-is-better scale.

Do not replace it in the ordinary UI with a centered transformation.

A centered form may be useful internally or explanatorily:

$$
S_B=0.25-B
$$

Under this transformation:

- Neutral 50% = 0
- Better than neutral = positive
- Worse than neutral = negative
- Truncation = 0

The primary Adaptive metric remains:
> Trajectory Brier

on the familiar lower-is-better Brier scale.

## Primary and Secondary Binary Metrics

### Primary metric

**Trajectory Brier**

Question answered:
> How good were my committed beliefs over the predetermined forecasting window?

This is the primary Adaptive Binary performance score. Final Brier remains a diagnostic.

### Initial Brier

Define:

$$
B_{\text{initial}}=B(p_0,y)
$$

Question answered:
> How good was my first committed judgment?

This remains a diagnostic.

### Final Brier

The final forecast is the latest valid ForecastRevision whose immutable commit timestamp is strictly earlier than:

$$
C=\min(R,T)
$$

This definition remains correct even if Reckonsolve only learns $R$ later and the audit history contains revisions committed after effective resolution.

Define:

$$
B_{\text{final}}=B(p_{\text{final}},y)
$$

Question answered:
> How good was the last probability I held while the question was still forecastable?

This remains a diagnostic.

### Hold-Initial Counterfactual

Calculate the score that would have resulted if the initial probability had remained standing throughout the active forecasting portion.

Use the same:

- Fixed Forecast Deadline
- Effective Resolution Time
- Neutral truncation
- Predetermined denominator

Call this:

$$
B_{\text{hold-initial}}
$$

For the same active endpoint and neutral duration:

$$
B_{\text{hold-initial}}=\frac{(C-t_0)B(p_0,y)+0.25d_N}{T-t_0}.
$$

### Updating Gain

Define:

$$
\boxed{G_{\text{update}}=B_{\text{hold-initial}}-B_{\text{trajectory}}}
$$

Interpretation:

- Positive means the actual revision path mechanically improved the trajectory score relative to never updating
- Zero means revisions had no net trajectory effect
- Negative means the revision path mechanically worsened the trajectory score

This is a mechanical counterfactual.

The UI and documentation must not claim that updating **caused** better forecasting performance.

## Active Forecast Fraction

Early resolution may cause much of a predetermined window to be neutrally truncated.

Active Forecast Fraction exposes how much of the window contained actual forecasting.

Define:

$$
F_{\text{active}}=\frac{C-t_0}{T-t_0}
$$

where:

$$
C=\min(R,T)
$$

Display this as a diagnostic such as:
> Active forecasting: 10% of scheduled window

This helps the user interpret a heavily truncated trajectory score.

It does not modify the score.

## Aggregate Analytics Weighting

Time weighting occurs **within** each Prediction.

It must not cause long-duration Predictions to dominate aggregate analytics.

For $N$ eligible Resolved Predictions:

$$
\boxed{\bar B_{\text{trajectory}}=\frac{1}{N}\sum_{j=1}^{N}B_{\text{trajectory},j}}
$$

Each eligible Prediction contributes exactly one Trajectory Brier to the aggregate mean.

A 100-day forecast and a 2-day forecast each contribute one Prediction-level score.

## Invalid Predictions

Invalid Predictions contribute no scoring observations.

They must be excluded from:

- Trajectory Brier aggregates
- Initial Brier aggregates
- Final Brier aggregates
- Updating Gain aggregates
- Final-probability calibration

Their immutable historical forecast record remains preserved.

This is particularly important for policy-conditioned forecasts where a material intervention-policy breach causes Invalidation.

## Resolution Corrections

Terminal corrections append history and recompute the score from effective facts.

If the effective Binary outcome is corrected:

- Preserve all original Resolution facts and corrections
- Recompute the Trajectory Brier against the latest effective outcome
- Keep the original $t_0$
- Keep the original immutable Forecast Deadline $T$
- Keep all ForecastRevision timestamps
- Do not create a new scoring window

An outcome or effective-time correction requires an explanation and appends history. Corrected $R$ may change final revision selection, neutral truncation, and the trajectory score. Original recorded-at and all revision timestamps remain unchanged. If corrected $R\le t_0$, there is no score or calibration observation.

## Adaptive lifecycle

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

## Scoring precision

Standing durations use exact integer microseconds between canonical UTC instants. Brier losses and weighted means use exact rational arithmetic. Local display dates and rounded score text never determine elapsed duration or scoring values.

## Boundary Conditions

### Immediate resolution

This boundary concerns Adaptive forecasts. One-Shot admits an existing answer that the user has not yet checked; its reported times do not gate scoring.

If effective resolution time is at or before initial forecast time, the Prediction is not a meaningful scored forecast and should not produce a trajectory score.

### Deadline must follow creation

Require:

$$
T>t_0
$$

A zero-duration or negative-duration scoring window is invalid.

### Resolution exactly at deadline

If:

$$
R=T
$$

there is no neutral truncation.

Actual standing forecasts score through the deadline.

### Revision exactly at deadline

A revision committed at:

$$
t=T
$$

is rejected.

### Resolution recorded long after effective resolution

Use $R$, not recorded-at, for trajectory scoring.

### Outcome corrected after scoring

Recompute from immutable source history.

Do not mutate historical ForecastRevisions.

## Brier Versus Log Score Decision

Reckonsolve uses Brier loss for both modes and time-averages it for Adaptive.

Reasons:

- Bounded 0-to-1 loss
- Stable behavior in a relatively small personal dataset
- Existing Reckonsolve continuity
- Natural compatibility with reliability and calibration analysis
- Easy interpretation as squared probability error
- Literal 0% and 100% remain scoreable without infinite loss
- Straightforward time averaging

Log score is not a supported scoring rule.

## Binary calibration and uncertainty

Calibration asks whether events assigned a given probability occur at approximately that frequency. It is separate from score.

Adaptive uses the final eligible probability strictly before $C=\min(R,T)$. One-Shot uses its effective single probability and answer. Each eligible Prediction counts once in its own mode. Neutral truncation never creates a synthetic 50% calibration observation, and neither revisions nor Reviews become separate observations.

The probability bins are 0–9%, 10–19%, through 90–100%. For a populated bin containing $n$ Predictions, the mean forecast and observed Yes frequency are:

$$
\bar p=\frac{1}{n}\sum_{j=1}^{n}p_j,
\qquad
\hat f=\frac{1}{n}\sum_{j=1}^{n}y_j.
$$

Compare the mean forecast with observed frequency. Empty bins have no invented means or uncertainty bounds. Reckonsolve does not compute time-weighted trajectory calibration.

The observed frequency has a pointwise 95% Wilson interval. For $s$ successes in $n>0$ observations, let $\hat f=s/n$ and $z\approx1.959963984540054$. Define:

$$
c=\frac{\hat f+z^2/(2n)}{1+z^2/n},
\qquad
h=\frac{z\sqrt{\hat f(1-\hat f)/n+z^2/(4n^2)}}{1+z^2/n}.
$$

The displayed bounds are $[\max(0,c-h),\min(1,c+h)]$. They describe uncertainty in observed frequency, not uncertainty in mean Brier or evidence of causal skill. They are pointwise intervals, not simultaneous guarantees across all bins. Small samples and selectively logged exercises can make apparent calibration misleading.

The same proportion calculation is used in [Numeric calibration](numeric-scoring.md#sampling-uncertainty-in-calibration).

## Illustrative Adaptive scorecard

An illustrative eligible Resolved Adaptive Binary scorecard:

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

## Adaptive scoring invariants

The following preserve the meaning of an Adaptive score:

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
- Brier remains the canonical Binary score
- No time-weighted trajectory calibration is computed
