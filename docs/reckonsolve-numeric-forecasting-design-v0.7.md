# Reckonsolve Numeric Forecasting Design

## Document Status

**Status:** Accepted implementation contract for Reckonsolve v0.7.0

**Current implementation baseline:** Reckonsolve v0.6.0 uses a legacy Numeric forecast model consisting of one user-selected-confidence central interval plus a median.

**Target release:** Reckonsolve v0.7.0 Forecasting Model Overhaul.

This document is normative for the v0.7.0 Numeric implementation unless a later explicitly accepted design decision supersedes it.

It is implementation-facing.

The **Forecasting Rulebook** governs which questions belong in Reckonsolve and how the user should formulate and reason about them.

The **Binary Trajectory Scoring Design** governs Binary trajectory semantics.

This document governs the v0.7.0 Numeric forecast representation, validation, scoring, visualization, calibration analytics, lifecycle integration, persistence boundary, and migration rules.

---

## 1. Purpose

Reckonsolve should train the user to form, express, update, and evaluate calibrated and appropriately sharp probabilistic beliefs about personally relevant uncertain numerical outcomes.

The primary Numeric forecast object should answer:

> What compact set of quantiles best represents my current subjective distribution over this numerical outcome?

The primary resolved Numeric score should answer:

> Given the realized value, how sharp and accurate was the final probabilistic forecast while the question was still forecastable?

The global Numeric analytics should answer:

> Across many forecasts, are the quantiles and interval coverages behaving like the probabilities I claim?

---

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

---

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

---

## 4. Core Forecast Model

Every new v0.7.0 Numeric Prediction uses exactly five quantiles:

\[
\boxed{q_5,\ q_{25},\ q_{50},\ q_{75},\ q_{95}}
\]

where \(q_\tau\) denotes the forecasted \(\tau\)-quantile of the target quantity.

The user-facing representation is:

- **90% central interval:** \([q_5,q_{95}]\)
- **Median:** \(q_{50}\)
- **50% central interval:** \([q_{25},q_{75}]\)

There is no confidence selector.

There is no choice between the legacy interval model and the new model for newly created predictions.

> New Numeric means the five-quantile model.

---

## 5. Quantile Semantics

### 5.1 Quantiles are inverse-CDF statements

The durable semantic statement is:

\[
Q(\tau)=q_\tau
\]

for:

\[
\tau\in\{0.05,0.25,0.50,0.75,0.95\}.
\]

For an effectively continuous distribution with distinct quantiles, it is natural to visualize these as CDF anchors:

\[
F(q_\tau)=\tau.
\]

That equality must not be treated as universally exact.

For discrete outcomes or repeated quantiles, a valid \(\tau\)-quantile satisfies:

\[
P(Y<q_\tau)\le\tau\le P(Y\le q_\tau).
\]

This distinction is required for correct tie handling and calibration analytics.

### 5.2 Central 50% interval

For an effectively continuous quantity:

\[
[q_{25},q_{75}]
\]

corresponds approximately to:

- 25% probability below \(q_{25}\)
- 50% probability inside the closed interval
- 25% probability above \(q_{75}\)

For a discrete quantity, endpoint probability mass may make closed-interval coverage exceed 50%.

### 5.3 Central 90% interval

For an effectively continuous quantity:

\[
[q_5,q_{95}]
\]

corresponds approximately to:

- 5% probability below \(q_5\)
- 90% probability inside the closed interval
- 5% probability above \(q_{95}\)

For a discrete quantity, endpoint probability mass may make closed-interval coverage exceed 90%.

### 5.4 Median

The median is:

\[
q_{50}.
\]

It is a probability balance point.

It need not equal the mean, mode, or geometric midpoint of either interval.

Skewed forecasts are valid.

---

## 6. Numeric Target Contract

A Numeric Prediction forecasts exactly one well-defined scalar random variable.

Good examples:

- First written mechanic estimate in USD
- Number of whole calendar days until a defined event
- September electricity bill in USD
- Number of attendees
- Temperature at a specified time and source

A single Numeric Prediction must not combine multiple outcome variables.

For example:

> What will the repair cost and how long will it take?

must be represented as two separate predictions.

---

## 7. Resolution Criteria and Scoring-Critical Definition

Resolution Criteria should define the target quantity before the initial forecast is committed.

When relevant, they should specify:

- What variable is measured
- Measurement start
- Measurement end
- Source of truth
- Unit
- Inclusion or exclusion of taxes, fees, adjustments, or components
- Aggregation rule if several candidate measurements can exist
- Rounding or resolution convention if material
- Exceptional-case handling
- Intervention policy for policy-conditioned predictions

The Forecast Deadline is a separate field and does not define the factual value of the target.

### 7.1 Clarification versus redefinition

Ordinary clarification may be audited without invalidating a prediction if it does not change the underlying random variable.

A material change to what historical forecasts referred to is not a normal metadata edit.

If changing the definition would change the random variable, such as:

- Initial estimate → final invoice
- Pre-tax → post-tax
- First quote → lowest quote
- USD → cents or another unit
- One source of truth → materially different source
- Different measurement start or end

then the existing Prediction must not be silently reinterpreted.

Recommended behavior:

> Mark the original Prediction Invalid and create a new Prediction under the new definition.

If the original definition remains resolvable, it may instead be resolved under the original contract.

---

## 8. Unit and Precision Contract

### 8.1 Unit is required

Every new Numeric Prediction must have one required nonblank unit.

Examples include USD, days, hours, °F, kg, and people.

### 8.2 Unit is immutable after initial commitment

Once the initial forecast is committed, unit is part of the scoring contract.

It must not be edited.

Changing from dollars to cents, days to hours, or any other scale transformation changes the numerical score and historical meaning.

### 8.3 Preserve exact fixed precision

The v0.6.0 implementation already has a sound exact-value foundation in `FixedPrecisionValue`: a signed scaled integer plus Prediction-level decimal precision, with no float-based domain input.

v0.7.0 should preserve or evolve that exact representation rather than regress to binary floating-point storage for user-entered forecast and resolution values.

All five quantiles and the realized outcome must use the Prediction's declared precision.

### 8.4 Display precision is not scoring rounding

Scoring uses exact stored values.

UI formatting must not round values before scoring.

---

## 9. Value-Type Constraint

v0.7.0 should support at least two Numeric value constraints:

- **Decimal/continuous-style**
- **Whole-number**

This is not a separate forecast type.

Both use the same five-quantile model and WIS.

For whole-number Predictions:

- Forecast quantiles must satisfy the whole-number constraint
- Resolution value must satisfy the whole-number constraint
- Repeated quantiles are expected and valid
- Calibration analytics must use discrete-aware tie semantics

Do not add a discrete PMF editor in v0.7.0.

---

## 10. Forecast Revision Contract

A v0.7.0 Numeric ForecastRevision is one immutable complete five-quantile statement.

Conceptually it contains:

```text
revision_id
prediction_id
sequence
created_at
q05
q25
q50
q75
q95
rationale
```

The exact persistence layout may use normalized quantile rows rather than five literal columns.

### 10.1 Complete revisions

Every committed revision contains all five quantiles.

If only \(q_{95}\) changes, the new revision still records the complete five-quantile distribution that now stands.

### 10.2 Atomic initial creation

The Prediction and its sequence-one Numeric ForecastRevision must be created atomically.

There must be no period in which a scored Numeric Prediction exists without a standing complete forecast.

### 10.3 Immutable timestamps

A revision becomes effective at its system-generated commit time.

Users must not backdate or forward-date forecast revisions.

### 10.4 No-change revisions

A normal revision that repeats all five current quantile values should be rejected as unchanged.

Use Forecast Review for deliberate reconsideration that retains the forecast.

---

## 11. Forecast Reviews and Journals

A Numeric Forecast Review means:

> I deliberately reconsidered the current five-quantile forecast and retained it.

A Review:

- Does not create a NumericForecastRevision
- Does not change WIS
- Does not change the final scoring revision
- Does not create a calibration observation
- Does not split any future trajectory interval if Numeric trajectory scoring is later designed

Journal entries and corrections likewise do not alter the standing forecast.

The legacy phrase **Keep this interval** should be replaced for v0.7.0 Numeric UI with language such as **Keep current forecast** or **Keep current distribution**.

---

## 12. Forecast Deadline Contract

Every new v0.7.0 Numeric Prediction must have one mandatory Forecast Deadline.

Let:

\[
T
\]

be that timestamp.

The Forecast Deadline is:

- Chosen atomically with the initial forecast
- Stored as an exact timezone-aware instant
- Strictly later than initial forecast time
- Immutable after commitment
- The last permissible instant for revisions and Reviews

Forecasting is allowed on:

\[
[t_0,T).
\]

At exactly \(T\), a nonterminal Prediction becomes Locked.

Journals may continue according to ordinary product rules.

Resolution and Invalidation remain possible after the Deadline.

Expected Resolution remains separate optional editable metadata with no scoring effect.

---

## 13. Effective Resolution Time

Let:

\[
R
\]

be `effective_resolution_at`.

It is:

> The earliest defensible timestamp at which the numerical outcome became fixed and ascertainable under the Resolution Criteria and source of truth.

Let `recorded_at` be the immutable timestamp at which the user entered the Resolution.

These must remain separate.

Scoring uses \(R\), not `recorded_at`.

---

## 14. Final Scoring Cutoff

Define:

\[
C=\min(R,T).
\]

The final scoring revision is:

> The latest valid v0.7.0 Numeric ForecastRevision whose immutable commit timestamp is strictly earlier than \(C\).

### 14.1 Resolution before Deadline

If \(R<T\), the last revision before \(R\) is final.

There is no Numeric neutral truncation and no post-resolution Numeric scoring contribution.

### 14.2 Resolution after Deadline

If \(R\ge T\), the last revision before \(T\) is final.

No post-Deadline waiting time enters Numeric scoring.

### 14.3 Revision committed after effective resolution but before recorded resolution

The application may not know \(R\) until later.

If a revision was committed after the outcome had already become effectively resolved, that revision remains immutable audit history but is excluded from scoring.

For scoring:

\[
t_{revision}\ge C
\]

is never eligible.

### 14.4 Immediate resolution boundary

If:

\[
R\le t_0
\]

the record is not a meaningful scored forecast under the v0.7.0 contract and should not produce WIS or calibration observations.

---

## 15. Outcome Contract

A resolved Numeric Prediction has one finite exact value:

\[
y\in\mathbb R
\]

subject to the Prediction's value-type and precision constraints.

Allowed values include positive values, zero, negative values, integers, and exact decimals.

Do not allow NaN, positive infinity, negative infinity, or textual pseudo-values such as `unknown`.

If the factual outcome cannot validly be determined, use Invalid rather than a nonnumeric sentinel.

---

## 16. Quantile Ordering Validation

Every v0.7.0 Numeric revision must satisfy:

\[
\boxed{q_5\le q_{25}\le q_{50}\le q_{75}\le q_{95}}.
\]

Equality is valid.

Strict inequality is not required.

### 16.1 Never silently sort

If the user enters crossed quantiles, Reckonsolve must reject the revision.

It must not reorder values automatically.

The quantile labels have semantic meaning; sorting would change the user's statements.

### 16.2 Zero-width intervals

Zero-width 50% or 90% intervals are valid if the ordering constraint holds.

WIS handles them without special scoring logic.

Do not impose a minimum width.

---

## 17. Canonical Numeric Scoring Rule

The canonical v0.7.0 Numeric score is **Weighted Interval Score (WIS)** using:

- The median \(q_{50}\)
- The 50% central interval \([q_{25},q_{75}]\)
- The 90% central interval \([q_5,q_{95}]\)

Lower is better.

The formula follows the standard WIS weighting for central prediction intervals.

---

## 18. Interval Score Definitions

For a central \((1-\alpha)\) interval \([L,U]\) and realized value \(y\):

\[
IS_\alpha(L,U;y)
=
(U-L)
+
\frac{2}{\alpha}(L-y)\mathbf 1[y<L]
+
\frac{2}{\alpha}(y-U)\mathbf 1[y>U].
\]

Interval endpoints count as contained.

### 18.1 50% interval score

For \(\alpha_{50}=0.50\):

\[
IS_{50}
=
(q_{75}-q_{25})
+4(q_{25}-y)\mathbf 1[y<q_{25}]
+4(y-q_{75})\mathbf 1[y>q_{75}].
\]

### 18.2 90% interval score

For \(\alpha_{90}=0.10\):

\[
IS_{90}
=
(q_{95}-q_5)
+20(q_5-y)\mathbf 1[y<q_5]
+20(y-q_{95})\mathbf 1[y>q_{95}].
\]

---

## 19. WIS Formula

For the fixed v0.7.0 five-quantile model:

\[
\boxed{
WIS
=
\frac{
0.5|y-q_{50}|
+0.25IS_{50}
+0.05IS_{90}
}{2.5}
}.
\]

The fixed weights are:

- Median weight \(w_0=0.5\)
- 50% interval weight \(w_{50}=0.50/2=0.25\)
- 90% interval weight \(w_{90}=0.10/2=0.05\)
- \(K=2\), giving denominator \(K+0.5=2.5\)

Lower is better.

\[
WIS\ge0.
\]

There is no finite upper bound.

---

## 20. Equivalent Five-Quantile Interpretation

Under the standard quantile-score convention:

\[
QS_\tau(q,y)=
\begin{cases}
2(1-\tau)(q-y), & y\le q\\
2\tau(y-q), & y>q
\end{cases}
\]

then:

\[
\boxed{
WIS
=
\frac{
QS_{0.05}+QS_{0.25}+QS_{0.50}+QS_{0.75}+QS_{0.95}
}{5}
}.
\]

This interpretation is important for Reckonsolve.

The canonical score evaluates the five quantiles the user actually supplied.

It does **not** score the interpolated visualization.

Changing the interpolation method later must not change historical WIS.

---

## 21. Score Unit and Scale

WIS retains the unit and numerical scale of the target.

Examples:

- USD forecast → WIS in USD
- Day forecast → WIS in days
- kg forecast → WIS in kg

WIS is not a universal 0-to-1 skill scale.

A WIS of 100 on a lunch-cost forecast and 100 on a car-repair forecast do not carry the same practical meaning even though both may use USD.

### 21.1 Prohibited aggregate

v0.7.0 must not publish a global metric such as **Overall Numeric WIS** by averaging raw WIS across heterogeneous Numeric predictions.

Grouping only by unit is not sufficient to make arbitrary raw WIS values comparable.

A future normalized or reference-relative skill score requires a separate design.

---

## 22. Canonical Per-Prediction Score Components

For one resolved eligible Prediction, Reckonsolve should derive at least:

- WIS
- Realized value \(y\)
- Median absolute error \(|y-q_{50}|\)
- 50% interval width \(q_{75}-q_{25}\)
- 50% containment
- 50% miss direction and miss distance if outside
- \(IS_{50}\)
- Weighted 50% contribution
- 90% interval width \(q_{95}-q_5\)
- 90% containment
- 90% miss direction and miss distance if outside
- \(IS_{90}\)
- Weighted 90% contribution

These should be derived from immutable forecast and resolution facts.

They need not all be persisted as canonical database facts.

---

## 23. WIS Decomposition

The WIS implementation should preserve enough derived information to support decomposition into:

- Dispersion/sharpness contribution
- Underprediction penalty
- Overprediction penalty

This need not dominate the v0.7.0 UI, but the analytics/domain layer should make the decomposition available for future diagnostics.

---

## 24. Initial and Final WIS

For a resolved eligible v0.7.0 Numeric Prediction:

### 24.1 Initial WIS

Score the sequence-one revision against \(y\):

\[
WIS_{initial}.
\]

### 24.2 Final WIS

Score the final scoring revision selected under Section 14:

\[
WIS_{final}.
\]

### 24.3 Initial-to-final improvement

Define:

\[
\boxed{\Delta WIS=WIS_{initial}-WIS_{final}}.
\]

Interpretation:

- Positive → final forecast mechanically scored better
- Zero → no change in WIS
- Negative → final forecast mechanically scored worse

This is an outcome-relative descriptive comparison.

The UI and documentation must not claim that updating **caused** the improvement.

### 24.4 No Numeric Updating Gain counterfactual in v0.7.0

Do not reuse the Binary `Updating Gain` name or hold-initial trajectory counterfactual.

Numeric trajectory scoring has not been designed.

---

## 25. Cross-Prediction Updating Summary

Raw \(\Delta WIS\) values must not be averaged across heterogeneous targets.

A scale-free descriptive summary may count signs:

- Number of revised + resolved eligible Numeric predictions
- Number with \(WIS_{final}<WIS_{initial}\)
- Number with equality
- Number with \(WIS_{final}>WIS_{initial}\)

The UI may report the fraction of revised Numeric forecasts that finished with lower WIS than their initial forecast.

This loses magnitude and must not be presented as a universal skill score.

---

## 26. Global Numeric Calibration Dataset

Every eligible resolved v0.7.0 Numeric Prediction contributes exactly **one** calibration observation.

Use the final scoring revision only.

Do not treat every revision, Forecast Review, Journal entry, or interpolated CDF point as an independent calibration observation.

Invalid Predictions contribute none.

Legacy interval-v1 Numeric Predictions contribute none to v0.7.0 five-quantile calibration.

---

## 27. Quantile Calibration for Effectively Continuous Targets

For each quantile level:

\[
\tau\in\{0.05,0.25,0.50,0.75,0.95\}
\]

define:

\[
\hat F_\tau
=
\frac{1}{N}\sum_{j=1}^{N}\mathbf 1[y_j\le q_{\tau,j}].
\]

With negligible ties, calibrated forecasts should approximately satisfy:

\[
\hat F_\tau\approx\tau.
\]

The primary visualization should plot nominal quantile level against observed frequency with the perfect-calibration diagonal.

Do not invent 10%, 20%, 30%, ..., 90% Numeric calibration buckets.

---

## 28. Discrete-Aware Quantile Calibration

For whole-number targets, equality with a quantile may have non-negligible probability.

Exact calibration therefore must not assume:

\[
P(Y\le q_\tau)=\tau.
\]

For each \(\tau\), compute:

\[
\hat F_\tau^-=
\frac{1}{N}\sum_{j=1}^{N}\mathbf 1[y_j<q_{\tau,j}]
\]

and:

\[
\hat F_\tau=
\frac{1}{N}\sum_{j=1}^{N}\mathbf 1[y_j\le q_{\tau,j}].
\]

A calibrated discrete quantile is compatible with:

\[
\boxed{\hat F_\tau^-\lesssim\tau\lesssim\hat F_\tau}
\]

allowing sampling variation.

The UI may visualize the interval between empirical `< q` and `≤ q` frequencies as a tie band around each nominal quantile level.

Do not force whole-number forecasts into the continuous diagonal test.

---

## 29. Central-Interval Calibration

### 29.1 Continuous-style 50% interval

Report:

- Fraction below \(q_{25}\)
- Fraction inside \([q_{25},q_{75}]\)
- Fraction above \(q_{75}\)

Targets are approximately:

\[
25\%,50\%,25\%.
\]

### 29.2 Continuous-style 90% interval

Report:

- Fraction below \(q_5\)
- Fraction inside \([q_5,q_{95}]\)
- Fraction above \(q_{95}\)

Targets are approximately:

\[
5\%,90\%,5\%.
\]

### 29.3 Whole-number interval interpretation

For discrete targets, endpoint mass may increase closed-interval coverage.

For the 50% interval:

\[
P(Y<q_{25})\le0.25,
\]

\[
P(Y>q_{75})\le0.25,
\]

so:

\[
P(q_{25}\le Y\le q_{75})\ge0.50.
\]

For the 90% interval:

\[
P(Y<q_5)\le0.05,
\]

\[
P(Y>q_{95})\le0.05,
\]

so:

\[
P(q_5\le Y\le q_{95})\ge0.90.
\]

Do not label a whole-number forecast miscalibrated merely because closed-interval containment exceeds the nominal percentage.

---

## 30. Median Balance

For effectively continuous targets, the median diagnostic may show fraction below median and fraction above median with an approximate 50% / 50% target.

For whole-number targets, retain equality:

- Below \(q_{50}\)
- Equal to \(q_{50}\)
- Above \(q_{50}\)

The valid discrete median condition is compatible with:

\[
P(Y<q_{50})\le0.50
\]

and:

\[
P(Y\le q_{50})\ge0.50.
\]

Do not discard ties.

---

## 31. Sampling Uncertainty in Calibration

Reckonsolve is a personal forecasting system and will often have small \(N\).

The Analytics UI must always show the eligible sample size.

Do not hide calibration until an arbitrary threshold is reached.

For simple binary proportions such as interval containment, display a binomial uncertainty interval.

Wilson score intervals are the recommended v0.7.0 default because they behave reasonably at small sample sizes and near 0 or 1.

For discrete tie-band quantile calibration, show the empirical `< q` and `≤ q` bounds and sample count; do not imply a single precise observed frequency when ties are material.

---

## 32. Global Numeric Analytics UX

The main v0.7.0 Numeric Analytics surface should be **calibration-first**.

Recommended first-class elements:

1. Five-level quantile calibration plot
2. 50% interval below / inside / above summary
3. 90% interval below / inside / above summary
4. Median balance
5. Eligible resolved sample size
6. Sampling-uncertainty display
7. Optional revised-and-resolved sign summary for initial versus final WIS

Do not make global raw WIS the centerpiece.

Do not display a single opaque **Numeric skill score**.

---

## 33. Individual Resolved Prediction UX

A resolved eligible Numeric Prediction should show approximately:

```text
Resolved: $900

WIS
$166
Lower is better

Median
$700
Absolute error: $200

50% interval
$500 – $1,200
Outcome: inside
Width: $700

90% interval
$200 – $3,000
Outcome: inside
Width: $2,800
```

Use neutral probabilistic language.

Do not label an interval miss simply **Wrong**.

A valid 90% interval should miss occasionally.

---

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

---

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

---

## 36. Revision UX

When revising:

- Prepopulate all five current quantiles
- Allow editing any subset
- Commit one complete immutable replacement revision
- Preserve rationale
- Reject unchanged five-quantile revisions
- Use Forecast Review to retain the current distribution

The user should not need to reconstruct all five values from memory.

---

## 37. Implied Distribution Visualization

The five quantiles are authoritative forecast data.

The visual curve is derived presentation logic.

### 37.1 Continuous distinct-quantile case

If adjacent quantiles have distinct numerical values, use piecewise-linear interpolation in CDF space between the elicited probability levels.

For adjacent points \((q_a,a)\) and \((q_b,b)\) with \(q_a<q_b\), define:

\[
F_{impl}(x)
=
a+(b-a)\frac{x-q_a}{q_b-q_a}
\]

for:

\[
q_a\le x\le q_b.
\]

### 37.2 Repeated quantiles

If:

\[
q_a=q_b
\]

for two or more adjacent quantile levels, do not divide by zero and do not pretend the CDF equals several probabilities at one point.

Render the repeated quantile as a vertical jump spanning the relevant cumulative-probability levels.

This represents point-mass/discrete concentration implied by repeated inverse-CDF anchors.

### 37.3 Anchor styling

The UI should visually distinguish:

- User-elicited quantile anchors
- Software-interpolated segments

Tooltips or labels may identify **Elicited 75th percentile** versus **Interpolated cumulative probability**.

---

## 38. Outer Tails

The user supplies \(q_5\) and \(q_{95}\), but not the shape of probability below and above them.

v0.7.0 must not invent complete outer-tail distributions.

For effectively continuous targets, the visualization may annotate approximately:

- 5% probability below \(q_5\)
- 5% probability above \(q_{95}\)

For discrete targets, use quantile-aware wording because endpoint mass can alter strict-tail probability.

Do not:

- Fit arbitrary exponential tails
- Fit a normal/lognormal distribution solely to complete the graph
- Infer hard minimum or maximum values
- Produce a normalized full PDF that implies unsupported tail shape

---

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

---

## 40. Interpolation Must Not Affect Scoring

WIS and calibration use the elicited quantiles directly.

They do not use interpolated CDF values.

Therefore:

\[
\boxed{\text{forecast/scoring semantics}\neq\text{visual interpolation semantics}}.
\]

A later visualization improvement must not alter historical WIS or the meaning of stored forecasts.

---

## 41. Resolution UX

Resolution should collect:

- Exact actual value
- Effective resolution time
- Optional Resolution Notes
- Optional Postmortem

The Prediction's unit and precision remain fixed.

The UI should separately preserve the automatic `recorded_at` timestamp.

If an objective source provides an exact time, the user should enter or confirm that time.

---

## 42. Resolution Corrections

Terminal corrections remain append-only and audited.

If the effective actual value changes:

- Preserve original Resolution facts
- Preserve correction history
- Recompute WIS
- Recompute Initial WIS
- Recompute Final WIS
- Recompute calibration contributions

If effective resolution time changes:

- Preserve correction history
- Re-evaluate which Numeric ForecastRevision is the final scoring revision
- Recompute all affected scoring and analytics

A correction must never rewrite historical forecast revisions.

---

## 43. Invalid Predictions

Invalid v0.7.0 Numeric Predictions contribute no:

- WIS
- Initial/final improvement observation
- Quantile calibration observation
- Interval coverage observation
- Median-balance observation

Their complete historical record remains preserved.

Material intervention-policy breach continues to use the Rulebook's Invalid semantics.

---

## 44. Legacy Numeric Model

The v0.6.0 Numeric model is a different forecast contract.

Conceptually:

\[
\text{interval-v1}=(L,M,U,c)
\]

where \(c\) is a user-selected confidence percentage.

The v0.7.0 model is:

\[
\text{quantiles-5-v2}=(q_5,q_{25},q_{50},q_{75},q_{95}).
\]

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

An old 90% interval may imply \(q_5\), \(q_{50}\), and \(q_{95}\), but it does not provide \(q_{25}\) or \(q_{75}\).

An old 80% interval provides different outer quantiles entirely.

Never synthesize quartiles by interpolation, parametric fitting, or midpoint assumptions.

### 44.4 No mixed scoring

Legacy interval scores and v0.7.0 WIS must not be averaged or presented as one common score.

Legacy forecasts do not enter v0.7.0 five-quantile calibration analytics.

---

## 45. Legacy Transition Convenience

A convenience action may eventually offer:

> Create new v2 prediction from this definition

It may copy non-forecast definition data such as question, background, Resolution Criteria, unit, precision, and tags.

It must not copy or infer five forecast quantiles from a legacy interval.

The user must explicitly enter the new v2 forecast.

This convenience is optional and not required for v0.7.0 completion.

---

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

---

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

---

## 48. Persistence Architecture

The v0.6.0 repository currently stores legacy revisions in a `numeric_forecast_revisions` shape containing lower, median, upper, confidence percentage, sequence, created-at, and rationale.

Those fields have legacy meaning and should continue to mean exactly that.

Do not repurpose legacy lower/upper fields as \(q_5\)/\(q_{95}\) and then bolt quartiles onto the old schema.

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

---

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

---

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

---

## 51. Numeric Trajectory Scoring Is Deliberately Deferred

v0.7.0 preserves exact Numeric revision timestamps and the immutable Forecast Deadline so future Numeric trajectory scoring remains possible.

However, v0.7.0 must not invent a trajectory formula merely for symmetry with Binary.

There is no universally natural Numeric analogue of Binary's outcome-independent neutral Brier constant:

\[
0.25.
\]

WIS depends on unit and scale, so there is no universal neutral post-resolution loss.

Until a separate accepted design exists:

- Preserve the trajectory data
- Score the final valid revision
- Compare initial versus final within the same Prediction
- Do not publish a metric labeled Numeric trajectory score

---

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

---

## 53. Analytics Cohort Eligibility

A resolved Numeric Prediction enters the canonical v0.7.0 Numeric analytics cohort only if:

- It uses `quantiles-5-v2`
- It has a valid final scoring revision before \(C=\min(R,T)\)
- It has a valid finite realized value
- It is Resolved rather than Invalid
- Its scoring contract is recognized as eligible

Each eligible Prediction contributes one Prediction-level observation.

No duration-based aggregate weight is used.

---

## 54. Implementation Invariants

Codex should treat the following as hard invariants unless a later accepted design explicitly supersedes them:

- Every new v0.7.0 Numeric Prediction uses exactly \(q_5,q_{25},q_{50},q_{75},q_{95}\)
- Newly created Numeric predictions do not expose the legacy confidence selector
- A Numeric model is fixed for a Prediction's lifetime
- Existing pre-v0.7 Numeric predictions remain legacy interval-v1
- Every v2 revision is complete and immutable
- Quantiles satisfy \(q_5\le q_{25}\le q_{50}\le q_{75}\le q_{95}\)
- Equal quantiles are allowed
- Crossed quantiles are rejected and never auto-sorted
- Numeric values preserve exact fixed-precision semantics
- Unit and scoring-critical quantity definition do not change after commitment
- Every new v2 Prediction has one mandatory immutable exact Forecast Deadline
- Expected Resolution has no scoring effect
- Forecast revisions cannot be user-backdated
- Revisions and Reviews are rejected at or after Forecast Deadline
- `effective_resolution_at` is distinct from `recorded_at`
- The final scoring revision is the latest valid revision strictly before \(\min(R,T)\)
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

---

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
- \(\Delta WIS=WIS_{initial}-WIS_{final}\)
- Positive and negative sign interpretation is correct
- Raw \(\Delta WIS\) is not averaged across heterogeneous targets

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

---

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
10. Implement final-scoring-revision selection using \(\min(R,T)\)
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

---

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

---

## 58. Relationship to Binary Trajectory Scoring

Binary and Numeric share one v0.7.0 forecasting lifecycle but do not share one scoring rule.

Binary:

\[
\text{standing probabilities through time}
\rightarrow
\text{Trajectory Brier}
\]

Numeric:

\[
\text{five-quantile final standing distribution}
\rightarrow
\text{WIS}
\]

Binary early-resolution neutral truncation is intentionally Binary-specific.

Numeric v0.7.0 has no trajectory score.

Do not import Binary's neutral constant, temporal averaging, Active Forecast Fraction, Hold-Initial counterfactual, or Updating Gain into Numeric merely for symmetry.

---

## 59. Summary Contract

The intended v0.7.0 Numeric contract is:

> Every new Numeric Prediction forecasts one precisely defined scalar quantity in one immutable unit using five quantiles: the 5th, 25th, 50th, 75th, and 95th percentiles. The user interface presents these as a 90% central interval, a median, and a 50% central interval, with no confidence selector and no legacy-model choice. Every committed revision is a complete immutable five-quantile statement. Quantiles may be equal but may not cross. The Prediction has a mandatory immutable exact Forecast Deadline and uses a separate effective resolution timestamp. The final scoring revision is the latest valid revision strictly before the earlier of effective resolution and the Forecast Deadline. Resolved v2 forecasts receive standard five-quantile WIS using the median, 50% interval, and 90% interval. WIS scores only the elicited quantiles, retains target unit and scale, and is not globally averaged across heterogeneous personal Numeric questions. Global Numeric analytics are calibration-first: five quantile levels, 50% and 90% interval behavior, median balance, sample size, and sampling uncertainty, with discrete-aware tie semantics for whole-number outcomes. The implied central CDF uses transparent piecewise-linear interpolation between distinct quantiles, vertical jumps for repeated quantiles, and no invented outer-tail shape. Legacy user-selected-confidence Numeric predictions remain a hard separate cohort for their entire lifetime and are never silently converted, rescored, or mixed with the v2 calibration record. Numeric trajectory scoring is deliberately deferred beyond v0.7.0.
