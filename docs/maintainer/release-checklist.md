# Source release checklist

Use this repeatable process for a source release. Completed acceptance and dated test results belong in [the archive](../archive/README.md), not in the next release's checklist. The current baseline is v0.8.0, schema 20, CSV format 5, and four supported contracts; a later authorized release must state its own baseline.

## Verify the candidate

1. Confirm the package version, changelog entry, intended branch/commit, and Git status.
2. From the repository root, run:

   ```powershell
   uv sync --locked
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   git diff --check
   uv run python tools/evaluate_search.py --size 2000
   powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
   ```

3. Check `uv run rscd --version` and affected command help.
4. Complete a focused human Windows checklist for the changed workflows, including both types/modes where affected. Use [disposable visual profiles](development.md#disposable-visual-review) for palettes, scaling, widths, sidebar, keyboard, and wrapping. Do not use stable personal data for fixtures.
5. Verify supported upgrades, refusal before mutation, search repair, separate analytics, backup/reopen, and complete CSV/dictionary output. Confirm generated artifacts remain ignored.
6. Record actual results and their limits, including whether full-suite/private-build results precede final edits. Update current guides/spec/architecture only where behavior changed. Do not reuse old acceptance as evidence for new code.

## Publish the source release

1. The user adds the intended changes, commits, and pushes unless publishing is explicitly delegated.
2. On GitHub, open Releases, draft a release, and create `vX.Y.Z` from the intended release commit on the default branch.
3. Use `Reckonsolve vX.Y.Z` as the title and the matching [changelog](../../CHANGELOG.md) entry as the notes. Keep the changelog release date aligned with publication (UTC).
4. Select latest when appropriate; do not mark a stable source release as prerelease.
5. Publish and verify the tag/source archives point to the intended commit. Do not upload ignored private frozen builds. GitHub supplies the source ZIP/tarball.
6. Update any remaining candidate wording after publication. There is no separate maintained release-note draft in the active docs.

## Refresh the installed tool

From the updated checkout:

```powershell
uv tool install --force .
rsc --version
```

Reopen the shell if needed. This refreshes GUI/CLI scripts and their development counterparts, not either database.
