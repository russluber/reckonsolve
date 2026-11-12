# New Prediction and Prediction Detail verification — 2026-11-11

This records the unreleased second redesign slice on `ux-redesign`, based on
`671d50c` plus the implementation changes subsequently committed as `d303a50`.
It records automated evidence and the qualified user review below, not complete
Detail acceptance or a release. The package version remains 0.8.0.

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

## Reported user review and follow-up

The user reported checking the supplied journeys at `d303a50`, finding them usable
and committing/pushing the public and private checkpoints. They explicitly described
Prediction Detail features and fixtures as incomplete and the presentation as rough.
This accepts the reviewed paths at that source; it does not close the full Detail
contract, fixture coverage or the separately unreported Windows scaling/focus matrix.

The user requested a stronger Journal page-title hierarchy, cleaner eligible-action
layout and Current revision near Timeline. Follow-up presentation work raises the
shared page-title role above Questions, removes gaps left by hidden controls, and
places the jump/order controls in a persistent, wrapping Timeline header. Native
recheck was subsequently accepted by the user, who explicitly found Current revision
beside Timeline more intuitive. This accepts that tuning; the preceding 1,110-test
run applies to the earlier implementation, not these later changes.

The follow-up working tree based on `d303a50` passed **1,112 tests in 269.77 seconds**,
plus Ruff check/format, public/private documentation links, reference preservation
and whitespace checks. New regressions verify the actual Journal title/Question
hierarchy in both palettes, both Adaptive jump targets and history scrolling,
narrow control wrapping and gap-free Resolved action rows. Offscreen captures
inspect both palettes at 1100 × 850 and narrower writing layouts, including
760 × 520 fallback scrolling with Commit/Cancel reachable. Native Windows scaling
remains separate from this scoped user acceptance of the tuning.

The starter review profile is deliberately limited: it does not seed waiting Numeric
One-Shots, every Invalid mode/type, audited transcription/Journal/Definition correction
histories, long revision chains, or current-versus-earlier-scored forecast examples.
Automated tests cover additional cases, but they do not make those examples available
in the starter visual profile or establish full feature completeness. The remaining
Detail feature/fixture audit stays open before closing this slice.

## Calibration appearance repair

After accepting the hierarchy/Timeline refinements, the user reported a blacked-out
Trajectory Binary Final-Probability Calibration graph/table in light mode. The
reproduction confirmed that the comparison retained its previous surface while
text switched themes. Its palette handler read colors during Qt's propagation
and repolish pass; a coalesced next-event-loop refresh now reads the final surface.
This repairs the existing Performance adapter, without implementing its later
report redesign or changing analytics, counts, filters or scoring.

Four native-widget regressions failed before the repair and passed afterward.
They start in each explicit appearance, switch repeatedly in both directions,
and cover stacked and paired layouts at 900/1400 logical pixels. Assertions inspect
painted graph/table backgrounds, text contrast, bins, counts and unchanged exact
snapshots using an injected temporary database. All 52 focused analytics/chart/
workspace checks passed. Fresh actual Qt light/dark captures were inspected;
captures and reproduction helpers remain ignored with the other review artifacts.
This offscreen evidence does not establish the user's native recheck of the repair.

The final combined working tree passed **1,116 tests in 258.97 seconds**, with no
failures, errors or skips. Ruff check/format, public/private documentation links,
reference preservation and both whitespace checks passed. Storage, analytics,
migrations, dependencies and personal data remain unchanged. The earlier test runs
above retain their original artifact scope; this run covers the accepted hierarchy/
Timeline tuning together with the calibration repair.
