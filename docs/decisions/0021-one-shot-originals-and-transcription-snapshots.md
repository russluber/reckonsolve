# 0021: Preserve One-Shot originals with separate transcription snapshots

- Status: Accepted
- Date: 2026-09-26

## Context

Product-spec Section 36 introduces a single forecast made before checking an
already-existing answer, often transcribed later. Its Brier or WIS must not depend
on an invented forecasting window or on the accuracy of reported times. Copying
mistakes may be corrected without overwriting the original forecast or answer.
M56 is the internal foundation; public workflows are staged in M57–M60.

## Decision

Schema 19 adds two closed pairs:

| Model | Scoring contract |
|---|---|
| `binary-one-shot-v1` | `binary-one-shot-brier-v1` |
| `numeric-one-shot-5-v1` | `numeric-one-shot-wis-v1` |

Both require a null exact Deadline and no legacy date-only Deadline. They do not
make retired `binary-final-v1` or interval-v1 archives supported.

Reuse `forecast_revisions` and `numeric_quantile_revisions` for exactly one
sequence-one original forecast. Numeric definitions retain their immutable unit,
precision, and value constraint. Reuse the original type-specific Resolution
tables for an optional answer; their revision references identify the original
forecast, and `resolved_at` is the app entry instant. One-Shot never stores an
effective-resolution instant. SQL guards prevent additional forecasts, Reviews,
deadline assignment, original-row replacement, and contradictory timing facts.

`one_shot_forecast_times` and `one_shot_answer_times` retain the original reported
wall-clock minute, approximate flag, and optional offset in minutes. A blank
report is an explicit row with null wall time and offset and a false approximate
flag. These rows never replace the system timestamps on forecast and answer rows.
No UTC conversion or chronological comparison is applied to reported times.

`one_shot_corrections` is a per-Prediction append-only sequence of complete,
relational before/after snapshots. Each snapshot contains the one type-appropriate
forecast, optional answer, reported times, Resolution notes, and Postmortem. Each
correction has its own system instant and optional note. SQL checks require a
changed snapshot, current before values, contiguous sequence, unchanged forecast
type and answer presence, valid exact quantities, and whole-number integrality.
Original rationale remains on the immutable forecast; Question and Resolution
Criteria keep their separate Definition-history contract.

Two read-only SQL views expose original and effective values. Effective forecast
fields come from the latest correction. Answer fields come from the latest
correction containing an answer, falling back to the original Resolution. This
lets a forecast be corrected while waiting, then receive its first answer without
the earlier correction's blank answer hiding it. Python independently validates
the complete correction replay before returning facts or passing compatibility.

The internal repository samples the clock under `BEGIN IMMEDIATE`. Creation with
an answer commits every row together. Later answering and corrections recheck
metadata version, correction head, answer presence, and lifecycle. Scores remain
pure derived results: exact shared Brier or the existing five-quantile WIS, with
no duration, cutoff, neutral segment, or revision comparison.

Migration 19 rebuilds only the contract table from shipped DDL and updates the
minimum affected guards. It preserves all supported rows, IDs, timestamps,
anchors, and migration history, with foreign keys enabled throughout. The whole
upgrade rolls back on failure; compatibility checks run before DDL and before
commit. Startup, normal transactions, repair, and backup retain the whole-archive
refusal of retired, unknown, missing, or mismatched contracts.

## Consequences

M56 exposes no application, GUI, or CLI One-Shot creation path. Its internal
repository explicitly opts into One-Shot transactions. Ordinary workflows refuse
an archive containing internal One-Shot records until their complete integration
lands, rather than silently omit or misinterpret them. This temporary workflow
guard is separate from the expanded storage compatibility check. SQLite backup
can already retain and reopen the complete internal record. CSV format 4 explicitly
refuses such an archive until M60 supplies format 5.

Search's existing projection is not yet a complete One-Shot retrieval contract;
M58 owns correction-text projection and ordinary archive/search integration.
M57 owns user-facing correction and answer operations. Neither milestone should
route One-Shot through a deadline scorer or treat a correction as another forecast.

## M57 implementation follow-up

M57 replaces the temporary whole-archive workflow refusal with explicit individual
One-Shot operations and basic effective archive reads. All transactions still validate
the closed contract set before work and before commit. Writes return their complete
Detail snapshot from the write transaction; a failed follow-up read cannot obscure a
successful save. The foundation repository methods retain their record return values.
Search projection version 2 follows One-Shot terminal prose corrections and can rebuild
the derived index; full retrieval and reflection integration remain M58. The two
deadline-based aggregate sources explicitly exclude One-Shot. CSV format 4 continues
to refuse these archives; SQLite backup remains complete.

## M60 export follow-up

M60 follow-up: format-5 export replaces the temporary format-4 refusal. Original and
effective facts plus full correction snapshots are explicitly labeled; shared revision
and resolution files retain the immutable originals and audit anchors. Exported reported
times remain wall minutes with documentary flags/offsets. The same compatibility gate
validates the source before export. This adds no canonical table or score authority.

## Alternatives considered

- Reusing the retired final-Binary identity would conflate incompatible history
  and weaken whole-database retirement checks.
- Updating the original forecast in place would erase transcription history.
- Appending ordinary revisions would imply repeated forecasting and expose
  One-Shot to trajectory and initial/final calculations.
- Separate original forecast and answer tables would duplicate established exact
  values, lifecycle guards, and shared-history anchors unnecessarily.
- A fabricated Deadline or UTC-converted reported time would introduce false
  precision and the wrong eligibility rules.
- Storing scores or mutable effective values would create another authority that
  could disagree with the original and correction chain.
