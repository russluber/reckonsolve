# Reckonsolve experience redesign

**Version:** 0.2 · **Date:** 2026-10-26

**Status:** Active master UX design; J-01–J-08 are Preferred. Further specification and validation are outstanding.

**Authorization:** Documentation only. No software implementation is authorized.

## Purpose and reading map

Reckonsolve should feel like a personal forecasting journal: a place to find a question, recover what you thought, record an honest change of mind, and return later to examine the outcome. The redesign replaces the feature-driven **Dashboard / Predictions / Analytics** arrangement with a **Journal-centered experience**, with focused workspaces for individual Predictions and rigorous performance analysis.

This is the single starting point for the active redesign: whole-experience direction, agreed preferred decisions **J-01–J-08**, progress, the overall roadmap, cross-cutting issues, and contract alignment. Detailed chapters own their local requirements and validation cases. Keep stable paths and IDs, and link between owners rather than copying registers. This is a working design hub, not a finished interaction specification or a queue of implementation tickets.

- Start with the [design charter](../../product-spec.md#active-ux-redesign-charter) and [shared UX design and review procedure](../development.md#ux-design-and-review) for scope, maturity/evidence, and authorization.
- For the preferred home and navigation, read [J-01–J-08](#preferred-decisions-j-01j-08).
- For what remains undecided, read [open design issues](#open-design-issues).
- For where the redesign stands, read [the roadmap](#design-map-and-roadmap).
- For individual Prediction work, use the existing [Prediction Detail v0.3 design](prediction-detail-redesign.md) and its [R-01–R-42 register](prediction-detail-redesign.md#6-consolidated-requirements-register-r-01-through-r-42). Those requirements are not duplicated here. **R-33 and R-34 remain withdrawn, not deferred.**

### Authority and status

The [product specification](../../product-spec.md) governs scope, terminology, history, lifecycle, scoring, retrieval, and safety. The [repository instructions](../../../AGENTS.md) govern this work; the [documentation index](../../README.md) identifies the owning references. The current baseline is **v0.8.0, schema 20, search projection 3, relational CSV format 5**.

J-01–J-08 are **agreed preferred design decisions** supplied for this exploration. That means the direction is selected for further specification; it does not mean the details are finalized, prototype-validated, implemented, manually accepted as software, or published. Open issues below must not be treated as implicit decisions. No item in this master draft is approved for implementation.

The [active design charter](../../product-spec.md#active-ux-redesign-charter) permits documenting alternatives to the current interface/workflow. The [contract-alignment section](#contract-alignment-before-implementation) owns those proposed differences; they must be resolved before implementation. The current product contract remains in force until explicitly amended at the appropriate stage. This document authorizes no app code, schema, stored-record, scoring, CLI, or runtime-data change, and no repair of the discrepancy below.

Use the [shared maturity labels](../development.md#design-maturity-and-authorization). J-01–J-08 remain **Preferred**; the Detail chapter records observed needs, preferred directions, and withdrawn items under its existing R IDs. Implementation authorization is **Not authorized**. This workflow update records no new prototype/runtime evidence or final design approval.

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

Resolved rows show both the forecast and the actual outcome/actual value. Which Adaptive forecast is summarized, and how an excluded latest revision or corrected One-Shot is labeled, still needs design work; a row must not imply that an ineligible or original value produced the displayed result. Search-match explanation is a separate open issue, not permission to drop the existing provenance contract.

### J-02 — Meaningful recent activity is the default browsing order

The preferred ordinary Journal order brings recently worked-on Predictions toward the top. **Merely viewing a Prediction does not count as activity.** Opening, searching, filtering, and changing sort remain read-only.

The exact qualifying events and ordering semantics are **unverified and open**. Creation, changed forecasts, deliberate Reviews, Journal writing/correction, metadata/Definition edits, answer entry, terminal corrections, and Postmortem/Skip actions must each be considered explicitly. Their inclusion is not settled by this list. Define event timestamps, ties, passive Deadline transitions, and behavior after saving before implementing the order.

Journal recency must remain distinct from **forecast last considered**, which uses an eligible Revision or Review. A Journal entry still does not refresh forecasting attention or change a score. Search relevance versus a user-selected activity sort also needs explicit treatment.

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

Put **search, advanced filters, and Saved Views under More filters**, including access to **Expected Resolution** and **age**. Preserve existing mode/type/status/tag/date/history and dynamic Saved View capabilities while exploring their arrangement. Age is a requested design topic; its reference event, units, boundaries, and Saved View treatment are not yet specified. One-Shot gains no invented Deadline or new Expected Resolution input.

The next exercise must resolve quick-view composition with advanced filters, active-filter visibility, reset behavior, search explanation, and Saved View application. Moving controls under a disclosure must not make the current query unknowable.

### J-05 — Rename Analytics to Performance

**Performance** is a separate, rigorous analytics workspace. Keep room for the full analytical work rather than squeezing it into Journal's home or replacing it with headline tiles.

The name changes the intended presentation, not the mathematics. Preserve Adaptive/One-Shot cohort separation, Binary/Numeric distinctions, exact-unit filtering, sample counts and uncertainty, chart/table alternatives, and the prohibition on pooled raw WIS or Delta WIS. Layout and disclosure still need an exercise grounded in the [existing analytics contracts](../../product-spec.md#364-individual-scores-and-separate-analytics). No automatic advice is introduced.

### J-06 — A compact top app bar

Use a compact top bar with **Journal as home**, a prominent **New** action, and an **always-visible, subtle chart icon in the upper-right opening Performance**. Keep **Settings secondary**. There is no persistent sidebar or row of peer destination tabs.

The chart control needs an accessible name such as Performance, a tooltip, keyboard access, and a visible focus state; subtle must still be discoverable. Its exact geometry, secondary Settings route, and behavior at narrow widths remain open. Native Windows title-bar behavior and the shared visual system remain foundations.

### J-07 — Prediction Detail is a full-workspace drill-down

Opening a Journal row replaces the main workspace with its type-appropriate Prediction Detail. Use the existing [Detail v0.3 preferred directions](prediction-detail-redesign.md), not a competing master-document redesign of its internals. Detail may retain its contextual panes; the app does not introduce multiple simultaneously open Detail tabs.

**Back restores Journal's browsing context:** search text and matching/history scope, filters, selected or modified Saved View, sort, and scroll position, with sensible focus restoration. A real saved change may alter query membership or order; preserving context must not freeze stale results or silently substitute another query.

Guard unsaved drafts when Back, New, Performance, Settings, shortcuts, or window close would leave the current task. The exact keep/discard/cancel interaction is open. This is not authorization for persistent drafts, a new visited-screen history, or restoring transient state across process restart.

### J-08 — Creation normally returns to Journal

After normal successful creation, return to Journal with a quiet, nonblocking confirmation and the prior browsing context preserved. Do not reset search, filters, sort, Saved View state, or scroll just to display the new Prediction. How to reveal a newly created item that falls outside the current query remains open.

**Exception: an answered One-Shot automatically opens its answered Detail so the forecast, answer, and score can be inspected.** This includes creation with an answer; later Add answer should likewise lead to the answered Detail result. The Journal return context remains available through Back. An unanswered One-Shot follows the normal proposed Journal return.

Confirmation follows successful atomic saving. Cancel, validation failure, lock contention, or stale context creates no partial Prediction or answer and must retain entered draft content appropriately. Existing One-Shot rules still prohibit score previews before Save.

## Design map and roadmap

The Prediction Detail exercises are **provisionally done at v0.3**: preferred directions are recorded across Adaptive Binary/Numeric, Locked, Resolved, later Postmortem writing, One-Shot, and Invalid. They have not passed prototype or usability validation. Their [remaining v0.4 work](prediction-detail-redesign.md#8-remaining-design-exercises) still covers responsiveness, accessibility, draft safety, content stress, and confirmation.

| Area | Current position | Owning reference |
| --- | --- | --- |
| Whole experience and navigation | J-01–J-08 recorded as preferred direction; details open | This master document |
| Prediction Detail | Provisionally complete design exercises at v0.3; validation outstanding | [Detail design and R-01–R-42](prediction-detail-redesign.md#6-consolidated-requirements-register-r-01-through-r-42) |
| Journal retrieval | Search, filters, Saved Views, rows, and recency need specification | This document, then the agreed detailed design |
| New Prediction | Composition and mode/type flows need exploration | Existing [creation contracts](../../product-spec.md#3510-creation-detail-lifecycle-and-correction-workflows) and [One-Shot contract](../../product-spec.md#363-creation-detail-and-lifecycle) constrain the exercise |
| Performance | Name and separate-workspace direction selected; organization open | Existing [analytics rules](../../product-spec.md#356-binary-diagnostics-scorecards-and-analytics) and [Numeric calibration](../../product-spec.md#359-numeric-calibration-and-implied-distribution-presentation) |
| Shared UI, Settings, integration, validation | Upcoming design work | [Desktop presentation contract](../../product-spec.md#34-desktop-presentation-contract) |

**Next exercise:** Journal search, filters, and Saved Views. The sequence below is the one overall design roadmap; chapter backlogs supply local questions and cases, not a competing schedule. Detail's prospective v0.4 is its next local design/validation revision when revisited, not a prerequisite to starting every other area. Apply cross-cutting review during each exercise and consolidate findings at step 6. This is not implementation authorization or a release schedule.

1. **Journal search, filters, and Saved Views.** Work through ordinary browsing, all three quick views, query composition, More filters, Expected Resolution, age, search-match provenance, recent-activity semantics, sorting, saved/modified views, reset, and empty/error states. Produce a coherent query and row design across modes/types/states.
2. **New Prediction composition.** Explore the writing experience for Adaptive and One-Shot, Binary and Numeric, required versus optional content, complete Numeric entry, mode/type draft retention, cancel/failure, and J-08's two landing paths. Preserve the current default Adaptive mode and the One-Shot visible supporting-field contract unless an explicit change is agreed.
3. **Performance.** Design the full analysis workspace: orientation, mode/type/tag/unit filters, scores and diagnostics, calibration and uncertainty, sparse/empty data, tables, and chart interpretation. Reuse existing mathematics; do not invent a universal skill score or advice engine.
4. **Shared UI and Settings.** Resolve the top bar, secondary utilities, action labels, typography/density, palettes, routine confirmations versus persistent errors, shortcuts, and Settings/recovery access. Preserve backup, export, search repair, tag maintenance, and stable/development identity boundaries.
5. **Integration journeys.** Walk Journal → Detail → Back, search → exact historical match → Back, New → Journal, and answered One-Shot → Detail → Journal. Include Performance/Settings detours, modified Saved Views, changed query membership, and navigation with an active draft.
6. **Cross-cutting validation.** Apply accessibility, focus, draft safety, responsiveness, long/sparse content, and error-state checks throughout the exercises, then review them together. Include Detail's outstanding v0.4 questions; do not call v0.3 validated merely because this roadmap exists.
7. **Final specification and handoff.** Resolve open decisions and governing-spec differences, assemble testable criteria and a coverage matrix, obtain design acceptance, and define small reviewable implementation slices. Only a subsequent explicit user instruction can authorize a software slice.

### Cross-cutting review conditions

Use the [shared review conditions and evidence procedure](../development.md#review-conditions-and-evidence) for the supported 760 × 520 logical-pixel window, Windows scaling, accessibility/focus, long/sparse content, navigation, and draft safety. The master owns dependencies across areas, including J-07's return context and J-08's creation/answered-One-Shot landing paths; detailed cases remain in their owning chapter.

No prototype or runtime validation of this redesign has been completed by this documentation pass. Record actual evidence and remaining limits after each future exercise; link Detail's local validation findings here when they affect the wider experience.

## Open design issues

These issues refine the preferred decisions; they do not reopen J-01–J-08 by default.

| Issue | What still needs an explicit answer |
| --- | --- |
| **O-01 — Activity** | Which committed events qualify, which timestamps are used, how ties/nulls/passive transitions work, and when rows reorder. Viewing is already excluded. |
| **O-02 — Retrieval composition** | How quick views combine with advanced filters and Saved Views; search relevance defaults; how active constraints remain legible when More filters is closed. |
| **O-03 — Age and dates** | Whether age means since creation or another named event; relative boundaries and dynamic Saved View behavior. Keep Expected Resolution date-only and distinct from Deadline. |
| **O-04 — Row truth and density** | Complete Numeric summaries; Adaptive latest versus scoring-eligible forecast; corrected One-Shot facts; factual dates/tags; search snippets and historical provenance without turning ordinary rows into rationale previews. |
| **O-05 — Navigation and drafts** | Safe exit choices, focus/scroll restoration after changed membership, minimum-width top bar, shortcut mapping, and Settings/Performance return behavior. |
| **O-06 — Creation feedback** | Quiet confirmation and access to a new item excluded by the current query; exact return context after the answered One-Shot exception. |
| **O-07 — Detail validation** | Carry forward the [existing v0.4 questions](prediction-detail-redesign.md#9-preferred-direction-vs-unresolved-decisions), including narrow panes, original/effective disclosures, and the single Add Answer dialog's terminal safeguard. |
| **O-08 — Contract and discrepancy review** | Resolve the presentation differences below before implementation. Separately verify the cleared-Postmortem discrepancy; this draft approves no fix. |

## Contract alignment before implementation

The product spec remains authoritative. Under its [design charter](../../product-spec.md#current-baseline-and-proposed-replacements), these are proposed differences to explore and resolve, not reasons to stop an authorized design exercise. This register owns cross-area alignment tasks; the specification will hold explicitly approved future requirements and authorized implementation criteria when ready. No target behavior is amended by the workflow update:

| Current governing contract | Preferred direction requiring reconciliation |
| --- | --- |
| [Section 34.3](../../product-spec.md#343-application-shell-and-navigation-contract) retains Dashboard, Predictions, Analytics, and a remembered sidebar; [34.9](../../product-spec.md#349-keyboard-and-accessibility-contract) maps shortcuts to them. | J-01/J-05/J-06 introduce Journal, Performance, and a top bar. Map every existing capability and affected shortcut. |
| [Attention and Dashboard](../../product-spec.md#attention-and-dashboard) and [34.6](../../product-spec.md#346-page-and-workflow-presentation) expose attention sections/labels. | J-03 removes persistent attention alerts/counters from the proposed experience. Decide retained on-demand retrieval without changing underlying classification rules. |
| [Section 33.5](../../product-spec.md#335-archive-filters-and-sorting) defaults ordinary browsing to Created newest and active search to Relevance. | J-02 proposes meaningful recent activity for ordinary browsing; qualifying events and search interaction remain open. Age is not an existing named filter contract. |
| [Sections 33.4–33.6](../../product-spec.md#334-ranking-grouping-and-result-explanation) require explained search results, snippets, contextual navigation, and dynamic Saved Views. | J-01/J-04 prefer factual rows without rationale previews and retrieval controls under More filters. Resolve search-specific explanation rather than dropping it silently; do not assume schema 20 can persist new query concepts. |
| [Section 36.3](../../product-spec.md#363-creation-detail-and-lifecycle) sends both answered and unanswered One-Shot creation to Detail; [34.3](../../product-spec.md#343-application-shell-and-navigation-contract) also describes creation opening Detail. | J-08 normally returns to Journal, retaining immediate Detail for answered One-Shot. The unanswered path is a deliberate proposed difference. |

None of these UX choices changes immutable forecast history, terminal finality, transaction-time checks, scoring cutoffs, model separation, documentary One-Shot times, or recovery formats. If a later design needs a true behavioral or persistence change, identify it explicitly and obtain the appropriate authorization before implementation.

## Known discrepancy: cleared Postmortem

**STATICALLY IDENTIFIED, UNVERIFIED AND UNFIXED.** This is an inspection finding, not a reproduced runtime bug or an approved repair.

The [governing reflection rule](../../product-spec.md#terminal-facts-corrections-and-reflection) defines Needs Postmortem as Resolved with blank effective reflection and no explicit Skip completion. An audited clear preserves prior text as history; an explicit Skip keeps a blank record outside the queue.

Static inspection found different Adaptive Binary query patterns:

- Dashboard's `list_needs_postmortem_predictions()` in [data/predictions.py](../../../src/reckonsolve/data/predictions.py) uses a correction-exists `CASE`, allowing the latest correction's `new_postmortem` to remain null after an intentional clear.
- The archive `needs_postmortem` calculation in that file, and the corresponding [search query](../../../src/reckonsolve/data/search.py), use `COALESCE(latest correction.new_postmortem, original resolution.postmortem)`. A cleared null may therefore fall back to the original nonblank text.

This suggests that a Resolved Adaptive Binary record with originally nonblank reflection, later cleared and not skipped, could appear in Dashboard's Needs Postmortem while archive/search classification excludes it. Runtime reproduction, scope across other modes/types, and regression coverage have **not** been verified here. No application or test code, query, schema, search index, or personal database has been changed, and no fix is authorized. Record a separate verification task if the user later authorizes that work; do not turn this discrepancy into intended filter semantics.

## Readiness for a future handoff

A sufficiently specified redesign needs agreed journeys and screen/state coverage across both modes and types, all lifecycle states, retrieval/history provenance, empty/failure states, and draft exits. It also needs resolved contract differences, readable prototypes at supported sizes/scales, keyboard/focus/accessibility review, and the user's acceptance of the resulting experience. The [Detail handoff procedure](prediction-detail-redesign.md#10-future-codex-handoff-procedure) remains the reference for that area.

Follow the [shared completion gate and handoff](../development.md#completion-gate-and-handoff). Record accepted target requirements and criteria in a clearly labeled future section of the governing specification, then identify the explicitly authorized software slice. **Design acceptance and a written handoff do not themselves authorize software implementation.** This documentation update establishes the workflow and ownership only; current product behavior, preferred decisions, and outstanding validation remain unchanged.

## Draft history

- **2026-10-26 — v0.1:** Established the whole-experience map; recorded preferred J-01–J-08; linked the existing Detail v0.3/R-01–R-42 design without duplicating it; separated open issues, contract-alignment tasks, and the unverified/unfixed cleared-Postmortem discrepancy. No implementation, runtime validation, or governing-spec amendment is implied.

- **2026-10-26 — v0.2:** Established this document as the single redesign hub and overall roadmap; linked the governing design charter and shared maturity/review/handoff procedure; clarified chapter ownership, next exercise, and contract-alignment handling. Preserved J-01–J-08, open issues, the Detail R register, and the unverified/unfixed discrepancy. No design was promoted to Validated or Approved design, and no implementation or executable prototype was authorized.
