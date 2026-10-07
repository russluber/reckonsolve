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

When default caches are restricted, use `uv --cache-dir .uv-cache ...`; pytest can use `--basetemp build/pytest-tmp` and `-p no:cacheprovider`. Create the parent `build/` directory first if it is absent. Keep temporary reports, logs, screenshots, scratch scripts, and disposable test data under ignored `build/<task>/` or a system temporary directory. Generated caches and test artifacts remain untracked.

Test domain validation and exact analytics independently of Qt. Use temporary SQLite files for migrations, rollback, corrections, concurrency, search, backup, export, and restart. Use pytest-qt where actual widget interaction matters. Source and packaged launchers must enforce the same supported-contract boundary.

The [search evaluation procedure](search-evaluation.md) supplies a disposable relevance and large-corpus check. Timings are evidence for a particular run, not machine-independent thresholds.

### Main window tests

`tests/test_main_window.py` covers the application shell, navigation, keyboard shortcuts, and themes. Workflow tests live in separate `test_*_ui.py` modules for creation, browsing, search, Dashboard, Detail, metadata, revisions, Journals, terminal actions, Settings, and tag management.

Shared application fakes live in `tests/main_window_fakes.py`; widget helpers and function-scoped fixtures live in `tests/main_window_helpers.py`. Import fixtures explicitly into the modules that use them, keeping their scope local to those tests.

Run the module for the workflow you are changing, for example:

```powershell
uv run pytest tests/test_prediction_creation_ui.py
```

## Disposable visual review

```powershell
uv run python tools/run_visual_review.py empty
uv run python tools/run_visual_review.py representative
uv run python tools/run_visual_review.py long-text
```

These profiles create temporary database and presentation files without opening either personal database. Closing the app cleans up temporary directories. The profiles cover their seeded records; exercise additional One-Shot scenarios with disposable paths or development records when a change affects them.

Review affected screens in light/dark palettes, relevant Windows scaling settings, normal/narrow widths, and expanded/compact sidebar modes. Check wrapping, complete dates, badges, focus, keyboard navigation, dropdowns, errors, empty states, and long selectable text. Charts need text alternatives. Preserve browsing context on Detail return.

Human visual acceptance is separate from offscreen Qt tests. Dated acceptance belongs in [the archive](../archive/README.md), not this repeatable procedure.

## Documentation checks

After editing or moving documentation, run:

```powershell
uv run python tools/check_docs.py
git diff --check
```

The checker requires a Git checkout and Git on PATH. It reads tracked and new unignored Markdown files, including the archive and bundled attribution documents. It checks local inline/image/reference links, Markdown section anchors, and explicit HTML anchor tags, ignoring code examples and comments. Paths beginning with `/` resolve from the repository root. Failures include file/line locations and exit with status 1; discovery failures exit with status 2. It runs offline and changes no files.

Heading anchors follow the basic [GitHub rules](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links), including duplicate-heading suffixes. Unusual Markdown/HTML still needs rendered review. External URLs and bare/backticked file paths are outside the check; use `rg` for obsolete paths and review external destinations separately.

Use `$...$` for inline mathematics and `$$` on separate lines for equation blocks, with blank lines around each block. These delimiters work in [GitHub Markdown](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/writing-mathematical-expressions) and [VS Code's built-in preview](https://code.visualstudio.com/docs/languages/markdown#math-formula-rendering). Keep mathematical meaning unchanged when fixing rendering. Use plain text or code formatting for command syntax and simple calculations intended to appear literally. Preview complex equations as well as running the link checker; it does not validate mathematics.

In mathematics, set named scores/operators such as `\operatorname{WIS}` and `\operatorname{Brier}` upright with `\operatorname{...}`. Put word subscripts and superscripts in `\text{...}`, for example `\operatorname{WIS}_{\text{initial}}` and `t_{\text{revision}}`. Keep variable indices and numeric indices in ordinary math notation.

## Private Windows build

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The script uses pinned PyInstaller in the separate `packaging` group and creates a private `onedir` GUI bundle. It verifies local styles/icons and runs disposable frozen smoke checks covering all four contracts, supported upgrades, unsupported refusal, search repair, mode-filtered Saved Views, analytics, format-5 export, backup, and restart.

Builds and smoke artifacts stay in ignored `build/` and `dist/`. Relocation checks run the copied bundle with its bundled runtime and explicit disposable data. Private artifacts are not public release assets, installers, or signed distributions.

Follow the [release checklist](release-checklist.md) for source publication. Record checks with their actual code/version and limits; earlier acceptance is not evidence for later edits.
