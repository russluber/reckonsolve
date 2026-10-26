# Prediction Detail Redesign — Living Design Draft

**Status:** Detail chapter of the active UX redesign; preferred directions recorded, validation outstanding. Implementation authorization: Not authorized.

**Version:** 0.3

**Date:** 2026-10-25

**Primary focus:** Preserve the v0.2 Adaptive design and incorporate completed-exercise-oriented One-Shot Detail, answer entry, archival-first Invalid Detail, and contextual Mark Invalid preparation. The next local revision is v0.4 for responsive/accessibility and draft-safety design and validation when this chapter is revisited.

**Project home:** The [master experience redesign](reckonsolve-experience-redesign.md) owns overall scope, progress, priorities, cross-cutting dependencies, and contract alignment. This chapter owns the Detail journeys, R-01–R-42, and local validation cases. Follow the [design charter](../../product-spec.md#active-ux-redesign-charter) and [shared review procedure](../development.md#ux-design-and-review). **Workflow alignment:** 2026-10-26; UX design remains v0.3, with no new requirements or validation evidence.

> **Authority:** This document captures observed user needs, preferred interface concepts, and open questions. It does **not** supersede [the product specification](../../product-spec.md), alter any forecasting contract, or authorize Codex to implement changes. The [forecasting guide](../../guides/forecasting-guide.md) remains the source for admissible questions and the Rulebook. The [user guide](../../guides/user-guide.md) describes existing workflows. Apparent conflicts require explicit resolution with the user before any implementation.

## Contents

1. [Purpose and design philosophy](#1-purpose-and-design-philosophy)
2. [Status of the research and design](#2-status-of-the-research-and-design)
3. [Adaptive Binary user journey](#3-user-journey-reconsider-an-adaptive-binary-forecast)
4. [Layout concepts and selected direction](#4-layout-concepts-and-selected-direction)
5. [Integrated nonmodal revision and lifecycle extensions](#5-integrated-nonmodal-revision)
   - [Adaptive Numeric](#54-adaptive-numeric-entry-comparison-and-history)
   - [Locked Adaptive and resolution](#55-locked-adaptive-and-deliberate-resolution)
   - [Resolved Adaptive and Postmortem](#56-resolved-adaptive-results-first-reflection-later)
   - [One-Shot Detail and Add Answer: R-36–R-40](#57-one-shot-detail-completed-exercise-and-later-answer-entry)
   - [Invalid Detail and Mark Invalid: R-41–R-42](#58-invalid-detail-archival-reading-and-contextual-invalidation)
6. [Requirements register: R-01–R-42](#6-consolidated-requirements-register-r-01-through-r-42)
7. [Boundaries and invariants](#7-boundaries-and-invariants-codex-must-preserve)
8. [Remaining exercises and v0.4 validation](#8-remaining-design-exercises)
9. [Preferred direction and unresolved decisions](#9-preferred-direction-vs-unresolved-decisions)
10. [Future Codex handoff](#10-future-codex-handoff-procedure)
11. [Draft history / update log](#11-draft-history)

## 1. Purpose and design philosophy

Reckonsolve is a local-first, single-user Windows forecasting journal devoted to **calibrated observational judgment under personally relevant uncertainty**. It is a tool for predicting and learning about uncertain parts of the world, not for self-control, goal enforcement, social forecasting contests, or manipulating the world to make predictions come true.

The product's governing commitment is:

> Let the user change their mind freely, but never let the application rewrite the fact that they used to think something else.

The redesign should make this philosophical identity apparent through ordinary interaction:

1. **Clarity of judgment.** Keep the Question, current committed forecast, and the exact meaning of the outcome readily understandable.
2. **Freedom to reconsider.** Make evidence-driven revisions and deliberate reaffirmations natural, without rewarding or penalizing the act of changing one's mind.
3. **Integrity of history.** Distinguish recorded beliefs, supporting evidence, Reviews, and audited corrections without obscuring their original chronology.
4. **Learning over score-chasing.** Let existing scores, charts, and user-authored reflections illuminate how judgment developed, rather than gamifying forecast count or presenting sparse outcomes as conclusive. Individualized automated learning feedback is outside this redesign; R-33 and R-34 are withdrawn.
5. **Calm deliberation.** Make reasoning comfortable and nonintrusive; avoid modal interruptions for activities in which the user is actively thinking.

These are **UX objectives**, not new product rules. Reckonsolve's existing distinctions between observational forecasts, policy-conditioned forecasts, and inadmissible agentic forecasts remain unchanged.

## 2. Status of the research and design

The v0.1 draft recorded a first-person user-journey interview, an inspection of the existing code and documentation, and comparison of three low-fidelity design concepts. The v0.2 revision incorporated the subsequent Adaptive Numeric, Locked Adaptive, Resolved Adaptive, and Postmortem decisions. This v0.3 revision preserves those directions and consolidates the One-Shot and Invalid UX exercises as R-36–R-42. The interview provides qualitative evidence about how the user currently works; preferred layouts still require prototype and usability validation.

This chapter's scope is Prediction Detail, including its contextual editors and terminal confirmation. Dashboard entry points describe the current journeys; the [master redesign](reckonsolve-experience-redesign.md) owns exploration of their proposed Journal replacements. A chapter boundary is not a prohibition on that wider authorized design work. Adaptive, One-Shot, and Invalid have preferred directions from completed design discussions. None is implemented, prototype-validated, or manually accepted as software. The prospective local v0.4 covers responsive layouts, accessibility, draft safety, and content stress; the master determines overall sequencing.

Use the [shared design maturity labels](../development.md#design-maturity-and-authorization) for decisions and review evidence. The following existing register annotations describe needs, directions, and open work; they do not grant implementation authorization:

- **Observed need:** Supported by the user's account of current behavior or pain points.
- **Preferred design direction:** Explicitly liked or selected by the user, but not necessarily finalized or implementation-ready.
- **Open:** Requires more investigation, usability testing, or comparison against other Prediction types and lifecycle states.
- **Withdrawn:** Explicitly rejected as a direction; retained by ID for traceability, not deferred for later implementation.
- **Implementation authorization:** **Not authorized.** Track this independently of design maturity; no item has reached Validated or Approved design through the workflow alignment. Approval of a design discussion does not authorize code, schema, or domain changes.

### Existing code and contract references

- [Product specification — desktop presentation contract](../../product-spec.md#34-desktop-presentation-contract)
- [Product specification — Adaptive contract](../../product-spec.md#35-adaptive-forecasting-contract)
- [Product specification — One-Shot contract](../../product-spec.md#36-one-shot-prediction-contract)
- [Product specification — terminal facts, corrections, and reflection](../../product-spec.md#terminal-facts-corrections-and-reflection)
- [ADR 0021 — One-Shot originals and transcription snapshots](../../decisions/0021-one-shot-originals-and-transcription-snapshots.md)
- [Main window and navigation](../../../src/reckonsolve/ui/main_window.py)
- [Binary and Numeric Detail screens](../../../src/reckonsolve/ui/screens.py)
- [One-Shot UI](../../../src/reckonsolve/ui/one_shot.py)
- [Dashboard](../../../src/reckonsolve/ui/dashboard.py)
- [Visual system](../../../src/reckonsolve/ui/visual_system.py)

The current UI is native PySide6/Qt Widgets, with a centralized palette-aware visual system. It has contextual navigation to Prediction Detail, immutable historical operations, and existing safety/validation/keyboard-accessibility expectations. The redesign should reuse these foundations.

## 3. User journey: Reconsider an Adaptive Binary forecast

### 3.1 Current (*as-is*) journey

The usual trigger is **new evidence from outside Reckonsolve**. The user tends to go to Dashboard, where Open predictions are readily available, rather than to the Predictions browser.

| Stage | Actual behavior | Finding |
| --- | --- | --- |
| Encounter evidence | Learns something potentially relevant to an active prediction. | Reconsideration is primarily evidence-driven, not schedule-driven. |
| Locate | Opens Dashboard, finds the Open prediction, clicks it. | Dashboard is the practical working set of active forecasts. |
| Reorient | Glances at the Question and current forecast percentage. | Question and committed belief must be prominent. |
| Recover reasoning | Scrolls down to Timeline, sometimes through extensive history. | Current rationale and surrounding evidence are not immediately accessible. |
| Reassess | Sometimes returns to Deadline, Background, or Resolution Criteria. | The forecasting contract matters during deliberation. |
| Choose action | Scrolls back up and selects Revise Forecast, Add Journal Entry, or Still at X% / Review. | Choice of action follows reconsideration, not necessarily the other way around. |
| Form a revision | Works out the new percentage **inside** the current modal dialog, usually before writing rationale, but sometimes iterating. | Revision editor is a space for forming judgment, not only entering it. |
| Commit | Saves one deliberate revision. | Intermediate numbers are drafts; only the chosen forecast enters history. |
| Verify | Checks updated percentage, scrolls to the new rationale and rereads it. | Verification is part of a successful task. |
| Appreciate trajectory | Looks at Probability History to see how the percentage changed over time. | Graph is a valued visual summary, often for appreciation rather than formal analysis. |

**Related but distinct behavior:** At times, the user Journals new evidence to remember it for later, without reconsidering their probability immediately. A Forecast Review is rarer and may involve rereading the *entire* Timeline oldest-to-newest before affirming an unchanged forecast.

### 3.2 Confirmed pain points

1. **Long vertical traversal:** question and actions near the top, Timeline much lower, Probability History at the bottom; user repeatedly scrolls between these.
2. **Modal revision interruption:** the dialog blocks interaction with underlying Prediction Detail. Clicking the background produces Windows' modal alert sound/flashing behavior. The user wants to consult context while forming a judgment, not be forced into a restrictive dialog.
3. **Scattered post-save verification:** updated percentage, new rationale, and graph are separated spatially.

**Existing strengths worth retaining:** The Binary probability control's typed entry, spin arrows, mouse-wheel adjustment, and preset percentage buttons are already satisfactory. The rationale box is generally usable; more room for multi-paragraph text would be beneficial but is not a primary pain point.

### 3.3 Target (*to-be*) journey — hypothesis

1. Open from Dashboard after encountering evidence.
2. Remain oriented through a compact persistent header: Question, **committed** forecast, exact Forecast Deadline, status, and available actions.
3. Read recent Journal evidence and full revision rationales in a comfortable Timeline. If needed, jump to the revision that established the current probability; optionally read oldest-first for a full review.
4. Consult Resolution Criteria and Probability History in the adjacent contextual pane, without losing Timeline position.
5. Open a **nonmodal contextual revision editor**, with Timeline and criteria remaining accessible.
6. Experiment with draft probability and rationale. Explicitly commit only the final judgment.
7. Automatically return to Overview on success: updated current probability, newly added rationale immediately accessible, and refreshed graph. Retain draft and show persistent error on failure.

This is a task sequence, **not** a demand for a wizard or prescribed cognitive order. The user must be able to move freely between reasoning and numbers.

## 4. Layout concepts and selected direction

Three low-fidelity concepts were discussed:

- **A — Split Workspace:** two working panes below a forecasting header: Timeline left, contextual tools right.
- **B — Modular Workbench:** a VS Code-like arrangement with three independently managed/resizable panels.
- **C — Document + Inspector:** an Obsidian-like dominant reading document with a persistent inspector.

**Preferred direction:** **A**, borrowing **C's comfortable journal-reading experience**. B's complexity has no demonstrated corresponding user need so far. The preferred desktop proportions are now 60/40 Timeline/Context in Overview and 40/60 Timeline/editor while writing. These are starting proportions for prototyping, not fixed pixel dimensions or implementation approval.

### 4.1 Structural sketch

```text
+-----------------------------------------------------------------------+
| PERSISTENT FORECAST HEADER                                             |
| Full Question                                            Adaptive/Open |
| CURRENT COMMITTED FORECAST: 65%        Forecast Deadline: [exact time]  |
| [Revise] [Add Journal] [Forecast Review] [More...]                      |
+------------------------------------------+----------------------------+
| TIMELINE ~60%                            | CONTEXT / TOOLS ~40%       |
| independently scrollable                | independently scrollable   |
|                                          |                            |
| Journal, Oct 23 [preview / expand]       | Resolution Criteria        |
| Journal, Oct 21 [preview / expand]       | full short text visible    |
| Revision, Oct 18, 50% -> 65%             |                            |
|   CURRENT FORECAST ESTABLISHED HERE      | Probability History        |
|   full rationale                         | [historically faithful     |
| Review, Oct 15                           |  time-series graphic]     |
| ... older history ...                    |                            |
|                                          | On Revise: contextual      |
|                                          | editor replaces graph     |
+------------------------------------------+----------------------------+
```

This depicts **relationships, not final dimensions**. In Overview, the Timeline is the primary reading surface at approximately 60% of workspace width, with Context at 40% (R-24). During revision, reverse to approximately 40% Timeline and 60% editor (R-25), retaining readable criteria. The later Postmortem editor uses the same 40/60 arrangement (R-35). Resizability, minimum pane widths, transition behavior, and narrow-window stacking remain open; these ratios must not override legibility or accessibility.

### 4.2 Compact persistent forecast header

**Preferred:** Keep the essential context visible even when reading far back in the Timeline. In Open and Locked, include Question; current *committed* probability or complete five-quantile Numeric forecast; mode/status; exact immutable Adaptive Forecast Deadline; and accessible actions appropriate for that lifecycle. Locked retains this orientation. Resolved gives outcome and results first prominence, with committed forecast and timing still available as context (Section 5.6).

A larger header that compresses when navigating is an optional visualization idea, **not a settled requirement**. Avoid truncation that changes the meaning of the Question, overlarge sticky chrome, aggressive countdowns, and draft numbers masquerading as committed beliefs.

**Time distinction:** The Forecast Deadline is the end of the Adaptive revision window, not necessarily the date of the predicted event or optional Expected Resolution. A relative "time left" indication, if used, must not make these synonymous or suggest that the probability decays automatically.

### 4.3 Timeline — narrative history

The user prefers **newest first by default**, with the ability to switch to oldest-first for comprehensive Forecast Reviews. All entries retain their actual causal/historical sequence; sorting is a presentation choice.

| Event | Preferred rendering | Why |
| --- | --- | --- |
| Forecast Revision | Full rationale by default, visible before/after forecast values and timestamp; unusually long prose may be collapsible | Deliberate change of probabilistic judgment |
| Journal | Compact, readable preview; expand readily to full entry | Evidence/reasoning may have been noted without reconsidering the forecast |
| Forecast Review | Clear unchanged-forecast event, timestamp, and readable note, with long content expandable | Deliberate reconsideration rather than revision |
| Current revision | Subtle marker **at its real Timeline position**, plus header jump-to-revision action | Rapid access to the reasoning that established the current forecast |

**Do not relocate or duplicate the latest revision above more recent Journals.** Those Journals may contain evidence for future consideration and deserve their correct place. Do **not** invent a formal "unprocessed evidence" status: a Journal does not imply that the user has or hasn't considered its content.

Preserve the distinction between **last revised** and **last considered** (Revision or Review), and do not make Journal activity refresh Needs Attention. Preserve Journal correction history at the original Timeline position and the ability to navigate from historical search matches to superseded text.

Aesthetically, the Timeline should be readable like a thoughtful journal: suitable line length, comfortable typography and spacing, selectable text, quiet timestamps, and clear event types. Avoid dashboard-like competition among many identical cards.

### 4.4 Context / Tools — supporting workspace

In the ordinary **Overview** state, show Resolution Criteria in place (usually a couple sentences or a paragraph), and the type-appropriate visualization nearby: Binary Probability History or the current Numeric distribution. Background is secondary but remains accessible. If criteria become long, provide an obvious readable expansion route rather than silent truncation. An unset optional field must remain visibly unset; this design adds no required criteria text.

The Binary graph is a compact summary of the *probabilistic journey*. It complements rather than replaces the textual Timeline. Draw only history implied by real committed forecasts and their times; do not smooth or visually invent intermediate beliefs. Numeric instead shows one current five-quantile distribution without a history overlay; its historical changes are communicated through interval-oriented Timeline entries (Section 5.4).

Both panes should scroll independently during extended reading. Preserve useful pane positions across a temporary editor switch where feasible; test trackpad, wheel, keyboard focus, and narrow-window nested-scroll behavior. Do not make multiple tiny scrollbars the dominant interaction.

## 5. Integrated nonmodal revision

### 5.1 Editor state

Clicking Revise replaces the type-appropriate Overview visualization in the contextual pane with the **Draft Revision** editor. The desktop split changes from 60/40 Timeline/Context to 40/60 Timeline/editor. The Timeline and Resolution Criteria remain accessible without a modal focus trap. Numeric adds the current/draft comparison described in Section 5.4.

**Editor content and behavior:**

- Clearly label the **current committed** forecast separately from the **draft new** forecast.
- Preserve the existing Binary input: direct percentage entry, up/down spin controls, mouse wheel, and current preset buttons. A new slider is **not** requested.
- Put probability first and rationale second, reflecting the user's most common sequence, but permit unrestricted movement between them.
- Provide comfortable rationale space, potentially auto-expanding until a sensible maximum height, then scrolling within the field.
- A draft may be adjusted repeatedly without recording historical revisions, score observations, or freshness changes.
- It should be possible to revisit Overview/graph without discarding a current draft. Exact navigation and focus rules remain to be validated.
- Use a clear explicit **Commit Revision** action, a non-destructive Discard/Cancel path, and suitable keyboard semantics.

### 5.2 Commit and verification

**On successful commit:**

1. Exit the editor and **automatically return to Overview**.
2. Update the committed forecast in the persistent header.
3. Display the newly committed revision and full rationale at the top of the newest-first Timeline (or otherwise immediately in view).
4. Restore the 60/40 Overview split and refresh Binary Probability History or the Numeric current-distribution visualization with the new *committed* data.
5. Optionally display a subtle, nonblocking success notification; refreshed canonical content remains the durable evidence of success.

**On failed commit:** Retain the draft in the editor; show a clear persistent error; do not create a partial historical entry or incorrectly show success. Existing Deadline checks, no-op checks, optimistic concurrency, atomicity, and validation remain authoritative. Behavior on navigation away or application close with an unsaved draft is an **open interaction question**; do not silently invent a persistent draft data model.

### 5.3 Distinct action meanings

- **Revise:** A changed, complete Adaptive forecast is committed as an immutable new revision, if eligible.
- **Add Journal Entry:** Evidence or reasoning is recorded without changing the forecast or attention freshness.
- **Forecast Review / Still at X% / Keep current forecast:** A deliberate unchanged forecast is recorded as a Review (while eligible), which changes last-considered/attention freshness without inventing a revision. Numeric wording refers to the complete forecast/distribution.

The action region may be a quiet header toolbar rather than a standalone card. Sections 5.5–5.6 establish the preferred Locked, Resolve, and Resolved direction. Detailed action placement, Edit Details, Mark Invalid, guarded Delete, and correction routes still require validation; consequential actions retain their existing confirmations and safeguards.

### 5.4 Adaptive Numeric: entry, comparison, and history

**R-22 — Guided yet unrestricted entry.** Present the inputs in the suggested outside-in order: **90% interval** (`q05`, `q95`), **median** (`q50`), then **50% interval** (`q25`, `q75`). Keep all five fields available together, prefilled from the committed forecast for revision. The user may edit in any order and move freely between values, rationale, Timeline, and criteria. Guidance is not a wizard, a forced sequence, or a new confidence selector. Unit, precision, and value constraint remain visible immutable context. Preserve exact values, valid ties, and existing validation; never sort, round, or silently repair crossing values.

**R-23 — Current/draft comparison.** In the wider editor pane, show **Current committed** and **Draft revision** side by side with aligned 90% interval, median, and 50% interval rows. All five values must remain inspectable; the median alone cannot stand for a complete forecast. Keep rationale below the forecast controls with comfortable writing space. An incomplete or invalid draft must be visibly incomplete or invalid, never rendered as a valid committed distribution. Exact comparison geometry and any draft preview remain prototype questions; do not add a historical distribution overlay.

```text
NUMERIC REVISION — preferred desktop arrangement
+--------------------------+--------------------------------------------+
| TIMELINE ~40%            | CONTEXT / EDITOR ~60%                      |
|                          | Resolution Criteria (readable)             |
| Journal preview          | Unit / precision / constraint (read-only) |
| Numeric revision         | Current committed   | Draft revision       |
|  90%: [q05, q95]         | 90%: [10, 90]       | [q05] to [q95]      |
|  Median: q50             | Median: 50          | [q50]               |
|  50%: [q25, q75]         | 50%: [30, 70]       | [q25] to [q75]      |
| Full rationale           | Rationale [comfortable multiline editor]  |
| ... correct chronology   | [Commit Revision] [Discard] [Overview]    |
+--------------------------+--------------------------------------------+
```

Numbers above are illustrative, not defaults. R-24 and R-25 apply the 60/40 Overview and 40/60 editing proportions to both Adaptive types. Side-by-side comparison is the wide-window direction; narrow layouts must retain explicit labels and all values even if stacking is necessary.

**R-26 — Interval-oriented Numeric Timeline.** Render each complete Numeric forecast as its 90% interval, median, and 50% interval, with unit, real commit time, rationale, and readable before/after values on revisions. Preserve every quantile and causal position, including repeated values. Journal and Review anchors use the type-appropriate forecast and remain distinct event types. Do not reduce the history to a median trajectory or imply a Numeric trajectory score.

**R-27 — Current distribution without history overlay.** In Numeric Overview, show only the current committed five-quantile distribution through the existing implied central CDF, alongside its exact text summary. Distinguish elicited anchors from interpolation, show ties as jumps, and invent no outer tails or full density. Historical distributions remain available through the Timeline. This is a presentation of current belief, not a Numeric probability-history chart or an input to scoring.

### 5.5 Locked Adaptive and deliberate resolution

**R-28 — Continuity at the Deadline.** Locked retains the Question, complete latest committed forecast, immutable Deadline, Timeline, and type-appropriate Overview visualization in the familiar workspace. Explain that the forecasting window has closed. Revision and Forecast Review are unavailable; Journal, Resolve, and Mark Invalid remain available under existing eligibility rules. Locking creates no new forecast or terminal fact. The exact disabled-versus-hidden treatment of ineligible controls remains a prototype detail, but their unavailability must be understandable.

**R-29 — Criteria in view.** Keep Resolution Criteria readable in Locked Overview and while preparing resolution, alongside the Timeline. Use an explicit unset state when absent and a clear expansion route for long text. Criteria need not be copied into the form or made mandatory. Retaining context must not allow a material redefinition of the proposition.

**R-30 — Inline nonmodal resolution form.** Resolve opens a contextual form in the right pane so the user can consult history and criteria while entering **Yes/No** or the exact **Numeric actual value**, effective resolution time, and optional factual Resolution notes. Give the form adequate width using the 40/60 editing arrangement. Data entry alone creates no terminal record. Keep a clear Cancel path and persistent validation errors without losing input. The same resolution pattern applies when an eligible Adaptive forecast is still Open; it does not require waiting for Locked.

**R-31 — Separate terminal confirmation.** Proceeding from the form opens a distinct, explicit modal confirmation before the one-way write. Show the complete Question, proposed **outcome/actual value**, **effective resolution time** with unambiguous time-zone context, and **latest committed forecast** (probability or all five Numeric values, revision identity/time, and unit where applicable). State that resolution ends forecasting and allows audited factual corrections rather than reopening. Cancelling confirmation returns to the populated form. The ordinary deliberation workspace remains nonmodal; this consequential decision retains the specification's modal safeguard.

```text
LOCKED OVERVIEW (60/40)             RESOLUTION ENTRY (40/60)
Timeline | Criteria + visualization  Timeline | Criteria + outcome/time/notes
         | [Journal] [Resolve]               | [Continue to confirmation]
                                                    |
                                      Separate modal confirmation
                                      - outcome / exact actual value
                                      - effective time + zone
                                      - latest committed forecast
                                      [Confirm resolution] [Back]
                                                    |
                                      Atomic write -> Resolved results
```

The **latest committed forecast is context, not a promise of scoring eligibility**. Scoring uses the existing cutoff `C = min(R, T)` and immutable history: Numeric selects the latest revision strictly before that cutoff; Binary scores the eligible standing path with its existing neutral-truncation rule. A later committed revision remains visible even when excluded. The confirmation must not label the latest revision as the scoring forecast automatically; any eligibility summary must be derived from the proposed effective time. `R <= t0` remains explicitly unscored, and effective time cannot exceed original recorded-at. Recorded-at is supplied by the application at commit, not entered as another user timestamp.

Existing transaction-time eligibility and reviewed-context checks remain authoritative. If a commit fails or context is stale, preserve the form and show the error; require the user to review refreshed facts before another confirmation. No partial resolution, fabricated time, or silent overwrite is permitted.

### 5.6 Resolved Adaptive: results first, reflection later

**R-32 — Results-first landing.** Normal entry to Resolved Detail, including immediately after resolution, leads with the outcome/actual value and existing type-appropriate scorecard, or an explicit unscored explanation. Keep Question and Resolved status clear. Effective resolution time and immutable recorded-at remain distinct, and the scoring cutoff/eligible history remain inspectable. The committed forecast is supporting context rather than an active-edit invitation. Use Binary Trajectory Brier or Numeric WIS under their existing contracts; disclose existing diagnostics without inventing a new score or personal skill assessment. Timeline, criteria, historical reasoning, and transparent corrections remain available. A search link to a specific historical match still opens that matched context.

**R-33 and R-34 — Withdrawn.** The user decided not to pursue individualized automated learning feedback because reliable per-prediction interpretation would add too much complexity. Neither direction is an open question, a deferred feature, nor an implementation task. Do not generate personalized diagnoses, lessons, or recommendations from a single result. This withdrawal does not remove existing factual scorecards, diagnostics, aggregate Analytics, or user-authored reflection.

**R-35 — Deferred, open-ended Postmortem editor.** The user's usual later entry point is Dashboard's existing **Needs Postmortem** section. Reflection often involves rereading the forecast's reasoning, though the user also writes broader retrospective thoughts. Do not require reflection immediately after resolution. Provide an explicit Postmortem writing state with approximately **40% Timeline / 60% editor**, so the complete record can be consulted while writing freely. Keep results and criteria accessible as context, and preserve the useful Timeline reading position where feasible.

```text
RESOLVED LANDING
Question / Resolved
Outcome or actual value | existing scorecard or explicit unscored reason
Effective time / recorded-at / forecast context
[Write or edit Postmortem] [eligible correction actions]
Timeline and supporting context remain accessible

POSTMORTEM WRITING — preferred desktop arrangement
+--------------------------+--------------------------------------------+
| TIMELINE ~40%            | POSTMORTEM EDITOR ~60%                     |
| Prior forecasts          | Outcome / results context                 |
| Rationales               | [Open-ended multiline reflection]         |
| Journals and Reviews     |                                            |
| Resolution / corrections | [Save Postmortem] [Cancel]                 |
+--------------------------+--------------------------------------------+
```

The Postmortem is optional free text: no required questionnaire, structured lesson fields, automatic diagnosis, or mandatory explanation for Skip. Retain the existing option to supply a Postmortem during Resolution; the redesign favors returning later without removing that product-spec capability. Factual Resolution notes remain distinct from reflection. Saving, correcting, or clearing uses the existing audited terminal-text operations with prior versions recoverable; Cancel writes nothing and a failed save retains text. **Skip Postmortem** preserves its existing immutable completion fact, leaves score/state unchanged, and permits later reflection without putting a skipped blank record back into the queue. The precise placement of optional resolution-time reflection and Skip remains to be prototyped.

### 5.7 One-Shot Detail: completed exercise and later answer entry

**Observed journey and rationale.** The user generally settles a One-Shot estimate and checks the already-existing answer outside Reckonsolve, then transcribes both later. Opening Detail is usually a chance to inspect the result of a completed exercise. It is not ordinarily a workspace for ongoing belief revision. The supported alternative—saving the forecast before checking and adding the answer later—still needs a clear route. Neither path requires proof of an external commitment or a newly precise timestamp.

**R-36 — Completed-exercise-oriented Detail.** Normal entry after saving an answered One-Shot should immediately orient the user to Question, Binary/Numeric type, One-Shot mode, Resolved status, the estimate they made, and the answer. Keep the shared calm visual grammar and source-aware Back navigation, while adapting the content hierarchy to this shorter exercise. Preserve rationale, Background/checking method, tags, Journals, any saved Resolution Criteria, Definition history, reported times, and app-recorded times. Do not force an Adaptive revision workspace, Probability History path, or a large empty Timeline to dominate a short record. Historical search navigation still takes the user to its matched context.

**R-37 — Immediate score inspection.** Put the original estimate, answer, and existing type-appropriate score together at the top of answered Detail. Binary shows the Yes probability, Yes/No answer, and ordinary Brier. Numeric shows all five quantiles through the 90% interval, median, and 50% interval, immutable unit/precision/constraint, actual value, and WIS; existing factual decomposition can be secondary disclosure. Lower is better under the existing contracts. This gives immediate feedback about the transcribed exercise without generating advice or a diagnosis of the user's skill.

Original and effective facts must be unambiguous after a correction: the current score uses the **effective corrected forecast and answer**, while the immutable original estimate/answer and complete audit chain remain readily inspectable through clearly labeled original/effective presentation. Do not put an original value beside a corrected score as if that value produced it. A compact corrected-facts summary with an adjacent original disclosure is an illustrative option; exact disclosure geometry remains open. No answer means no score; Invalid is explicitly unscored. Do not substitute Adaptive Trajectory Brier, Initial/Final/Delta WIS, cutoff selection, hold-initial, Updating Gain, or elapsed-time weighting. Scores appear after successful save, not as answer-entry previews or score-driven suggestions.

```text
ANSWERED ONE-SHOT — illustrative content hierarchy, not fixed dimensions
Question                                      Binary/Numeric | One-Shot | Resolved
Estimate as originally entered: probability OR 90% / median / 50% + unit
Answer: Yes/No OR exact actual value           Brier OR WIS
If corrected: effective forecast + answer + their score; original facts disclosed
[Postmortem / existing reflection route]       [More... Correct transcription]
Supporting context: rationale, Background, reported times / app entry times
Timeline, saved criteria, Definition and correction histories remain accessible
```

**R-38 — Secondary, discoverable Correct transcription.** The ordinary task is inspecting the recorded result; a copying repair should not compete with the answer or score. Keep **Correct transcription** plainly discoverable through a labeled secondary action or clearly named menu item, available by keyboard and never solely on hover. Preserve the existing route while waiting and after answering, subject to lifecycle safeguards. Explain that it repairs copied facts, not a change of mind after checking. Use the existing complete before/after snapshots, app timestamps, optional correction note, validation, concurrency checks, and applicable correction confirmation. Originals remain recoverable, the effective score recomputes, and the record still contributes at most one answered observation. A correction while waiting must not hide an answer added later. Placement and disclosure details need prototype validation; no new correction model or required explanation is introduced.

**R-39 — Waiting for Answer.** When saved without an answer, lead with Question, One-Shot, **Waiting for answer**, and the complete saved forecast. Make **Add Answer** the prominent next action. Eligible Journal, metadata, Correct transcription, and Mark Invalid routes remain available without competing with it. There is no score yet. Omit Adaptive Deadline, Expected Resolution planning, revisions, Forecast Reviews, staleness attention, and trajectory concepts rather than displaying inactive Adaptive machinery. Waiting for answer remains a presentation of the existing nonterminal state, not a new canonical status.

**R-40 — Compact conventional Add Answer dialog.** Add Answer opens one conventional modal dialog for this short transcription task. Show Question and the saved effective forecast as read-only context; accept Yes/No or the exact Numeric actual value at the existing immutable unit/precision/constraint, optional reported answer-check time, and existing optional factual notes/reflection. Keep optional content subordinate and within established capabilities. Do not make the user re-enter their forecast or pass through a wizard, review page, and repeated confirmation for the same answer.

The dialog itself must make the terminal consequence explicit: its deliberate **Add Answer** save resolves the One-Shot, preserves the original forecast, and permits audited transcription correction without reopening forecasting. Use a clear Cancel path and safe keyboard/default focus. The preferred flow is **open dialog → enter/review answer → explicitly save → answered Overview**, with the existing score immediately inspectable. Cancel writes nothing. Failed validation, lock contention, or stale context retains input with a persistent error; success is shown only after the atomic operation succeeds.

```text
WAITING FOR ANSWER                         ADD ANSWER — one modal decision
Question | One-Shot | Waiting for answer   Question + saved forecast (read-only)
Saved forecast                            Answer: [Yes/No OR exact actual + unit]
[Add Answer]                              Optional reported checked time / notes
Secondary eligible actions                Resolves this One-Shot; no reopening
                                          [Add Answer] [Cancel]
                                                    |
                                          Atomic save -> answered Overview
                                          Forecast + answer + Brier/WIS
```

**Documentary time stays documentary.** Reuse the [One-Shot time contract](../../product-spec.md#362-durable-model-recorded-history-and-time): reported forecast-finalized and answer-checked wall minutes are optional, may be approximate or equal, retain any supplied offset, and stay distinct from immutable app-entry instants. Do not convert them into an Adaptive effective resolution instant, demand seconds, compare them as eligibility cutoffs, or use them to gate/weight scores. The answer dialog adds the answer's documentary report; it must not silently replace the earlier forecast report. Any repair uses the established audited route.

**Confirmation boundary.** R-40 deliberately proposes removing the current extra confirmation after the Add Answer dialog's save. The single dialog must itself satisfy the [specification's explicit modal terminal-decision safeguard](../../product-spec.md#347-feedback-and-nonblocking-status-notifications); it is not permission for an unreviewed background write. Verify the exact wording and safe submission behavior in v0.4 and reconcile any remaining conflict with the authoritative specification before implementation. This simplification does not remove Adaptive resolution's separate confirmation (R-31), Mark Invalid's separate confirmation (R-42), or correction safeguards.

### 5.8 Invalid Detail: archival reading and contextual invalidation

**Observed journey and rationale.** The user rarely revisits Invalid records, but sometimes reads them to learn how to formulate better questions and forecasts. A poorly specified original question is a common reason for invalidation. On return, the recorded reason is usually the primary reference; Question, Resolution Criteria, and relevant history also help double-check whether invalidation was appropriate. The interface should support the user's own reflection without inferring lessons, recommending a rewritten question, or treating the record as an active forecast.

**R-41 — Archival-first Invalid Overview.** Normal entry leads with the full Question, mode/type, **Invalid**, immutable recorded decision time, a prominent effective **recorded reason**, and the explicit statement **Not scored**. If no optional reason was recorded, say so rather than inventing one. Show the latest historical forecast as context with the complete type-appropriate values. Make Question, saved Resolution Criteria, Background, protected Definition history, and the full forecasting record easy to consult. Preserve Adaptive revisions/Reviews and their real chronology where present; preserve One-Shot originals/transcription corrections and Journal histories where applicable. Use readable disclosures and selectable text; do not require every audit version to be expanded on arrival.

The Overview is for reading the preserved archive and reconsidering the reasoning behind the decision. It offers no reopening, new forecast, new Journal, answer entry, scoring invitation, or deletion escape from meaningful history. Existing eligible metadata/text/Journal corrections remain available with their own safeguards. A reason correction appends history and changes the effective displayed text, not the terminal decision, original time, or scoring eligibility. Inspecting Question, criteria, or history creates no new fact. Search into superseded text must still reach the exact historical match.

```text
INVALID OVERVIEW — illustrative desktop arrangement
Question                                           Mode / type | Invalid
Not scored                         Marked Invalid: [recorded date/time]
Recorded reason: [user's effective text, prominently readable; or Not recorded]
+------------------------------------------+----------------------------+
| TIMELINE ~60%                            | ARCHIVAL CONTEXT ~40%      |
| Original forecast, rationale             | Resolution Criteria        |
| Revisions/Reviews where applicable       | Question / Definition      |
| Journals and preserved edit histories    | history (collapsed)        |
| Invalidation and reason corrections      | Background / forecast facts|
+------------------------------------------+----------------------------+
Secondary: existing eligible corrections; no generated advice or learning score
```

There is no Brier/WIS of zero, failed-forecast grade, or comparison against a hypothetical answer. The user can draw lessons from the original record; the application does not generate personalized diagnoses, recommendations, or advice. R-33/R-34 remain withdrawn, not deferred. Historical visualizations, if retained as supporting context, must not imply that Invalid is scored or still active; their exact prominence is open for validation.

**R-42 — Contextual nonmodal Mark Invalid preparation.** From an eligible nonterminal Adaptive or One-Shot Detail, open a labeled **Mark Invalid** form in the contextual pane. Keep approximately **60% Timeline / 40% editor** so reviewing the record remains primary while composing the optional free-text reason. This is a deliberate exception to the Adaptive revision/resolution/Postmortem 40/60 writing arrangement, not a reversal of R-25 or R-35. Keep Resolution Criteria available and readable without losing the reason draft or Timeline position; absent optional criteria stay visibly unset. For One-Shot, preserve any existing criteria and Background/checking method without adding a new mandatory criteria field.

Explain that Invalid preserves the entire record, excludes it from scores, and is terminal. Give the editor a clear Cancel path and **Continue to confirmation**. Preparation alone writes nothing and does not make the record Invalid. Do not require a reason category, automated question diagnosis, mandatory lesson, or newly required prose.

Proceeding opens a **separate explicit modal terminal confirmation** showing the full Question, proposed reason or explicit no-reason state, and the consequences: preserved history, not scored, and no reopening. Keep mode/type and current committed/effective forecast available as context. Use an explicit **Confirm Mark Invalid** action and a safe Back/Cancel route that returns to the populated editor. Recheck current eligibility and reviewed context through the existing atomic operation. If facts are stale, refresh and require renewed review rather than silently confirming different facts. Failure retains the reason with a persistent error and no partial history.

```text
MARK INVALID PREPARATION — nonmodal, preferred desktop arrangement
+------------------------------------------+----------------------------+
| TIMELINE ~60%                            | MARK INVALID ~40%          |
| Read full relevant forecasting history   | Resolution Criteria        |
| Consult Question and Definition history  | [Optional reason]          |
| Preserve useful reading position         | [Continue to confirmation] |
|                                          | [Cancel]                   |
+------------------------------------------+----------------------------+
                  -> Separate modal confirmation: Question + reason + consequences
                     [Confirm Mark Invalid] [Back]
                  -> Atomic save -> Invalid Overview (R-41)
                     Invalid + recorded reason + Not scored + preserved history
```

After success, close the editor/confirmation and automatically show the Invalid Overview with the saved reason, original decision time, explicit unscored status, and preserved history immediately inspectable. Do not leave an editable terminal draft or display an active-workflow success state. The final proportions and focus restoration remain subject to v0.4 accessibility and narrow-window validation.

## 6. Consolidated requirements register: R-01 through R-42

These are **working requirements and design directions**, not independently authorized implementation tickets. R-01–R-21 carry forward v0.1; R-22–R-35 retain v0.2; R-36–R-42 consolidate the One-Shot and Invalid exercises in v0.3. The Adaptive directions in Sections 3–5.6 remain intact; R-42 specifies its own preparation ratio. R-33 and R-34 are explicitly withdrawn and must not be treated as pending work. Where a row includes a proposed solution, retain the distinction between the underlying user need and the chosen presentation idea.

| ID | Requirement / working direction | Status |
| --- | --- | --- |
| **R-01** | Rapidly recover reasoning behind the current forecast. | Observed need |
| **R-02** | Consult judgment, history, Deadline, and criteria without long travel between distant sections. | Observed need |
| **R-03** | Allow deliberation before choosing Revise, Journal, or Review; no artificial stepper. | Observed need |
| **R-04** | Preserve convenient capture of evidence for later consideration through Journal. | Observed need |
| **R-05** | Support both quick recent-reasoning recovery and oldest-first complete history review. | Observed need |
| **R-06** | Clearly distinguish Revision, Journal, and Forecast Review in purpose and effect. | Observed need |
| **R-07** | The revision editor must support *forming* a judgment, not only entering one. | Observed need |
| **R-08** | Permit context consultation while drafting without modal restriction; prefer integrated nonmodal editor. | Need + preferred direction |
| **R-09** | Calm deliberation: no unnecessary alert sound, modal flash, or aggressive competing emphasis. | Observed need |
| **R-10** | Immediately show the new committed forecast after a successful revision. | Observed need |
| **R-11** | Make new committed rationale easy to inspect and verify. | Observed need |
| **R-12** | Keep a faithful, easily accessed Binary Probability History summary alongside written history; Numeric uses the current distribution under R-27. | Need + preferred direction |
| **R-13** | Make Question, committed forecast, Deadline, and Resolution Criteria accessible during reconsideration and draft. | Observed need |
| **R-14** | Distinguish Deadline from predicted event horizon and optional Expected Resolution; no implied automatic probability change. | Need / contract safeguard |
| **R-15** | Keep true chronology while marking and linking to the revision establishing the current forecast. | Preferred direction |
| **R-16** | Show full Revisions by default, expandable Journal previews, and readable Reviews. | Preferred direction |
| **R-17** | Keep a compact persistent forecast context header when reading deep history. | Preferred direction |
| **R-18** | Independently scroll Timeline and contextual workspace without resetting each other's position. | Preferred direction |
| **R-19** | Probability-first but fluid probability/rationale elicitation; preserve existing spin-box and presets. | Need + preferred direction |
| **R-20** | Accommodate multi-paragraph rationale writing comfortably, perhaps through controlled expansion. | Improvement opportunity |
| **R-21** | After success automatically return to Overview with updated header, Timeline, and graph; on failure retain draft. | Preferred direction |
| **R-22** | Guide Numeric entry through 90% interval, median, then 50% interval, while keeping all five fields freely editable in any order. | Preferred direction + contract safeguard |
| **R-23** | Show complete Current committed and Draft revision Numeric values side by side during editing, with clear labels and rationale space. | Preferred direction |
| **R-24** | Use approximately 60/40 Timeline/Context in desktop Overview. | Preferred direction; responsive validation open |
| **R-25** | Reverse to approximately 40/60 Timeline/editor during revision and contextual form entry. | Preferred direction; responsive validation open |
| **R-26** | Present Numeric Timeline forecasts through 90% interval, median, and 50% interval, preserving all values, rationale, anchors, and chronology. | Preferred direction |
| **R-27** | Visualize the current committed Numeric distribution without historical overlays; retain exact text and central-CDF limits. | Preferred direction + contract safeguard |
| **R-28** | Keep Locked Adaptive continuous with Open Detail while explaining that revisions and Reviews have ended; retain eligible Journal and terminal actions. | Preferred direction + contract safeguard |
| **R-29** | Keep Resolution Criteria readable in Locked Overview and resolution entry; unset criteria remain optional. | Preferred direction |
| **R-30** | Prepare Adaptive resolution in an inline nonmodal contextual form with Timeline and criteria available. | Preferred direction |
| **R-31** | Require a separate terminal confirmation explicitly showing outcome/actual value, effective time, and latest committed forecast without mislabeling scoring eligibility. | Preferred direction + contract safeguard |
| **R-32** | Lead Resolved Adaptive entry with outcome and existing results/scorecard or an explicit unscored explanation; preserve historical context. | Preferred direction |
| **R-33** | Individualized automated learning feedback is not pursued. Existing factual scores and self-authored reflection remain. | **Withdrawn — not deferred** |
| **R-34** | The related individualized automated learning-feedback direction is not pursued or carried forward as a recommendation feature. | **Withdrawn — not deferred** |
| **R-35** | Support later optional, open-ended Postmortem writing, commonly from Needs Postmortem, with approximately 40/60 Timeline/editor. | Observed need + preferred direction |
| **R-36** | Orient One-Shot Detail to a usually completed external exercise transcribed with its answer later, while preserving the later-answer path and all context/history. | Observed need + preferred direction |
| **R-37** | Make original estimate, answer, and ordinary Brier or exact five-quantile WIS immediately inspectable; distinguish originals from effective corrected facts used by the score. | Observed need + contract safeguard |
| **R-38** | Keep audited Correct transcription secondary but plainly discoverable, preserving originals, complete snapshots, and one scored observation. | Preferred direction + contract safeguard |
| **R-39** | Lead Waiting for Answer with Add Answer and the saved forecast; omit Adaptive Deadline, revisions, Reviews, staleness, and trajectory. | Preferred direction + contract safeguard |
| **R-40** | Use a compact conventional Add Answer dialog with one explicit terminal save, no redundant multi-step confirmation, and existing documentary time semantics. | Preferred direction; confirmation wording/contract validation open |
| **R-41** | Lead Invalid Detail with recorded reason and Not scored; preserve Question, criteria/Definition, and forecasting history for archival reading and self-directed reflection, without generated advice. | Observed need + preferred direction |
| **R-42** | Prepare Mark Invalid nonmodally at approximately 60/40 Timeline/editor with criteria available, then use separate explicit terminal confirmation and return to Invalid Overview after save. | Preferred direction + contract safeguard; responsive validation open |

## 7. Boundaries and invariants Codex must preserve

This exploration **does not authorize changes** to domain, analytics, scoring, history, admissibility, or data format. Specifically:

- Adaptive Deadline is an immutable exact instant; Open/Locked eligibility and the cutoff for scoring remain as specified.
- Effective resolution time, immutable recorded-at, and optional Expected Resolution are distinct. Numeric final-revision selection is strictly before `min(R, T)`; the latest committed forecast shown in confirmation may be ineligible. Binary retains its standing-duration and neutral-truncation rules; no Numeric trajectory or neutral score is added.
- Forecast Revision, Forecast Review, and Journal are distinct. Reviews do not create forecast revisions; Journals do not reset attention.
- Saved statements, revisions, Reviews, Journal originals and corrections, Definition snapshots, and terminal facts/corrections remain recoverable and historically honest.
- No intermediate editor draft is canonically recorded until the existing application operation successfully commits.
- Existing terminal decisions, corrections, deletion limits, and Postmortem/Skip behavior remain unchanged.
- Inline nonmodal Adaptive resolution and Mark Invalid preparation retain separate explicit modal terminal confirmation (R-31/R-42). R-40 proposes one deliberate modal Add Answer decision, with no redundant second confirmation; the specification's safeguard remains authoritative and must be reconciled before implementation. Postmortem may be deferred or supplied at Resolution; neither reflection, invalidation reason, nor criteria becomes mandatory.
- Binary and Numeric models retain their different forecasting representations and scoring contracts. Adaptive Numeric is exactly q05/q25/q50/q75/q95, with immutable unit/precision/constraint and whole-distribution revisions; no silent sorting or rounding.
- Adaptive Binary Trajectory Brier, Adaptive Numeric WIS, and One-Shot Brier/WIS remain separate, including eligibility and Analytics denominators. Numeric raw WIS is not a universal comparable skill metric.
- One-Shot has one original committed forecast, no ordinary revision/Review/Deadline, optional documentary reported times, and audited **Correct transcription** rather than Adaptive updating. Its score uses effective corrected facts while preserving originals; reported times never become eligibility cutoffs or score inputs, and later-answer replay remains intact.
- Invalid and unanswered records have no score. Invalidation preserves Question, criteria/Definition and complete history; correcting a reason never reopens the decision. Archival self-reflection introduces no generated advice or revival of R-33/R-34.
- Existing Search, Saved Views, back-navigation preservation, search-to-superseded-history, backup/export, local data ownership, and visual-system contracts remain authoritative.
- Retain native Qt/Windows behavior, system light/dark palettes, keyboard accessibility, safe focus, and chart text alternatives. Avoid new UI frameworks, themes, hosted dependencies, or canonical schema changes for presentational needs.

See [specification Sections 33–36](../../product-spec.md) for full authoritative details; the abbreviated boundaries above cannot override them. The withdrawal of R-33/R-34 concerns new automated interpretation, not removal of the specification's existing score and Analytics capabilities.

## 8. Remaining design exercises

Open Adaptive Binary, Adaptive Numeric, Locked Adaptive, Resolved Adaptive, later Postmortem writing, One-Shot, and Invalid have preferred design directions. Their design exercises are recorded; they have **not** passed prototype or usability validation. This section is the Detail chapter's local validation backlog. The [master roadmap](reckonsolve-experience-redesign.md#design-map-and-roadmap) owns priorities and shared dependencies. When this chapter is revisited for **v0.4**, work through the cases below using the [shared review conditions](../development.md#review-conditions-and-evidence), recording the actual artifact, evidence, and limits. Withdrawn feedback proposals remain outside the exercise.

| Exercise | Critical design question |
| --- | --- |
| One-Shot — validate R-36–R-40 | Can the user immediately inspect original/effective forecast, answer, and correct score, find transcription correction, and add an answer through one deliberate compact dialog without Adaptive machinery or false timestamp precision? |
| Invalid — validate R-41–R-42 | Is the recorded reason prominent and explicitly unscored, with Question/criteria/Definition/history easy to consult? Does 60/40 nonmodal preparation preserve context through separate confirmation and post-save Overview? |
| Adaptive Numeric — validate R-22–R-27 | Do unrestricted entry, all five values, side-by-side comparison, interval-oriented Timeline, and current-only CDF remain legible for ties, signed/exact values, and long units? |
| Locked Adaptive — validate R-28–R-31 | Does continuity make closed revision/Review eligibility clear? Can the user consult criteria while entering resolution and verify every terminal fact in the separate confirmation? |
| Resolved Adaptive / Postmortem — validate R-32 and R-35 | Are results first, scoring eligibility truthful, and deferred reflection easy to reach? Does the 40/60 editor support both rereading reasoning and writing freely while preserving optionality and audited history? |
| Long or sparse content | 30+ mixed events, multi-paragraph criteria/rationales, empty optional fields, long Questions, and entries corrected in history. |
| v0.4 responsiveness and accessibility | At least ~760 × 520 logical pixels, common desktop sizes, 100%/150%/200% scaling, both palettes, keyboard-only and pointer/trackpad use; determine minimum pane widths, stacking order, long-header behavior, and safe focus through layout transitions. |
| v0.4 draft safety and terminal review | Decide editor switching, Back/global navigation, Escape/window close, discard, stale-context refresh, and focus restoration without silent loss, accidental submit, partial writes, or a new persistent-draft data model. Validate the single Add Answer modal decision against separate Adaptive/Invalid confirmation. |

### Suggested prototype tasks

1. From Dashboard, locate an Open Adaptive Binary prediction and identify Question, current committed forecast, exact Deadline, and criteria.
2. Find the rationale for the current forecast below newer Journal entries without changing history order.
3. Read a recent Journal fully and then navigate oldest-to-newest for a comprehensive Review.
4. Start a revision, consult Timeline and criteria, adjust probability through existing controls, write several paragraphs, and switch panel context without losing the draft.
5. Commit and immediately verify current probability, recorded rationale, and updated Probability History.
6. Simulate validation/concurrency/Deadline rejection: draft preserved, explicit error, no phantom revision.
7. Repeat in Adaptive Numeric: enter values in different orders, compare all current/draft values, verify 60/40 to 40/60 transitions, ties and crossing validation, interval-oriented history, and a current-only CDF without invented tails.
8. Cross the exact Deadline with and without an open draft. Confirm Locked continuity, unavailable revisions/Reviews, and eligible Journals/terminal actions without an invented history event.
9. Prepare resolution while consulting criteria, then inspect the separate confirmation for outcome/actual, effective time/zone, and latest committed forecast. Exercise Cancel, stale context, early effective time excluding newer revisions, and the `R <= t0` unscored case.
10. Open Resolved Detail and verify results-first orientation, separate effective/recorded times, faithful historical access, and existing correction routes. Return later through Needs Postmortem, write freely in 40/60, and exercise Save, Cancel, failure, prior versions, and Skip without changing scores.
11. Transcribe a completed external One-Shot with its answer and go directly to answered Detail: identify original estimate, answer, and ordinary Brier or exact five-quantile WIS. Repeat Binary/Numeric, missing/approximate/equal-minute reported times, exact signed values, and ties; confirm no score preview before save, trajectory, cutoff, or new advice.
12. Open Waiting for Answer, find Add Answer, and complete its single modal decision. Exercise Cancel, invalid Numeric actual, keyboard submission, stale context, and lock failure; verify retained input, atomic save, and return to answered Overview with the correct score.
13. Find Correct transcription by mouse and keyboard, repair a copied forecast/answer/time, and inspect original/effective facts plus the full audit chain. Correct a forecast while waiting, then add an answer; verify that the answer remains visible and only one observation is scored.
14. Mark an eligible Adaptive or One-Shot Invalid in 60/40 while reading Timeline and criteria. Back out of the separate confirmation without losing the reason; simulate stale context/failure, then save and verify Invalid Overview, recorded reason, original time, Not scored, and complete history.
15. Revisit Invalid with a long or absent reason, prior reason/Definition/Journal corrections, and substantial forecast history. Inspect why the decision was made and reach historical search matches without reopening, scoring, or generated advice.
16. Check independent scrolling, accessible names, logical and visible focus, keyboard operation, chart text alternatives, long/sparse content, narrow-window stacking, 100%/150%/200% scaling, and both system palettes across every state. Exercise draft safety on editor/context switches, Back, global shortcuts, Escape, window close, confirmation cancellation, and refreshed stale facts.

**No prototype has passed these tasks yet.** These are candidate acceptance tests for future evaluation.

## 9. Preferred direction vs. unresolved decisions

**Preferred for further prototyping:** two-pane Split Workspace; C-like Timeline reading experience; compact persistent forecast context in Open/Locked; current revision jump; event-sensitive Timeline density; reverse chronological default with oldest-first option; independent scrolling; readable criteria; 60/40 Timeline/Context Overview and 40/60 Timeline/editor; nonmodal revision with automatic Overview return on success; existing Binary controls; unrestricted guided Numeric entry and current/draft comparison; interval-oriented Numeric Timeline and current-only distribution visualization; Locked continuity; nonmodal resolution entry followed by separate modal terminal confirmation; results-first Resolved landing; later open-ended Postmortem writing; completed-exercise-oriented One-Shot results with immediate original/effective forecast, answer, and Brier/WIS inspection; secondary discoverable transcription correction; prominent Add Answer while waiting and a compact single modal answer decision; archival-first Invalid with prominent recorded reason and Not scored; and 60/40 nonmodal Mark Invalid preparation followed by separate confirmation and Invalid Overview.

**Open:** minimum pane widths and resizability around the preferred ratios; narrow-window collapse/stacking and focus during ratio transitions; graph/Overview access without losing a draft; unsaved draft handling across navigation/close; readable long Questions/criteria and large histories; keyboard focus in nested scrolling; detailed Numeric comparison/preview geometry; expired/stale draft recovery and confirmation refresh; exact action hierarchy and placement of existing corrections, Skip, and optional resolution-time Postmortem; results/diagnostic disclosure; exact One-Shot original/effective/correction disclosure and compact-dialog geometry; Invalid reason/history prominence and criteria access while preparing invalidation; the single Add Answer decision's terminal wording and safe submission under the specification; and whether the header needs an expanded/collapsed transition. These are priorities for v0.4, especially responsive/accessibility and draft-safety validation, not a reopening of the settled mode/lifecycle directions. These interaction questions must not silently introduce draft persistence, change eligibility, or require new canonical facts.

**Withdrawn, not open:** R-33 and R-34, individualized automated learning feedback. There is no pending per-prediction diagnosis or recommendation exercise.

**Outside this chapter's decisions:** new 'unprocessed' Journal state, dedicated evidence queues, extra forecasting models, new score metrics, reminders/goals/gamification, or changes to history/persistence. The [master](reckonsolve-experience-redesign.md) owns the authorized global Journal/Performance/navigation design exploration and its J decisions; this chapter does not approve or block those proposals. No code implementation is authorized. Preserving existing scorecards and user-authored Postmortems does not revive the withdrawn feedback proposals.

## 10. Future Codex handoff procedure

Use the [shared completion gate and handoff](../development.md#completion-gate-and-handoff) and the master's [readiness review](reckonsolve-experience-redesign.md#readiness-for-a-future-handoff). This chapter supplies the Detail-specific criteria and evidence: applicable R IDs, mode/type/lifecycle cases, current/draft and original/effective distinctions, nonmodal preparation and deliberate terminal decisions, exact historical search destinations, responsive/focus/draft-safety cases, and unresolved wording or confirmation issues. R-33/R-34 are excluded as withdrawn.

Reconcile relevant contract differences in the governing specification before implementation. An explicitly authorized software slice should reference the approved Detail revision and applicable R IDs, reuse the existing visual system/application operations, and be verified with disposable data and human visual review. The master owns how that slice fits the overall redesign. Design acceptance, this backlog, and this document's presence do not authorize production changes.

## 11. Draft history

- **2026-10-24 — v0.1:** Captured the evidence-driven reconsideration journey, the R-01–R-21 register, preferred Split Workspace, journal-like Timeline, nonmodal revision and verification flow, preservation constraints, and forthcoming Adaptive Numeric/lifecycle validation. No runtime change or product-spec modification is implied.
- **2026-10-25 — v0.2:** Preserved and extended v0.1 with Adaptive Numeric R-22–R-27, Locked/resolution R-28–R-31, results-first Resolved R-32, and deferred open-ended Postmortem R-35. Explicitly withdrew R-33/R-34 following the decision against individualized automated learning feedback. Updated scope, desktop ratios and sketches, remaining questions, and validation tasks; corrected relative reference paths. Next exercise: One-Shot, then Invalid, then cross-cutting responsive/accessibility validation. This remains exploratory design only, with no implementation approval or change to the authoritative product specification.

- **2026-10-25 — v0.3:** Consolidated One-Shot R-36–R-40 and Invalid R-41–R-42: completed-exercise-first results and immediate estimate/answer/Brier or WIS inspection; secondary audited transcription correction; Waiting for Answer with prominent Add Answer and one compact modal decision retaining documentary time semantics; archival-first Invalid with recorded reason, preserved Question/criteria/Definition/history, and explicit unscored status; and 60/40 nonmodal Mark Invalid preparation with separate terminal confirmation and automatic Invalid Overview. Added rationale, illustrative layouts, contents, contract references, and prototype tasks; moved the next exercise to v0.4 responsive/accessibility, draft-safety, and confirmation validation. Preserved the v0.2 Adaptive design and withdrawal of R-33/R-34. Exploratory working draft only: not implementation authorization, not a product-spec amendment, and no change to application code, data contracts, or scoring.

- **2026-10-26 — Workflow alignment of v0.3:** Made Detail a linked chapter of the active redesign, delegated overall priorities/contract alignment to the master and review/maturity/handoff procedure to the development guide, and clarified global exploration versus local chapter scope. Preserved all R-01–R-42 register rows, design directions, withdrawn items, and validation tasks. This editorial update is not v0.4 validation, a new requirement, design approval, or implementation authorization.
