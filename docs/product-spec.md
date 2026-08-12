# Reckonsolve — A Personal Forecasting Journal

## v0.1 Product Specification

Status: Approved product scope for implementation  
Platform: Windows desktop  
Working relationship to Predlog: Fresh successor project, not an extension of the existing CLI codebase

Related repository documentation: [Architecture](architecture.md) and [technical decision records](decisions/README.md).

---

## 1. Purpose

Build a local-first personal forecasting journal that lets one person:

1. make binary probabilistic predictions;
2. record the reasoning behind them;
3. update beliefs as information changes;
4. preserve the complete history of those updates;
5. resolve predictions against real outcomes; and
6. study calibration and forecasting performance.

The product is not merely a database of current probabilities. Its defining value is an honest historical record of what the user believed, why they believed it, and how those beliefs changed.

The v0.1 release is successful when it is useful enough to replace the user's old Predlog CLI for day-to-day binary forecasting.

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

> A local-first forecasting journal where you can make probabilistic predictions, explain your reasoning, update your beliefs over time without rewriting history, resolve outcomes, and study your calibration.

---

## 3. Constitutional product principles

These principles take precedence over implementation convenience.

### 3.1 Historical integrity

A saved forecast revision is immutable. The application may never silently overwrite a probability, rationale, or timestamp belonging to a historical revision.

Changing one's mind creates a new revision. It does not mutate the old one.

### 3.2 Belief updating is encouraged

Revising a forecast is a normal and desirable act. The interface should make it easy to move from one probability to another while preserving both.

### 3.3 Reasoning is first-class

The app must support more than probabilities. A forecast revision may contain its own rationale, and a prediction may accumulate journal entries even when the probability does not change.

### 3.4 Low floor, high ceiling

Creating a binary prediction requires only:

- a question; and
- a probability.

All additional structure is optional. The app may encourage useful detail, but it must not require boilerplate.

### 3.5 Probability does not decay

A stale forecast remains the probability the user last entered. The app may flag that forecast as needing attention, but it must never automatically lower, raise, or otherwise alter the probability.

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
- Package the application for normal use on Windows.

### Deferred to v0.2

- Numeric interval forecasting.
- Forecast Reviews, including a dedicated "Still at 60%" action.

### Explicitly later than v0.2 unless separately promoted

- Multiple-choice forecasts.
- Dedicated date forecasts.
- Full continuous or discrete probability distributions.
- Quantile elicitation.
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

The enduring Yes/No question plus its stable metadata and lifecycle state.

Example:

> Will I finish *Statistical Rethinking* before December 1?

### Forecast revision

A timestamped statement of probability and optional rationale. A prediction has one or more revisions. Revisions are immutable.

### Current forecast

The most recent valid forecast revision.

### Journal entry

A timestamped note about evidence or reasoning that does not itself change the forecast probability.

### Forecast deadline

The last time at which ordinary forecast revisions are allowed. It is optional.

### Expected resolution

The date or time by which the user expects the outcome to be knowable. It is optional and distinct from the forecast deadline.

### Resolution

The recorded Yes/No outcome and its associated resolution information.

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
- type, fixed to binary in v0.1;
- status;
- created timestamp; and
- updated timestamp for mutable metadata.

Optional fields:

- Background;
- Resolution Criteria;
- Forecast Deadline;
- Expected Resolution; and
- tags.

System-derived information should not be redundantly stored unless needed for correctness or performance. For example, Current Forecast should normally be derived from the latest valid revision.

### 7.2 ForecastRevision

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

### 7.3 JournalEntry

Required fields:

- stable identifier;
- prediction identifier;
- body;
- created timestamp; and
- reference to the forecast revision that was current when the entry was created.

The revision reference lets the app accurately show the probability held at the time without treating the journal entry as a forecast revision.

### 7.4 Resolution

Required fields:

- stable identifier;
- prediction identifier;
- binary outcome;
- resolved timestamp; and
- the forecast revision used for scoring, or enough information to derive it unambiguously.

Optional fields:

- factual resolution notes; and
- postmortem.

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
- `journal_entries`
- `resolutions`
- `tags`
- `prediction_tags`

Do not create a forecast-reviews entity in v0.1. Reviews are a v0.2 feature.

---

## 8. Editing and immutability rules

### 8.1 Forecast revisions

After a revision is saved, the normal application must not edit or delete it in place. A new probability creates a new row/event.

Example:

```text
Aug 12    60%
Aug 25    60% → 40%
Sep 14    40% → 50%
```

The Aug 12 record must never become "Aug 12 — 70%."

### 8.2 Prediction metadata

Background and tags may be edited normally.

Question wording, Resolution Criteria, and Forecast Deadline can affect what historical forecasts mean. v0.1 should at minimum warn before potentially meaning-changing edits. The data model must not assume that silent semantic rewriting is harmless.

A complete metadata-edit audit trail is a Later refinement, not a prerequisite for v0.1.

### 8.3 Journal entries

Journal entries belong to the historical timeline. Prefer append-only behavior. If v0.1 permits correcting a journal-entry typo, it must not affect forecast scoring or disguise a probability change.

### 8.4 Resolved predictions

Normal forecast revisions are disabled after resolution. Resolution correction may be supported with a deliberate confirmation flow, but casual toggling of an outcome is not acceptable.

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

Optional details are hidden behind a clear affordance such as "More details":

- Rationale
- Background
- Resolution Criteria
- Forecast Deadline
- Expected Resolution
- Tags

### 9.2 Probability input

The application accepts any whole-number probability from 0% through 100%, inclusive. Values such as 37% are valid; fractional percentages are not part of v0.1.

The initial design should make 10-point probabilities fast to enter:

```text
10  20  30  40  50  60  70  80  90
```

These controls are shortcuts, not constraints. The user must remain able to enter any permitted whole-number probability directly. At 0% and 100%, the interface may plainly note that the forecast expresses absolute certainty, but it must not block submission or require confirmation solely because an endpoint was chosen.

### 9.3 Creation behavior

Creating a prediction and its first revision must be atomic: either both persist or neither does.

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

After saving:

- the new revision appears in the timeline;
- Current Forecast changes to the new probability; and
- the probability-history chart gains a point.

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

Adding a journal entry must not:

- create a forecast revision;
- change the current probability; or
- reset the v0.1 Needs Attention clock, which is based on the latest forecast revision.

The last rule changes in v0.2 when explicit Forecast Reviews exist.

---

## 13. Probability-history chart

Every point corresponds to an immutable forecast revision.

Minimum requirements:

- probability on the vertical axis;
- time on the horizontal axis;
- revisions shown in chronological order;
- current and historical probabilities represented accurately; and
- sensible rendering when only one revision exists.

Hovering or selecting a point may show timestamp, transition, and rationale if the chosen UI toolkit makes this inexpensive. Rich interaction is not required for the first usable slice.

The chart must not treat journal entries as probability observations.

---

## 14. Lifecycle

### 14.1 Open

- Forecast revisions allowed.
- Journal entries allowed.
- Can be resolved or marked invalid.

### 14.2 Locked

The forecast deadline has passed.

- Normal forecast revisions are not allowed.
- Journal entries remain allowed.
- The prediction awaits an outcome.
- It can be resolved or marked invalid.

An Open prediction with no forecast deadline remains Open until resolved or invalidated.

### 14.3 Resolved

- Outcome is recorded as Yes or No.
- No further forecast revisions are allowed.
- The prediction is eligible for scoring.
- Resolution notes and a postmortem may be recorded.

### 14.4 Invalid

- The prediction is preserved.
- No further forecast revisions are allowed.
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

### 16.1 Needs Attention

In v0.1, a nonterminal prediction needs attention when its latest forecast revision is older than the configured stale threshold.

The interface should say "Forecast last updated," not "Last reviewed," because v0.1 does not record Reviews.

The exact default threshold was not settled in product design. Choose a clearly documented default during implementation and make it configurable without overbuilding the settings system.

### 16.2 Ready to Resolve

A prediction is Ready to Resolve when:

- it is not Resolved or Invalid; and
- its Expected Resolution has passed.

Ready to Resolve is an attention bucket, not a fifth canonical lifecycle status.

### 16.3 Locked

Locked predictions should be distinguishable from predictions that merely need attention or are ready to resolve.

A prediction may satisfy more than one attention condition. The UI must use clear, deterministic placement or badges rather than losing information.

---

## 17. Prediction browser

The Predictions screen provides:

- text search over question text;
- status filter;
- tag filter;
- a clear empty state; and
- navigation to Prediction Detail.

At minimum, filters cover:

- All, Open, Locked, Resolved, and Invalid; and
- individual tags.

Full-text search across rationales, Background, and journal entries is Later unless it is nearly free within the chosen architecture.

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

The exact binning scheme is an implementation choice that must be documented and tested.

### 18.3 Brier performance over time

Display forecasting performance over resolution time using a clearly labeled cumulative or rolling measure.

The first implementation may use cumulative mean Brier if that is simplest, but the label must say what is being calculated. Do not imply that movement proves skill improvement: forecast difficulty and composition may also change.

### 18.4 Filtering

Analytics should support All predictions and tag-filtered subsets if feasible within v0.1 without compromising core correctness.

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

The normal UI should encourage Invalid rather than Delete once a prediction has meaningful history. Because this is the user's private local database, v0.1 may use warnings and friction rather than absolute prohibition.

Resolved scored predictions should not be casually deletable from the normal interface. The purpose is to protect honest calibration statistics, not to deny the user ownership of their data.

Deletion behavior must be transactional and must not leave orphan records.

---

## 20. Backup and export

Backup and export are different features.

### Backup

A backup is sufficient for complete application recovery. It must capture the canonical SQLite state consistently, including related metadata required by the app.

Minimum UI:

- Back Up Now;
- destination selection or a clearly disclosed destination; and
- last successful backup time.

### CSV export

CSV is a portable analytical representation, not a complete relational restoration format.

The export must be documented well enough that fields and repeated entities are understandable. If several CSV files are required to represent predictions, revisions, journal entries, and resolutions honestly, prefer a clearly named export bundle over flattening away history.

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

The initial implementation direction is a Python desktop application using PySide6 and SQLite, packaged for Windows. This direction may be revisited only deliberately; product invariants must survive any technology change.

Required boundaries:

- SQLite is canonical.
- Database migrations must be deliberate and testable.
- Creating a prediction plus its first revision is atomic.
- Creating a revision is append-only in normal application logic.
- Resolution and invalidation are transactional.
- System-generated instants are stored in UTC and displayed in the computer's local time.
- Date-only values retain their calendar-date meaning and are not converted between time zones.
- Analytics queries must use the final eligible revision exactly once per resolved prediction.
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
- implement numeric forecasting in v0.1;
- implement Forecast Reviews in v0.1;
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

### Milestone 4: Immutable revisions

- Revise probability with optional rationale.
- Preserve every earlier revision.
- Enforce revision restrictions after lock or terminal state.

### Milestone 5: Timeline and journal

- Add journal entries.
- Show revisions and journal entries in one chronological timeline.
- Preserve which revision was current for each journal entry.

### Milestone 6: Probability-history chart

- Plot revision probability over time.
- Handle one or many revisions accurately.

### Milestone 7: Lifecycle and resolution

- Implement Open, Locked, Resolved, and Invalid behavior.
- Resolve Yes/No with optional notes and postmortem.
- Implement deliberate Delete versus Invalid behavior.

### Milestone 8: Dashboard

- Surface Open, Needs Attention, Ready to Resolve, and Locked predictions.
- Use latest revision time for v0.1 freshness.

### Milestone 9: Tags and prediction browser

- Browse all predictions.
- Search question text.
- Filter by status and tag.

### Milestone 10: Analytics

- Brier scoring.
- Reliability diagram.
- Clearly labeled Brier performance over time.
- Tests for final-eligible-revision selection and exclusions.

### Milestone 11: Backup and CSV export

- Produce a consistent recoverable backup.
- Export portable CSV data without erasing historical structure.

### Milestone 12: Windows packaging and polish

- Package for normal Windows use.
- Verify fresh install, upgrade/migration, backup, restart, and core user loop.

---

## 27. Cross-cutting acceptance criteria

v0.1 is not complete unless all of the following are true:

1. A prediction can be created using only Question and Probability.
2. Optional structure never blocks quick creation.
3. Restarting the app preserves all data.
4. Revising a forecast creates a new historical record.
5. No normal UI path silently rewrites an earlier revision.
6. A journal entry can be added without changing probability.
7. Forecast Deadline and Expected Resolution behave as separate concepts.
8. Locked predictions reject normal revisions but accept journal entries.
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
- atomic prediction plus initial revision creation;
- current-revision selection;
- lock-boundary behavior;
- resolution and invalidation transitions;
- final eligible forecast selection for scoring;
- exclusion of Invalid and unresolved predictions;
- Brier calculations;
- calibration bin assignment;
- Needs Attention and Ready to Resolve date logic;
- cascade/restrict behavior for deletion;
- database migrations;
- backup consistency; and
- reopen-after-restart persistence.

Use representative edge cases such as a single revision, several revisions at the same displayed probability, resolution before Expected Resolution, a missing Forecast Deadline, and time-boundary transitions.

---

## 29. Open implementation decisions

The application and project name is resolved as **Reckonsolve**. Probability input and time handling are resolved in Sections 9.2 and 24. The following choices were not fully settled at the product-design stage. Resolve them during the relevant milestone, document the decision, and do not let them expand scope:

- precise visual design system;
- default stale threshold;
- exact calibration binning scheme;
- cumulative versus windowed Brier trend for the first implementation;
- precise deletion restrictions after meaningful history exists;
- whether meaning-changing metadata edits receive a lightweight audit event in v0.1;
- exact CSV export layout; and
- installer/packaging format.

When making these decisions, preserve the constitutional principles and choose the smallest solution that supports genuine use.

---

## 30. v0.2 opening scope

The first planned additions after a stable v0.1 are:

### Numeric interval forecasting

Add numeric forecasts represented initially by lower bound, upper bound, and confidence level, together with appropriate resolution and analytics such as interval coverage, width/sharpness, and Winkler score.

### Forecast Reviews

Add an explicit way to record that a forecast was reconsidered and retained without creating a fake probability revision:

```text
Current forecast: 35%
[ Still 35% ]  [ Revise ]
```

Once Reviews exist, Needs Attention should use last thoughtful review rather than only the latest probability revision.

Neither feature should be partially prebuilt into v0.1 beyond avoiding schema choices that make later extension unnecessarily difficult.

---

## 31. Instruction to coding agents

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
