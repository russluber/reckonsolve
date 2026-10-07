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
5. Complete the release's manual acceptance record below. Use [the disposable visual-verification profiles](v0.6-visual-verification.md) for palette, scaling, window size, sidebar, and keyboard checks, then exercise Adaptive and One-Shot Binary/Numeric workflows. Do not use the stable database for test data.
6. Confirm schema version 20 and CSV export format 5. Verify a complete SQLite backup can reopen with all four supported contracts and a repaired search index. Confirm generated `build\`, `dist\`, caches, temporary databases, presentation files, backups, and exports remain untracked.

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
migration. Format-5 export and v0.8 release/build validation were assigned to M60.

- [x] Open Analytics: Adaptive is selected initially and existing Adaptive
  results are unchanged. Select One-Shot and confirm its Binary and Numeric sections
  are clearly identified; switching back restores the Adaptive view.
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

## v0.8 development: M60 final manual acceptance

M60 implements format-5 export and the v0.8.0 source candidate on schema 20. Automated
validation is recorded in [the validation record](v0.8-validation.md). M57–M59 are
already accepted; these final checks focus on portability and the assembled release.

The user confirmed all M60 checks passed. Closeout refinements use yellow Waiting for
answer badges and blue Needs Postmortem badges, remove the desktop commitment-guidance
expander and extra Deadline explanations, and use sentence case in creation copy.
The user selected Adaptive for the regular mode; the interface and current docs use
that name. Stored identities and mode filters are unchanged; CLI `--mode adaptive`
also accepts `--mode deadline` for compatibility.

- [x] In `uv run reckonsolve-dev`, export a development archive containing Adaptive
  and One-Shot Binary/Numeric records from Settings. Open the ZIP: README says format 5;
  the three `one_shot_*.csv` files contain originals, effective facts, and corrections.
  Check one corrected record against Detail, including reported times and exact values.
- [x] Export the same development archive with `uv run rscd export-csv PATH.zip`.
  Confirm the CLI reports format 5 and agrees with the desktop export's history.
- [x] Create a SQLite backup from Settings and confirm its destination is clearly shown.
  The automated disposable recovery checks reopen backups; do not replace your real
  database for this review. Confirm cancellation leaves an existing destination alone.
- [x] Check the assembled application at your normal scaling and preferred palette:
  both creation modes, reported-time entry, One-Shot Detail/history, Predictions filters,
  Analytics mode switch, Settings export, and keyboard navigation. Existing M57–M59
  acceptance covers their detailed behavior; report any regression in this candidate.
- [x] Confirm `uv run rscd --version` reports 0.8.0 and review the
  [v0.8 release notes](v0.8-release-notes.md). Accept M60 before changing the changelog's
  Unreleased heading to the actual release date and publishing a tag/source release.

No installer or private frozen artifact is published by this milestone.
