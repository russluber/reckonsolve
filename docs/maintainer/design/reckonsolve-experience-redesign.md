# Reckonsolve experience redesign

**Version:** 0.3 · **Date:** 2026-10-28

**Status:** Active master UX design; J-01–J-31 are Preferred. Further specification, contract reconciliation, and validation are outstanding.

**Authorization:** Documentation only. No software implementation is authorized.

## Purpose and reading map

Reckonsolve should feel like a personal forecasting journal: a place to find a question, recover what you thought, record an honest change of mind, and return later to examine the outcome. The redesign replaces the feature-driven **Dashboard / Predictions / Analytics** arrangement with a **Journal-centered experience**, with focused workspaces for individual Predictions and rigorous performance analysis.

This is the single starting point for the active redesign: whole-experience direction, agreed preferred decisions **J-01–J-31**, progress, the overall roadmap, cross-cutting issues, and contract alignment. The master owns the J decisions, including Journal retrieval and rows; no separate Journal register is introduced. Detailed chapters own their local requirements and validation cases. Keep stable paths and IDs, and link between owners rather than copying registers. This is a working design hub, not a finished interaction specification or a queue of implementation tickets.

- Start with the [design charter](../../product-spec.md#active-ux-redesign-charter) and [shared UX design and review procedure](../development.md#ux-design-and-review) for scope, maturity/evidence, and authorization.
- For the preferred home and navigation, read [J-01–J-08](#preferred-decisions-j-01j-08).
- For the subsequent Journal decisions, read [J-09–J-31](#preferred-journal-decisions-j-09j-31). Later decisions explicitly refine or supersede the affected earlier wording.
- For what remains undecided, read [open design issues](#open-design-issues).
- For where the redesign stands, read [the roadmap](#design-map-and-roadmap).
- For individual Prediction work, use the existing [Prediction Detail v0.3 design](prediction-detail-redesign.md) and its [R-01–R-42 register](prediction-detail-redesign.md#6-consolidated-requirements-register-r-01-through-r-42). Those requirements are not duplicated here. **R-33 and R-34 remain withdrawn, not deferred.**

### Authority and status

The [product specification](../../product-spec.md) governs scope, terminology, history, lifecycle, scoring, retrieval, and safety. The [repository instructions](../../../AGENTS.md) govern this work; the [documentation index](../../README.md) identifies the owning references. The current baseline is **v0.8.0, schema 20, search projection 3, relational CSV format 5**.

J-01–J-31 are **agreed preferred design decisions** supplied for this exploration. That means the direction is selected for further specification; it does not mean the details are finalized, prototype-validated, implemented, manually accepted as software, or published. Open issues below must not be treated as implicit decisions. No item in this master draft is approved for implementation.

The [active design charter](../../product-spec.md#active-ux-redesign-charter) permits documenting alternatives to the current interface/workflow. The [contract-alignment section](#contract-alignment-before-implementation) owns those proposed differences; they must be resolved before implementation. The current product contract remains in force until explicitly amended at the appropriate stage. This document authorizes no app code, schema, stored-record, scoring, CLI, or runtime-data change, and no repair of the discrepancy below.

Use the [shared maturity labels](../development.md#design-maturity-and-authorization). Every J decision remains **Preferred**; the Detail chapter records observed needs, preferred directions, and withdrawn items under its existing R IDs. Implementation authorization is **Not authorized**. J-09–J-31 consolidate the user's selected directions from the Journal discussions, supplied in the 2026-10-28 documentation handoff. Those preferences are the evidence for selection, not evidence of usability or runtime validation. This pass records no new prototype/runtime evidence or final design approval.

## Principles for the experience

1. **A journal, without gamification.** No streaks, quotas, scores for participation, competitive rankings, or pressure to produce more Predictions. The user chooses when a question or reflection matters.
2. **Fidelity to the record.** Preserve the distinction between committed forecasts, drafts, Journal entries, Forecast Reviews, Definition changes, answers, and audited corrections. Let the user change their mind without rewriting what they used to think.
3. **No nudging or invented urgency.** No persistent attention alerts or counters, obligatory reflection, countdown pressure, or implied backlog debt. A Deadline closes Adaptive forecasting; it does not establish that the outcome is known.
4. **Facts and self-authored reflection.** Existing scorecards and calibration remain available with their limits. Do not generate personal diagnoses, lessons, recommendations, or automatic advice. The user interprets and reflects.
5. **Readable, factual presentation.** Let complete Questions and type-appropriate forecasts carry the hierarchy. Keep optional prose optional and preserve exact Numeric values, uncertainty, and original/effective distinctions.
6. **Comfortable movement and safe drafting.** Make returning to the same browsing context dependable. Keep errors visible and drafts recoverable through failed saves; avoid accidental submission or silent loss on navigation.
7. **Local, native, accessible.** Retain the offline Windows/PySide6 foundation, system palettes, keyboard access, visible focus, and text alternatives for charts. Presentation exploration introduces no new framework, service, or data contract.

Here, **Journal** names the proposed home for the entire Prediction collection. A **Journal entry** remains the existing reasoning/evidence event within one Prediction. Renaming the home does not change that event's meaning or freshness effects.

## Preferred decisions J-01–J-08

### J-01 — One Journal home for all Predictions

Journal unifies the everyday working set and the archive. Its default collection includes all supported Predictions across Adaptive/One-Shot, Binary/Numeric, and nonterminal/Resolved/Invalid states; a default view must not quietly omit older or completed records.

Use compact, factual rows with the **full Question wrapped naturally**. Row heights vary with content. Do not force a fixed-height card, ellipsis, or rationale snippet into ordinary browsing rows. Keep forecast type, mode, and lifecycle understandable without visual clutter. Numeric presentation must retain the complete five-quantile meaning rather than substitute a median alone.

Resolved rows show both the forecast and the actual outcome/actual value. [J-28](#j-28--resolved-rows-use-the-scoring-eligible-forecast) now owns forecast selection, and [J-29](#j-29--structured-exact-numeric-summaries) owns the complete Numeric summary. [J-11](#j-11--explain-non-question-search-matches-in-the-result) supplies search-specific explanation without adding rationale previews to ordinary rows.

### J-02 — Meaningful recent activity is the default browsing order

The preferred ordinary Journal order brings recently worked-on Predictions toward the top. **Merely viewing a Prediction does not count as activity.** Opening, searching, filtering, and changing sort remain read-only.

The initial event list was exploratory. [J-20–J-22](#j-20--recent-activity-means-substantive-new-work) now select the core inclusions and exclusions; timestamp provenance, remaining edge cases, ties, and behavior after saving remain open under O-01. This is still an unvalidated design, not an implemented ordering rule.

Journal recency must remain distinct from **forecast last considered**, which uses an eligible Revision or Review. A Journal entry still does not refresh forecasting attention or change a score. [J-19](#j-19--contextual-default-sorts-with-manual-override) owns search/browse sort defaults; [J-23–J-25](#j-23--name-the-three-time-concepts-separately) distinguish the time concepts and proposed factual filter.

### J-03 — No persistent attention alerts or counters

Do not carry Dashboard's attention machinery into the Journal as persistent banners, badges, numerical counters, or prompts to catch up. No always-present Needs Attention or Ready to Resolve queue is part of the preferred home.

Factual lifecycle labels, dates, user-requested filters, and the quiet Needs postmortem view can support retrieval without prescribing action. This decision concerns attention presentation; it does not silently delete canonical facts, remove existing filter semantics, or make errors disappear. Validation failures and other information the user must act on still need the spec's persistent feedback.

### J-04 — Three quiet, always-visible quick views

Keep **All / Unresolved / Needs postmortem** visible as quietly underlined text controls. **All is the default.** These are filters within Journal, not separate peer destinations or app tabs. Show no attention counters beside them.

| Quick view | Intended membership |
| --- | --- |
| **All** | All supported Predictions, including Resolved and Invalid. |
| **Unresolved** | Nonterminal Adaptive **Open and Locked**, plus One-Shot **Waiting for answer**. Locked says the revision window ended; it does not assert that the outcome is known. |
| **Needs postmortem** | Resolved Predictions with blank effective reflection and **no explicit Skip Postmortem completion**, under the governing reflection contract. |

Explicitly skipped Postmortems stay outside Needs postmortem even when their reflection is blank; their Predictions remain available in All, and later reflection remains possible. This is optional reflection, not an overdue obligation. The cleared-Postmortem implementation discrepancy is [recorded separately](#known-discrepancy-cleared-postmortem).

**Supersession:** v0.1/v0.2 placed search, advanced filters, and Saved Views under More filters and proposed preserving dynamic Saved Views. [J-09](#j-09--persistent-immediately-visible-search) supersedes the search placement; [J-13](#j-13--retire-saved-views-entirely-as-a-proposed-contract-change) supersedes Saved View retention. Those earlier directions are retained here as history, not parallel preferred alternatives. Advanced controls follow [J-12–J-18](#j-12--active-advanced-filter-chips-stay-visible), with date concepts clarified by J-23–J-27. One-Shot gains no invented Deadline or new Expected Resolution input.

Quick-view composition and visible active constraints now follow J-10/J-12/J-17/J-18. Remaining reset, sort-transition, and empty/error details are tracked under O-02; retiring Saved Views safely remains a contract-alignment task. Moving controls under a disclosure must not make the current query unknowable.

### J-05 — Rename Analytics to Performance

**Performance** is a separate, rigorous analytics workspace. Keep room for the full analytical work rather than squeezing it into Journal's home or replacing it with headline tiles.

The name changes the intended presentation, not the mathematics. Preserve Adaptive/One-Shot cohort separation, Binary/Numeric distinctions, exact-unit filtering, sample counts and uncertainty, chart/table alternatives, and the prohibition on pooled raw WIS or Delta WIS. Layout and disclosure still need an exercise grounded in the [existing analytics contracts](../../product-spec.md#364-individual-scores-and-separate-analytics). No automatic advice is introduced.

### J-06 — A compact top app bar

Use a compact top bar with **Journal as home**, a prominent **New** action, and an **always-visible, subtle chart icon in the upper-right opening Performance**. Keep **Settings secondary**. There is no persistent sidebar or row of peer destination tabs.

The chart control needs an accessible name such as Performance, a tooltip, keyboard access, and a visible focus state; subtle must still be discoverable. Its exact geometry, secondary Settings route, and behavior at narrow widths remain open. Native Windows title-bar behavior and the shared visual system remain foundations.

### J-07 — Prediction Detail is a full-workspace drill-down

Opening a Journal row replaces the main workspace with its type-appropriate Prediction Detail. Use the existing [Detail v0.3 preferred directions](prediction-detail-redesign.md), not a competing master-document redesign of its internals. Detail may retain its contextual panes; the app does not introduce multiple simultaneously open Detail tabs.

**Back restores Journal's browsing context:** selected quick view, search text and matching/history scope, advanced filters, sort, and scroll position, with sensible focus restoration. A real saved change may alter query membership or order; preserving context must not freeze stale results or silently substitute another query. **Supersession:** v0.1/v0.2 also named selected/modified Saved View restoration; J-13 removes that from the preferred target. The current specification's Saved View restoration contract remains in force pending reconciliation.

Guard unsaved drafts when Back, New, Performance, Settings, shortcuts, or window close would leave the current task. The exact keep/discard/cancel interaction is open. This is not authorization for persistent drafts, a new visited-screen history, or restoring transient state across process restart.

### J-08 — Creation normally returns to Journal

After normal successful creation, return to Journal with a quiet, nonblocking confirmation and the prior browsing context preserved. Do not reset the quick view, search, filters, sort, or scroll just to display the new Prediction. The earlier Saved View state reference follows J-13's proposed retirement, as in J-07. How to reveal a newly created item that falls outside the current query remains open.

**Exception: an answered One-Shot automatically opens its answered Detail so the forecast, answer, and score can be inspected.** This includes creation with an answer; later Add answer should likewise lead to the answered Detail result. The Journal return context remains available through Back. An unanswered One-Shot follows the normal proposed Journal return.

Confirmation follows successful atomic saving. Cancel, validation failure, lock contention, or stale context creates no partial Prediction or answer and must retain entered draft content appropriately. Existing One-Shot rules still prohibit score previews before Save.

## Preferred Journal decisions J-09–J-31

Every decision below has maturity **Preferred**, with implementation **Not authorized**. The motivations and alternatives explain the selected direction; remaining issues identify work still needed before validation and contract reconciliation. These decisions refine J-01–J-08 without changing the current product contract.

### J-09 — Persistent, immediately visible search

**Preferred:** Keep Journal search immediately visible without opening More filters. The user's usual retrieval cue is remembered **Question words**, so finding a known Prediction should start directly from the Journal home. A keyboard shortcut should reach the same field under the future shortcut mapping.

This supersedes J-04's earlier placement under More filters. It does not narrow search to Questions: preserve the broader current/effective text corpus, deliberate superseded-history option, safe matching modes, and ranking contract in [Sections 33.2–33.4](../../product-spec.md#332-searchable-corpus-and-historical-semantics). Exact placement and narrow-window geometry still need review.

### J-10 — Search within the selected quick view

**Preferred:** Search narrows **All**, **Unresolved**, or **Needs postmortem**, whichever is selected, together with the other active filters. Switching quick views retains the query. Do not silently search the entire collection when the selected scope has no matches.

A zero-result state can explicitly offer **Search All** to let the user widen the quick-view scope. This is distinct from the existing deliberate **Search for any word** fallback; neither action silently weakens other constraints. Status compatibility follows J-18. Global search regardless of the selected view was the alternative; scoped search keeps the visible view meaningful. Empty-state wording and reset interactions remain in O-02.

### J-11 — Explain non-Question search matches in the result

**Preferred:** During active text search, show visible, source-labeled matching excerpts for non-Question content, such as a forecast rationale, Review, Journal entry, Background, terminal reflection, or tag. A result must explain why it appeared even when the remembered words are absent from its current Question. For a current-Question match, avoid an unnecessary second copy of the Question as a snippet; keep its match legible in the full Question. Ordinary browsing rows have no rationale snippets.

Retain one grouped result per Prediction, safely emphasized plain text, additional-match information, and navigation to the actual matched context. Superseded-only matches require deliberate history inclusion, an explicit superseded source label, and expansion/navigation to the matching historical version. Earlier revision rationales remain genuine history in normal search under the existing corpus contract. Omitting explanations would make broad search opaque; permanent prose previews would burden browsing. Reconcile the nonduplicate Question treatment with [33.4's per-result snippet requirement](../../product-spec.md#334-ranking-grouping-and-result-explanation); excerpt length and multiple-source presentation remain open.

### J-12 — Active advanced-filter chips stay visible

**Preferred:** Active advanced constraints remain visible and individually removable even while More filters is closed. Inactive/default filters create no chips. A closed disclosure must not conceal the reason for a narrowed result set.

Label tag combinations explicitly as **All selected tags** or **Any selected tag**, distinct from All/Any **words** and the **All** quick view; a bare “All” or “Any” chip is ambiguous. This retains a calm default without hiding applied constraints. Chip grouping, long labels, exact reset scope, and how sort overrides are represented remain O-02 questions; the preferred visibility/removability itself is settled.

### J-13 — Retire Saved Views entirely as a proposed contract change

**Preferred:** The user chooses to retire **Saved Views entirely** from the future product: desktop UI, CLI listing/execution, tag-library dependencies, and eventually persistence. Hiding only the UI while retaining the feature elsewhere is not the preferred endpoint. The user prefers direct search, quick views, and advanced filters over maintaining named reusable query configurations and their extra controls.

This supersedes J-04's retention direction and J-07/J-08's Saved View context references; it does not withdraw advanced filters or tag management. It is an explicit **proposed behavior and compatibility change**, not approval to delete existing views, remove commands, alter the schema, rewrite migrations, or change backup contents. [Section 33.6](../../product-spec.md#336-saved-views), tag-library/CLI dependencies, and [schema-20 compatibility](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) remain governing requirements. The [contract-alignment register](#contract-alignment-before-implementation) owns reconciliation and safe persisted-state/backup migration planning. The transition policy for existing views and old supported backups remains open; no destructive cleanup is authorized.

### J-14 — Retain advanced filtering

**Preferred:** Keep advanced **tags, forecast type, mode, status, dates, and sort** controls. The user has rarely needed these so far but anticipates their value as the collection grows. Retiring them together with Saved Views would remove useful ways to inspect the record.

Preserve broader text/history controls and existing filter meanings unless an explicit proposed difference is recorded. Expected Resolution remains an available date meaning where applicable, independent of Forecast Deadline; One-Shot gains no new planning input. J-17/J-18 specialize status controls, and J-24 adds a proposed factual filter. Arrangement and reset details remain open, not the decision to keep these capabilities.

### J-15 — More filters expands inline

**Preferred:** More filters opens inline and pushes the full-width Journal list down. Closing it returns that space to the list while J-12 keeps active constraints visible. Do not introduce a filter sidebar or modal dialog.

The inline alternative keeps the collection's reading width and makes controls part of the current retrieval task. Wrapping, tab order, focus on collapse, and the amount of vertical space at the supported minimum size still need review; intentional disclosure expansion must be distinguished from unwanted control movement during refresh.

### J-16 — Filter changes apply immediately

**Preferred:** Selections take effect without an **Apply** step. Preserve focus and the values of other controls while results refresh, and keep empty/error states visible. Pending or failed refreshes must not present stale results as if they match the latest selections; retained results require the existing explicit warning.

An Apply button would add a second state for selected versus applied constraints. Immediate application keeps that relationship direct. Debouncing, partial date/number entry, keyboard interaction, and failed-refresh recovery remain design details; immediate application does not authorize silent query broadening or changes to canonical data.

### J-17 — Status refinements adapt to the quick view

**Preferred:** Offer status refinements that are meaningful inside the selected view:

| Quick view | Status refinement |
| --- | --- |
| **All** | The lifecycle choices, with mode-aware labels including One-Shot Waiting for Answer where applicable. |
| **Unresolved** | Adaptive Open, Adaptive Locked, and One-Shot Waiting for Answer. |
| **Needs postmortem** | No redundant status filter; membership is already Resolved under J-04. |

**Waiting for Answer is a UI label, not a stored status.** This avoids meaningless terminal choices inside Unresolved and a redundant control in Needs postmortem. Refinements remain subject to other filters, including mode/type; exact disabled/empty combinations need review without inventing lifecycle states.

### J-18 — Clear incompatible status refinements on view changes

**Preferred:** Switching quick views automatically clears an incompatible status refinement while retaining compatible search and filters. Discreetly indicate the removed constraint so the user understands the new result set. Do not keep hidden per-view filter memories that restore earlier constraints on a later switch.

Preserving an incompatible status could make a view falsely appear empty; separate hidden memories would make its controls unpredictable. Specify the compatibility mapping and accessible indication in O-02, including the redundant status refinement when entering Needs postmortem. Other compatible constraints can legitimately yield zero results and must not be discarded to manufacture matches.

### J-19 — Contextual default sorts with manual override

**Preferred:** Default ordinary browsing with a blank search to **Recently active**; default active text search to **Relevance**. The user may deliberately select another supported sort without changing which Predictions match. Recently active helps resume substantive work, while Relevance helps recover remembered words.

Do not infer the unresolved transition policy: when text starts/clears, a view changes, Back restores context, or reset is used, whether an existing manual override remains active and when a contextual default resumes still need explicit decisions. J-02's browsing direction and [33.5's current Created newest/Relevance defaults](../../product-spec.md#335-archive-filters-and-sorting) require reconciliation before implementation.

### J-20 — Recent activity means substantive new work

**Preferred:** Meaningful recent activity includes initial creation, a complete changed Adaptive revision, deliberate Forecast Review, a **new Journal entry**, first outcome/resolution/answer entry, and a **new Postmortem/reflection**. These are occasions on which the user added substantive work to the record. New reflection can occur later even though it uses the existing audited terminal-text operation; distinguish its meaning from editing an existing reflection under J-21.

Exclude mere viewing, browsing/search/filter/sort actions, automatic Deadline transitions, and edits to tags, Background, or Expected Resolution. These should not promote a Prediction as though new forecasting or reflection occurred. Corrections and initial Mark Invalid have their own owners in J-21/J-22. This general activity concept is distinct from forecast-last-considered freshness and changes neither attention nor scores. Timestamp provenance, simultaneous events, ties, refresh/reordering, Skip, and any unclassified event remain O-01 questions rather than implicit inclusions.

### J-21 — Historical corrections generally do not advance recency

**Preferred:** Exclude correction of an existing Journal, Definition clarification/correction, outcome/actual/effective-resolution correction, and edits to an existing Postmortem from Recently active. Generally, repairing an old fact should not look like newly considering the forecast or writing a new reflection.

Corrections still change effective displayed facts and may legitimately change query membership or scoring eligibility under their existing contracts. Excluding their timestamp from general recency neither hides history nor freezes the row's contents. The alternative of treating every write as activity would conflate maintenance with new work. Clearing/re-adding reflection and One-Shot transcription or other correction edge cases need explicit classification under O-01 before implementation.

### J-22 — Initial Mark Invalid counts as activity

**Preferred:** A deliberate initial **Mark Invalid** counts as meaningful recent activity. It is a substantive one-way decision about the record, even though Invalid never scores.

This differs from repairing the reason on an existing Invalid record, which falls under the general correction principle in J-21. Excluding every Invalid-related action would hide the user's fresh decision. Use the actual committed decision, not a fabricated transition or a correction timestamp; exact derivation belongs to O-01.

### J-23 — Name the three time concepts separately

**Preferred:** Distinguish **since Creation**, **since last forecast considered**, and general **Recently active**. Do not label all three “Age.” Creation measures time in the collection; last considered measures eligible Adaptive reconsideration; recent activity also includes substantive work that changes neither forecast nor freshness.

One generic age control would conceal the reference event. Use explicit labels in filters, sorting, and dates; J-24/J-25 own the proposed last-considered filter and J-26/J-27 own row dates. Exact relative/calendar presentation and boundaries remain O-03 questions. No new reminder or universal age metric is implied.

### J-24 — Optional Last considered more than N days ago filter

**Preferred:** Offer an advanced, optional **Last considered more than N days ago** filter for Adaptive Predictions. Anchor it to the latest eligible revision or deliberate Review, including the initial revision when no later eligible event exists. A new Journal, metadata edit, or correction must not reset that reference.

This lets the user inspect factual reconsideration history on demand rather than receive reminders or an attention queue. It does not apply to One-Shot. Exact N bounds/presets, day boundaries, cutoff/eligibility details, and control wording remain open under O-03; do not silently copy the current staleness threshold as the new filter's full contract.

### J-25 — Last considered applies across Adaptive lifecycle states

**Preferred:** J-24 is a factual filter over **all Adaptive states, including Resolved and Invalid**, constrained by the selected quick view and other active filters. It does not automatically add an unresolved condition.

Restricting it to unresolved records would turn a factual question into an implicit action queue and conceal relevant history. Terminal records retain the last eligible revision/Review even though they cannot be reconsidered in the app. Define unsupported-mode and no-match presentation explicitly; One-Shot does not acquire a last-considered field or reminder behavior.

### J-26 — Two quiet, clearly labeled row dates

**Preferred:** Ordinary rows show the **last substantive activity date**, plus only **one appropriate additional date**, both visually secondary and clearly labeled. The primary reading order remains Question, forecast, and lifecycle.

Showing every possible timestamp would compete with the record's meaning; one ambiguous date would conceal what happened. The first date uses J-20–J-22 rather than an arbitrary last-write timestamp. J-27 selects the nonterminal Adaptive second date; terminal and One-Shot choices, repeated dates, relative wording, precision/access to exact times, and label provenance remain O-03/O-04 questions. Do not fill an extra slot with an invented timestamp.

### J-27 — Open and Locked Adaptive rows show Forecast Deadline

**Preferred:** For **Open/Locked Adaptive**, the additional date is the immutable **Forecast Deadline**, not optional Expected Resolution. It identifies the real end of forecasting even when planning metadata is blank or changes. Keep its exact-instant meaning distinct from date-only Expected Resolution.

One-Shot rows have no Deadline. Resolved/Invalid rows may instead use the terminal decision date, pending refinement; distinguish immutable recorded decision time from effective resolution and corrections. This does not remove Expected Resolution filtering or Detail context. Final labels and date/time presentation must be checked against the current [35.11 display contract](../../product-spec.md#3511-archive-search-saved-views-dashboard-and-cli).

### J-28 — Resolved rows use the scoring-eligible forecast

**Preferred:** A Resolved Adaptive row summarizes the **scoring-eligible forecast**, rather than automatically showing the latest committed revision when a later revision is ineligible. Use immutable revision times, Deadline, and latest effective resolution facts under the existing [cutoff contract](../../product-spec.md#354-shared-exact-forecasting-window-and-resolution-time-contract).

- **Adaptive Binary:** Show the last eligible standing probability strictly before the cutoff as a forecast summary. It is not the full duration-weighted Trajectory Brier path or a substitute score.
- **Adaptive Numeric:** Show all five quantiles of the complete revision selected strictly before the cutoff, as presented under J-29.
- **Unscored Adaptive:** Explicitly identify the unscored case, including effective resolution at/before the initial forecast; do not invent a scoring forecast or use an ineligible latest revision as one.
- **One-Shot:** Use effective corrected forecast and answer facts, preserving access to originals and correction history; there is no Adaptive cutoff selection.

Show actual Yes/No outcome or exact Numeric actual separately. A summary that simply used the latest or original forecast could misrepresent the facts behind the result. Exact labels, excluded-latest disclosure, and unscored row geometry remain O-04; full history and score interpretation belong in Detail.

### J-29 — Structured, exact Numeric summaries

**Preferred:** Use three clearly labeled elements: **90% interval** (q05–q95), **Median** (q50), and **50% interval** (q25–q75). Preserve all five exact quantities, stored precision, and units; do not use compact rounding or abbreviate a value such as 12,345 to 12k. Open/Locked rows show the current committed distribution; Resolved selection follows J-28. Keep the resolved actual value separate.

The user selected this structured summary over a compressed single-line alternative because a Numeric forecast is a distribution, not just a median. Allow row heights to adapt and elements to stack at narrow widths. Long units, signed/large quantities, ties, and extreme exact precision need content-stress review; density cannot justify dropping values or silently changing them.

### J-30 — Omit tags from ordinary rows

**Preferred:** Reserve tags for advanced filtering and Prediction Detail rather than displaying routine tag badges in ordinary Journal rows. The user chose this over additional recognition cues in every row to keep the list focused on Question, forecast, lifecycle, and relevant dates.

When text search matches a tag, explain that source under J-11. This exception does not restore permanent tag clutter or remove tag associations/management. Hiding ordinary row tags is a proposed display difference from the current contract, recorded below; matched-tag wrapping and multiple matches remain part of row review.

### J-31 — One continuously sorted list

**Preferred:** Present the collection in a single continuous list, without lifecycle groupings. In **All**, Open, Locked, Resolved, Invalid, and unanswered One-Shot Predictions can appear together according to the selected sort. Narrower quick views filter that same list.

Lifecycle determines the facts and actions shown for a row, not a mandatory section in which it must sit. Grouping by lifecycle would reintroduce Dashboard-style divisions and weaken the collection-wide sort. Remaining row states and reordering/focus behavior need review, but lifecycle grouping is not an open alternative.

## Design map and roadmap

The Prediction Detail exercises are **provisionally done at v0.3**: preferred directions are recorded across Adaptive Binary/Numeric, Locked, Resolved, later Postmortem writing, One-Shot, and Invalid. They have not passed prototype or usability validation. Their [remaining v0.4 work](prediction-detail-redesign.md#8-remaining-design-exercises) still covers responsiveness, accessibility, draft safety, content stress, and confirmation.

| Area | Current position | Owning reference |
| --- | --- | --- |
| Whole experience and navigation | J-01–J-08 retained, with explicit later refinements/supersession; details open | This master document |
| Prediction Detail | Provisionally complete design exercises at v0.3; validation outstanding | [Detail design and R-01–R-42](prediction-detail-redesign.md#6-consolidated-requirements-register-r-01-through-r-42) |
| Journal retrieval and rows | J-09–J-31 consolidated as Preferred: search/filter interactions, proposed Saved View retirement, activity/dates, truthful row summaries, and continuous ordering; remaining interactions and validation open | [This master's Journal decisions](#preferred-journal-decisions-j-09j-31) and O-01–O-04/O-09 |
| New Prediction | Composition and mode/type flows need exploration | Existing [creation contracts](../../product-spec.md#3510-creation-detail-lifecycle-and-correction-workflows) and [One-Shot contract](../../product-spec.md#363-creation-detail-and-lifecycle) constrain the exercise |
| Performance | Name and separate-workspace direction selected; organization open | Existing [analytics rules](../../product-spec.md#356-binary-diagnostics-scorecards-and-analytics) and [Numeric calibration](../../product-spec.md#359-numeric-calibration-and-implied-distribution-presentation) |
| Shared UI, Settings, integration, validation | Upcoming design work | [Desktop presentation contract](../../product-spec.md#34-desktop-presentation-contract) |

**Next exercise:** Finish the remaining Journal interactions: manual sort/default transitions, chips/reset, long and special-state rows, and activity/date provenance. The main directions are now recorded; this is not a completed or validated Journal specification. Safe Saved View retirement remains an explicit future contract/compatibility task. The sequence below is the one overall design roadmap; chapter backlogs supply local questions and cases, not a competing schedule. Detail's prospective v0.4 is its next local design/validation revision when revisited, not a prerequisite to starting every other area. Apply cross-cutting review during each exercise and consolidate findings at step 6. This is not implementation authorization or a release schedule.

1. **Complete Journal retrieval and row specification.** Use J-09–J-31 as the preferred baseline. Resolve O-01–O-04: sort overrides, quick-view/status transitions, chips/reset, empty/error states, activity timestamp derivation, explicitly named date concepts and filter boundaries, and long/special-state row presentation. Keep J-13's safe retirement and contract reconciliation visible under O-09. Produce a coherent query and row design across modes/types/states before calling this area ready for validation.
2. **New Prediction composition.** Explore the writing experience for Adaptive and One-Shot, Binary and Numeric, required versus optional content, complete Numeric entry, mode/type draft retention, cancel/failure, and J-08's two landing paths. Preserve the current default Adaptive mode and the One-Shot visible supporting-field contract unless an explicit change is agreed.
3. **Performance.** Design the full analysis workspace: orientation, mode/type/tag/unit filters, scores and diagnostics, calibration and uncertainty, sparse/empty data, tables, and chart interpretation. Reuse existing mathematics; do not invent a universal skill score or advice engine.
4. **Shared UI and Settings.** Resolve the top bar, secondary utilities, action labels, typography/density, palettes, routine confirmations versus persistent errors, shortcuts, and Settings/recovery access. Preserve backup, export, search repair, tag maintenance, and stable/development identity boundaries.
5. **Integration journeys.** Walk Journal → Detail → Back, search → exact historical match → Back, New → Journal, and answered One-Shot → Detail → Journal. Include Performance/Settings detours, retained quick-view/search/filter/sort context, changed query membership, and navigation with an active draft. Review any approved Saved View retirement transition separately; do not retain a conflicting Saved View target journey by default.
6. **Cross-cutting validation.** Apply accessibility, focus, draft safety, responsiveness, long/sparse content, and error-state checks throughout the exercises, then review them together. Include Detail's outstanding v0.4 questions; do not call v0.3 validated merely because this roadmap exists.
7. **Final specification and handoff.** Resolve open decisions and governing-spec differences, assemble testable criteria and a coverage matrix, obtain design acceptance, and define small reviewable implementation slices. Only a subsequent explicit user instruction can authorize a software slice.

### Cross-cutting review conditions

Use the [shared review conditions and evidence procedure](../development.md#review-conditions-and-evidence) for the supported 760 × 520 logical-pixel window, Windows scaling, accessibility/focus, long/sparse content, navigation, and draft safety. The master owns dependencies across areas, including J-07's return context and J-08's creation/answered-One-Shot landing paths; detailed cases remain in their owning chapter.

No prototype or runtime validation of this redesign has been completed by this documentation pass. Record actual evidence and remaining limits after each future exercise; link Detail's local validation findings here when they affect the wider experience.

### Journal review cases still to evaluate

These are future review cases for the preferred design, not tests run or evidence of validation:

- Recover a Prediction by remembered Question words; repeat with a rationale, corrected Journal, superseded-only version, and tag match. Confirm visible source explanation and exact matched navigation, with no ordinary browsing snippets/tags.
- Keep a query while switching all three quick views; exercise compatible and incompatible status refinements, explicit Search All and Any-word fallbacks, and legitimate zero results from other retained filters.
- Open/close More filters, remove chips, edit partial date/N inputs, and refresh through error/recovery using keyboard and pointer. Check focus, active-constraint visibility, full list width, and the remaining reset/sort policies once specified.
- Contrast new revision/Review/Journal/reflection/Invalid activity with viewing, automatic locking, metadata maintenance, and historical corrections. Verify proposed timestamp provenance and factual last-considered filtering across terminal Adaptive records without including One-Shot.
- Read long Questions, five exact Numeric quantities with long units, ties, corrected One-Shots, ineligible latest Adaptive revisions, unscored Resolved, Invalid, and unanswered rows. Review quiet date labels and narrow stacking without lifecycle grouping.
- Return from Detail or creation after a qualifying activity or query-membership change; check the continuous selected sort, focus/scroll, and the answered-One-Shot exception. Persisted Saved View retirement needs separate compatibility/migration evidence after an approved future contract exists.

## Open design issues

These issues refine the preferred decisions; they do not reopen J-01–J-31 by default. A selected direction does not resolve all of its interaction or data-derivation details.

| Issue | What still needs an explicit answer |
| --- | --- |
| **O-01 — Activity** | J-20–J-22 settle core inclusions/exclusions. Derive the timestamp from actual committed qualifying events: do not assume a generic last-write field. Resolve ties/nulls, simultaneous creation/answer/reflection, ordering after saves/Back, Skip, cleared/re-added reflection, One-Shot transcription corrections, and other unclassified edge cases. Do not backdate recency using documentary One-Shot times or effective resolution time without an explicit decision. |
| **O-02 — Retrieval composition** | J-09–J-19 settle visibility, scoping, inline instant filtering, status adaptation, and contextual defaults. Resolve manual sort-override transitions when search starts/clears, views change, Back restores context, or reset is used; exact reset scope and chip removal/grouping, including tags All/Any; compatibility mapping and discreet cleared-status notice; search/history/word-mode placement, pending/partial inputs, and empty/error/fallback presentation. No hidden per-view memory or silent broadening. |
| **O-03 — Named time filters and dates** | J-23–J-27 distinguish Creation, last considered, activity, and Deadline. Specify N bounds/presets and strict elapsed/calendar boundaries, time-zone view and exact eligibility derivation across terminal Adaptive states; mode-inapplicable presentation; relative versus absolute date labels and access to exact instants. Keep Expected Resolution optional/date-only and distinct from Deadline. |
| **O-04 — Row truth and density** | J-26–J-31 settle core contents and continuous ordering. Refine terminal second dates (recorded decision versus effective time), One-Shot additional date or its absence, duplicate-date treatment, excluded-latest/corrected-facts labels, explicit unscored and Invalid/waiting states, multiple search excerpts/history destinations, long Questions/units, all exact Numeric values, adaptive heights, and narrow stacking. Do not reopen ordinary-row tag/rationale omission or substitute lifecycle groups. |
| **O-05 — Navigation and drafts** | Safe exit choices, focus/scroll restoration after changed membership, minimum-width top bar, shortcut mapping, and Settings/Performance return behavior. |
| **O-06 — Creation feedback** | Quiet confirmation and access to a new item excluded by the current query; exact return context after the answered One-Shot exception. |
| **O-07 — Detail validation** | Carry forward the [existing v0.4 questions](prediction-detail-redesign.md#9-preferred-direction-vs-unresolved-decisions), including narrow panes, original/effective disclosures, and the single Add Answer dialog's terminal safeguard. |
| **O-08 — Contract and discrepancy review** | Resolve the presentation differences below before implementation. Separately verify the cleared-Postmortem discrepancy; this draft approves no fix. |
| **O-09 — Safe Saved View retirement** | J-13 selects complete retirement, but existing views and old supported backups remain protected by the current contract. Specify the transition, retention/disposition of persisted configurations, CLI compatibility, tag-reference removal, versioned/atomic migration and rollback, schema-20/earlier supported upgrade and recovery behavior, and user-facing compatibility guidance. Do not delete views or change schema under this design pass. |

## Contract alignment before implementation

The product spec remains authoritative. Under its [design charter](../../product-spec.md#current-baseline-and-proposed-replacements), these are proposed differences to explore and resolve, not reasons to stop an authorized design exercise. This register owns cross-area alignment tasks; the specification will hold explicitly approved future requirements and authorized implementation criteria when ready. J-13 explicitly proposes changing the protected Saved View behavior/compatibility contract; recording that preference is not its reconciliation or approval to remove anything. No current requirement is amended by this consolidation:

| Current governing contract | Preferred direction requiring reconciliation |
| --- | --- |
| [Section 34.3](../../product-spec.md#343-application-shell-and-navigation-contract) retains Dashboard, Predictions, Analytics, and a remembered sidebar; [34.9](../../product-spec.md#349-keyboard-and-accessibility-contract) maps shortcuts to them. | J-01/J-05/J-06 introduce Journal, Performance, and a top bar. Map every existing capability and affected shortcut. |
| [Attention and Dashboard](../../product-spec.md#attention-and-dashboard) and [34.6](../../product-spec.md#346-page-and-workflow-presentation) expose attention sections/labels. | J-03 removes persistent attention alerts/counters from the proposed experience. Decide retained on-demand retrieval without changing underlying classification rules. |
| [Section 33.5](../../product-spec.md#335-archive-filters-and-sorting) defaults ordinary browsing to Created newest and active search to Relevance, with deterministic sorts and explicit reset/failure states. | J-02/J-19–J-22 propose Recently active with substantive-event semantics. Resolve timestamp derivation, ties, manual-override transitions, reset, and retained-result warnings; do not reuse forecast freshness as general recency. |
| [Sections 33.2–33.4](../../product-spec.md#332-searchable-corpus-and-historical-semantics), [33.9](../../product-spec.md#339-desktop-and-cli-boundaries), and [34.6](../../product-spec.md#346-page-and-workflow-presentation) govern broad search, grouped/source-labeled snippets, contextual navigation, and control stability. | J-09–J-12/J-15/J-16 keep search visible, scope it to quick views, and reserve prose excerpts for active search. Preserve the full corpus, history opt-in, source labels, additional matches, and matched navigation. Reconcile avoiding duplicate current-Question snippets with 33.4's per-result snippet requirement. Inline disclosure intentionally moves the list; a result refresh must not move or erase the controls. |
| [Section 33.5](../../product-spec.md#335-archive-filters-and-sorting), [Attention and Dashboard](../../product-spec.md#attention-and-dashboard), and [36.5](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) govern filters, lifecycle/mode, and date/freshness meanings. | J-10/J-12/J-14/J-17/J-18 introduce quick-view composition, visible removable constraints, context-adapted status refinements, and automatic incompatible-status clearing. J-23–J-25 propose a distinct optional cross-lifecycle Adaptive Last considered filter. Specify its boundary/eligibility semantics without extending One-Shot or silently restricting to unresolved. Preserve existing date meanings and structured-filter AND semantics. |
| [Section 33.6](../../product-spec.md#336-saved-views) requires dynamic Saved Views; [33.7](../../product-spec.md#337-tag-library-management) counts/retargets/removes tag references; [33.9](../../product-spec.md#339-desktop-and-cli-boundaries) exposes CLI listing/execution; [34.3](../../product-spec.md#343-application-shell-and-navigation-contract) and [34.8](../../product-spec.md#348-responsiveness-and-presentation-preferences) preserve browsing/Saved View context and persisted query configurations. | J-13 prefers complete retirement across these surfaces/dependencies, superseding older master preservation wording. Reconcile current commands, tag-management counts/warnings/transactions, context restoration, and persisted-configuration guarantees explicitly. This is a product/compatibility change, not just control placement. |
| [Recovery rules](../../product-spec.md#recovery-settings-and-technical-boundaries), [33.8](../../product-spec.md#338-search-persistence-repair-and-portability), [35.3](../../product-spec.md#353-durable-model-and-cohort-identity), and [36.5](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) preserve supported history and Saved Views in upgrade/SQLite recovery. Schema 20 adds nullable mode persistence; existing views retain All modes. CSV format 5 excludes Saved Views and is not restorable. | J-13's eventual persistence retirement requires a separately approved safe transition for existing views, schema-20 and earlier supported upgrades/backups, migration/rollback, and complete recovery. Decide retained-state disposition and compatibility guidance before authorizing a versioned migration; never edit applied migrations or use CSV as a recovery substitute. No deletion, schema change, backup rewrite, or migration is authorized here. |
| [Sections 34.6](../../product-spec.md#346-page-and-workflow-presentation), [35.11](../../product-spec.md#3511-archive-search-saved-views-dashboard-and-cli), and [36.5](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) describe row tags/dates and current/effective forecasts or terminal summaries; [35.4–35.8](../../product-spec.md#354-shared-exact-forecasting-window-and-resolution-time-contract) and [36.4](../../product-spec.md#364-individual-scores-and-separate-analytics) govern scoring eligibility. | J-26–J-31 prefer two quiet labeled dates, scoring-eligible Resolved Adaptive summaries, exact structured Numeric values, tags only as search-match explanation, and one continuously sorted list. Reconcile row-tag omission and date density/precision explicitly; preserve Deadline exact-instant meaning, full history, corrected One-Shot facts, and explicit unscored cases. A final eligible Binary probability is only a summary of the scored path. |
| [Section 36.3](../../product-spec.md#363-creation-detail-and-lifecycle) sends both answered and unanswered One-Shot creation to Detail; [34.3](../../product-spec.md#343-application-shell-and-navigation-contract) also describes creation opening Detail. | J-08 normally returns to Journal, retaining immediate Detail for answered One-Shot. The unanswered path is a deliberate proposed difference. |

These preferences preserve immutable forecast history, terminal finality, transaction-time checks, scoring cutoffs, exact values, model separation, and documentary One-Shot times. J-13 explicitly proposes future behavior/persistence retirement; current schema 20, complete SQLite recovery, and analytical format-5 export remain unchanged. Reconcile every proposed contract difference and obtain separate implementation authorization before changing software, commands, persistence, or recovery behavior.

## Known discrepancy: cleared Postmortem

**STATICALLY IDENTIFIED, UNVERIFIED AND UNFIXED.** This is an inspection finding, not a reproduced runtime bug or an approved repair.

The [governing reflection rule](../../product-spec.md#terminal-facts-corrections-and-reflection) defines Needs Postmortem as Resolved with blank effective reflection and no explicit Skip completion. An audited clear preserves prior text as history; an explicit Skip keeps a blank record outside the queue.

Static inspection found different Adaptive Binary query patterns:

- Dashboard's `list_needs_postmortem_predictions()` in [data/predictions.py](../../../src/reckonsolve/data/predictions.py) uses a correction-exists `CASE`, allowing the latest correction's `new_postmortem` to remain null after an intentional clear.
- The archive `needs_postmortem` calculation in that file, and the corresponding [search query](../../../src/reckonsolve/data/search.py), use `COALESCE(latest correction.new_postmortem, original resolution.postmortem)`. A cleared null may therefore fall back to the original nonblank text.

This suggests that a Resolved Adaptive Binary record with originally nonblank reflection, later cleared and not skipped, could appear in Dashboard's Needs Postmortem while archive/search classification excludes it. Runtime reproduction, scope across other modes/types, and regression coverage have **not** been verified here. No application or test code, query, schema, search index, or personal database has been changed, and no fix is authorized. Record a separate verification task if the user later authorizes that work; do not turn this discrepancy into intended filter semantics.

## Readiness for a future handoff

A sufficiently specified redesign needs agreed journeys and screen/state coverage across both modes and types, all lifecycle states, retrieval/history provenance, empty/failure states, and draft exits. It also needs resolved contract differences, readable prototypes at supported sizes/scales, keyboard/focus/accessibility review, and the user's acceptance of the resulting experience. The [Detail handoff procedure](prediction-detail-redesign.md#10-future-codex-handoff-procedure) remains the reference for that area.

Follow the [shared completion gate and handoff](../development.md#completion-gate-and-handoff). Record accepted target requirements and criteria in a clearly labeled future section of the governing specification, then identify the explicitly authorized software slice. **Design acceptance and a written handoff do not themselves authorize software implementation.** This documentation update consolidates preferred decisions and their unresolved consequences; it leaves current product behavior and outstanding validation unchanged.

## Draft history

- **2026-10-26 — v0.1:** Established the whole-experience map; recorded preferred J-01–J-08; linked the existing Detail v0.3/R-01–R-42 design without duplicating it; separated open issues, contract-alignment tasks, and the unverified/unfixed cleared-Postmortem discrepancy. No implementation, runtime validation, or governing-spec amendment is implied.

- **2026-10-26 — v0.2:** Established this document as the single redesign hub and overall roadmap; linked the governing design charter and shared maturity/review/handoff procedure; clarified chapter ownership, next exercise, and contract-alignment handling. Preserved J-01–J-08, open issues, the Detail R register, and the unverified/unfixed discrepancy. No design was promoted to Validated or Approved design, and no implementation or executable prototype was authorized.

- **2026-10-28 — v0.3:** Consolidated the user's Journal decisions J-09–J-31 as Preferred, with motivations, alternatives, remaining issues, and future review cases. Retained J-01–J-08 and their IDs; explicitly superseded J-04's search-under-More-filters/Saved View retention and J-07/J-08's Saved View restoration references. Updated the one roadmap, Journal progress, and contract-alignment tasks, including complete Saved View retirement as a proposed behavior/compatibility/persistence change requiring safe schema-20/backup reconciliation. Detail remains v0.3 with R-01–R-42 intact and R-33/R-34 withdrawn. The cleared-Postmortem discrepancy remains separately identified, unverified, and unfixed. No governing behavior requirement, application/test code, schema, runtime data, or validation/implementation authorization changed.
