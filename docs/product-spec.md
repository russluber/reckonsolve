# Reckonsolve product specification

Current contract: v0.8.0; schema 20; relational CSV format 5.

This is the source of truth for product scope, terminology, invariants, and acceptance criteria. It describes implemented behavior, not authorization for new work. Supporting guides and designs explain these requirements. A conflict or unresolved product choice must be surfaced to the user before implementation.

Completed milestone plans and earlier contracts are preserved in the [historical specification](archive/product-spec-through-v0.8.md). Sections 33-36 keep their established numbers so existing contract references remain useful. Their release labels identify the origins of active requirements; Section 36 extends the Adaptive contract in Section 35. Retired-model promises in the archive do not grant runtime support.

## Current contract map

- [Shared product rules](#shared-product-rules): history, Journals, corrections, attention, deletion, interfaces, and recovery.
- [Retrieval and organization](#33-retrieval-and-organization-contract): search, Saved Views, tags, and source-aware navigation.
- [Desktop presentation](#34-desktop-presentation-contract): visual system, navigation, accessibility, and responsive behavior.
- [Adaptive forecasting](#35-adaptive-forecasting-contract): exact Deadlines, trajectory Binary, five-quantile Numeric, and compatibility.
- [One-Shot forecasting](#36-one-shot-prediction-contract): existing answers, external notes, documentary time, transcription corrections, and separate scoring.

## Shared product rules

### Purpose and scope

Reckonsolve is a personal, local-first forecasting journal for one Windows user. It records Binary and Numeric probabilistic judgments, reasoning, honest changes of mind, answers, and calibration feedback. It works offline. It is a fresh successor to Predlog, not an extension of its CLI codebase.

> Let the user change their mind freely, but never let the application rewrite the fact that they used to think something else.

Supported creation modes are Adaptive and One-Shot. Adaptive remains the default. Their scoring and timing contracts are distinct; One-Shot is a mode within the existing Binary/Numeric types, not a third type or restoration of retired models.

Reasoning is first-class; required forecast inputs stay visually primary while prose remains optional. Forecast values never decay automatically. Staleness is a presentation/attention fact, not a probability change. Data ownership stays local; no account, hosted service, telemetry, or synchronization is required.

### Forecast history and atomic work

- Saved forecast statements, revisions, Reviews, Journal originals/corrections, Definition snapshots, terminal facts/corrections, and Postmortem completions are immutable.
- Creating a Prediction, its immutable contract/definition, first complete forecast, initial metadata/tags, and optional One-Shot answer is atomic.
- An Adaptive belief change appends a complete changed revision. Returning to a value used by an older non-current revision is valid. Submitting the current forecast unchanged creates no revision.
- One-Shot has exactly one original forecast. Correct transcription appends complete before/after snapshots; it does not create a new committed forecast or a fictitious updating interval.
- Type-specific values belong to the forecast statement, not merely a mutable current value on Prediction. Displayed current/effective facts are derived from canonical history.
- Numeric quantities use exact fixed base-ten precision at an immutable unit and value constraint. Every statement has exactly q05/q25/q50/q75/q95, ordered with ties allowed. No silent rounding, sorting, interpolation for scoring, or arbitrary quantile set is permitted.
- Opening, cancelling, invalid input, no-op correction, failed concurrency checks, or lock contention creates no partial history.
- Every write checks reviewed context and current eligibility inside its transaction. No silent overwrite, merge, or fabricated event time is allowed.

### Metadata and Definition history

Question and Resolution Criteria define the proposition. Clarification or correction requires explicit confirmation and one immutable before/after Definition snapshot, saved atomically with metadata. Cancel/no-op appends nothing. A material target, source, policy, threshold, or convention change calls for Invalid/new-Prediction guidance rather than relabeling old forecasts.

Background, tags, and Adaptive Expected Resolution are ordinary editable metadata, not fully audited field histories. Numeric unit, precision, and value constraint, mode/model/scoring identity, and Adaptive exact Deadline cannot be edited. One-Shot does not offer Expected Resolution or a new Resolution Criteria input; existing stored criteria and planning metadata are preserved without merging or deleting text.

Detail keeps Definition history collapsed by default. Optional values must be visibly unset when unset; enabling a draft control may seed a convenient value without claiming it is already stored.

### Journals and Forecast Reviews

A Journal records reasoning/evidence without changing forecast or freshness. It captures the transaction-current type-appropriate forecast anchor. New Journals are allowed only while nonterminal: Adaptive Open/Locked or One-Shot Waiting for answer.

Body corrections append immutable text versions and remain available after Resolution/Invalidation. They preserve the original timestamp, anchor, and Timeline position; no new forecast or backdated reasoning is created. Detail shows the effective body once, marks edited entries, and reveals original/superseded versions through collapsed Edit history. Search can navigate to a matched earlier version. Individual Journal deletion is unavailable.

A Forecast Review is Adaptive-only deliberate reconsideration retaining the current forecast. It records an immutable anchor, timestamp, and optional note; it creates no revision, chart marker, or scored observation. Multiple genuine Reviews are allowed while Open and before the Deadline. They carry the reviewed revision and metadata context and reject stale saves. Numeric wording refers to the current forecast/distribution, not a retired single interval.

### Terminal facts, corrections, and reflection

Resolution and Invalidation are one-way decisions. Neither reopens forecasting or permits new Journals/Reviews. Terminal originals and recorded-at times remain immutable; corrections append history and determine effective displayed facts. Outcome/value/effective-time corrections follow the model-specific contracts below. Invalid reason corrections change only text, not state or the original decision time.

Resolution notes are factual provenance; Postmortem is reflection. Each Prediction has one effective displayed Postmortem with transparent prior versions. It is optional at Resolution and can be added, corrected, or cleared later through audited terminal text correction. Clearing never deletes history.

Needs Postmortem includes only Resolved records with blank effective reflection and no explicit Skip completion. Skip appends an immutable completion fact, leaves score/state unchanged, and permits later reflection. A skipped entry does not return to the queue merely because reflection is blank. No reminder, penalty, or required explanation is added.

### Attention and Dashboard

Dashboard prioritizes actionable entries, identifying type, mode, current/effective forecast, lifecycle, and overlapping attention labels. Opening a row reaches the matching Detail. Attention categories are not canonical lifecycle states.

For nonterminal Adaptive records, Needs Attention uses the later eligible revision or Review and a configurable stale threshold, default 14 complete 24-hour periods. Journal/metadata/correction activity does not reset it. Freshness uses elapsed canonical UTC time, not display dates.

Ready to Resolve applies only to nonterminal Adaptive records when the computer's local calendar date is later than the optional Expected Resolution date. Expected Resolution is inclusive date-only planning metadata. Locking uses the exact immutable Deadline independently. One-Shot has no updating staleness or Expected Resolution-based attention; Waiting for answer is a presentation of its nonterminal state.

### Delete versus Invalid

Prefer Invalid once meaningful history exists. Delete is a confirmed, transactional exception for an untouched Open creation mistake. Eligibility is rechecked at commit: only the initial forecast exists; metadata is unchanged; no Journal, Review, Definition change, or other meaningful correction/terminal history exists. Initial rationale, metadata, and tags entered atomically do not alone disqualify the record. An expired Adaptive Deadline does.

Locked, revised, edited, journaled, reviewed, Resolved, Invalid, or corrected history is not normally deletable. Guarded deletion removes the eligible parent and its children atomically without orphan rows. No live database purge/reset or bulk deletion is implicitly authorized by a plan or a documentation change.

### Desktop and CLI

Desktop and CLI are thin presentations over shared application operations and canonical SQLite. Stable `reckonsolve` and `reckonsolve-cli`/`rsc` share the stable identity; `reckonsolve-dev` and `reckonsolve-cli-dev`/`rscd` share a separate development identity. Neither copies, falls back, or synchronizes between them.

CLI commands include list, show, search, saved-views, saved-view, create binary/numeric (optionally --one-shot), revise, journal, review, resolve, invalidate, delete, backup, and export-csv. Help/version finish without opening a database. IDs are stable integers. Read commands are side-effect free, with deterministic output and explicit failure instead of false empty results.

Mutations are interactive, show current context, preserve model validation, and confirm terminal/deletion decisions. Ctrl+C/end of input cancels unfinished work. Rationale/Journal/Review prompts are single-line; desktop text can be multiline. Human-readable output is usable without ANSI color; user text is never interpreted as commands or markup. Expected failures exit nonzero.

Metadata, Journal/terminal/transcription corrections, later Postmortem/Skip, Saved View mutation, tag-library maintenance, and search repair are desktop mutations. CLI show exposes their exact original/effective history. No JSON output, bulk mutation, arbitrary normal-user database selector, or stable scripting API is promised.

Simultaneous reads and sequential writes use independent connections. Bounded lock handling and stale-context failures preserve history without overwrite or indefinite retry. A GUI change appears on the next CLI invocation; a CLI change appears on normal GUI navigation/refresh/restart. No watcher or push synchronization is added.

### Recovery, settings, and technical boundaries

SQLite backup is the complete recovery artifact, verified before atomic destination replacement. It preserves supported canonical history, database settings, tags, Saved Views, and derived search state. Search may be deterministically rebuilt from canonical text on supported recovery. A successful backup alone advances last-successful-backup metadata.

CSV format 5 is analytical relational history with a dictionary, not an importer/restore format. Section 36.5 extends the earlier format-4 layout with One-Shot files. Failed export/backup preserves the previous destination. Saved Views, settings, presentation preferences, scores, CDF points, and search-index rows are excluded from CSV.

Settings supplies data/recovery facts, backup, export, search repair, the stale threshold, and keyboard guidance. Runtime databases are outside the source tree: stable `%LOCALAPPDATA%\Reckonsolve`, development `%LOCALAPPDATA%\Reckonsolve Dev`. Identity-scoped presentation.ini is separate from canonical SQLite and excluded from backup/export.

Use Python managed by uv, PySide6, standard-library SQLite, explicit transactions, pure domain/analytics rules, and lightweight immutable migration history. Do not introduce an ORM, migration/chart/theme framework, hosted service, web frontend, cloud database, or production dependency without a separately justified scope decision. Tests and private builds use only disposable paths.

Later features require explicit scope authorization: multi-user/social/cloud/mobile clients, structured evidence/attachments/Collections/graphs, notifications, automatic probability changes, extra forecast types or quantiles, numeric trajectory scoring, raw cross-question WIS pooling, conversion/importers, public installers/signing/update systems, and infrastructure for hypothetical scale.

## 33. Retrieval and organization contract

Search, filters, Saved Views, and tag maintenance remain local and canonical-history preserving. The following requirements originated in v0.5; Section 36 extends them with One-Shot provenance and mode filtering.

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

Historical search does not invent history for fields that Reckonsolve never audited. Background, Expected Resolution, and tag associations therefore expose only their current values. Date values, probabilities, Numeric quantile values, outcomes, statuses, and Postmortem-completion facts are rendered or filtered as structured information rather than indexed as undifferentiated prose.

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

SQLite backup continues to copy the complete database, including Saved Views and the physical derived index. Recovery verifies canonical migration history and either verifies or deterministically rebuilds the index before reporting success. Current relational CSV export is format version 5: it reflects current tag rows and associations but excludes the derived index, Saved Views, query text, ranking data, and spelling vocabulary.

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

## 34. Desktop presentation contract

The native visual system, shared shell, metadata parity, responsive layouts, and accessibility requirements originated in v0.6. These remain current; Section 36 incorporates the v0.8 creation and badge refinements.

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
- type-aware visual refinement across Dashboard, New Prediction, Prediction Detail, Predictions, Analytics, Settings, tag management, and existing dialogs;
- type-aware **Edit Details** parity for Binary and Numeric Predictions while keeping Numeric unit and decimal precision immutable; and
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
- the current Binary probability or complete five-quantile Numeric forecast;
- ordinary body text;
- labels and compact row metadata; and
- secondary explanatory or historical text.

Manual per-widget point-size additions should be replaced when practical by shared semantic helpers. Long Questions and user-authored text wrap naturally and remain selectable where they are currently selectable. Styling must not truncate canonical user text in Detail or dialogs.

#### Surfaces and panels

The main canvas, sidebar, input areas, raised content panels, selected rows, and modal dialogs use a restrained surface hierarchy derived from the active palette. Reusable panels replace inconsistent native-looking boxes where doing so improves hierarchy. A panel is not added around every label merely for decoration.

Borders and separators must remain visible in both system modes without becoming the most prominent elements. Rounded corners are used consistently. Layout shadows, if any, are subtle and never the sole indication that two regions are separate.

#### Status and forecast emphasis

Binary probability or the complete Numeric forecast remains readable without opening another view. Lifecycle and forecast type may use compact badges or labels, but the words **Open**, **Locked**, **Resolved**, **Invalid**, **Binary**, and **Numeric** remain present. Attention classifications remain explicit text and are not reduced to color or an unexplained icon.

Tags remain text labels with their stored display spelling. v0.6 does not introduce tag colors or semantic color assignment.

#### Icons

The existing local Lucide assets remain the icon source. Icons continue to derive legible colors from the active Qt palette and retain visible text for unfamiliar or consequential actions. Icon-only controls are limited to conventional shell actions such as collapsing the sidebar or closing a dismissible notification, and they require tooltips and accessible names.

v0.6 does not copy Super Productivity icons, assets, or branding.

#### Motion

Motion is limited to short sidebar width changes, disclosure expansion, and nonblocking status-notification entrance or exit where supported cleanly. It must not animate data values, charts, row ordering, or lifecycle changes in a way that obscures the final state. When Qt or the platform indicates that widget animation should be reduced or disabled, Reckonsolve follows that preference. A motion failure must degrade to an immediate state change.

### 34.5 Controls and action hierarchy

Every existing action is assigned a shared presentation role:

- **Primary**: the intended next committed action in the current context, such as Create Prediction, Save Revision, or Resolve Prediction inside its deliberate dialog.
- **Secondary**: a normal alternative, such as Add Journal Entry, Keep current forecast, or Edit details.
- **Quiet**: navigation or maintenance that should remain available without competing with the main action, such as Clear filters, Refresh, Back, or a disclosure toggle.
- **Caution**: Mark Invalid and its confirmation use the shared orange tone.
- **Destructive**: Delete uses the shared red tone and requires explicit confirmation.

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

The creation screen keeps Question and the type-appropriate forecast inputs visually primary. Binary remains the default forecast type. Adaptive keeps optional details collapsed; One-Shot follows Section 36's visible Background/Rationale/Tags layout. Optional fields must not acquire new required-looking styling, and no decorative stepper may imply that creation has multiple mandatory stages.

The form gains consistent label alignment, field spacing, error placement, button roles, focus order, and responsive wrapping. Switching type, validation failure, cancellation, and successful atomic creation retain their existing behavior.

#### Prediction Detail

Detail begins with a compact identity region containing the complete Question, forecast type, lifecycle state, current Binary probability or complete Numeric 90%/50% intervals and median, and nonempty tags. The current forecast is visually stronger than supporting metadata. The contextual Back action is always reachable by mouse and keyboard.

Common lifecycle-eligible actions remain immediately visible and use the shared action hierarchy. Rare correction, invalidation, or deletion actions may be grouped in a clearly labeled secondary area or menu only if their wording, availability, keyboard access, confirmation, and discoverability remain intact. No action may be hidden solely to achieve a cleaner screenshot.

Metadata, terminal summary, scorecard, history chart, timeline, Definition history, correction history, and Journal edit history use consistent sections and disclosures. Existing rules about hiding or de-emphasizing empty optional content remain. Collapsing a visual section changes no product data.

Binary and Numeric Detail must share the same visual grammar while retaining type-appropriate values and operations. User-authored rationale, Journal, Review, terminal, Postmortem, and correction text remains plain, selectable, wrap-safe, and historically explicit.

**Edit Details** has the same lifecycle availability and safety contract for Binary and Numeric. Editable metadata is Question, Background, Resolution Criteria when applicable, tags, and Adaptive Expected Resolution. Adaptive Forecast Deadline is read-only; One-Shot has no Deadline or Expected Resolution editor. Numeric unit, precision, and value constraint stay immutable; quantiles and forecast rationale belong to forecast history rather than metadata edits.

Question and Resolution Criteria clarifications receive the proposition-meaning warning and append a complete immutable Definition snapshot. Ordinary Background, Expected Resolution, and tag edits do not fabricate Definition history. Cancellation and no-ops write nothing. Every save transactionally rechecks the reviewed metadata version so a stale dialog cannot overwrite a newer GUI or CLI change.

The metadata row, tag associations, metadata version, Definition snapshot when required, and derived search documents update atomically. Editing metadata creates no Numeric ForecastRevision, Journal entry, Review, terminal record, scoring observation, or freshness reset. A Forecast Deadline edit may change the subsequently derived Open/Locked display exactly as it already does for Binary. The action remains desktop-only; v0.6 does not add CLI metadata editing.

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

Presentation changes do not add canonical fields or alter stored forecasts, lifecycle, scoring, or search semantics. The current schema is 20; schema changes belong to authorized domain/persistence work, not visual preferences.

The visual system belongs in a small centralized UI boundary rather than scattered widget-local styles. Reusable page headers, panels, action roles, badges, status regions, and palette helpers may be introduced where they remove real repetition. Domain, analytics, application, and data-access modules must not import the visual layer.

Qt palette roles, font metrics, style hints, layouts, and local Lucide resources remain authoritative inputs. v0.6 adds no production dependency, web renderer, Material framework, QML rewrite, second GUI toolkit, external theme package, or copied Super Productivity component.

Presentation preference storage is opened and tested independently of the canonical SQLite data path. Failure to read or write a presentation preference falls back to safe defaults and must not prevent database startup or a forecasting operation. Automated tests isolate presentation settings just as they isolate databases and must never read or modify the user's real settings.

Stable and development CLI commands share current product operations. Visual preferences and metadata editing introduce no CLI command, option, prompt, or persistence rule. Simultaneous reads and sequential GUI/CLI writes retain their existing contract; a CLI-side tag or other metadata-context change must still cause an already-open Numeric Edit Details dialog to fail safely as stale.

Backup remains complete SQLite recovery; CSV remains analytical format 5. Neither artifact contains window geometry, sidebar mode, transient messages, or other presentation state.

## 35. Adaptive forecasting contract

v0.7 introduces exact forecasting commitments and supports Binary trajectory
and five-quantile Numeric Predictions. The original staged plan preserved legacy
workflows; the user-approved 2026-09-20 amendment retires those workflows before
release, without rewriting or deleting their records. It incorporates the
following accepted design inputs:

- [Forecasting Rulebook v0.7](reckonsolve-forecasting-rulebook-v0.7.md);
- [Binary Trajectory Scoring Design v0.7](maintainer/design/binary-trajectory-v0.7.md); and
- [Numeric Forecasting Design v0.7](maintainer/design/numeric-forecasting-v0.7.md).

Those documents retain the complete rationale, examples, and mathematical
derivations. This section is the repository's governing implementation
contract. If later wording in a supporting document appears to conflict with
this section, surface the conflict and revise this specification deliberately
rather than choosing silently.

The release promise is:

> Make only forecasts that measure judgment rather than self-control, commit
> each new forecast to an exact immutable forecasting window, score the whole
> standing Binary probability path, and represent every new Numeric belief as
> one fixed five-quantile distribution.

Shared requirements above govern behavior not changed by this contract. Section 35.3 supersedes historical legacy-support and coexistence promises. Adaptive requires exact immutable Deadlines, trajectory Binary scoring, and fixed five-quantile Numeric forecasts. Section 36 supplies the explicit One-Shot exception. Completed M46-M55 plans remain in the archived specification.

### 35.1 Included scope and governing invariants

v0.7 includes:

- the Forecasting Rulebook as durable, local product guidance for deciding
  which questions belong in Reckonsolve;
- durable forecast-model and scoring-contract identities that do not depend
  on application version or optimistic-concurrency metadata;
- one mandatory, exact, timezone-aware, immutable Forecast Deadline for every
  newly created Binary or Numeric Prediction;
- separate effective-resolution and recorded-at instants for every new-model
  Resolution, including append-only correction of effective resolution time;
- duration-weighted Binary Trajectory Brier with neutral truncation after
  early resolution;
- Binary Initial Brier, Final Brier, hold-initial counterfactual, Updating
  Gain, and Active Forecast Fraction diagnostics;
- a new Numeric model consisting of the 5th, 25th, 50th, 75th, and 95th
  percentiles, presented as a 90% interval, median, and 50% interval;
- exact five-quantile WIS, individual score decomposition, and
  initial-versus-final WIS diagnostics;
- continuous-style and whole-number Numeric value constraints with
  discrete-aware calibration;
- an implied central CDF that distinguishes elicited quantiles from
  interpolation and invents no outer-tail shape;
- explicit retirement of legacy Binary and interval-v1 Numeric workflows,
  preserving supported v0.7 data and refusing legacy-containing databases safely;
- matching GUI and CLI workflows over the same canonical database; and
- migration, search, backup, relational CSV export, recovery, and private
  frozen-build hardening for the new records.

The following invariants govern the release:

- A ForecastRevision remains immutable regardless of model.
- Forecast-model identity and scoring-contract identity are immutable
  Prediction-level facts and are not inferred from the running package
  version.
- `metadata_version` remains only an optimistic-concurrency token; it never
  doubles as model or scoring identity.
- New creation offers only the new v0.7 model for the selected Binary or
  Numeric forecast type. It does not expose a legacy/new model selector.
- Existing v0.7 Predictions retain their models, facts, history, and scores.
  Legacy records retain their original meaning in their original database but
  are not supported by the post-M54B application; refusal never implies deletion.
- No migration invents an exact deadline, effective resolution time,
  probability trajectory, quantile, or WIS for a legacy record.
- New Binary and Numeric Predictions share a forecasting lifecycle but retain
  deliberately different scoring rules.
- Every eligible Resolved Prediction contributes at most one
  Prediction-level observation to its compatible aggregate.
- Invalid and unresolved Predictions remain excluded from scoring.
- Corrections recompute from immutable source facts; they never rewrite
  ForecastRevision history or the original recorded-at audit instant.
- All behavior remains offline, local-first, single-user, and shared between
  only the paired stable or development GUI and CLI identities.

### 35.2 Forecasting Rulebook and admissible questions

Reckonsolve trains calibrated observational judgment, not compliance with
goals, promises, habits, or commitments. A forecast may be personal because
its outcome matters to the user; it need not be about the user.

Before creating a Prediction, the user should check that it is personally
relevant or genuinely interesting, meaningfully uncertain, and objectively
resolvable. The user should also identify realistic post-forecast actions
that could materially affect the outcome and consider whether seeing the
forecast could turn it into a goal or change behavior enough to contaminate
the result.

The Rulebook recognizes three mental classifications:

- **A - Observational**: little meaningful discretionary control remains
  after commitment.
- **B - Policy-conditioned**: substantial realistic influence remains, but a
  clear precommitted behavioral intervention policy can hold that influence
  fixed.
- **C - Inadmissible**: the question mainly measures future agency,
  self-control, compliance, or a manipulable result and does not belong in
  Reckonsolve.

This classification is guidance rather than a persisted product field.
v0.7 adds no A/B/C database column, scoring split, archive filter, or required
attestation. Desktop New Prediction omits the "Choosing a forecasting commitment"
expander following the v0.8 closeout review. Admissibility and Deadline-selection
advice remain in the Rulebook and forecasting guide; optional CLI guidance remains available.
The complete Rulebook remains the durable reference.
Creation copy uses sentence case while retaining "Forecast Deadline · Required".
The unset shortcut prompt and explanatory Deadline footer are omitted; a chosen
date/time summary and validation messages remain available.

Prefer uncertain consequences after major discretionary choices have already
been made or frozen. Do not pretend a forecast is observational merely
because an unlikely theoretical intervention exists; judge practical,
realistically available control in the ordinary course of events.

For a policy-conditioned forecast:

- the policy is part of the forecast's meaning;
- it uses objective behavioral language, covers material channels of
  influence, and distinguishes allowed ordinary interaction;
- it must be realistic enough not to distort normal life;
- it is written as a clearly labeled subsection of Resolution Criteria;
- it is fixed once the initial forecast is committed; and
- a material breach makes the Prediction Invalid rather than scored with a
  post-hoc excuse.

v0.7 does not add a dedicated Intervention Policy field because the software
does not yet need separate programmatic semantics. Resolution Criteria
continues to hold the policy text. A material change to the target, policy,
source of truth, unit, measurement window, or scoring window is not a normal
metadata correction. Resolve under the original contract when possible;
otherwise mark the original Invalid and create a new Prediction.

Real-world welfare takes precedence over preserving a score. The user should
intervene when life requires it and invalidate the forecast if that
intervention breaks the committed policy. Such invalidation protects the
learning record and is not a forecasting failure.

The Rulebook may evolve prospectively. A later clarification must not
retroactively relabel, rescore, or condemn Predictions made under an earlier
accepted contract.

### 35.3 Durable model and cohort identity

Every Prediction has one immutable forecast-model identity and one immutable
scoring-contract identity. Exact stored names are an implementation detail.
The original staged implementation distinguished these four cohorts; only the
right-hand column remains supported after M54B:

| Forecast type | Legacy cohort | New v0.7 cohort |
|---|---|---|
| Binary | one final captured probability with ordinary Brier | standing probability trajectory with Trajectory Brier |
| Numeric | `interval-v1`: lower, median, upper, chosen confidence | `quantiles-5-v2`: q05, q25, q50, q75, q95 with WIS |

The earlier M46–M54 implementation identified and preserved legacy records rather
than reinterpreting them. That remains the historical description of those
milestones, not a requirement to retain legacy editors or scoring in the release.

The supported contract after M54B is:

- `create binary` creates only the Binary trajectory model;
- `create numeric` creates only `quantiles-5-v2`;
- there is no normal conversion command or model selector;
- all reads, writes, anchors, scoring, and rendering dispatch from stored
  model identity rather than guessed table population.

#### Approved legacy-retirement policy (2026-09-20)

The user confirmed that legacy records were disposable tests rather than a real
forecasting archive. The product will begin genuine use with the v0.7 models.
Maintaining old-model workflows is therefore outside the revised release scope.

- **Retire behavior, not history:** remove legacy editors, lifecycle/revision
  dispatch, individual scorecards, aggregate sections, CLI paths, and their
  runtime-only helpers. Do not merely hide legacy cards while keeping a second
  supported forecasting system underneath.
- **Preserve v0.7 data:** a supported upgrade must retain every v0.7 Prediction,
  model/scoring identity, exact Deadline, revision, Journal and correction,
  Review, definition change, effective/recorded terminal fact, Postmortem record,
  tag relationship, and Saved View. Rebuilt derived state must reproduce the
  same retrieval and scoring results. Retirement does not reset either identity.
- **Refuse mixed and legacy databases:** if even one legacy Prediction exists,
  reject the whole database before migration, search repair, or normal writes.
  This applies to Open, Locked, Resolved, and Invalid records, and to GUI and CLI.
  Do not hide unsupported rows and operate on the remaining subset. A new-model
  database containing an unknown or mismatched identity is also refused.
- **Explain refusal clearly:** identify the unsupported model/database and explain
  that no conversion or deletion occurred. An old database or SQLite backup
  containing legacy records will not open in the new application. Keep the
  original artifact usable with a compatible earlier version; do not overwrite it
  or promise that a v0.7 analytical export can restore it.
- **No implicit cleanup permission:** this contract authorizes no purge, reset,
  automatic conversion, timestamp inference, or bulk deletion. Cleaning disposable
  test data is a separate explicitly approved operation with identified targets,
  backup/recovery guidance, and preservation of any v0.7 records the user keeps.
  Until then a mixed database may legitimately prevent launching the new build.
- **Separate history from shared infrastructure:** retain tables, revision anchors,
  Brier-loss math, correction relationships, and migration machinery still needed
  by the supported models. A table's age or name alone does not make it obsolete.
  Any schema cleanup must be versioned, transactional, and preserve supported data;
  never modify an already-applied migration in place. Keeping necessary historical
  migration SQL is not a promise of legacy application support.

Fresh databases and valid pre-retirement v0.7-only databases are supported inputs.
M54B must inventory and test the supported upgrade paths, including supported schema-18 v0.7-only databases and their schema-20 upgrades. Older backups are classified by their stored
schema and model contracts, not their filename, identity folder, or package-version
label. Unsupported schemas and malformed/missing identities produce a clear,
non-mutating compatibility error rather than guessed models or a fresh replacement.
Never strand valid v0.7 history as a convenience for simplifying the schema; surface
any such migration obstacle before implementation proceeds.

### 35.4 Shared exact forecasting-window and resolution-time contract

For each new v0.7 Prediction, define:

- `t0` as the immutable system-generated commit instant of its sequence-one
  ForecastRevision;
- `T` as its Forecast Deadline;
- `R` as its effective resolution time; and
- `C = min(R, T)` as its scoring cutoff.

#### Forecast Deadline

`T` is:

- required during initial creation;
- one exact timezone-aware instant converted to canonical UTC for storage;
- strictly later than `t0`;
- committed atomically with the Prediction and first ForecastRevision;
- immutable after commitment; and
- the last instant at which a ForecastRevision or Forecast Review may commit.

Forecasting is allowed on the half-open interval `[t0, T)`. At exactly `T`,
an otherwise nonterminal Prediction is Locked. Resolution and Invalidation
remain available after locking, and Journals retain their existing Locked
behavior.

The creation UI must make Forecast Deadline prominent, explain that it cannot
be edited later, and distinguish it from Expected Resolution. It should
discourage deadlines chosen merely to match the modal expected outcome,
unnecessarily short cutoffs, distant safety buffers, and choices optimized
for a desired score. Input may use local date, time, and zone-aware platform
controls, but the committed value must resolve to one unambiguous instant.

M54C replaces the desktop required-field checkbox with an initially unset
deadline picker shared by both forecast types. Explicit shortcuts are **End of
today**, **End of tomorrow**, **7 days**, and **30 days**, plus **Custom…**.
Shortcuts use the local calendar date at the time of the click, adding 0, 1, 7,
or 30 calendar days and choosing 23:59:00. They are conveniences, not recommended
forecasting horizons. The selected exact date/time is always shown and editable;
opening the screen alone chooses nothing. Custom opens editable date/time fields
with today's 23:59 as a visible starting choice. Seconds are zero.

Local entry uses the system time zone's rules for the chosen date, including
future daylight-saving changes, and displays the resulting zone and UTC offset.
An optional **Use another UTC offset** control retains explicit-offset entry.
A nonexistent local time is rejected without shifting it; a repeated local time
requires a deliberate choice between its two offsets. Invalid or expired input
remains visible for correction, and the existing transaction still enforces
`T > t0`. Switching forecast type retains the draft deadline; successful creation
resets it to unset. Expected Resolution remains independent. This change adds
no schema, CLI prompt, persisted preference, or scoring behavior.

For the new cohorts, Edit Details displays Forecast Deadline as immutable
context and offers no addition, change, or removal action. The retired date-only
legacy editor is not part of the post-M54B application.

#### Expected Resolution

Expected Resolution remains optional, editable, date-only planning metadata.
It predicts when the answer may become knowable and retains the existing
Ready to Resolve behavior. It never changes `T`, `R`, lifecycle locking,
revision eligibility, a scoring denominator, or an analytical observation.

#### Revision timing

New-model ForecastRevision instants are system-generated and cannot be
backdated or forward-dated by the user. Each new revision must commit strictly
after its preceding revision and strictly before `T`. If the supplied system
clock does not produce a later canonical instant, the operation rejects the
save clearly rather than inventing elapsed time or rewriting a timestamp.
Forecast Reviews must commit before `T` but do not split a scoring interval.

#### Effective resolution and recorded-at

`R` is the earliest defensible exact instant at which the outcome became
fixed and ascertainable under the committed Resolution Criteria and source of
truth. The user enters or confirms this value during Resolution. When an
objective source supplies an exact time, that source time should be used.

`recorded_at` is the immutable system-generated instant when the Resolution
was entered into Reckonsolve. It remains the audit and terminal-ordering fact.
`R` must not be later than `recorded_at`. Delayed data entry never changes
scoring because scoring uses `R`, not `recorded_at`.

A revision committed before the Resolution was recorded but at or after `C`
remains visible immutable history and is excluded from scoring. The
application does not delete it or pretend it never stood before Reckonsolve
learned the effective facts.

If `R <= t0`, the Prediction may retain an honest Resolution record but is not
a meaningful scored forecast. It produces no Trajectory Brier, WIS, or
calibration observation, and the UI explains why rather than substituting the
initial revision or a zero-duration score.

### 35.5 Binary standing forecasts and Trajectory Brier

For a Binary outcome `y` in `{0, 1}` and probability `p` on the zero-to-one
scale, ordinary Brier loss remains:

```text
B(p, y) = (p - y)^2
```

For one eligible Binary trajectory Prediction, consider only revisions with
commit instants strictly before `C`. Each probability stands from its commit
instant until the next scoring-relevant revision or `C`. Journals, Journal
corrections, Forecast Reviews and notes, metadata clarifications, terminal
text, and Postmortem activity do not split or weight this path.

Let the actual standing segments have exact elapsed durations `d_i` and Brier
losses `B_i`. Define neutral truncation duration:

```text
d_N = T - R, when R < T
d_N = 0,     when R >= T
```

Then the primary Binary score is:

```text
Trajectory Brier =
    (sum(d_i * B_i) + d_N * 0.25)
    / (T - t0)
```

Lower is better, and the result remains between zero and one.

If `R < T`, actual forecast weighting stops at `R` and the remainder of the
predetermined window contributes neutral Brier loss `0.25`. This neutral
truncation:

- preserves the denominator chosen before the outcome;
- does not create a synthetic 50% ForecastRevision;
- does not state that the user believed 50%; and
- is Binary-specific.

If `R >= T`, standing probabilities score only through `T`. Waiting to record
or learn a late outcome adds no post-deadline time. If `R = T`, there is no
neutral interval. Exact elapsed durations use normalized instants and
sufficient precision for sub-day updates; the implementation must not
discretize the path into calendar days.

Every eligible Binary trajectory Prediction contributes one Trajectory Brier
to its aggregate regardless of whether its window lasted hours or months.
Time weighting occurs within a Prediction; longer Predictions do not receive
more aggregate weight.

### 35.6 Binary diagnostics, scorecards, and analytics

For each eligible Resolved Binary trajectory Prediction, the scorecard shows
Trajectory Brier as the primary score and may progressively disclose:

- **Initial Brier**: Brier loss of the sequence-one probability against the
  effective outcome;
- **Final Brier**: Brier loss of the latest revision strictly before `C`;
- **Hold-initial Trajectory Brier**: the counterfactual score obtained by
  retaining the initial probability through the active portion while using
  the same fixed deadline, effective time, neutral truncation, and
  denominator;
- **Updating Gain**: hold-initial Trajectory Brier minus actual Trajectory
  Brier, where positive means the recorded revision path mechanically helped,
  zero means no net effect, and negative means it mechanically hurt; and
- **Active Forecast Fraction**: `(C - t0) / (T - t0)`, shown as the portion
  of the planned window that contained actual forecasting.

Updating Gain is a mechanical hindsight counterfactual, not proof that
updating caused skill. Active Forecast Fraction explains heavy neutral
truncation and never alters the score.

Binary Analytics separates:

- the new trajectory cohort, with count, equal-Prediction mean Trajectory
  Brier, distribution or time summaries, and clearly labeled diagnostics;
- final-probability calibration for eligible new-model Predictions, using one
  final probability strictly before `C` as a diagnostic rather than a
  trajectory score.

Legacy aggregate sections are removed by M54B. Ordinary Brier remains necessary
for the supported trajectory calculation and Initial/Final diagnostics; retiring
legacy forecasts does not retire that shared mathematics.

No headline silently averages legacy Brier and Trajectory Brier. No revision
is an independent aggregate observation. v0.7 adds no metric called
trajectory calibration, no time-weighted calibration construction, and no
Binary log score.

### 35.7 Five-quantile Numeric model

Every new Numeric Prediction forecasts one well-defined scalar random
variable in one required immutable unit. A combined target such as cost and
duration must be represented as two Predictions.

In addition to unit and the existing exact fixed decimal precision, the
Prediction records one immutable value constraint:

- **Decimal / continuous-style**; or
- **Whole-number**.

This is not a third forecast type. Both constraints use the same five
quantiles and WIS. Whole-number mode requires every quantile and realized
value to be mathematically integral, permits repeated quantiles, and uses
discrete-aware calibration. v0.7 adds no probability-mass-function editor.

Each `quantiles-5-v2` ForecastRevision contains exactly:

- `q05`, the 5th percentile;
- `q25`, the 25th percentile;
- `q50`, the median or 50th percentile;
- `q75`, the 75th percentile;
- `q95`, the 95th percentile;
- an optional rationale;
- one immutable system-generated commit instant; and
- deterministic per-Prediction sequence.

The UI presents those values as:

```text
90% interval: q05 to q95
Median:       q50
50% interval: q25 to q75
```

There is no chosen confidence level. Every new Numeric revision always
expresses the same 90% interval, median, and 50% interval.

Required ordering is:

```text
q05 <= q25 <= q50 <= q75 <= q95
```

Equality is valid. Crossed quantiles are rejected and never silently sorted.
Negative, zero, positive, whole, and supported exact decimal values remain
valid subject to the Prediction's fixed precision and value constraint.
NaN, infinities, and textual sentinels are invalid.

One revision is a complete five-quantile statement. Changing any subset
appends all five current values atomically; a save identical to all five
current values creates no revision and directs deliberate unchanged
reconsideration to Forecast Review. Revision input is prepopulated and may be
edited in any order. Reckonsolve may suggest the outside-in sequence 90%
interval, median, then 50% interval, but it must not enforce a wizard or
cognitive ordering.

The Numeric Review action uses model-neutral wording such as **Keep current
forecast** or **Keep current distribution**, not **Keep this interval**.
Reviews and Journals preserve their existing history and freshness semantics
and never change quantiles or scoring.

Resolution Criteria should define the target, measurement start and end,
source of truth, unit conventions, inclusions and exclusions, aggregation or
rounding rules, exceptional cases, and any intervention policy when material.
Unit, precision, value constraint, Forecast Deadline, and material target
definition are scoring-critical and may not be redefined after commitment.

### 35.8 Numeric scoring selection and WIS

For an eligible Resolved `quantiles-5-v2` Prediction, the final scoring
revision is the latest valid five-quantile revision committed strictly before
`C = min(R, T)`.

If `R < T`, the last revision before effective resolution is final. If
`R >= T`, the last revision before the deadline is final. A revision at
exactly `C` is ineligible. Numeric scoring has no neutral truncation, no
post-resolution contribution, and no trajectory score in v0.7.

For interval `[L, U]`, realized value `y`, and tail probability `alpha`:

```text
IS_alpha(L, U; y) =
    (U - L)
    + (2 / alpha) * (L - y), when y < L
    + (2 / alpha) * (y - U), when y > U
```

Only the applicable miss term is added. Equality with an endpoint has zero
outside-distance penalty.

The canonical five-quantile Weighted Interval Score is:

```text
WIS =
    (0.5 * abs(y - q50)
     + 0.25 * IS_0.50(q25, q75; y)
     + 0.05 * IS_0.10(q05, q95; y))
    / 2.5
```

This is equivalent to the mean of the five corresponding quantile scores.
Scoring uses exact stored values, never rounded display text or interpolated
CDF points.

WIS is lower-is-better and retains the target's unit and scale. It is useful
for comparing revisions within one Prediction and interpreting one resolved
forecast, but it is not a universal personal skill score. v0.7 does not
average raw WIS, interval width, median error, or WIS improvement across
heterogeneous Numeric questions; matching unit labels alone do not guarantee
comparable scale or difficulty.

A resolved Numeric scorecard shows:

- actual value;
- primary WIS;
- median absolute error and signed median miss;
- 50% and 90% interval width;
- whether each interval was below, inside, or above the actual;
- miss direction and distance when outside;
- each interval score and weighted contribution; and
- correction-history presence when an effective scoring fact changed.

The scorecard may progressively disclose dispersion, underprediction, and
overprediction decomposition, but WIS remains the canonical summary.

Initial WIS uses sequence one. Final WIS uses the final scoring revision.
`Delta WIS = Initial WIS - Final WIS`, so positive means the final
distribution scored better, zero means equal, and negative means worse.
Across heterogeneous Predictions, only counts and fractions better/equal/
worse may be combined; raw Delta WIS magnitudes are not averaged. Do not call
this Numeric Updating Gain.

### 35.9 Numeric calibration and implied-distribution presentation

Global five-quantile Numeric analytics are calibration-first. Each eligible
Resolved `quantiles-5-v2` Prediction contributes exactly one observation
using its final scoring revision and latest effective actual value.

The view includes:

- sample size;
- calibration at nominal levels 5%, 25%, 50%, 75%, and 95%;
- 50% interval outcomes split into below, inside, and above;
- 90% interval outcomes split into below, inside, and above;
- median balance; and
- Wilson binomial uncertainty intervals or an equivalently explicit
  small-sample treatment for displayed proportions.

For Decimal / continuous-style targets, quantile calibration compares each
nominal level `tau` with the empirical frequency of `y <= q_tau` and shows
the perfect-calibration diagonal. It does not generate synthetic Numeric
10%-through-90% confidence bins.

For Whole-number targets, equality may carry real probability mass.
Calibration therefore reports both empirical `P(y < q_tau)` and
`P(y <= q_tau)` as a tie band around each nominal level. Interval and median
views preserve below/equal/inside/above information and do not label a
closed-interval coverage rate above nominal as automatically miscalibrated.

The current Numeric forecast has an implied central CDF derived only between
the five elicited anchors:

- distinct adjacent quantiles connect by piecewise-linear interpolation in
  cumulative-probability space;
- repeated adjacent quantiles render as a vertical probability jump without
  division by zero;
- elicited anchors are visually distinguishable from interpolated segments;
- approximately 5% below `q05` and 5% above `q95` may be described with
  discrete-aware wording where needed; and
- no normal, lognormal, exponential, minimum, maximum, full density, or other
  unsupported outer-tail shape is invented.

The CDF is presentation derived from the quantiles. Interpolation never
changes WIS, calibration, stored history, or export values. Every revision
and its five exact quantiles remains recoverable from the textual timeline,
so the chart is not the sole historical representation.

M54B removes legacy `interval-v1` containment bins and raw aggregate summaries.
They never enter five-quantile calibration or WIS feedback. Binary/Numeric
selection, tag and exact-unit filtering, and continuous-style/whole-number
separation retain their supported meanings.

### 35.10 Creation, Detail, lifecycle, and correction workflows

New Prediction retains the Binary/Numeric choice and calm v0.6 visual system,
but the minimum committed fields become:

- Binary: Question, whole-number probability from 0% through 100%, and exact
  Forecast Deadline;
- Numeric: Question, unit, precision, value constraint, q05, q25, q50, q75,
  q95, and exact Forecast Deadline.

Rationale, Background, Resolution Criteria, Expected Resolution, and tags
remain optional. For policy-conditioned forecasts, the Rulebook advises
placing the policy in Resolution Criteria; the software does not force prose.
The Prediction, immutable model identities, deadline, optional details and
tags, and first complete revision commit atomically.

Binary and Numeric Detail must show:

- forecast type and model cohort;
- complete Question and lifecycle;
- exact immutable Forecast Deadline;
- optional Expected Resolution separately;
- current type-appropriate forecast;
- full causal timeline and Review/Journal distinctions;
- relevant history visualization;
- terminal effective and recorded times when Resolved; and
- type-appropriate scorecard or explicit unscored explanation.

Legacy editors, scorecards, and normal navigation are absent after M54B.
Compatibility errors must be calm, clear, and never suggest automatic conversion.

The shared active lifecycle is:

- **Open** before `T` and before a terminal decision: revisions, Reviews, and
  Journals are allowed.
- **Locked** at or after `T` while nonterminal: revisions and Reviews are
  rejected; Journals, Resolution, and Invalidation remain allowed.
- **Resolved**: no new forecast activity; effective outcome, `R`, and
  `recorded_at` are retained for scoring and audit.
- **Invalid**: preserved, unscored, and unavailable for forecast activity.

Needs Attention remains based on the later eligible Revision or Review.
Journal activity does not reset it. Ready to Resolve remains driven only by
optional Expected Resolution. Needs Postmortem remains a Resolved-only
completion queue. No v0.7 score changes these attention classifications.

For a new-model Resolution, the user supplies outcome or exact actual value,
effective resolution time, optional Resolution notes, and optional
Postmortem. Reckonsolve supplies recorded-at. Resolution is atomic and
one-way.

The existing append-only correction workflow is extended so one confirmed
new-model correction may change the effective outcome, Resolution notes,
Postmortem, and/or effective resolution time. A change to outcome, actual
value, or effective resolution time requires a nonempty explanation because
it may change scoring selection or score. Before/after effective-time facts,
changed-field flags, reason, and correction timestamp are preserved.
Recorded-at never changes.

For supported Resolutions, canonical scoring selection is derived from immutable revision timestamps,
immutable `T`, and latest effective `R`. An audited correction to `R` may
therefore change the final eligible revision without rewriting any revision
or original Resolution fact. Any cached revision identifier is derived and
must not override those canonical facts.

Question and Resolution Criteria retain Definition-history protection.
Clarifications that preserve meaning may be audited. A material target,
policy, source, or convention change follows Invalid/new-Prediction guidance.
For new models, the immutable Deadline is not part of an editable Definition
snapshot because no normal edit exists.

### 35.11 Archive, search, Saved Views, Dashboard, and CLI

Dashboard and Predictions remain one Binary/Numeric archive. Each row renders the
stored forecast type, model-appropriate current forecast or terminal summary,
lifecycle, tags, dates, and attention labels. A new Numeric row shows the
90% interval, median, and 50% interval without a confidence selector.
Desktop Dashboard, Predictions, and Prediction Detail show an exact immutable
Forecast Deadline as a readable local date and time, separate from the forecast
value. Detail keeps the offset-bearing instant available in a tooltip while the
canonical Deadline and CLI exact-time display remain unchanged.
Deadline date filtering projects an exact new-model deadline into the
query's one local-calendar view. No legacy rows are silently omitted: their
presence prevents opening the database under Section 35.3.

Search keeps the v0.5 lexical, explainable, grouped behavior. Five-quantile
values, score values, model identities, and timestamps remain structured
facts rather than undifferentiated indexed prose. New revision rationales,
Reviews, Journals, definitions, terminal text, and correction explanations
enter the same current/effective and superseded projection rules. Search
repair remains derived-only and cannot change model or scoring facts.

Saved Views remain dynamic query configurations. Tags retain their stable
identity and transactional rename/merge/delete behavior. v0.7 does not turn
model cohorts into Collections or persist result membership. Existing status,
forecast-type, tag, attention, date, and sort semantics remain unchanged
unless a later explicitly approved slice adds a model-cohort filter.

The existing CLI command family remains the companion interface:

- `create binary` requires probability and an exact Forecast Deadline;
- `create numeric` creates only the five-quantile model and prompts for unit,
  precision, value constraint, all five quantiles, and exact Forecast
  Deadline;
- `revise` dispatches to Binary trajectory or Numeric five-quantile from
  stored model identity;
- `review` uses current-forecast wording and retains no-change semantics;
- `resolve` collects a type-appropriate outcome plus effective resolution
  time and preserves automatic recorded-at;
- `show` displays model identity, exact deadlines, all five quantiles,
  effective and recorded resolution facts, correction history, and
  type-appropriate score information; and
- `list` and `search` display model-appropriate summaries for both supported types.

CLI prompts remain human-directed and line-oriented. The CLI reuses the same
application operations, validation, migrations, model dispatch, and SQLite
transactions as the GUI. It does not calculate scores, issue ad hoc SQL, or
create a synchronization system.

### 35.12 Persistence, migration, backup, and export

The implemented M46 migration followed schema version 15 and established the
shared prospective contract. Its historical requirements were:

- add durable forecast-model and scoring-contract identities;
- mark every existing Binary and Numeric Prediction with its exact legacy
  identity;
- add exact immutable deadline storage for new models without replacing or
  guessing legacy date-only values;
- add prospective effective-resolution storage and append-only correction
  support while retaining original recorded terminal instants;
- preserve every existing row and derived search document; and
- be idempotent, history-validated, foreign-key checked, and covered by a
  forced-failure rollback test.

The implemented Numeric persistence migration added a clean immutable five-quantile
revision representation rather than repurposing `numeric_forecast_revisions`.
The physical layout may use generic child rows keyed by allowed quantile
level, but the domain transaction must require exactly one value for each of
5, 25, 50, 75, and 95 and no others. Journal, Review, Resolution, correction,
search, and timeline relationships must anchor unambiguously to the
model-appropriate complete revision.

M54B supersedes the earlier legacy-upgrade promise with Section 35.3's support
boundary. Detect unsupported legacy records before mutating an existing database;
test supported v0.7-only upgrades and rollback separately from refusal cases.
Do not delete supported rows to make a database fit a simplified schema.

Canonical data includes model and scoring identity, exact deadline, every
immutable revision and quantile, effective and recorded Resolution facts,
and every correction. Trajectory Brier, WIS, calibration, CDF interpolation,
final scoring-revision selection, and model-appropriate display summaries
remain derived.

SQLite backup continues to copy and verify the entire current database. A
restored supported backup must preserve both supported models and deterministically
reproduce their scores and search projection. A backup containing retired models
is subject to the same non-mutating refusal as a live database.

The Adaptive relational layout originated in **format version 4**. Current format 5 retains it and adds the One-Shot files specified in Section 36.5.
It preserves every historical relationship applicable to v0.7 records, with enough
explicit files or columns to preserve:

- forecast-model and scoring-contract identity;
- exact new-model Forecast Deadlines;
- Numeric value constraint;
- complete five-quantile revision values and levels;
- effective and recorded resolution times;
- effective-time corrections and their explanations;
- revision sequence and immutable timestamps; and
- the Binary trajectory versus five-quantile Numeric model/scoring boundary.

Exact Numeric values remain scaled integers paired with precision or another
documented exact base-ten form. The version-four data dictionary explains
how to reconstruct each standing Binary segment, select the final Numeric
revision, distinguish the supported scoring contracts, and interpret nulls.
The format documents the retirement of legacy-only files or columns instead of
pretending to be a format-3-compatible export. CSV remains an
analytical export, not an import or restoration format. Saved Views,
application settings, presentation preferences, derived scores, CDF points,
and search-index rows remain excluded.

The implementation should record consequential ADRs for model-version
identity and prospective exact-time/scoring semantics. It must not introduce
an ORM, migration framework, external analytics library, charting library,
web service, or new production dependency without a separately demonstrated
need.

### 35.13 Implementation history

M46-M55, including M54A/M54B/M54C, are complete. Their plans and acceptance history are in the [archived specification](archive/product-spec-through-v0.8.md#3513-implementation-milestones). Historical legacy-preservation steps are not instructions to restore retired models.

### 35.14 v0.7 acceptance criteria

v0.7 is not complete unless all of the following are true:

1. All supported v0.7 workflows and existing records retain their meaning through
   retirement and release hardening. Legacy behavior is absent after M54B rather
   than silently remapped onto supported models.
2. Legacy-only and mixed databases, unknown/mismatched identities, and unsupported
   schemas fail clearly before normal mutation in both GUI and CLI. No legacy
   record is deleted, assigned invented values, converted, or silently omitted.
3. Every new Binary and Numeric Prediction has one exact immutable Deadline
   strictly after its initial revision and commits parent, model identity,
   deadline, optional details, and first revision atomically.
4. New-model revisions are system-timestamped, strictly ordered, and rejected
   at or after Deadline; Reviews are rejected at or after Deadline and never
   split scoring.
5. Expected Resolution remains optional editable planning metadata and has no
   effect on Deadline, effective time, locking, or scoring.
6. New-model Resolution retains distinct effective and recorded times and
   uses effective time for scoring cutoff.
7. A post-effective revision remains in history but never enters a segment or
   becomes the final scoring revision.
8. A score-affecting outcome or effective-time correction is append-only,
   explained, and deterministically recomputes from immutable source facts;
   recorded-at remains unchanged.
9. `R <= t0` produces an explicit unscored record rather than a fabricated
   zero-duration result.
10. Binary Trajectory Brier uses exact standing durations, the fixed
    denominator, 0.25 neutral truncation only for `R < T`, and no synthetic
    ForecastRevision.
11. Binary Initial Brier, Final Brier, hold-initial, Updating Gain, and Active
    Forecast Fraction match their defined formulas and remain diagnostics.
12. Each eligible Binary trajectory Prediction has equal aggregate weight;
    legacy and trajectory scores are never silently averaged.
13. Each Numeric v2 revision contains exactly q05, q25, q50, q75, and q95,
    preserves exact precision, permits equality, rejects crossing, and
    enforces its value constraint.
14. Numeric creation and revision expose the fixed five quantiles, not a chosen
    confidence or legacy-model selector. No normal GUI or CLI path operates a
    retired forecast model.
15. Numeric final-revision selection is strictly before `min(R, T)` and has
    no neutral truncation or trajectory component.
16. WIS, its two interval scores, median term, boundary behavior,
    decomposition, and five-quantile-score equivalence are correct from exact
    stored values.
17. Raw WIS and Delta WIS are not averaged across heterogeneous Predictions;
    cross-Prediction update feedback uses only better/equal/worse counts or
    fractions.
18. Continuous-style calibration uses exactly the five elicited levels;
    whole-number calibration preserves strict/inclusive ties; both show
    sample size and uncertainty.
19. The CDF distinguishes elicited anchors and interpolation, handles repeated
    quantiles as jumps, invents no outer-tail distribution, and never affects
    scoring.
20. GUI and CLI create, mutate, resolve, display, and search the same canonical
    Binary trajectory and five-quantile Numeric data through shared application
    operations.
21. Dashboard, Predictions, Saved Views, tags, attention, Definition history,
    Journal history, Reviews, Postmortems, and search retain their established
    semantics for both supported models.
22. Backup, the format-4 layout retained within current format 5, migration, search repair, restart, and the
    private frozen build preserve every supported historical fact and enforce
    the documented unsupported-database boundary.
23. Tests and smoke workflows use only explicit temporary databases and never
    read or write stable or development user data.
24. The complete v0.7 application remains offline, local-first, single-user,
    and proportionate to a personal forecasting journal.
25. Retirement never performs personal database cleanup implicitly. Backup/reset
    or selective removal of disposable tests remains a separate explicitly
    authorized operation; retained v0.7 records are not collateral deletion.

### 35.15 Explicitly outside v0.7

- Persisted A/B/C admissibility classification, a mandatory attestation, or
  automated judgment of whether a user's question or policy is admissible.
- A dedicated structured Intervention Policy field or automatic policy-breach
  detection.
- Conversion of a legacy Prediction to a new model, inferred legacy
  quantiles, reconstructed legacy trajectories, or silent mixed-cohort
  aggregates.
- Numeric trajectory scoring, Binary trajectory calibration, Binary log
  score, a universal cross-question Numeric score, or causal updating claims.
- More than the fixed five Numeric quantiles, arbitrary quantile grids,
  multiple distributions per revision, a discrete PMF editor, parametric
  distribution fitting, invented outer tails, or automatic unit conversion.
- Multiple-choice, date-distribution, conditional, relational, or any other
  new forecast type.
- A Forecast Review queue, review schedule, anti-anchoring session, concealed
  prior forecast, or required forecast-writing wizard.
- Collections, structured Sources/Evidence, attachments, prediction graphs,
  reminders, background monitoring, automatic probability changes, or
  recommendation feeds.
- Semantic/vector/web search, an external service, cloud sync, accounts,
  profiles, sharing, collaboration, or telemetry.
- CSV import, JSON or Markdown export, restoration from analytical export,
  machine-readable CLI mutation API, or bulk editing.
- A new GUI framework, ORM, external search or analytics server, unnecessary
  production dependency, or infrastructure for hypothetical scale.
- Logo creation, a normal Windows installer, code signing, automatic updates,
  public binary distribution, or other packaging expansion.

---

## 36. One-Shot Prediction contract

Implemented in v0.8.0 on schema 20, with format-5 export. Adaptive remains the default. Completed M56-M60 plans and release acceptance are preserved in the archive.

This is a **v0.8.0** feature rather than a v0.7.1 patch: it introduces new durable
scoring contracts, a versioned SQLite migration, creation and Detail workflows, GUI/CLI
operations, separate analytics, and a new relational export format. It adds a mode
within the existing Binary and Numeric Prediction types; it does not replace their v0.7
Adaptive workflows or add a third forecast type. The [v0.8 One-Shot Rulebook
addendum](reckonsolve-one-shot-rulebook-v0.8.md) supplies user-facing guidance. This
section governs behavior if the addendum or older sections appear to conflict.

### 36.1 Purpose, admission, and boundaries

A **One-Shot Prediction** is one final probabilistic judgment made before the user
checks an answer that already exists and can ordinarily be revealed soon by a specified
observation, measurement, or lookup. It may ask a Binary Yes/No question or forecast one
Numeric quantity. The user may work through drafts privately; only the final values they
settled on before checking are the One-Shot forecast. Examples include estimating a
tree's height before measuring it or assigning a probability that the tree exceeds a
stated height threshold before checking the measurement.

The answer's physical state may predate the forecast. For this mode, *reveal* means the
user first checked the previously unknown answer using the chosen source or method; it
does not mean the quantity first came into existence. This is a deliberately different
contract from Section 35's `R = earliest fixed and ascertainable` rule and `R <= t0`
exclusion. Those exact-time rules continue to govern Adaptive Predictions only.
One-Shot is for observational uncertainty, not goals, controllable results, general
future-event forecasts, or a way to avoid a Deadline on an ongoing question. “Soon” is
guidance, not a hard elapsed-time or scoring limit.

The source and measurement convention should be considered before looking. **Background**
is visible and optional, and encourages recording the context and checking method; the
application does not require boilerplate for a simple question. A material post-answer
change to the target, threshold, unit, measurement method, source of truth, or answer
convention does not become a transcription correction. Resolve against the original
meaning when possible; otherwise preserve the record as Invalid and create a new
Prediction. One-Shot records remain subject to the Rulebook's observational and
non-intervention principles.

### 36.2 Durable model, recorded history, and time

Each One-Shot Prediction has one immutable mode/model and scoring-contract identity,
separate from both Adaptive cohorts and the retired legacy identities. The Binary
forecast is one whole-number Yes probability from 0% through 100%. The Numeric forecast
uses the same exact fixed unit, precision, continuous-style or whole-number constraint,
and ordered q05/q25/q50/q75/q95 values as the supported v0.7 Numeric representation. It
has **no Forecast Deadline** and no ordinary revision or Forecast Review operation.
Draft changes before the user commits the original forecast are not revisions. The first
canonical forecast statement and all initial details are saved atomically.

Reckonsolve records its own immutable entry instant automatically. It must never present
a later transcription from a phone note as though Reckonsolve itself had recorded the
forecast before the answer. The form asks when the user finalized the forecast and when
they checked the answer; both reported times may be approximate or left blank. An
optional note may describe when the user started thinking. Preserve a reported date and
wall-clock minute as entered, visibly labeled as user-reported, rather than converting
it into a falsely exact UTC event instant. An explicit offset, if supplied, remains
documentary context. These times are not revision timestamps, eligibility cutoffs, score
inputs, or proof of an external commitment. Equal minute-level times are allowed; the
application never invents seconds to order them. The user is responsible for entering
only a forecast settled before they checked the answer; choosing One-Shot makes that
meaning clear without a mandatory evidence upload, precise clock time, or separate
attestation questionnaire.

The answer and its app-recorded entry instant remain distinct from the optionally
reported reveal time. A One-Shot entered after the answer is known may save its initial
forecast and answer in one transaction; a One-Shot entered before checking may save
without an answer and add it later. The first path does not create a fictitious in-app
forecasting interval or backdate the canonical entry instant. The second path uses the
app's actual entry time for its audit trail but does not gain Adaptive updating or
trajectory scoring. Neither path requires an exact elapsed duration, and the existence
or absence of reported times cannot alone make an otherwise valid One-Shot score or fail
to score.

The original forecast statement, original answer when present, original reported
metadata, and system entry instants remain recoverable. **Correct transcription** is
an append-only, timestamped before/after correction of a copied forecast value,
answer, or reported time. It changes the effective displayed fact and recomputes its
one-shot score. It never updates or deletes the original statement, creates a forecast
revision, or claims that the user made a new forecast before reveal. A correction note
is optional; the
before/after values, correction action, and app time are mandatory audit facts. Question
and previously saved Resolution Criteria clarifications retain protected Definition history; a material
target change follows the Invalid/new-Prediction rule. Corrections of optional prose
keep the existing transparent text-history discipline. Both entry and correction
transactions are atomic and reject stale context.

### 36.3 Creation, Detail, and lifecycle

New Prediction continues to open on the current Adaptive form. A prominent
**One-Shot** action opens a tailored screen using the existing Binary or Numeric input
controls. Required fields are Question and the type-appropriate forecast values, plus
unit, precision, and value constraint for Numeric. The answer is optional at creation.
Optional rationale, Background, tags, reported times, and other established supporting
metadata remain available without obscuring the forecast. Following the user's M57
interface review, Background, Rationale, and Tags are visible in that order within the
Forecast card, immediately after the forecast's reported-time controls and above Include
the answer now, with no More details expander. Background holds both context and the
checking method; no separate How I will check the answer / Resolution Criteria field is
offered for new One-Shots. It uses the existing Background metadata field and editing
rules, without duplicating its text into Resolution Criteria. The Question placeholder
is What did you predict? Background asks for context and how the answer will be checked,
while Rationale asks what led to the prediction. Advice to choose the source or measurement
convention before looking belongs in the Rulebook, not in the form placeholder.
Expected Resolution is not offered in One-Shot creation or editing, including
the CLI; any value already stored is preserved as historical metadata.
Both creation modes use the same page background and card placement, with reciprocal
top-right One-Shot / Adaptive switches. Switching modes retains unsaved drafts.
The user-approved name **Adaptive** replaces With Deadline / Deadline-based in current
presentation. Adaptive forecasts allow revisions and Reviews until their permanent
Forecast Deadline. This is presentation terminology only: the immutable model/scoring
identities, Deadline rules, and stored `deadline` mode retain their meaning. CLI `list`
and `search` accept `--mode adaptive`; `--mode deadline` remains a compatible alias.
Adaptive New Prediction also supplies optional Background and Resolution Criteria
placeholders explaining context and how the question will be settled. These prompts are
placeholder text only and are never saved as user content.
Reported times use separate date and time controls: a calendar date picker defaults to
today when enabled, beside one segmented hh:mm AM/PM time field. Type hours, Tab,
minutes, Tab, then A or P; Shift+Tab goes backward and Up/Down adjusts the selected
section. Clicking a section permits replacing it. Valid one- or two-digit entries stay
in the section until Tab, so typing 7, Tab, 30, Tab, P produces 7:30 PM without skipping
minutes. An entry above the section's maximum is bounded and advances to the next
section (for example, hour 13 becomes 12 and selects minutes); the field never stores
an invalid hour/minute. The 12-hour format maps 12 AM to midnight and 12 PM to noon.
Time defaults to the current local minute when first enabled. An
Approximate time choice and optional explicit offset context remain available. Reported
times start unset until Record date and time is checked, and remain documentary wall
times, including during repeated or nonexistent local hours.
Date controls leave room for the complete displayed date, including the four-digit year.
Shared date/time and dropdown styling keeps the arrow inside the rounded field outline.
Any previously saved Resolution Criteria remains available in Detail and metadata
editing with its established protected Definition history; no existing text is deleted
or combined with Background. A form with an answer
shows no Brier, WIS, or score-driven suggestion before Save. Cancel and validation
failures create no partial forecast or answer. Successful creation with an answer goes
directly to Resolved Detail. Creation without an answer goes to **Waiting for answer**
Detail.

Waiting for answer is a One-Shot presentation of the existing nonterminal state, not a
new canonical lifecycle state. It offers **Add answer**, permits ordinary Journal and
metadata work under established safeguards, and allows Invalidate. It never offers
Revise, Forecast Review, a Deadline editor, or Needs Attention based on forecast
staleness. One-Shot does not use Expected Resolution or Ready to Resolve planning.
Once answered, it is Resolved and retains the
existing Postmortem, Skip Postmortem, terminal correction, and guarded
deletion/invalidation behavior where applicable. One-Shot Detail keeps Question,
forecast, tags, selectable notes, original/effective facts, correction and Definition
history, Journal history, terminal facts, scorecard, and reflection. Its language omits
probability history as an updating path, initial-versus-final comparisons, trajectory
timing, and “keep current forecast” actions.

The One-Shot Timeline uses the same Journal-card pattern as Adaptive Detail:
each entry appears once at its original recording position with its current corrected
text. An unchecked Edit history control reveals the original and earlier versions;
matched search results for superseded Journal text open that history and highlight the
matching version. Journal corrections remain append-only and do not create forecast
updates or separate top-level Journal events.

The one-shot correction action is available after Save, including after Resolution, so a
user can correct a copied value or measured answer. The current scorecard uses the
latest effective corrected forecast and answer, while Detail and CLI `show` keep the
original and every correction inspectable. A correction is an audited repair to the
transcription, not an unmarked edit to history or an opportunity to add a new
retrospective forecast.

### 36.4 Individual scores and separate analytics

Every eligible Resolved One-Shot contributes at most one observation. Binary uses
ordinary `Brier = (p - y)^2` for its one effective probability and Yes/No answer. It has
no standing durations, neutral truncation, Trajectory Brier, hold-initial
counterfactual, or Updating Gain. Numeric uses the existing exact five-quantile WIS
formula on its one effective distribution and actual value. It has no cutoff-based
revision selection, Numeric trajectory score, Initial/Final/Delta WIS, or updating
direction. Missing answers and Invalid Predictions have no score. User-reported times
and the later app-entry time never enter either score. No reported-time comparison
substitutes for the user's declaration that the forecast preceded checking the answer.

Analytics adds a **separate combined One-Shot view** regardless of whether the answer
was entered with the forecast or later. Its Binary section shows resolved count, mean
ordinary Brier, and the established probability calibration presentation. Its Numeric
section reuses the five elicited-level and 50%/90% interval calibration rules, with
continuous-style and whole-number results separate, count and uncertainty visible, and
exact-unit filtering retained. One-Shot Numeric WIS is a per-Prediction score, not a
cross-question mean; raw WIS is never pooled merely because unit labels match. One-Shot
and Adaptive records never share a score mean or calibration denominator.
Individual Detail and export distinguish app-recorded times from optional user-reported
times; no phone-versus-app aggregate split, source selector, or filter is required.
Analytics should briefly note that externally transcribed results rely on the user's
record and that selectively entering exercises can bias apparent calibration; this is
interpretation guidance, not a proof or attestation flow.

The Analytics **Prediction mode** selector defaults to **Adaptive** and offers
**One-Shot**. Forecast type and tag filters apply within the selected mode; choosing
Numeric enables the exact-unit filter. Binary bins remain 0–9%, 10–19%, through
90–100%, with count, mean forecast, observed Yes frequency, and a pointwise 95% Wilson
interval for that frequency. The interval describes observed frequency, not uncertainty
in mean Brier. Empty bins have no invented means or uncertainty bounds. Numeric tables
retain the established pointwise Wilson intervals, inclusive interval endpoints, and
strict/inclusive whole-number tie bands. Every chart has a text-table alternative.

### 36.5 Retrieval, interfaces, compatibility, and portability

Dashboard, Predictions, search, Saved Views, tags, and Detail include supported One-Shot
records rather than silently omitting them. Rows show Binary/Numeric type, One-Shot
mode, current effective forecast, Waiting for answer or terminal state, and relevant
attention labels without a fabricated Deadline. One-Shot Waiting for answer badges use
the shared yellow warning tone in Predictions (including search results) and Dashboard;
Needs Postmortem uses the blue informational tone, and Resolved retains its green
success tone. An explicit mode filter lets users find One-Shot or
Adaptive Predictions and may be saved dynamically; date filters do not
invent a Forecast Deadline for One-Shot. Search keeps grouped text provenance and
indexes effective text and transparent superseded corrections under existing repair
rules, not numeric values or scores as prose.

The CLI offers interactive One-Shot Binary and Numeric creation with an optional answer
in the same command, later `resolve`, and type-aware `list`, `search`, and `show`. The
CLI and desktop share application operations, canonical validation, atomic transactions,
and scoring. `revise` and `review` reject One-Shot clearly; Journal and ordinary
supported lifecycle commands remain model-aware. As with the existing desktop-only
terminal-correction workflow, desktop **Correct transcription** and CLI read-only
correction history are sufficient for v0.8; no new CLI correction or metadata command is
implied. Both launchers enforce the closed supported contract set before any migration
or derived repair.

Schema version **19** adds One-Shot model/scoring pairs, optional reported-time
facts, and append-only forecast/answer transcription corrections while preserving every
supported schema-18 row and all earlier canonical history. Do not reuse the retired
`binary-final-v1` identity or make old legacy archives loadable. Existing valid
v0.7-only archives must upgrade without changing their Deadline, revision, resolution,
score, tag, search, or Saved View meaning. Legacy-only, mixed-with-legacy, unknown, and
mismatched archives continue to fail without mutation. SQLite backup remains the
complete recovery artifact. Relational CSV advances to **format 5** to export One-Shot
identity, original/effective values, reported versus app times, correction chain, and
data dictionary; it remains analytical, not restorable. M60 replaces the earlier
format-4 refusal with complete format-5 export. The existing format-4 files retain their
column layouts. Three additional files provide `one_shot_original_facts.csv`,
`one_shot_effective_facts.csv`, and `one_shot_corrections.csv`. These retain the original
forecast and first answer, app-entry instants, optional wall-minute reports with
approximation and offset context, and every correction's complete before/after values,
sequence, note, and app timestamp. The effective snapshot is explicitly derived, not a
second scored observation. Shared forecast, resolution, Journal, Definition, tag, and
Postmortem files retain their original relationships. Empty archives still export all
headers. One consistent checked read produces each ZIP; failures preserve an existing
destination. The dictionary explains later-answer replay without treating an earlier
correction's blank answer as deletion of a later original answer.

The user-approved M58 amendment adds schema version **20** solely to retain an optional
`deadline` or `one_shot` mode in each dynamic Saved View. Existing views migrate with a
null mode, meaning All modes; their names, tags, other filters, and dynamic membership
remain unchanged. The migration is atomic and does not alter Prediction history,
scoring, or the existing export layout.

No mobile app, synchronization, note import, attachment system, proof of phone-note
authorship, web service, new forecast type, or new production dependency is part of this
contract. v0.7 release notes and historical Rulebook promises remain descriptions of
v0.7; this section prospectively adds the One-Shot exception without reconstructing an
older Prediction.

### 36.6 Implementation history

M56-M60 are complete and manually accepted where applicable. See the [milestone plans](archive/product-spec-through-v0.8.md#366-proposed-implementation-milestones), [release acceptance](archive/releases/v0.8-acceptance.md), and [validation evidence](archive/releases/v0.8-validation.md). New work requires separate authorization.

### 36.7 v0.8 acceptance criteria

1. Default New Prediction still creates the current Adaptive contract; the
   One-Shot action opens its tailored Binary/Numeric form and never stores a fabricated
   Deadline.
2. One-Shot forecast and optional answer save atomically; cancel, invalid input, lock
   contention, or stale context leaves no partial or rewritten history.
3. The app distinguishes its own entry time from optional user-reported forecast and
   reveal times. Approximate, missing, or equal-minute reported times do not gate or
   alter one-shot scoring.
4. A saved one-shot forecast has no ordinary revision or Review operation; Waiting for
   answer offers Add answer, and Resolved/Invalid behavior retains established
   historical safeguards.
5. Correcting a transcription preserves the original and every correction, changes the
   effective score deterministically, and cannot silently redefine the question.
6. Binary individual and aggregate scores use one ordinary Brier observation; Numeric
   individual score uses one exact five-quantile WIS and aggregate calibration never
   pools raw WIS. Neither mode enters Adaptive aggregates.
7. GUI and CLI create, answer, retrieve, and show the same one-shot record. Search,
   Saved Views, tags, Dashboard, Postmortems, backup, and format-5 CSV include it
   without data loss or unsupported-cohort omission.
8. Supported v0.7 history and scores survive schema-19/20 upgrade unchanged; retired or
   malformed archives remain safely refused. Tests and private-build review use only
   disposable databases.

### 36.8 Explicitly outside v0.8

- General deadline-free ongoing forecasting, multiple committed One-Shot revisions,
  Forecast Reviews, or time-weighted One-Shot scores.
- Verified external timestamping, evidence attachments, automatic import from phone
  notes, mobile or cloud clients, sync, and social sharing.
- Automatic policing of whether the user had seen the answer, mandatory proof, or
  mandatory measurement prose.
- Reinstating retired Binary-final or interval-v1 runtime models, converting them to
  One-Shot, or merging their aggregates with supported cohorts.
- Numeric trajectory scoring, pooled raw WIS, extra quantiles, additional forecast
  types, or a universal skill score.

---

## 37. Instruction to coding agents

Before implementing a milestone:

1. Read this specification fully.
2. Identify the milestone and affected invariants.
3. Inspect the existing code and tests.
4. Propose or implement the smallest coherent vertical change.
5. Add tests for historical integrity and domain behavior.
6. Verify the user-visible workflow end to end.
7. Report any product ambiguity instead of inventing a scope-expanding feature.

The guiding rule is:

> Let the user change their mind freely, but never let the application rewrite the fact
> that they used to think something else.
