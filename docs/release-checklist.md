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
5. Manually exercise the milestone checklist in the development identity. Do not use the stable database for test data.

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
