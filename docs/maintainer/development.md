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

## UX design and review

Use this procedure for the [active UX redesign charter](../product-spec.md#active-ux-redesign-charter). The [master redesign](design/reckonsolve-experience-redesign.md) owns the overall roadmap, progress, shared dependencies, and contract differences; detailed chapters own their requirements and local review cases. Keep both layers current after each exercise. Chat discussions inform the work; the owning repository documents hold the current result.

### Run a design exercise

1. **Choose a journey.** Read the master, the affected chapter, and the relevant current contract. State the user's task, trigger, success condition, modes/types/states, and the particular uncertainty to resolve. Follow repository instructions on specification reading; check for intervening changes before relying on earlier conclusions.
2. **Understand the baseline.** Inspect relevant current behavior, implementation, or existing test coverage as needed. Distinguish observed use, specification requirements, static inspection, and reproduced runtime behavior. Record discrepancies separately; discovering one grants no permission to fix it.
3. **Explore alternatives.** Compare written flows or wireframes and their tradeoffs. Document proposed departures from current presentation/workflow requirements in the master's contract-alignment register. Preserve protected rules and surface scope/invariant changes explicitly. Creating/running an executable prototype requires a stated scope beyond a documentation-only edit; use disposable data within that scope.
4. **Record the decision.** Update the owning decision/requirement or issue with its ID, user need, preferred direction, reason, open questions, relevant contract links, maturity, and evidence or validation still needed. Reuse existing J/R IDs; preserve withdrawn items. Link between related items instead of copying their full text or creating one document per conversation.
5. **Review the journey.** Walk through task-based scenarios and the conditions below using the artifact actually available. Record what was evaluated, its revision, findings, and limits. A written walkthrough, static mockup, interactive prototype, and running app provide different evidence; none proves a test that was not performed.
6. **Close the exercise.** Update the chapter's local backlog and the master's progress/next exercise. Record meaningful user acceptance at the level actually given. Check changed documentation links/references and diffs. Leave unresolved issues visible; do not promote a preference merely because it has been written down.

### Design maturity and authorization

| Label | Meaning |
| --- | --- |
| **Exploring** | Need, alternatives, or interaction questions are still being investigated. |
| **Preferred** | The user has selected a direction for further specification; relevant validation remains. |
| **Validated** | The specified journeys were evaluated against recorded review conditions; evidence and remaining limits are linked. This label claims only the scope actually evaluated. |
| **Approved design** | The user explicitly accepted the specified target UX and its criteria; relevant open issues and contract differences are resolved for that scope. |
| **Withdrawn** | Rejected direction retained for traceability; not a pending or deferred feature. |

An **observed need** is an evidence description, not a maturity or authorization level. Track implementation authorization independently, naming the explicitly authorized slice and its boundaries; otherwise it remains **Not authorized**. No maturity label, prototype approval, or document version authorizes production changes. Track implemented, manually accepted as software, and published status separately from design maturity.

### Review conditions and evidence

Review the relevant paths at approximately **760 × 520 logical pixels**, ordinary larger windows, **100%/150%/200% Windows scaling**, and both system palettes. Cover keyboard-only and pointer/trackpad use, meaningful accessible names, logical/visible focus and restoration, text alternatives for charts, and long wrapped/selectable text. Check full Numeric values/units, empty optional content, sparse/large histories, corrected and superseded text, and empty results versus errors.

For navigation, verify search/filter/sort/Saved View and scroll restoration, matched-history destinations, and changed query membership. For drafts, cover editor/context and mode/type switches, Back/global navigation, Escape/window close, cancelled confirmations, validation/lock/stale-context failures, and expired Adaptive eligibility. Check deliberate terminal decisions and faithful original/effective facts. Review only applicable cases and document gaps rather than declaring the whole redesign validated.

Prototype and runtime reviews use disposable records and presentation settings, never stable personal data. The existing [disposable visual profiles](#disposable-visual-review) exercise the current app and do not demonstrate the proposed redesign. Evidence must identify whether it came from a design artifact or executable behavior. Keep temporary captures/reports under ignored `build/<task>/` or a system temporary directory. Link concise design findings from the owning chapter; preserve dated software acceptance evidence in the archive when that phase is reached.

### Completion gate and handoff

For a proposed software slice, assemble the approved journeys, mode/type/lifecycle coverage, applicable decision IDs, empty/failure and draft-exit behavior, accessibility/responsive criteria, and linked review evidence. Resolve its contract differences in the specification and label approved future requirements explicitly, keeping current behavior recognizable. Obtain design acceptance and a separate explicit implementation instruction for the slice; approval may cover several steps when the user's instruction clearly does so.

After authorized implementation, run appropriate runtime/regression checks and human visual acceptance, update the current specification and affected guides/architecture, and retain dated evidence. Documentation-only passes need the [documentation checks](#documentation-checks), not a redundant runtime suite or a claim of UI acceptance. Use ADRs for consequential technical approaches rather than recording each UX preference as an architecture decision.

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
