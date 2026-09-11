# 0017: Derive trajectory scores from immutable history and effective terminal facts

- Status: Accepted
- Date: 2026-09-10

## Context

M48 enables Binary trajectory Resolution. An outcome may become knowable before
it is recorded, and an audited correction to that effective instant can change
which revisions score. The legacy captured-final revision cannot express this
selection. Terminal text must also remain searchable and Postmortem completion
must follow corrected text, including an intentional clearing of that text.

## Decision

Load the stored contract, complete revision history, original Resolution, and
trajectory correction chain in one SQLite transaction. Pure analytics normalizes
instants to UTC, measures integer microsecond durations, and uses standard-library
`Fraction` arithmetic for segment losses, neutral remainder, and all diagnostics.
Only presentation rounds the results. No calculated score or synthetic neutral
revision is stored. The original captured revision remains immutable recording
context; it is not the new cohort's final scoring authority.

Resolution samples the injected clock under write access. An explicit choice to
use recording time takes effective time from that same sample. A source time is
validated against recorded-at. Corrections append to the schema-16 trajectory
chain, keep original recorded-at, require a reason for outcome/time changes, and
derive eligibility again. GUI notes-only edits retain undisplayed timestamp
precision; CLI accepts explicit offset-bearing instants.

Schema 17 adds the read-only `binary_resolution_history_rows` union of the two
Binary correction tables for terminal-text search and Postmortem queries. It
adds the missing dirty-search trigger, updates the Postmortem-completion guard,
and dirties any pre-existing trajectory corrections for projection refresh.
Neither historical migration 16 nor any canonical row is rewritten. Scoring
does not use this union: it dispatches explicitly by stored model identity.

## Consequences

- Delayed entry and later corrections cannot erase or backdate a revision.
- Revisions at/after the effective cutoff remain visible but excluded.
- `R <= t0` produces an explicit unscored record, not a neutral score.
- Search and Postmortem completion see current corrected text in either cohort.
- A search refresh failure rolls back the accompanying terminal correction.
- Legacy aggregates exclude trajectory records; separate new-cohort analytics
  remain M49. SQLite backup is complete; the existing CSV staging guard remains.

## Alternatives considered

- **Reuse captured-final Brier:** ignores standing durations and effective time.
- **Rewrite the captured revision after correction:** mutates original facts and
  makes a derived pointer compete with canonical timestamps.
- **Store neutral forecast rows or cached scores:** invents history or creates
  redundant state requiring invalidation after every terminal correction.
- **Merge the canonical correction tables:** needlessly changes legacy audit
  storage when only the terminal-text read shape is shared.
- **Edit migration 16 in place:** fails to upgrade databases already at that version.
