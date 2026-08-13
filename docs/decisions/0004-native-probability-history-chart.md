# 0004: Render probability history with a native Qt widget

- Status: Accepted
- Date: 2026-08-13

## Context

Milestone 6 needs one focused chart on Prediction Detail: the complete probability history of one Prediction. The chart must represent every immutable ForecastRevision, use stored time rather than revision spacing on its horizontal axis, preserve the 0% through 100% probability domain, and remain useful with only one revision. It is a presentation of forecast history, not scoring analytics.

Reckonsolve currently has no charting dependency. Although Qt Charts is present in the community PySide6 distribution, [Qt documents the module as commercially licensed or GPLv3 and deprecated since Qt 6.10](https://doc.qt.io/qt-6.11/qtcharts-index.html). Its open-source option is GPLv3 rather than LGPL; otherwise, using it requires a commercial license. [Qt explains that applications using its GPL-only open-source libraries must also be licensed under the GPL](https://www.qt.io/development/open-source-lgpl-obligations). Reckonsolve therefore avoids using Qt Charts rather than introducing licensing obligations that conflict with the intended MIT distribution or building a new feature on a deprecated API. A general plotting dependency would add substantial machinery for a deliberately narrow chart.

The visual semantics also matter. Connecting revisions with diagonal interpolation would imply that belief changed continuously between saved revisions. Spacing revisions evenly by sequence would conceal the actual elapsed time between them.

## Decision

Render the Prediction Detail probability history in a dedicated, theme-aware PySide6 `QWidget` using `QPainter` and the system palette. The widget consumes the existing `list_forecast_revisions` application query. It adds no production dependency, persistence entity, database migration, or analytics operation.

The chart uses these semantics:

- Every immutable ForecastRevision produces exactly one marker; Journal events produce none.
- The vertical axis is fixed at 0% through 100%.
- Marker positions on the horizontal axis use the actual stored instants, while labels render those instants in the computer's local time.
- Revisions connect in immutable sequence order with a step-after line: one probability remains in force until the next revision instant, where the line changes vertically.
- Equal stored instants share one horizontal position. Sequence determines connection and current-marker order.
- A backward system-clock adjustment is shown honestly: the sequence-ordered line may travel backward on the time axis rather than re-sorting history or inventing a later timestamp.
- A single revision receives symmetric time-axis padding so its marker is centered without implying another observation.
- Hover interaction is not required. The widget exposes an accessible summary, and Forecast entries in the unified timeline remain the exact nonvisual representation of revision order, timestamps, transitions, probabilities, and rationales.

This decision applies to the single-Prediction probability-history chart. It does not preselect a rendering approach for later calibration or Brier-performance charts, whose requirements may justify a different choice.

## Consequences

- Reckonsolve keeps its existing runtime dependency set and avoids using Qt Charts under either its GPLv3 open-source option or a commercial license.
- The chart follows the active Qt palette and can remain visually consistent with later application styling.
- Forecast-history semantics stay explicit and independently testable: one-revision layout, elapsed-time projection, step geometry, equal timestamps, endpoint probabilities, and regressing clocks do not depend on a third-party chart engine.
- Reckonsolve owns a small amount of axis, layout, and painting code. Rich interaction, zooming, and general-purpose chart features are intentionally absent from this first slice.
- Later analytics charts must make their own proportionate dependency and rendering decision rather than inheriting this widget by accident.

## Alternatives considered

### Qt Charts

Qt Charts would provide ready-made axes and series through PySide6, but its open-source option is GPLv3 rather than LGPL (with commercial licensing as the alternative), it is deprecated, and it is disproportionate to this MIT project's one small chart.

### An external Python plotting library

Libraries such as pyqtgraph or Matplotlib offer broader plotting features, but either would add a production dependency and packaging weight that Milestone 6 does not need. Later analytics may revisit that tradeoff against concrete requirements.

### Diagonal interpolation

A conventional line between revision markers is compact, but it falsely suggests gradual probability movement. Forecast probability is piecewise constant because only saved revisions change it.

### Equal spacing by revision sequence

Equal spacing would make dense histories easy to read, but it would violate the product requirement that the horizontal axis represent time and would hide whether revisions were minutes or months apart.

### Timestamp re-sorting or synthetic offsets

Re-sorting by timestamp could reverse the saved causal order after a clock adjustment, while jittering equal timestamps or forcing monotonic synthetic times would invent facts. Stored time controls position and revision sequence controls history order instead.
