# 0013: Use a rebuildable SQLite FTS5 search projection

- Status: Accepted
- Date: 2026-08-27

## Context

Reckonsolve's v0.5 search must cover current and historical user-authored text, support ordinary words, phrases, incremental prefixes, and useful relevance, and still explain which preserved record matched. Canonical Prediction history spans several normalized tables and append-only correction chains. Flattening that history into ad hoc `LIKE` queries would make ranking weak and force every query to replay many relationships, while treating an index as canonical state would put historical integrity at risk.

The application remains a single-user, local-first program with SQLite as its canonical store. Search must add no server, network requirement, background service, or casual production dependency. A projection failure must not permit canonical history and its index to commit out of step.

## Decision

Use SQLite FTS5, supplied by the standard-library SQLite binding, for a contentful, per-fragment derived projection. One `prediction_search` row represents one searchable source fragment and stores unindexed provenance beside the indexed body: Prediction identity, source classification and record, optional correction/version and sequence, occurrence time, and whether the text is superseded. Canonical tables remain the only source of truth.

Schema version 14 adds the FTS table, a projection-version record, a vocabulary view, and a small dirty-Prediction queue. Narrow SQL triggers only mark affected Prediction identifiers when searchable canonical relationships change. They do not copy text, replay correction chains, or contain search rules. Immediately before `Database.transaction()` commits, Python projection code deterministically replaces every dirty Prediction's documents inside that same transaction. A projection failure therefore rolls back the canonical write as well.

Startup explicitly proves that FTS5 is available. It builds the projection after migration, refreshes any safely retained dirty identifiers, and fully rebuilds when the projection algorithm version changes. It also compares the complete projection with canonical replay, so an equal-sized but incorrect recovered index is rebuilt before search can report false emptiness. An explicit Settings action can discard and rebuild the derived rows without changing canonical history.

Search input is parsed as ordinary user text into parameterized FTS queries; raw FTS syntax is never accepted. Pure domain code groups fragments by Prediction and applies deterministic source-aware ranking. Effective text is searched by default, with distinct superseded documents available only when historical search is requested.

## Consequences

- Search remains offline, uses no additional package, and scales independently of the normalized read shape.
- Results retain enough provenance for later UI snippets, source labels, and historical badges.
- Canonical mutations pay the bounded cost of reprojecting each affected Prediction before commit. This is proportionate to a personal journal and simpler to reason about than incremental fragment surgery.
- The first version-14 startup must project existing history. Future projection-algorithm changes can advance the separate projection version and rebuild without a canonical schema redesign.
- SQLite backups contain the derived tables because they copy the complete database, but those rows remain disposable and reproducible. Relational CSV export does not treat them as user data.
- A Python or packaged runtime without FTS5 cannot use schema version 14 and fails with an explicit capability error rather than silently falling back to inferior or inconsistent search.
- Direct canonical SQL outside Reckonsolve's transaction boundary is unsupported; startup can safely consume a retained dirty queue, while explicit integrity checking and repair cover projection corruption.
- Complete startup verification adds work proportional to the local corpus, accepted here because the data is personal-scale and a silently wrong recovered index would violate the search contract.

## Alternatives considered

- **Scan canonical text with `LIKE` or Python substring checks:** simple for Question-only search, but increasingly expensive and poor at phrases, prefixes, ranking, and cross-table explainability.
- **Store one flattened document per Prediction:** easier to query, but loses the source and correction provenance needed for grouping, ranking, and honest historical matches.
- **Maintain FTS rows entirely in SQL triggers:** atomic, but would duplicate complex effective-value replay in SQL and make the historical rules difficult to test and evolve.
- **Refresh the projection after canonical commit:** reduces transaction time, but creates an observable stale window and lets refresh failure leave committed history unsearchable.
- **Add an external search engine or embedding service:** disproportionate for one local user, adds dependencies or network/privacy concerns, and does not improve the core historical-integrity boundary.
