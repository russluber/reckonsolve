# 0020: Resolve local deadlines without silent clock changes

- Status: Accepted
- Date: 2026-09-22

## Context

M54C removes the required-field checkbox and routine manual UTC-offset entry from
desktop creation. A future deadline needs the offset at its selected date, which
may differ from today's. Windows local-time conversion must also distinguish
nonexistent spring-forward times and repeated fall-back times.

## Decision

Keep the native editor's wall-clock fields in a UTC carrier, then resolve them
through `QTimeZone.systemTimeZone()` using the existing PySide6 dependency. Check
the before/after transition candidates against the original date and minute:
zero matching candidates is a gap; two distinct candidates require explicit
selection; one candidate is unambiguous. Show the resulting zone and offset.

Retain an explicit-offset override. Convert only the selected minute to an aware
UTC datetime and send it to the existing atomic creation operation. Shortcuts
choose local calendar days at 23:59:00 when clicked; they never recompute on save.
The shared draft stays unset until deliberate selection and is not persisted.

## Consequences

Ordinary creation needs no offset arithmetic. DST gaps are never shifted silently
and repeated times never receive a guessed occurrence. Platform zone rules remain
an input to presentation; stored UTC deadlines are immutable and unaffected by
later zone changes. Injectable clocks and zones cover these cases offline.
Effective-resolution input and CLI prompts keep their existing explicit offsets.

## Alternatives considered

- Today's fixed offset is simpler but can misinterpret future deadlines.
- Directly using a local-zone date/time editor can normalize nonexistent input
  before the user sees an error.
- Adding another timezone dependency is unnecessary while Qt already supplies
  Windows timezone rules and explicit transition resolution.
