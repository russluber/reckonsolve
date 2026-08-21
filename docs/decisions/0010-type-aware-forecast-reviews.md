# 0010: Preserve type-aware Forecast Reviews as immutable revision anchors

- Status: Accepted
- Date: 2026-08-20

## Context

A Forecast Review must prove that the user deliberately reconsidered the current Binary probability or Numeric interval and retained it unchanged. It must refresh Needs Attention without masquerading as a forecast change, chart observation, or scoring observation. The record also has to remain trustworthy when another application instance changes the forecast or proposition while a Review dialog is open.

## Decision

Store Reviews in one `forecast_reviews` table. Each row contains a stable identifier, Prediction identifier, canonical UTC timestamp, optional note, and exactly one composite foreign key to either a Binary or Numeric ForecastRevision owned by that Prediction.

The application carries the reviewed revision identifier and metadata version. The repository rechecks both, derives Open eligibility against the current local date, and inserts the Review inside one `BEGIN IMMEDIATE` transaction. Database triggers independently require an Open persisted Prediction and its current type-appropriate revision. Saved Reviews reject update, direct delete, and identity replacement; deliberate parent deletion may cascade.

Timeline queries join a Review to its retained revision context. Dashboard freshness uses the later of the latest revision or Review timestamp. Revision lists, history charts, and analytics sources do not query Reviews.

## Consequences

Reviews cannot rewrite or inflate forecast history and cannot affect resolution scoring. A stale Review dialog fails visibly rather than recording reconsideration of a forecast or definition the user did not review. Multiple Reviews of the same still-current revision remain valid separate acts. A saved Review makes a Prediction meaningful history and therefore ineligible for the normal untouched-record Delete flow.

The table has two nullable revision columns plus an exclusive-or constraint. This is slightly more verbose than separate type tables, but keeps one lifecycle, immutability, freshness, and export concept for both forecast models. Milestone 20 must include this table and both revision relationships in the documented CSV bundle.

## Alternatives considered

- **Append an unchanged ForecastRevision:** rejected because it would fabricate a forecast change and add false chart and scoring-selection history.
- **Treat a Journal entry as a Review:** rejected because ordinary reasoning does not necessarily mean the forecast was deliberately reconsidered, and Journal activity must not reset Needs Attention.
- **Store only a last-reviewed timestamp on Prediction:** rejected because it would overwrite prior Reviews and lose their exact forecast context and optional notes.
- **Use separate Binary and Numeric Review tables:** rejected because the lifecycle and immutable record are identical apart from the revision target, and one constrained table keeps reads and future export simpler.
