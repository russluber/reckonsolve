# New Prediction and Prediction Detail verification — 2026-11-11

This records the unreleased second redesign slice on `ux-redesign`, based on
`671d50c` plus the local implementation changes. It is a verification checkpoint,
not native user acceptance or a release. The package version remains 0.8.0.

Scope: [authorized second slice](../../product-spec.md#3811-authorized-second-implementation-slice).
Structure: [architecture](../../architecture.md#9-desktop-presentation-boundary).
Repeatable review: [disposable native walkthrough](../../maintainer/development.md#new-prediction-and-detail-review).

## Implemented scope

Creation, contract-specific Detail reading, shared Timeline/interval/task components
and focused forms replace the former screen monolith, retaining compatibility
imports. Adaptive reading has committed headers and independent panes; One-Shot
reading retains the completed-exercise page. Contextual writing, draft consultation,
guarded departures, lifecycle reading and internal Definition/transcription review
use existing canonical operations. Later reflection has dedicated forms and a shared
reflection-only command preserving every other effective terminal fact.

## Automated evidence

The final working-tree run passed **1,110 tests in 238.99 seconds**, with no failures,
errors or skips. Focused
real-database checks cover contextual saves, guarded departure, retained Overview
and palette changes, long matching Journal reveal, Numeric Deadline rejection with
retained input and repeatable feedback, both One-Shot answer/reflection/repair flows,
and Adaptive reflection-only original/fact/score preservation. Existing history,
atomicity, stale/concurrent writes, scoring, compatibility, recovery and retrieval
regressions remain part of the full suite.

Ruff check/format, public/private document links, reference preservation and whitespace checks passed.
Data/domain/analytics implementations, schema 21, applied migrations, projection 3,
CSV 6 and pinned dependencies remain unchanged. No personal database was used.

## Visual evidence and limits

Actual PySide6 widgets were captured offscreen with installed Windows Segoe UI
regular/semibold/bold fonts and injected temporary databases/preferences. Inspection
covered both appearances, representative Adaptive/One-Shot/lifecycle reading,
contextual revision, inline reflection and the 760 × 520 logical-pixel baseline.
Offscreen scale factors 1.5 and 2 supplement the baseline captures; they do not
establish native Windows scaling acceptance. Short windows retain outer fallback
scrolling in addition to independent contextual pane scrolling.

Captures/XML and temporary helpers stay ignored under `build/ux-journal-implementation`.
These checks do not constitute human visual acceptance, exhaustive accessibility
testing or the final integrated redesign review. Earlier first-slice acceptance
does not accept the changed Detail forms. Performance/Settings redesign and relocation
remain separate work. No installed tool, packaging, release, staging, commit or push
was performed.
