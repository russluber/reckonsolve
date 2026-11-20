# Post-review workspace refinement verification — 2026-11-13

The [compact Journal entry follow-up](#compact-journal-entries--2026-11-19) follows
the earlier [whole-app candidate readiness](2026-11-13-redesign-readiness.md#final-candidate-readiness--2026-11-19).
Its current source/native evidence and pending human review remain separate from
that earlier full-suite/package snapshot. Version 0.9.0 remains Unreleased.

The earlier [focused New Prediction](#focused-new-prediction--2026-11-19)
presentation retains its own evidence and human-review scope. Earlier acceptance
below remains tied to the previously evaluated refinements.

This is the unreleased [authorized feedback package](../../product-spec.md#3815-authorized-post-review-workspace-refinements),
based on clean public `fe6a3df` (`ux-redesign`). The user checked the combined
journeys successfully, then reported eight presentation/responsiveness refinements.
Earlier four-slice acceptance and successful functional feedback remain scoped;
the initial package was subsequently reviewed as recorded below. It authorizes no installed-tool change,
personal-data operation, packaging, version/tag selection or publication.

## Changes and evidence

| Reported concern | Implemented response and regression coverage |
| --- | --- |
| Slow Journal returns and idle Updating results flashes | Same-request reads retain current rows while checking the archive, reuse unchanged widgets and replace changed rows only. Polling skips hidden/busy screens. Held reads, changed rows, failure clearing, retained disclosure focus and source returns are covered. New retrievals still mask the old listing; generation checks, full counts, admission and canonical target checks remain. |
| Archaic One-Shot Detail | Binary/Numeric now share the two-pane visual system, semantic badges and disclosure controls. Results, inline later reflection and visible Journal Entries occupy the left; context, reported/recorded facts, original facts and corrections occupy the right. Waiting/Resolved/Invalid coverage retains exact historical navigation and the existing Add Answer/transcription/Invalid guards, without Adaptive updating controls. |
| Repeated offsets and fixed date order | Settings offers DD-MM-YYYY, MM-DD-YYYY and YYYY-MM-DD (default), stored beside identity-scoped presentation preferences. Windows remains the zone source with read-only name/current offset. Ordinary readouts omit offsets; exact entry and terminal confirmation retain offset/DST cues. Tests cover persistence, restart/relocation, native input values/precision, date-filter completeness, cached Timeline refresh and reformatting an existing tool receipt without rerunning it. |
| Label and pane hierarchy | Principal labels include Current Committed Revision, Current Revision, Keep Forecast and Needs Postmortem. Main headings use TIMELINE / OVERVIEW / ARCHIVAL CONTEXT; subsection headings use Title Case. |
| Terminal pane balance | Resolved/Invalid reading is 50/50 for both modes/types. Open/Locked or waiting reading stays 60/40; contextual writing and Mark Invalid retain their selected task proportions and smooth transitions. Ten explicit pane/state cases supplement existing lifecycle/long-history checks. |
| Repeated Overview under task tabs | The shared workspace suppresses its inner Overview heading while contextual tabs identify that pane, restoring it after task close. Consult/save/return guards retain entered values and context. |

The fixed public contract deliberately replaces the earlier fixed GUI date order,
all-reading 60/40 rule and unconditional pending-row clearing. It preserves exact
canonical instants, date-only meanings and supplied documentary One-Shot offsets.
CLI/default shared text and CSV formats do not follow a GUI preference. The shared
One-Shot text adapter accepts an optional UI formatter while retaining its CLI default.
Presentation reuse includes date/Windows-zone context rather than reusing old labels
after those settings change. No unresolved consequential choice remains for this
bounded package after the user's explicit Windows/date-format selection.

## Responsiveness observations

The integrated disposable fixture contains **41 Predictions**. On this Windows
source environment, checked retrieval took about **25–32 ms**, while the previous
full-widget rebuild/return took **1.103 / 1.108 / 1.105 seconds**. After reuse,
three final returns measured **0.029 / 0.031 / 0.031 seconds**, still including a
fresh checked read. Runtime construction through initial results/layout and a widget
capture measured **0.892 seconds**, after fixture seeding and imports. This is not
a process/cold-disk startup benchmark or a guarantee for every journal/device.

The idle timer's former clearing/rebuild path explained the visible flash. The new
same-request path retains reading; automated held-read/error cases verify that this
does not hide a failed refresh. The earlier 2,000-Prediction corpus limit and deliberate
Enter/Search submission remain; this package changes no ranking, corpus or live-text
submission policy. Measurement/capture scripts and artifacts remain ignored under
`build/ux-feedback-2026-11-13/`.

## Verification

The final full suite passed **1,240 tests in 458.69 seconds**, with zero failures,
errors or skips. It includes the date-format/restart/relocation, quiet Journal/focus,
pane/heading cases above and existing history, rollback, exact-quantity, cutoff,
correction, refusal, migration, search, backup/export and independent-connection
coverage. Earlier stopped runs exposed outdated case/timestamp expectations; those
expectations were aligned with the explicitly adopted display contract before this
final run. Ruff check and format passed for 318 Python files.

Public/private documentation and whitespace checks passed. The separate preservation
audit verified all 66 J identifiers, all 42 R identifiers including both withdrawals,
unchanged reference assets, 88 current public-reference mirrors and lower-layer
dependency boundaries. These checks grant no human acceptance or publication.

Actual PySide6 widgets were rendered offscreen with installed Segoe UI at 1200 × 850
and the supported 760 × 520 logical minimum. Both modes/types and Open/Waiting,
Resolved and Invalid reading were captured in both palettes; the minimum-size probes
had no horizontal overflow in outer/left/right reading areas. Adaptive contextual
Overview captures verify the hidden duplicate heading. Settings captures cover all
three date choices. Representative light Binary One-Shot, dark Numeric One-Shot,
terminal Adaptive, tabbed Overview and Settings images were inspected. These are
native widget captures, not a complete human Windows display-scaling, accessibility
or file-dialog matrix. Previously recorded storage/device and large-corpus limits
remain applicable.

## Focused human recheck

Run `uv run python tools/run_visual_review.py integrated` and use the
[post-review three-part checklist](../../maintainer/development.md#post-review-refinement-recheck):
Journal return/idle stability, both One-Shot types/states, then date choices and
Adaptive terminal/task hierarchy in both appearances and reviewed window/scale.
The profile confines data/preferences/move artifacts to its temporary tree and is
discarded after closing. Automated injected runtimes separately verify preference
restart/relocation. Do not repeat all accepted slice walkthroughs or use personal
data for presentation checks. Human acceptance was pending at that initial checkpoint;
the subsequent reported checks and reopened One-Shot concern are recorded below.

Application/data/domain/analytics code, bundled assets, migrations 1–21, search
projection, CSV format, dependencies and private visual references are unchanged.
The agent performed no staging, commit, tag, push or publication.

## One-Shot results and reflection follow-up

At saved public `7af51f5`, the user reported acceptance of the eight focused checks,
while reopening One-Shot visual quality. The earlier 1,240-test result/captures above
remain tied to that initial package. This follow-up is authorized by the explicit
presentation feedback under Section 38.15; it adds no scoring/history/storage rule.

Checked Answer now precedes a full-pane-width scorecard with a prominent exact score
and secondary interpretation/breakdown. Results, Postmortem and Journal Entries have
separate hierarchy; history, times/facts and originals use compact keyboard-accessible
chevron headings rather than wide rounded action buttons. Historical target bodies
retain their identity and automatic reveal. Other screens retain their disclosure defaults.

The user explicitly selected retaining Skip as completion with later reflection
through More. One-Shot now shows Postmortem Skipped with its original date and no
prominent Write/Skip. Cancelling later writing retains that settled state; saving
reflection preserves the original completion, score and queue exclusion while showing
ordinary reflection/Edit. Confirmation explains the option to write later. This
corrects the misleading unchanged task presentation without permanently locking reflection.

Four new Binary/Numeric regressions cover actual stacked geometry, score prominence,
compact keyboard disclosures and the cancel/Skip/later-write journey with immutable
completion, original forecast, score and queue checks. Existing focused One-Shot/
retrieval/workspace checks passed 77 cases before these additions; all four new
cases also passed after the final provenance-label adjustment.

Final-source native captures cover ten Binary/Numeric compositions: Waiting,
Resolved awaiting reflection, Skipped, written after Skip, and Invalid. Each was
captured at 1200 × 850 in both palettes, with Dark minimum-window probes at
760 × 520 and 9/12/15-point Segoe UI. All outer/left/right horizontal-overflow
checks passed. Inline writers were also captured. Representative scorecards,
settled/written states and enlarged-text scrolling were inspected. Generated
artifacts stay ignored under `build/ux-oneshot-polish/`; this is not a full human
Windows scaling, screen-reader or native-dialog matrix.

Native inspection also exposed a misleading scorecard note after a reflection-only
save. The effective-corrected-facts note now requires actual transcription provenance;
a Postmortem save does not imply that forecasting/scoring facts were repaired. The
later-write regression covers this distinction without changing canonical replay.

Final full-source verification after that adjustment: **1,244 passed in 446.51
seconds**, with zero failures, errors or skips. Ruff check/format passed for 319
Python files. Public/private documentation checks passed 338/300 local links;
whitespace checks passed in both repositories. The preservation audit verified
89 current public-reference mirrors, all stable private IDs/withdrawals, unchanged
reference assets and protected lower layers/migrations/dependencies. These results
supersede earlier focused/intermediate runs for this follow-up's final source.

The user subsequently reported that the layouts improved and the settled Skip/later-
writing treatment was good at saved public `f552dc8`. This is scoped positive feedback
on those refinements, retaining the recorded content/device limits. Carry those
directions and the accepted functional/Journal/date/Adaptive checks forward.
All runtime evidence uses disposable data; no personal journal, installed tool,
private reference, protected lower layer, migration, dependency or Git publication changed.

## Journal preview rhythm and scoring disclosure

Based on clean public `f552dc8`, the user requested tighter Numeric Journal previews,
a slightly smaller Binary percentage with matching Numeric values, and compact
Forecast used for scoring disclosure. Section 38.15 authorizes this presentation
tuning; forecasting facts, retrieval, scoring and history are unchanged.

Journal now uses a row-specific forecast role, two points smaller than Detail's
existing forecast role. Binary percentages and all five Numeric values share that
size/weight/accent. Percentile labels remain secondary. Content-sized groups use
the existing wrapping FlowLayout with a fixed gap, rather than stretching five
columns across the window. A long label/value pair stays intact and reflows in
q05/q25/q50/q75/q95 order; signs, exact precision and the single unit label remain.
Both modes share this row grammar. Terminal forecast context uses the existing
compact keyboard-accessible chevron without changing its facts or initial disclosure.

Two new mode-specific native regressions compare real row geometry at 1600/1100/760
logical widths, matching Binary/Numeric fonts, Detail/Question hierarchy, constant
gaps, compact span and unchanged checked facts. Existing Binary/Numeric terminal
journeys now exercise the compact disclosure with Space and verify its open/closed
body and arrow. Four final focused cases passed in 3.98 seconds. The earlier 45-case
focused run preceded the final long-value FlowLayout refinement and is not final-source
evidence for that reflow.

Actual Qt captures show a mixed Journal at 1200 × 900 in both palettes and resolved
Binary/Numeric scored-forecast disclosures collapsed/expanded. Dark 760 × 720 probes
at 9/12/15-point Segoe UI covered ordinary and large signed six-decimal quantities;
no horizontal overflow or clipped value height remained. Representative mixed,
long-value and compact-context captures were inspected. Artifacts remain ignored under
`build/ux-row-rhythm/`; these do not claim a complete human Windows scaling matrix.

Final full-source suite: **1,246 passed in 474.04 seconds**, with zero failures,
errors or skips. Ruff check/format passed for 319 Python files. Public/private
documentation checks passed 339/302 local links and both whitespace checks passed.
The preservation audit verified 90 current public-reference mirrors, all 66 J IDs,
all 42 R IDs/both withdrawals, unchanged reference assets and protected lower layers,
migrations and dependencies. Earlier focused results remain tied to their stated source.

The [narrow three-point recheck](../../maintainer/development.md#journal-preview-and-scoring-disclosure-recheck)
remains **pending**. No personal data, installed tool, protected lower layer, migration,
dependency, private reference or Git publication changed.

## Further labels, marker and expanded facts refinement

The row/disclosure changes above remained uncommitted at public `f552dc8` when the
user requested three corrections. This pass preserves that candidate and extends
its checkpoint: Journal uses 50th without Median, WIS Actual diamonds remain gold
in light/dark, and both expanded One-Shot facts/history panels have consistent
rounded borders, padding and readable snapshots. Section 38.15 records this scope.

The marker had borrowed the warning-text color, making it brown in light mode.
Dedicated fill/outline tokens preserve gold and visible edges without reducing
warning-text contrast or changing projection/score. The facts/history frame insets
had been removed during the prior layout cleanup. Restored insets and width-flexible
wrapped labels now keep text inside both frames; original, correction heading/date,
Before, After and notes have distinct internal spacing. Compact chevrons, complete
facts and historical destinations remain. Detail interval labels still name Median.

Seven focused cases passed in 5.00 seconds. They include real rendered marker pixels
through light → dark → light, outline contrast and unchanged marker positions; four
Binary/Numeric × 9/15-point cases verify expanded panel insets, label bounds, complete
wrapped text/notes, no horizontal overflow at 1200/760 widths and unchanged canonical
facts. The existing two row cases also require 50th and no Median in Journal.

Actual Qt captures cover both One-Shot types' expanded times, originals and scrolled
Before/After views in both palettes; 760 × 720 probes at 9/15-point Segoe UI retained
complete label height and no horizontal overflow. Both WIS palettes were captured
with the breakdown open. Representative expanded Numeric originals/correction,
Binary times and light WIS marker were inspected. Artifacts remain ignored under
`build/ux-fact-panels/`; this is not a full human Windows scaling/accessibility matrix.

Final combined-source suite: **1,251 passed in 516.11 seconds**, with zero failures,
errors or skips. Ruff check/format passed for 319 Python files. Public/private
documentation checks passed 341/303 local links and both whitespace checks passed.
The preservation audit verified 91 current public-reference mirrors, all 66 J IDs,
all 42 R IDs/both withdrawals, unchanged reference assets and protected lower layers,
migrations and dependencies. This supersedes the earlier candidate's source result
for the combined uncommitted checkpoint.

The user subsequently reported acceptance of the
[combined candidate recheck](../../maintainer/development.md#expanded-facts-and-marker-recheck),
then requested the remaining Adaptive reveal consistency below. Earlier source results
remain version-scoped; no personal data, installed
tool, scoring/history rule, migration, dependency or Git publication was changed.

## Adaptive Overview reveal consistency

The user accepted the label/marker/fact-panel fixes and requested compact chevron
controls for the remaining inline Adaptive Overview button reveals. Probability
History on Invalid Binary, More Information on both types, Latest Committed
Distribution on terminal Numeric and supporting scored-forecast wrappers now reuse
the existing compact control. No content, chart selection, disclosure default,
historical destination or editor/dialog action was changed.

Six new Binary/Numeric × Open/Resolved/Invalid regressions exercise both palettes,
Space-key expansion/collapse, arrow/body state, existing direct-chart/default
visibility, minimum-width scrolling and unchanged canonical snapshots. Together
with the existing current-versus-scored distribution case, seven focused checks
passed in 6.79 seconds.

The broad run exposed a timing-sensitive long-history geometry assertion: its
integer pane ratio can reach the target before the final animation frame restores
normal Timeline wrapping. The check now waits for that restoration before inspecting
settled overflow, with runtime motion unchanged. All four 9/12-point Binary/Numeric
long-history cases then passed in 19.54 seconds; final full verification follows below.

Actual Qt captures cover all six reading compositions collapsed/expanded in both
palettes at 1200 × 850, plus Dark 760 × 520 horizontal-access checks. Invalid Binary
and Resolved Numeric collapsed views were inspected. Generated evidence stays ignored
under `build/ux-adaptive-reveals/`; this is not a complete human Windows device or
accessibility matrix. The [short reveal recheck](../../maintainer/development.md#adaptive-overview-reveal-recheck)
remains pending; accepted earlier presentation checks carry forward.

This work extends the same uncommitted checkpoint at public `f552dc8`; private notes
remain separate and ignored. No personal data, installed tools, protected lower
layers, migration, dependency, staging, commit, tag, push or publication changed.

Final combined-source verification after strengthening the settled-animation check:
**1,257 passed in 472.44 seconds**, with zero failures, errors or skips. Ruff
check/format passed for 319 Python files. Documentation checked 343/303 public/private
local links; both whitespace checks passed. The preservation audit verified 92 current
public-reference mirrors, all 66 J IDs, all 42 R IDs/both withdrawals, unchanged
reference assets and protected lower layers/migrations/dependencies. This final run
supersedes the intermediate timing-sensitive failure and earlier source counts.

## Adaptive Numeric definition visibility

The user requested that Unit and Decimal Places be visible near Resolution Criteria
rather than hidden in More Information. This extends the same uncommitted source
candidate at public `f552dc8`, under Section 38.15. Both fixed values now appear in
a two-field row immediately below criteria in Open, Locked, Resolved and Invalid
Adaptive Numeric reading. More Information retains optional context/history without
duplicate fields, distinguishing no additional information from unavailable history.
One-Shot definitions, editing, canonical precision and scoring are unchanged.

Nine focused regressions passed in **5.40 seconds**: four lifecycle states at 9/12-point
text, ordinary/minimum widths, exact selectable values, placement, long-unit wrapping,
no horizontal overflow, optional/empty metadata and canonical equality, plus a
definition-history failure/recovery case. The larger-text check exposed an existing
unwrapped current-distribution heading; allowing that heading to wrap removes its
eight-pixel minimum-width overflow without changing chart content.

Actual Qt captures cover all four states at 9/12-point Segoe UI in both appearances,
1200 × 850 and 760 × 720, plus expanded More Information. Resolved ordinary Light
and long-unit Dark captures were inspected. Generated evidence stays ignored under
`build/ux-numeric-definition/`; it does not establish a complete human Windows
scaling, accessibility or device matrix. The [short placement recheck](../../maintainer/development.md#adaptive-numeric-definition-visibility-recheck)
remains pending alongside the prior reveal check; accepted earlier journeys carry
forward. No personal-data operation, installed-tool replacement, protected lower-layer,
migration, dependency or Git publication change is involved.

Final combined-source suite: **1,266 passed in 487.76 seconds**, with zero failures,
errors or skips. Ruff check/format passed for 319 Python files; documentation checked
345/303 public/private local links and both whitespace checks passed. The preservation
audit verified 93 current public-reference mirrors, all 66 J IDs and 42 R IDs including
both withdrawals, unchanged reference assets, protected lower layers, migrations and
dependencies, and ignored private notes. This supersedes the preceding candidate's
source result; it does not imply human acceptance or a published release. Nothing
was staged, committed or pushed by the agent.

**Binary More Information cleanup:** The user subsequently found the redundant
Prediction Details heading beneath More Information on Invalid Adaptive Binary.
The shared Binary body now starts directly with its recorded context, with no
duplicate heading in any lifecycle state. When optional context/history is absent,
it uses the same explicit empty message as Numeric; unavailable definition history
remains an error. Existing disclosure defaults and all recorded facts are preserved.

All **57 focused Detail/metadata checks passed in 59.18 seconds**, including the
extended Binary/Numeric definition-history failure/recovery case. Actual Qt captures
of populated/empty Invalid Binary in both palettes at 1200 × 850 and 760 × 720 verified
the missing heading, retained context, canonical equality and no horizontal overflow;
representative Light empty/Dark populated captures were inspected. Artifacts remain
ignored under `build/ux-binary-information/`. Ruff check/format, both documentation
checks, preservation and whitespace checks passed. The 1,266-test full-suite result
above precedes this small cleanup and is not final-source evidence for it. This is
routine tuning within the existing pending visual checkpoint; check the same expanded
Invalid Binary panel, carrying accepted earlier journeys forward. No personal data,
installed tool, protected lower layer, Git staging, commit or push was changed.

## Final toolbar and presentation follow-up

At the unchanged saved public `f552dc8` baseline, the user requested four further
refinements before saving the combined checkpoint. Desktop One-Shot badges and
matching Detail headings now read Answer Pending, retaining warning yellow and the
existing Open lifecycle. CLI wording remains unchanged. Reset View on Journal and
Performance reserves its focus border; a baseline regression reproduced 54 pixels
available for a 56-pixel Journal label. The completed fix retains full text and the
same button width at normal/11/13-point text in both palettes.

Performance's diagnostics, percentile detail and Binary calibration tables reuse
the existing compact chevrons, preserving exact content, keyboard activation, body
identities, session retention and Reset View defaults. Actual reset/retry actions
remain buttons. Performance and Settings always offer an icon-only notebook action
with tooltip/accessibility label Journal beside the right-hand utilities. This is an
explicit user-authorized replacement of the earlier different-destination-only home
rule in Section 38.2; source-aware Back remains independent. Journal retrieval is
retained and no home self-action or creation/Detail destination is added. Global
archive refusal disables this navigation action as well.

All **91 focused checks passed in 63.67 seconds**. Coverage includes complete focused
New/Journal Reset/Performance Reset text in both palettes at normal/11/13-point fonts;
five Journal/Prediction/Performance origins for direct Journal versus source Back;
six report disclosures with Space-key arrows/body state and no canonical writes;
existing report session/reset/refresh/failure/return journeys; desktop One-Shot
wording and unchanged CLI behavior.

Actual Qt captures cover Journal, both pending One-Shot types, Performance and
Settings in both palettes, 1200 × 900 and 760 × 720 where applicable, with expanded
percentile support and focused Reset View. Journal and Settings direct returns and
unchanged pending records were checked; representative Performance Light, Settings
Dark, pending badges and focused Journal captures were inspected. Generated evidence
remains ignored under `build/ux-final-utilities/`, without a complete human device,
Windows scaling or accessibility claim. The [four-point recheck](../../maintainer/development.md#final-toolbar-and-presentation-recheck)
is pending, carrying earlier accepted journeys forward. This extends the same
uncommitted save point; no personal data, installed tools, protected lower layers,
migration, dependency, staging, commit, tag, push or publication changed.

Final combined-source suite after the four utility/presentation fixes:
**1,277 passed in 510.55 seconds**, with zero failures, errors or skips. Ruff
check/format passed for 319 Python files. Documentation checked 347/303 public/private
local links; both whitespace checks passed. The preservation audit verified 94 current
public-reference mirrors, all 66 J IDs/42 R IDs including both withdrawals, unchanged
R1/R2 reference assets, protected lower layers/migrations/dependencies and ignored
private notes. This supersedes earlier candidate source results, including the
focused-only Binary heading follow-up; it does not claim human acceptance or release.

**Settings Performance access:** The user then requested the existing chart icon
on Settings. It now appears beside Journal and appearance, while New remains absent.
Within the existing one-source navigation model, opening Performance from Settings
inherits its underlying Journal/Prediction source. A return from a Performance detour
retains the report's independent origin rather than creating a Settings/Performance
Back cycle. Current report refresh, session scope/disclosures/position, Settings
visit-local cleanup and archive refusal remain unchanged. Section 38.2 explicitly
updates the prior Settings action scope; Section 38.15 records this authorized extension.

All **46 focused workspace/Performance checks passed in 60.83 seconds**, including
Journal, Prediction and Performance origins through the Settings chart action, keyboard
activation, utility placement, two successive Back returns, and retained report state
after both Journal and Settings detours without canonical writes. Actual Qt captures
cover Settings in Light/Dark at 1200 × 900 and 760 × 720 and the retained report return;
the smaller Dark Settings composition was inspected. Generated evidence remains
ignored under `build/ux-settings-performance/`. The same bounded navigation recheck
now includes this chart action; prior human acceptance remains version-scoped, and
the 1,277-test result above precedes this extension. No personal data, installed tool,
protected lower layer, migration, dependency, staging, commit or push changed.

Final combined-source verification including Settings Performance access:
**1,281 passed in 502.91 seconds**, with zero failures, errors or skips. Ruff
check/format passed for 319 files. Public/private documentation checked 347/303 local
links; both whitespace checks passed. Preservation verified 94 current public-reference
mirrors, every J/R identifier and withdrawal, unchanged reference assets and protected
lower layers/migrations/dependencies, and ignored private notes. This supersedes the
preceding candidate's source result; scoped human toolbar/return review remains pending.

## Reported latest refinement acceptance

During readiness on 2026-11-13 the user explicitly reported the latest saved refinements,
including Settings → Performance, checked with no remaining issues. This records scoped
acceptance of the saved visual candidate at `e6690aa`, carrying earlier accepted
journeys forward. Actual Windows scaling percentage and a complete device/accessibility
matrix were not supplied. Earlier pending labels above retain their historical source
scope. The [readiness record](2026-11-13-redesign-readiness.md) owns subsequent technical
checks and the controlled adoption plan; installed-tool/data operations and publication
remain separate.

## Focused workspace widths and Journal rhythm

**Authorized and implemented — 2026-11-13; human visual acceptance pending.** After
reviewing the focused-width comparisons, the user explicitly instructed implementation
for Journal and Prediction Detail. This continuation starts from saved public
`4a4916c` on `ux-redesign`. Earlier acceptance above does not accept these later edits.

- MainWindow centers its existing toolbar/page content with a 1,024-logical-pixel
  Journal cap and a 1,120-pixel Detail cap, using available width in smaller windows.
  Other routes retain their original sizing; the native window and its safe remembered
  normal/maximized state are unchanged. Notifications remain inside the working area.
- Shared row typography gives Journal semibold Questions, smaller matching Binary/
  Numeric forecasts and larger supporting labels/dates, with tighter internal gaps
  and clear row separation. Page-title hierarchy, selectable/wrapped Questions,
  exact percentile values/units, query membership and historical navigation remain.
  Detail's existing type roles and lifecycle/task pane proportions are unchanged.
- A failing native regression reproduced the Binary Journal heading row growing to
  415 pixels despite a 30-pixel measured wrapping height. FlowLayout inherited a
  surplus-expansion request. Advertising no expanding directions retains native
  height-for-width wrapping and prevents the artificial gap before the entry body.

Focused UI verification passed **137 tests in 130.85 seconds**. Four new mode/type
cases cover centered wide/narrow geometry, retained pane proportions, unchanged
canonical snapshots and native window geometry saved independently of content width.
The reproduced heading-height regression passes after the shared layout repair.
Existing control, appearance, keyboard/source-return and long-history regressions
were included. Full-source verification is recorded in the closure below.

Controlled-clock disposable data produced **68 native offscreen captures** with
Windows Segoe UI: Journal plus all 14 available mode/type/lifecycle reading
combinations at 1,600 × 1,000 and 760 × 520 logical pixels in both palettes, then
Binary/Numeric revision forms. Horizontal-overflow, reading/writing proportions,
retained draft text through resizing/appearance/Overview consultation, notification
containment and unchanged canonical snapshots passed. Representative wide Journal,
Binary/Numeric reading and writing/minimum views were inspected. These are Qt
offscreen checks, not complete physical Windows scaling/accessibility or user
acceptance. Generated evidence remains ignored under `build/ux-focused-width/`.

For the bounded human review, run the existing disposable `detail` profile. Compare
Journal while maximizing/narrowing, read Binary/Numeric and One-Shot terminal/Answer
Pending Detail, then resize and switch appearance during a revision and consult
Overview. Check the Binary Journal prose follows its heading without the artificial
hole. The installed snapshot is unchanged until the user deliberately updates it.
No personal data, protected lower layer, migration, dependency, staging, commit,
push, version/tag or publication is changed by this continuation.

**Verification closure:** The final executable source passed **1,286 tests in
512.69 seconds**, with zero failures, errors or skips. Locked offline sync, Ruff
check and format check passed. Public/private documentation checked 356/300 local
links with zero errors; both whitespace checks and preservation passed. The audit
retained all 66 J IDs, 42 R IDs, both withdrawals, unchanged reference assets and
95 public-reference mirrors; protected lower layers/migrations/dependencies remain
unchanged and private notes remain ignored by the public repository.

The same 68-capture matrix was repeated successfully at `QT_SCALE_FACTOR=1.5`
and `2`, giving **204 native captures across simulated 100%/150%/200% Qt scaling**.
Draft retention, pane proportions, horizontal overflow, notification containment
and canonical snapshots passed at each factor. These simulated offscreen scales
do not establish the user's physical Windows scaling/accessibility acceptance.
The focused human check above remains pending. No runtime code changed after the
full-suite run; subsequent edits only close documentation/evidence.

## Focused Performance report width

**Authorized and implemented — 2026-11-13; human review pending.** After saving the
Journal/Detail refinement at public `1d7b85c`, the user separately approved the
recommended focused Performance treatment. One shared ContentWidth token and its
route constraint center the existing toolbar/report at a maximum of 1,280 logical
pixels. Smaller windows use available width. The existing paired/stacked breakpoint,
pinned scope strip, typography, exact report populations/statistics, retained
tag/unit/disclosure state and source returns are unchanged. Other destinations and
native window geometry/preferences retain their existing behavior.

The focused Performance/Journal run passed **48 tests in 68.82 seconds**. Two new
palette cases exercise the centered maximum at 1,600/1,280/1,100/760-pixel widths,
paired versus stacked sections, pinned controls inside the viewport, the same report
identity/request, retained supporting expansions and zero canonical writes. Existing
session/reset, failure and navigation regressions were included.

A controlled-clock disposable archive with 12 answered observations per contract
produced **60 native offscreen captures** across simulated Qt scales 1/1.5/2,
Light/Dark, collapsed/expanded content and scrolled pinned controls. Wide paired and
narrow stacked views, all six ordinary supporting expansions, no horizontal page
overflow, current report identity and exact unchanged report facts passed.
Representative wide and expanded/narrow captures were inspected. These simulations
do not establish physical Windows scaling/accessibility or user visual acceptance.
Generated evidence remains ignored under `build/ux-focused-width/`.

The bounded human check uses the existing disposable `performance` profile:
maximize/narrow, expand supporting charts/tables, scroll with Tag / Reset View pinned,
and retain tag/unit/disclosure scope across a Journal or Settings detour. Reset View
retains its existing meaning. No personal-data or installed-tool operation, migration,
dependency, staging, commit, push, version/tag or publication is performed by this
continuation. Final source verification is recorded below.

**Verification closure:** Final executable source passed **1,288 tests in
533.11 seconds**, with no failures, errors or skips. Locked offline sync, Ruff
check/format, public/private documentation (356/302 local links), both whitespace
checks and preservation passed. All 66 J IDs, 42 R IDs, both withdrawals and existing
reference assets remain; 95 public-reference mirrors and lower-layer boundaries
were checked. Protected application/data/domain/analytics, migrations and dependencies
are unchanged, and notes remain ignored by the public repository. The 60 native
captures and focused tests above supplement this full run. Human visual acceptance
is pending. Subsequent edits only close documentation/evidence; executable code did
not change after the full-suite run.

## Quieter scrollbars and roomier Detail — 2026-11-14

**Authorized and implemented; human review pending.** The user reported the
Performance checkpoint saved/pushed, then requested less intrusive side scrollbars
and a little more Detail width while retaining side margins. This continuation
starts from locally clean public `79989a6` on `ux-redesign`. Earlier accepted
journeys and test runs retain their original source scope.

Detail's shared content cap increases from 1,120 to 1,200 logical pixels, reducing
each side margin by 40 pixels in a sufficiently wide window. Smaller windows use
available width. Journal/Performance retain their 1,024/1,280 limits. Native window
geometry/preferences, four-contract pane proportions/motion, source context,
drafts and canonical history remain unchanged.

The shared native scrollbar stylesheet uses transparent tracks and rounded neutral
8-pixel thumb fills inside a 14-pixel slider hit lane. Hover, pressed and focus
states remain visible. End-arrow boxes are omitted; Qt still owns track paging,
wheel, dragging and keyboard actions. Both orientations, existing visibility
policies and independent Detail panes remain. There is no custom scrolling engine,
auto-hide behavior, preference, dependency or lower-layer change.

Final executable source passed **1,296 tests in 712.70 seconds**, with zero
failures, errors or skips. The ten focused scrollbar interaction/contrast cases
also passed independently in 0.89 seconds across Light/Dark, both orientations
and windows11/Fusion styles. They cover the inset hit lane, dragging,
Home/End/Page Down, track paging and native wheel input.

Disposable fixtures produced **264 native offscreen captures** across simulated
Qt scales 1/1.5/2: 204 Journal/Detail captures and 60 Performance captures. The
Journal/Detail matrix covers both palettes, 14 available four-contract/lifecycle
reading combinations at wide/minimum sizes, Binary/Numeric revision drafts,
appearance/width changes, pane ratios and notification containment. The Performance
matrix covers paired/stacked widths, six supporting expansions and pinned controls.
Horizontal-overflow, draft retention, report identity and unchanged canonical
snapshot/report facts checks passed. Representative wide/minimum reading,
writing and expanded report captures were inspected. Offscreen simulations do not
establish physical Windows scaling, accessibility or human visual acceptance.
Generated evidence remains ignored under `build/ux-focused-width/`.

For the bounded human review, use the existing disposable detail and performance
profiles. Compare both palettes, drag/wheel/key-scroll in Journal, independent
Detail panes and Performance, then maximize/narrow Detail and switch appearance
with a revision draft present. Confirm the additional room still leaves side
margins at wide sizes. Installed tools and personal data are unchanged. All Git,
version/tag and publication steps remain user-owned.

**Verification closure:** Locked offline sync, Ruff check/format, public/private
documentation (356/307 local links), both whitespace checks and preservation
passed. All 66 J IDs, 42 R IDs, withdrawn R-33/R-34 and reference packs remain;
95 public-reference mirrors and lower-layer boundaries were checked. Protected
application/data/domain/analytics, migrations, assets and dependencies are unchanged;
private notes remain ignored. No executable code changed after the full-suite
run; subsequent edits only close documentation/evidence. Human visual acceptance
of this source remains pending.

## Narrative Detail and wider Journal — 2026-11-14

The user reported both preceding scrollbar/Detail-width profiles checked and good.
That accepts the supplied review scope; no physical Windows scaling/accessibility
matrix or release approval is inferred. Public `0e6d913` on `ux-redesign` was locally
clean at this continuation. New feedback separately requests a wider Journal and
flat Detail reading closer to the reviewed references, with inline event dates and
coherent hierarchy. Public Section 38.15 records the authorized presentation scope.

Journal now matches Detail's 1,200-logical-pixel cap, while Performance keeps 1,280.
Shared TimelineEntry uses a thin rule and a wrapping event/date header across
Adaptive forecasts, Reviews, Journals, terminal events, One-Shot recorded/Journal
history and definition changes. Detail-only reading styles remove enclosing cards
and their insets. Pane headings lead event/subsection names, body prose is readable
and dates quieter. Current Revision retains its accent marker/jump. Native controls,
semantic status/error/focus feedback, pane ratios/motion, draft/source/scroll state,
exact facts, immutable row identities and historical search targets remain.

Final focused verification passed **92 tests in 101.07 seconds**, covering Detail
reading/writing, long-history reuse, historical search/corrections and exact
timestamp provenance. Four new contract cases exercise inline dates at wide width,
natural narrow wrapping, heading/body/time hierarchy, selectable timestamps, both
palettes and unchanged canonical snapshots. Existing local and canonical exact-time
tooltip forms remain with their original callers.

The 33 One-Shot workflow checks also passed in 9.39 seconds, including the updated
flat-alignment/complete-text case at 9- and 15-point native fonts for both types.
Expanded facts retain all original/Before/After values and notes without clipping
or horizontal page overflow. The former padded-card assertion is superseded by
the explicitly authorized flat reading contract.

The composition produced **204 native offscreen Journal/Detail captures** at Qt
scales 1/1.5/2 with real Windows Segoe UI. Both palettes, 14 available contract/state
reading combinations, wide/minimum geometry, Binary/Numeric revision drafts,
appearance/Overview consultation and notification containment passed their checks.
Another **16 captures** cover long Binary/Numeric history and expanded corrected
One-Shot facts/recorded history at wide/narrow widths in both palettes, retaining
row identities through order changes and exact canonical snapshots with no writes.
Representative ordinary, scaled and expanded/long-history captures were inspected.
Generated evidence stays ignored under `build/ux-focused-width/`. These simulations
do not establish physical Windows/accessibility or human acceptance.

The bounded human review uses the existing disposable detail profile: compare
Journal wide/narrow, inspect Binary/Numeric forecasts and Journal/Review headers,
use Current Revision/order, expand One-Shot Recorded History and Originals &
Corrections, and retain a revision draft while consulting Overview. Review both
palettes. The agent changed no installed tool or personal data and performed no
Git/version/tag/publication action. Human acceptance of this later source remains
pending; prior checks retain their own artifact scope.

**Verification closure:** Final source passed all **1,300 tests** in two disjoint
alphabetic module groups: 789 in 286.07 seconds and 511 in 461.24 seconds, with zero
failures, errors or skips. The groups partition the full collected suite before
`test_one_shot_workflows.py` and from that module onward, using separate disposable
test directories and caches. Locked offline sync, Ruff check/format, public/private
documentation (356/310 local links), both whitespace checks and preservation passed.
All 66 J IDs, 42 R IDs, withdrawn R-33/R-34, R1/R2 references and 95 public-reference
mirrors remain. Protected lower layers, migrations, assets and dependencies are
unchanged; private notes remain ignored. No executable code changed after the final
group runs; subsequent edits only close documentation/evidence. The supplied
visual review is the remaining human acceptance step for this source.

## Framed workspace surfaces — 2026-11-14

The user explicitly accepted narrative Detail and wider Journal, particularly
Timeline/Overview and ruled entries, and reported the checkpoints saved/pushed.
Public `19cf7e6` on `ux-redesign` was locally clean at this continuation. The next
request separately authorizes a visible outer outline and related margin tone to
distinguish focused surfaces. This does not infer release approval or an unreported
physical Windows scaling/accessibility review.

The existing shared toolbar/page widget now paints one quiet 1-pixel outline with
restrained 10-pixel outer corners. Its existing parent paints a slightly deeper,
palette-relative outer canvas. Interior colors, flat reading sections, typography,
spacing and width constraints remain. Settings/creation keep full-width sizing and
share the boundary. Explicit native styled-background painting uses no graphics
shadow/effect, new wrapper, animation, preference or dependency. Native geometry,
notification parenting, focus, scroll, draft/source context and protected facts remain.

Eight focused geometry/paint/contrast cases passed in **6.92 seconds**, including
two new palette cases checking actual canvas, outline and gutter pixels across all
five routes, unchanged widths and canonical snapshots. **264 native offscreen
captures** cover Journal/Detail and Performance at Qt scales 1/1.5/2: 204 reading/
writing captures across 14 available contract/state combinations, and 60 report
captures with paired/stacked sections, six supporting expansions and pinned controls.
Both palettes, wide/minimum layouts, draft retention, horizontal overflow,
notification containment, report identity and unchanged canonical facts passed.
Representative light/dark framed surfaces were inspected. Simulations do not
establish physical Windows/accessibility or human visual acceptance. Generated
evidence stays ignored under `build/ux-focused-width/`.

The bounded human review compares Journal, Detail and Performance framing in both
palettes, narrows the window and retains a Detail draft through appearance changes.
The accepted interior composition should remain familiar. Installed tools, personal
data and all Git/version/tag/publication operations remain user-owned.

**Verification closure:** Final source passed all **1,302 tests** in three disjoint
groups: 791 in 344.70 seconds, 490 in 301.95 seconds and the 21 visual-system cases
in 0.88 seconds, with zero failures, errors or skips. The full collected suite is
partitioned before `test_one_shot_workflows.py`, from that module onward excluding
`test_visual_system.py`, and that visual-system module independently. Each uses
separate disposable test directories/caches. Locked offline sync, Ruff check/format,
public/private documentation (356/312 local links), both whitespace checks and
preservation passed. All stable J/R identifiers, withdrawals and reference packs,
95 mirrored public references and protected lower-layer/migration/dependency
boundaries remain intact; notes remain ignored. No executable code changed after
these final runs. Subsequent edits close documentation/evidence only; the short
human framing review remains pending.

## Structural rules and Detail headers — 2026-11-14

The user accepted framed workspaces and reports both checkpoints saved/pushed.
Public `31c5197` on `ux-redesign` was locally clean. The next request separately
authorizes reference-aligned structural rules, a clean toolbar, Question-first
Detail metadata/tag chips and actual Numeric legend symbols. No consequential
unresolved choice or protected-rule conflict was found.

The shared toolbar omits the duplicate in-content product/development name while
native window titles retain their identity. Its bottom rule separates navigation
from content. Journal adds a rule between search/filter controls and results and
uses the bundled Lucide magnifier inside its existing search field; Enter/Search,
clear and Ctrl+F behavior remain. The icon refreshes with the palette without
adding an input command or duplicate action.

Detail has a persistent rule between forecast/actions and panes, plus a
mouse-transparent vertical rule following the existing automatic 60/40, 40/60 and
50/50 boundary through native layout movement. There is no manual splitter or
forced history reflow. The full Question precedes wrapping mode/status/tag chips;
literal selectable tag names use quiet outlines distinct from filled identity/
status chips, without generated hashtag prefixes. Numeric Detail has matching
thin 90%, thick 50% and vertical Median marks beside the legend text in both modes.
Adaptive timing, complete values/units, accepted widths, flat reading and all
history/scoring/storage rules remain.

Final source passed all **1,308 tests** in three disjoint groups: **797 in 309.28
seconds**, **490 in 241.04 seconds** and **21 visual-system cases in 0.93 seconds**,
with zero failures, errors or skips. The groups partition the complete suite before
`test_one_shot_workflows.py`, the remainder excluding `test_visual_system.py`, and
that visual-system module independently, using separate disposable directories/
caches. Six new final-source header/tag/legend/divider cases also passed in 7.35
seconds. They cover all four contracts, visible literal wrapped tags below the
Question, wide horizontal legends, both palettes and wide/minimum widths, moving
rules and retained drafts. Earlier focused runs passed 138 reading/history/
workflow/Journal/icon cases in 125.38 seconds before the final decorative-action
naming adjustment, and 57 metadata/restart cases in 29.91 seconds.

**264 native offscreen captures** cover Journal/Detail and Performance at Qt scales
1/1.5/2 with real Windows Segoe UI: 204 reading/writing captures across 14 available
contract/state combinations, and 60 report captures with paired/stacked sections,
six supporting expansions and pinned controls. Both palettes, wide/minimum
layouts, draft retention, horizontal overflow, notification containment, report
identity and unchanged canonical facts passed. Representative final Journal,
Numeric reading/revision and One-Shot result captures were inspected, including
scaled minimum-width geometry. The final decorative-action naming change affects
no painted geometry. Generated evidence remains ignored under
`build/ux-focused-width/`. Simulations do not establish physical Windows/
accessibility or human visual acceptance.

The short human review uses `uv run python tools/run_visual_review.py detail`:
inspect Journal's clean toolbar, rules and magnifier; compare Detail's Question-first
chips and Numeric legend; retain a revision draft while consulting Overview and
watch the divider through pane changes. Review both palettes and narrow/wide
windows. Earlier acceptance remains scoped; this later composition awaits review.
No executable code changed after the final suite runs. Installed tools, personal
data and all Git/version/tag/publication actions remain user-owned and untouched.

**Verification closure:** Locked offline sync, Ruff check/format (320 files),
public/private documentation (356/315 local links), both whitespace checks and
preservation passed. All stable J/R identifiers, withdrawals, reference packs and
95 public-reference mirrors remain. Protected application/data/domain/analytics,
bundled assets, migrations and dependencies are unchanged; notes remain ignored.
Final edits only close documentation/evidence. Human review of this composition
remains separate from these automated and offscreen checks.

## Flat surfaces and scrollbar refinement — 2026-11-19

Both repositories were locally clean at public `f233faf` on `ux-redesign` and its
separate private checkpoint. The direct feedback authorizes flat noninteractive
surfaces, hover-expanding shared scroll thumbs and centered Settings. Earlier
acceptance remains scoped; the prior saved structural refinement is not treated
as blanket approval of this later source. Outside layout suggestions do not
authorize a new navigation rail, pane ratio, criterion-collapse rule or scroll model.

The shared stylesheet paints a 4-pixel resting thumb that expands to 8 on hover,
focus or press inside the unchanged 14-pixel native hit lane. Native drag, track
paging, wheel and keyboard actions remain. Ordinary read-only panels use flat
rules, with square workspace/status/tag/message boundaries; interactive fields,
buttons and dropdowns retain their treatment. Shared dialog presentation gives
repeated forecast context complete, unboxed, selectable body text with shrinkable
width and wrapped minimum height. Main committed forecasts stay prominent.
Settings joins the 1,200-wide centered toolbar/page shell while retaining its
existing 920-wide administration body. Journal/Detail stay 1,200; Performance stays
1,280. Existing criteria, independent scroll, task proportions/motion, exact facts,
guards and canonical boundaries remain.

Six final context tests passed in **12.24 seconds**, covering Binary/Numeric Keep
Forecast, Resolve and Add Journal Entry, both palettes, ordinary-font wide/minimum
geometry and 15-point native fonts at wide geometry. Text height, body scale,
transparent context background, mouse/keyboard selection, retained task identity,
no page overflow and unchanged canonical snapshots are checked. Custom 15-point
controls at minimum geometry are not claimed; they can require a wider window,
independently of DPI scaling. The final shared visual module passed **21 tests in
1.34 seconds**, including eight cross-style/orientation/palette cases checking
actual 4/8-pixel paint, stable geometry, full-lane drag, focus, track paging, wheel
and keyboard actions. An earlier focused **140-test** run passed in 186.91 seconds
before the final body-scale adjustment; final full-source/native closure follows.

The short human review uses `uv run python tools/run_visual_review.py detail`.
Check the three task contexts and a retained draft, hover/focus/drag the page and
pane scrollbars, and visit Settings in both palettes and wide/minimum windows.
No installed tool, personal database, dependency, migration or Git/release state
is changed by the agent. Human visual acceptance remains pending.

**Final source closure:** All **1,314 tests** passed in three disjoint groups:
**803 in 328.16 seconds**, **490 in 243.79 seconds**, and the **21 visual-system
cases in 1.34 seconds**, with zero failures, errors or skips. The complete suite is
partitioned before `test_one_shot_workflows.py`, the remainder excluding
`test_visual_system.py`, and that module independently, with separate disposable
test directories/caches. No executable source changed after these final runs.

**348 native offscreen captures** cover the final source at Qt scales 1/1.5/2 with
Windows Segoe UI: 288 Journal/Detail/task/Settings captures and 60 Performance
captures. Both palettes, ordinary/minimum geometry, 14 available contract/state
reading combinations, Binary/Numeric revision/Review/Resolution/Journal tasks,
Settings width, wrapped text, notification containment, retained drafts and
unchanged canonical snapshots passed. Performance retains paired/stacked sections,
six supporting expansions, pinned controls and report identity/facts. Representative
final task and ordinary/scaled Settings captures were inspected. Evidence stays
ignored under `build/ux-flat-surfaces/`; simulation is not physical Windows/
accessibility or human acceptance evidence.

**Documentation/preservation closure:** Locked offline sync, Ruff check/format
(320 files), public/private documentation (356/316 local links), both whitespace
checks and preservation passed. Stable identifiers/withdrawals/reference packs,
95 current public-reference mirrors and protected lower-layer/migration/asset/
dependency boundaries remain intact; notes remain ignored. Subsequent edits only
close documentation/evidence; the short human review remains pending.

## Wider workspaces and compact Settings — 2026-11-19

The user accepted the flat-surface/expanding-scrollbar refinement, retained native
proportional thumb lengths after explanation, and reports both checkpoints saved/
pushed. Public `f08a361` on `ux-redesign` was locally clean; the separate private
repository was also clean. This is scoped acceptance, not release approval or a
supplied physical Windows/accessibility matrix. The next request authorizes wider
focused workspaces and ordinary Settings with every option visible without scrolling.

Journal/Detail/Settings caps increase to **1,320** logical pixels and Performance
to **1,440**, retaining centered margins, available narrow width and native geometry.
Settings replaces its long single column/920-wide inner cap with four paired rows:
preferences/context left and the same administrative tools right. A concise header,
reduced local gaps/padding and inline folder guidance/chooser keep the shared text/
control scale. Explicit control tab order includes the chooser between date format
and backup. Ordinary Settings have no scroll range at supported minimum geometry;
exceptional long results/paths or enlarged native text retain complete safe overflow.
No overflow is forced hidden. Existing tool results, visit clearing, navigation,
relocation, exact facts, draft/report state and protected rules remain.

Style-switch verification also reproduced queued Numeric metric work after widget
destruction. A child-owned single-shot timer now cancels that work with the interval
while preserving coalesced measurement, exact values and projection. The regression
destroys an interval before queued delivery and verifies clean Qt event processing.

Seven final focused cases passed in **24.07 seconds**: four two-palette/two-style
Settings cases cover all ordinary controls, complete labels, no scrolling and
keyboard order across wide/mid/minimum geometry; two preserve long-result text,
overflow and visit clearing; one covers Numeric timer lifetime. Eight additional
captures use real Segoe UI with complete representative paths and actual chooser
controls across both palettes, Windows11/Fusion and ordinary/minimum geometry;
all have zero horizontal/vertical scroll range. Minimum Light and enlarged Dark
compositions were inspected. Final full-suite/scaled closure is recorded below.

The short human review uses `uv run python tools/run_visual_review.py detail`:
compare wider Journal/Detail/Performance, retain a Detail draft and report scope,
and inspect every ordinary Settings option at wide/minimum sizes in both palettes.
Include folder selection visibility and keyboard order; no actual move is needed.
The agent changed no installed tool, personal database, dependency, migration or
Git/release state. Human visual acceptance of this later composition remains pending.

**Final verification closure:** All **1,321 tests** passed in three disjoint groups:
**804 in 348.95 seconds**, **496 in 408.70 seconds** and **21 visual-system cases in
1.47 seconds**, with zero failures, errors or skips. The complete suite is
partitioned before `test_one_shot_workflows.py`, the remainder excluding
`test_visual_system.py`, and that module independently, using separate disposable
directories/caches. No executable source changed after these final runs.

**356 native offscreen captures** cover final geometry: 288 Journal/Detail/task/
Settings and 60 Performance captures at Qt scales 1/1.5/2, plus the eight dedicated
real-font Settings captures above. The ordinary Settings captures include actual
location controls and complete paths, with no horizontal/vertical scroll range at
wide/minimum sizes in both palettes/scales. Fourteen available Detail contract/state
combinations, all four contracts, reading/writing proportions, retained drafts,
notification containment, complete text, report identity/disclosures and unchanged
canonical facts passed their checks. Representative ordinary and scaled Settings
captures were inspected. Evidence remains ignored under `build/ux-settings-fit/`;
simulation is separate from physical Windows/accessibility and human acceptance.

Locked offline sync, Ruff check/format (320 files), public/private documentation
(356/320 local links), both whitespace checks and preservation passed. All stable
J/R IDs, withdrawals, R1/R2 assets and 95 public-reference mirrors remain; protected
application/data/domain/analytics, migrations, assets and dependencies are unchanged.
Private notes remain ignored. Final edits only close documentation/evidence; the
short visual review and user-owned Git handoff remain pending.

## Rounded prediction metadata — 2026-11-19

The wider-workspace checkpoint was saved with scoped positive user feedback;
public `bfee0ad` on `ux-redesign` and the separate private repository were locally
clean. The user requests rounded mode/type, lifecycle/status and tag chips, then
clarifies that this covers both Detail and Journal previews. This combined check
owns both still-uncommitted refinements; no later width choice is inferred.

Detail header and Journal preview metadata containers share
`reckonsolvePredictionMetadata`; their badge/tag labels receive the existing
4-pixel small radius. Journal uses FlowLayout, a neutral mode/type StatusBadge,
its existing semantic status tone and shared TagChips for exact current names
already supplied by its canonical summary. Tags remain selectable context without
generated hashtags or new filter actions. Metadata wraps naturally. Other flat
surfaces, widths, Question/forecast/date hierarchy, exact Numeric summaries,
counts, passages, navigation and return behavior remain unchanged. No stored fact,
query, tag relationship, dependency, installed-tool or Git/release operation changes.

All **76 relevant final cases** passed in separate groups: **51 Journal/workspace/
retrieval/read-consistency/response-budget cases in 79.61 seconds**, **four extended
Journal+Detail metadata cases in 8.58 seconds**, and the **21 visual-system cases in
1.52 seconds**. The metadata cases cover all four contracts, correct mode/status,
C#/long literal names, complete selectable wrapping, both palettes, wide/minimum
geometry and unchanged canonical snapshots. The visual module is isolated from
other Qt style/focus state and activates its own top-level test window. Earlier
Detail-only checks preceded this Journal extension and remain scoped to that source.

**68 current native offscreen captures** cover both palettes, 14 available Detail
contract/state combinations, wide/minimum geometry, revision writing and Journal
previews with the new chips. Wrapping, draft/pane retention, no horizontal overflow,
notification containment and unchanged canonical facts passed. Representative
Journal previews and Detail captures were inspected. Generated evidence stays
ignored under `build/ux-metadata-chips/`; physical Windows/scaling and human visual
acceptance remain separate. The previous 1,321-test full-suite evidence belongs to
the saved wider-workspace source, not this later focused presentation checkpoint.

The short human review compares rounded preview/header chips in all four contracts
and both palettes. Detail remains 1,320; discussion of 1,440 is not adoption or a
width-experiment instruction. Other accepted composition and user-owned operations
remain. No product code changed after final focused verification.

Ruff check/format, public/private documentation (356/324 local links), both whitespace
checks and preservation passed. Stable J/R identifiers/withdrawals, R1/R2 assets,
95 public-reference mirrors and protected lower-layer/migration/dependency boundaries
remain; private notes stay ignored. Current Journal/Detail chip review remains pending.

## Focused New Prediction — 2026-11-19

Public `541bd19` (`ux-redesign`) and the separate private repository were locally
clean at this request. The preceding metadata checkpoint is saved; this does not
infer additional human acceptance or remote publication. The user now requests
New Prediction's foreground/background alignment with the other main screens,
explicitly retaining functionality.

Creation was the remaining unbounded toolbar/page route, so a wide window left
no contrasting side margins. Its shared outer surface now caps at **1,320 logical
pixels**, exposing the existing deeper canvas and square outline in both themes.
Adaptive and One-Shot retain their centered **980-wide inner form columns**;
One-Shot's scroll surface now explicitly shares the existing transparent treatment.
The existing form composition, text/input scale, fields/defaults, optional sections,
mode/type drafts, keyboard flow, validation, save/cancel/source returns and creation
toolbar restrictions remain. Smaller windows use available width and native scrolling.
Only the shell width selection and shared visual-system adapter change at runtime.

All **111 focused final cases** passed in separate groups: six creation/frame cases
in **7.12 seconds**, 84 creation/One-Shot/workspace cases in **35.87 seconds** and
21 isolated visual-system cases in **1.36 seconds**. The four new contract cases
check actual foreground/outer-canvas pixels, wide/minimum geometry, centered forms,
no horizontal overflow, retained raw inputs and toolbar restrictions. Existing cases
cover creation/validation, mode/type switching, drafts, guarded cancellation and
source returns. No executable source changed after these checks.

**96 native offscreen captures** cover all four contracts, ordinary/expanded optional
sections, both themes and 1,600 × 1,000 / 760 × 520 logical geometry at Qt scales
1/1.5/2, using real Windows Segoe UI. Geometry, raw draft retention, no horizontal
overflow, reachable Save controls and zero canonical records passed in each run.
Representative wide Light Adaptive, wide Dark One-Shot and scaled minimum Numeric
captures were inspected. Evidence stays ignored under `build/ux-creation-surface/`.
This is simulated native evidence, separate from physical Windows/accessibility
and human visual acceptance. The earlier full suite belongs to the saved wider-
workspace baseline; this cosmetic checkpoint does not claim a fresh full-suite run.

For the short human review, run `uv run python tools/run_visual_review.py detail`
and open New Prediction. Compare both appearances in a wide and smaller window;
switch Adaptive/One-Shot and Binary/Numeric, expand optional sections and verify
the familiar form, draft retention and cancellation. Use disposable data. No
installed tool, personal database, dependency, migration or Git/release state was
changed by the agent. Current human visual review remains pending.

Locked offline sync, Ruff check/format (320 files), public/private documentation
(356/326 local links), both whitespace checks and preservation passed. All 66 J
identifiers, 42 R identifiers and both withdrawals, R1/R2 assets, 95 public-reference
mirrors and protected application/data/domain/analytics, migration and dependency
boundaries remain. Private notes stay ignored. These final edits close documentation
and evidence only; human review and user-owned Git operations remain separate.

## Compact Journal entries — 2026-11-19

During final human review the user identified excess space below Journal Entry
headings and redundant Numeric forecast summaries. They explicitly selected compact
heading/correction actions and complete omission of the Numeric Journal summary,
retaining Binary's short Forecast at the time line below its body. The suggested
replacement forecast chevron was rejected. Version 0.9.0 remains Unreleased.

`TimelineEntry.add_action` scopes compact padding and a stable native focus border
to Journal correction controls across Adaptive/One-Shot Binary/Numeric. Corrected
Binary/One-Shot header dates now use the shared natural-width Timeline label;
an expanded regression reproduced their unnecessary 32-pixel header even after
button padding was reduced. Wide ordinary headers now use the compact action's
natural 20-pixel height; narrower/larger-font headers wrap safely. The body follows
the measured header with ordinary spacing. Labels, accessible action names,
keyboard activation, correction panes and exact timestamps remain.

Adaptive Numeric Journal rows render their body directly after the header. The
repeated 90% interval/Median/50% interval block is omitted; the committed header,
actual forecast/revision rows and Numeric Reviews retain complete exact context.
Stored original anchors, causal position, body/correction versions and search
targets are unchanged. Binary retains its one-line historical percentage below
the body. No query, storage, scoring, lifecycle, dependency or geometry rule changes.

All **203 relevant final cases passed** in separate groups: **182 Detail/workspace/
responsiveness/Journal/One-Shot cases in 153.55 seconds** and **21 isolated visual-
system cases in 1.39 seconds**. Expanded four-contract checks include original and
corrected entries, compact actual geometry, keyboard correction activation, stable
focus size, body-first order and unchanged snapshots. A Numeric regression creates
a Journal, corrects its text, then commits a later forecast: its old anchor and
collapsed text history remain intact, full revision rows remain visible and no
replacement forecast disclosure is introduced. No runtime source changed after
these final checks.

**288 final native offscreen captures** cover all four contracts with original/
corrected Journals, both palettes, 1,600 × 1,000 / 760 × 520 logical geometry,
9/13-point Segoe UI and Qt scales 1/1.5/2. Each font/scale probe runs in a separate
process. Complete text, natural wrapping/spacing, stable focus geometry, Binary's
anchored percentage, Numeric body-first reading and unchanged canonical snapshots
passed. Representative wide and minimum/enlarged entries/screens were inspected.
This is simulated native evidence, separate from physical Windows/accessibility
and human visual acceptance. Generated evidence remains ignored under
`build/ux-journal-entry-tuning/`.

A filesystem comparison with the preceding candidate wheel verifies that only
the four intended UI modules differ among its 166 application files; protected
application/data/domain/analytics, migrations and bundled resources match byte for
byte. Tests extend the existing Detail finish module. The earlier 1,325-case full
suite and source/wheel/private-build artifacts belong to the preceding readiness
payload; they are not fresh whole-suite/package validation of this later tuning.
Refresh final delivery evidence for the eventual accepted source. All Git commands
remain reserved to the user and were not run for this pass.

For the short human recheck, run `uv run python tools/run_visual_review.py detail`.
Inspect Journal entries in Adaptive Numeric and Binary, including edited entries,
then compare One-Shot correction headings. Check both palettes at wide/smaller
sizes: the body should follow its compact heading, Numeric should not repeat its
forecast block, Binary should retain its short context and Correct Entry should
remain usable with the keyboard. Other accepted journeys carry forward; final
whole-app human visual approval remains pending. No installed tool or personal
database was opened or changed.

**Documentation/preservation closure:** Locked offline sync and Ruff check/format
(320 files) passed. The existing documentation engine with filesystem discovery
checked **363 public links/58 Markdown files** and **328 private links/five files**,
zero errors. Filesystem checks retained 66 J identifiers, 42 R identifiers and both
withdrawals, verified 96 public-reference mirrors, lower-layer imports and affected-
file whitespace/conflict markers. Reference packs were not edited. No Git command
was run; Git-based status/diff/tracking checks remain with the user. No executable
source changed after the final focused/native checks; later edits close documentation
only. Human visual acceptance of this follow-up remains pending.
