# Reckonsolve One-Shot Rulebook Addendum (v0.8)

Status: v0.8 guidance; M57 individual workflows, M58 retrieval/reflection, and M59
aggregate Analytics have manual acceptance. M60 export/release validation is implemented
and manually accepted; release closure remains. This is not part of the v0.7 release. This
addendum applies only to the new One-Shot mode described in [product-spec Section
36](product-spec.md#36-planned-v080-one-shot-prediction-contract-and-milestone-plan).
The [v0.7 Forecasting Rulebook](reckonsolve-forecasting-rulebook-v0.7.md) remains the
guidance for existing Adaptive Predictions. Its observational-judgment and
historical-honesty principles continue to apply here, but its Rule 18 requirement for an
exact Forecast Deadline does not apply to One-Shot.

## What belongs in One-Shot

Use One-Shot when an answer already exists, you do not know it yet, and you can
ordinarily check it soon after writing your final forecast. The forecast can be one Yes
probability or five Numeric quantiles. You may think, estimate, and change draft numbers
before deciding on the final set. Only that final set is the forecast you record. The
important order is **final forecast first, check the answer second**.

For example, stand near a tree, write down your final q05/q25/q50/q75/q95 height
estimates, then measure it. A Binary version could ask whether that same tree exceeds a
stated height. You may enter your note and the measured answer into Reckonsolve later.
Your later app entry is an honest transcription, not a claim that Reckonsolve witnessed
the earlier decision. If Reckonsolve is available before you check, you may save the
forecast first and enter the answer afterward.

One-Shot is not a shortcut for a question whose answer does not exist yet and may evolve
while you learn more. Use the ordinary Adaptive mode for that kind of ongoing
uncertainty. Questions you can substantially steer remain subject to the Rulebook's
observational or policy-conditioned admission test; a short wait does not turn a goal
into an observational forecast.

## Define the answer before looking

Consider which tree, person, object, record, or result you mean and how you will check
it. For a measured quantity, consider the unit, measurement method, endpoints, and
rounding that could change the answer. For Yes/No, make the threshold and source clear.
The One-Shot screen offers **Background** for context and how you will check the answer,
and **Rationale** records the clues, assumptions, or comparisons that led to your forecast.

Good practice: choose the source or measurement convention before looking. Use Background
when ambiguity matters; simple questions need no required prose.

The height of a tree can exist before you forecast it. For One-Shot, the reveal is when
you check the previously unknown answer by your chosen method. It is not the instant the
tree acquired its height. If the original question is unresolvable under what you meant,
preserve it as Invalid and start a new question rather than choosing a more favorable
meaning after seeing the result.

## Record times without false precision

Reckonsolve always records when you entered a One-Shot forecast or answer into the app.
You may also report when you finished the forecast in your phone note and when you
checked the answer. These are useful for memory, but One-Shot Brier and WIS do not use
elapsed time. Approximate times, two events noted within the same minute, or missing
times do not prevent a score. Do not invent precise seconds for an event you recorded
only approximately. An optional note can say when you started thinking; earlier drafts
do not have to be transcribed.

The app cannot verify an external note or prove whether you had seen the answer. Enter a
One-Shot only when you are satisfied that your final values preceded your check. This is
a personal learning record, so the useful safeguard is honest labeling and preserving
what was entered and corrected, not an evidence upload or a long attestation form.

## Read scores and correct copying mistakes

One Binary probability receives one ordinary Brier score after its Yes/No answer is
entered. One Numeric distribution receives one five-quantile WIS after its actual value
is entered. No Forecast Deadline, revision trajectory, or update score is implied.
Individual scores appear after Save; the creation screen does not show a live score
while you copy values beside an already-known answer.

If you copied a probability, quantile, measured answer, or reported time incorrectly,
use **Correct transcription**. Reckonsolve shows the corrected value and recomputes the
score while retaining your original app entry and every correction. Use that action to
match what you actually wrote or observed. It is not a way to make a new forecast after
seeing the answer. Optional reasoning, Journal notes, and a later Postmortem can help
explain what you learned without changing the one committed forecast.

In Analytics, choose **Prediction mode → One-Shot**. The combined view has separate
Binary and Numeric sections, with ordinary mean Binary Brier and probability calibration,
plus Numeric quantile/interval calibration. Each answered Prediction counts once using
its current corrected facts. Waiting for answer and Invalid records do not count.
Reported times do not change eligibility or weight. Adaptive results remain in
their own view, and raw Numeric WIS is never averaged across questions.

A single result does not prove calibration, and choosing which phone-note
exercises to enter can bias a collection. Record misses as well as hits if you want the
summary to teach you something. See the [Analytics guide](analytics-guide.md#11-one-shot-analytics)
for examples, filters, uncertainty, and whole-number ties.

## Keep a recoverable copy

Use **Settings → Back Up Now** or the CLI `backup` command for a complete SQLite
recovery file. CSV format 5, available through Settings or `export-csv`, is for analysis.
It includes original and effective One-Shot facts, reported and app-recorded times, and
every transcription correction with a data dictionary. A copied external note is still
an external note; export does not turn its reported time into proof of commitment.
CSV cannot restore the application or its Saved Views and settings.
