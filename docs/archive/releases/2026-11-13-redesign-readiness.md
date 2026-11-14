# Redesign readiness — 2026-11-13

This is an unreleased readiness record for public `e6690aa` plus the narrowly scoped
readiness corrections below. The user authorized readiness implementation/checks and
reported the latest saved refinements, including Settings → Performance, checked
with no remaining issues. The four earlier requested walkthroughs and combined
journeys retain their reported acceptance. No actual Windows scaling percentage was
supplied; this is scoped human acceptance, not a complete device/accessibility matrix.

## Scope and corrections

The implementation remains the four closed forecasting/scoring contracts under
schema 21, search projection 3 and analytical CSV 6. Applied migrations, scoring,
history, data boundaries and dependencies were not changed. Corrections align CLI
export help, a verification diagnostic and the forecasting guide with format 6, and
clarify default versus relocated active paths. The ordinary-use procedure now derives
runtime constraints from `uv.lock` rather than assuming an unconstrained tool install
selects the tested dependencies. No new feature or visual treatment was introduced.

The latest UI acceptance therefore applies to the unchanged visual implementation.
The [controlled adoption procedure](../../guides/user-guide.md#adopt-the-redesigned-source)
is prepared for review. Personal backup/update/restore operations, installed-tool
replacement, frozen executable publication, version/tag changes, merge and Git
publication remain separately authorized work.

## Source and search checks

- Focused CLI, transfer, upgrade, relocation, package and compatibility-smoke checks:
  **137 passed in 60.96 seconds**. Export help now identifies format 6 and remains
  database-free. Existing cancellation/failure, writer exclusion, history and recovery
  cases remain meaningful verification of the current implementation.
- The standalone Adaptive search benchmark created 2,000 synthetic predictions and
  6,000 derived documents in 71.095 seconds. Five-repeat warm medians were 31.245 ms
  for one exact target, 169.763 ms for 2,000 broad results, 36.995 ms for an 80-result
  tag cohort and 55.671 ms for no result. Every expected count/rank was complete.
  These are shared retrieval measurements, not mixed-mode Journal paint latency or
  proof that the earlier automatic-search budget passed. Enter/Search remains selected.

## Isolated source-package installation

Built a source distribution and pure-Python wheel, verifying all 166 application
files against the checkout. Both artifacts excluded private notes, tests, environments,
caches and runtime data; the wheel included resources and license/notices. An isolated
tool install used explicit build-local `UV_TOOL_DIR`/`UV_TOOL_BIN_DIR`, Python 3.13.5
and the four runtime distributions pinned to 6.11.1 by the exported lock constraints.
All six GUI/CLI entry points were installed inside that disposable boundary.

The installed package was loaded from its wheel location, without the source tree
on its import path. Its shared delivery smoke exercised all four contracts, staged
supported upgrade, originals/corrections, scoring, search repair, refusal before
mutation, complete backup/reopen, CSV 6 and restart. It passed in separate processes
at Qt factors 1, 1.5 and 2. Light/Dark Journal, Performance and Settings captures at
1200 × 900 and the 760 × 520 logical minimum retained the toolbar controls. These are
offscreen Qt-scale probes; they do not certify actual Windows scaling, input methods
or every device. The standalone CLI version/export-help entry points also passed.
This is wheel/source-package evidence, not a new frozen executable validation.

## Recovery with the previous compatible build

A read-only comparison found all 118 installed application files matched public
`5f92ac0`. A separate rollback wheel was built from that Git snapshot and installed
only into another disposable tool directory. Neither the real installation nor a
stable/development personal database was opened or changed.

The previous-build delivery smoke produced a supported schema-20 four-contract
journal and complete backup. The candidate upgraded it to 21 after a synthetic review
of two Saved Views. Across 25 protected tables, all previous columns and rows were
preserved; only the selected retirement/provenance transition was admitted. Its
verified pre-upgrade recovery reopened in the previous build at schema 20 and matched
the original protected facts. That build also refused the upgraded active journal
without changing its bytes. This proves the prepared recovery route on disposable
data; it does not make reinstalling older code a downgrade of a live schema-21 journal.
Later work requires its own current backup and is absent from the older recovery copy.

## Handoff and limits

The accepted app and the technical results below support a separately reviewed
controlled adoption step. Keep the candidate/rollback artifacts,
constraints and personal recovery backups distinct. The existing source package still
reports 0.8.0, as does the older installed build; source/artifact identity matters.
No next release version was selected. Installation, personal-data movement or cleanup,
version/tag/merge and publication were not performed.

Generated artifacts, manifests, scripts, logs, screenshots and disposable journals
remain ignored under `build/ux-readiness/`. They are evidence inputs, not public assets
or build dependencies. Private decisions remain in their separate ignored repository.

## Final verification

The final source suite passed **1,281 tests in 504.26 seconds**, with zero failures,
errors or skips. Locked offline environment sync, Ruff check/format, both documentation
checks and both whitespace checks passed. Preservation checks retained all 66 J IDs,
42 R IDs and both withdrawals, unchanged reference assets, protected lower layers,
migrations/dependencies and ignored private notes.

After documentation alignment, the final wheel was rebuilt and checked against all
166 application files and the current README metadata. Fresh isolated final-wheel
and direct-source tool installations repeated the delivery smoke successfully. The
earlier three Qt-scale probes used the identical application payload; only README
metadata changed in the final rebuilt wheel. No source/runtime test result is claimed
for untested later code. Representative scaled Settings and final-wheel Journal
captures were inspected. The ordinary-use source-install flags and automatic creation
of the exported constraints directory were executed in the disposable boundary.

| Artifact | SHA-256 |
| --- | --- |
| Final candidate wheel | `b5319a08bdb83dd5117466810b9a97bacd2f52cbfdabfaf908309b911816a3fb` |
| Final source distribution | `259b0f2d373bf3ba2d0b290b8c956342f073ac87073a87509c877fc240c70c77` |
| Previous-code rollback wheel | `bc2fb9c1fc7d951120d37e59b229c9c3987451277a50b022eead7e62a071eb76` |

The controlled adoption procedure is ready for a separate installation/data decision.
No normal tool directory, personal database, package version/tag, branch merge or
publication was changed. The user owns the public/private checkpoint commits.

Final documentation checks covered 355 public and 292 private local links, with no
errors. The preservation audit verified 95 current public-reference mirrors and all
stable identifiers/withdrawals. Both Git indexes remain untouched by the agent.
