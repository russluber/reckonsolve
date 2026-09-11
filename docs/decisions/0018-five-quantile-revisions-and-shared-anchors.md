# 0018: Store complete five-quantile revisions with explicit shared-history anchors

- Status: Accepted
- Date: 2026-09-11

## Context

M50 must establish Numeric v2 without interpreting old intervals as quantiles or
exposing an incomplete GUI/CLI workflow. Existing Journals and Reviews reference
either Binary or interval revisions, and Numeric Resolution references an interval.
The new cohort needs equally strong ownership and immutable-history guarantees.

## Decision

Use a dedicated immutable definition row for the value constraint and a separate
revision table with five required scaled-integer columns. Retain the parent's
fixed unit and precision. Enforce ordering, integral whole-number values, complete
changed revisions, contiguous sequences, and strictly increasing pre-Deadline
timestamps in the domain and database boundaries.

Extend shared Journal, Review, and Numeric Resolution tables with a third explicit
quantile anchor rather than weakening existing foreign keys or sharing an
unqualified integer revision ID. Exactly-one and composite ownership constraints
keep references unambiguous even when revision IDs coincide across tables.
The captured v2 Resolution anchor is recording context only; canonical scoring
selection derives from effective time and the immutable Deadline.

Rebuild the affected shared tables and their referencing correction tables in the
existing immediate migration transaction. Snapshot and copy all legacy columns
unchanged, drop children before parents, restore constraints/indexes/guards, and
check foreign keys before commit. Reuse unchanged DDL from the frozen migration
registry, not live schema text; never disable foreign keys or use writable_schema.
The legacy interval revision table and its rows remain untouched.

Pure individual WIS uses Fraction arithmetic over stored scaled integers, including
the zero terms of its decomposition. It consumes one compatible history and offers
no raw cross-question aggregation. All five quantiles, rather than interpolation
or rendered text, are the score's authority.

## Consequences

Completeness is atomic and there is no partially populated quantile revision.
Existing Journal corrections, terminal corrections, and their identifiers survive
unchanged. The migration is larger than a column-only addition because SQLite
cannot extend the existing exactly-one-anchor checks in place. Rollback and
populated-history preservation tests therefore cover the entire operation.

Public Numeric creation remains interval-v1 until M51. The foundation repository
is internal; tests use only disposable databases. M52 connects terminal workflows
to the new anchors and pure scorecard; M55 completes relational export.

## Alternatives considered

- Reuse interval columns: rejected because chosen-confidence intervals do not
  encode five elicited quantiles and legacy history must retain its meaning.
- Generic quantile child rows: possible, but unnecessary for a fixed approved grid;
  named required columns enforce completeness without deferred child-count checks.
- Duplicate Journal/Review systems: rejected to retain existing correction,
  search-provenance, and event-identity semantics.
- Polymorphic revision IDs without real foreign keys: rejected because accidental
  cross-model or cross-Prediction anchors would be harder to prevent.
