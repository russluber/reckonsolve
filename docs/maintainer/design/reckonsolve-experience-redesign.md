# Reckonsolve experience redesign

**Version:** 0.4 · **Date:** 2026-10-28

**Status:** Active master UX design; J-01–J-66 are Preferred. Further specification, contract reconciliation, and validation are outstanding.

**Authorization:** Documentation only. No software implementation is authorized.

## Purpose and reading map

Reckonsolve should feel like a personal forecasting journal: a place to find a question, recover what you thought, record an honest change of mind, and return later to examine the outcome. The redesign replaces the feature-driven **Dashboard / Predictions / Analytics** arrangement with a **Journal-centered experience**, with focused workspaces for individual Predictions and rigorous performance analysis.

This is the single starting point for the active redesign: whole-experience direction, agreed preferred decisions **J-01–J-66**, progress, the overall roadmap, cross-cutting issues, and contract alignment. The master owns the J decisions, including Journal retrieval and rows; no separate Journal register is introduced. Detailed chapters own their local requirements and validation cases. Keep stable paths and IDs, and link between owners rather than copying registers. This is a working design hub, not a finished interaction specification or a queue of implementation tickets.

- Start with the [design charter](../../product-spec.md#active-ux-redesign-charter) and [shared UX design and review procedure](../development.md#ux-design-and-review) for scope, maturity/evidence, and authorization.
- For the preferred home and navigation, read [J-01–J-08](#preferred-decisions-j-01j-08).
- For Journal retrieval and rows, read [J-09–J-31](#preferred-journal-decisions-j-09j-31) and the [J-32–J-66 checkpoint](#preferred-journal-decisions-j-32j-66). Later decisions explicitly refine or supersede affected earlier wording; the earlier IDs remain in place.
- For what remains undecided, read [open design issues](#open-design-issues).
- For where the redesign stands, read [the roadmap](#design-map-and-roadmap).
- For individual Prediction work, use the existing [Prediction Detail v0.3 design](prediction-detail-redesign.md) and its [R-01–R-42 register](prediction-detail-redesign.md#6-consolidated-requirements-register-r-01-through-r-42). Those requirements are not duplicated here. **R-33 and R-34 remain withdrawn, not deferred.**

### Authority and status

The [product specification](../../product-spec.md) governs scope, terminology, history, lifecycle, scoring, retrieval, and safety. The [repository instructions](../../../AGENTS.md) govern this work; the [documentation index](../../README.md) identifies the owning references. The current baseline is **v0.8.0, schema 20, search projection 3, relational CSV format 5**.

J-01–J-66 are **agreed preferred design decisions** supplied for this exploration. That means the direction is selected for further specification; it does not mean the details are finalized, prototype-validated, implemented, manually accepted as software, or published. Open issues below must not be treated as implicit decisions. No item in this master draft is approved for implementation.

The [active design charter](../../product-spec.md#active-ux-redesign-charter) permits documenting alternatives to the current interface/workflow. The [contract-alignment section](#contract-alignment-before-implementation) owns those proposed differences; they must be resolved before implementation. The current product contract remains in force until explicitly amended at the appropriate stage. This document authorizes no app code, schema, stored-record, scoring, CLI, or runtime-data change, and no repair of the discrepancy below.

Use the [shared maturity labels](../development.md#design-maturity-and-authorization). Every J decision remains **Preferred**; the Detail chapter records observed needs, preferred directions, and withdrawn items under its existing R IDs. Implementation authorization is **Not authorized**. J-09–J-31 retain the earlier Journal checkpoint; J-32–J-66 consolidate the user's subsequent selected directions, supplied in the 2026-10-28 documentation handoff from **UI UX redesign resources**. The selection/tradeoff evidence is that discussion and the explicit handoff, not measured usability, a prototype, or running software. This pass records no new prototype/runtime evidence or final design approval. The charter's J-01–J-31 pointer identifies the earlier checkpoint; this master now owns J-01–J-66. No governing-spec amendment is made here.

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

Resolved rows show forecast and actual outcome/actual value when an eligible forecast exists. [J-28](#j-28--resolved-rows-use-the-scoring-eligible-forecast) owns selection, [J-39](#j-39--resolved-without-an-eligible-forecast-is-explicitly-unscored) specifies the no-eligible-forecast exception, and [J-29](#j-29--structured-exact-numeric-summaries) owns the complete Numeric summary. [J-40](#j-40--invalid-rows-label-the-last-forecast-and-not-scored) separately specifies Invalid context. [J-11](#j-11--explain-non-question-search-matches-in-the-result) supplies search-specific explanation without adding rationale previews to ordinary rows.

### J-02 — Meaningful recent activity is the default browsing order

The preferred ordinary Journal order brings recently worked-on Predictions toward the top. **Merely viewing a Prediction does not count as activity.** Opening, searching, filtering, and changing sort remain read-only.

The initial event list was exploratory. [J-20–J-22](#j-20--recent-activity-means-substantive-new-work) now select the core inclusions and exclusions; J-42/J-46 settle Skip and documentary-time treatment, and J-43/J-44 settle the return direction after saves. Timestamp derivation, remaining edge cases, and ties remain open under O-01. This is still an unvalidated design, not an implemented ordering rule.

Journal recency must remain distinct from **forecast last considered**, which uses an eligible Revision or Review. A Journal entry still does not refresh forecasting attention or change a score. [J-19](#j-19--contextual-default-sorts-with-manual-override) owns search/browse sort defaults; [J-23–J-25](#j-23--name-the-three-time-concepts-separately) distinguish the time concepts and proposed factual filter.

### J-03 — No persistent attention alerts or counters

Do not carry Dashboard's attention machinery into the Journal as persistent banners, badges, numerical counters, or prompts to catch up. No always-present Needs Attention or Ready to Resolve queue is part of the preferred home.

Factual lifecycle labels, dates, user-requested filters, and the quiet Needs postmortem view can support retrieval without prescribing action. This decision concerns attention presentation; J-65/J-66 distinguish quiet search/advanced-filter result counts from attention counters. It does not silently delete canonical facts, remove existing filter semantics, or make errors disappear. Validation failures and other information the user must act on still need the spec's persistent feedback.

### J-04 — Three quiet, always-visible quick views

Keep **All / Unresolved / Needs postmortem** visible at the top as quietly underlined text controls; J-63 clarifies that these page controls scroll away. **All is the default.** These are filters within Journal, not separate peer destinations or app tabs. Show no attention counters beside them.

| Quick view | Intended membership |
| --- | --- |
| **All** | All supported Predictions, including Resolved and Invalid. |
| **Unresolved** | Nonterminal Adaptive **Open and Locked**, plus One-Shot **Waiting for answer**. Locked says the revision window ended; it does not assert that the outcome is known. |
| **Needs postmortem** | Resolved Predictions with blank effective reflection and **no explicit Skip Postmortem completion**, under the governing reflection contract. |

Explicitly skipped Postmortems stay outside Needs postmortem even when their reflection is blank; their Predictions remain available in All, and later reflection remains possible. This is optional reflection, not an overdue obligation. The cleared-Postmortem implementation discrepancy is [recorded separately](#known-discrepancy-cleared-postmortem).

**Supersession:** v0.1/v0.2 placed search, advanced filters, and Saved Views under More filters and proposed preserving dynamic Saved Views. [J-09](#j-09--persistent-immediately-visible-search) supersedes the search placement; [J-13](#j-13--retire-saved-views-entirely-as-a-proposed-contract-change) supersedes Saved View retention. Those earlier directions are retained here as history, not parallel preferred alternatives. Advanced controls follow [J-12–J-18](#j-12--active-advanced-filter-chips-stay-visible), with date concepts clarified by J-23–J-27. One-Shot gains no invented Deadline or new Expected Resolution input.

Quick-view composition and visible active constraints now follow J-10/J-12/J-17/J-18. J-32–J-35 and J-49–J-52 settle reset, sort-transition, and empty/pending/error directions, with remaining composition/recovery details under O-02; retiring Saved Views safely remains a contract-alignment task. Moving controls under a disclosure must not make the current query unknowable.

### J-05 — Rename Analytics to Performance

**Performance** is a separate, rigorous analytics workspace. Keep room for the full analytical work rather than squeezing it into Journal's home or replacing it with headline tiles.

The name changes the intended presentation, not the mathematics. Preserve Adaptive/One-Shot cohort separation, Binary/Numeric distinctions, exact-unit filtering, sample counts and uncertainty, chart/table alternatives, and the prohibition on pooled raw WIS or Delta WIS. Layout and disclosure still need an exercise grounded in the [existing analytics contracts](../../product-spec.md#364-individual-scores-and-separate-analytics). No automatic advice is introduced.

### J-06 — A compact top app bar

Use a compact top bar with **Journal as home**, a prominent **New** action, and an **always-visible, subtle chart icon in the upper-right opening Performance**. Keep **Settings secondary**. There is no persistent sidebar or row of peer destination tabs.

The chart control needs an accessible name such as Performance, a tooltip, keyboard access, and a visible focus state; subtle must still be discoverable. Its exact geometry, secondary Settings route, and behavior at narrow widths remain open. Native Windows title-bar behavior and the shared visual system remain foundations.

### J-07 — Prediction Detail is a full-workspace drill-down

Opening a Journal row replaces the main workspace with its type-appropriate Prediction Detail. Use the existing [Detail v0.3 preferred directions](prediction-detail-redesign.md), not a competing master-document redesign of its internals. Detail may retain its contextual panes; the app does not introduce multiple simultaneously open Detail tabs.

**Back restores Journal's browsing context:** selected quick view, search text and matching/history scope, advanced filters, sort, and browsing vicinity, with sensible focus restoration. J-43/J-44 refine the earlier scroll-position wording: apply real reordering or removal while restoring an anchor around the prior browsing area, rather than relying on a pixel offset or chasing the changed row. J-52 distinguishes return/background refresh from a deliberate retrieval change. A real saved change may alter query membership or order; preserving context must not freeze stale results or silently substitute another query. **Supersession:** v0.1/v0.2 also named selected/modified Saved View restoration; J-13 removes that from the preferred target. The current specification's Saved View restoration contract remains in force pending reconciliation.

Guard unsaved drafts when Back, New, Performance, Settings, shortcuts, or window close would leave the current task. The exact keep/discard/cancel interaction is open. This is not authorization for persistent drafts, a new visited-screen history, or restoring transient state across process restart.

### J-08 — Creation normally returns to Journal

After normal successful creation, return to Journal with a quiet, nonblocking confirmation and the prior browsing context preserved. Do not reset the quick view, search, filters, sort, or scroll just to display the new Prediction. The earlier Saved View state reference follows J-13's proposed retirement, as in J-07. J-45 resolves the formerly open out-of-query case: retain that Journal view with a quiet confirmation, without a View prediction link or a switch to All.

**Exception: an answered One-Shot automatically opens its answered Detail so the forecast, answer, and score can be inspected.** This includes creation with an answer; later Add answer should likewise lead to the answered Detail result. The Journal return context remains available through Back. An unanswered One-Shot follows the normal proposed Journal return.

Confirmation follows successful atomic saving. Cancel, validation failure, lock contention, or stale context creates no partial Prediction or answer and must retain entered draft content appropriately. Existing One-Shot rules still prohibit score previews before Save.

## Preferred Journal decisions J-09–J-31

Every decision below has maturity **Preferred**, with implementation **Not authorized**. The motivations and alternatives explain the selected direction; remaining issues identify work still needed before validation and contract reconciliation. These decisions refine J-01–J-08 without changing the current product contract.

### J-09 — Persistent, immediately visible search

**Preferred:** Keep Journal search immediately visible without opening More filters. The user's usual retrieval cue is remembered **Question words**, so finding a known Prediction should start directly from the Journal home. A keyboard shortcut should reach the same field under the future shortcut mapping. Persistent here means directly available at the page top, not sticky while scrolling; J-63 clarifies that distinction.

This supersedes J-04's earlier placement under More filters. It does not narrow search to Questions: preserve the broader current/effective text corpus, deliberate superseded-history option, safe matching modes, and ranking contract in [Sections 33.2–33.4](../../product-spec.md#332-searchable-corpus-and-historical-semantics). Exact placement and narrow-window geometry still need review.

### J-10 — Search within the selected quick view

**Preferred:** Search narrows **All**, **Unresolved**, or **Needs postmortem**, whichever is selected, together with the other active filters. Switching quick views retains the query. Do not silently search the entire collection when the selected scope has no matches.

**Refinement/history:** v0.3 optionally suggested an extra **Search All** empty-state button. J-34 supersedes that suggestion: use the ordinary **All** quick-view control to widen scope deliberately, with no redundant recovery button. The ability to select All remains. The current specification's deliberate **Search for any word** fallback is a separate capability whose placement still needs reconciliation; no direction permits silent broadening. Status compatibility follows J-18. Global search regardless of the selected view was the alternative; scoped search keeps the visible view meaningful. J-33/J-34 now own reset scope and the minimal zero-result direction.

### J-11 — Explain non-Question search matches in the result

**Preferred:** During active text search, show visible, source-labeled matching excerpts for non-Question content, such as a forecast rationale, Review, Journal entry, Background, terminal reflection, or tag. A result must explain why it appeared even when the remembered words are absent from its current Question. For a current-Question match, avoid an unnecessary second copy of the Question as a snippet; keep its match legible in the full Question. Ordinary browsing rows have no rationale snippets.

Retain one grouped result per Prediction, safely emphasized plain text, additional-match information, and navigation to the actual matched context. Superseded-only matches require deliberate history inclusion, an explicit superseded source label, and expansion/navigation to the matching historical version. Earlier revision rationales remain genuine history in normal search under the existing corpus contract. Omitting explanations would make broad search opaque; permanent prose previews would burden browsing. Reconcile the nonduplicate Question treatment with [33.4's per-result snippet requirement](../../product-spec.md#334-ranking-grouping-and-result-explanation); J-47 now selects the best-ranked explanation plus expandable additional matches, and J-48 places history inclusion under More filters. Excerpt length, accessible disclosure geometry, and exact destinations still need review.

### J-12 — Active advanced-filter chips stay visible

**Preferred:** Active advanced constraints remain visible and individually removable even while More filters is closed. Inactive/default filters create no chips. A closed disclosure must not conceal the reason for a narrowed result set.

Label tag combinations explicitly as **All selected tags** or **Any selected tag**, distinct from All/Any **words** and the **All** quick view; a bare “All” or “Any” chip is ambiguous. This retains a calm default without hiding applied constraints. J-33 settles chip/reset scope, J-48/J-53 keep history/Last considered chips visible, and J-62 shows sort state in its dropdown. Chip grouping, long labels, and accessible removal remain O-02 questions; the preferred visibility/removability itself is settled.

### J-13 — Retire Saved Views entirely as a proposed contract change

**Preferred:** The user chooses to retire **Saved Views entirely** from the future product: desktop UI, CLI listing/execution, tag-library dependencies, and eventually persistence. Hiding only the UI while retaining the feature elsewhere is not the preferred endpoint. The user prefers direct search, quick views, and advanced filters over maintaining named reusable query configurations and their extra controls.

This supersedes J-04's retention direction and J-07/J-08's Saved View context references; it does not withdraw advanced filters or tag management. It is an explicit **proposed behavior and compatibility change**, not approval to delete existing views, remove commands, alter the schema, rewrite migrations, or change backup contents. [Section 33.6](../../product-spec.md#336-saved-views), tag-library/CLI dependencies, and [schema-20 compatibility](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) remain governing requirements. The [contract-alignment register](#contract-alignment-before-implementation) owns reconciliation and safe persisted-state/backup migration planning. The transition policy for existing views and old supported backups remains open; no destructive cleanup is authorized.

### J-14 — Retain advanced filtering

**Preferred:** Retain **tags, forecast type, mode, status, dates, and sort** capabilities. J-62 refines placement: sort stays above the list beside More filters, rather than inside that disclosure. The user has rarely needed these so far but anticipates their value as the collection grows. Retiring them together with Saved Views would remove useful ways to inspect the record.

Preserve broader text/history controls and existing filter meanings unless an explicit proposed difference is recorded. Expected Resolution remains an available date meaning where applicable, independent of Forecast Deadline; One-Shot gains no new planning input. J-17/J-18 specialize status controls, and J-24 adds a proposed factual filter. J-33 resolves reset scope; remaining control geometry is open, not the decision to keep these capabilities.

### J-15 — More filters expands inline

**Preferred:** More filters opens inline and pushes the full-width Journal list down. Closing it returns that space to the list while J-12 keeps active constraints visible. Do not introduce a filter sidebar or modal dialog.

The inline alternative keeps the collection's reading width and makes controls part of the current retrieval task. Wrapping, tab order, focus on collapse, and the amount of vertical space at the supported minimum size still need review; intentional disclosure expansion must be distinguished from unwanted control movement during refresh.

### J-16 — Filter changes apply immediately

**Preferred:** Selections take effect without an **Apply** step. Preserve focus and the values of other controls while results refresh, and keep empty/error states visible. Pending or failed refreshes must not present stale results as if they match the latest selections. J-50 retains visibly outdated results only while pending; J-51 replaces them on a definitive error. This refines v0.3's general retained-results warning wording and proposes a departure from the current failure-retention contract.

An Apply button would add a second state for selected versus applied constraints. Immediate application keeps that relationship direct. J-49 conditions debounced live search on measured responsiveness, and J-57 distinguishes a numeric draft from the last applied valid filter. Partial date entry, keyboard interaction, and failed-refresh recovery still need detail; immediate application does not authorize silent query broadening or changes to canonical data.

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

J-32/J-33/J-35 resolve the transition policy left open in v0.3: an applicable deliberate sort persists through search/view changes; explicit Reset Journal returns to automatic browsing, and clearing text discards manual Relevance. There is no hidden per-view manual sort memory. J-62 owns visible automatic/manual sort state. J-02's browsing direction and [33.5's current Created newest/Relevance defaults](../../product-spec.md#335-archive-filters-and-sorting) require reconciliation before implementation.

### J-20 — Recent activity means substantive new work

**Preferred:** Meaningful recent activity includes initial creation, a complete changed Adaptive revision, deliberate Forecast Review, a **new Journal entry**, first outcome/resolution/answer entry, and a **new Postmortem/reflection**. These are occasions on which the user added substantive work to the record. New reflection can occur later even though it uses the existing audited terminal-text operation; distinguish its meaning from editing an existing reflection under J-21.

Exclude mere viewing, browsing/search/filter/sort actions, automatic Deadline transitions, and edits to tags, Background, or Expected Resolution. These should not promote a Prediction as though new forecasting or reflection occurred. Corrections and initial Mark Invalid have their own owners in J-21/J-22. This general activity concept is distinct from forecast-last-considered freshness and changes neither attention nor scores. J-42 excludes explicit Skip, J-46 anchors One-Shot creation to actual app entry, and J-43/J-44 govern return reordering/removal. Timestamp derivation, simultaneous events, ties, and unclassified edges remain O-01 questions rather than implicit inclusions.

### J-21 — Historical corrections generally do not advance recency

**Preferred:** Exclude correction of an existing Journal, Definition clarification/correction, outcome/actual/effective-resolution correction, and edits to an existing Postmortem from Recently active. Generally, repairing an old fact should not look like newly considering the forecast or writing a new reflection.

Corrections still change effective displayed facts and may legitimately change query membership or scoring eligibility under their existing contracts. Excluding their timestamp from general recency neither hides history nor freezes the row's contents. The alternative of treating every write as activity would conflate maintenance with new work. Clearing/re-adding reflection and One-Shot transcription or other correction edge cases need explicit classification under O-01 before implementation.

### J-22 — Initial Mark Invalid counts as activity

**Preferred:** A deliberate initial **Mark Invalid** counts as meaningful recent activity. It is a substantive one-way decision about the record, even though Invalid never scores.

This differs from repairing the reason on an existing Invalid record, which falls under the general correction principle in J-21. Excluding every Invalid-related action would hide the user's fresh decision. Use the actual committed decision, not a fabricated transition or a correction timestamp; exact derivation belongs to O-01.

### J-23 — Name the three time concepts separately

**Preferred:** Distinguish **since Creation**, **since last forecast considered**, and general **Recently active**. Do not label all three “Age.” Creation measures time in the collection; last considered measures eligible Adaptive reconsideration; recent activity also includes substantive work that changes neither forecast nor freshness.

One generic age control would conceal the reference event. Use explicit labels in filters, sorting, and dates; J-24/J-25 own the proposed last-considered filter and J-26/J-27 own row dates. J-54 settles strict elapsed-day filtering; J-58–J-61 settle routine local absolute dates, year inclusion, and Deadline clock-time precision. Remaining derivation and display details stay in O-03. No new reminder or universal age metric is implied.

### J-24 — Optional Last considered more than N days ago filter

**Preferred:** Offer an advanced, optional **Last considered more than N days ago** filter for Adaptive Predictions. Anchor it to the latest eligible revision or deliberate Review, including the initial revision when no later eligible event exists. A new Journal, metadata edit, or correction must not reset that reference.

This lets the user inspect factual reconsideration history on demand rather than receive reminders or an attention queue. It does not apply to One-Shot. J-53/J-54 select a custom positive integer N, no required presets, and a strict elapsed-time boundary; J-55–J-57 govern mode incompatibility and draft/application state. Bounds and exact eligible-event derivation remain open under O-03; do not silently copy the current staleness threshold as the new filter's full contract.

### J-25 — Last considered applies across Adaptive lifecycle states

**Preferred:** J-24 is a factual filter over **all Adaptive states, including Resolved and Invalid**, constrained by the selected quick view and other active filters. It does not automatically add an unresolved condition.

Restricting it to unresolved records would turn a factual question into an implicit action queue and conceal relevant history. Terminal records retain the last eligible revision/Review even though they cannot be reconsidered in the app. J-55/J-56 specify explicit One-Shot clearing and disabled-input behavior, and J-34 specifies minimal no-match feedback; One-Shot does not acquire a last-considered field or reminder behavior.

### J-26 — Two quiet, clearly labeled row dates

**Preferred:** Ordinary rows show the **last substantive activity date**, plus at most **one appropriate additional date**, visually secondary and clearly labeled, subject to J-38's single-date One-Shot and J-41's duplicate-date suppression. This refines v0.3's two-date framing. The primary reading order remains Question, forecast, and lifecycle.

Showing every possible timestamp would compete with the record's meaning; one ambiguous date would conceal what happened. The first date uses J-20–J-22/J-42/J-46 rather than an arbitrary last-write timestamp. J-36–J-38 resolve the terminal/One-Shot choices left open in v0.3; J-41 suppresses Last active when its local date repeats the contextual date, and One-Shot has only Last active. J-58–J-61 own absolute labels, local time, and precision. Thus two dates are a maximum when useful, not a requirement to fill two slots. Row geometry and provenance still need review.

### J-27 — Open and Locked Adaptive rows show Forecast Deadline

**Preferred:** For **Open/Locked Adaptive**, the additional date is the immutable **Forecast Deadline**, not optional Expected Resolution. It identifies the real end of forecasting even when planning metadata is blank or changes. Keep its exact-instant meaning distinct from date-only Expected Resolution.

One-Shot rows have no Deadline. The provisional v0.3 terminal-decision-date idea is refined by J-36 (effective Outcome known for Resolved) and J-37 (immutable original Invalidated date). J-58/J-59 require the actionable Open/Locked Deadline's local date and clock time without a persistent zone suffix. This does not remove Expected Resolution filtering or Detail context. Final labels and date/time presentation must be checked against the current [35.11 display contract](../../product-spec.md#3511-archive-search-saved-views-dashboard-and-cli).

### J-28 — Resolved rows use the scoring-eligible forecast

**Preferred:** A Resolved Adaptive row summarizes the **scoring-eligible forecast**, rather than automatically showing the latest committed revision when a later revision is ineligible. Use immutable revision times, Deadline, and latest effective resolution facts under the existing [cutoff contract](../../product-spec.md#354-shared-exact-forecasting-window-and-resolution-time-contract).

- **Adaptive Binary:** Show the last eligible standing probability strictly before the cutoff as a forecast summary. It is not the full duration-weighted Trajectory Brier path or a substitute score.
- **Adaptive Numeric:** Show all five quantiles of the complete revision selected strictly before the cutoff, as presented under J-29.
- **Unscored Adaptive:** Explicitly identify the unscored case, including effective resolution at/before the initial forecast; do not invent a scoring forecast or use an ineligible latest revision as one.
- **One-Shot:** Use effective corrected forecast and answer facts, preserving access to originals and correction history; there is no Adaptive cutoff selection.

Show actual Yes/No outcome or exact Numeric actual separately. A summary that simply used the latest or original forecast could misrepresent the facts behind the result. J-39 specifies actual outcome plus explicit Unscored / No eligible forecast when none qualifies; an ineligible forecast is retained in Detail, not shown as an ordinary scoring summary. Excluded-latest disclosure and precise unscored row geometry remain O-04; full history and score interpretation belong in Detail.

### J-29 — Structured, exact Numeric summaries

**Preferred:** Use three clearly labeled elements: **90% interval** (q05–q95), **Median** (q50), and **50% interval** (q25–q75). Preserve all five exact quantities, stored precision, and units; do not use compact rounding or abbreviate a value such as 12,345 to 12k. Open/Locked rows show the current committed distribution; Resolved selection follows J-28/J-39. Invalid uses the full distribution labeled Last forecast under J-40. Keep the resolved actual value separate.

The user selected this structured summary over a compressed single-line alternative because a Numeric forecast is a distribution, not just a median. Allow row heights to adapt and elements to stack at narrow widths. Long units, signed/large quantities, ties, and extreme exact precision need content-stress review; density cannot justify dropping values or silently changing them.

### J-30 — Omit tags from ordinary rows

**Preferred:** Reserve tags for advanced filtering and Prediction Detail rather than displaying routine tag badges in ordinary Journal rows. The user chose this over additional recognition cues in every row to keep the list focused on Question, forecast, lifecycle, and relevant dates.

When text search matches a tag, explain that source under J-11. This exception does not restore permanent tag clutter or remove tag associations/management. Hiding ordinary row tags is a proposed display difference from the current contract, recorded below; matched-tag wrapping and multiple matches remain part of row review.

### J-31 — One continuously sorted list

**Preferred:** Present the collection in a single continuous list, without lifecycle groupings. In **All**, Open, Locked, Resolved, Invalid, and unanswered One-Shot Predictions can appear together according to the selected sort. Narrower quick views filter that same list.

Lifecycle determines the facts and actions shown for a row, not a mandatory section in which it must sit. Grouping by lifecycle would reintroduce Dashboard-style divisions and weaken the collection-wide sort. J-43/J-44/J-52 now specify the return/retrieval direction, and J-64 conditionally prefers uninterrupted scrolling with a pragmatic Load more fallback. This decision establishes unified ordering, not an unconditional loading/virtualization architecture. Row/focus and technical validation remain; lifecycle grouping is not an open alternative.

## Preferred Journal decisions J-32–J-66

All decisions in this checkpoint are **Preferred**; implementation is **Not authorized**. They record the user's selected directions and tradeoffs, refining the v0.3 questions rather than claiming validation. Responsiveness, content stress, accessibility, and technical feasibility remain to be evaluated against a separately scoped artifact. The illustrative debounce interval is not a performance finding.

### J-32 — Applicable manual sort takes precedence

**Preferred:** Automatic defaults are **Recently active** with blank search and **Relevance** with active search. A deliberate applicable sort, such as Created oldest/newest, takes precedence through search entry, search clearing, and quick-view changes until changed or explicitly reset. Do not keep hidden per-view manual sort memories.

This preserves deliberate browsing intent instead of unexpectedly reordering whenever search context changes. J-35 supplies the specific inapplicable Relevance exception; J-33 supplies reset. Other optional-value sorts retain the existing null/tie rules pending menu reconciliation, not a new per-view sort policy.

### J-33 — Clear and reset controls have distinct scopes

**Preferred:** Use explicit actions with these scopes; avoid ambiguous **Clear all**:

| Action | Effect |
| --- | --- |
| **Clear filters** | Remove advanced constraints only; retain text query, quick view, and applicable manual sort. |
| Remove one active chip | Remove only its own constraint. |
| Clear search | Remove text only; J-35 handles Relevance becoming inapplicable. |
| **Reset Journal** | Restore All, empty search, no advanced constraints, and automatic Recently active. |

The user can make a local adjustment without losing the rest of the retrieval task. History inclusion is an advanced constraint under J-48. Exact treatment/placement of the existing All/Any words control and spelling guidance still needs O-02 reconciliation; it must not silently broaden the query.

### J-34 — Minimal and truthful zero-result feedback

**Preferred:** A successful search with no matches shows a minimal, accurate explanatory message. Add no redundant recovery buttons in the empty region: the visible search, ordinary quick views, chips, and explicit reset controls already permit adjustment. Never silently broaden query or constraints, and never describe a query/index failure as zero matches.

This **specifically supersedes J-10's optional extra Search All button**, not the ordinary ability to switch to All. It reduces duplicate controls without hiding the selected scope. The governing All/Any-word fallback and suggestion presentation still need explicit reconciliation under the contract register; their matching semantics are not silently retired. J-51 separately owns definitive errors.

### J-35 — Cleared search discards manual Relevance

**Preferred:** If the user manually selected Relevance, clearing the query makes that sort inapplicable. Discard its manual override and resume automatic Recently active. A subsequent search uses its automatic Relevance default; do not secretly restore the old manual override. Other applicable manual sorts persist under J-32.

Relevance has no meaning without text. A visible return to automatic ordering is more predictable than a dormant override that reappears later.

### J-36 — Resolved Adaptive shows effective Outcome known

**Preferred:** A Resolved Adaptive row's contextual second date is **Outcome known**, using latest effective resolution instant $R$, not the immutable time Resolution was recorded. Scoring cutoff remains based on $R$ under the existing $C = \min(R, T)$ contract. General Last active remains based on substantive app activity.

An audited effective-time correction can change the displayed outcome date and eligible forecast without advancing general recency. This keeps outcome chronology and entry chronology distinct; full effective/recorded instants remain inspectable in Detail. J-60 selects date-only row precision.

### J-37 — Invalid Adaptive shows its original Invalidated date

**Preferred:** An Invalid Adaptive row's contextual date is **Invalidated**, from the immutable original decision instant, rather than its obsolete Forecast Deadline. Correcting the reason never changes that date. Last active follows substantive activity, including initial Mark Invalid under J-22, not reason-maintenance timestamps.

The original decision explains the archived record's state; the Deadline no longer serves as its routine contextual date. This refines J-27's provisional terminal-date wording without changing history or lifecycle.

### J-38 — One-Shot rows have only Last active

**Preferred:** Both unanswered and answered One-Shot rows show only **Last active** in routine Journal browsing. Add no Created, answer-recorded, or Deadline second date. Documentary forecast/reveal times, app entry/answer timestamps, originals, and corrections stay available in Detail.

One-Shot has no ongoing forecasting window. A second routine timestamp adds density without helping the primary retrieval task; no slot needs filling merely for symmetry with Adaptive. This is a row-display choice, not removal of timestamp evidence.

### J-39 — Resolved without an eligible forecast is explicitly unscored

**Preferred:** If Resolved Adaptive has no eligible forecast, for example $R \le t_0$ (the initial forecast instant), emphasize the actual outcome/value and explicit **Unscored / No eligible forecast**. Do not show an ineligible forecast as an ordinary row scoring summary. Keep that immutable forecast and its chronology in Detail.

This makes the outcome readable without inventing eligibility or a zero score. **Unscored is a scoring condition, not a new lifecycle status**: the record remains Resolved. J-40's Invalid historical context is intentionally different.

### J-40 — Invalid rows label the Last forecast and Not scored

**Preferred:** Invalid rows retain the last committed forecast as archival context, clearly labeled **Last forecast**, together with **Not scored**. Numeric uses J-29's full exact 90% interval, Median, and 50% interval with all five quantities and units; no rounded or median-only substitute.

The label makes no scoring-eligibility claim. It helps recall what was invalidated, unlike J-39's Resolved no-eligible-forecast summary. Preserve One-Shot effective/original transcription distinctions under its existing contract; do not turn a correction into another committed forecast. Precise corrected-context labeling remains O-04.

### J-41 — Suppress duplicate local row dates

**Preferred:** If Last active and the contextual date fall on the same **local calendar date**, omit Last active from the routine row and show the contextual labeled date only. For Adaptive, that label is **Deadline** in Open/Locked, **Outcome known** in Resolved, or **Invalidated** in Invalid. One-Shot always has its single Last active date under J-38.

Compare local dates, not identical UTC instants or equal displayed strings. Deadline still includes its local clock time under J-58. Full instants remain in Detail. This reduces repetitive metadata while preserving the more meaningful contextual label.

### J-42 — Skip Postmortem changes membership without activity

**Preferred:** Explicit **Skip Postmortem** is administrative and does **not** advance Recently active. It still changes Needs postmortem membership through the existing completion fact. Writing a new Postmortem counts as substantive activity; correcting an existing one does not. Initial Mark Invalid still counts under J-22.

This distinguishes optional completion bookkeeping from new reflection. Clearing and later re-adding reflection remains an O-01 edge case; this decision does not fabricate a general last-write rule or alter the governing Skip/history contract.

### J-43 — Return near the prior browsing area after reordering

**Preferred:** Detail → Back after substantive activity fully updates the selected sort while restoring the prior browsing vicinity, for example through neighboring-row anchors. Do not automatically scroll to the modified Prediction after it moves to the top.

The user should resume browsing without freezing a stale order. Variable-height Questions and Numeric rows make a pixel offset alone unreliable; anchor choice and fallback after missing neighbors need validation alongside J-64's loading approach.

### J-44 — Out-of-scope records disappear on Back

**Preferred:** If a saved change means a Prediction no longer matches the selected quick view, search, or advanced filters, preserve that retrieval state and browsing vicinity on Back, and remove the record strictly from the out-of-scope list. Do not add a temporary membership exception or switch queries to keep it visible. Use a quiet successful-save confirmation.

This preserves both query truth and the user's place. Saving a Postmortem or Skip can remove a record from Needs postmortem even when the event does not advance general activity. Exact anchor/focus fallbacks remain O-05.

### J-45 — Out-of-query creation returns with quiet confirmation

**Preferred:** Ordinary creation of a Prediction outside the current retrieval returns to the existing Journal view with a simple, quiet, nonblocking **Prediction created** confirmation. Preserve query, quick view, advanced filters, applicable sort, and browsing vicinity. Add no **View prediction** link and do not automatically switch to All.

The existing controls let the user retrieve the new record later without interrupting the current task. Preserve J-08's exception: creation of an already-answered One-Shot immediately opens answered Detail. This settles the formerly open reveal-link choice; notification accessibility and exception return details still need review.

### J-46 — Documentary One-Shot times never backdate recency

**Preferred:** One-Shot creation, including creation with an answer already known, counts at the app's actual entry instant. Later qualifying engagement uses its actual app timestamp. An old reported forecast/reveal time is documentary context and must not backdate Recently active.

This orders work actually entered or performed in Reckonsolve without claiming that the app recorded an external forecast earlier. Preserve reported dates and original app timestamps; neither is rewritten to implement recency. Other transcription-correction edge classifications remain O-01.

### J-47 — Group additional matches behind an inline disclosure

**Preferred:** Return one result per Prediction. Put the best-ranked, source-labeled matching explanation first, with an inline expandable **N more matches** disclosure for additional matching content. Allow navigation to each exact matching source/context, explicitly marking superseded versions. Preserve J-11's nonduplicate current-Question treatment and the existing ranking/corpus semantics.

This explains broad text matches without flooding the initial result list with prose. Ordinary browsing rows still have no previews. Disclosure focus, accurate fragment counts without duplicate unchanged snapshots, excerpt length, and historical destination geometry need review; no ranking change is implied.

### J-48 — History inclusion is an advanced visible constraint

**Preferred:** Put the **Include superseded history** switch under More filters. When active, show a visible removable chip even if the disclosure is closed. Inclusion broadens search provenance only; it never makes superseded text the effective record.

This keeps routine controls compact while explaining a historical match. Preserve the existing corpus: old revision rationales/Reviews remain genuine default history, while superseded audited text requires opt-in, labels, and exact version navigation. Fields without audited history gain none.

### J-49 — Debounced live search depends on measured responsiveness

**Preferred:** Search as the user types, without requiring Enter, **conditioned on measured responsiveness**. Approximately **200–300 ms** is only an illustrative starting point for testing, not a finalized delay or acceptance threshold.

Coalesce typing to avoid redundant keystroke-by-keystroke searching. Keep focus and controls responsive, avoid UI freezing, and prevent older responses from overwriting newer work. Evaluate realistic large collections, long histories, and Include superseded history before settling the approach. No prototype or performance proof exists for the proposed Journal; the current browser's debounce is not such proof.

### J-50 — Pending results remain visibly outdated

**Preferred:** While a query is pending, retain the previous results visibly identified as **previous/outdated**, with **Updating results** feedback. Current controls stay interactive. Only a completion for the latest current retrieval request may apply; ignore older completions even while that newest request is pending. Previous rows must never masquerade as matches for the current controls.

This avoids blanking the list during ordinary typing while telling the truth about its state. Match counts/explanations must share that provenance rather than imply current results. First-load pending presentation and stale-row navigation need O-02 detail. J-51 intentionally uses different behavior after a definitive error.

### J-51 — Definitive search error replaces the old listing

**Preferred:** On a definitive search error, replace the old listing with an explicit error state, clearly distinct from a successful zero-result query. Preserve entered search, quick view, filters, and sort; mutate no Prediction. A retry capability may be considered, but no redundant retry button is mandated.

Pending old results under J-50 are temporary context; after failure they should not resemble a valid current listing. This intentionally departs from the current archive contract that permits retaining old results with a warning. Exact recovery/repair routes and error wording remain O-02 and contract-alignment work.

### J-52 — Deliberate retrieval changes start at the top

**Preferred:** A deliberate query, filter, quick-view, or clear/reset change resets results scroll to the top **once the new results apply**, not during the still-pending typing interval. Preserve focused search input. Only the newest applied result set can trigger that reset.

Detail → Back and background refresh of the **same retrieval** instead restore the browsing area under J-43/J-44; they do not chase a reordered row or reset the list. The trigger distinction preserves orientation while starting an intentional new retrieval at its first result. Partial numeric drafts that retain the applied filter under J-57 are not yet a new applied retrieval.

### J-53 — Last considered uses a custom positive integer

**Preferred:** Under More filters, Last considered accepts a custom positive **integer number of days**. Blank means inactive; no preset durations are required. A successfully applied value has a visible chip when the disclosure is collapsed.

This lets the user ask their own factual question without a suggested review schedule. Bounds remain TBD; do not silently adopt an attention-setting threshold or invent a default. J-54 defines the threshold and J-57 separates numeric drafts from applied values.

### J-54 — Last considered means strict elapsed time

**Preferred:** **Last considered > N days** means elapsed time strictly greater than $N \times 24$ hours from the actual canonical instants/UTC. Equality is excluded. Local calendar boundaries and daylight-saving transitions do not change the duration.

Use the latest eligible Adaptive revision or deliberate Review, falling back to the initial revision. Apply across all Adaptive lifecycle states subject to quick-view and other constraints, as in J-24/J-25. A Journal or correction does not refresh this reference. Exact eligible-event derivation around Deadline, effective cutoff, and terminal history remains O-03 work; this preference does not silently redefine canonical eligibility or create One-Shot freshness.

### J-55 — Explicit One-Shot clears Last considered

**Preferred:** Choosing explicit **Mode: One-Shot** automatically clears an active Adaptive-only Last considered constraint, gives a discreet accessible explanation, and preserves compatible filters. Do not restore the cleared value secretly on a later mode switch.

This follows J-18's incompatible-status clearing principle: do not leave a contradiction hidden in the query or manufacture an inexplicable empty view. It does not authorize discarding other compatible constraints to force matches.

### J-56 — Show the unavailable Last considered input

**Preferred:** While Mode is explicitly One-Shot, keep the Last considered input visible within More filters but disabled, with **Available for Adaptive predictions only**. Attempting to use it must not silently change Mode. Switching back to Adaptive enables it without restoring the cleared value.

The explanation makes the mode distinction discoverable without a surprise query change. Accessible disabled-state explanation, draft handling through mode switches, and keyboard focus need review with J-55/J-57.

### J-57 — Numeric draft and applied filter stay distinct

**Preferred:** During a temporary invalid/incomplete **nonempty** numeric threshold draft, retain the last successfully applied valid filter and label the pending/validation error. A new valid numeric value applies automatically. A deliberate empty input clears the filter. Its chip always depicts the **actually applied value**, not an invalid draft.

This preserves immediate application without making ordinary editing silently remove or misrepresent a constraint. If no valid value has yet applied, there is no applied filter/chip to retain. Draft feedback, accessibility, and temporary versus definitive validation wording remain to be evaluated.

### J-58 — Actionable Deadline includes local clock time

**Preferred:** Open/Locked Adaptive Journal rows show **Deadline as date and local clock time**. The exact Deadline instant controls whether revisions/Reviews can commit; date alone would conceal a consequential boundary. Last active remains date only.

This preserves the governing exact-time meaning and refines row density rather than introducing a countdown or urgency cue. J-59 owns compact zone presentation, and exact instant/offset context stays accessible in Detail/on demand.

### J-59 — Compact local Deadline without a persistent zone suffix

**Preferred:** Use the Windows/system local zone by default for Journal dates/times, with no persistent timezone abbreviation or UTC-offset suffix on Deadline rows. Exact timezone/offset context remains available in Detail or on demand.

This keeps routine metadata compact while preserving unambiguous underlying instants. An app-specific zone option is **not decided** and is not a committed Settings feature. DST repeats, zone changes, and on-demand access still need display/accessibility review; this choice does not permit shifting or guessing stored times.

### J-60 — Outcome known is date only in the row

**Preferred:** Resolved Adaptive **Outcome known** shows only its local calendar date in Journal. Keep exact effective R time in Detail. Unlike an actionable Deadline, this routine historical label need not carry clock-time density.

J-36 still requires effective R rather than recorded-at; date-only rendering never changes scoring cutoff, precision of the stored instant, or correction history.

### J-61 — Routine dates are absolute and include the year

**Preferred:** Use absolute calendar dates including the year throughout routine Journal date labels, not relative wording such as **3 days ago**. Deadline uses local date plus clock time; Outcome known, Invalidated, and Last active use local date only.

Absolute dates stay stable and comparable across a long-lived collection. Exact format and local-time accessibility need review, but relative-day labels are not an unresolved alternative. J-41's duplicate-date suppression still applies.

### J-62 — Sort remains visible beside More filters

**Preferred:** Place a small, always-visible **Sort** dropdown directly above the list beside **More filters**, showing the current automatic or manual sort. Do not bury it in the disclosure. Search and quick views are likewise directly available at the top when the page is not scrolled.

This makes the active order inspectable without expanding advanced controls and refines J-14's earlier grouping of sort with advanced capabilities. Actual menu contents, automatic/manual wording, and narrow-window arrangement remain pending. Always-visible here means disclosure-independent; J-63 rules out sticky page controls.

### J-63 — Journal controls scroll away

**Preferred:** Search, quick views, More filters, and Sort scroll away with the Journal page; they are **not sticky**. The compact global app bar remains available. A keyboard shortcut should reach/focus search without manual scrolling; its specific binding is not finalized.

The user selected more reading space for rows, particularly at smaller windows, over persistent retrieval chrome. This clarifies J-04/J-09/J-62's visibility wording without hiding controls behind a disclosure. Minimum-window geometry, shortcut mapping, and focus restoration remain O-05 work.

### J-64 — Continuous scrolling is conditional on practicality

**Preferred:** Browse the unified Journal with continuous scrolling, **if pragmatic in the existing PySide6 architecture**. Use efficient batch/incremental fetching or virtualization as appropriate to keep interaction fluid and preserve reliable Detail → Back anchors; do not require every row to load/render simultaneously.

An explicit **Load more** control is an acceptable fallback if seamless scrolling adds substantial engineering complexity or performance cost. Advanced virtualization is not an unconditional requirement. No technical feasibility or performance validation has occurred; loading and variable-height anchor restoration must be assessed together before choosing the approach. J-31's one sorted list remains the intended collection model either way.

### J-65 — Quiet counts describe the full retrieval result

**Preferred:** Above the listing, show a quiet factual count when active text search or advanced constraints narrow the collection. Count all matching **Predictions**, not fragments or just rows loaded so far in continuous scrolling. Ensure that obtaining the accurate total remains performant.

Show no count for ordinary All with no search/advanced filters, and no numeric badges on quick-view labels. Counts help inspect retrieval, not assess performance or urge completion. Pending/error feedback must not present an old count as a successful current total; count-state details require review under O-02. J-66 resolves quick-view-only selection.

### J-66 — Quick views and manual sort alone do not trigger counts

**Preferred:** Selecting only **Unresolved** or **Needs postmortem** does not show a result count. A manual sort alone also does not. Active text search or advanced filtering does show the count, including when combined with a quick view.

This refines J-65's broad searching/filtering wording: retrieval feedback should not become a backlog or attention counter. Needs postmortem stays an optional reflection view. It preserves J-03/J-04's rejection of attention counters while permitting factual counts for a deliberate search/filter task.

## Design map and roadmap

The Prediction Detail exercises are **provisionally done at v0.3**: preferred directions are recorded across Adaptive Binary/Numeric, Locked, Resolved, later Postmortem writing, One-Shot, and Invalid. They have not passed prototype or usability validation. Their [remaining v0.4 work](prediction-detail-redesign.md#8-remaining-design-exercises) still covers responsiveness, accessibility, draft safety, content stress, and confirmation. Detail's version is independent of this master v0.4 checkpoint; R-01–R-42 remain intact, including withdrawn R-33/R-34.

| Area | Current position | Owning reference |
| --- | --- | --- |
| Whole experience and navigation | J-01–J-08 retained with later refinements; shared shell/draft details open | This master document |
| Prediction Detail | Provisionally complete design exercises at v0.3; validation outstanding | [Detail design and R-01–R-42](prediction-detail-redesign.md#6-consolidated-requirements-register-r-01-through-r-42) |
| Journal retrieval and rows | J-09–J-66 consolidated as Preferred; sort/reset, search states, lifecycle dates, activity/return directions, conditional scrolling, and count triggers selected. Residual specification and technical/usability validation remain | [J-09–J-31](#preferred-journal-decisions-j-09j-31), [J-32–J-66](#preferred-journal-decisions-j-32j-66), and O-01–O-06/O-09 |
| New Prediction | Composition and mode/type flows need exploration; J-08/J-45 settle the ordinary/answered-One-Shot landing directions | Existing [creation contracts](../../product-spec.md#3510-creation-detail-lifecycle-and-correction-workflows) and [One-Shot contract](../../product-spec.md#363-creation-detail-and-lifecycle) constrain the exercise |
| Performance | Name and separate-workspace direction selected; organization open | Existing [analytics rules](../../product-spec.md#356-binary-diagnostics-scorecards-and-analytics) and [Numeric calibration](../../product-spec.md#359-numeric-calibration-and-implied-distribution-presentation) |
| Shared UI, Settings, integration, validation | Upcoming design work, informed by J-43–J-46/J-52/J-59/J-63 | [Desktop presentation contract](../../product-spec.md#34-desktop-presentation-contract) |

**Next exercise:** Finish residual Journal specification and plan scoped validation: qualifying-event derivation/edge cases; exact sort menu, status/mode compatibility and word-mode/fallback placement; N bounds/eligibility; row and disclosure geometry; and variable-height return anchors. Assess live-search/count responsiveness and practical PySide6 continuous loading before choosing an implementation approach. Do not reopen the selected sort/reset/date/count directions as if still unanswered. Safe Saved View retirement remains an explicit future contract/compatibility task. This is not a completed or validated Journal specification.

The sequence below is the **one overall design roadmap**. Chapter backlogs supply local questions and cases, not a competing schedule. Detail's prospective v0.4 is its next local design/validation revision when revisited. Apply cross-cutting review during each exercise and consolidate findings at step 6. This is not implementation authorization, permission to build/run a prototype, or a release schedule.

1. **Complete Journal specification and establish validation scope.** Use J-09–J-66 as the preferred baseline. Resolve residual O-01–O-04 and return/feedback details in O-05/O-06; prepare the cases below across modes/types/states. Keep J-13's safe retirement and contract reconciliation visible under O-09. Obtain a separate stated scope for any executable prototype or performance experiment; record measured evidence for J-49/J-64/J-65 rather than assuming feasibility.
2. **New Prediction composition.** Explore writing for Adaptive/One-Shot and Binary/Numeric, required versus optional content, complete Numeric entry, mode/type draft retention, cancel/failure, and J-08/J-45's two landing paths. Preserve default Adaptive and the current One-Shot visible supporting-field contract unless a change is explicitly selected.
3. **Performance.** Design orientation, mode/type/tag/unit filters, scores/diagnostics, calibration/uncertainty, sparse/empty data, tables, and chart interpretation. Reuse existing mathematics; introduce no universal skill score or advice engine.
4. **Shared UI and Settings.** Resolve top-bar geometry, secondary utilities, typography/density, palettes, routine confirmations versus persistent errors, shortcuts, and Settings/recovery access. Preserve backup, export, search repair, tag maintenance, and identity boundaries. J-59 does not commit an app-specific time-zone setting.
5. **Integration journeys.** Walk Journal → Detail → Back, exact historical match → Back, New → Journal, and answered One-Shot → Detail → Journal. Distinguish deliberate retrieval changes from return/background refresh, applying real order/membership changes while preserving browsing vicinity. Include Performance/Settings detours and active drafts. Review a future approved Saved View transition separately, not as a retained target journey.
6. **Cross-cutting validation.** Apply accessibility, focus, draft safety, responsiveness, long/sparse content, and error checks throughout, then review them together. Include Detail's outstanding v0.4 questions and practical loading/anchor/count performance. Record evidence against the evaluated artifact; neither document version implies validation.
7. **Final specification and handoff.** Resolve remaining decisions and governing-spec differences, assemble criteria/coverage, obtain design acceptance, and define reviewable software slices. Only a subsequent explicit instruction authorizes a software slice.

### Cross-cutting review conditions

Use the [shared review conditions and evidence procedure](../development.md#review-conditions-and-evidence) for the supported 760 × 520 logical-pixel window, Windows scaling, accessibility/focus, long/sparse content, navigation, and draft safety. The master owns dependencies including Journal return/creation and search states; Detail-specific internals remain in that chapter.

No prototype, runtime, usability, or performance validation of this redesign has been completed by this documentation pass. Static inspection below only characterizes selected current code paths. Record actual evidence and limits after future scoped exercises; link local Detail findings when they affect the wider experience.

### Journal review cases still to evaluate

These are **future review cases**, not tests run or evidence of validation:

- Exercise automatic Recently active → search Relevance → clear Recently active; manually choose Created oldest/newest and retain it through search entry/clear and all quick views. Manually select Relevance, clear it, then search again without restoring a hidden override. Inspect visible automatic/manual state and applicable/null/tie behavior.
- Compare Clear filters, one-chip removal, clear search, and Reset Journal. Retain exactly the intended query/view/sort constraints, including history inclusion, and inspect no hidden per-view memories. Check compatible/incompatible status changes and accessible explanations without discarding legitimate constraints to manufacture results.
- Recover remembered Question, rationale, Background, tag, corrected Journal, and superseded-only matches. Confirm one Prediction result, best-ranked source first, N more matches expansion, each exact destination and superseded label, and no ordinary-row previews/tags. Include words distributed across sources and duplicate unchanged snapshots.
- Keep a query while switching all three quick views. Verify minimal accurate zero matches and the ordinary All control, no extra Search All recovery button, and no silent broadening. Review the existing All/Any words and spelling capabilities' future placement against the governing contract rather than treating them as removed.
- Type rapidly through pending queries, filter/view changes, history inclusion, and out-of-order completions. Keep prior results explicitly outdated with Updating results, controls interactive, focus stable, and only the newest result set applied. Cover first-load pending, old-row navigation, and count provenance. Debounce duration is to be measured, not assumed.
- Fail a definitive query/index operation after previously successful results: replace the listing with an error, preserve all retrieval controls, distinguish successful zero matches, and preserve canonical records. Review explicit recovery/repair without mandating a redundant retry button.
- Edit Last considered from a valid integer through an invalid/incomplete nonempty draft to another valid value, then deliberately blank it. Keep the prior applied value/chip during invalid input, show draft feedback, apply valid input automatically, and clear only on deliberate empty. Repeat with no previously applied filter and define bounds/accessibility.
- Check Last considered just below, exactly at, and just above N × 24 hours, including DST changes, initial fallback, Reviews, ineligible revisions, all Adaptive states, and every quick view. Choose explicit One-Shot: clear the filter with explanation, keep a disabled visible input, retain compatible filters, and re-enable without hidden value restoration.
- Contrast creation/revision/Review/new Journal/new reflection/initial Invalid activity with viewing, Skip, automatic locking, metadata and historical corrections. Include an old documentary One-Shot entered with an answer now, effective-R corrections, tied instants, cleared/re-added reflection, and unresolved correction classifications without inferring last-write recency.
- Read Open/Locked local date-and-time Deadline, Resolved date-only effective Outcome known, original Invalidated date, and the single Last active on answered/unanswered One-Shots. Include years, local-midnight/UTC date differences, duplicate local-date suppression, DST repeated times, changed system zone, and exact instant/offset access in Detail. Suppressing Last active must not suppress Deadline clock time.
- Stress long Questions, exact signed/large Numeric quantities, ties, long units, and narrow stacking. Verify all five quantiles for eligible Resolved and Last forecast / Not scored Invalid, actual value separate, no ineligible scoring summary for R <= t0, and honest corrected One-Shot context. No invented status, missing values, rounding, or lifecycle sections.
- Return from Detail after substantive activity moves a row, or a save/Skip removes it from the query. Apply the correct order and strict membership while restoring neighboring browsing anchors, including missing neighbors, variable heights, loaded/unloaded rows, and an empty resulting set. Do not jump to the changed record or preserve it as a temporary exception.
- Deliberately change query/filter/view/clear: reset results to the top once the new results apply, with focused search retained. Compare Detail return and background refresh of the same retrieval, which preserve the browsing area. Pending typing or an unapplied invalid numeric draft must not prematurely reset it.
- Create an out-of-query record and return to the existing Journal with quiet Prediction created, no View prediction link or All switch. Compare unanswered One-Shot ordinary return with answered One-Shot immediate Detail; inspect Back context and accessible confirmation without accidental draft loss.
- At realistic large collection/history sizes, assess live search, historical inclusion, accurate full matching-Prediction totals, and fluid incremental browsing/anchor restoration. Evaluate PySide6 complexity before preferring seamless loading over the acceptable Load more fallback; advanced virtualization is not a mandatory outcome.
- Show counts for active text/advanced filters, including with a quick view, counting the whole result set rather than loaded rows or fragments. Omit them for All/no constraints, quick-view-only Unresolved/Needs postmortem, and manual sort alone; no quick-view badges. Include zero/pending/error counts and responsive counting.
- At supported sizes/scales/palettes, let page retrieval controls scroll away while the global bar remains available; reach search by keyboard, open/collapse filters and match disclosures, and preserve sensible focus. Persisted Saved View retirement requires separately approved transition/recovery evidence, not this review's disposable retrieval cases.

## Open design issues

These issues refine **J-01–J-66**; they do not reopen selected directions by default. Preferred interaction rules still require complete specification, technical assessment, and validation.

| Issue | What still needs an explicit answer |
| --- | --- |
| **O-01 — Activity** | Core events, Skip exclusion, and actual-entry One-Shot recency are selected in J-20–J-22/J-42/J-46. Derive qualifying timestamps from committed facts without assuming a generic last-write field. Resolve ties/nulls, simultaneous creation/answer/reflection, cleared/re-added reflection, One-Shot transcription-correction subcases, and other unclassified edges. J-43/J-44 settle reordering/removal on Back; do not reopen documentary-time backdating or count Skip as activity. |
| **O-02 — Retrieval composition** | J-32–J-35/J-47–J-52/J-62/J-65/J-66 settle sort/reset, disclosure/history, pending/error, scroll triggers, and count direction. Specify the actual sort menu and applicability, visible automatic/manual wording, chip grouping/long labels, complete compatible-status mapping and accessible notices, All/Any-word placement/reset scope, fallback/suggestion placement, partial date input, first-load pending/stale-row navigation, definitive-error recovery/repair, and count feedback during pending/error. Measure responsive searching/counting; do not finalize debounce from the illustrative interval or silently weaken matching. |
| **O-03 — Named time filters and dates** | J-53–J-61 settle positive integer N, blank inactivity, strict elapsed > N × 24 hours, explicit One-Shot clearing/disabled input, draft-versus-applied numeric state, system-local absolute dates/year, and Deadline clock time. N bounds remain TBD. Specify eligible revision/Review derivation around Deadline/effective cutoff and terminal history, query clock consistency, exact date/time formatting and on-demand zone/offset access, DST/system-zone changes, and disabled/draft feedback. Expected Resolution stays independent/date-only; an app-specific zone setting is undecided, not planned. |
| **O-04 — Row truth and density** | J-36–J-41/J-47/J-58–J-61 settle contextual dates, One-Shot single date, duplicate local dates, no-eligible-forecast versus Invalid context, match disclosure, and absolute/time precision. Review exact labels/geometry, excluded-latest and corrected One-Shot Last forecast provenance, accurate additional-match counts/destinations, Question snippet reconciliation, full Numeric quantities/units, adaptive heights, and narrow stacking. Do not reopen date choices, ordinary tag/prose omission, or lifecycle grouping. |
| **O-05 — Navigation and drafts** | J-43/J-44/J-52 settle browsing vicinity versus deliberate retrieval scroll reset, and J-63 settles nonsticky page controls. Specify anchor selection/fallback when neighbors vanish or batches unload, empty-result and focus restoration, pragmatic loading under J-64, safe draft exits, minimum-width global bar, search shortcut binding, and Settings/Performance return behavior. Do not solve anchors with pixel offset alone or force advanced virtualization. |
| **O-06 — Creation feedback** | J-08/J-45 settle ordinary Journal return, quiet Prediction created without a View prediction link or All switch, and immediate answered-One-Shot Detail. Review notification wording/duration/accessibility, fully updated in-scope insertion with browsing vicinity retained, and precise Back/focus context after the answered exception. No reveal-link decision remains open. |
| **O-07 — Detail validation** | Carry forward the [existing v0.4 questions](prediction-detail-redesign.md#9-preferred-direction-vs-unresolved-decisions), including narrow panes, original/effective disclosures, and the single Add Answer dialog's terminal safeguard. The Detail R register and withdrawn R-33/R-34 are unchanged. |
| **O-08 — Contract and discrepancy review** | Resolve the differences below before implementation, including stable search/control semantics, minimal empty-state versus current fallback placement, current failure retention versus J-51, default sort, exact row sources/dates, and proposed loading/count changes. The charter still names the earlier J-31 checkpoint; no spec amendment is made here. Separately verify the cleared-Postmortem discrepancy; this pass neither verifies nor fixes it. |
| **O-09 — Safe Saved View retirement** | J-13 remains a proposed complete product-contract transition, not approved removal. Specify retention/disposition of existing configurations, CLI/tag dependencies, versioned atomic migration/rollback, schema-20/earlier supported upgrade and old-backup recovery, and user-facing compatibility guidance. Preserve original supported artifacts and a safe recovery route; CSV is not a substitute. No existing view, schema, command, or backup may change under this documentation pass. |

## Contract alignment before implementation

The product spec remains authoritative. Under its [design charter](../../product-spec.md#current-baseline-and-proposed-replacements), these are proposed differences to explore and resolve, not reasons to stop an authorized design exercise. This is the single cross-area alignment register; explicitly approved future requirements and software criteria will belong in the specification when ready. J-13's Saved View transition and J-51's error behavior are not reconciled merely by selecting them. **No current requirement is amended by this checkpoint.**

### Static current-browser baseline and limits

Read-only inspection of [prediction_browser.py](../../../src/reckonsolve/ui/prediction_browser.py) in the local checkout found a 250 ms single-shot debounce, refresh-time querying, and a QListWidget populated by iterating the returned archive snapshot/search hits. These inspected paths have no explicit page/Load more control or incremental-fetch interface; they do not establish that advanced virtualization is needed or that all current lower-layer query paths are unlimited. The render path displays a count for ordinary snapshots as well as search, and a failed refresh retains old results with a warning when a prior snapshot exists. Date context can include Created, Forecast deadline, Forecast considered, Expected resolution, and Terminal decision; ordinary forecast wording includes Current forecast.

These are **static code observations**, not a runtime reproduction, performance measurement, new behavior requirement, or approval to fix anything. They explain the current-to-preferred loading/count/label differences; the current debounce does not prove J-49's proposed workload responsiveness. The separate cleared-Postmortem finding below remains unverified/unfixed.

### Alignment register

| Current governing contract | Preferred direction requiring reconciliation |
| --- | --- |
| [Section 34.3](../../product-spec.md#343-application-shell-and-navigation-contract) retains Dashboard, Predictions, Analytics, and a remembered sidebar; [34.9](../../product-spec.md#349-keyboard-and-accessibility-contract) maps shortcuts to them. | J-01/J-05/J-06 introduce Journal, Performance, and a compact global bar. J-62/J-63 put retrieval controls above the list, disclosure-independent but scrolling away. Map every existing capability and shortcut; the search binding and narrow geometry remain open. |
| [Attention and Dashboard](../../product-spec.md#attention-and-dashboard) and [34.6](../../product-spec.md#346-page-and-workflow-presentation) expose attention sections/labels. The current browser statically renders ordinary counts. | J-03/J-04 remove persistent attention alerts/badges. J-65/J-66 select factual full matching-Prediction counts only for text/advanced retrieval, not quick views or manual sort alone. Reconcile on-demand retrieval/count presentation and measure counting without changing canonical classifications or making optional reflection a backlog. |
| [Section 33.5](../../product-spec.md#335-archive-filters-and-sorting) defaults ordinary browsing to Created newest and nonblank search to Relevance, with deterministic sorts and optional-value handling. | J-02/J-19–J-22/J-42/J-46 select Recently active from substantive app events, excluding Skip/corrections/documentary backdating. J-32/J-35 retain applicable manual sorts through transitions and discard manual Relevance on query clear. Define event derivation, ties, menu/applicability, and explicit automatic/manual state; do not substitute forecast freshness for activity. |
| [Sections 33.2–33.4](../../product-spec.md#332-searchable-corpus-and-historical-semantics) require broad current/effective and deliberate historical search, grouping, source-labeled snippets, additional matches, ranking, and exact context navigation. | J-09–J-12/J-47/J-48 preserve corpus/ranking/provenance, show best-ranked explanation then expandable N more matches, and place history inclusion under More filters with an active chip. Reconcile avoiding a duplicate current-Question snippet with 33.4's per-result snippet wording. History inclusion never changes effective facts; old immutable rationales/Reviews stay in the default corpus. |
| [Section 33.3](../../product-spec.md#333-query-and-matching-contract) requires deliberate All/Any words, a Search for any word empty-state offer, and optional accepted spelling suggestions. [33.5](../../product-spec.md#335-archive-filters-and-sorting) names Clear search and filters and distinct empty/failure states. | J-33 separates Clear filters, chip removal, clear text, and Reset Journal. J-34 prefers minimal accurate zero matches and no redundant recovery buttons, superseding only J-10's extra Search All suggestion; ordinary All remains. Reconcile current fallback/suggestion placement and word-mode/reset semantics explicitly, preserving deliberate capabilities and no silent broadening. No governing requirement is removed here. |
| [Section 33.5](../../product-spec.md#335-archive-filters-and-sorting) permits failed refreshes to retain previous results with a warning; [34.6](../../product-spec.md#346-page-and-workflow-presentation) explicitly preserves that presentation. [33.8](../../product-spec.md#338-search-persistence-repair-and-portability) requires visible index failure/repair; [33.9](../../product-spec.md#339-desktop-and-cli-boundaries) allows debounce without stale results masquerading as current. | J-49/J-50 condition live debounce on responsiveness and retain visibly outdated rows only while pending, with newest-request application and interactive controls. J-51 intentionally replaces the old listing on definitive error, preserving retrieval state and explicit error/repair distinction. This is a proposed failure-presentation contract change, not an implementation interpretation of retention. First-load, recovery, and count states still need specification; no redundant retry button is required. |
| [Sections 33.9–33.10](../../product-spec.md#339-desktop-and-cli-boundaries) require responsive navigation/search and large-corpus evidence. [34.6](../../product-spec.md#346-page-and-workflow-presentation) keeps the header/control frame stable through result-state changes. Current inspected rendering populates returned rows without an explicit pagination control. | J-15's intentional inline disclosure moves the list, but result refresh must not reflow/erase controls. J-52 resets result scroll only when deliberate new retrieval applies; same-retrieval refresh/return preserves browsing area. J-63's deliberate page scrolling is distinct from refresh-induced jumps. J-64 prefers pragmatic continuous loading with Load more as acceptable fallback; assess batching/anchors/responsiveness without imposing advanced virtualization. |
| [Section 33.5](../../product-spec.md#335-archive-filters-and-sorting), [Attention and Dashboard](../../product-spec.md#attention-and-dashboard), and [36.5](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) govern filter AND semantics, lifecycle/mode, local-calendar date meanings, and elapsed forecast freshness. | J-10/J-12/J-14/J-17/J-18 introduce quick-view/status composition and visible chips. J-23–J-25/J-53–J-57 add a distinct optional cross-lifecycle Adaptive filter: positive integer, strict elapsed > N × 24 hours, draft/applied separation, and explicit One-Shot clearing/disabled explanation without hidden restoration. Resolve eligible-event derivation and N bounds; preserve current date meanings and no One-Shot freshness. |
| [Section 33.6](../../product-spec.md#336-saved-views) requires dynamic Saved Views; [33.7](../../product-spec.md#337-tag-library-management) counts/retargets/removes tag references; [33.9](../../product-spec.md#339-desktop-and-cli-boundaries) exposes CLI listing/execution; [34.3](../../product-spec.md#343-application-shell-and-navigation-contract) and [34.8](../../product-spec.md#348-responsiveness-and-presentation-preferences) preserve Saved View context/configurations. | J-13 remains **PROPOSED complete retirement** across desktop, CLI, tags, and eventually persistence, superseding earlier master preservation wording. Reconcile commands, tag counts/warnings/transactions, context restoration, and persisted-query guarantees explicitly. This is a product/compatibility transition, not merely hidden controls, and no spec amendment/removal is authorized now. |
| [Recovery rules](../../product-spec.md#recovery-settings-and-technical-boundaries), [33.8](../../product-spec.md#338-search-persistence-repair-and-portability), [35.3](../../product-spec.md#353-durable-model-and-cohort-identity), and [36.5](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) preserve supported history/search/Saved Views in upgrades and SQLite recovery. Schema 20 adds nullable mode; existing views retain All modes. CSV format 5 excludes Saved Views and is not restorable. | J-13 requires a separately approved safe transition for existing configurations, schema-20/earlier supported upgrades/backups, retention/disposition, compatibility, versioned atomic migration, rollback, and complete recovery. Preserve original supported artifacts and a recovery path; never rewrite applied migrations or use CSV as recovery. No deletion, schema change, backup rewrite, or migration is authorized here. |
| [Sections 34.6](../../product-spec.md#346-page-and-workflow-presentation), [35.11](../../product-spec.md#3511-archive-search-saved-views-dashboard-and-cli), and [36.5](../../product-spec.md#365-retrieval-interfaces-compatibility-and-portability) describe row tags/dates and current/effective summaries. 35.11 already requires a readable local date/time Deadline. [35.4–35.8](../../product-spec.md#354-shared-exact-forecasting-window-and-resolution-time-contract) govern eligible cutoff selection. | J-26–J-31/J-36–J-41/J-58–J-61 choose Last active plus lifecycle-specific context when useful, one date for One-Shot, and duplicate local-date suppression. Open/Locked Deadline retains clock time; Outcome known uses effective R date, Invalidated the original decision date. Reconcile reduced/current row labels, routine tag omission, exact local/year formatting and on-demand offset access. General activity never replaces effective/recorded facts; an app-zone setting is undecided. |
| [Sections 35.4–35.8](../../product-spec.md#354-shared-exact-forecasting-window-and-resolution-time-contract) exclude forecasts at/after cutoff and require explicit unscored R <= t0; [36.4](../../product-spec.md#364-individual-scores-and-separate-analytics) uses One-Shot effective corrected facts. Invalid never scores. | J-28/J-29/J-39/J-40 specify faithful row sources: eligible forecast plus actual when eligible; actual plus Unscored / No eligible forecast when none qualifies; Invalid Last forecast / Not scored with all five Numeric values. Reconcile Current forecast-style labels with these sources, keeping corrections/originals and ineligible history in Detail. A final eligible Binary probability summarizes, rather than replaces, its scored path; Unscored is not a lifecycle. |
| [Section 34.3](../../product-spec.md#343-application-shell-and-navigation-contract) preserves search/filters/Saved View/sort/loaded results/scroll context when practical and prohibits silently substituting a different query after Detail. [34.7](../../product-spec.md#347-feedback-and-nonblocking-status-notifications) governs quiet acknowledgments and persistent failures. | J-07/J-43/J-44/J-52 require fully current ordering/membership with prior browsing vicinity restored using reliable anchors, not a frozen list, top-row chase, or temporary query exception. Specify missing/unloaded-neighbor and focus fallback alongside J-64. Quiet save feedback does not obscure failures or imply stale results are current. Saved View aspects remain subject to J-13's separate transition. |
| [Section 36.3](../../product-spec.md#363-creation-detail-and-lifecycle) sends both answered and unanswered One-Shot creation to Detail; [34.3](../../product-spec.md#343-application-shell-and-navigation-contract) also describes creation opening Detail. | J-08/J-45 normally return to the existing Journal, even when the new Prediction is outside retrieval, with quiet Prediction created and no View prediction link or All switch. Keep immediate Detail for answered One-Shot. Unanswered/ordinary landing is a proposed contract difference; retain atomicity, draft safety, and no score preview before Save. |

These preferences preserve immutable history, terminal finality, transaction-time checks, exact values/times, scoring cutoffs, model separation, documentary One-Shot facts, and search provenance. J-13 explicitly proposes a future behavior/persistence transition; J-51 proposes changed definitive-error presentation. Current schema 20, supported upgrade/SQLite recovery, analytical format-5 export, CLI, and all governing requirements remain in force. Resolve each relevant difference and obtain separate software authorization before changing behavior, commands, persistence, or recovery.

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

- **2026-10-28 — v0.4:** Consolidated the user's selected J-32–J-66 as **Preferred**: applicable manual-sort precedence and explicit reset scopes; minimal zero matches; effective lifecycle row dates, exact Numeric/unscored/Invalid context and local duplicate-date suppression; Skip/documentary-time activity; truthful return/creation behavior; grouped/history matches; conditional live search with distinct pending/error handling; scroll-change triggers; strict elapsed Last considered with mode/draft handling; absolute local dates/time precision; visible nonsticky controls; pragmatic continuous scrolling and contextual full-result counts. Reconciled earlier open wording and J-10's optional Search All button without erasing prior decisions. Updated the one roadmap, O-01–O-06 and related issues, future cases, and contract alignment, including static current-browser observations and explicit failure-retention/fallback gaps. Saved View retirement remains a proposed product-contract transition requiring safe recovery planning. Detail stays v0.3/R-01–R-42 with R-33/R-34 withdrawn. The cleared-Postmortem discrepancy stays unverified/unfixed. No governing-spec amendment, code/test/runtime/schema/CLI change, prototype/performance proof, design promotion, or implementation authorization occurred.
