# Post-review workspace refinement verification — 2026-11-13

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
