# Numeric scoring

This maintained reference explains the five-quantile forecast, exact Weighted Interval Score (WIS), calibration, and the limits of implied-distribution charts. The [product specification](../../product-spec.md#35-adaptive-forecasting-contract) governs Adaptive behavior and its [One-Shot contract](../../product-spec.md#36-one-shot-prediction-contract) governs One-Shot. Storage and transactions are described in [architecture](../../architecture.md).

For practical interpretation and worked scores, read [the user guide](../../guides/user-guide.md#8-numeric-scores-and-updating-what-you-can-compare). Question admissibility and eliciting quantiles belong in [the forecasting guide](../../guides/forecasting-guide.md).

| Mode | Distribution scored | Time affects selection? |
| --- | --- | --- |
| Adaptive | The last complete revision strictly before the scoring cutoff. | Yes: exact effective resolution time and immutable Deadline determine the cutoff. |
| One-Shot | One effective forecast after transcription corrections. | No: reported times and app-entry times never select or weight it. |

Both modes use the same five quantiles and WIS formula. Neither has Numeric trajectory scoring or neutral truncation. Modes never share score or calibration denominators, and raw WIS is never pooled across Predictions.

## One-Shot selection and corrections

One-Shot scores one final five-quantile guess settled before checking an existing answer. It may be entered with its answer or answered later. There is no Deadline, ordinary revision/Review, scoring cutoff, Initial/Final/Delta WIS, or updating direction.

Use the effective quantiles and actual value after replaying complete transcription snapshots. A forecast correction made before a later first answer does not erase that later answer. Originals, the original answer, corrections, and app timestamps remain inspectable. Optional reported forecast/reveal wall times are documentary and never gate or alter WIS, including when missing, approximate, or equal to the minute.

An answered, non-Invalid Prediction contributes exactly one observation. Corrections change that observation's effective values rather than adding another. Changing the target, unit, source, or answer convention is not a transcription repair; preserve the original meaning or use Invalid/new-Prediction guidance.

## Core Forecast Model

Every Numeric Prediction uses exactly five quantiles:

$$
\boxed{q_5,\ q_{25},\ q_{50},\ q_{75},\ q_{95}}
$$

where $q_\tau$ denotes the forecasted $\tau$-quantile of the target quantity.

The user-facing representation is:

- **90% central interval:** $[q_5,q_{95}]$
- **Median:** $q_{50}$
- **50% central interval:** $[q_{25},q_{75}]$

There is no confidence selector.

Both Adaptive and One-Shot use this fixed representation.

> Numeric means the five-quantile model.

## Quantile Semantics

### Quantiles are inverse-CDF statements

The durable semantic statement is:

$$
Q(\tau)=q_\tau
$$

for:

$$
\tau\in\{0.05,0.25,0.50,0.75,0.95\}.
$$

For an effectively continuous distribution with distinct quantiles, it is natural to visualize these as CDF anchors:

$$
F(q_\tau)=\tau.
$$

That equality must not be treated as universally exact.

For discrete outcomes or repeated quantiles, a valid $\tau$-quantile satisfies:

$$
P(Y<q_\tau)\le\tau\le P(Y\le q_\tau).
$$

This distinction is required for correct tie handling and calibration analytics.

### Central 50% interval

For an effectively continuous quantity:

$$
[q_{25},q_{75}]
$$

corresponds approximately to:

- 25% probability below $q_{25}$
- 50% probability inside the closed interval
- 25% probability above $q_{75}$

For a discrete quantity, endpoint probability mass may make closed-interval coverage exceed 50%.

### Central 90% interval

For an effectively continuous quantity:

$$
[q_5,q_{95}]
$$

corresponds approximately to:

- 5% probability below $q_5$
- 90% probability inside the closed interval
- 5% probability above $q_{95}$

For a discrete quantity, endpoint probability mass may make closed-interval coverage exceed 90%.

### Median

The median is:

$$
q_{50}.
$$

It is a probability balance point.

It need not equal the mean, mode, or geometric midpoint of either interval.

Skewed forecasts are valid.

## Numeric Target Contract

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

## Resolution Criteria and Scoring-Critical Definition

Resolution Criteria should define the target quantity before the initial forecast is committed.

Adaptive offers an optional Resolution Criteria field. One-Shot encourages recording context and the checking method in optional Background; it does not require a separate criteria field or boilerplate prose. The underlying quantity and checking convention should still be clear before looking at the answer.

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

### Clarification versus redefinition

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

## Unit and Precision Contract

### Unit is required

Every new Numeric Prediction must have one required nonblank unit.

Examples include USD, days, hours, °F, kg, and people.

### Unit is immutable after initial commitment

Once the initial forecast is committed, unit is part of the scoring contract.

It must not be edited.

Changing from dollars to cents, days to hours, or any other scale transformation changes the numerical score and historical meaning.

### Preserve exact fixed precision

`FixedPrecisionValue` represents each quantity as a signed scaled integer plus the Prediction's fixed decimal precision, with no float-based domain input.

User-entered forecasts and actual values retain that exact base-ten representation rather than binary floating-point approximations.

All five quantiles and the realized outcome must use the Prediction's declared precision.

### Display precision is not scoring rounding

Scoring uses exact stored values.

UI formatting must not round values before scoring.

## Value-Type Constraint

Numeric supports two fixed value constraints:

- **Decimal/continuous-style**
- **Whole-number**

This is not a separate forecast type.

Both use the same five-quantile model and WIS.

For whole-number Predictions:

- Forecast quantiles must satisfy the whole-number constraint
- Resolution value must satisfy the whole-number constraint
- Repeated quantiles are expected and valid
- Calibration analytics must use discrete-aware tie semantics

A discrete PMF editor is not supported.

## Adaptive forecast revisions

An Adaptive Numeric ForecastRevision is one immutable complete five-quantile statement.

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

Persistence records one complete immutable forecast; see [architecture](../../architecture.md) for its physical layout.

### Complete revisions

Every committed revision contains all five quantiles.

If only $q_{95}$ changes, the new revision still records the complete five-quantile distribution that now stands.

### Atomic initial creation

The Prediction and its sequence-one Numeric ForecastRevision must be created atomically.

There must be no period in which a scored Numeric Prediction exists without a standing complete forecast.

### Immutable timestamps

A revision becomes effective at its system-generated commit time. Commit instants are strictly increasing and before the Deadline. A regressed clock rejects a save rather than inventing elapsed time.

Users must not backdate or forward-date forecast revisions.

### No-change revisions

A normal revision that repeats all five current quantile values is rejected as unchanged.

Use Forecast Review for deliberate reconsideration that retains the forecast.

## Adaptive Reviews and Journals

A Numeric Forecast Review means:

> I deliberately reconsidered the current five-quantile forecast and retained it.

A Review:

- Does not create a NumericForecastRevision
- Does not change WIS
- Does not change the final scoring revision
- Does not create a calibration observation
- Has no time-weighted scoring effect

Journal entries and corrections likewise do not alter the standing forecast.

Review wording refers to the current forecast or distribution. One-Shot has no Forecast Review; its Journals likewise never change the forecast or score.

## Adaptive Forecast Deadline

Every Adaptive Numeric Prediction has one mandatory Forecast Deadline. One-Shot has none.

Let $t_0$ be the immutable system-generated commit instant of the sequence-one forecast.

Let:

$$
T
$$

be that timestamp.

The Forecast Deadline is:

- Chosen atomically with the initial forecast
- Stored as an exact timezone-aware instant
- Strictly later than initial forecast time
- Immutable after commitment
- The last permissible instant for revisions and Reviews

Forecasting is allowed on:

$$
[t_0,T).
$$

At exactly $T$, a nonterminal Prediction becomes Locked.

Journals may continue according to ordinary product rules.

Resolution and Invalidation remain possible after the Deadline.

Expected Resolution remains separate optional editable metadata with no scoring effect.

## Adaptive effective resolution time

Let:

$$
R
$$

be `effective_resolution_at`.

It is:

> The earliest defensible timestamp at which the numerical outcome became fixed and ascertainable under the Resolution Criteria and source of truth.

Let `recorded_at` be the immutable timestamp at which the user entered the Resolution.

These remain separate, and effective $R$ cannot exceed original `recorded_at`, including after correction.

Scoring uses $R$, not `recorded_at`.

## Adaptive final scoring cutoff

Define:

$$
C=\min(R,T).
$$

The final scoring revision is:

> The latest valid Numeric ForecastRevision whose immutable commit timestamp is strictly earlier than $C$.

### Resolution before Deadline

If $R<T$, the last revision before $R$ is final.

There is no Numeric neutral truncation and no post-resolution Numeric scoring contribution.

### Resolution after Deadline

If $R\ge T$, the last revision before $T$ is final.

No post-Deadline waiting time enters Numeric scoring.

### Revision committed after effective resolution but before recorded resolution

The application may not know $R$ until later.

If a revision was committed after the outcome had already become effectively resolved, that revision remains immutable audit history but is excluded from scoring.

For scoring:

$$
t_{\text{revision}}\ge C
$$

is never eligible.

### Immediate resolution boundary

If:

$$
R\le t_0
$$

the record is not a meaningful scored forecast under the Adaptive contract and produces neither WIS nor calibration observations. This exclusion does not apply to One-Shot, whose answer may already exist before the guess.

## Outcome Contract

A resolved Numeric Prediction has one finite exact value:

$$
y\in\mathbb R
$$

subject to the Prediction's value-type and precision constraints.

Allowed values include positive values, zero, negative values, integers, and exact decimals.

Do not allow NaN, positive infinity, negative infinity, or textual pseudo-values such as `unknown`.

If the factual outcome cannot validly be determined, use Invalid rather than a nonnumeric sentinel.

## Quantile Ordering Validation

Every Numeric forecast and transcription correction must satisfy:

$$
\boxed{q_5\le q_{25}\le q_{50}\le q_{75}\le q_{95}}.
$$

Equality is valid.

Strict inequality is not required.

### Never silently sort

If the user enters crossed quantiles, Reckonsolve must reject the revision.

It must not reorder values automatically.

The quantile labels have semantic meaning; sorting would change the user's statements.

### Zero-width intervals

Zero-width 50% or 90% intervals are valid if the ordering constraint holds.

WIS handles them without special scoring logic.

Do not impose a minimum width.

## Canonical Numeric Scoring Rule

The canonical Numeric score is **Weighted Interval Score (WIS)** using:

- The median $q_{50}$
- The 50% central interval $[q_{25},q_{75}]$
- The 90% central interval $[q_5,q_{95}]$

Lower is better.

The formula follows the standard WIS weighting for central prediction intervals.

## Interval Score Definitions

For a central $(1-\alpha)$ interval $[L,U]$ and realized value $y$:

$$
\operatorname{IS}_\alpha(L,U;y)
=
(U-L)
+
\frac{2}{\alpha}(L-y)\mathbf 1[y<L]
+
\frac{2}{\alpha}(y-U)\mathbf 1[y>U].
$$

Interval endpoints count as contained.

### 50% interval score

For $\alpha_{50}=0.50$:

$$
\operatorname{IS}_{50}
=
(q_{75}-q_{25})
+4(q_{25}-y)\mathbf 1[y<q_{25}]
+4(y-q_{75})\mathbf 1[y>q_{75}].
$$

### 90% interval score

For $\alpha_{90}=0.10$:

$$
\operatorname{IS}_{90}
=
(q_{95}-q_5)
+20(q_5-y)\mathbf 1[y<q_5]
+20(y-q_{95})\mathbf 1[y>q_{95}].
$$

## WIS Formula

For the fixed five-quantile model used by both modes:

$$
\boxed{
\operatorname{WIS}
=
\frac{
0.5|y-q_{50}|
+0.25\operatorname{IS}_{50}
+0.05\operatorname{IS}_{90}
}{2.5}
}.
$$

The fixed weights are:

- Median weight $w_0=0.5$
- 50% interval weight $w_{50}=0.50/2=0.25$
- 90% interval weight $w_{90}=0.10/2=0.05$
- $K=2$, giving denominator $K+0.5=2.5$

Lower is better.

$$
\operatorname{WIS}\ge0.
$$

There is no finite upper bound.

## Equivalent Five-Quantile Interpretation

Under the standard quantile-score convention:

$$
\operatorname{QS}_\tau(q,y)=
\begin{cases}
2(1-\tau)(q-y), & y\le q\\
2\tau(y-q), & y>q
\end{cases}
$$

then:

$$
\boxed{
\operatorname{WIS}
=
\frac{
\operatorname{QS}_{0.05}+\operatorname{QS}_{0.25}+\operatorname{QS}_{0.50}+\operatorname{QS}_{0.75}+\operatorname{QS}_{0.95}
}{5}
}.
$$

This interpretation is important for Reckonsolve.

The canonical score evaluates the five quantiles the user actually supplied.

It does **not** score the interpolated visualization.

Changing the interpolation method later must not change historical WIS.

## Score Unit and Scale

WIS retains the unit and numerical scale of the target.

Examples:

- USD forecast → WIS in USD
- Day forecast → WIS in days
- kg forecast → WIS in kg

WIS is not a universal 0-to-1 skill scale.

A WIS of 100 on a lunch-cost forecast and 100 on a car-repair forecast do not carry the same practical meaning even though both may use USD.

### Prohibited aggregate

Reckonsolve does not average raw WIS across Numeric Predictions, even when unit labels match.

Grouping only by unit is not sufficient to make arbitrary raw WIS values comparable.

A normalized or reference-relative Numeric skill score is not supported.

## Canonical Per-Prediction Score Components

For one resolved eligible Prediction, Reckonsolve derives:

- WIS
- Realized value $y$
- Median absolute error $|y-q_{50}|$
- 50% interval width $q_{75}-q_{25}$
- 50% containment
- 50% miss direction and miss distance if outside
- $\operatorname{IS}_{50}$
- Weighted 50% contribution
- 90% interval width $q_{95}-q_5$
- 90% containment
- 90% miss direction and miss distance if outside
- $\operatorname{IS}_{90}$
- Weighted 90% contribution

These are derived from the effective forecast and answer while retaining immutable originals and correction history.

Scores are reproducible derived values, not canonical database facts.

## WIS Decomposition

WIS is decomposed into:

- Dispersion/sharpness contribution
- Underprediction penalty
- Overprediction penalty

The decomposition is derived from exact scoring components; WIS remains the canonical summary.

## Adaptive initial and final WIS

For a resolved eligible Adaptive Numeric Prediction:

### Initial WIS

Score the sequence-one revision against $y$:

$$
\operatorname{WIS}_{\text{initial}}.
$$

### Final WIS

Score the revision selected by the [Adaptive cutoff](#adaptive-final-scoring-cutoff):

$$
\operatorname{WIS}_{\text{final}}.
$$

### Initial-to-final improvement

Define:

$$
\boxed{\Delta \operatorname{WIS}=\operatorname{WIS}_{\text{initial}}-\operatorname{WIS}_{\text{final}}}.
$$

Interpretation:

- Positive → final forecast mechanically scored better
- Zero → no change in WIS
- Negative → final forecast mechanically scored worse

This is an outcome-relative descriptive comparison.

The UI and documentation must not claim that updating **caused** the improvement.

### No Numeric Updating Gain counterfactual

Do not reuse the Binary `Updating Gain` name or hold-initial trajectory counterfactual.

Numeric has no supported trajectory score or hold-initial time-weighted counterfactual.

## Adaptive cross-Prediction updating summary

Raw $\Delta \operatorname{WIS}$ values must not be averaged across heterogeneous targets.

A scale-free descriptive summary may count signs:

- Number of revised + resolved eligible Numeric predictions
- Number with $\operatorname{WIS}_{\text{final}}<\operatorname{WIS}_{\text{initial}}$
- Number with equality
- Number with $\operatorname{WIS}_{\text{final}}>\operatorname{WIS}_{\text{initial}}$

The UI may report the fraction of revised Numeric forecasts that finished with lower WIS than their initial forecast.

This loses magnitude and must not be presented as a universal skill score.

## Global Numeric Calibration Dataset

Every eligible answered Numeric Prediction contributes exactly **one** calibration observation within its mode and value constraint.

Adaptive uses the final eligible scoring revision; One-Shot uses the effective single forecast.

Do not treat every revision, Forecast Review, Journal entry, or interpolated CDF point as an independent calibration observation.

Invalid Predictions contribute none.

Unanswered Predictions contribute none. Mode, exact-unit, tag, and continuous-style/whole-number filters retain their separate populations.

## Quantile Calibration for Effectively Continuous Targets

For each quantile level:

$$
\tau\in\{0.05,0.25,0.50,0.75,0.95\}
$$

define:

$$
\hat F_\tau
=
\frac{1}{N}\sum_{j=1}^{N}\mathbf 1[y_j\le q_{\tau,j}].
$$

With negligible ties, calibrated forecasts should approximately satisfy:

$$
\hat F_\tau\approx\tau.
$$

The primary visualization should plot nominal quantile level against observed frequency with the perfect-calibration diagonal.

Do not invent 10%, 20%, 30%, ..., 90% Numeric calibration buckets.

## Discrete-Aware Quantile Calibration

For whole-number targets, equality with a quantile may have non-negligible probability.

Exact calibration therefore must not assume:

$$
P(Y\le q_\tau)=\tau.
$$

For each $\tau$, compute:

$$
\hat F_\tau^-=
\frac{1}{N}\sum_{j=1}^{N}\mathbf 1[y_j<q_{\tau,j}]
$$

and:

$$
\hat F_\tau=
\frac{1}{N}\sum_{j=1}^{N}\mathbf 1[y_j\le q_{\tau,j}].
$$

A calibrated discrete quantile is compatible with:

$$
\boxed{\hat F_\tau^-\lesssim\tau\lesssim\hat F_\tau}
$$

allowing sampling variation.

The UI may visualize the interval between empirical `< q` and `≤ q` frequencies as a tie band around each nominal quantile level.

Do not force whole-number forecasts into the continuous diagonal test.

## Central-Interval Calibration

### Continuous-style 50% interval

Report:

- Fraction below $q_{25}$
- Fraction inside $[q_{25},q_{75}]$
- Fraction above $q_{75}$

Targets are approximately:

$$
25\%,50\%,25\%.
$$

### Continuous-style 90% interval

Report:

- Fraction below $q_5$
- Fraction inside $[q_5,q_{95}]$
- Fraction above $q_{95}$

Targets are approximately:

$$
5\%,90\%,5\%.
$$

### Whole-number interval interpretation

For discrete targets, endpoint mass may increase closed-interval coverage.

For the 50% interval:

$$
P(Y<q_{25})\le0.25,
$$

$$
P(Y>q_{75})\le0.25,
$$

so:

$$
P(q_{25}\le Y\le q_{75})\ge0.50.
$$

For the 90% interval:

$$
P(Y<q_5)\le0.05,
$$

$$
P(Y>q_{95})\le0.05,
$$

so:

$$
P(q_5\le Y\le q_{95})\ge0.90.
$$

Do not label a whole-number forecast miscalibrated merely because closed-interval containment exceeds the nominal percentage.

## Median Balance

For effectively continuous targets, the median diagnostic may show fraction below median and fraction above median with an approximate 50% / 50% target.

For whole-number targets, retain equality:

- Below $q_{50}$
- Equal to $q_{50}$
- Above $q_{50}$

The valid discrete median condition is compatible with:

$$
P(Y<q_{50})\le0.50
$$

and:

$$
P(Y\le q_{50})\ge0.50.
$$

Do not discard ties.

## Sampling Uncertainty in Calibration

Reckonsolve is a personal forecasting system and will often have small $N$.

The Analytics UI must always show the eligible sample size.

Do not hide calibration until an arbitrary threshold is reached.

For simple binary proportions such as interval containment, display a binomial uncertainty interval.

Displayed proportions use pointwise 95% Wilson intervals, with the formula in [Binary calibration and uncertainty](binary-scoring.md#binary-calibration-and-uncertainty). They describe uncertainty in observed frequency, not WIS. Empty groups have no invented rates or bounds.

For discrete tie-band quantile calibration, show the empirical `< q` and `≤ q` bounds and sample count; do not imply a single precise observed frequency when ties are material.

## Global Numeric Analytics UX

The Numeric Analytics surface is **calibration-first**.

The view includes:

1. Five-level quantile calibration plot
2. 50% interval below / inside / above summary
3. 90% interval below / inside / above summary
4. Median balance
5. Eligible resolved sample size
6. Sampling-uncertainty display
7. Adaptive-only revised-and-resolved sign summary for initial versus final WIS

Do not make global raw WIS the centerpiece.

Do not display a single opaque **Numeric skill score**.

## Illustrative resolved scorecard

An illustrative resolved Numeric scorecard:

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

## Implied Distribution Visualization

The five quantiles are authoritative forecast data.

The visual curve is derived presentation logic.

### Continuous distinct-quantile case

If adjacent quantiles have distinct numerical values, use piecewise-linear interpolation in CDF space between the elicited probability levels.

For adjacent points $(q_a,a)$ and $(q_b,b)$ with $q_a<q_b$, define:

$$
F_{\text{impl}}(x)
=
a+(b-a)\frac{x-q_a}{q_b-q_a}
$$

for:

$$
q_a\le x\le q_b.
$$

### Repeated quantiles

If:

$$
q_a=q_b
$$

for two or more adjacent quantile levels, do not divide by zero and do not pretend the CDF equals several probabilities at one point.

Render the repeated quantile as a vertical jump spanning the relevant cumulative-probability levels.

This represents point-mass/discrete concentration implied by repeated inverse-CDF anchors.

### Anchor styling

The UI should visually distinguish:

- User-elicited quantile anchors
- Software-interpolated segments

Tooltips or labels may identify **Elicited 75th percentile** versus **Interpolated cumulative probability**.

## Outer Tails

The user supplies $q_5$ and $q_{95}$, but not the shape of probability below and above them.

Reckonsolve does not invent complete outer-tail distributions.

For effectively continuous targets, the visualization may annotate approximately:

- 5% probability below $q_5$
- 5% probability above $q_{95}$

For discrete targets, use quantile-aware wording because endpoint mass can alter strict-tail probability.

Do not:

- Fit arbitrary exponential tails
- Fit a normal/lognormal distribution solely to complete the graph
- Infer hard minimum or maximum values
- Produce a normalized full PDF that implies unsupported tail shape

## Interpolation Must Not Affect Scoring

WIS and calibration use the elicited quantiles directly.

They do not use interpolated CDF values.

Therefore:

$$
\boxed{\text{forecast/scoring semantics}\neq\text{visual interpolation semantics}}.
$$

A later visualization improvement must not alter historical WIS or the meaning of stored forecasts.

## Corrections and reproducible scores

Terminal corrections remain append-only and audited.

For an Adaptive actual-value correction:

- Preserve original Resolution facts
- Preserve correction history
- Recompute WIS
- Recompute Initial WIS
- Recompute Final WIS
- Recompute calibration contributions

For an Adaptive effective-time correction:

- Preserve correction history
- Re-evaluate which Numeric ForecastRevision is the final scoring revision
- Recompute all affected scoring and analytics

These score-affecting Adaptive corrections require explanations. Original recorded-at and all forecast revisions remain immutable; corrected effective time cannot exceed original recorded-at. If it moves to or before initial commitment, the Prediction becomes unscored. One-Shot instead replays [transcription corrections](#one-shot-selection-and-corrections) of forecast and answer without a cutoff or updating comparison.

## Invalid Predictions

Invalid Numeric Predictions contribute no:

- WIS
- Initial/final improvement observation
- Quantile calibration observation
- Interval coverage observation
- Median-balance observation

Their complete historical record remains preserved.

Material intervention-policy breach continues to use the Rulebook's Invalid semantics.

## Why Numeric has no trajectory or neutral score

Adaptive retains exact Numeric revision history and an immutable Forecast Deadline for audit and cutoff selection.

Those time facts do not imply a Numeric trajectory formula.

There is no universally natural Numeric analogue of Binary's outcome-independent neutral Brier constant:

$$
0.25.
$$

WIS depends on unit and scale, so there is no universal neutral post-resolution loss.

For Adaptive Numeric:

- Preserve the trajectory data
- Score the final valid revision
- Compare initial versus final within the same Prediction
- Do not publish a metric labeled Numeric trajectory score

## Relationship to Binary scoring

Adaptive Binary and Numeric share exact Deadline and effective-time rules but select and combine forecasts differently.

Binary:

$$
\text{standing probabilities through time}
\rightarrow
\operatorname{Trajectory\ Brier}
$$

Numeric:

$$
\text{five-quantile final standing distribution}
\rightarrow
\operatorname{WIS}
$$

Binary early-resolution neutral truncation is intentionally Binary-specific.

Neither Numeric mode has a trajectory score. One-Shot Binary uses ordinary Brier, and One-Shot Numeric uses one WIS; neither has a time-weighted component.

Do not import Binary's neutral constant, temporal averaging, Active Forecast Fraction, Hold-Initial counterfactual, or Updating Gain into Numeric merely for symmetry.
