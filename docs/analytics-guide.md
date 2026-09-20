# Reckonsolve Analytics: A Practical User's Guide

This guide explains the v0.7 Analytics screen in plain language. You do not need
to memorize formulas. Start with the routine below; use the later sections when
a particular label or chart is confusing.

**New to Numeric forecasts?** Read Sections 6 → 7 → 8 in order. They build from
entering your five numbers, through interpreting outcomes, to judging revisions.
For Binary basics, start with Section 4.

The cards intentionally keep explanations out of the way. Hover a card title for
its scope or a timing value for its meaning; this guide contains the longer
interpretations and cautions. Counts, chart axes, table values, and empty states
remain visible in the app.

Quick navigation: [Binary calibration](#4-binary-calibration-read-the-table-first),
[Trajectory Binary numbers](#5-trajectory-binary-what-the-compact-summary-means),
[Numeric calibration and ties](#6-five-quantile-numeric-calibration),
[uncertainty bars](#7-what-95-wilson-means),
[WIS and updates](#8-numeric-scores-and-updating-what-you-can-compare),
[legacy forecasts](#9-older-predictions-the-legacy-sections),
[individual scorecards](#what-can-i-see-for-one-prediction).

**The purpose is to improve your next forecast, not to make every chart look perfect.**
One surprising outcome is not evidence that your method is broken. Look for
repeated patterns, inspect the underlying questions, and change one habit at a time.

## Start here: Which numbers can change what I do?

**You do not need to use every number on this page.** Start with calibration and
the Numeric outcome-balance tables. Use scores afterward to inspect particular
forecasts and revisions. Timing weights explain a score; they are not improvement
targets.

| What you want to know | Look here first | A concrete next step if the pattern persists |
|---|---|---|
| Am I assigning Yes too much probability? | Binary Mean Forecast versus Observed Yes, with the bin's Count | If a comparable group averages 64% but only 45% resolve Yes, review whether you ignored the base rate or double-counted evidence. Before a similar new forecast, write down the base rate before adjusting for the case. |
| Am I underestimating how large a quantity can be? | Numeric 90% Interval: Above; q95 calibration | Repeated upper-tail misses suggest checking omitted delay/cost/growth scenarios. List plausible high outcomes before choosing your next q95. Do not move every percentile upward automatically. |
| Is my central estimate too high or low? | Numeric Median Balance | With few ties, persistently more outcomes above the median suggests estimates that are too low; the reverse suggests too high. Compare your next median with similar past cases. |
| Are my ranges too narrow? | Numeric 50%/90% Interval: Below, Inside, Above | If both tails miss too often, list sources of variation you omitted and consider broader intervals where that evidence warrants it. If misses are on only one side, investigate location or that tail first. |
| Are revisions helping in hindsight? | Binary Mean Updating Gain and helped/tied/hurt counts; Numeric better/equal/worse pairs | Read a few helpful and harmful revisions. Keep an evidence-gathering habit that explains the helpful cases; test whether the harmful cases reflect overreaction. More updates is not itself the goal. |
| Why does a Binary score stay near 0.25? | Average Forecast Weight and Average Neutral Weight | Check whether much of the planned period received neutral scoring after early resolution. This explains the score; it does **not** tell you to change probabilities or move the recorded outcome time. |

For whole-number Numeric forecasts, read the tie bands before diagnosing bias.
For any group, a tiny sample can look extreme just by chance. The point is to
choose an investigation, not to obey an automatic correction formula.

### What a score cannot prescribe

There is no honest rule like “Brier is 0.18, so subtract 10 percentage points next
time” or “WIS is 3, so double every interval.” Those scores summarize losses;
different mistakes can produce the same score. A good forecast can have an unlucky
outcome. Calibration patterns plus the original reasoning help distinguish
possible causes.

Use this loop: **notice a repeated pattern → inspect its predictions → choose one
prospective habit → gather more outcomes → reassess**. For example, if deadlines
repeatedly miss on the late side and the notes omit handoff delays, your next
experiment is to account for handoffs—not to add an arbitrary amount to every
forecast. If the archive is still mostly test data, none of its patterns diagnose
your real forecasting habits.

That is the purpose of Analytics: finding questions worth investigating and
tracking the consequences of your forecasts. It is not an automatic coach. For a
small personal archive, the individual scorecards and Postmortems can be more
useful than the headline averages. More summary metrics would not, by themselves,
solve that problem.

## 1. A useful five-minute review

1. **Choose the forecasts you mean to study.** Select Binary or Numeric. Use a
   meaningful tag if you want to study one subject. Avoid choosing a subset only
   because it makes your results look good.
2. **Check the sample size.** Only eligible resolved predictions count. A graph
   based on a few outcomes is a description of those outcomes, not a reliable
   diagnosis of your forecasting ability. Filtering makes samples smaller.
3. **Read calibration before chasing a score.** For Binary, compare Mean Forecast
   with Observed Yes. For Numeric, inspect the five percentiles and whether
   outcomes fall below, inside, or above your intervals.
4. **Pick one persistent pattern to investigate.** For example: “My high-probability
   Yes forecasts happen less often than I say,” or “Actual quantities keep landing
   above my upper bound.” Open some of those predictions from Predictions and
   read their reasoning, revisions, and outcome evidence.
5. **Write one concrete experiment in your journal or Postmortem.** For example:
   “Before my next delivery-time forecast, check similar past deliveries and list
   one reason this delivery could be unusually late.” Gather more outcomes before
   judging whether that habit helps.

It is also a valid conclusion to write: **“Not enough evidence to change anything.”**
The app does not automatically recommend or modify probabilities or percentiles.

## 2. Know which forecasts you are looking at

“All types” displays several separate sections; it does not calculate one universal score.

| Section | Which predictions? | Main feedback |
|---|---|---|
| Trajectory Binary forecasts | New v0.7 Yes/No predictions | Time-weighted Brier, plus separate final-probability calibration |
| Five-quantile Numeric | New v0.7 quantity predictions | Five-percentile calibration, interval outcomes, and update direction |
| Legacy Binary | Older Yes/No predictions | Final Brier and final-probability calibration |
| Legacy Numeric | Older single-interval predictions | Confidence versus containment, plus unit-specific errors and interval scores |

Older predictions keep their original rules. Updating the app does not convert
their history into new-model forecasts. Within five-quantile Numeric, continuous-style
and whole-number predictions also have separate calibration displays.

**Filters:** Forecast type and Tag select the relevant resolved observations.
Numeric unit is an exact unit-label filter, not a conversion tool. Choose Numeric
before selecting a unit. `days` and `hours` do not become comparable automatically.
All visible analytical results follow the selected filters, but each section still
uses its own eligible model and measurement group. Counts in different sections
therefore need not match. Analytics has no date-range control; date filtering in
Predictions is a separate browsing feature.

**What does not count:** Open, Locked, and Invalid predictions do not score.
For new models, an outcome already fixed at or before the initial forecast is
explicitly unscored. An empty section or “Not available” is not a score of zero.
One prediction contributes once, not once per revision, Review, or Journal entry.

### What is averaged, and over what?

**Mean means average.** Unless a label identifies a bin or revised pair, a
Trajectory Binary average gives each eligible resolved prediction one equal vote.
It is not weighted by the number of revisions or by how long the prediction ran.

| Display | What goes into it? |
|---|---|
| Mean Trajectory Brier; Mean initial/final Brier; Mean hold-initial trajectory; Mean Updating Gain | One corresponding value per eligible resolved Trajectory Binary prediction |
| Average Forecast Weight; Average Neutral Weight | One weight per eligible resolved Trajectory Binary prediction |
| Binary Mean Forecast in a bin | One final eligible probability per prediction in that bin |
| Observed Yes | Yes outcomes divided by resolved predictions in that bin |
| Numeric percentile frequencies and outcome balances | One scored forecast/outcome per eligible prediction in that measurement group and current filters |
| Numeric better/equal/worse percentages | Eligible revised pairs only; unrevised forecasts are listed separately |
| Legacy update means | Revised-and-resolved pairs only; legacy raw Numeric means also require the selected exact unit |

For example, one Binary prediction has Forecast Weight 20% and another has 100%.
**Average Forecast Weight is 60%**, even if one lasted an hour and the other a
month. Average Neutral Weight is 40%. These labels describe average calculation
weights across predictions, not your accuracy, activity level, or the fraction
of the total score earned by each component.

## 3. Two different questions: calibration and score

**Calibration:** “Do my stated chances match how often things happen?”
If many comparable 70% Yes forecasts come true about 70% of the time, that is
consistent with calibration at that probability.

**Score:** “How well did the forecast perform against the actual outcome?”
A score can reward useful precision and penalize confident mistakes. Lower Brier
and lower WIS are better under their respective rules.

These are not interchangeable. Always forecasting 50% in a roughly half-Yes
collection might be calibrated but not very informative. A single correct 99%
forecast receives a good score, but does not establish calibration.

Do not treat Brier as an accuracy percentage: **0.16 does not mean 84% accurate.**

## 4. Binary calibration: read the table first

### First: what is a Binary forecast?

A **Binary forecast** assigns a probability to a question with two outcomes:
Yes or No. For “Will the repair finish by Friday?”, **70% means a 70% chance of
Yes and a 30% chance of No**. It does not mean “I am 70% certain my forecast is
correct,” and it is not a prediction that 70% of this one repair will be done.

The repair eventually produces one outcome, not a percentage. A No outcome was
possible under your 70% forecast; one No does not prove the probability was bad.
Across many comparable 70% forecasts, you would expect roughly seven Yes outcomes
per ten—not exactly seven in every group of ten.

**Worked example:** You make ten 70% forecasts. Seven resolve Yes and three No.
The observed Yes rate is `7 / 10 = 70%`, matching the stated probabilities in this
small sample. If only four resolve Yes, the observed rate is 40%. Investigate
whether the probabilities were too high, but do not diagnose a permanent bias
from ten outcomes alone. Brier scores evaluate the individual forecasts;
calibration evaluates patterns across forecasts.

### Now read the calibration table

The trajectory section calls this **final-probability calibration**, not trajectory
calibration. It uses one last standing probability strictly before the earlier of
the effective resolution time and Deadline. It does not plot every revision.
Legacy Binary uses its captured final scoring probability instead.

| Column | Meaning |
|---|---|
| Probability bin | Which probabilities were grouped together: 20–29%, for example. The last bin includes 100%. |
| Count | Number of predictions in that bin, not number of revisions. |
| Mean Forecast | Average stated probability in that bin. |
| Observed Yes | Percentage of those predictions that actually resolved Yes. |

Example: 20 predictions in the 60–69% bin have Mean Forecast **64%** and Observed
Yes **45%**. Your probabilities suggested roughly 13 Yes outcomes; there were 9.
For this group, your Yes probabilities were higher than the observed frequency.
That is a reason to inspect the questions, not to mechanically change every future
64% forecast to 45%.

Mean Forecast belongs inside its bin by construction. It is not a separate test
of calibration. If it genuinely falls outside, report a bug; do not interpret it
as feedback about your skill. Empty bins have no meaningful mean or observed rate.

### The plot is the same comparison

- **Horizontal axis:** Mean Forecast, not the midpoint of the bin.
- **Vertical axis:** Observed Yes.
- **Diagonal:** Forecast and observed frequency agree.
- **Point above the diagonal:** Yes happened more often than you predicted.
- **Point below the diagonal:** Yes happened less often than you predicted.

The Trajectory Binary plot uses separate diamonds, with **no line between bins**.
Empty bins stay empty: the app has no observation to draw there. The diagonal is
only a reference, not an interpolated forecast. The legacy Binary plot retains
its older visual connectors; they are not estimates at every probability.
A bin with one prediction necessarily observes either 0% or 100%; that does not
prove catastrophic miscalibration. The Binary table's counts matter enormously;
this chart does not provide the Numeric chart's Wilson uncertainty bars.

The unconnected-marker presentation takes inspiration from
[Metaculus's calibration chart](https://github.com/Metaculus/metaculus/blob/main/front_end/src/app/%28main%29/questions/track-record/components/charts/calibration_chart.tsx).
It is not a statistical clone: Reckonsolve retains actual bin means on the
horizontal axis, its fixed bin definitions, and one final observation per
prediction. Metaculus's additional uncertainty bands are not implemented here.

**What to try if a pattern persists:** Examine your base rates and evidence.
If high Yes probabilities repeatedly overshoot and low Yes probabilities undershoot,
your forecasts may be too extreme. If most occupied bins are below the diagonal,
investigate a general tendency to predict Yes too readily. These are different
patterns; “move everything toward 50%” is not a universal solution.

## 5. Trajectory Binary: what the compact summary means

Brier for one probability is the squared distance from the outcome. A 60% forecast
gets `(0.60 - 1)^2 = 0.16` for Yes, or `(0.60 - 0)^2 = 0.36` for No. A 50% forecast
gets 0.25 either way. Zero is best; one is the worst possible single Brier.

Trajectory Brier asks how those probabilities performed **for the time they stood**
between the initial forecast and its permanent Deadline. A late accurate revision
does not erase earlier inaccurate hours.

### Score

- **Mean Trajectory Brier:** Average of the eligible predictions' trajectory scores.
  Each prediction has one equal vote; a month-long prediction does not outweigh a
  day-long prediction. Time weighting happens *inside* each prediction.
- **Eligible resolved Predictions:** How many predictions entered that average.

There is no universal “good” score for unrelated question sets. Difficulty and
question selection matter. A score below 0.25 beats holding 50% under the same
contract, but does not by itself prove expertise.

### Timing

- **Resolved before deadline:** Effective outcome time was earlier than Deadline.
- **Reached deadline:** Effective outcome time was at or after Deadline.
- **Average Forecast Weight:** Across eligible resolved predictions, the average
  weight assigned to actual forecasts when calculating Trajectory Brier.
- **Average Neutral Weight:** Across those same predictions, the average weight
  assigned to the fixed neutral loss of 0.25 after an early outcome. The two
  averages add to 100%.

For example, if the outcome becomes known four hours into a ten-hour planned window,
the split is **40% Forecast Weight / 60% Neutral Weight**. If the outcome is not known until
the Deadline or later, it is **100% Forecast Weight / 0% Neutral Weight**. The card averages
these weights across eligible predictions, giving each prediction equal weight;
it does not add up their hours. This is not time spent using the app or reviewing
predictions. The forecast share is the same statistic previously called *Mean
active forecasting*, now shown alongside its neutral remainder. These are
calculation weights, **not percentages of the resulting score** and not a measure
of accuracy. A higher Forecast Weight is not inherently better.

After early resolution, the remaining planned time receives **neutral loss 0.25**.
This is a scoring convention, not a forecast revision or an invented 50% calibration
observation. Consequently, even an excellent short active forecast can have a
trajectory score near 0.25 when most of its planned window is neutral time.
Never move effective time or choose deadlines to flatter the score: record when
the outcome genuinely became fixed and ascertainable, and choose deadlines prospectively.

### Updating

- **Mean initial Brier:** How the first probability scored against the outcome,
  ignoring how long it stood.
- **Mean final Brier:** How the last eligible probability scored, also ignoring duration.
- **Mean hold-initial trajectory:** The trajectory score you would have received
  by retaining the first probability for the whole active period, with the same
  neutral remainder after early resolution.
- **Mean Updating Gain:** Hold-initial trajectory minus actual trajectory.
  Positive means the recorded updates helped mechanically; negative means they
  hurt; zero means the scores tied. A tied result need not mean there were no updates.

Initial/final Brier and Trajectory Brier answer different questions. Do not expect
their averages to be equal. Updating Gain is a hindsight comparison, **not evidence
that making more revisions causes improvement**.

### Worked example

You commit a ten-hour window. For two hours you say 20%; for the next two hours
you say 80%. The outcome becomes knowable at hour four and is Yes.

| Contribution | Calculation | Contribution to Trajectory Brier |
|---|---|---|
| First two hours | 2/10 × 0.64 | 0.128 |
| Next two hours | 2/10 × 0.04 | 0.008 |
| Remaining six hours | 6/10 × 0.25 | 0.150 |
| Total | Sum | **0.286** |

The window uses **40% your forecasts / 60% neutral score**.
Initial Brier is **0.64**; Final Brier is **0.04**.
Holding 20% would have scored `4/10 × 0.64 + 6/10 × 0.25 = 0.406`.
Updating Gain is `0.406 - 0.286 = +0.120`.

The update helped, even though the overall trajectory score is above 0.25.
**Action:** Inspect what evidence prompted useful or harmful changes. Ask whether
you could have noticed it sooner, or whether you reacted too strongly to weak
evidence. Do not add fake revisions just to look active; Reviews retain a forecast
without splitting its scored trajectory.

## 6. Five-quantile Numeric calibration

### Step 1: Predict a quantity, not a Yes/No answer

A **Numeric forecast** describes uncertainty about a number. Compare:

- Binary: “Will this repair finish within seven days?” → a Yes probability.
- Numeric: “How many elapsed days will this repair take?” → possible durations.

In v0.7, you enter **five values in the same unit**. Together they describe a
middle estimate and how far the result could plausibly fall on either side.
They are one forecast, not five separate predictions.

We will use a repair measured in days, with one decimal place and **continuous-style**
semantics: durations such as 4.2 days make sense. We first assume few outcomes
land exactly on the chosen values; Step 7 explains what changes when many do.

### Step 2: Understand the five labels

A **quantile**, also called a **percentile**, is a cutoff in your beliefs about
the quantity. The number after `q` is a fixed probability level. **You enter the
quantity at that level**, not another probability.

Suppose you enter:

| Field | Your value | What you are saying for this continuous-style example |
|---|---|---|
| q05 | 1.0 days | Roughly 5% chance the repair takes at most 1 day; roughly 95% chance it takes longer |
| q25 | 3.0 days | Roughly 25% chance it takes at most 3 days |
| q50 | 5.0 days | The **median**: roughly half the chance lies on either side of 5 days |
| q75 | 7.0 days | Roughly 75% chance it takes at most 7 days; roughly 25% chance it takes longer |
| q95 | 9.0 days | Roughly 95% chance it takes at most 9 days; roughly 5% chance it takes longer |

Read `q95 = 9` as **“my 95th-percentile estimate is 9 days,”** not “95% chance of
exactly 9 days” or “95% confidence that I am good at forecasting.”

The probabilities are **cumulative**: the chance of at most 7 days already
includes the chance of at most 3 days. Do not add 5%, 25%, 50%, 75%, and 95%.
The median is not necessarily the arithmetic average or the most likely exact
value. q05 and q95 are not an absolute minimum and maximum.

Reckonsolve requires `q05 ≤ q25 ≤ q50 ≤ q75 ≤ q95`. Equal values are allowed;
crossed values are rejected. These five cutoffs do not specify every possible
outcome or a complete distribution beyond the outer values.

### Step 3: See the two intervals hidden in those five numbers

An **interval** is a range with a lower and upper endpoint. Reckonsolve derives
two **central prediction intervals**, with equal probability allocated to the
two tails in the continuous, negligible-tie interpretation. The **tails** are
the unusually low and unusually high possibilities outside the interval:

| Derived interval | Endpoints | Repair example | Intended probability split |
|---|---|---|---|
| Central 50% | q25 to q75 | 3.0–7.0 days | 25% below, 50% inside, 25% above |
| Central 90% | q05 to q95 | 1.0–9.0 days | 5% below, 90% inside, 5% above |

The middle interval covers `75% − 25% = 50%` of probability; the outer covers
`95% − 5% = 90%`. **q95 is one cutoff; it does not create a 95% central interval.**
The 50% interval sits inside the 90% interval. They can have unequal distances
on either side of the median; “central” means balanced tail probabilities, not
geometric symmetry. All these intervals count their endpoints as inside.

You enter the five values; you do not choose a separate confidence percentage in
this model. The older interval-v1 model works differently (Section 9).

### Step 4: Resolve one prediction

The repair actually takes **6.0 days**. Compare that one result with the forecast:

- Median miss: `6 − 5 = +1 day`. The actual was one day **above** your median.
- 50% interval: 6 is inside 3–7.
- 90% interval: 6 is inside 1–9.
- At or below each cutoff? q05: No; q25: No; q50: No; q75: Yes; q95: Yes.

Those are observations, not five independent outcomes. One repair contributes
once to each relevant check, always using its one final eligible forecast.

If the actual were **8.0 days**, it would be above the 50% interval but inside the
90% interval. That is an outcome your forecast allowed. If it were **12.0 days**,
it would be above both. An occasional outer miss is also allowed by a 90%
forecast. **“Inside” does not prove a good forecast, and “outside” does not prove
a bad one.** Section 8 explains how a score evaluates this individual result.

### Step 5: Use many outcomes to check calibration

**Calibration** asks whether your probability claims match observed frequencies
over repeated forecasts. The app compares each actual with **that prediction's
own cutoffs**—not every repair against the same 7-day threshold.

**Worked q75 example:** Across 20 eligible resolved forecasts, 15 actuals are at
or below their own q75 and 5 are above. The observed frequency is
`15 / 20 = 75%`. That agrees with the q75 claim in this sample. Different
predictions may have very different q75 values.

If only 10 of 20 were at or below q75, the frequency would be 50%, not 75%.
Your upper-middle estimates may be too low: more actuals exceeded them than
you intended. Investigate the missed cases, then consider uncertainty before
changing your method. Twenty outcomes do not establish a precise long-run rate.

The **Continuous-Style Calibration** table repeats this check at all five levels:

- **Nominal:** the stated probability level: 5%, 25%, 50%, 75%, or 95%.
- **Actual ≤ q:** count and percentage of outcomes at or below their own cutoff.
  `≤` means “less than or equal to.”
- **95% Wilson:** uncertainty around that observed percentage; see Section 7.

On the plot, the horizontal position is the nominal level and the vertical
position is the observed percentage. The diagonal is agreement. A point above
it means actuals fell below that cutoff more often than intended: the cutoff
may be **too high**. A point below suggests it may be **too low**. This direction
differs from Binary calibration, where the horizontal axis is a Yes probability.

The CDF preview in Prediction Detail instead plots your quantity values against
the five probability levels. It describes one forecast before resolution; it
does not measure calibration. Its interpolation adds no calibration observations.

### Step 6: Judge the ranges using Below / Inside / Above

**Coverage** is simply the fraction of actuals inside an interval. In Analytics,
the 50% Interval and 90% Interval tables show coverage alongside the two kinds
of miss. Median Balance shows Below / Equal / Above the median.

**Worked example, 20 continuous-style forecasts with negligible ties:**

| 90% intervals | Below | Inside | Above | Interpretation |
|---|---|---|---|---|
| A | 1 (5%) | 18 (90%) | 1 (5%) | Matches the intended split in this sample |
| B | 0 (0%) | 14 (70%) | 6 (30%) | Misses concentrate above: investigate underestimating the quantity or upper tail |
| C | 3 (15%) | 14 (70%) | 3 (15%) | Same coverage as B, but both tails miss: investigate ranges that are too narrow |

This is why coverage alone is not enough. B and C both contain 70% of outcomes
but suggest different questions to investigate. The sample is illustrative,
not a threshold for declaring your forecasts calibrated or broken.

For the **50% interval**, the reference split is 25% / 50% / 25%, so misses are
expected about half the time. For **Median Balance**, the reference is roughly
half below and half above when ties are negligible. Do not aim for every outcome
to land inside every interval: a forecast that says “almost anything can happen”
is not necessarily useful. Section 8 covers the cost of unnecessarily wide ranges.

### Step 7: Distinguish continuous-style from whole-number forecasts

Choose the type according to what the quantity **means**, not just how you want
to display it:

| Setting | Meaning | Example |
|---|---|---|
| Continuous-style | Measurements that can vary between integers | Elapsed repair time of 4.2 days; a mass of 2.35 kg |
| Whole-number | Integer-valued outcomes | Number of people who attend; number of completed tasks |

**Precision** is separate: it controls the exact decimal places stored for values.
A duration rounded to zero decimal places does not become a count. Whole-number
values must be integral even if displayed as `3.0`. The value constraint, unit,
and precision are fixed for that prediction.

Whole numbers often produce **ties**: an actual exactly equals a forecast cutoff.
Then “strictly below” and “at or below” are not interchangeable. A percentile
cutoff is allowed to have the stated probability **between** these two chances.
For instance, a valid median can have less than 50% below it and more than 50%
at or below it, because many outcomes equal it.

**Worked median example:** You forecast q50 = 3 people for ten comparable events.
Three have fewer than 3 attendees, four have exactly 3, and three have more:

- Strictly below 3: `3 / 10 = 30%`.
- At or below 3: `(3 + 4) / 10 = 70%`.
- Exactly equal: `4 / 10 = 40%`—the difference between 70% and 30%.

The nominal 50% lies between 30% and 70%. The 70% inclusive frequency is **not
by itself evidence that the medians are too high**. This pattern can be
consistent with the median claim, allowing for sampling variation.

The **Whole-Number Calibration** plot draws an open dot at 30%, a filled dot at
70%, and a band between them. **That band represents ties, not uncertainty.**
The table additionally gives a separate Wilson interval for each observed
frequency. Other percentiles use the same strict/inclusive comparison.

Inclusive whole-number intervals can cover **more** than their nominal 50% or
90% without being miscalibrated. In the extreme, if the quantity truly is certain
to be 3, all five quantiles can be 3; both intervals [3, 3] contain 100% of outcomes.
Do not widen or shift a correctly placed cutoff merely to force an exact hit rate.

Rounding or repeated quantiles can create ties in continuous-style forecasts too.
That chart still uses inclusive frequencies; when ties are substantial, exact
agreement with the nominal percentage is not a rigid target there either.

### Step 8: Turn the evidence into one experiment

- Repeated upper misses: check omitted large-outcome scenarios before setting q95.
- Repeated lower misses: check plausible small outcomes before setting q05.
- Actuals usually above your median, with few ties: compare your next median with
  a reference set of similar cases; you may be underestimating the quantity.
- Too many misses on both sides: look for uncertainty sources you left out.

Use a recurring pattern plus reviewed examples—not one bad resolution—to choose
a change. “Include supplier delays in my next repair forecast” is an experiment.
“Add two days to every number because this chart looks bad” is not a justified rule.

## 7. What “95% Wilson” means

### First separate three similar-looking percentages

| Term | What it describes | Example |
|---|---|---|
| q95 | One cutoff in your forecast for a quantity | Your 95th-percentile repair time is 9 days |
| 90% prediction interval | A range of possible values for one future outcome | You put the middle 90% between 1 and 9 days |
| 95% Wilson interval | Uncertainty about a frequency estimated from resolved outcomes | Five of ten actuals were at or below their medians; the observed rate is 50%, with an uncertainty interval of 23.7%–76.3% |

The prediction interval contains quantities such as **days**. The Wilson interval
contains **percentages describing a rate**, not days. One concerns where a quantity
may land; the other concerns how precisely your track record estimates a rate.

### Why not just report the observed rate?

Suppose five of ten actuals are at or below their predicted medians. The observed
rate is exactly 50%. But another batch of ten could easily give a different rate.
You have only ten observations; you do not know the long-run rate exactly.

**Wilson** is the name of the calculation Reckonsolve uses to put an uncertainty
interval around a count divided by a total. It uses those two numbers—not the
quality of your reasoning—to quantify sampling uncertainty. The calculation
follows the [Wilson method described by NIST](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

Here is the same observed rate with progressively more evidence, using the app's
calculation (endpoints rounded to one decimal place):

| Actuals at or below q50 | Observed rate | 95% Wilson interval |
|---|---|---|
| 5 of 10 | 50% | 23.7%–76.3% |
| 50 of 100 | 50% | 40.4%–59.6% |
| 500 of 1,000 | 50% | 46.9%–53.1% |

**Same dot, different precision.** Under comparable sampling conditions, more
observations make the estimated rate more precise. A wide bar says “we cannot
pin this rate down yet,” not “your prediction interval was too wide.”

### What does the 95% promise?

Imagine an unknown, stable long-run rate and many independent batches of outcomes.
For each batch, calculate a Wilson interval. The 95% procedure is designed so that
**about 95% of those intervals contain the true rate** under the sampling model.
Wilson coverage is approximate, not exactly 95% for every rate and sample size.

It does **not** mean there is a 95% chance that:

- your next actual value is inside the displayed Wilson interval;
- the next batch's observed percentage is inside it;
- your forecasting is calibrated.

Nor does this method assign a 95% probability to the true rate lying in this
particular interval. The 95% describes the **procedure's repeated reliability**,
not a probability calculated for the unknown rate after seeing your data.

The practical reading is simpler: **these data leave this much uncertainty about
the underlying rate, assuming independent, sufficiently comparable observations.**
The interval is not a guarantee for a heterogeneous or strongly correlated archive.

### Worked example: Inspect a q95 result

You have 20 eligible forecasts. Only 15 actuals were at or below their q95 values:

1. The intended level is **95%**.
2. The observed rate is `15 / 20 = 75%`.
3. Its Wilson interval is approximately **53.1%–88.8%**.
4. The intended 95% is above that interval. For continuous-style forecasts with
   few ties, this is a reason to investigate underestimated upper tails.

Contrast **19 of 20**: observed 95%, Wilson **76.4%–99.1%**. The observed rate
matches the target, but the interval is broad. You cannot conclude your long-run
calibration is precisely 95% from that sample.

Use these comparisons as prompts, not an automatic pass/fail test. Looking at
many percentiles or repeatedly changing filters increases the chance of finding
an apparent discrepancy. A bar containing the target does not prove calibration;
a bar missing it does not explain why the discrepancy occurred.

### How to read the bars in Reckonsolve

- **Continuous-style plot:** the dot is the observed rate; its vertical bar is
  the Wilson interval. Read the point's count before interpreting the gap.
- **Whole-number plot:** the band between open and filled dots represents ties.
  The table—not that band—contains Wilson intervals for the strict and inclusive
  rates separately. Do not treat the nominal level as an exact target for each
  endpoint when ties are present.
- **Outcome-balance tables:** each Below, Inside, Above, or Equal percentage has
  its own Wilson interval. For example, compare a 90% interval's Inside rate
  with 90%, not with the Wilson method's 95% confidence level.

Each Wilson interval concerns **one** reported frequency. “Pointwise” means just
that; it is not a 95% guarantee for the whole chart. Ten closely related forecasts
about one event can provide less independent evidence than ten unrelated outcomes.
There is no universal minimum sample size that makes every conclusion reliable.

## 8. Numeric scores and updating: what you can compare

### First distinguish a hit from a useful forecast

Two forecasts can both contain the actual and still differ in usefulness. A
1–1,000-day interval is easier to hit than a 1–9-day interval, but communicates
much less. Conversely, an extremely narrow interval can miss badly.

**WIS means Weighted Interval Score.** It evaluates your median and both intervals
together: narrower intervals cost less, but missed outcomes add penalties. Lower
is better. It evaluates one resolved forecast; calibration still requires many.
The interval-score principle is described in
[Forecasting: Principles and Practice](https://otexts.com/fpp3/distaccuracy.html).

### Worked score: Return to the repair

Keep `q05=1, q25=3, q50=5, q75=7, q95=9 days`. The actual is 6 days:

| Component | Calculation before weighting | Contribution to this model's WIS |
|---|---|---|
| Median error | Distance from 5 to 6 is 1 day | `1 / 5 = 0.20` |
| 50% interval | Width `7 − 3 = 4`; actual inside, so no miss penalty | `4 / 10 = 0.40` |
| 90% interval | Width `9 − 1 = 8`; actual inside, so no miss penalty | `8 / 50 = 0.16` |
| Total | Add the weighted contributions | **0.76 days** |

Those weights are fixed by Reckonsolve's five-quantile scoring contract. You do
not choose them. The score is not “76% accurate.”

Now suppose the actual is **12 days** instead. The median error is 7; the actual
is 5 days above the inner interval and 3 days above the outer interval. The fixed
miss-penalty rules make their interval scores `4 + 4 × 5 = 24` and
`8 + 20 × 3 = 68`. WIS becomes `7/5 + 24/10 + 68/50 = 5.16 days`.
The farther-out miss costs more. These individual contributions help you see
whether loss came from width, a displaced median, or missed tails.

### Worked revision comparison

For the **same repair and actual of 6 days**, suppose the initial forecast was
`1, 3, 5, 7, 9` and the final eligible forecast was `2, 4, 6, 8, 10`:

- Initial WIS: **0.76 days**.
- Final WIS: `0/5 + 4/10 + 8/50 =` **0.56 days**.
- **Delta WIS = Initial − Final = +0.20 days**: final scored better in hindsight.

Here the widths stayed the same, but the median moved onto the actual. Ask what
evidence justified that move at the time. The result does not establish that
shifting forecasts upward is generally a good strategy.

The score uses the last revision **strictly before** the earlier of effective
resolution and Deadline. Later revisions remain in history but do not improve
the score retrospectively. A correction to an incorrectly recorded actual or
effective time can legitimately change the score and comparison.

### Read aggregate updating feedback without pooling unlike scores

Analytics does **not** average raw WIS across unrelated Numeric questions, even
when their unit labels match. A 2-day error on a one-week repair and a 2-day error
on a ten-year project do not have the same practical meaning.

Instead, **Five-Quantile Updates — Initial versus Final** counts which direction
each eligible revised pair went. Suppose there are ten such pairs: six better,
two equal, two worse. The display shows **60% / 20% / 20%**. Four additional
unrevised predictions would be listed separately; they would not turn into ties
or change those percentages.

This counts directions, not sizes: six tiny gains could coexist with two large
losses. “Equal” means equal WIS, not necessarily identical forecasts. “Unrevised”
means the final scored revision is still revision 1, even if excluded later
revisions exist. Positive Delta WIS means better, negative means worse, zero tied.

**Action:** Inspect some better and worse pairs and their reasoning. Look for a
repeatable process issue—new evidence, overreaction, or ignored reference cases.
Neither a good WIS nor a high better-pair percentage tells you to revise more often.

### What can I see for one prediction?

Yes—open a **resolved** prediction from Predictions (or another existing entry
point) and scroll to its resolution/scorecard area. Analytics summarizes groups;
these scorecards describe that one prediction. There is no meaningful
single-prediction calibration curve: one observation cannot tell you whether your
stated probabilities are reliable over repeated forecasts.

| Model | Already displayed in Prediction Detail |
|---|---|
| Trajectory Binary | Effective Yes/No outcome, Trajectory Brier, final eligible probability and revision ID; expand **Score details** for Probability Scores (Initial/Final Brier), Updating (hold-initial/actual trajectory and gain), and Timing (Forecast/Neutral Weight) |
| Five-quantile Numeric | Effective actual value and scored five-percentile revision; expand **WIS Breakdown** for the interval/outcome graphic, Initial/Final/Delta WIS, median error and contribution, and each interval's exact range, outcome location, width, outside distance, interval score, and weighted contribution |

Binary **Forecast Weight** is that prediction's Active Forecast Fraction. It is
**not an average**. Its complement appears as Neutral Weight. The aggregate card
averages these per-prediction weights; the individual card does not.

The Numeric graphic uses one shared quantity scale for both scored intervals.
The thicker band distinguishes the inner 50% interval from the outer 90% interval;
thickness is not an extra probability or score. Each row labels its own endpoints
and median in matching text; tied values share a label and crowded labels stagger.
The vertical tick marks the median; the diamond marks the effective actual,
with its value labeled below on each row, including when it falls outside the
outer interval. A clear, separated actual shows only its number; crowded labels
add “actual” for clarity. If the actual equals an endpoint or median, their shared label
names both roles. Read exact endpoints and
values in the selectable text below. This shows the **final scored revision**,
not an excluded later forecast, and is not a calibration chart or a probability
density. Collapsed intervals remain visible as endpoint ticks. Hover metric
captions or values for their short definitions.

Both new-model scorecards identify excluded later revisions and corrected scoring
facts when applicable. If the outcome was fixed at or before the initial forecast,
they say **Not scored** with a reason instead of inventing a score. Open, Locked,
and Invalid predictions have no resolved-outcome scorecard. Older predictions
keep their legacy scorecards rather than receiving Trajectory Brier or WIS.

**How to use the individual numbers:** For Binary, compare the actual trajectory
with holding the initial forecast and then read the revisions that changed it.
For Numeric, a positive signed median miss means actual was above your median;
the interval locations show which side missed. Use the WIS contributions to see
whether width or missed outcomes account for the loss, then inspect the reasoning.
An endpoint miss in one resolved question is a case to learn from, not proof that
all future intervals should change.

## 9. Older predictions: the legacy sections

### Legacy Binary

Mean Brier uses one captured final probability per resolved prediction. Its
calibration table works as described in Section 4, but never mixes with trajectory
Binary. **Brier performance over time** plots cumulative mean Brier against
resolution time. It is not calibration and not a rolling recent-performance chart.
Later points share most of their data with earlier points; the curve becomes less
responsive as the archive grows. A falling line can reflect easier questions as
well as better forecasts.

Initial-versus-final feedback compares revised-and-resolved pairs; positive
initial-minus-final improvement means the final probability scored better. Its
pair count may be smaller than the headline resolved count.

### Legacy Numeric

Each prediction has one chosen-confidence interval and a median. The containment
chart groups those confidence percentages into bins, comparing **Mean Confidence**
with **Observed Containment**. It is not the five-percentile chart.

For example, intervals with mean confidence 80% that contain only 50% of outcomes
may be too narrow or badly located; inspect whether misses are predominantly above
or below them. A point below the containment diagonal means fewer hits than stated
confidence, not the same directional quantity bias as a q75 calibration point.

Select Numeric and one exact unit to see legacy magnitude summaries:

- **Median absolute error:** Distance between median and actual, ignoring direction.
- **Interval width:** Upper minus lower. Narrower alone is not necessarily better.
- **Interval score:** Width plus missed-outcome penalties, reflecting stated confidence.

Legacy update feedback also compares confidence, containment, and (for a selected
unit) magnitude metrics between initial and final forecasts. Better containment
alone could come from much wider intervals or changed confidence. Read these
together, not as independent victories. Even with the same unit, question scales
and difficulty can differ; the legacy unit filter is not a promise of comparability.

## 10. A short diagnostic checklist

Before deciding “I need to change my forecasting,” ask:

- Am I reading the intended model section and the intended filters?
- Is this a score, a calibration frequency, a timing fact, or a hindsight comparison?
- How many observations support this particular point—not just the whole screen?
- Could ties, correlated questions, or a different mix of subjects explain it?
- Are actual outcomes and effective resolution times recorded correctly?
- Can I describe one change to my **future process**, backed by reviewed examples?

Do not invalidate an honestly resolved prediction because it scored badly, change
its meaning after the outcome, or adjust effective time for a better result. Use
corrections only for genuine errors. Scores can legitimately change after those
audited corrections; reopening Analytics alone must not change history.

Useful Postmortem template:

> I noticed [pattern] in [count and filtered group]. The sample is [limited / more
> informative], with [relevant uncertainty or ties]. In the underlying predictions,
> I found [specific reasoning issue]. Next time I will [one concrete habit]. I will
> reassess after more outcomes rather than adjusting to every new dot.

For the governing rules, see Section 35 of the [Product specification](product-spec.md)
and the [Forecasting Rulebook](reckonsolve-forecasting-rulebook-v0.7.md).
For implementation boundaries, see [Architecture](architecture.md).
