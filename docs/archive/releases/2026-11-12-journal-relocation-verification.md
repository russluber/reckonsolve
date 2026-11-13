# Journal relocation verification — 2026-11-12

This records the unreleased [authorized fourth slice](../../product-spec.md#3813-authorized-fourth-implementation-slice-journal-relocation),
based on public `336abb5` (`ux-redesign`). The prior acceptance-only edits were already
present and preserved. The first three requested walkthroughs remain accepted with
their recorded limits. Source verification, the reported acceptance below and publication stay separate.

## Implemented package

Settings offers Choose folder, a selectable current/new/recovery review and deliberate
Move and restart. A shared identity-first GUI/CLI resolver keeps bootstrap metadata
and appearance/geometry separate from the active journal. Current clients coordinate
ordinary access and exclusive movement; native fencing also refuses older writable
handles. A complete checked image supplies verified destination/recovery copies,
including WAL facts. Persistent source read-only protection and notices prevent old
entry points from forking the journal. Pending phases require explicit recovery.

Restart recreates the runtime in the same process/identity, with fresh Journal state
and retained appearance/geometry. Failed unprotected movement reconnects current
operations; protected/uncertain failure blocks editing until recovery. Existing-only
startup refuses empty/unrelated/missing configured files before migration/initialization.
Supported older backup upgrade/refusal remains intact. The [ADR](../../decisions/0023-native-journal-relocation-and-recovery.md)
owns protocol reasoning, storage scope and exceptional source-retention details.

No personal journal was opened or moved. No installed tool/bundle, SQL schema,
immutable migration, score algorithm, search projection, CSV format or dependency was
changed. No Git staging, commit, tag, push or publication was performed by the agent.

## Verification

Final full suite: **1,208 tests passed in 423.29 seconds**, with zero failures,
errors or skips. Final focused relocation/UI checks passed **39**
cases; the combined run with archive retirement passed **69** in 33.79 seconds,
with no failures, errors or skips. An earlier broader run passed 125 GUI/CLI, restart, backup/smoke and relocation
checks before the final ownership tightening. Ruff check and formatting passed for the current source tree.

Coverage includes normal/repeated authority resolution, exact four-contract complete
images, committed WAL with a pinned read-only reader, immutable correction history,
modern shared/exclusive access, uncoordinated writable handles, native read-only source
protection, partial/truncated notice recovery, and process exit at preparing,
recovery-verified, copies-verified, source-protected, notice-written, locator-installed
and complete boundaries. Verified recovery never silently chooses a copy.

Historical source snapshots `bad5a09` and `336abb5` were exported locally to disposable
directories; their GUI and CLI startup refused the protected old path without changing
or recreating it. These historical tests may skip in a shallow checkout missing the
objects; they both ran in this evaluated checkout. The native VFS/handle tests remain
self-contained. No private notes are a runtime/test dependency.

Other checks cover conflicting files/identity roots, hard links/junction aliases,
space/permission failure, malformed/missing location state, replaced/changed copies,
generation mismatch, genuine creation versus an empty configured file, supported
older backup upgrade at the configured path, folder/review cancellation, failed-move
reconnection, blocked partial-move editing, paired CLI resolution, and the actual
QApplication restart loop with fresh state and retained appearance.

Documentation checks passed **312 public / 290 private local links**, across 55/5
Markdown files, with zero errors. The preservation audit verified **86** local
mirrors of current public references, all 66 J / 42 R IDs and withdrawals, unchanged
R1/R2 assets, protected modules/migrations/dependencies and ignored private notes.
Both Git whitespace checks passed. The relocation profile/help example was checked
against its parser and executed using injected disposable roots. Earlier
development failures are superseded by the final results, not claimed as passing
evidence. The empty-file startup regression was reproduced before its narrow fix.

### Native capture and timing sample

Pinned Python 3.13.5 / PySide6 6.11.1, actual offscreen Qt and Segoe UI metrics, local
fixed NTFS on the available C: volume. Captures include Light/Dark Settings/review,
a smaller review with 12-point text and reachable buttons, and fresh Journal after
movement. Generated files remain ignored under `build/ux-relocation/`; R1/R2 references
were not altered. These are executable captures, not new design mockups.

On the disposable 28-prediction Detail fixture, folder review took about **29 ms**;
movement, verification and old-window close took about **250 ms**. The latter excludes
new-window construction. These are local observations, not latency promises for large
archives or other devices. Separate process interruption was tested; physical power
cuts/controller failures, a second physical volume and the full native Windows
scaling/focus/accessibility matrix were not individually exercised. No cross-volume
atomic data rename is assumed: destination/recovery images are written independently.

## One bounded native handoff

Run `uv run python tools/run_visual_review.py relocation` from the project root. It
prints the temporary parent containing **New journal folder** and **Another journal
folder**. Use only those precreated destinations. The profile contains 13 Predictions
(three answered per contract plus an unresolved-only case); all data/config stay in
that disposable tree and are discarded after the final window closes.

1. Cancel folder selection and then cancel the current/new/recovery review. The
   Settings location and journal remain unchanged.
2. Choose New journal folder and Move and restart. Check fresh Journal, all four
   prediction contracts/history and Performance counts, retained appearance/window
   size, and the new Settings path. No earlier draft/report/search state should return.
3. Try the current folder to see the explicit conflict with no overwrite; then review
   Another journal folder and cancel, or complete a second move. Check readable paths,
   persistent failure, both palettes and reachable controls in a smaller window.

Concurrency, refusal and forced interruption are covered by disposable automation;
do not manufacture them on a personal journal. The reported acceptance below closes
this requested walkthrough. Final integrated redesign acceptance and installed-tool
replacement/publication remain later.

## Reported slice 4 acceptance — 2026-11-12

The user accepted the supplied relocation walkthrough, reported “Everything’s good,”
and reported staging, committing and pushing both checkpoints. Public `ux-redesign`
was verified clean at `961d202` (`feat: add recovery-backed journal relocation and restart`),
matching its locally cached upstream reference, before this acceptance update.
Push completion is user-reported; the agent did not fetch, stage, commit or push.

This closes the requested fourth-slice native-review gate with the limits above.
All four requested software-slice walkthroughs are now accepted with recorded limits.
No defect was reported, and no already accepted preference or journey is reopened.
This does not establish every scaling/accessibility/device condition, physical
power-loss resilience or final integrated redesign acceptance.

The next gate is a final integrated review: reconcile the implemented package and
current documentation with the approved contract, carry forward existing test and
human evidence, and identify only actual gaps that still need a decision or bounded
review. Installed-tool replacement, personal journal operations, packaging, version/tag
selection and publication remain separate, unperformed steps.

This acceptance update changes documentation only. Public/private link/reference,
stable-ID/asset preservation and whitespace checks passed. The 1,208-test source result
above remains tied to `961d202`; no redundant runtime suite was run for these edits.
