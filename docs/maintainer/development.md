# Development and testing

Read [repository instructions](../../AGENTS.md), the [product specification](../product-spec.md), and the [architecture](../architecture.md) before changing behavior or boundaries.

## Source setup

Python is pinned in `.python-version`; dependencies and entry points are declared in `pyproject.toml` and locked in `uv.lock`.

```powershell
uv sync --locked
uv run reckonsolve-dev
uv run rscd --help
```

Development GUI/CLI use `%LOCALAPPDATA%\Reckonsolve Dev`, separate from stable personal data. Manual development entries persist there. Automated tests inject temporary paths and must never discover either real database.

An installed `uv tool` is a separate source snapshot. `uv tool install --force .` refreshes bare commands; `uv run` uses the checkout environment.

## Quality checks

During iteration, run narrow checks for the affected behavior. Before closing an implementation milestone, run:

```powershell
uv run pytest
uv run ruff check .
uv run ruff format --check .
git diff --check
```

When default caches are restricted, use `uv --cache-dir .uv-cache ...`; pytest can use `--basetemp .pytest-tmp` and `-p no:cacheprovider`. Generated caches and test artifacts remain ignored.

Test domain validation and exact analytics independently of Qt. Use temporary SQLite files for migrations, rollback, corrections, concurrency, search, backup, export, and restart. Use pytest-qt where actual widget interaction matters. Source and packaged launchers must enforce the same supported-contract boundary.

The [search evaluation procedure](search-evaluation.md) supplies a disposable relevance and large-corpus check. Timings are evidence for a particular run, not machine-independent thresholds.

## Disposable visual review

```powershell
uv run python tools/run_visual_review.py empty
uv run python tools/run_visual_review.py representative
uv run python tools/run_visual_review.py long-text
```

These profiles create temporary database and presentation files without opening either personal database. Closing the app cleans up temporary directories. The profiles cover their seeded records; exercise additional One-Shot scenarios with disposable paths or development records when a change affects them.

Review affected screens in light/dark palettes, relevant Windows scaling settings, normal/narrow widths, and expanded/compact sidebar modes. Check wrapping, complete dates, badges, focus, keyboard navigation, dropdowns, errors, empty states, and long selectable text. Charts need text alternatives. Preserve browsing context on Detail return.

Human visual acceptance is separate from offscreen Qt tests. Dated acceptance belongs in [the archive](../archive/README.md), not this repeatable procedure.

## Private Windows build

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The script uses pinned PyInstaller in the separate `packaging` group and creates a private `onedir` GUI bundle. It verifies local styles/icons and runs disposable frozen smoke checks covering all four contracts, supported upgrades, unsupported refusal, search repair, mode-filtered Saved Views, analytics, format-5 export, backup, and restart.

Builds and smoke artifacts stay in ignored `build/` and `dist/`. Relocation checks run the copied bundle with its bundled runtime and explicit disposable data. Private artifacts are not public release assets, installers, or signed distributions.

Follow the [release checklist](release-checklist.md) for source publication. Record checks with their actual code/version and limits; earlier acceptance is not evidence for later edits.
