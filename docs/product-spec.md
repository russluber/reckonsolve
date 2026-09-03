# Reckonsolve — A Personal Forecasting Journal

## v0.1 Baseline and v0.2/v0.3/v0.4/v0.5/v0.6 Product Specifications

Status: v0.5 source release implemented; v0.6 approved for staged implementation
Platform: Windows desktop  
Working relationship to Predlog: Fresh successor project, not an extension of the existing CLI codebase

Related repository documentation: [Architecture](architecture.md) and [technical decision records](decisions/README.md).

---

## 1. Purpose

Build a local-first personal forecasting journal that lets one person:

1. make binary and numeric probabilistic predictions;
2. record the reasoning behind them;
3. update beliefs as information changes;
4. preserve the complete history of those updates;
5. resolve predictions against real outcomes; and
6. study calibration and forecasting performance without collapsing unlike quantities into misleading comparisons.

The product is not merely a database of current probabilities. Its defining value is an honest historical record of what the user believed, why they believed it, and how those beliefs changed.

The v0.1 baseline is successful when it is useful enough to replace the user's old Predlog CLI for day-to-day binary forecasting. v0.2 extends that honest historical workflow to one central numeric prediction interval per revision and adds explicit Forecast Reviews without weakening binary behavior. v0.3 adds a command-line companion that operates on the same canonical local data through the same application rules as the desktop interface. v0.4 closes the learning loop with historically honest terminal-record corrections, later Postmortems, individual scorecards, and initial-versus-final update feedback. v0.5 makes the growing journal reliably retrievable and manageable through explainable full-text search, richer archive controls, dynamic Saved Views, and deliberate tag-library maintenance. v0.6 gives the completed desktop application a coherent, responsive, accessible visual system and application shell without changing the forecasting model or canonical data.

---

## 2. Product identity

The application is:

- personal;
- local-first;
- offline-capable;
- reasoning-centered;
- historically honest;
- domain-agnostic; and
- low-friction at the point of capture.

It is not:

- a social forecasting platform;
- a crowd-forecasting system;
- a collaboration tool;
- a hosted web service;
- an automated prediction engine; or
- a system that changes the user's forecasts on their behalf.

Core product statement:

> A local-first forecasting journal where you can make probabilistic predictions about events or quantities, explain your reasoning, update your beliefs over time without rewriting history, resolve outcomes, and study your calibration.

---

## 3. Constitutional product principles

These principles take precedence over implementation convenience.

### 3.1 Historical integrity

A saved forecast revision is immutable. The application may never silently overwrite a binary probability, numeric bound, numeric median, confidence level, rationale, or timestamp belonging to a historical revision.

Changing one's mind creates a new revision. It does not mutate the old one.

### 3.2 Belief updating is encouraged

Revising a forecast is a normal and desirable act. The interface should make it easy to change a binary probability or numeric interval while preserving both the old and new statements.

### 3.3 Reasoning is first-class

The app must support more than forecast values. A revision may contain its own rationale, and a prediction may accumulate journal entries even when its forecast does not change.

### 3.4 Low floor, high ceiling

Creating a binary prediction requires only:

- a question; and
- a probability.

All additional structure is optional. The app may encourage useful detail, but it must not require boilerplate.

Creating a numeric prediction necessarily requires Question, unit, precision, lower bound, median estimate, upper bound, and confidence. Background, Resolution Criteria, dates, tags, and rationale remain optional rather than becoming numeric boilerplate.

### 3.5 Forecast values do not decay

A stale binary forecast remains the probability the user last entered. A stale numeric forecast retains its last bounds, median, and confidence. The app may flag either as needing attention, but it must never automatically alter the saved forecast.

### 3.6 Local ownership

SQLite is the canonical store. No account, internet connection, or cloud service is required. Backup and portable export are visible product features.

### 3.7 Personal, not social

The application serves one local user. Do not introduce accounts, profiles, groups, leaderboards, comments, public feeds, or aggregation.

### 3.8 Advanced structure is opt-in

Power must not become bureaucracy. Background, resolution criteria, dates, tags, and rationale should enrich a prediction without obstructing quick capture.

---

## 4. v0.1 scope

v0.1 supports binary forecasts only.

### Included

- Create a Yes/No prediction with a probability.
- Add optional rationale and question metadata.
- View the current forecast.
- Create immutable forecast revisions.
- Add journal entries without changing the probability.
- View a unified chronological timeline.
- View probability history as a chart.
- Use the Open, Locked, Resolved, and Invalid lifecycle.
- Resolve a prediction as Yes or No.
- Add factual resolution notes and a reflective postmortem.
- Tag predictions.
- Browse, search, and filter predictions.
- Surface Needs Attention, Ready to Resolve, and Locked predictions.
- Calculate Brier scores.
- Display a calibration/reliability diagram.
- Display Brier performance over time.
- Back up the complete application database.
- Export prediction data to CSV.
- Establish visual identity, isolated development data, and a private frozen Windows build without publishing a normal installer.

### Approved for v0.2 staged implementation

- Numeric interval forecasting.
- Forecast Reviews, including a dedicated "Still at 60%" action.

### Explicitly later than v0.2 unless separately promoted

- Multiple-choice forecasts.
- Dedicated date forecasts.
- Full continuous or discrete probability distributions.
- Standalone multi-quantile elicitation beyond the two endpoints implied by one central interval.
- Conditional forecasts.
- Collections.
- Structured Sources/Evidence.
- Prediction relationships and graph visualization.
- Full review sessions and anti-anchoring review modes.
- Notifications and automatic reminders.
- Attachments.
- Log loss, Expected Calibration Error, probability bias, and advanced revision analytics.
- JSON and Markdown exports.

---

## 5. Primary user loop

The complete v0.1 loop is:

1. Create a binary prediction.
2. Optionally explain the initial forecast.
3. Revisit the prediction as events unfold.
4. Add journal entries or create new probability revisions.
5. Stop forecasting when its deadline passes, if one exists.
6. Resolve the prediction when the outcome is known.
7. Optionally write a postmortem.
8. Learn from Brier score and calibration analytics.

Every implementation milestone should preserve or extend this loop rather than creating disconnected features.

---

## 6. Core concepts and terminology

### Prediction

The enduring forecasting question plus its type-specific definition, stable metadata, and lifecycle state. A Prediction has exactly one forecast type for its entire lifetime.

Binary example:

> Will I finish *Statistical Rethinking* before December 1?

Numeric example:

> How many days will it take person X to respond to my offer?

### Forecast revision

A timestamped statement of belief and optional rationale. For a binary prediction, the statement is one Yes probability. For a numeric prediction, it is one central prediction interval, a median estimate, and a confidence level. A prediction has one or more revisions. Revisions are immutable.

### Current forecast

The most recent valid forecast revision.

### Journal entry

A timestamped note about evidence or reasoning that does not itself change the forecast values.

### Forecast deadline

The last calendar date on which ordinary forecast revisions are allowed. It is optional.

### Expected resolution

The calendar date by which the user expects the outcome to be knowable. It is optional and distinct from the forecast deadline. Time-of-day precision is not part of v0.1.

### Resolution

The recorded type-appropriate outcome and its associated resolution information: Yes/No for a binary prediction or the realized quantity for a numeric prediction.

### Postmortem

A reflection written after resolution about what the user got right or wrong in their reasoning or updating.

### Invalid prediction

A preserved but non-scored prediction that became malformed, unresolvable, or meaningless.

---

## 7. Data and domain model

The exact SQL schema is an implementation decision, but it must preserve the following domain model and invariants.

### 7.1 Prediction

Required fields:

- stable identifier;
- question text;
- forecast type, fixed to binary in v0.1 and fixed to either binary or numeric once v0.2 creates the prediction;
- status;
- created timestamp; and
- updated timestamp for mutable metadata.

A numeric Prediction also has a required unit label and fixed decimal precision. Unit and precision belong to the enduring Prediction definition, not to individual revisions, and are immutable after creation.

Optional fields:

- Background;
- Resolution Criteria;
- Forecast Deadline;
- Expected Resolution; and
- tags.

System-derived information should not be redundantly stored unless needed for correctness or performance. For example, Current Forecast should normally be derived from the latest valid revision.

### 7.2 ForecastRevision

In v0.1, a binary ForecastRevision has these required fields:

Required fields:

- stable identifier;
- prediction identifier;
- probability;
- created timestamp; and
- revision sequence or an equivalent deterministic ordering mechanism.

Optional field:

- rationale.

Invariant:

> Probability belongs to ForecastRevision, not Prediction.

The v0.2 numeric counterpart is defined in Section 30. Its lower bound, median estimate, upper bound, and confidence likewise belong to the immutable revision rather than Prediction.

### 7.3 JournalEntry

Required creation facts:

- stable identifier;
- prediction identifier;
- original body;
- original created timestamp; and
- reference to the forecast revision that was current when the entry was created.

The revision reference lets the app accurately show the probability held at the time without treating the journal entry as a forecast revision.

The displayed body may be corrected, but the entry's identity, original created timestamp, and forecast-revision reference remain immutable. The original body and every superseded body must remain available in a deterministic correction history. Each correction records its own timestamp; the latest body is the one shown in the main timeline entry.

### 7.4 Resolution

In v0.1, a binary Resolution has these required fields:

Required fields:

- stable identifier;
- prediction identifier;
- binary outcome;
- resolved timestamp; and
- the forecast revision used for scoring, or enough information to derive it unambiguously.

Optional fields:

- factual resolution notes; and
- postmortem.

The v0.2 numeric counterpart records an actual value using the Prediction's unit and precision. Both forecast types capture exactly one final eligible revision for scoring.

### 7.5 Tags

Tags are reusable labels with a many-to-many relationship to predictions. A single fixed domain field is not part of the design.

### 7.6 Invalid-state information

An invalid prediction should preserve:

- the time it was marked invalid; and
- an optional reason.

It remains visible and is excluded from scoring.

### 7.7 Minimum conceptual entities

- `predictions`
- `forecast_revisions`
- `prediction_definition_changes`
- `journal_entries`
- `resolutions`
- `tags`
- `prediction_tags`

Do not retrofit forecast reviews into the completed v0.1 schema history. Reviews are introduced by a new v0.2 migration and milestone.

---

## 8. Editing and immutability rules

### 8.1 Forecast revisions

After a revision is saved, the normal application must not edit or delete it in place. A new probability creates a new row/event.

In v0.1, a normal revision must change the current probability. Submitting the same probability with new reasoning would falsely imply that the forecast changed. A Journal entry records evidence or reasoning without asserting that the user deliberately re-evaluated the forecast; the v0.2 **Still at 60%** Review records that deliberate reconsideration while retaining the probability. This rule compares against the current revision only: returning later to a probability used by an older, non-current revision remains a valid change and creates a new revision.

Example:

```text
Aug 12    60%
Aug 25    60% → 40%
Sep 14    40% → 50%
```

The Aug 12 record must never become "Aug 12 — 70%."

### 8.2 Prediction metadata

Background, Expected Resolution, and tags may be edited normally.

Question wording and Resolution Criteria define the proposition being forecast. Before saving a change to either field, v0.1 must show a confirmation explaining that the edit may change the proposition's meaning. If the proposition has changed materially rather than merely being clarified or corrected, the interface should guide the user to create a new Prediction instead.

Adding, changing, or removing a Forecast Deadline also requires confirmation and history because it changes the forecast cutoff, derived Locked behavior, and potentially which revisions are eligible. Its confirmation must describe those scheduling consequences rather than claim that the proposition itself changed. Changing a Forecast Deadline alone does not require creating a new Prediction. If one save changes both a proposition field and the Forecast Deadline, one confirmation must explain both consequences and one definition-change record captures the save.

Each confirmed save that changes one or more protected fields—Question, Resolution Criteria, or Forecast Deadline—creates one immutable lightweight definition-change record. The record contains before and after snapshots of all three protected fields and a UTC timestamp. The metadata update and its definition-change record must be atomic: either both persist or neither does. Cancelling the form or submitting values that make no effective change must not create a record. Expected Resolution remains ordinary editable metadata and never triggers this confirmation or definition history by itself.

Prediction Detail exposes these records in a collapsed **Definition history** section so historical forecasts can be interpreted against the definition in effect at the time without overwhelming the primary view.

This is a focused v0.1 safeguard, not a comprehensive generic audit system. A complete audit trail for all metadata edits remains Later.

Optional date controls must distinguish an unset value from a saved date. When a Forecast Deadline or Expected Resolution is unset, the interface must present it as blank or **Not set**; it must not display today's date in a way that suggests today is stored. Enabling an unset date control may use today as the initial editable choice.

### 8.3 Journal entries

Journal entries belong to the historical timeline. New journal entries are allowed only while a prediction is Open or Locked.

v0.1 permits transparent, body-only corrections to a saved journal entry. A correction must append immutable edit history rather than overwrite the saved body. The timeline continues to place the entry at its original created timestamp, marks its current body **Edited**, and offers an expandable edit history containing the original body and every superseded version in correction order.

A correction must not change the entry's original timestamp or forecast-at-the-time revision reference, create a ForecastRevision, change probability, affect forecast scoring, or reset the Needs Attention clock. Corrections remain allowed after a prediction becomes Resolved or Invalid because an audited correction is not a new journal assertion; this flow is for correcting existing text, not backdating new reasoning.

v0.1 provides no operation or normal UI action to delete an individual journal entry. A later deliberate deletion of its parent Prediction may still remove the entry and its correction history transactionally under the rules in Section 19.

### 8.4 Resolved predictions

Normal forecast revisions are disabled after resolution. Resolution and invalidation are deliberate, one-way terminal decisions in v0.1. The interface must clearly describe that finality before saving either action. v0.1 provides no reopen, outcome-toggle, or terminal-record correction flow; adding one later requires a separately designed historically honest workflow rather than casual status editing.

---

## 9. Creation flow

### 9.1 Minimum form

```text
New Prediction

Question
[ Will the Padres win tonight? ]

Probability
[ 40% ]

[ Create Prediction ]
```

Required:

- Question
- Probability

Milestone 4 adds optional initial details behind a clear affordance such as "More details":

- Rationale
- Background
- Resolution Criteria
- Forecast Deadline
- Expected Resolution
- Tags

These values establish the Prediction and first ForecastRevision; they are not later metadata edits. Initial Question, Resolution Criteria, and Forecast Deadline values therefore require no edit confirmation and create no definition-change record. Rationale belongs to the first ForecastRevision, while Background, Resolution Criteria, dates, and tags belong to the initial Prediction state.

An initial Forecast Deadline may be the computer's current local calendar date or a later date, but it must not already have passed when the prediction is submitted. The deadline date is inclusive, so choosing today leaves the prediction Open through today. Expected Resolution may be in the past, and v0.1 imposes no required ordering between Expected Resolution and Forecast Deadline; they describe distinct concepts rather than a validated date range.

### 9.2 Probability input

The application accepts any whole-number probability from 0% through 100%, inclusive. Values such as 37% are valid; fractional percentages are not part of v0.1.

The initial design should make 10-point probabilities fast to enter:

```text
10  20  30  40  50  60  70  80  90
```

These controls are shortcuts, not constraints. The user must remain able to enter any permitted whole-number probability directly. At 0% and 100%, the interface may plainly note that the forecast expresses absolute certainty, but it must not block submission or require confirmation solely because an endpoint was chosen.

### 9.3 Creation behavior

Creating a prediction must be atomic. Once Milestone 4 adds optional initial details, the Prediction, its metadata and tag associations, and its first ForecastRevision with any rationale must either all persist or all roll back.

After successful creation, navigate to the Prediction Detail screen.

---

## 10. Prediction Detail screen

This is the primary working screen.

It must answer:

1. What am I forecasting?
2. What do I believe now?
3. Why?
4. How did I get here?
5. When does forecasting close or resolution become due?

Minimum content:

- question;
- tags;
- lifecycle status;
- current probability;
- Revise Forecast action;
- Add Journal Entry action;
- Resolve or Mark Invalid actions where appropriate;
- forecast deadline and expected resolution when present;
- Background and Resolution Criteria when present;
- collapsed Definition history when protected metadata has changed;
- unified chronological timeline; and
- probability-history chart.

Conceptual layout:

```text
Will unemployment exceed 5% before 2028?
#economics  #macro                         OPEN

Current Forecast
35%

[ Revise Forecast ]  [ Add Journal Entry ]

Forecast deadline: Dec 31, 2027
Expected resolution: Jan 2028

BACKGROUND
...

RESOLUTION CRITERIA
...

TIMELINE
Aug 12    FORECAST    35%
Aug 29    JOURNAL     The latest jobs report...
Sep 14    FORECAST    35% → 45%

PROBABILITY HISTORY
[ chart ]
```

Empty optional sections should not dominate the page.

---

## 11. Revision flow

The revision form displays:

- current forecast;
- new probability input; and
- optional "What changed?" rationale.

Saving performs an append, not an update.

```text
Current forecast
60%

New forecast
[ 40% ]

What changed? (optional)
[ ... ]

[ Save Revision ]
```

The new probability must differ from the current forecast. If the user's reasoning changed but their probability did not, v0.1 directs that thought to a Journal entry rather than creating a forecast revision; before Milestone 5, the interface may explain that this workflow is coming next. Returning to a probability used by an older, non-current revision is valid because it still represents a change from the current forecast.

After saving:

- the new revision appears in the forecast-only timeline/history introduced in Milestone 4;
- Current Forecast changes to the new probability; and
- the probability-history chart gains a marker.

Milestone 5 merges Journal entries into this forecast history to produce the unified chronological timeline specified for Prediction Detail.

Do not create a new revision when the user merely opens and closes the form.

v0.1 has no dedicated "Still at 60%" Review action.

---

## 12. Journal flow

A journal entry records new information or thought without changing the forecast.

Example:

```text
Aug 18 · Journal

New employment numbers came out. They weaken one of my
original arguments, but not enough for me to move away from 60%.

Forecast at the time: 60%
```

The Add Journal Entry flow accepts a required body and is available for Open and Locked predictions. Saving captures the current ForecastRevision reference atomically with the new entry. Resolved and Invalid predictions reject new journal entries.

Forecast revisions and journal entries appear together in one oldest-to-newest timeline. Journal entries show their original local timestamp, the body, and **Forecast at the time: N%** derived from the captured revision. Timeline order must remain deterministic when events have the same stored instant. Correcting an entry does not move it to the correction time.

An existing journal entry exposes a deliberate **Correct Entry** action. The correction form starts with the current body. After a correction, the timeline shows the latest body with an **Edited** marker and provides an expandable edit history with the original and all prior bodies. Corrections are allowed in every lifecycle state, including Resolved and Invalid, but no individual Delete action is available.

Adding a journal entry must not:

- create a forecast revision;
- change the current probability; or
- reset the v0.1 Needs Attention clock, which is based on the latest forecast revision.

Correcting a journal entry has the same three non-effects and must also leave the original timestamp and forecast-at-the-time revision reference unchanged.

In v0.2, an explicit Forecast Review—not ordinary Journal activity—records deliberate reconsideration of an unchanged forecast and resets the Needs Attention clock.

---

## 13. Probability-history chart

Every marker corresponds to exactly one immutable ForecastRevision. Journal entries and Journal corrections are never probability observations and must not add markers.

Minimum requirements:

- a fixed 0% through 100% probability scale on the vertical axis;
- actual elapsed stored time on the horizontal axis, with timestamps displayed in the computer's local time;
- revisions connected in immutable revision-sequence order without re-sorting them by timestamp;
- a step-after, piecewise-constant line: a saved probability remains in force until the next revision, when the line changes vertically to the new value;
- current and historical probabilities represented accurately; and
- sensible, nondegenerate rendering when only one revision exists. A lone marker should be centered using axis padding; the padding does not imply additional observations or a forecast before creation.

Revisions with the same stored instant share one horizontal position, so a change between them is vertical. If the system clock moved backward between saves, the sequence-ordered line may travel backward on the time axis rather than falsifying either the stored timestamp or revision order. The chart must not spread revisions at artificial equal intervals or invent timestamp offsets merely to avoid overlap.

Hovering or selecting a marker may show timestamp, transition, and rationale if the chosen UI toolkit makes this inexpensive. Rich interaction is not required for the first usable slice.

The chart must have an accessible summary of its revision sequence. The existing textual Forecast entries in the unified timeline remain the exact nonvisual equivalent; the chart must not become the only way to recover a revision's probability, order, timestamp, transition, or rationale.

---

## 14. Lifecycle

### 14.1 Open

- Forecast revisions allowed.
- New journal entries and transparent corrections to existing entries are allowed.
- Forecast Reviews are allowed and retain the current forecast unchanged.
- Can be resolved or marked invalid.

### 14.2 Locked

The forecast deadline has passed.

Because Forecast Deadline is a date-only value, its stored calendar date is inclusive. An otherwise Open prediction becomes Locked when the computer's local calendar date is later than its Forecast Deadline, not at the start of the deadline date.

- Normal forecast revisions are not allowed.
- New journal entries and transparent corrections to existing entries remain allowed.
- Forecast Reviews are not allowed; a Review must occur while the prediction is Open.
- The prediction awaits an outcome.
- It can be resolved or marked invalid.

An Open prediction with no forecast deadline remains Open until resolved or invalidated.

### 14.3 Resolved

- Outcome is recorded as Yes or No.
- No further forecast revisions are allowed.
- No new journal entries are allowed, but transparent corrections to existing entries remain allowed.
- No Forecast Reviews are allowed.
- The prediction is eligible for scoring.
- Resolution notes and a postmortem may be recorded.

### 14.4 Invalid

- The prediction is preserved.
- No further forecast revisions are allowed.
- No new journal entries are allowed, but transparent corrections to existing entries remain allowed.
- No Forecast Reviews are allowed.
- It is excluded from all scoring and calibration analytics.
- An optional invalidation reason should be supported.

### 14.5 Status derivation

Where practical, derive time-dependent Locked state from the forecast deadline rather than relying on the application to run at the exact transition time. Persist terminal decisions such as Resolved and Invalid.

---

## 15. Resolution flow

Minimum form:

```text
Resolve Prediction

Outcome
( ) Yes
( ) No

Resolution notes (optional)
[ ... ]

Postmortem (optional)
[ ... ]

[ Resolve ]
```

Resolution notes are factual provenance, for example:

> Outcome determined from the certified election result.

The postmortem is reflective, for example:

> I overweighted the July polling shift and failed to account for subgroup instability.

Ordinary Brier scoring uses the final valid forecast revision made before forecasting closed or the prediction was resolved.

Each resolved prediction contributes exactly one observation to ordinary scoring. Do not count every revision as an independent resolved forecast.

---

## 16. Dashboard

The Dashboard prioritizes action rather than showing an undifferentiated list.

It should surface counts and useful entries for:

- Open;
- Needs Attention;
- Ready to Resolve; and
- Locked.

Each Dashboard row must identify its forecast type. A Binary row shows its
current Yes probability. A Numeric row shows its confidence interval, median,
and unit; it must not resemble a percentage-only Binary forecast. Selecting
either row opens the matching type-specific Prediction Detail view.

### 16.1 Needs Attention

In v0.2, a nonterminal prediction needs attention when the later of its latest eligible ForecastRevision or Forecast Review is at least the configured stale threshold old. Freshness uses elapsed time between that canonical UTC instant and the current canonical UTC instant; local display formatting does not change that duration.

The interface says **Forecast last considered** so the label remains accurate whether freshness came from a changed revision or a Review that retained the forecast.

The default stale threshold remains **14 days**: fourteen complete 24-hour periods since the later eligible Revision or Review. It is stored with the application data and adjustable through one minimal Settings control without introducing a general preferences framework. Adding or correcting Journal text does not reset this clock.

### 16.2 Ready to Resolve

A prediction is Ready to Resolve when:

- it is not Resolved or Invalid; and
- its Expected Resolution has passed.

Expected Resolution is an inclusive date-only expectation. A prediction becomes Ready to Resolve when the computer's local calendar date is later than its Expected Resolution date, not at the start of that date.

Ready to Resolve is an attention bucket, not a fifth canonical lifecycle status.

### 16.3 Locked

Locked predictions should be distinguishable from predictions that merely need attention or are ready to resolve.

A prediction may satisfy more than one attention condition. The UI must use clear, deterministic placement or badges rather than losing information.

---

## 17. Prediction browser

The Predictions screen provides:

- text search over question text;
- status filter;
- forecast-type filter;
- tag filter;
- a clear empty state; and
- navigation to Prediction Detail.

At minimum, filters cover:

- All, Open, Locked, Resolved, and Invalid; and
- All types, Binary, and Numeric; and
- individual tags.

Search, status, forecast-type, and tag filters combine using logical AND. Each
result identifies Binary or Numeric forecast type and presents the matching
current forecast summary without obscuring a Numeric unit or interval.

The v0.1 question-only behavior remains the compatibility baseline. v0.5 explicitly promotes full-text retrieval across the wider historically honest journal corpus under the contract in Section 33.

---

## 18. Analytics

v0.1 analytics are intentionally focused.

### 18.1 Brier score

For binary forecast probability `p` and outcome `y` in `{0, 1}`:

```text
Brier = (p - y)^2
```

Requirements:

- show the number of scored resolved predictions;
- show mean Brier score;
- exclude Invalid predictions;
- use exactly one final eligible revision per resolved prediction; and
- make the direction clear: lower is better.

### 18.2 Calibration/reliability diagram

Compare stated probabilities with observed frequencies using probability bins.

Requirements:

- display the perfect-calibration reference line;
- make bin counts or data sparsity discoverable;
- exclude Invalid and unresolved predictions; and
- use the same final-eligible-revision rule as Brier scoring.

v0.1 uses ten fixed probability bins: `0-9%`, `10-19%`, continuing in ten-point bands through `80-89%`, and `90-100%`. A forecast belongs to exactly one bin; 0% is included in the first and 100% in the last. Each occupied bin is plotted at its actual mean forecast probability on the horizontal axis and its observed Yes frequency on the vertical axis, rather than at an invented bin midpoint. Bin counts must be visible or otherwise directly discoverable, including zero counts for empty bins; empty bins do not create fake calibration observations or chart points.

The bins remain fixed when filtering so views stay comparable. They group observations only for calibration display and never round, rewrite, or constrain the underlying whole-number forecasts.

### 18.3 Brier performance over time

v0.1 displays **Cumulative mean Brier by resolution time**. Resolved predictions are ordered by their canonical resolution instant, with stable Resolution-record order breaking timestamp ties. The first point is the first scored prediction's Brier score; every later point is the mean Brier of all predictions resolved up to and including that point. The series begins with one scored prediction rather than waiting for an arbitrary rolling-window size.

The label must say exactly what is being calculated, state that lower is better, and avoid implying that movement proves skill improvement: forecast difficulty and composition may also change.

### 18.4 Filtering

Analytics supports All predictions and one tag-filtered subset at a time. The same filter is applied before the Brier summary, calibration bins, and cumulative series are calculated, so all three views describe the same scored set. Tag filtering must not alter the one-final-eligible-revision selection rule.

### 18.5 Not in v0.1

- Log loss.
- Expected Calibration Error.
- Probability-bias statistic.
- Initial-versus-final Brier comparisons.
- Revision-quality or update-value scores.
- Numeric coverage, interval width, or Winkler score.

---

## 19. Delete versus Invalid

Deletion is appropriate for:

- an accidental duplicate;
- a test record; or
- immediate junk creation.

Invalidation is appropriate when:

- the question becomes impossible to resolve;
- its resolution criteria fail;
- the event ceases to make sense; or
- the prediction is genuinely malformed after meaningful history exists.

The normal v0.1 UI permits permanent deletion only for an untouched Open prediction. For this rule, untouched means all of the following remain true at the moment of deletion:

- the persisted and derived status is Open;
- only the required initial ForecastRevision exists;
- prediction metadata has not been changed after creation;
- no Journal entry exists; and
- no Definition history record exists; and
- no Forecast Review exists.

Initial rationale, metadata, and tags supplied during atomic creation do not by themselves make the prediction ineligible for deletion. A Forecast Deadline that has since passed does make it ineligible because the prediction is then Locked.

Deletion requires an explicit permanent-action confirmation and rechecks eligibility inside the deletion transaction. Once a prediction is Locked, revised, edited, journaled, reviewed, Resolved, or Invalid, the normal application rejects deletion. For a nonterminal prediction with meaningful history, the interface directs the user toward **Mark Invalid** so the record is preserved but excluded from scoring.

Resolved and Invalid predictions are never deletable from the normal v0.1 interface. The purpose is to protect honest history and calibration statistics, not to deny the user ownership of their underlying local database.

Deletion behavior must be transactional and must not leave orphan records.

---

## 20. Backup and export

Backup and export are different features.

### Backup

A backup is sufficient for complete application recovery. It must capture the canonical SQLite state consistently, including related metadata required by the app.

v0.1 creates one SQLite backup file through SQLite's online backup mechanism rather than copying the live database file directly. The user chooses the destination, with a timestamped `.sqlite3` filename suggested. Reckonsolve writes and verifies a temporary snapshot before replacing the selected destination, rejects the live canonical database as a destination, and never damages an existing backup when snapshot creation or verification fails. Choosing Cancel creates no file and changes no application state.

The backup contains the complete database needed for recovery, including Forecast and Journal history, terminal records, tags, definition history, and persisted settings. Settings persist and display the last successful backup time across application restarts. A failed or cancelled attempt must not advance that time.

Minimum UI:

- Back Up Now;
- destination selection or a clearly disclosed destination; and
- last successful backup time.

### CSV export

CSV is a portable analytical representation, not a complete relational restoration format.

The v0.2 CSV ZIP is format version 2 and contains `predictions.csv`, `forecast_revisions.csv`, `numeric_forecast_revisions.csv`, `definition_changes.csv`, `journal_entries.csv`, `journal_corrections.csv`, `forecast_reviews.csv`, `resolutions.csv`, `numeric_resolutions.csv`, `invalidations.csv`, `tags.csv`, and `prediction_tags.csv`, plus `README.txt`. Stable identifiers and relationship columns preserve the joins among Binary and Numeric Predictions, their type-appropriate ForecastRevisions, Journal entries and corrections, Forecast Reviews, terminal records, and tags rather than flattening away repeated history. Numeric values remain exact scaled integers paired with the parent Prediction's fixed precision; they are not silently converted through binary floating point.

The README documents every file and column, relationship keys, null handling, timestamp and date conventions, and how current forecasts and corrected Journal bodies are derived. CSV files use UTF-8, standard quoting, and Windows-friendly line endings. Canonical instants remain UTC text and date-only values remain ISO calendar dates. Optional nulls are represented by documented blank fields; legitimate stored text is preserved without analytical rewriting.

The bundle excludes application settings and is not a restoration format. It is built from one consistent read of canonical data, changes no application state, and is installed at the selected destination only after the complete temporary ZIP validates successfully. Cancelled or failed exports do not replace an existing export.

JSON and Markdown export are Later.

---

## 21. Settings

Keep v0.1 settings sparse.

Candidate settings:

- data/database location display;
- backup controls;
- CSV export;
- stale forecast threshold;
- probability input increment preference, if implemented; and
- System, Light, or Dark appearance.

Do not build a general preferences framework beyond present needs.

---

## 22. Primary screens

v0.1 has six primary screens:

| Screen | Purpose |
|---|---|
| Dashboard | Surface what is open and what needs action |
| New Prediction | Create a binary forecast quickly |
| Prediction Detail | View and work with one prediction |
| Predictions | Search, filter, and browse the archive |
| Analytics | Inspect Brier score, calibration, and performance over time |
| Settings | Manage data, backup, export, and minimal preferences |

Dialogs or secondary views may support revision, journal, resolution, invalidation, deletion, and metadata editing without becoming primary navigation destinations.

---

## 23. UX requirements

- Favor a calm desktop-journal feel over a dense trading dashboard.
- Keep Question and Probability visually primary during creation.
- Hide or de-emphasize empty optional metadata.
- Make current probability and status immediately legible.
- Use plain language around scoring and lifecycle states.
- Confirm destructive or historically consequential actions.
- Provide helpful empty states for a new database.
- Do not show false precision.
- Preserve keyboard-friendly workflows where practical.
- Do not require network access for core behavior.
- Do not make the user restate self-evident Resolution Criteria.

---

## 24. Technical boundaries

The implementation direction is a Python desktop application using PySide6 and SQLite, targeting eventual normal Windows distribution. v0.1 establishes visual identity, isolates development data from future stable data, and validates a private frozen Windows build. A normal installer, code signing, and public binary distribution are Later. This direction may be revisited only deliberately; product invariants must survive any technology change.

Required boundaries:

- SQLite is canonical.
- Database migrations must be deliberate and testable.
- Creating a prediction plus its first revision is atomic.
- Creating a revision is append-only in normal application logic.
- Resolution and invalidation are transactional.
- Numeric quantities must use an exact base-ten representation consistent with the Prediction's fixed decimal precision; binary floating-point is not canonical storage.
- System-generated instants are stored in UTC and displayed in the computer's local time.
- Date-only values retain their calendar-date meaning and are not converted between time zones.
- Analytics queries must use the final eligible type-appropriate revision exactly once per resolved prediction.
- Unitless numeric containment calibration may combine units, but raw numeric errors and interval scores must not be aggregated across unlike units.
- The application must reopen existing data correctly after restart.

Architecture should stay proportionate to a single-user local desktop app. Prefer clear modules and a testable data-access/domain layer over service-oriented infrastructure.

---

## 25. Must-not-introduce guardrails

Unless the product spec is explicitly revised, Codex must not:

- add authentication or accounts;
- add cloud sync or hosted storage;
- add a REST or GraphQL API;
- turn the project into a web app or PWA;
- add social or collaboration features;
- add multiple users or profiles;
- add leaderboards, tournaments, or crowd forecasts;
- overwrite historical forecast revisions;
- store the canonical current probability only on Prediction;
- treat every revision as an independent observation in calibration;
- require Background, Resolution Criteria, dates, tags, or rationale;
- automatically change stale probabilities;
- conflate Forecast Deadline with Expected Resolution;
- weaken or silently reinterpret existing binary behavior while adding numeric forecasts;
- add more than one central numeric interval per revision, a full probability distribution, or automatic unit conversion in v0.2;
- treat a Forecast Review as a new forecast revision or independent scoring observation;
- quietly expand Later features into the MVP;
- delete legitimate history merely because a prediction becomes invalid; or
- add infrastructure for hypothetical future scale.

---

## 26. Implementation milestones

Build vertical slices. Do not attempt the entire specification in one undifferentiated change.

### Milestone 1: Application shell and persistence

- PySide6 application opens.
- Navigation shell exists.
- SQLite database initializes and migrates safely.
- Application can close and reopen the same database.

### Milestone 2: Binary creation vertical slice

- Create a question and probability.
- Persist Prediction and first ForecastRevision atomically.
- Reopen and display the prediction after restart.

Acceptance demonstration:

> Open app → create 60% prediction → close app → reopen app → prediction and 60% revision remain.

### Milestone 3: Prediction Detail

- Display question, current forecast, status, dates, optional metadata, and tags.
- Support safe metadata editing.

### Milestone 4: Immutable revisions and complete creation details

- Add the optional **More details** creation section for initial rationale, metadata, and tags.
- Persist all supplied initial state atomically without an edit warning or definition-change record.
- Revise probability with optional rationale.
- Preserve every earlier revision.
- Enforce revision restrictions after lock or terminal state.
- Show saved forecast revisions in a forecast-only timeline/history that Milestone 5 will extend with Journal entries.

### Milestone 5: Timeline and journal

- Add journal entries for Open and Locked predictions and reject new entries for Resolved and Invalid predictions.
- Show revisions and journal entries in one deterministic chronological timeline.
- Preserve which revision was current for each journal entry and show its probability as **Forecast at the time**.
- Support transparent body corrections in every lifecycle state while preserving the original body, every superseded body, original timestamp, and forecast-revision reference.
- Mark corrected entries **Edited**, expose their correction history, and provide no individual journal-entry deletion.

### Milestone 6: Probability-history chart

- Plot exactly one marker per immutable revision using a fixed 0% through 100% vertical scale and actual stored time on the horizontal scale.
- Connect revisions in sequence order with a step-after line that represents the probability held between revisions.
- Handle one revision, multiple revisions, equal timestamps, repeated nonconsecutive probabilities, and clock regression without inventing observations or timestamps.
- Exclude Journal events and retain the unified timeline as the chart's exact nonvisual equivalent.

### Milestone 7: Lifecycle and resolution

- Implement Open, Locked, Resolved, and Invalid behavior.
- Resolve Yes/No with optional notes and postmortem.
- Make resolution and invalidation deliberate one-way v0.1 terminal decisions.
- Permanently delete only explicitly confirmed, transaction-current untouched Open predictions; direct meaningful nonterminal history toward Invalid instead.

### Milestone 8: Dashboard

- Surface Open, Needs Attention, Ready to Resolve, and Locked predictions.
- Use latest revision time for v0.1 freshness.
- Default Needs Attention to 14 elapsed days and persist one minimal configurable threshold.
- Preserve overlapping attention classifications rather than forcing predictions into one exclusive bucket.

### Milestone 9: Tags and prediction browser

- Browse all predictions.
- Search question text.
- Filter by status and tag.

### Milestone 10: Analytics

- Brier scoring.
- Ten-bin reliability diagram with actual bin means, observed frequencies, and discoverable counts.
- Clearly labeled cumulative mean Brier by resolution time.
- All-predictions and single-tag analytical subsets.
- Tests for final-eligible-revision selection and exclusions.

### Milestone 11: Backup and CSV export

- Produce a verified, consistent, recoverable SQLite backup at a user-selected destination and persist its last successful time.
- Export a documented relational CSV ZIP without erasing historical structure.
- Preserve an existing destination artifact when backup or export generation fails.

### Milestone 12: Visual identity and private release readiness

- Establish an offline icon-resource system using only selected, version-pinned Lucide SVG assets, retain clear text for important actions, and include the applicable third-party license notices.
- Add an original, user-directed Reckonsolve application icon suitable for the window, taskbar, and future Windows distribution.
- Apply conservative native-Windows polish to action hierarchy, spacing, resizing, high-DPI behavior, keyboard access, and light/dark palette legibility without introducing a custom theme framework or broad redesign.
- Give development runs an explicit visible identity and a separate per-user database location from future stable builds. Never silently copy or migrate the stable database into the development location.
- Create a repeatable private PyInstaller `onedir` smoke build and verify that it runs without a source checkout, Python, or `uv`; keep generated artifacts untracked and unpublished.
- Verify resource loading, development/stable data isolation, migration, backup, restart, and the core user loop in the private frozen build.
- Defer an installer, shortcuts, uninstall behavior, code signing, automatic updates, and public binary distribution until a later release-readiness decision.

The approved v0.2 milestones continue as Milestones 13 through 20 in Section 30. Each must preserve the completed v0.1 binary workflow.

---

## 27. Cross-cutting acceptance criteria

v0.1 is not complete unless all of the following are true:

1. A prediction can be created using only Question and Probability.
2. Optional structure never blocks quick creation.
3. Restarting the app preserves all data.
4. Revising a forecast creates a new historical record.
5. No normal UI path silently rewrites an earlier revision.
6. A journal entry can be added while Open or Locked without changing probability or creating a ForecastRevision.
7. Forecast Deadline and Expected Resolution behave as separate concepts.
8. Locked predictions reject normal revisions but accept new journal entries; Resolved and Invalid predictions reject new entries.
9. A prediction can resolve Yes or No and be scored.
10. Invalid predictions remain visible and are excluded from scoring.
11. Each resolved prediction contributes one final eligible forecast to ordinary Brier and calibration analytics.
12. Stale forecasts are flagged without changing their probabilities.
13. Dashboard attention buckets behave correctly across date boundaries and app restarts.
14. Backup produces recoverable application data.
15. CSV export preserves enough structure to be honest about revisions and outcomes.
16. Core workflows function offline.
17. Numeric forecasts and Forecast Reviews are absent from v0.1.

---

## 28. Testing priorities

Highest-risk behavior should receive automated tests before visual polish:

- immutable revision append behavior;
- atomic journal-entry creation with the current ForecastRevision reference;
- journal lifecycle boundaries, including terminal rejection of new entries and terminal permission for audited corrections;
- immutable journal correction history, retained original context, and rejection of individual deletion;
- deterministic unified-timeline ordering, including equal stored timestamps;
- verification that journal creation and correction do not create revisions, change probability, or reset Needs Attention;
- probability-history marker selection and step geometry for one or many revisions, including 0%, 100%, equal timestamps, a nonconsecutive return to an earlier probability, and a regressing clock;
- verification that Journal entries and corrections never appear as probability-history observations;
- immutable type-aware Forecast Reviews, Open-only lifecycle enforcement, exact current-revision ownership, stale-context rejection, and Needs Attention reset without revision, chart, or scoring effects;
- atomic creation of a Prediction, optional initial metadata and tags, and its first revision with optional rationale;
- atomic protected-field metadata edits and definition-change records;
- current-revision selection;
- lock-boundary behavior;
- resolution and invalidation transitions;
- immutable terminal records and rejection of repeated or conflicting terminal actions;
- final eligible forecast selection for scoring;
- exclusion of Invalid and unresolved predictions;
- Brier calculations;
- calibration bin assignment;
- Needs Attention and Ready to Resolve date logic;
- cascade/restrict behavior for deletion;
- database migrations;
- backup consistency; and
- reopen-after-restart persistence;
- development and stable application-data isolation;
- local icon availability, palette legibility, text-label retention, and accessible action names; and
- private frozen-build startup, migration, backup, restart, and core-loop behavior without the development environment.

Use representative edge cases such as a single revision, several revisions at the same displayed probability, resolution before Expected Resolution, a missing Forecast Deadline, and time-boundary transitions.

For repeated displayed probabilities, cover a valid nonconsecutive return such as `60% -> 40% -> 60%`; normal v0.1 revision submission must reject an unchanged current probability such as `60% -> 60%`.

---

## 29. Open implementation decisions

The application and project name is resolved as **Reckonsolve**. Metadata-edit safety, probability input, time handling, and the v0.1 visual/release-readiness boundary are resolved in Sections 8.2, 9.2, 24, and Milestone 12. M12 uses native system styling, selected local Lucide assets, an original user-directed app icon, separated development data, and a private `onedir` validation build. It does not choose a normal installer or public distribution channel.

The installer format, signing approach, public distribution channel, and final original icon artwork remain intentionally unresolved until the user chooses to pursue normal Windows distribution. They are Later decisions rather than v0.1 acceptance blockers.

The v0.2 numeric product contract is resolved in Section 30. Numeric precision and storage are recorded in Section 30.2 and ADR 0009. Forecast Reviews are allowed only while Open, as recorded in Sections 14 and 30.8.

The v0.3 CLI product contract, command identities, shared-data behavior, interaction model, and staged implementation plan are resolved in Section 31. Logo artwork, normal binary distribution, and automation-oriented CLI features remain deferred.

The v0.4 resolution-integrity and learning contract is resolved in Section 32. Resolved outcomes may be corrected only through append-only history, Invalid Predictions remain Invalid, Postmortems may be completed later, and initial-versus-final analytics use one paired observation per eligible Prediction rather than treating revisions independently.

The v0.5 retrieval-and-organization contract is resolved in Section 33. Search is local, lexical, explainable, current/effective by default, and historically explicit when superseded text is requested. Saved Views remain dynamic queries rather than Collections, and global tag maintenance changes current organizational metadata without rewriting forecast, Journal, or terminal history.

The v0.6 visual-system and application-shell contract is resolved in Section 34. The desktop follows the system light/dark preference, retains the native window frame, uses comfortable density and one restrained green accent, separates primary destinations from creation and contextual Detail, supports remembered expanded and compact navigation, and uses nonblocking status notifications only where acknowledgment does not require a decision. Presentation preferences remain noncanonical and separate from forecast data.

When making these decisions, preserve the constitutional principles and choose the smallest solution that supports genuine use.

---

## 30. v0.2 approved scope and milestone plan

v0.2 adds one practical numeric forecasting model and explicit Forecast Reviews to the completed binary application. It is an additive release: existing binary predictions, revisions, resolutions, analytics, backups, and exports must continue to work without reinterpretation or data loss.

### 30.1 Included in v0.2

- Numeric Predictions using one central prediction interval per immutable revision.
- Signed, exact, fixed-precision quantities with a user-supplied unit label.
- A required median estimate and whole-number confidence from 1% through 99%.
- Numeric creation, revision, journal, timeline, visualization, lifecycle, resolution, browsing, dashboard, and analytics workflows.
- Forecast Reviews for binary and numeric predictions, allowing the user to record deliberate reconsideration without fabricating a changed forecast.
- Type-aware backup, CSV export, restart, migration, and private frozen-build verification.

### 30.2 Numeric Prediction definition and value representation

A Numeric Prediction has these required enduring fields:

- Question;
- unit label; and
- decimal precision.

The unit describes the quantity in the user's own language, such as `days`, `books`, `USD`, or `messages`. Reckonsolve does not maintain a conversion system or infer relationships between differently spelled units.

Numeric values may be negative, zero, or positive. They use exact base-ten fixed precision rather than binary floating-point. Whole numbers are the default through precision zero, while a user who genuinely needs decimals may deliberately choose a supported number of decimal places. The same precision applies to every bound, median, and actual outcome for that Prediction. Milestone 13 must select and document a modest technical upper bound on decimal places.

Unit and precision are part of the enduring quantity definition and cannot be edited after creation. If either was defined incorrectly or the quantity itself changes materially, the honest workflow is to mark the old Prediction Invalid when appropriate and create a new one.

### 30.3 Central prediction interval contract

Each Numeric ForecastRevision contains exactly:

- an inclusive lower bound;
- a required median estimate;
- an inclusive upper bound;
- a whole-number confidence level from 1% through 99%;
- an optional rationale;
- an immutable created timestamp; and
- a deterministic revision sequence.

The required ordering is:

```text
lower <= median <= upper
```

Equality is valid, especially for discrete quantities or narrow low-confidence intervals. The median is the user's central estimate: the user is expressing roughly equal probability above and below it. It is not automatically calculated as the arithmetic midpoint and need not be geometrically centered between the bounds.

The interval is central and equal-tailed. For confidence `c%`, the user is expressing `c%` probability inside the inclusive interval and `(100 - c) / 2%` in each tail. For example, an 80% interval leaves 10% below the lower bound and 10% above the upper bound.

Confidence may be any whole percentage from 1 through 99. Zero and 100 are excluded because they do not define a useful finite central interval and the proper interval score is undefined at 100%. The input should make multiples of 5 easy and offer especially convenient 50%, 80%, 90%, and 95% shortcuts without restricting manual entry.

### 30.4 Numeric revision and historical-integrity rules

Changing any of lower bound, median, upper bound, or confidence creates one new immutable Numeric ForecastRevision. One save changes all supplied forecast values atomically; it never edits an earlier revision in place.

Submitting values identical to the current revision does not create a revision. A Journal entry remains appropriate for evidence or reasoning that does not itself assert deliberate reconsideration. The dedicated Review action explicitly records that the current numeric interval was reconsidered and retained.

The normal revision operation must enforce lifecycle eligibility and optimistic concurrency both before and inside its transaction. A Journal entry must reference the exact type-appropriate revision that was current when the entry was created. Journal entries, corrections, and Reviews never create chart observations or change numeric forecast values.

### 30.5 Numeric creation, detail, timeline, and visualization

New Prediction gains an explicit Binary/Numeric type choice. Binary remains the familiar default so the existing quick path does not become more cumbersome.

Numeric quick creation requires only Question, unit, precision, lower bound, median, upper bound, and confidence. Existing optional rationale, metadata, dates, and tags remain behind **More details**. The Prediction and first Numeric ForecastRevision, including optional details and tags, are saved in one transaction.

Prediction Detail must make forecast type, unit, current interval, median, confidence, and lifecycle immediately legible. A concise presentation may read:

```text
80% interval: 3-21 days
Median estimate: 7 days
```

The unified timeline shows every numeric revision and its optional rationale, interleaved causally with anchored Journal entries and later Reviews. The numeric history visualization shows the lower and upper bounds as an interval band and the median as a distinct line or markers over stored time. It contains exactly one observation per Numeric ForecastRevision, handles one revision and equal or regressing timestamps, and retains the textual timeline as its exact nonvisual equivalent.

### 30.6 Numeric lifecycle, resolution, and scoring selection

Open, Locked, Resolved, Invalid, Forecast Deadline, Expected Resolution, Needs Attention, and Ready to Resolve retain their v0.1 meanings and become type-aware.

- Open Numeric Predictions accept normal revisions, Journal entries, and Forecast Reviews.
- Locked Numeric Predictions reject normal revisions and Forecast Reviews but accept Journal entries.
- Resolved and Invalid Numeric Predictions reject normal revisions, new Journal entries, and Forecast Reviews.
- Numeric resolution records the realized value at the Prediction's fixed precision, even when it falls outside the forecast interval.
- Resolution notes and Postmortem remain optional.
- Resolution captures exactly one final eligible Numeric ForecastRevision for scoring.
- Unresolved and Invalid Numeric Predictions are excluded from numeric scoring and calibration.
- Existing untouched-prediction deletion and meaningful-history safeguards apply to Numeric Predictions.

### 30.7 Numeric analytics

For one resolved Numeric Prediction with final eligible interval `[lower, upper]`, median `m`, actual value `y`, confidence fraction `c`, and `alpha = 1 - c`:

**Containment** is Yes when `lower <= y <= upper`, otherwise No. Because this result and the stated confidence are unitless, containment calibration may combine predictions with different quantities and units. The calibration view uses the same fixed ten confidence bands as the binary reliability view, reports the actual mean stated confidence, observed containment rate, and count for every nonempty band, and warns against conclusions from sparse data.

**Median absolute error** is `abs(m - y)`. It answers how far the central estimate missed in the Prediction's natural unit.

**Interval score** is a proper score that rewards narrow intervals while penalizing misses:

```text
(upper - lower)
+ (2 / alpha) * (lower - y), when y < lower
+ (2 / alpha) * (y - upper), when y > upper
```

Only the applicable miss term is added. Lower interval score is better. This is commonly called the interval or Winkler interval score.

Median absolute error, interval width, and interval score retain the quantity's unit. Reckonsolve may summarize them only within one exact unit label or for an individual Prediction. It must not present an overall raw score that averages days, dollars, counts, and other unlike quantities. No cross-unit normalization or composite numeric performance grade is part of v0.2.

All numeric analytics use exactly one final eligible revision per resolved Prediction. Tags and type/unit filters must define a consistent subset across headline numbers, tables, and charts.

The Analytics screen keeps Binary and Numeric results in separate labeled sections when **All types** is selected; it never invents a score that combines the two forecast models. The exact-unit selector is enabled only for the **Numeric** forecast-type view. With **All units** selected, Numeric containment calibration may use the complete unitless subset, but median absolute error, interval width, and interval score summaries remain explicitly unavailable. Choosing one exact unit applies that unit before the Numeric headline, table, chart, and raw averages are calculated. Tag, forecast-type, and unit filters combine rather than describing mismatched subsets.

### 30.8 Forecast Reviews

A Forecast Review is an immutable record that the user deliberately reconsidered the current forecast and retained it unchanged. It records:

- stable identifier;
- Prediction identifier;
- exact current type-appropriate ForecastRevision reference;
- created timestamp; and
- optional note.

A Review does not create or modify a ForecastRevision, change probability or numeric interval values, add a scoring observation, or add a probability/numeric-history chart marker. It appears in the unified timeline and preserves the reviewed forecast context.

For binary forecasts, the action may read **Still at 60%**. For numeric forecasts, it may read **Keep this interval**. After Reviews exist, Needs Attention uses the most recent eligible ForecastRevision or Forecast Review, whichever is later. Journal entries continue not to reset the Needs Attention clock.

A Review may be created only while the Prediction is Open. Locked, Resolved, and Invalid Predictions reject it both before and inside the save transaction. The action carries the exact reviewed revision and metadata-version context so a concurrent forecast or proposition edit is rejected rather than attached to stale context. Multiple deliberate Reviews of the same still-current revision are valid because each records a separate reconsideration and refreshes Needs Attention.

The Review note is optional. Cancelling creates no record. A saved Review is meaningful history, so the normal untouched-prediction Delete action is no longer available. Full review sessions, prompted checklists, concealed prior forecasts, and anti-anchoring workflows remain Later.

### 30.9 Implementation milestones

#### Milestone 13: Numeric domain and persistence foundation

- Choose and document the bounded decimal-precision representation.
- Add a safe migration for forecast type and type-specific numeric data without rewriting the completed v0.1 migrations.
- Introduce independently testable Numeric Prediction, Numeric ForecastRevision, and Numeric Resolution domain concepts.
- Preserve every existing binary row, invariant, query, and workflow through migration and restart.
- Prove exact signed decimal round trips, interval validation, confidence endpoints, immutability, and transaction rollback.

This milestone is intentionally foundation-heavy. It should not expose a half-working Numeric option in the UI.

#### Milestone 14: Numeric creation and current detail

- Add the Binary/Numeric creation choice while keeping Binary as the default quick path.
- Implement atomic Numeric creation with all required values and optional **More details** content.
- Display the current interval, median, confidence, unit, metadata, and lifecycle on Prediction Detail.
- Reopen the application and display the identical values after restart.

Acceptance demonstration:

> Create an 80% interval of 3-21 days with median 7 -> close -> reopen -> the same interval, median, confidence, precision, and unit remain.

#### Milestone 15: Numeric revisions, timeline, and history chart

- Append a revision when any numeric forecast value changes; reject a completely unchanged submission.
- Enforce stale-token and lifecycle checks transactionally.
- Show numeric revisions and anchored Journal entries in one causal timeline.
- Add the lower/upper interval band and median history visualization with an exact nonvisual equivalent.
- Verify that Journal creation/correction changes neither revision count nor chart observations.

#### Milestone 16: Numeric lifecycle, resolution, and scoring selection

- Apply Open, Locked, Resolved, Invalid, delete, and deadline behavior to Numeric Predictions.
- Resolve with an exact actual value, including an outcome outside the interval.
- Capture exactly one final eligible Numeric ForecastRevision.
- Preserve resolution, invalidation, restart, and transactional rollback behavior.

#### Milestone 17: Type-aware Dashboard and Predictions browser

- Render concise explicitly labeled Binary and Numeric summaries; Numeric rows
  show confidence interval, median, and unit rather than a percentage-only
  surrogate.
- Make search, status/type/tag filters, selection, and detail navigation work
  for both types.
- Include Numeric Predictions correctly in Needs Attention, Ready to Resolve,
  and Locked sections.
- Add the All types/Binary/Numeric forecast-type filter and combine it with
  search, status, and tag filtering.

#### Milestone 18: Numeric analytics

- Add containment calibration with mean confidence, observed containment, and count.
- Add median absolute error, interval width, and proper interval score views within one unit.
- Support type, tag, and unit filtering with consistent subsets.
- Explicitly prevent misleading cross-unit raw-score aggregation.
- Test final-eligible-revision selection, inclusive boundaries, misses on each side, confidence extremes, sparse bins, and exclusions independently of chart rendering.

#### Milestone 19: Forecast Reviews

- Permit Reviews only while Open and reject them while Locked, Resolved, or Invalid.
- Add immutable type-aware Reviews referencing the exact current revision.
- Show Reviews in the unified timeline without changing forecast values, revision history, charts, or scoring.
- Update Needs Attention to use the later of the last eligible revision and Review while leaving Journal behavior unchanged.
- Cover concurrency, cancellation, restart, and both Binary and Numeric workflows.

#### Milestone 20: v0.2 portability and hardening

- Verify backup and restart recovery across Binary, Numeric, and Review records.
- Extend the documented CSV ZIP to format version 2 with twelve relational CSV files, including type-specific Numeric revisions and outcomes plus Forecast Reviews.
- Exercise a real v0.1-shaped schema-version-8 database through every v0.2 schema version while preserving Binary history.
- Run the complete automated suite and private frozen-build smoke workflow across both forecast types and Reviews.
- Align README, architecture, decision records, and user-facing export documentation with implemented v0.2 behavior.

An installer, code signing, automatic updates, and public binary distribution remain separate Later work.

### 30.10 v0.2 acceptance criteria

v0.2 is not complete unless all of the following are true:

1. Every existing v0.1 binary workflow and historical record still behaves correctly.
2. A Numeric Prediction can be created from the required numeric fields without optional boilerplate.
3. Signed whole and supported decimal values round-trip exactly through restart, backup, and export.
4. Every Numeric ForecastRevision satisfies `lower <= median <= upper` and confidence 1% through 99%.
5. Any numeric forecast change appends one immutable revision; cancel and unchanged submission append none.
6. Journal entries retain the exact Binary or Numeric revision context and never change forecast values.
7. Numeric history contains exactly one interval/median observation per Numeric ForecastRevision.
8. Numeric lifecycle and deadline rules match their binary counterparts.
9. A Numeric Prediction can resolve to any valid actual value, including one outside its interval.
10. Each resolved Numeric Prediction contributes exactly one final eligible revision to numeric analytics.
11. Inclusive containment, median absolute error, and interval score are correct at boundaries and on both sides of a miss.
12. Cross-unit containment calibration is clearly unitless, while raw numeric errors and scores are never misleadingly aggregated across unlike units.
13. Forecast Reviews preserve exact context and change neither forecast history, chart observations, nor scoring observations.
14. Needs Attention uses the later of the latest eligible Revision or Open-state Review; Journal activity remains excluded.
15. Backup, export, migration, restart, and the private frozen build preserve both forecast types and Reviews.
16. Core workflows remain fully offline and single-user.

### 30.11 Explicitly outside v0.2

- More than one interval or confidence level in a single revision.
- Full probability distributions or arbitrary quantile sets.
- Automatic unit conversion, unit inference, or editing a Prediction's unit/precision after creation.
- A normalized or composite raw score across unlike units.
- Multiple-choice, dedicated date, conditional, or relational forecasts.
- Full Forecast Review sessions, prompted checklists, or anti-anchoring modes.
- Every feature already listed as Later in Section 4 unless separately promoted through an explicit specification revision.

---

## 31. v0.3 CLI companion product contract and milestone plan

v0.3 adds a source-distributed command-line companion to the completed desktop application. It is an additive interface to the existing product, not a replacement for the GUI and not a second forecasting system. The desktop interface must retain every completed v0.2 workflow and invariant.

The v0.3 user outcome is:

> A Prediction created or changed through either the desktop app or the matching CLI appears through the other interface because both use the same canonical local database and the same application operations.

This user experience is **shared local data**, not synchronization in the replication sense. v0.3 introduces no copy, merge, synchronization ledger, background process, server, account, or network dependency.

### 31.1 Shared-data and architecture contract

The desktop interface and CLI are two presentation layers over the same application and persistence boundaries:

```text
PySide6 desktop UI ---+
                      +--> Application operations --> Domain and analytics rules
Terminal CLI ---------+                |
                                       +--> SQLite data access --> Canonical database
```

Requirements:

- The CLI invokes the existing purpose-specific application operations and read models. It must not duplicate lifecycle, validation, concurrency, historical-integrity, scoring-selection, backup, or export rules.
- The CLI must not issue ad hoc SQL or treat the current forecast as independently mutable state.
- Each command opens the database selected by its application identity, applies the same migration registry and startup validation as the desktop app, performs its work, and closes the connection deterministically.
- A CLI invocation must never silently recreate, replace, copy, merge, or repair an unrecognized or incompatible database.
- The normal user-facing CLI does not select an arbitrary database. Tests may inject an explicit temporary database through an internal composition boundary and must never discover or open either real user database.
- No CLI-specific schema or persistence table should be added unless a later milestone demonstrates a correctness need. Interface state, prompt progress, and display preferences are not canonical product data.
- Core behavior remains fully offline and single-user.

### 31.2 Command identities and data locations

The four source entry points have deliberately paired identities:

| Command | Interface | Identity and canonical data |
|---|---|---|
| `reckonsolve` | Stable GUI | Reckonsolve at `%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3` |
| `reckonsolve-cli` | Stable CLI | The same stable Reckonsolve database |
| `reckonsolve-dev` | Development GUI | Reckonsolve Dev at `%LOCALAPPDATA%\Reckonsolve Dev\reckonsolve.sqlite3` |
| `reckonsolve-cli-dev` | Development CLI | The same isolated Reckonsolve Dev database |

The CLI command selects its identity before resolving its path. Stable and development data remain isolated: no command falls back between them or automatically copies or migrates records from one identity to the other. The CLI is console-native and must not open a Qt window or require construction of the desktop UI.

During source development, the expected commands are `uv run reckonsolve-cli-dev ...` and `uv run reckonsolve-dev`. The stable CLI entry point exists for the same installed source environment as `reckonsolve`; a separately packaged CLI executable is not a v0.3 requirement.

### 31.3 Command surface

v0.3 supports this coherent command family:

```text
reckonsolve-cli list [filters]
reckonsolve-cli show PREDICTION_ID
reckonsolve-cli create binary
reckonsolve-cli create numeric
reckonsolve-cli revise PREDICTION_ID
reckonsolve-cli journal PREDICTION_ID
reckonsolve-cli review PREDICTION_ID
reckonsolve-cli resolve PREDICTION_ID
reckonsolve-cli invalidate PREDICTION_ID
reckonsolve-cli delete PREDICTION_ID
reckonsolve-cli backup [DESTINATION]
reckonsolve-cli export-csv [DESTINATION]
```

`PREDICTION_ID` is the existing stable integer identifier. v0.3 does not add mutable aliases, slugs, or a second identifier namespace. The development command exposes the same subcommands and behavior under `reckonsolve-cli-dev`.

Every command and subcommand provides useful `--help`. The exact spelling of individual filter flags and prompts may be refined during its owning milestone, but the workflows and semantics in this section are binding.

### 31.4 Read workflows and textual history

`list` is side-effect free. Its default view includes every Prediction in deterministic newest-created-first order. Each row must make the following immediately legible:

- stable Prediction identifier;
- forecast type;
- derived lifecycle status;
- Question;
- type-appropriate current forecast summary;
- tags when present; and
- Needs Attention and Ready to Resolve indicators when applicable.

The command supports question-text search plus lifecycle-status, forecast-type, and single-tag filtering. These filters use the same meanings and logical-AND composition as the desktop Predictions browser. Empty databases and no-match results are distinguished from read failures.

`show PREDICTION_ID` is also side-effect free. It displays the current type-aware Prediction detail, nonempty optional metadata, dates, tags, lifecycle or terminal facts, and the complete exact textual history available in the desktop interface. That history includes immutable Binary or Numeric revisions, rationales, Journal entries and their correction status/history, Forecast Reviews, and Definition history. Stored instants display in the computer's local time; date-only values retain their saved calendar dates. Numeric values retain the Prediction's exact fixed precision and unit.

Terminal charts are not required. The textual history must remain sufficient to recover forecast values, order, timestamps, retained Review context, and type-appropriate resolution information without a visual plot.

### 31.5 Interactive mutation model

All v0.3 mutation commands are human-directed interactive workflows. They may accept the Prediction identifier or artifact destination as an argument, but they prompt for the substantive values needed to create historical or terminal records. v0.3 does not provide scripting-oriented noninteractive mutation flags.

Requirements:

- Intermediate prompts never write partial state. One completed application operation performs the mutation atomically after input is validated.
- Optional rationale, notes, metadata, dates, and tags remain skippable wherever the desktop contract makes them optional.
- v0.3 CLI prose prompts accept one terminal line per field. This includes revision rationales, Journal bodies, and Forecast Review notes. The limit keeps the companion optimized for rapid capture and does not impose a one-line domain or storage invariant: the desktop interface continues to create, preserve, and display multiline text.
- Cancelling, pressing Ctrl+C, reaching end-of-input before submission, or declining a required confirmation creates no record and reports cancellation without a traceback.
- Ordinary validation errors are explained in plain language and permit a safe retry when practical. Expected not-found, lifecycle, stale-context, lock-contention, path, migration, and storage failures produce a nonzero exit status without an unhandled traceback.
- Consequential terminal actions show the reviewed current forecast and explain their one-way v0.2 semantics before confirmation. Permanent deletion requires its own explicit confirmation.
- Mutations carry and transactionally recheck the same current-revision, metadata-version, and lifecycle context required by their underlying application operations. The CLI never weakens optimistic concurrency to make a command appear successful.

Machine-readable JSON output, output stability intended as a public scripting API, shell completion, and bulk or piped mutation workflows are deferred. Human-readable output may evolve within v0.3 while remaining calm, concise, and usable in ordinary Windows terminals.

### 31.6 Creation and active forecasting workflows

`create binary` prompts for Question and whole-number probability from 0% through 100%. `create numeric` prompts for Question, unit, decimal precision, exact lower bound, median, upper bound, and whole-number confidence from 1% through 99%. Both flows offer the existing optional rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags without making them boilerplate. Creation persists the Prediction, first type-appropriate ForecastRevision, metadata, and tags in the existing atomic operation.

`revise PREDICTION_ID` infers the immutable forecast type and shows the reviewed current forecast before asking for a replacement. Binary and Numeric validation, rationale behavior, unchanged-submission rejection, Open-only revision eligibility, deadline handling, append-only history, and stale-context checks remain exactly as specified for the desktop app.

`journal PREDICTION_ID` records a required Journal body against the exact current type-appropriate revision. It is available while Open or Locked, creates no ForecastRevision, changes no forecast value, and does not reset Needs Attention.

`review PREDICTION_ID` shows the current type-appropriate forecast, accepts an optional note, and records an immutable Review of the unchanged revision. It is available only while Open, creates no ForecastRevision or chart/scoring observation, and resets Needs Attention under the existing rule.

These commands use the same operation result and refreshed read model that the desktop interface would use. Repeating a command after success must not duplicate the earlier mutation automatically; a new invocation represents a new explicit user action.

### 31.7 Lifecycle and data-management workflows

`resolve PREDICTION_ID` infers forecast type and requires a type-appropriate outcome: Yes or No for Binary, or one exact realized value at the Prediction's fixed precision for Numeric. Optional factual Resolution notes and Postmortem remain separate. The command captures exactly one final eligible scoring revision and preserves the existing one-way terminal contract.

`invalidate PREDICTION_ID` accepts an optional reason, explains that the Prediction will remain in history and be excluded from scoring, and requires confirmation before the existing atomic invalidation operation runs.

`delete PREDICTION_ID` is available only for a transaction-current untouched Open Prediction under Section 19. It explains that deletion is permanent, requires explicit confirmation, and rechecks all eligibility inside the deletion transaction. Meaningful, Locked, Resolved, or Invalid history is rejected rather than erased.

`backup` and `export-csv` invoke the existing complete SQLite-backup and relational CSV-ZIP operations. A destination may be supplied or prompted for. Cancel or failure must not replace an existing artifact, and only a successfully installed and verified backup advances the saved last-successful-backup time. CLI export remains CSV format version 2 unless the underlying product export contract is separately revised.

### 31.8 Multiple-process and refresh behavior

The GUI and CLI may be open at the same time, with each process owning its own SQLite connection. Simultaneous reads are supported. Sequential writes are the normal and recommended workflow.

Every write retains SQLite's bounded busy handling, immediate transaction boundary, database constraints, and application-level stale-context rechecks. If another process holds the write lock or changes the reviewed Prediction first, the command must fail clearly and leave canonical data intact; it must not silently overwrite, merge, or indefinitely retry. The user can inspect the current record and deliberately run the action again.

v0.3 does not promise push-based live updates to an already rendered GUI screen. A CLI change appears when the desktop app next starts, navigates, or performs its normal refresh; a GUI change appears on the next CLI invocation. No file watcher, daemon, inter-process message bus, or synchronization service is introduced.

### 31.9 Output and compatibility requirements

- Read results go to standard output; expected errors and cancellation explanations use standard error where appropriate.
- Success exits with status zero. Validation, not-found, lifecycle, concurrency, database, and artifact failures exit nonzero. A detailed public exit-code taxonomy is not part of v0.3.
- Free text is treated as text, not terminal markup. The CLI must not interpret Question, rationale, Journal, Review, notes, or Postmortem content as commands or formatting instructions.
- Output must remain understandable without ANSI color and usable in PowerShell and Windows Terminal. Decorative color may not be the only carrier of meaning.
- Exact historical timestamps, date-only semantics, whole-number probabilities and confidence, and fixed-precision Numeric quantities must not be rounded or reformatted misleadingly.
- Existing v0.2 databases must open without reinterpretation or data loss. If v0.3 requires no schema change, the schema remains version 12; any demonstrated migration need must follow the existing immutable migration discipline.
- Desktop behavior, backup recoverability, CSV format honesty, and the private GUI smoke build must remain intact throughout v0.3.

### 31.10 Implementation milestones

#### Milestone 21: CLI foundation, identity, and read model

- Add `reckonsolve-cli` and `reckonsolve-cli-dev` source entry points with shared command composition and paired stable/development identities.
- Open, validate, migrate, and close the identity-selected database without constructing the PySide6 interface.
- Implement command help, version reporting, `list`, its combined filters, and type-aware `show` with complete textual history.
- Preserve unambiguous empty, no-match, not-found, startup-failure, and expected-error output.
- Prove stable/development path selection, explicit temporary-path test injection, read-only behavior, exact Numeric formatting, local-time display, and GUI/CLI visibility against one shared temporary database.

Acceptance demonstration:

> Create Binary and Numeric Predictions through existing application operations -> run the matching CLI list and show commands -> both current forecasts and their full histories appear exactly, while the other identity's database remains untouched.

#### Milestone 22: Type-aware interactive creation

- Implement `create binary` and `create numeric` through existing atomic application operations.
- Preserve the Binary quick path, exact Numeric validation, optional details, tags, deadlines, and cancellation behavior.
- Return the new stable Prediction identifier and a concise type-appropriate forecast summary after success.
- Prove that CLI-created records survive restart and appear unchanged in the matching desktop interface.

Acceptance demonstration:

> Create one Binary and one Numeric Prediction through `reckonsolve-cli-dev` -> open `reckonsolve-dev` -> both records, first revisions, optional details, and tags appear in the GUI.

#### Milestone 23: Revisions, Journal entries, and Forecast Reviews

- Implement type-aware `revise`, `journal`, and `review` commands.
- Show reviewed context before mutation and reuse all existing unchanged-value, lifecycle, deadline, immutable-history, anchor, Review, freshness, and optimistic-concurrency rules.
- Keep Ctrl+C, end-of-input, validation failure, and rejected stale context side-effect free.
- Prove GUI-to-CLI and CLI-to-GUI timeline visibility for both forecast types without adding false revision, history-chart, or scoring observations.

#### Milestone 24: Terminal lifecycle and guarded deletion

- Implement type-aware `resolve`, `invalidate`, and `delete` commands with plain-language confirmation.
- Preserve final eligible scoring-revision capture, exact Numeric outcomes, optional Resolution notes/Postmortem, Invalid exclusion, and one-way terminal behavior.
- Enforce untouched-Open deletion eligibility inside the transaction and direct meaningful history toward Invalid rather than erasure.
- Test cancellation, deadline boundaries, stale context, lock contention, terminal rejection, restart, and both forecast types.

#### Milestone 25: Backup, export, cross-interface hardening, and v0.3 closure

- Implement CLI backup and CSV export through the existing verified transfer operations.
- Exercise source and destination failure safety, canonical-database destination rejection, last-successful-backup behavior, and format-version-two export contents.
- Add independent-connection tests for simultaneous reads, sequential cross-interface writes, write-lock failure, stale reviewed context, restart, migration, and stable/development isolation.
- Run the complete automated suite and the existing private GUI frozen-build smoke workflow so the additive CLI cannot regress v0.2.
- Align README, architecture, decision records when warranted, command help, and release documentation with the implemented source CLI.
- Close v0.3 as a source release; do not turn this milestone into a separately packaged CLI binary, installer, signing, or public binary-distribution project.

Implementation result:

> `backup` and `export-csv` accept an optional destination or prompt with the existing timestamped suggestion, then invoke the same verified SQLite and relational CSV operations used by Settings. Source/destination failures remain nonzero and artifact-safe; backup success alone advances the saved backup time. Independent-connection tests retain simultaneous reads, sequential cross-interface writes, bounded lock failure, stale-context rejection, restart, migration, and identity isolation. The complete v0.3 workflow remains a version-12, offline, single-user source release.

### 31.11 v0.3 acceptance criteria

v0.3 is not complete unless all of the following are true:

1. `reckonsolve-cli` and `reckonsolve` open the same stable canonical database, while both development commands share a separate development database.
2. A record created or changed in the GUI is visible on the next matching CLI invocation, and a record created or changed in the CLI is visible on the next matching GUI load or refresh.
3. `list` and `show` represent Binary and Numeric forecasts, lifecycle, tags, attention indicators, exact history, and terminal facts without rewriting or flattening them.
4. Read commands never mutate product data, including timestamps, settings, or migration state when no migration is pending.
5. CLI Binary and Numeric creation use the same required fields, optionality, exactness, and atomicity as desktop creation.
6. CLI revisions append exactly one changed type-appropriate ForecastRevision; unchanged, cancelled, stale, Locked, and terminal attempts append none.
7. CLI Journal entries retain their exact current revision context and do not change forecasts or freshness.
8. CLI Forecast Reviews are Open-only, retain an unchanged exact forecast context, reset freshness, and create no revision, chart, or scoring observation.
9. CLI Resolution captures exactly one final eligible type-appropriate scoring revision and preserves exact Numeric outcomes.
10. CLI Invalidation preserves history and excludes the Prediction from scoring; guarded deletion removes only an explicitly confirmed untouched Open Prediction.
11. Expected validation, lifecycle, concurrency, startup, migration, path, backup, and export failures are clear, nonzero, and historically safe.
12. Simultaneous reads and normal sequential GUI/CLI writes preserve one canonical history; conflicting writes never silently overwrite or merge records.
13. CLI backup is recoverable and CLI CSV export retains the complete v0.2 relational format and safety guarantees.
14. All automated checks and the existing private GUI smoke build pass without using either real user database.
15. All v0.2 desktop workflows and records retain their prior behavior.
16. The complete v0.3 source workflow remains offline and single-user.

### 31.12 Explicitly outside v0.3

- Original Reckonsolve logo or application-icon artwork.
- A separately frozen or installed CLI executable, installer integration, shell shortcuts, code signing, automatic updates, or public binary distribution.
- Live GUI refresh triggered by CLI writes, file watching, a resident daemon, inter-process messaging, database replication, merge logic, cloud sync, or hosted storage.
- JSON or Markdown export, machine-readable command output, a stable scripting API, noninteractive mutation flags, bulk import, or piped batch operations.
- Shell completion, a curses/Textual-style TUI, interactive terminal charts, or reproducing the desktop Analytics screen in the terminal.
- CLI metadata editing, Definition-history creation, Journal-entry correction, settings editing, or terminal-record correction/reopening.
- An arbitrary normal-user database selector or automatic movement between stable and development data.
- New forecast models, scoring methods, notifications, reminders, or any other Later feature not explicitly promoted in this section.

---

## 32. v0.4 resolution integrity and learning product contract and milestone plan

v0.4 strengthens what happens after an outcome becomes known. It is an additive release over the completed v0.3 desktop and CLI application: every existing Binary, Numeric, Journal, Review, lifecycle, shared-data, backup, and export invariant remains in force unless this section explicitly extends it.

The v0.4 user outcome is:

> Resolve quickly when the outcome is known, correct an honest mistake without erasing the original record, return to reflection later, and compare the first forecast with the final scoring forecast without pretending that every revision was a separate prediction.

v0.4 does not make terminal states reversible. It adds audited corrections to facts attached to a terminal decision while preserving the decision, its original time, and its scoring context.

### 32.1 Included scope and governing invariants

v0.4 includes:

- append-only correction of a Resolved Prediction's type-appropriate outcome, factual Resolution notes, and Postmortem;
- append-only correction of an Invalid Prediction's reason, without changing its terminal state;
- the ability to add or revise one displayed Postmortem after resolution while retaining every earlier version;
- a lightweight **Needs Postmortem** Dashboard queue with an explicit **Skip Postmortem** completion action;
- type-aware scorecards on resolved Prediction Detail;
- initial-versus-final update analytics that treat each eligible Prediction as one paired observation;
- read-only CLI visibility for the new terminal history;
- CSV export format version 3, migration, backup, recovery, and private-build hardening for the new records.

The following invariants govern the entire release:

- A Resolved Prediction remains Resolved and an Invalid Prediction remains Invalid.
- Neither terminal workflow reopens forecasting, permits a new ForecastRevision, or permits a new Journal entry or Forecast Review.
- The original resolution or invalidation record and its original timestamp remain immutable.
- A Resolution's captured scoring ForecastRevision remains immutable, even when the recorded outcome is corrected.
- Every accepted correction appends a timestamped record. No correction overwrites or deletes an earlier terminal fact or correction.
- The latest correction determines the effective displayed and analytical value, but the original and all superseded values remain inspectable.
- Each resolved Prediction still contributes exactly one observation to ordinary scoring and calibration.
- Correction, Postmortem, and Postmortem-completion records are not ForecastRevisions, Reviews, chart observations, or additional scoring observations.
- All new writes are atomic, enforce lifecycle ownership and optimistic concurrency inside the transaction, and leave no partial history after cancellation or failure.

### 32.2 Resolution and invalidation correction contract

A **Resolution correction** may change one or more of these fields in one atomic save:

- Binary outcome or exact Numeric actual value;
- factual Resolution notes; and
- Postmortem.

The correction record contains:

- a stable identifier and Resolution reference;
- a snapshot of the before and after values for all three type-appropriate fields;
- an explicit indication of which fields changed;
- its own canonical UTC timestamp; and
- a correction reason when required below.

Multiple corrections are permitted and form deterministic append-only history. A no-op submission creates no record. Clearing optional Resolution notes or Postmortem is a recorded change rather than deletion of their history. Numeric actual values retain the Prediction's exact fixed precision and never pass through binary floating point.

Changing a Binary outcome or Numeric actual value requires a short nonempty correction reason because that change alters scoring and calibration. A correction that changes only Resolution notes or Postmortem requires no separate reason. If one atomic correction changes the outcome and text, the outcome-change reason applies to the whole correction record.

The correction interface must show the currently effective terminal information, explain that the original remains in history, identify a score-affecting outcome change, and require deliberate confirmation before saving. Prediction Detail shows the latest effective values and makes the complete original-to-current correction history available without letting the audit material overwhelm the primary resolution summary.

An **Invalidation reason correction** may change or clear only the reason attached to an Invalid Prediction. It appends before and after reason text with its own timestamp, requires no separate correction reason, and preserves the original invalidation reason and every superseded version. It cannot change Invalid to Resolved, substitute an outcome, alter the invalidation timestamp, or reopen the Prediction.

### 32.3 Later and correctable Postmortems

A Prediction has one displayed Postmortem, not a sequence of separate post-resolution Journal entries. Its effective text is the latest value from the original Resolution plus any append-only Resolution corrections.

The Postmortem remains optional at resolution. After resolution, the desktop interface permits the user to:

- add the first Postmortem when the original Resolution left it blank;
- correct an existing Postmortem; or
- clear it while retaining its complete earlier text history.

These actions use the Resolution-correction contract in Section 32.2. They do not change the original resolution timestamp, scoring ForecastRevision, outcome unless explicitly included in the same confirmed correction, lifecycle state, or historical timeline position of the Resolution.

Resolution notes remain factual provenance and Postmortem remains reflective analysis. The interface should preserve that distinction without forcing either kind of text.

### 32.4 Needs Postmortem completion workflow

**Needs Postmortem** is a Dashboard attention queue, not a canonical lifecycle state and not a scoring classification. A Prediction appears in it when all of the following are true:

- it is Resolved;
- its effective Postmortem is blank; and
- no explicit Postmortem-skip record exists.

The queue has no waiting period and does not reuse the configurable Needs Attention threshold. It may overlap no nonterminal action bucket because only Resolved Predictions qualify. Each row identifies forecast type, Question, outcome, and original resolution time and opens the matching Prediction Detail view.

**Skip Postmortem** records one immutable timestamped completion fact. It means that the user deliberately considers reflection complete without writing prose; it does not alter the Resolution, score, lifecycle, or original terminal timestamp. A later Postmortem may still be added, and the preserved skip fact remains part of history. A Prediction leaves the queue when it has either a nonempty effective Postmortem or a skip record.

The queue and Skip action must remain calm and optional. v0.4 adds no notification, reminder, penalty, required explanation, or mandatory Postmortem.

### 32.5 Resolved Prediction scorecards

Prediction Detail gives every Resolved, scored Prediction a concise type-aware scorecard based on its immutable scoring ForecastRevision and latest effective outcome.

For Binary Predictions, the scorecard shows:

- the scored Yes probability;
- the effective Yes or No outcome;
- the individual Brier score; and
- a plain-language reminder that lower is better.

For Numeric Predictions, the scorecard shows:

- the scored interval, confidence, median, and exact unit;
- the effective actual value;
- inclusive containment;
- median absolute error;
- interval width; and
- proper interval score, with lower-is-better guidance where applicable.

If an outcome has been corrected, the scorecard recomputes from the latest effective outcome exactly once and visibly indicates that correction history exists. The captured scoring ForecastRevision never changes. Invalid and unresolved Predictions receive no scorecard, and Postmortem completion has no scoring effect.

### 32.6 Initial-versus-final update analytics

v0.4 adds retrospective feedback about how the final scoring forecast compared with the initial forecast. It is descriptive hindsight, not proof that an update caused improvement or that the same strategy will work on future questions.

For this feature:

- **initial** means the first type-appropriate ForecastRevision for the Prediction;
- **final** means the exact ForecastRevision captured by its Resolution for scoring;
- the primary update-analysis population contains only Resolved Predictions for which initial and final are different revisions;
- Resolved Predictions with only one revision are reported separately as unrevised rather than included as zero-change pairs;
- Invalid and unresolved Predictions are excluded;
- each eligible Prediction contributes exactly one initial/final pair; and
- intermediate revisions are not scored or aggregated in v0.4.

For a lower-is-better score, **score improvement** is:

```text
initial score - final score
```

A positive value means the final forecast scored better against the realized outcome, zero means no score difference, and a negative value means it scored worse.

Binary update analytics compare initial and final Brier scores and summarize the paired score improvement with sample count and sparse-data guidance.

Numeric update analytics may combine units only for unitless containment feedback. They show initial and final confidence and containment honestly rather than implying that containment alone is calibration. Median absolute error, interval width, and interval-score comparisons are available only within one exact unit label. A reduction in width is described as narrowing, not automatically as improvement; proper interval score supplies the width-and-miss performance comparison.

Analytics use the latest effective outcome after any correction while retaining the original Resolution timestamp as the Prediction's position in resolution-time views. The later correction timestamp remains visible in history but does not make the Prediction appear newly resolved.

Tag, forecast-type, and exact-unit filtering retain their existing logical meanings. Every headline, table, and chart in an update view must describe the same filtered paired population, show its count, and avoid claims of causal update skill from sparse or heterogeneous observations.

### 32.7 Desktop, CLI, portability, and compatibility boundaries

Resolution correction, Invalidation-reason correction, later Postmortem editing, and Skip Postmortem are desktop mutation workflows in v0.4. The existing CLI may still supply an original optional Postmortem while performing its established `resolve` command, but v0.4 adds no CLI command that mutates a terminal record or Postmortem completion.

`reckonsolve-cli show PREDICTION_ID` becomes a read-only textual equivalent for the new history. It displays original terminal facts, current effective values, every correction with reason and timestamp, Postmortem version history, and any Skip Postmortem completion fact without flattening them into an apparent overwrite. The shared stable/development data identities, sequential-write guidance, bounded lock handling, and normal GUI/CLI refresh behavior remain unchanged.

The complete SQLite backup contract remains unchanged: a verified backup must contain every new canonical record and reopen with the same effective values and history.

CSV export advances to **format version 3**. It retains every format-version-two file and adds relational records for:

- Resolution corrections;
- Invalidation-reason corrections; and
- Postmortem completion.

The version-three README documents how to derive effective terminal values from original and correction records, how score-affecting outcome corrections are identified, and how exact Numeric before/after values are represented. Export must preserve stable relationships, original and correction timestamps, before/after text, changed-field information, and required outcome-correction reasons. It remains an analytical export rather than a restoration format and retains the existing consistent-read and destination-safety guarantees.

Existing schema-version-12 v0.3 databases must migrate forward without reinterpreting or replacing any Prediction, ForecastRevision, Review, Journal, Resolution, Invalidation, tag, setting, or export meaning. Automated tests must exercise a real version-12-shaped database through every v0.4 migration and recovery path.

### 32.8 Implementation milestones

Milestones 26 through 31 are implemented in v0.4.0.

#### Milestone 26: Terminal-correction domain and persistence foundation

- Add safe append-only persistence for type-aware Resolution corrections, Invalidation-reason corrections, and Postmortem completion.
- Introduce independently testable effective-terminal-value derivation without mutating original terminal rows.
- Enforce exact Numeric representation, outcome-reason requirements, no-op rejection, deterministic correction ordering, and immutable scoring-revision ownership.
- Preserve one-way terminal lifecycle behavior and prove atomic rollback, optimistic concurrency, restart, and migration from the completed v0.3 schema.
- Keep this foundation out of the UI until the historically complete operations and read models are ready.

#### Milestone 27: Audited terminal correction and later Postmortem workflows

- Add desktop correction workflows for Binary and Numeric Resolutions and Invalid reasons.
- Require an explanation for outcome or actual-value corrections while keeping text-only corrections lightweight.
- Permit Postmortems to be added, corrected, or cleared after resolution through the same append-only contract.
- Show current effective terminal information and complete correction history on type-aware Prediction Detail.
- Confirm score-affecting changes and reject cancellation, no-op, stale, conflicting, or wrong-lifecycle attempts without partial history.

Acceptance demonstration:

> Resolve a Prediction with an incorrect outcome and no Postmortem -> correct the outcome with an explanation -> add a Postmortem later -> restart -> the original Resolution, both later changes, unchanged scoring ForecastRevision, and corrected effective score all remain visible.

#### Milestone 28: Resolved Prediction scorecards

- Add concise Binary and Numeric scorecards to Resolved Prediction Detail.
- Use exactly the captured scoring ForecastRevision and latest effective outcome.
- Preserve inclusive Numeric containment, exact-unit raw metrics, and clear lower-is-better explanations.
- Recompute after an outcome correction without adding a scoring observation or changing the Resolution's historical position.
- Cover endpoints, exact boundaries, misses on both sides, corrected outcomes, restart, and Invalid/unresolved exclusion independently of visual rendering.

#### Milestone 29: Initial-versus-final update analytics

- Add paired initial-versus-final Binary Brier feedback for revised-and-resolved Predictions.
- Add unitless Numeric containment feedback plus exact-unit median-error, width, and interval-score comparisons.
- Report unrevised Resolved Predictions separately and exclude them from the primary score-difference population.
- Use one pair per eligible Prediction, omit intermediate-revision hindsight aggregation, and retain existing filters and corrected-outcome behavior.
- Label the view as retrospective feedback, show counts and sparse-data cautions, and make no causal claim that updating itself produced the result.

#### Milestone 30: Needs Postmortem workflow

- Add the Resolved-only **Needs Postmortem** Dashboard section and count.
- Remove a Prediction from the queue when its effective Postmortem is nonempty or an explicit Skip record exists.
- Add a deliberate **Skip Postmortem** action that records completion without changing lifecycle or scoring.
- Preserve navigation, restart, outcome corrections, later Postmortem creation, and empty-state behavior for both forecast types.
- Keep the workflow optional and separate from Needs Attention thresholds, notifications, and analytics.

#### Milestone 31: v0.4 portability, CLI read support, and hardening

- Extend CLI `show` with complete original, effective, correction, Postmortem, and completion history while adding no terminal-mutation command.
- Advance relational CSV export to format version 3 and verify all new relationships, exact Numeric values, derivation instructions, and artifact-safety behavior.
- Prove complete SQLite backup and recovery, version-12 migration, restart, stable/development isolation, simultaneous reads, sequential cross-interface writes, bounded lock failure, and stale-context rejection.
- Run the complete automated suite and private GUI frozen-build smoke workflow across corrected Binary and Numeric outcomes, later Postmortems, scorecards, update analytics, and Needs Postmortem.
- Align README, architecture, decision records, command help, changelog, and release documentation with the implemented v0.4 behavior.
- Close v0.4 as a source release without expanding the milestone into logo work, a Windows installer, signing, automatic updates, or public binary distribution.

### 32.9 v0.4 acceptance criteria

v0.4 is not complete unless all of the following are true:

1. Every completed v0.3 desktop and CLI workflow retains its prior behavior unless this contract explicitly extends it.
2. Correcting a Binary outcome or exact Numeric actual value appends history and requires a nonempty explanation.
3. Correcting only Resolution notes, Postmortem, or an Invalidation reason appends history without requiring a separate explanation.
4. Original terminal values, terminal timestamps, and every superseded correction remain inspectable after restart.
5. Resolution corrections never change the captured scoring ForecastRevision, reopen a Prediction, or permit new forecasting activity.
6. An Invalid Prediction can correct only its reason and can never become Resolved through a v0.4 workflow.
7. The latest effective outcome is used exactly once in individual and aggregate scoring while the original outcome remains in correction history.
8. A Postmortem may be omitted at resolution, added later, corrected repeatedly, or cleared without creating a Journal entry or rewriting prior text.
9. Needs Postmortem contains exactly the Resolved Predictions with neither an effective Postmortem nor a Skip record.
10. Skip Postmortem records an immutable completion fact and changes neither score nor lifecycle.
11. Every Resolved Prediction scorecard uses its captured scoring ForecastRevision and latest effective outcome; Invalid and unresolved Predictions receive none.
12. Update analytics use exactly one initial/final pair per revised-and-resolved Prediction and never treat intermediate revisions as independent observations.
13. Unrevised Resolved Predictions are reported separately rather than diluting paired score differences with artificial zero-change observations.
14. Binary score improvement uses initial Brier minus final Brier and explains that positive is better.
15. Numeric containment feedback may combine units, while raw error, width, and interval-score comparisons never combine unlike units.
16. Corrected outcomes retain the original resolution-time position in time-based analytics and expose the later correction time only as history.
17. CLI `show` represents original and effective terminal facts, all correction history, and Postmortem completion without mutating them.
18. Backup, export format version 3, migration, restart, and the private frozen build preserve every new record and relationship.
19. Cancellation, no-op, stale-context, lifecycle, lock, migration, and artifact failures are historically safe and leave no partial correction.
20. The complete v0.4 workflow remains offline, local-first, and single-user.

### 32.10 Explicitly outside v0.4

- Reopening a Resolved or Invalid Prediction or returning it to Open or Locked.
- Changing a Resolution's captured scoring ForecastRevision or original resolution timestamp.
- Changing an Invalid Prediction into a Resolved Prediction or attaching a scored outcome to it.
- Deleting original terminal records, corrections, Postmortem history, or completion facts through the normal application.
- Aggregate hindsight scoring of every intermediate ForecastRevision or treating revisions as independent observations.
- A causal claim or generalized forecast-updating skill grade derived from initial-versus-final differences.
- Mandatory Postmortems, automatic reminders, notifications, penalties, or a Postmortem deadline.
- CLI mutation of Resolution corrections, Invalidation-reason corrections, later Postmortems, or Skip Postmortem.
- A comprehensive audit trail for all mutable metadata.
- New forecast types, new scoring rules, multiple intervals, full probability distributions, or automatic unit conversion.
- Full-text search, Collections, structured Sources/Evidence, attachments, prediction graphs, or advanced Forecast Review sessions.
- JSON or Markdown export, machine-readable CLI output, a scripting API, bulk import, or noninteractive mutation flags.
- Logo or application-icon creation, a normal Windows installer, code signing, automatic updates, or public binary distribution.
- Accounts, cloud sync, sharing, collaboration, or required network access.

---

## 33. v0.5 retrieval and organization product contract and milestone plan

v0.5 makes a larger Reckonsolve journal easy to find and organize without introducing a hosted search service, opaque recommendation system, or second source of truth. It promotes the previously deferred full-text-search work and strengthens the existing Predictions archive while preserving every completed Binary, Numeric, desktop, CLI, lifecycle, history, analytics, backup, and export invariant.

The release promise is:

> Recall the words you remember, find the right Prediction quickly, understand why it matched, and never mistake superseded text for the current record.

### 33.1 Included scope and governing invariants

v0.5 includes:

- local full-text search across the user-authored Prediction corpus defined in Section 33.2;
- explainable relevance ranking, source-labeled snippets, one grouped result per Prediction, and contextual navigation from a match to Prediction Detail;
- safe all-word, any-word, phrase, prefix, literal-substring, and spelling-suggestion behavior without exposing raw search-engine syntax;
- an explicit opt-in for superseded historical text while current and effective text remains the default;
- richer archive filtering, multiple-tag matching, deterministic sorting, and clear reset and empty states;
- dynamic Saved Views that retain a search-and-filter configuration without copying or freezing result membership;
- deliberate global tag rename, merge, and delete workflows with affected-record counts and transactional safeguards;
- read-only CLI search and Saved View execution through the same application query and canonical database as the matching GUI identity;
- a rebuildable local search index, migration, backup, restart, stable/development, cross-interface, and private-build hardening; and
- a repeatable relevance corpus and regression process that treats retrieval quality as release behavior rather than incidental SQL output.

The following invariants govern every v0.5 feature:

- SQLite remains the only canonical store. A search index is derived data and may never become the sole copy of any user text or relationship.
- Search, filtering, sorting, opening a result, and running a Saved View are read-only. They do not create history, change lifecycle, reset Needs Attention, advance metadata versions, or alter timestamps.
- Search results group matches by Prediction. Multiple matching fragments never make one Prediction appear to be several independent records.
- Relevance changes presentation order only. It never changes the canonical archive, timeline order, scoring-revision selection, or analytical population.
- Superseded text is excluded from normal search unless the user deliberately includes history, and every historical-only match is labeled as superseded.
- Structured status, forecast type, tag, date, and attention facts remain filters. They are not inferred from prose or persisted as search-engine truth.
- Binary and Numeric forecasts retain their completed type-specific creation, revision, lifecycle, resolution, scorecard, and analytics behavior.
- Saved Views are ordinary mutable organizational preferences, not forecast history, Collections, or snapshots of Prediction identifiers.
- Tag-library maintenance may change current tag metadata and associations but never edits a ForecastRevision, Journal version, Definition snapshot, Review, terminal fact, correction, score, or Postmortem completion.
- Every canonical write that changes searchable content and every corresponding search-index update commit atomically or roll back together.
- A missing, stale, incompatible, or damaged search index must produce an explicit repairable condition, never a false empty result set.
- All v0.5 behavior remains offline, single-user, and shared only between the paired stable or development GUI and CLI database identities.

### 33.2 Searchable corpus and historical semantics

Normal search covers the current or effective user-authored text of a Prediction plus every immutable text record that remains a genuine part of its forecasting history.

The default searchable corpus includes:

- current Question;
- current tag labels;
- current Background;
- current Resolution Criteria;
- every nonempty Binary or Numeric ForecastRevision rationale, including the initial rationale;
- every nonempty Forecast Review note;
- the effective body of every Journal entry after replaying any transparent corrections;
- effective Binary or Numeric Resolution notes;
- the effective Postmortem;
- the effective Invalidation reason; and
- every required explanation attached to a score-affecting Resolution correction.

Forecast rationales and Review notes are not superseded merely because a later forecast exists. Each remains an honest time-specific statement and stays in default search. A Journal entry contributes only its effective body by default, while its original timestamp, forecast anchor, and complete correction chain remain canonical. Resolution notes, Postmortem, and Invalidation reason likewise contribute only their latest effective values by default.

The **Include superseded history** option additionally searches:

- earlier Question and Resolution Criteria values preserved by Definition history;
- original and superseded Journal bodies;
- original and superseded Resolution-note and Postmortem values; and
- original and superseded Invalidation reasons.

Historical search does not invent history for fields that Reckonsolve never audited. Background, Expected Resolution, and tag associations therefore expose only their current values. Date values, probabilities, Numeric interval values, outcomes, statuses, and Postmortem-completion facts are rendered or filtered as structured information rather than indexed as undifferentiated prose.

Each searchable fragment has a stable source classification and enough relational identity to locate its canonical owner. At minimum, result sources distinguish:

- Current Question;
- Tag;
- Background;
- Resolution Criteria;
- Forecast rationale with type and revision sequence;
- Forecast Review note;
- Journal entry;
- Resolution notes;
- Postmortem;
- Invalidation reason;
- outcome-correction explanation; and
- each corresponding superseded historical source when history is included.

Repeated snapshots or correction rows must not create visually duplicate matches for unchanged text. Search projection may deduplicate identical derived fragments, but it may not delete or coalesce the underlying canonical history.

### 33.3 Query and matching contract

The user enters ordinary text rather than SQLite FTS syntax. Reckonsolve owns query parsing, quoting, validation, and normalization, and arbitrary punctuation must never turn a normal search into a database syntax error.

Matching follows these rules:

- Surrounding whitespace is ignored. A blank query applies no text constraint and retains normal archive browsing.
- Matching is Unicode-aware and case-insensitive. Equivalent ordinary Latin characters with or without common diacritics should match.
- Unquoted words use **All words** by default. Every word must occur somewhere within the same Prediction, but different words may occur in different source fragments.
- A quoted phrase must occur contiguously within one source fragment.
- The final unquoted word may match the beginning of a longer indexed word so an in-progress query such as `calibr` can find `calibration`.
- The existing Unicode-aware current-Question substring behavior remains eligible. Moving to full-text search must not make a previously valid Question substring undiscoverable.
- Exact contiguous text, exact Question, phrase, whole-token, and prefix evidence may all contribute to ranking; matching never rewrites stored text.
- If an All-words query has no result, Reckonsolve does not silently broaden it. The empty state offers **Search for any word**, and the resulting mode is visibly identified.
- **Any word** requires at least one query word and may be selected deliberately even when All-words results exist.
- A corpus-derived spelling suggestion may appear after a zero-result or clearly weak query. It never silently replaces the typed query, must not require a network service or general dictionary download, and runs only after the user accepts or selects the suggestion.
- Names, acronyms, units, and uncommon domain terms are not presumed to be misspellings merely because they are rare.
- v0.5 performs no automatic synonym expansion, semantic paraphrase inference, stemming that changes a complete word's meaning, or personalization from earlier searches.

Text matching combines with every active structured filter using logical AND. Match mode affects only the relationship among query words. It does not weaken status, type, date, attention, or tag requirements.

### 33.4 Ranking, grouping, and result explanation

Search retrieves matching fragments, then groups them by Prediction before producing the archive read model. One Prediction contributes one result row regardless of the number of matching sources.

The default relevance policy gives the strongest preference to:

1. an exact or literal match in the current Question;
2. a whole-word or prefix match in the current Question;
3. a current tag match;
4. a match in current Background or Resolution Criteria;
5. a match in Forecast rationale, Forecast Review, or effective Journal text;
6. a match in effective terminal notes, Postmortem, Invalidation reason, or an outcome-correction explanation; and
7. a superseded historical match when history is included.

Within that policy, term coverage, phrase proximity, source quality, and full-text relevance determine the main order. Recency may break otherwise close ties but must not push an old exact Question below a newer vague prose match. Stable Prediction identity supplies the final deterministic tie-breaker.

The exact numeric weighting is an implementation detail tuned against the approved relevance corpus. Changing weights may not violate the source priority, historical labeling, exact-Question expectation, or release acceptance cases.

Each matching result shows:

- current Question;
- Binary or Numeric type;
- current derived lifecycle status;
- current type-appropriate forecast or effective terminal summary;
- current tags;
- the best matching source label;
- a short plain-text snippet with safely emphasized matching text; and
- an additional-match count when other fragments in the same Prediction also matched.

The explanation must make relevance inspectable without exposing raw scores. Examples include **Question match**, **Journal entry match**, **Forecast revision 3 rationale**, and **Historical Postmortem version - superseded**.

Opening a result loads current Prediction Detail through the normal application query. When the best source has a visible destination, Detail scrolls to and expands the corresponding current metadata section, timeline record, Definition history, terminal correction history, or Postmortem area and temporarily emphasizes the matched passage. A stale or removed derived search target triggers a current re-query or index repair rather than opening fabricated text.

### 33.5 Archive filters and sorting

v0.5 evolves the existing Predictions screen rather than adding a seventh primary Search screen. The archive retains its current status, forecast-type, and tag behavior and adds the following retrieval controls:

- zero or more tag selections;
- **All selected tags** or **Any selected tag**, with All as the default;
- an optional attention filter for Needs Attention, Ready to Resolve, or Needs Postmortem;
- an optional inclusive date range with one selected date meaning: Created, Forecast Deadline, Expected Resolution, or terminal decision date; and
- an explicit sort selector.

Status choices remain All, Open, Locked, Resolved, and Invalid. Forecast-type choices remain All types, Binary, and Numeric. One selected attention classification narrows to that derived population; it does not create a persisted status. An active date range excludes Predictions without the selected date value. Stored date-only fields retain their calendar semantics, while canonical created and original terminal-decision instants are compared by their displayed local calendar date using one time-zone view per query. A later terminal correction never moves a Prediction into a different terminal-date range.

Supported sort choices are:

- Relevance, available when text search is nonblank;
- Created newest or oldest;
- Question A-Z or Z-A;
- Forecast last considered newest or oldest, using the later eligible ForecastRevision or Forecast Review;
- Expected Resolution soonest or latest; and
- terminal decision newest or oldest.

Rows without the selected optional sort value follow rows that have one. All sorts have a stable Prediction-identity tie-breaker. Relevance is the default while a nonblank search is active; Created newest remains the default for ordinary browsing. Choosing another sort is deliberate and must not change match eligibility.

All filter families combine using logical AND except the internal Any-selected-tags mode. A visible **Clear search and filters** action returns to the default archive. Empty results distinguish a genuinely empty database, no current matches, no All-words matches with an available Any-word fallback, and an index/query failure. A failed refresh retains previously rendered results only with an explicit warning.

### 33.6 Saved Views

A **Saved View** is a named dynamic archive query. It stores a retrieval configuration, not a list or copy of matching Prediction identifiers. Opening it reruns the current application query against current canonical data, so membership may legitimately change as Predictions, dates, attention conditions, tags, or effective text change.

A Saved View may retain:

- search text;
- All-words or Any-word mode;
- Include superseded history;
- lifecycle status;
- forecast type;
- selected tags and their All/Any mode;
- attention classification;
- selected date meaning and optional inclusive endpoints; and
- sort choice.

Saved View names are required, normalized nonempty text with case-insensitive identity and retained display spelling. The Predictions screen supports **Save current view**, **Save as new**, rename, explicit update, and delete. Applying a Saved View replaces the current archive controls with its stored configuration. Subsequent control changes mark the view as modified but do not silently overwrite it; only **Update saved view** changes the stored preference.

Built-in default browsing is not a mutable Saved View. Saved Views have stable identifiers, ordinary update/delete semantics, and no immutable audit history. Deleting a Saved View deletes no Prediction or tag and needs no historically consequential confirmation.

Tag references use stable tag identity rather than copied display text. A tag rename therefore follows the Saved View automatically. A tag merge retargets and deduplicates references. Deleting a referenced tag explicitly warns that affected Saved Views will lose that tag condition before the single confirmed transaction proceeds.

Saved Views are part of recoverable local application state and therefore belong in SQLite backup. They are omitted from the analytical CSV bundle just as other interface preferences are omitted. They are not Collections: the user cannot manually add or remove one Prediction while preserving a fixed membership list.

### 33.7 Tag-library management

v0.5 adds a secondary **Manage Tags** workflow reachable from Predictions and, where practical, Settings. It is not a new primary screen. The library lists every retained tag with its current Prediction-association count and Saved View reference count and supports filtering the tag list by name.

The workflow permits:

- renaming a tag while retaining its stable identity and all associations;
- merging one or more source tags into one selected target tag; and
- deleting a tag and removing its current Prediction and Saved View associations.

Existing tag validation and case-insensitive identity remain authoritative. A display-only capitalization or spelling cleanup is a rename. Renaming to the case-insensitive identity of another tag does not merge silently; the interface directs the user to the explicit merge workflow.

A rename displays the current and proposed labels plus the number of affected Predictions before saving. One transaction retains the tag's stable identifier, changes its display and normalized identity, rebuilds the affected search documents, and advances the optimistic metadata context of associated Predictions. Stable Saved View references require no retargeting and display the new label after refresh.

A merge displays the source tags, target tag, number of affected Predictions, and number of affected Saved Views before confirmation. One transaction unions Prediction associations into the target, removes duplicate associations, retargets and deduplicates Saved View filters, removes the source tags, updates affected search documents, and advances the optimistic metadata context of affected Predictions. Forecast history, Journal history, freshness, lifecycle, and analytics remain unchanged.

Deletion likewise displays affected counts and requires confirmation. One transaction removes the tag's Prediction associations, removes its Saved View references, removes the retained tag row, updates affected search documents, and advances affected Prediction metadata contexts. The confirmation explicitly warns when a Saved View will become broader because its tag condition is being removed. Cancellation or any failure leaves every association and Saved View unchanged.

Because global rename, merge, or deletion changes visible Prediction metadata after creation, affected Predictions no longer qualify as untouched creation records for normal deletion. No Definition snapshot is appended because tags remain outside proposition-definition history. Stale metadata dialogs must reject saving rather than restoring pre-management tag state.

v0.5 adds no tag hierarchy, aliases, colors, automatic tagging, bulk Prediction deletion, or generic bulk metadata editor.

### 33.8 Search persistence, repair, and portability

The search engine uses SQLite FTS5 through Python's standard-library `sqlite3` binding. v0.5 adds no hosted search process, web service, ORM, external search server, embedding model, or production search dependency. Source development and the private frozen Windows build must both prove FTS5 availability before the release can close.

The first v0.5 migration advances the completed schema-version-13 database and creates a content-bearing derived full-text index with unindexed source metadata plus a projection-version marker. Each row represents one searchable fragment rather than one flattened Prediction. Canonical tables remain authoritative for every displayed value, filter, relationship, and historical record.

A data-layer projector deterministically derives the complete search-document set for one Prediction. Every existing or new application mutation that changes searchable text or current tag labels/associations rebuilds the affected Prediction's documents inside the same `BEGIN IMMEDIATE` transaction as the canonical change. Multi-Prediction tag operations rebuild every affected Prediction before committing. Independent GUI and CLI connections therefore observe a consistent old or new state rather than a partially refreshed index.

The query layer safely compiles user text, retrieves fragment candidates, evaluates Prediction-level term coverage, applies structured filters before final ranking, groups by Prediction, and returns presentation-neutral hits. Widgets and CLI renderers perform no SQL, ranking, or history replay.

The search index may be rebuilt in full from canonical state after migration, projection-version change, integrity failure, backup recovery, or an explicit repair action. Rebuilding it creates no product history and changes no canonical application timestamp. An index failure remains visible and offers repair; Reckonsolve must not reinterpret the failure as zero matches.

SQLite backup continues to copy the complete database, including Saved Views and the physical derived index. Recovery verifies canonical migration history and either verifies or deterministically rebuilds the index before reporting success. Relational CSV export remains format version 3 because v0.5 adds no new analytical forecast fact: it reflects current tag rows and associations but excludes the derived index, Saved Views, query text, ranking data, and spelling vocabulary.

Stable and development identities retain separate databases and therefore separate indexes, tag libraries, and Saved Views. Tests and private smoke workflows use only explicit temporary paths.

### 33.9 Desktop and CLI boundaries

Desktop search lives in the Predictions screen so browsing, structured filters, Saved Views, result explanation, and contextual Detail navigation remain one coherent archive workflow. Search input is keyboard-first and may use a short debounce, but a pending query must not block ordinary navigation or display stale results as though they belong to the latest text.

v0.5 adds a read-only CLI search command through both paired identities:

```text
rsc search "QUERY" [filters]
rscd search "QUERY" [filters]
```

The long `reckonsolve-cli` and `reckonsolve-cli-dev` names expose the same command. CLI search supports the same All/Any word mode, history inclusion, status, forecast type, repeated tag filters with All/Any semantics, attention filter, date range, and deterministic sorts where they have a meaningful textual representation. It displays Prediction ID, Question, type, status, current forecast or terminal summary, best source label, snippet, and additional-match count. A suggestion is printed as a suggestion, never executed automatically.

The CLI can list Saved Views and execute one by exact case-insensitive name or stable identifier through the shared application query. Saved View creation, update, rename, and deletion and all tag-library mutations remain desktop-only in v0.5. Existing `list`, `show`, creation, active forecasting, lifecycle, backup, and export commands retain their prior contracts.

Search and Saved View execution are side-effect-free and do not require an interactive prompt. v0.5 adds no machine-readable output, shell query language, noninteractive mutation flag, background watcher, or live push refresh between already-open processes.

### 33.10 Search-quality and evaluation contract

Search is not accepted merely because FTS5 returns rows. Before UI weighting is finalized, the repository must contain a representative, synthetic, privacy-safe relevance corpus with named memory scenarios and expected inclusions, exclusions, and ranking positions.

The corpus and tests cover at least:

- exact current Questions;
- reordered words;
- words distributed across a Question and another fragment of the same Prediction;
- quoted phrases that must remain within one fragment;
- partial final words;
- case and common Latin-diacritic differences;
- punctuation, apostrophes, hyphens, percentages, and query characters meaningful to FTS syntax;
- one-edit spelling mistakes and deliberate acceptance or rejection of a suggestion;
- overlapping common terms that should not outrank a stronger Question match;
- identical text in multiple fragments without duplicate Prediction rows;
- effective Journal and terminal text after corrections;
- superseded-only text excluded by default and labeled when history is included;
- Binary and exact Numeric results;
- every structured filter, null date, tag mode, and deterministic sort boundary;
- immediate visibility after GUI and CLI writes, restart, and migration;
- independent connections, bounded lock failure, and atomic index rollback; and
- index corruption or incompatibility reported as repairable failure rather than empty search.

Every approved memory scenario must place its intended Prediction within the top three relevant results, and an unambiguous exact current-Question search must rank that Prediction first. Tests assert stable ordering only where the contract makes order meaningful; they do not freeze incidental floating-point relevance values.

The hardening milestone records search time and result completeness against a synthetic corpus substantially larger than expected ordinary personal use. The goal is perceptibly immediate first-page retrieval without introducing infrastructure for hypothetical web scale. A fixed cross-machine millisecond assertion is not a correctness criterion, but an observed regression that makes typing or opening results visibly sluggish blocks release until investigated.

Reckonsolve stores no hidden query history, click profile, or behavioral ranking telemetry. When real use exposes a poor retrieval case, a privacy-safe reproduction becomes a regression scenario before weights or matching rules change.

### 33.11 Implementation milestones

Milestones 32 through 38 implement v0.5.0. Work remains one coherent vertical slice at a time.

#### Milestone 32: Search projection and retrieval foundation

- Record the consequential SQLite FTS5 and rebuildable-derived-index approach in an architecture decision record.
- Add the safe schema-version-13 migration, projection-version state, FTS capability validation, and deterministic full rebuild.
- Define presentation-neutral search documents, queries, fragments, grouped hits, source classifications, and repair errors.
- Project default-effective and opt-in superseded text without flattening or mutating canonical history.
- Add safe parsing for words, phrases, prefix completion, literal Question substrings, All/Any matching, and explicit spelling suggestions.
- Add deterministic grouping and source-priority ranking against the synthetic relevance corpus.
- Integrate per-Prediction index refresh into every existing searchable canonical write transaction and prove rollback, restart, correction replay, stable/development isolation, and independent-connection consistency.
- Expose no end-user search UI until the complete read model and failure states are ready.

#### Milestone 33: Explainable desktop full-text search

- Replace the Predictions screen's question-only text path with the shared grouped full-text query while preserving blank-query archive behavior.
- Show one result per Prediction with type, status, current forecast or terminal summary, tags, source label, safe snippet, and additional-match count.
- Add All/Any mode, quoted phrases, prefix behavior, spelling suggestions, and Include superseded history with unmistakable historical labels.
- Open current type-aware Detail at the best matching metadata, timeline, Definition-history, or terminal-history context.
- Preserve keyboard focus, accessible result summaries, responsive query updates, explicit empty states, and visible retained-results behavior after expected query failure.

Acceptance demonstration:

> Create a Prediction, revise it with rationale, add and correct a Journal entry, resolve it, and add a later Postmortem -> search different remembered phrases -> each phrase finds one Prediction with the correct source -> superseded Journal wording appears only after Include superseded history -> restart -> the same current and historical matches remain.

#### Milestone 34: Rich archive filters and deterministic sorting

- Add multi-tag All/Any filtering, attention classification, inclusive date meaning/range, and the complete sort choices from Section 33.5.
- Apply every structured filter before final relevance ordering and preserve logical-AND behavior across filter families.
- Derive Locked and attention conditions against one current date/instant per query without persisting them in the index.
- Define null-date placement, local-date projection for instants, stable tie-breakers, clear-all behavior, and no-match explanations.
- Cover filter and sort combinations across Binary, Numeric, nonterminal, terminal, corrected outcome, missing-date, and date-boundary records.

#### Milestone 35: Dynamic Saved Views

- Add recoverable persistence for named mutable Saved Views and stable tag references without storing result membership.
- Add Save current view, Save as new, apply, modified-state, explicit update, rename, and delete workflows inside Predictions.
- Restore every query, history, filter, date, attention, tag-mode, and sort control exactly and rerun against current data.
- Preserve case-insensitive name identity, clear duplicate-name errors, cancellation, restart, backup, and stable/development isolation.
- Keep Saved Views out of forecast history, Analytics, CSV export, Collections, and primary navigation.

#### Milestone 36: Transactional tag-library management

- Add the secondary tag-library workflow with association and Saved View counts.
- Implement explicit rename, confirmed merge, and confirmed deletion using stable tag identity and existing validation.
- Update Prediction associations, Saved View references, optimistic metadata contexts, and affected search documents atomically.
- Reject stale metadata saves after global tag changes and preserve untouched canonical forecast, Journal, terminal, freshness, and analytical facts.
- Cover duplicate-case labels, display-only rename, many-to-one merge deduplication, deletion that broadens Saved Views, cancellation, rollback, restart, backup, and cross-interface reads.

#### Milestone 37: CLI retrieval parity

- Add type-aware `search` to stable and development CLI identities through the shared application query.
- Support the meaningful text, history, filter, date, tag-mode, attention, and sort options without exposing raw FTS syntax.
- Render best-source explanation, snippet, additional matches, explicit suggestions, empty states, and repairable failures without mutation.
- Add read-only Saved View listing and execution while keeping Saved View and tag-library mutation desktop-only.
- Preserve existing CLI commands, single canonical database identity, sequential-write guidance, bounded locks, and normal restart refresh.

#### Milestone 38: v0.5 portability, relevance, and release hardening

- Prove complete migration from a real schema-version-13 v0.4 database, forced-failure rollback, full-index rebuild, integrity failure reporting, and repair from canonical history.
- Verify backup and recovery of Saved Views and search capability while retaining CSV format version 3 and documenting every intentional exclusion.
- Exercise simultaneous reads, sequential GUI/CLI writes, stale contexts, tag-wide transactions, stable/development isolation, and no false empty results after failure.
- Run and document the full relevance corpus and a substantially larger synthetic performance corpus.
- Extend the private frozen-build smoke workflow to prove FTS5 availability, migration, effective/history search, Saved Views, tag maintenance, CLI-compatible canonical results, backup, repair, and restart without the source environment.
- Run the complete automated suite and align README, architecture, decision records, command help, changelog, and release documentation with implemented v0.5 behavior.
- Close v0.5 as a source release without expanding into semantic search, Collections, new forecast models, logo work, an installer, signing, updates, or public binary distribution.

### 33.12 v0.5 acceptance criteria

v0.5 is not complete unless all of the following are true:

1. Every completed v0.4 desktop and CLI workflow retains its prior behavior unless this contract explicitly extends it.
2. Normal search covers every default source in Section 33.2 and returns one grouped row per matching Prediction.
3. Search is Unicode-aware, case-insensitive, safe for arbitrary punctuation, and never exposes a raw FTS parse error to ordinary query input.
4. All-words matching may combine words across fragments of one Prediction but never across different Predictions.
5. Quoted phrases remain fragment-local, prefix completion finds expected longer words, and existing current-Question substring discovery is preserved.
6. Any-word fallback and spelling suggestions are explicit user choices and never silently change the typed query.
7. An exact unambiguous current-Question query ranks its Prediction first, and every approved memory scenario ranks its intended Prediction within the top three.
8. Every result explains its best source, shows a safe relevant snippet, reports additional matches, and opens current Detail at the matching context when one exists.
9. Effective corrected Journal and terminal text is searchable by default while superseded-only text is absent unless Include superseded history is active.
10. Every historical-only result is visibly labeled superseded and never masquerades as current Question, Journal, or terminal text.
11. Relevance affects presentation only and never changes canonical history, lifecycle, freshness, scoring, analytics, or timeline order.
12. Status, type, attention, date, and tag filters combine exactly as specified, including All/Any multi-tag behavior and null-date exclusion.
13. Every sort is deterministic, Relevance is available only for nonblank search, and ordinary browsing still defaults to Created newest.
14. A Saved View restores its complete configuration and dynamically reruns against current data without storing membership.
15. Editing archive controls after applying a Saved View never silently overwrites the saved configuration.
16. Saved Views persist across restart and backup, remain isolated between stable and development identities, and remain absent from analytical CSV export.
17. Tag rename retains identity and associations; tag merge unions and deduplicates; tag deletion removes only the confirmed current associations and references.
18. Global tag changes update affected search results and Saved Views atomically, reject stale metadata forms, and alter no forecast, Journal, terminal, freshness, or scoring fact.
19. Every searchable canonical write and its affected index projection commit or roll back together across GUI and CLI operations.
20. Index rebuild reproduces search behavior from canonical data without creating history or changing application timestamps.
21. An unavailable, corrupt, incompatible, or stale index is reported and repairable rather than displayed as no matches.
22. CLI search and Saved View execution use the same application query and produce semantically equivalent eligibility, source, and ordering behavior as the matching GUI identity.
23. Backup, migration, recovery, restart, stable/development isolation, cross-interface access, and the private frozen build preserve all canonical v0.5 state and search capability.
24. Search quality and weighting changes are guarded by the privacy-safe relevance corpus, and no hidden query or click history is collected.
25. The complete v0.5 workflow remains offline, local-first, single-user, and proportionate to a personal forecasting journal.

### 33.13 Explicitly outside v0.5

- Semantic or vector search, embeddings, a bundled language model, automatic synonym inference, web search, hosted indexing, or an external search server.
- Hidden query logging, click tracking, behavioral personalization, advertising, recommendation feeds, or popularity-based ranking.
- Collections, manually curated result membership, favorites, pins, tag hierarchy, tag colors, tag aliases, or automatic tagging.
- Structured Sources/Evidence, attachments, Prediction relationships, graphs, or backlinks.
- Generic bulk Prediction editing, bulk deletion, bulk import, or a scripting API.
- CLI mutation of Saved Views or the tag library, machine-readable search output, noninteractive mutation flags, or live inter-process push refresh.
- New forecast types, multiple Numeric intervals, full distributions, conditional forecasts, new scoring rules, or advanced Forecast Review sessions.
- Notifications, automatic reminders, background monitoring, or automatic forecast changes.
- A new CSV format solely for derived search data or Saved Views, JSON or Markdown export, or restoration from analytical export.
- A normal Windows installer, application-icon artwork, code signing, automatic updates, or public binary distribution.
- Accounts, profiles, cloud sync, sharing, collaboration, or required network access.

---

## 34. v0.6 visual system and application shell product contract and milestone plan

v0.6 is a desktop presentation release over the completed v0.5 product. It gives Reckonsolve a coherent visual language, corrects the information hierarchy of the application shell, improves responsiveness and keyboard access, and makes routine feedback less interruptive. It does not add a forecasting workflow merely to justify a new version number.

The governing objective is:

> Make the existing forecasting journal feel calm, deliberate, responsive, and internally consistent without changing what any saved forecasting fact means.

The interaction and visual discipline of Super Productivity is inspiration at the pattern level only. Reckonsolve does not copy that application's task-management structure, source code, artwork, branding, or feature density. The implementation remains native PySide6 and preserves Reckonsolve's identity as a personal forecasting journal.

### 34.1 Included in v0.6

v0.6 includes:

- a centralized, palette-aware desktop visual system for spacing, typography, surfaces, borders, radii, icons, control states, action roles, focus, and restrained motion;
- a reorganized application shell that distinguishes primary destinations, the New Prediction action, contextual Prediction Detail, and Settings;
- manually toggleable and remembered expanded and compact sidebar modes;
- contextual return navigation from Prediction Detail without making Detail a permanent primary destination;
- comfortable, consistent page headers, content panels, status indicators, action groups, rows, dialogs, empty states, and error states;
- clear primary, secondary, quiet, and destructive action hierarchy;
- nonblocking status notifications for routine acknowledgments, while retaining persistent messages and modal confirmation when the information requires attention or a decision;
- responsive layouts that remain usable at the supported minimum window size and under common Windows display scaling;
- safe restoration of window geometry, maximized state, and preferred sidebar mode as noncanonical presentation preferences;
- documented keyboard shortcuts, deliberate tab order, visible keyboard focus, accessible names, and no essential hover-only interaction;
- type-aware visual refinement across Dashboard, New Prediction, Prediction Detail, Predictions, Analytics, Settings, tag management, and existing dialogs; and
- migration-free backup, CLI, search, frozen-build, and release hardening proving that presentation changes leave canonical behavior untouched.

### 34.2 Product and visual principles

#### Existing behavior is the baseline

v0.6 restyles and reorganizes existing desktop behavior. It does not redefine Prediction eligibility, lifecycle, revision history, Journal anchoring, Review freshness, terminal correction, scoring, search matching, Saved View membership, tag identity, backup, or export semantics.

A visual refactor must not quietly create a new product rule. If a proposed layout would require a new domain state, workflow, database fact, or interpretation of history, that work is outside v0.6 unless the specification is revised again.

#### Calm, comfortable density

The desktop should resemble a thoughtful journal rather than a dense task manager, trading terminal, or enterprise dashboard. Ordinary controls have comfortable targets and breathing room. Increased polish must not reduce legibility merely to display more information at once.

Question and the current type-appropriate forecast remain the strongest elements in creation and Detail. Supporting metadata, timestamps, tags, historical annotations, and explanatory text use quieter presentation without becoming inaccessible.

#### Consistency over decoration

The visual system uses a small shared scale rather than screen-specific pixel choices. It defines semantic roles for:

- compact, ordinary, and section spacing;
- body, secondary, label, section-title, page-title, and forecast-emphasis typography;
- base, raised, selected, input, warning, error, and destructive surfaces;
- subtle panel borders and corner radii;
- primary, secondary, quiet, and destructive controls;
- hover, selected, pressed, disabled, and keyboard-focus states; and
- short entrance or disclosure motion where it improves continuity.

Exact values are implementation details, but they must be centralized and tested in context rather than independently improvised in each widget.

#### System theme and native window behavior

Reckonsolve continues to follow the operating system's effective light/dark palette. v0.6 may add a centralized palette-relative Qt stylesheet and reusable presentation widgets, but it adds no theme framework, theme gallery, custom stylesheet editor, bundled font, or independent Light/Dark setting.

The native Windows title bar, window controls, resizing, taskbar behavior, and standard dialogs remain native. v0.6 does not adopt a custom-drawn title bar, glass background, wallpaper, or translucent application shell.

The current restrained green cue becomes Reckonsolve's single ordinary accent family. Separate contrast-safe light and dark values may be tuned during implementation. Status, warning, destructive, and analytical colors retain their semantic roles. No meaning may rely on green or any other color alone.

#### Content before chrome

Visual chrome must not compete with the forecast. Icons support labels rather than replace unfamiliar actions. Shadows remain minimal, borders remain subtle, and animation never delays navigation, saving, or error display.

### 34.3 Application-shell and navigation contract

The completed desktop still contains Dashboard, New Prediction, Prediction Detail, Predictions, Analytics, and Settings screens, but v0.6 changes how the shell presents them.

The expanded sidebar has this information hierarchy:

1. Reckonsolve identity and the compact/expanded toggle;
2. a visually distinct **New prediction** action;
3. the primary destinations **Dashboard**, **Predictions**, and **Analytics**;
4. flexible empty space; and
5. the utility destination **Settings** anchored at the bottom.

**New prediction** opens the existing creation screen but is styled and exposed as an action rather than as one peer among navigation destinations. It remains available by keyboard and retains the existing atomic creation behavior.

**Prediction Detail** is contextual and no longer appears as a permanent sidebar destination. Selecting a Prediction from Dashboard or Predictions, or successfully creating one, opens the same type-appropriate Detail host as before. Detail displays a clear return action. That action returns to the immediately preceding primary screen when one exists and otherwise returns to Predictions. Returning to Predictions preserves its current search text, filters, Saved View state, sort, loaded results, and scroll context when practical; it must not silently rerun a different query solely because Detail was opened.

The compact sidebar shows the same destinations and creation action using icons. Every compact item has an accessible name and a concise tooltip. Labels are either completely visible in expanded mode or deliberately hidden in compact mode; they must never be clipped into ambiguous fragments. Compact mode must retain clear active, hover, pressed, disabled, and keyboard-focus states.

The user may toggle the sidebar manually. The preferred mode is remembered separately for stable and development identities. Resizing the window must not overwrite that preference. The sidebar may enforce only the width required by its declared mode and may not squeeze the main content below its supported minimum.

Opening a contextual screen must not create a fake navigation destination or select an unrelated sidebar item. Exactly one primary destination may appear active at a time; New prediction has its own active-action treatment while its form is visible.

### 34.4 Shared visual language

#### Typography

Reckonsolve uses the native application font and respects operating-system text and display scaling. It adds no bundled typeface. A centralized relative type scale distinguishes:

- page titles;
- section titles;
- the current Binary probability or Numeric interval and median;
- ordinary body text;
- labels and compact row metadata; and
- secondary explanatory or historical text.

Manual per-widget point-size additions should be replaced when practical by shared semantic helpers. Long Questions and user-authored text wrap naturally and remain selectable where they are currently selectable. Styling must not truncate canonical user text in Detail or dialogs.

#### Surfaces and panels

The main canvas, sidebar, input areas, raised content panels, selected rows, and modal dialogs use a restrained surface hierarchy derived from the active palette. Reusable panels replace inconsistent native-looking boxes where doing so improves hierarchy. A panel is not added around every label merely for decoration.

Borders and separators must remain visible in both system modes without becoming the most prominent elements. Rounded corners are used consistently. Layout shadows, if any, are subtle and never the sole indication that two regions are separate.

#### Status and forecast emphasis

Binary probability or the complete Numeric interval remains readable without opening another view. Lifecycle and forecast type may use compact badges or labels, but the words **Open**, **Locked**, **Resolved**, **Invalid**, **Binary**, and **Numeric** remain present. Attention classifications remain explicit text and are not reduced to color or an unexplained icon.

Tags remain text labels with their stored display spelling. v0.6 does not introduce tag colors or semantic color assignment.

#### Icons

The existing local Lucide assets remain the icon source. Icons continue to derive legible colors from the active Qt palette and retain visible text for unfamiliar or consequential actions. Icon-only controls are limited to conventional shell actions such as collapsing the sidebar or closing a dismissible notification, and they require tooltips and accessible names.

v0.6 does not copy Super Productivity icons, assets, or branding.

#### Motion

Motion is limited to short sidebar width changes, disclosure expansion, and nonblocking status-notification entrance or exit where supported cleanly. It must not animate data values, charts, row ordering, or lifecycle changes in a way that obscures the final state. When Qt or the platform indicates that widget animation should be reduced or disabled, Reckonsolve follows that preference. A motion failure must degrade to an immediate state change.

### 34.5 Controls and action hierarchy

Every existing action is assigned one of four presentation roles:

- **Primary**: the intended next committed action in the current context, such as Create Prediction, Save Revision, or Resolve Prediction inside its deliberate dialog.
- **Secondary**: a normal alternative, such as Add Journal Entry, Still at N%, Keep this interval, or Edit details.
- **Quiet**: navigation or maintenance that should remain available without competing with the main action, such as Clear filters, Refresh, Back, or a disclosure toggle.
- **Destructive**: irreversible deletion or a historically consequential action requiring especially clear wording and confirmation.

One dialog or action region should ordinarily contain no more than one visually primary committed action. A Cancel action remains plainly available and never receives destructive styling. Disabled state must be distinguishable from ordinary text and must retain an explanation through nearby text or a tooltip when the reason is not obvious.

Hover, mouse selection, keyboard focus, and activated state are distinct. Hover must never masquerade as selection, and merely entering Predictions must not automatically select its newest row. Essential actions cannot exist only on hover; any hover-revealed convenience must have an equivalent keyboard-accessible and persistently discoverable route.

Buttons retain concise visible labels where consequences matter. Existing confirmation text, optimistic-concurrency checks, and no-op validation remain authoritative regardless of visual role.

### 34.6 Page and workflow presentation

#### Shared page frame

Every primary or contextual screen receives a consistent page header with a page title, optional concise supporting text, and an action region when needed. Header, content, empty state, and persistent error placement remain stable as content changes. A zero-result, loading, or error state must not cause the search controls or other page header content to jump vertically.

Form-like and reading-focused content may use a comfortable maximum readable width. Archive results, filter controls, tables, and charts may use the available width. The choice follows content type rather than applying one fixed width to every screen.

#### Dashboard

Dashboard retains its implemented Open, Locked, Needs Attention, Ready to Resolve, and Needs Postmortem behavior. v0.6 may refine section headers, counts, empty states, rows, spacing, and navigation affordances, but it adds no Review Forecasts queue, scheduling rule, notification, or new attention classification.

Each row keeps Question, type-appropriate current forecast or terminal summary, lifecycle or attention labels, and last-considered or relevant date context readable. Empty sections remain explicit. Visual compactness must not conceal the fact that attention sections can overlap.

#### New Prediction

The creation screen keeps Question and the type-appropriate forecast inputs visually primary. Binary remains the default forecast type. The collapsed optional-details design remains intact. Optional fields must not acquire new required-looking styling, and no decorative stepper may imply that creation has multiple mandatory stages.

The form gains consistent label alignment, field spacing, error placement, button roles, focus order, and responsive wrapping. Switching type, validation failure, cancellation, and successful atomic creation retain their existing behavior.

#### Prediction Detail

Detail begins with a compact identity region containing the complete Question, forecast type, lifecycle state, current Binary probability or complete Numeric interval/median/confidence, and nonempty tags. The current forecast is visually stronger than supporting metadata. The contextual Back action is always reachable by mouse and keyboard.

Common lifecycle-eligible actions remain immediately visible and use the shared action hierarchy. Rare correction, invalidation, or deletion actions may be grouped in a clearly labeled secondary area or menu only if their wording, availability, keyboard access, confirmation, and discoverability remain intact. No action may be hidden solely to achieve a cleaner screenshot.

Metadata, terminal summary, scorecard, history chart, timeline, Definition history, correction history, and Journal edit history use consistent sections and disclosures. Existing rules about hiding or de-emphasizing empty optional content remain. Collapsing a visual section changes no product data.

Binary and Numeric Detail must share the same visual grammar while retaining type-appropriate values and operations. User-authored rationale, Journal, Review, terminal, Postmortem, and correction text remains plain, selectable, wrap-safe, and historically explicit.

#### Predictions and search

Predictions retains the complete v0.5 search, filter, sort, Saved View, tag-management, failure-retention, and matched-context navigation contract. v0.6 changes presentation only.

One result row continues to represent one Prediction. Question is primary; forecast or terminal summary and lifecycle remain immediately legible; type, tags, dates, best matching source, snippet, and additional matches use a consistent secondary hierarchy. Clicking an ordinary row body or pressing Enter on a keyboard-selected row opens it. Hover alone selects nothing and opening the screen starts with no selected Prediction.

Search, Words mode, history scope, status, type, tags, attention, date, sort, Saved View, and maintenance controls wrap into deliberate rows or disclosures as width decreases. Their logical values and combination order remain unchanged. Empty and failed-result states occupy the result region without moving the search and filter frame.

Search emphasis remains safe and source-explainable. A cosmetic refactor must not flatten historical labels, hide suggestions, replace retained-results warnings with an empty list, or change ranking.

#### Analytics

Analytics retains exactly the existing observation selection, filters, Binary/Numeric separation, unit boundaries, score calculations, sparse-data guidance, tables, and chart summaries. v0.6 may organize headlines, tables, charts, guidance, and retrospective feedback into consistent panels with improved responsive sizing.

Visual emphasis must not imply that a sparse or descriptive metric is statistically conclusive. Charts continue to expose nonvisual summaries, and color remains supplementary to labels, axes, marker shapes, or text.

#### Settings, tag management, and dialogs

Settings uses consistent sections for attention preferences and data management. The canonical database path, backup time, destination, and export results remain selectable and persistent where the user may need to inspect or copy them.

Tag management retains current previews, counts, confirmations, stable identity rules, and transactional behavior. Modal and secondary windows receive consistent spacing, action placement, focus, error regions, and safe minimum sizing.

Dialogs must remain usable at the supported window and display scales. Expected validation appears within the relevant dialog without destroying entered text. The default focused button must not make a destructive or terminal action easy to confirm accidentally.

### 34.7 Feedback and nonblocking status notifications

v0.6 distinguishes acknowledgment, retained information, failure, and decision:

- A routine successful action that is immediately visible in refreshed content may show a short nonblocking status notification, for example **Forecast revised to 65%**, **Journal entry added**, or **Saved View renamed**.
- Information the user may need to copy or revisit, including a backup or export destination, remains in a persistent inline status region rather than disappearing automatically.
- An expected or unexpected failure remains visible until the user retries, dismisses it deliberately where safe, or leaves the affected context. A failure must never auto-dismiss into apparent success.
- An action requiring a decision, including permanent deletion, Resolution, Invalidation, score-affecting correction, tag merge, or tag deletion, retains an explicit modal confirmation before the write.

Routine notifications appear in a stable application-level overlay or reserved shell region that does not reflow the active page. They are plain text, announced through Qt accessibility support, and dismiss automatically after a short readable interval unless the pointer or keyboard is interacting with them. Repeated identical acknowledgments may be coalesced; notifications must not accumulate into a permanent log or obscure a required dialog.

Closing or missing a routine notification loses no unique information: the committed result must remain visible in the refreshed canonical view or recoverable from existing history. v0.6 adds no Windows notification-center integration, background alert, reminder, sound, or telemetry.

### 34.8 Responsiveness and presentation preferences

The supported desktop minimum remains a usable window approximately equivalent to the existing 760 by 520 logical-pixel minimum. At that size and at ordinary larger desktop sizes:

- sidebar labels are fully visible or deliberately compact, never partially clipped;
- the main page has a usable content region;
- control groups wrap or scroll rather than overlap;
- primary committed actions remain reachable;
- long Questions and metadata wrap without horizontal page scrolling;
- charts retain their documented nonvisual alternative when visual space is constrained; and
- empty, loading, success, warning, and error states do not unexpectedly relocate page controls.

The implementation must also be exercised at common Windows scaling factors, including 100%, 150%, and 200%, using Qt's logical sizing and font metrics rather than assuming one physical pixel density.

Reckonsolve remembers the user's preferred sidebar mode, last safe normal window geometry, and maximized state using Qt's platform-local presentation settings or an equivalently isolated presentation store. It does not restore a minimized state. On startup it restores geometry only when a meaningful portion intersects an available screen; otherwise it uses the tested default size and placement. Removing a monitor, changing scale, or corrupting presentation settings must not make the application inaccessible.

These values are disposable interface preferences, not forecasting records. They are separated by stable and development application identity, omitted from SQLite backup and CSV export, never indexed or searched, and never accessed by the CLI. Clearing them restores safe defaults without affecting a Prediction or any canonical history.

v0.6 does not persist transient notifications, open dialogs, hover state, keyboard focus, temporary form input, current scroll position across process restart, or a new history of visited screens. Existing Saved Views remain the only persisted archive-query configurations.

### 34.9 Keyboard and accessibility contract

The desktop adds these default global shortcuts where they do not conflict with active text editing or a modal dialog:

- **Ctrl+N** opens New Prediction and focuses Question;
- **Ctrl+F** opens Predictions and focuses Search;
- **Ctrl+1** opens Dashboard;
- **Ctrl+2** opens Predictions;
- **Ctrl+3** opens Analytics;
- **Ctrl+,** opens Settings;
- **Ctrl+B** toggles expanded and compact sidebar modes; and
- **Alt+Left** returns from contextual Prediction Detail to its source screen.

Existing dialog and multiline-text conventions, including Ctrl+Enter where already specified, remain unchanged unless a milestone explicitly verifies an equivalent safe mapping. Global navigation shortcuts must not submit, resolve, invalidate, delete, correct, or otherwise mutate a Prediction.

Shortcuts are discoverable through tooltips, accessible descriptions, or a compact reference in Settings or README; v0.6 does not add a command palette or configurable shortcut editor.

All interactive controls have meaningful accessible names. Logical focus order follows visual reading order. Focus is visibly distinguishable in both system modes. Enter and Space activate conventional controls, Escape cancels or closes only where safe, and returning from a dialog restores focus to a sensible initiating control when practical.

No essential information or action depends exclusively on hover, color, animation, a chart, or an icon. Status labels, analytical summaries, and historical relationships remain available as text.

### 34.10 Technical and data boundaries

v0.6 requires no SQLite schema migration. It creates no new Prediction, forecast, Journal, Review, terminal, tag, Saved View, analytics, search, backup, or export field. Schema version 15 remains current throughout the release.

The visual system belongs in a small centralized UI boundary rather than scattered widget-local styles. Reusable page headers, panels, action roles, badges, status regions, and palette helpers may be introduced where they remove real repetition. Domain, analytics, application, and data-access modules must not import the visual layer.

Qt palette roles, font metrics, style hints, layouts, and local Lucide resources remain authoritative inputs. v0.6 adds no production dependency, web renderer, Material framework, QML rewrite, second GUI toolkit, external theme package, or copied Super Productivity component.

Presentation preference storage is opened and tested independently of the canonical SQLite data path. Failure to read or write a presentation preference falls back to safe defaults and must not prevent database startup or a forecasting operation. Automated tests isolate presentation settings just as they isolate databases and must never read or modify the user's real settings.

The paired stable and development CLI commands retain their completed v0.5 behavior and output except for the package version. No CLI command, option, prompt, or persistence rule is added for visual preferences. Simultaneous reads and sequential GUI/CLI writes retain their existing contract.

Backup remains a complete schema-version-15 canonical recovery artifact. CSV remains format version 3. Neither artifact contains window geometry, sidebar mode, transient messages, or other v0.6 presentation state.

### 34.11 Implementation milestones

Milestones 39 through 45 implement v0.6.0. Work remains one coherent vertical slice at a time, and each milestone must leave the application usable rather than applying half of a visual contract across unrelated screens.

#### Milestone 39: Central visual-system foundation

- Introduce one palette-aware UI styling boundary with semantic spacing, typography, surface, border, radius, interaction-state, focus, action-role, and restrained-motion definitions.
- Add reusable presentation helpers only for recurring concepts such as page headers, content panels, action roles, text status badges, and persistent error/status regions.
- Define contrast-safe light/dark treatment for the restrained Reckonsolve green accent and every custom text, border, selection, warning, and destructive role.
- Keep the native font, title bar, dialogs, system theme selection, high-DPI behavior, and existing local Lucide assets.
- Replace representative ad hoc widget-local styling without changing layout, signals, operations, or persisted data, then prove palette changes refresh custom icons and semantic colors correctly.
- Add focused Qt tests for semantic role assignment, focus visibility, accessible names, disabled state, palette changes, and absence of domain/data imports from the visual layer.
- Record a technical decision only if the chosen stylesheet, proxy-style, or reusable-widget boundary will constrain future UI work.

Acceptance demonstration:

> Run the same representative page and dialog under Windows light and dark palettes -> headings, panels, inputs, buttons, focus, disabled controls, warning/destructive roles, and Lucide icons remain coherent and legible -> no forecast or application behavior changes.

#### Milestone 40: Responsive application shell and navigation hierarchy

- Rebuild the main shell around the approved New prediction action; Dashboard, Predictions, and Analytics primary destinations; bottom-anchored Settings utility; and contextual Prediction Detail.
- Remove Prediction Detail from permanent sidebar navigation without removing or duplicating either type-specific Detail implementation.
- Add expanded and compact sidebar modes with a clear toggle, complete labels or complete icon-only presentation, tooltips, accessible names, and remembered preference isolated by application identity.
- Add contextual return navigation that restores the source primary screen and preserves current Predictions query/filter/Saved View/result context when returning from Detail.
- Ensure active, hover, pressed, disabled, and focus states remain distinct and that opening Predictions selects no result automatically.
- Add safe window geometry and maximized-state restoration with off-screen recovery and default fallback, without restoring minimized state.
- Cover direct navigation, creation-to-Detail, Dashboard-to-Detail, search-result-to-matched-Detail, Back, compact toggling, restart, corrupted settings, removed-monitor geometry, stable/development isolation, and keyboard navigation.

Acceptance demonstration:

> Start expanded -> search and filter Predictions -> open a result -> Detail shows no fake primary destination and Back returns to the unchanged archive context -> collapse the sidebar -> restart -> the compact mode and safe window state return while all forecast data remains unchanged.

#### Milestone 41: Shared page frame, Dashboard, Settings, and feedback

- Apply the shared page-title, supporting-text, action-region, content-panel, badge, empty-state, persistent-error, and status-region grammar to Dashboard and Settings.
- Refine Dashboard section hierarchy, counts, type-aware rows, overlapping-attention labels, and empty sections without changing membership, ordering, timers, or navigation.
- Refine Settings grouping, attention controls, database path, backup status, backup/export actions, and persistent destination results without changing storage or artifact semantics.
- Add the application-level nonblocking status-notification host with no page reflow, accessible announcement, short dismissal, coalescing, and safe behavior during modal dialogs and navigation.
- Route only routine, immediately verifiable acknowledgments through transient notification; retain persistent backup/export paths and errors and every consequential confirmation.
- Cover long text, repeated notifications, navigation during display, palette changes, keyboard dismissal where offered, success/failure separation, and proof that notification failure cannot roll back or disguise an application operation.

#### Milestone 42: Creation and type-aware Prediction Detail refinement

- Apply the visual system to Binary and Numeric creation while preserving the default type, required fields, collapsed optional details, exact validation, cancellation, and atomic save.
- Standardize field labels, explanatory text, error placement, focus order, responsive wrapping, and primary/secondary action presentation across creation and every existing dialog.
- Recompose Binary and Numeric Detail headers so complete Question, lifecycle, current forecast, type, and tags establish a shared visual hierarchy.
- Group common, historical, correction, terminal, scorecard, chart, and metadata content consistently while preserving all current hidden-empty and collapsed-history behavior.
- Keep common actions immediately available; place rare or destructive actions only in a clearly discoverable secondary region that retains visible wording, accessible access, and existing confirmations.
- Preserve exact forecast history, Journal and Review distinctions, Definition and correction history, matched-search focusing, terminal finality, scoring-revision capture, and plain selectable user text.
- Cover every lifecycle and both forecast types at short and long content lengths, including no-history, extensive-history, corrected-terminal, skipped-Postmortem, endpoint probability, signed-decimal Numeric, and stale-context failures.

Acceptance demonstration:

> Create one Binary and one Numeric Prediction, revise and Journal each, resolve one, and open the other from search -> every value and action remains type-correct, the hierarchy is consistent, long text wraps, history remains honest, and no visual control bypasses existing validation or confirmation.

#### Milestone 43: Predictions, search, Saved Views, and tag-management refinement

- Apply the shared page frame and control roles to Predictions without changing the v0.5 archive/search query boundary.
- Redesign result rows around primary Question, type-appropriate forecast or terminal summary, lifecycle, tags, date context, best source, snippet, and additional matches while retaining one row per Prediction.
- Make ordinary row-body click and keyboard Enter open Detail while preserving a distinct nonautomatic selection model and no essential hover-only control.
- Make Saved View, query, word mode, history, structured filter, date, sort, clear, suggestion, repair, and tag-management controls wrap predictably at supported widths.
- Keep the search/filter frame fixed while populated, zero-result, loading, suggestion, retained-warning, and repairable-error content changes below it.
- Apply the same dialog, panel, action-role, selection, focus, and persistent-status grammar to Saved View and tag-management workflows.
- Re-run the full v0.5 relevance corpus and combined-filter tests to prove that no visual or activation change alters matching, ranking, source provenance, dynamic membership, tag transactions, or historical navigation.

Acceptance demonstration:

> At both minimum and ordinary window sizes, move between blank archive, matching search, zero-result search, suggestion, Saved View, and tag-management states -> controls remain stable and usable, no row begins selected, mouse and keyboard activation agree, and results remain semantically identical to v0.5.

#### Milestone 44: Analytics, keyboard, accessibility, and responsive completion

- Apply the visual system to Binary, Numeric, and All-types Analytics while preserving exact filters, unit boundaries, observation selection, calculations, sparse-data language, tables, charts, and retrospective cautions.
- Make analytical headlines, tables, charts, score guidance, and empty/error states readable at supported sizes without implying false statistical certainty.
- Implement and document the approved global shortcuts and ensure they do not fire through conflicting modal or text-editing contexts.
- Audit tab order, focus restoration, accessible names/descriptions, screen-reader text, keyboard row activation, tooltip availability, and no-color/no-hover alternatives across every primary and secondary desktop workflow.
- Exercise responsive behavior at the minimum supported logical size and common larger sizes, plus 100%, 150%, and 200% Windows display scaling.
- Verify palette changes, font scaling, disabled actions, long translated-style labels, long user text, and reduced/no-animation fallback without clipping essential information or controls.
- Keep chart calculations outside widgets and retain every existing nonvisual chart summary.

#### Milestone 45: v0.6 regression, frozen-build, and release closure

- Run the complete automated suite and add regression coverage for shell navigation, presentation preferences, nonblocking feedback, screen activation, keyboard shortcuts, responsive layouts, palette changes, and accessibility contracts.
- Prove that schema version 15 remains unchanged and that opening and using v0.6 does not rewrite any v0.5 Prediction, history, Saved View, tag, setting, search document, or analytics fact merely for presentation.
- Re-run search relevance and performance evidence, backup/recovery, CSV format-version-three validation, stable/development isolation, simultaneous reads, sequential GUI/CLI writes, restart, and explicit search repair.
- Extend the relocated private frozen-build smoke workflow to load the new style resources, expanded and compact shell, both forecast types, every primary screen, keyboard navigation, safe presentation defaults, backup, search, and restart without the source environment.
- Perform and record a manual visual matrix across system light/dark mode, 100%/150%/200% scaling, minimum/default/large window sizes, expanded/compact sidebar, new/ordinary/long-text databases, and representative success/error/confirmation states.
- Align README, architecture, applicable decision records, screenshots or visual-reference documentation, version metadata, changelog, and release notes with the implemented behavior.
- Close v0.6 as a source release without adding a Review Queue, new forecast model, custom theme framework, installer, signing, update system, public binary distribution, or logo artwork.

### 34.12 v0.6 acceptance criteria

v0.6 is not complete unless all of the following are true:

1. Every completed v0.5 forecasting, history, lifecycle, scoring, search, Saved View, tag, CLI, backup, and export behavior remains semantically unchanged.
2. Schema version 15 remains current and no database migration runs solely for v0.6 presentation work.
3. New prediction is visibly an action, Dashboard/Predictions/Analytics are primary destinations, Settings is a bottom utility, and Prediction Detail is contextual rather than permanent navigation.
4. Binary and Numeric creation still require exactly their established minimum fields and save the parent plus first revision atomically.
5. Expanded and compact sidebar modes expose the same destinations and creation action with no clipped label, missing tooltip, or inaccessible icon-only control.
6. The preferred sidebar mode and safe window state survive restart, remain isolated by stable/development identity, and recover from invalid or off-screen geometry.
7. Presentation preferences never enter SQLite backup, CSV export, search, CLI output, history, freshness, lifecycle, or analytics.
8. Contextual Detail Back returns to the appropriate source and preserves the active Predictions archive context when applicable.
9. Opening Predictions does not automatically select its newest or first result, and hover never masquerades as selection.
10. Page controls retain stable placement across populated, empty, loading, success, warning, and error content states.
11. Question and the current type-appropriate forecast remain visually primary in creation and Detail.
12. Every custom surface, border, text role, accent, warning, destructive state, disabled state, and focus indicator remains legible in system light and dark modes.
13. Lifecycle, attention, forecast type, analytical meaning, and action consequence never rely on color or iconography alone.
14. Primary, secondary, quiet, and destructive action roles are consistent, and one action region ordinarily has only one primary committed action.
15. No common forecasting action is hidden solely for visual cleanliness, and every secondary or overflow action remains discoverable by mouse and keyboard.
16. Routine success acknowledgment does not require dismissal and does not reflow the active page.
17. Backup/export destinations and all actionable failures remain persistent; consequential writes retain explicit pre-write confirmation.
18. A transient notification contains no unique information whose disappearance would make the committed result unknowable.
19. Every listed global shortcut reaches the documented screen or shell action without mutating forecast data or overriding an unsafe modal context.
20. Logical tab order, visible focus, accessible names, tooltips for icon-only controls, and keyboard activation cover all primary workflows.
21. No essential action or information is available only through hover, color, animation, an icon, or a visual chart.
22. Long Questions, metadata, rationales, Journal entries, Reviews, terminal text, correction history, and Postmortems wrap and remain readable without silent truncation in canonical Detail contexts.
23. At the supported minimum logical size, controls do not overlap, required actions remain reachable, and scrolling is available wherever content cannot fit.
24. The desktop remains usable at 100%, 150%, and 200% Windows scaling with font-aware sizing and no machine-specific absolute geometry.
25. Search and structured filters produce the same grouped results, ranking, provenance, suggestions, Saved View behavior, and matched-context navigation as v0.5.
26. Analytics selects the same exactly-once observations and produces the same type-safe calculations as v0.5.
27. GUI and CLI continue to share the same canonical databases without adding visual-preference coupling or a synchronization subsystem.
28. Automated tests never read or write the user's real canonical database or real presentation settings.
29. The private frozen build contains and renders every required local style and icon resource after relocation.
30. The complete v0.6 application remains offline, local-first, single-user, and proportionate to a personal forecasting journal.

### 34.13 Explicitly outside v0.6

- A Review Forecasts queue, review scheduling, review sessions, concealed prior forecasts, anti-anchoring mode, or prompted forecasting checklist.
- Any new Prediction type, interval model, distribution, scoring method, analytical observation, lifecycle state, attention classification, or historical record.
- Any change to search parsing, source coverage, relevance weights, ranking, suggestion policy, Saved View semantics, or tag identity beyond a regression fix required to preserve v0.5.
- Semantic search, embeddings, a language model, web search, recommendation feed, behavioral telemetry, or query-history collection.
- Collections, favorites, pins, structured Sources/Evidence, attachments, Prediction relationships, graphs, or backlinks.
- A master-detail archive, permanent right-side inspector, task board, calendar, project tree, drag-and-drop workflow, timer, or productivity dashboard.
- Custom themes, a theme marketplace, custom CSS, wallpapers, glass effects, a bundled font, an independent Light/Dark selector, or user-selected tag colors.
- A custom-drawn title bar, system tray workflow, global operating-system hotkey, command palette, configurable shortcut editor, sound, notification-center integration, reminder, or background monitoring.
- A web frontend, QML rewrite, second GUI toolkit, Material framework, or new production UI dependency.
- CLI presentation preferences, a CLI review wizard, new CLI mutation behavior, machine-readable output, or live inter-process push refresh.
- A database migration, new CSV format, JSON or Markdown export, or restoration from analytical export solely for visual presentation state.
- Logo artwork, a normal Windows installer, signing, automatic updates, or public binary distribution.
- Copying Super Productivity source code, assets, branding, or its task-management feature structure.

---

## 35. Instruction to coding agents

Before implementing a milestone:

1. Read this specification fully.
2. Identify the milestone and affected invariants.
3. Inspect the existing code and tests.
4. Propose or implement the smallest coherent vertical change.
5. Add tests for historical integrity and domain behavior.
6. Verify the user-visible workflow end to end.
7. Report any product ambiguity instead of inventing a scope-expanding feature.

The guiding rule is:

> Let the user change their mind freely, but never let the application rewrite the fact that they used to think something else.
