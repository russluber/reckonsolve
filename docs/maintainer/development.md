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

Journal/workspace regressions use injected temporary journals in `test_journal_workspace.py`, `test_journal_controls.py`, `test_journal_retrieval.py` and the 2,000-record `test_journal_response_budget.py`. Recovery/writer exclusion lives in `test_upgrade_protocol.py`. Older browser/Dashboard UI assertions were replaced by these current journeys; historical migration tests still exercise their original schemas.

On Windows, Qt's offscreen plugin may expose no fonts. `tests/conftest.py` then loads installed Segoe UI faces for genuine metrics; missing-glyph-box measurements are not UI evidence. This adds no bundled font or production dependency. Human Windows/scaling acceptance remains required.

`tests/test_main_window.py` covers the application shell, navigation, keyboard shortcuts, and themes. Workflow tests live in separate `test_*_ui.py` modules for creation, browsing, search, Dashboard, Detail, metadata, revisions, Journals, terminal actions, Settings, and tag management.

Shared application fakes live in `tests/main_window_fakes.py`; widget helpers and function-scoped fixtures live in `tests/main_window_helpers.py`. Import fixtures explicitly into the modules that use them, keeping their scope local to those tests.

Run the module for the workflow you are changing, for example:

```powershell
uv run pytest tests/test_prediction_creation_ui.py
```

## Exploratory design work

Private design charters, workshop procedures, exploratory decisions, and validation backlogs live in the optional, Git-ignored `notes/` folder. When it is available for an authorized design task, follow its `README.md`. The public project and its checks work without it. Before implementation, deliberately publish accepted requirements under the [specification's authorization rules](../product-spec.md#proposed-changes-and-authorization) and confirm the software slice; design approval is separate from implementation authorization.

## Disposable visual review

```powershell
uv run python tools/run_visual_review.py empty
uv run python tools/run_visual_review.py representative
uv run python tools/run_visual_review.py long-text
uv run python tools/run_visual_review.py detail
```

These profiles create temporary database and presentation files without opening either personal database. Closing the app cleans up temporary directories. Representative and long-text profiles include all four forecasting contracts, a waiting One-Shot and already-Locked Adaptive examples. Use these injected profiles for Journal, creation and Detail review; no personal upgrade or installed-tool replacement is needed.

The `detail` profile has 28 examples: the ten representative records, ten controlled cutoff/unscored/corrected-Invalid/waiting cases, and eight finishing cases. Search for **Earlier forecast scored**, **No eligible forecast**, **Corrected Invalid reason**, **Waiting for answer**, **Long history**, **Reflection history**, **Corrected exercise**, **All equal**, or **Nearby percentiles**. Long histories have 25 complete Adaptive forecasts plus Journals, Reviews and protected Definition/Journal corrections. Corrected exercises expose One-Shot transcription and later reflection provenance. All facts are seeded through ordinary application operations with controlled clocks.

Review affected screens in Follow Windows, Light and Dark, relevant Windows scaling settings and normal/minimum supported widths. There is no sidebar in the first Journal/workspace slice. Check wrapping, complete dates, badges, focus, keyboard navigation, dropdowns, errors, empty states, and long selectable text. Charts need text alternatives. Preserve browsing context on Detail return.

Human visual acceptance is separate from offscreen Qt tests. Dated acceptance belongs in [the archive](../archive/README.md), not this repeatable procedure.

### New Prediction and Detail review

Use the `detail` profile for one combined completion review. Keep all new records in that disposable window; representative and long-text remain useful smaller profiles.

1. **Read results and reflect.** Open Earlier forecast scored, No eligible forecast and Reflection history for both Adaptive types. Check the outcome/score, collapsed eligible forecast, Overview notes/reflection/score details, and Write/Edit Postmortem or Skip beside More. Write/edit reflection while consulting saved context; verify the saved version and actual terminal event order. Numeric Latest committed distribution must remain distinct from an earlier scored forecast. Check all four Corrected Invalid reason cases, last forecasts and More repairs.
2. **Read and revise long histories.** Open Long history for each Adaptive type. Check the full Question, Current revision jump, both Timeline orders, expanded Journal text/history and long criteria reader. Revise, consult Overview, switch appearance and return to retained inputs; commit a change. Try Journal/New/Back with entered work, keeping it before testing explicit discard. All equal and Nearby percentiles exercise exact tie/connector labels and long units.
3. **Inspect corrected exercise history.** Open Corrected exercise for both One-Shot types. Check effective forecast/answer/score, inline reflection, visible Journals, original facts and separately labeled transcription/reflection updates. Search **birchbeacon** or **copperbridge**: ordinary search must exclude the superseded-only word; Include superseded history must reveal its exact original Journal or Question version. Return to the preserved Journal retrieval. Try More → Correct transcription, review and Back without saving.
4. **Complete remaining task routes.** On disposable Open/Locked examples, prepare Resolve or More → Mark Invalid, return from confirmation to retained inputs, then confirm. Add a later answer to Waiting for answer for each One-Shot type. Create each mode/type combination; test crossed Numeric inputs, source-aware cancellation and ordinary/answered save landings. Earlier accepted creation behavior remains a regression constraint.

Repeat affected states at the supported minimum and 100%/150%/200% Windows scaling, using the fallback scroll when tall content exceeds a short window. Inspect keyboard focus, reachable Save/Cancel, modal boundaries and both appearances. Record the evaluated source and any limits; a passing automated capture does not substitute for these judgments.

For a focused long-history responsiveness recheck, open the `detail` profile and search **Long history**. In both Adaptive types, alternate Newest first / Oldest first, open Resolve and Keep forecast, then cancel. Open Revise, enter a draft and alternate Overview / Revision: movement should be smooth in both directions and retain inputs. Save one Review and verify the appended event, retained forecast and prompt next task opening. Repeat in both appearances and a smaller window; normal wrapping and scrolling must return after movement. If Windows disables animations, the pane change is immediate by design. Carry the other combined-review feedback forward rather than repeating that whole checklist for this repair.

### Performance and ordinary Settings review

```powershell
uv run python tools/run_visual_review.py performance
```

This disposable profile seeds 12 answered observations per contract, both Numeric value constraints and two exact units, tagged/untagged predictions, updating and corrected One-Shot facts. **No results yet** belongs only to an unresolved prediction. It opens the same isolated temporary application identity as the other profiles; no personal journal is used. Close the window to discard the fixture. The `empty` profile remains useful for whole-report emptiness.

1. Open Performance and inspect both paired rows, scroll through One-Shot, expand calibration tables and Numeric supporting detail. Compare normal/minimum widths and Light/Dark. The introduction scrolls away while one Tag/Reset strip stays visible; charts have counts and text alternatives.
2. Filter Work/Personal; set different units in the two Numeric sections. Visit Settings and use Back: selections, disclosures and useful report position remain while committed results refresh. Select No results yet to check truthful zero observations. Reset View restores All tags/both All units, collapsed details and the top without deleting data.
3. In Settings, save a disposable backup/export under an ignored build folder or a temporary directory, repair search, and try confirmed tag maintenance. Each latest result stays beside its tool; paths/errors can be selected. Cancelled file dialogs change nothing. Leave/re-enter Settings to clear visit results while Last successful backup remains. Back returns through Performance to its independent origin. All changes stay in this temporary journal.

Automated fault injection separately covers isolated/whole-report failure, retry, unit disappearance, failed tag reads, confirmed merge provenance, stale worker publication and global archive refusal. It never corrupts a personal database to manufacture an error. The native pass remains an acceptance input for actual Windows focus, scaling and perceived responsiveness.

### Journal relocation review

```powershell
uv run python tools/run_visual_review.py relocation
```

This managed disposable profile contains 13 predictions: three answered per contract plus one unresolved-only case. It prints the temporary parent containing **New journal folder** and **Another journal folder**. Use only these precreated destinations; source, recovery, metadata and moved journals remain in that temporary tree and are discarded after the final window closes. Other explicit-file profiles intentionally bypass user bootstrap and do not expose relocation.

1. In Settings, cancel folder selection and then cancel a review. Check unchanged current location and data. Review the current/new/recovery paths in both appearances and a smaller window; long paths remain selectable and Move and restart/Cancel remain reachable.
2. Choose New journal folder and Move and restart. Check fresh Journal, all four contracts/history and Performance counts, the new Settings path, retained appearance/window size, and fresh transient browsing/report state.
3. Select the current folder to check an explicit conflict without overwrite. Review Another journal folder and cancel, or complete a second move. Confirm failure remains readable beside location controls and that unrelated Settings tools still behave normally.

Automated native tests separately cover shared/exclusive access, older GUI/CLI handles/entry points, committed WAL, refused archives, exact complete images and killed-process recovery at every phase. They never move a personal journal or force-close another process. Source smoke/restart/backup tests remain part of the full suite; no frozen bundle or installed tool is replaced by these source checks. Read [ADR 0023](../decisions/0023-native-journal-relocation-and-recovery.md) before changing ordering/ownership, and retain the evaluated source/device limits in the [dated record](../archive/releases/2026-11-12-journal-relocation-verification.md).

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

The script uses pinned PyInstaller in the separate `packaging` group and creates a private `onedir` GUI bundle. It verifies local styles/icons and runs disposable frozen smoke checks covering all four contracts, supported upgrades, unsupported refusal, search repair, mode-filtered retrieval, analytics, format-6 export, backup, and restart.

Builds and smoke artifacts stay in ignored `build/` and `dist/`. Relocation checks run the copied bundle with its bundled runtime and explicit disposable data. Private artifacts are not public release assets, installers, or signed distributions.

Follow the [release checklist](release-checklist.md) for source publication. Record checks with their actual code/version and limits; earlier acceptance is not evidence for later edits.
