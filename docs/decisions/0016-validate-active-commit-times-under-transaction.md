# 0016: Validate active commit times under transaction

- Status: Accepted
- Date: 2026-09-10

## Context

M47 makes a new Binary Deadline an exact instant. A dialog can remain open
past that instant, and a second process can hold SQLite's write lock while a
save waits. Checking the clock only before transaction acquisition can admit
a revision or Review after its forecasting window has closed.

## Decision

Keep the clock injectable and presentation-independent. The application
validates the request and reviewed context; the Binary repository samples
the same clock again inside its write transaction for prospective creation,
revision, and Review. The actual saved revision timestamp is the transaction
sample. Deadline and strict revision-order validation use that timestamp.
Deletion also rechecks exact eligibility under transaction access.

Use the stored contract for lifecycle dispatch. Legacy date-only locking and
revision behavior remain unchanged. A late or regressed prospective revision
fails without inserting a row, adjusting an earlier timestamp, or manufacturing
a monotonic replacement time.

Desktop entry combines a native date/time picker with an explicit UTC offset.
Qt uses a UTC carrier for the wall-clock fields so it does not silently resolve
a local DST ambiguity. The supplied offset determines the UTC instant; it is
not a persisted time-zone rule. CLI entry requires the offset directly in the
ISO timestamp. Both paths reuse the same application validation.

## Consequences

- An open dialog or write-lock wait cannot bypass the exact cutoff.
- Tests can advance or regress the clock independently of GUI event timing.
- The user must check the offset for the intended date, including daylight
  saving time; the UI explains this beside the control.
- No timezone database dependency, new schema migration, backdated revision
  interface, or legacy timestamp reinterpretation is needed.

## Alternatives considered

- **Validate only at dialog opening or application preflight:** misses stale
  dialogs and lock waits.
- **Force monotonicity by adding a microsecond:** invents history and may
  cross the Deadline.
- **Implicit local-time conversion:** cannot unambiguously identify repeated
  DST wall-clock times and can normalize missing times without user intent.
- **Date-only cutoff for the new model:** loses the sub-day commitment that
  the approved scoring contract requires.
