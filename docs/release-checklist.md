# Source release checklist

This checklist closes a Reckonsolve source release. It does not publish an installer, signed executable, update channel, package, or private PyInstaller artifact.

## Verify the candidate

1. Confirm `pyproject.toml` and `CHANGELOG.md` contain the intended release version and date.
2. Confirm `git status --short` contains only the intended release changes.
3. From the repository root, run:

   ```powershell
   uv sync --locked
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv run python tools/evaluate_search.py --size 2000
   powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
   ```

4. Run `uv run rscd --version` and confirm the release version.
5. Complete the release's manual acceptance record. For v0.7, use [the disposable visual-verification profiles](v0.6-visual-verification.md) for palette, scaling, window size, sidebar, and keyboard checks, then exercise current Binary and Numeric creation, revision, Review, Resolution, correction, scorecards, Analytics, and export. Do not use the stable database for test data.
6. Confirm schema version 18 and CSV export format 4. Verify a complete SQLite backup can reopen with both supported models and a repaired search index. Confirm generated `build\`, `dist\`, caches, temporary databases, presentation files, backups, and exports remain untracked.

## Publish the source release

1. Add the intended files, commit with the milestone's chosen message, and push the branch.
2. On GitHub, open **Releases**, choose **Draft a new release**, and create a new tag named exactly `vX.Y.Z` from the release commit on the default branch.
3. Use `Reckonsolve vX.Y.Z` as the release title and adapt the matching `CHANGELOG.md` entry as the release notes.
4. Mark it as the latest release when appropriate. Do not mark a stable source release as a prerelease.
5. Do not upload `dist\Reckonsolve` or the ignored private-smoke directory. GitHub automatically supplies source ZIP and tarball archives.
6. Publish the release and verify the tag and source archives point to the intended commit.

## Refresh the installed local tool

After the release commit is present in the local checkout, reinstall its non-editable snapshot and reopen the shell if needed:

```powershell
uv tool install --force .
rsc --version
```

This refreshes `reckonsolve`, `reckonsolve-cli`, `rsc`, and their development counterparts. It does not alter either stable or development SQLite data.

## v0.8 development: M59 manual acceptance

M59 is implemented and manually accepted. The user confirmed all checks below passed.
Use `uv run reckonsolve-dev` and development records. The v0.7 release checks above
describe that historical release. Current development uses schema 20; M59 adds no
migration. Format-5 export and v0.8 release/build validation remain M60 work.

- [x] Open Analytics: With Deadline is selected initially and existing deadline-based
  results are unchanged. Select One-Shot and confirm its Binary and Numeric sections
  are clearly identified; switching back restores the deadline-based view.
- [x] Check answered Binary One-Shots against their Detail Brier scores. For two 80%
  forecasts with one Yes and one No, mean Brier is 0.340, answered count is 2, and the
  80–89% bin shows count 2, mean forecast 80%, and observed Yes 50%. The table includes
  uncertainty; empty bins have zero count and unavailable values.
- [x] Check Numeric continuous-style and whole-number panels, including an answer on
  a saved quantile. Review five percentile rows, 50%/90% interval balances, and median
  ties. WIS remains in individual Detail; no aggregate WIS average appears.
- [x] Try Forecast type, tag, and Numeric exact-unit filters. A subset with no answers
  shows an honest empty state. Waiting for answer and Invalid records do not count.
- [x] Add an answer to a waiting One-Shot, then revisit Analytics: its count increases
  by one. Correct a copied forecast or answer: results change while the count stays
  fixed. Changing only reported times leaves the results unchanged.
- [x] Resize to a narrow window and back. Chart/table pairs stack without clipping;
  tables, counts, uncertainty, help, and the short caution remain readable. Tab through
  filters and Refresh, and inspect both light/dark palettes at your normal scaling.

Manual acceptance is complete; M59 is ready to commit. No stable-database test data or public release
is needed for these checks.
