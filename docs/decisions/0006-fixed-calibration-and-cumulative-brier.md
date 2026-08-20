# 0006: Use fixed calibration bins and cumulative Brier performance

- Status: Accepted
- Date: 2026-08-20

## Context

Milestone 10 must turn immutable Resolution facts into focused personal forecasting analytics. The product requires exactly one final eligible forecast per resolved Prediction, a reliability diagram with discoverable sparsity, and a clearly labeled performance series over resolution time. It intentionally left the exact calibration bins and cumulative-versus-windowed trend unresolved.

The existing Resolution record already captures the transaction-current ForecastRevision chosen for scoring. Analytics therefore needs no new canonical table or migration. It needs deterministic read and calculation rules that remain honest for small data sets and stable when a tag filter is applied.

## Decision

The scoring data query joins each valid Resolution directly to its captured `scoring_revision_id`. Open, Locked, and Invalid Predictions do not enter the source. Each included Prediction and Resolution is validated to contribute once. Scores, calibration aggregates, and trend points are derived on demand rather than persisted.

Calibration uses ten fixed whole-number bands: `0-9%`, successive ten-point bands, and `90-100%`. The horizontal coordinate of an occupied bin is the actual mean forecast in that bin; the vertical coordinate is its observed Yes frequency. Empty bins contribute a visible zero count but no invented point. Fixed bands do not move under tag filtering.

Brier performance over time is the cumulative mean ordered by canonical Resolution instant, with Resolution identifier breaking timestamp ties. Every point includes all scored Predictions in that filtered set through that resolution. The UI labels the series **Cumulative mean Brier by resolution time**, says lower is better, and warns that movement does not itself establish improving skill.

All, single-tag, Brier summary, calibration, and trend views are calculated from one common source and filter. Native `QPainter` widgets consume the calculated values; they do not select observations or calculate scores.

## Consequences

- Historical forecast revisions are never mistaken for separate resolved observations.
- A manually or accidentally appended later revision cannot displace the Resolution's captured scoring revision.
- Calibration bands remain comparable between All and tag-filtered views.
- Actual bin means avoid the visual bias of plotting an arbitrary midpoint.
- Visible counts make early personal data sparsity explicit.
- The cumulative series works from the first resolution and needs no arbitrary window size, but it reacts more slowly as history grows.
- Analytics can be recomputed from canonical facts after restart, backup restoration, or future calculation corrections without migrating stored aggregates.

## Alternatives considered

### Score every ForecastRevision

Rejected because it would treat repeated belief updates as independent outcomes and violate the exactly-one scoring invariant.

### Select the latest revision during each analytics query

Rejected because Resolution already preserves the reviewed scoring revision. Re-deriving from latest sequence could make historical scores drift if later or malformed data appeared.

### Quantile or adaptive calibration bins

Rejected for v0.1 because boundaries would change with the data and selected tag, making comparisons harder to interpret.

### Five wider fixed bins

Rejected because they conceal more probability detail. Ten bins retain familiar ten-point interpretation while explicit counts disclose sparsity.

### Plot bin midpoints

Rejected because the midpoint can differ materially from the actual forecasts represented and can make a calibrated group appear off the reference line.

### Rolling Brier window

Rejected for the first personal-data implementation because a window size would be arbitrary, early data would require special handling, and observations outside the window would disappear from the visible measure.

### Persist analytical summaries

Rejected because the canonical Resolution, outcome, captured revision, and tags are already sufficient, and stored aggregates would introduce synchronization and migration risks without a demonstrated performance need.
