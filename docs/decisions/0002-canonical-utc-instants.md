# 0002: Store instants as canonical UTC text

- Status: Accepted
- Date: 2026-08-12

## Context

Reckonsolve compares and orders historical events across application restarts. Those instants need one deterministic storage representation, while the single user should see times in the context of the Windows computer they are using. Date-only values such as an expected resolution date have different semantics and must not shift to another calendar day through time-zone conversion.

## Decision

Represent system-generated instants as timezone-aware Python `datetime` values. Normalize them to UTC at the application boundary and persist canonical RFC 3339 text with six fractional-second digits and a trailing `Z`, for example `2026-08-12T19:30:00.000000Z`.

The data layer parses stored instants back into aware UTC values. Presentation code converts those instants to the computer's local time when it displays them. Date-only values remain calendar dates and are not converted between time zones.

A centralized injectable clock supplies the current instant so one application operation uses one timestamp and tests never depend on the user's clock. SQLite constraints require UTC-marked timestamp text; normal writes produce the stricter canonical representation through the shared serializer.

## Consequences

- Stored instants compare and sort consistently and do not depend on the machine's current time zone.
- Tests can supply exact instants and verify stable serialization.
- Daylight-saving and local-zone conversion stay at the presentation boundary instead of changing canonical history.
- Future migrations and data-access code must use the shared serializer and parser for instant fields.
- A user who changes the computer's time zone may see a different local rendering of the same preserved instant, which is correct.
- Date-only fields require their own database representation and must not be passed through the instant serializer.

## Alternatives considered

### Store local wall-clock text

Rejected because local text can be ambiguous during daylight-saving transitions and cannot identify an instant reliably without additional zone information.

### Store Unix timestamps

Rejected because integer or floating-point epochs are less inspectable in a personal SQLite database. Canonical UTC text remains precise, readable, and naturally sortable.

### Store offset timestamps exactly as entered

Rejected for system-generated events because equivalent instants would have multiple representations and ordering would require normalization. The interface can still render the canonical instant in local time.
