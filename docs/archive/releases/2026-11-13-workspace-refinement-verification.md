# Post-review workspace refinement verification — 2026-11-13

This is the unreleased [authorized feedback package](../../product-spec.md#3815-authorized-post-review-workspace-refinements),
based on clean public `fe6a3df` (`ux-redesign`). The user checked the combined
journeys successfully, then reported eight presentation/responsiveness refinements.
Earlier four-slice acceptance and successful functional feedback remain scoped;
this package awaits focused human recheck. It authorizes no installed-tool change,
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
data for presentation checks. This focused human acceptance is **pending**.

Application/data/domain/analytics code, bundled assets, migrations 1–21, search
projection, CSV format, dependencies and private visual references are unchanged.
The agent performed no staging, commit, tag, push or publication.
