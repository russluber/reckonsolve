# Reckonsolve

Reckonsolve is a local-first personal forecasting journal for Windows. It records binary probabilities and numeric prediction intervals, supports revising beliefs without rewriting history, resolves type-appropriate outcomes, and helps study calibration.

> Reckonsolve now has isolated development data, local action icons, and a validated private Windows build, but it is not ready for normal distribution. Original application-icon artwork, an installer, signing, and public binaries remain deferred.

The completed binary v0.1 baseline remains intact. Milestone 17 advances the approved staged v0.2 plan: **New Prediction** offers a Binary or Numeric interval choice, with Binary remaining the default quick path. Numeric Detail can append changed intervals, record type-anchored Journal history, resolve an exact realized value—including one outside the interval—or preserve an Invalid decision. Dashboard and Predictions now surface both forecast types clearly: Numeric summaries retain their confidence interval, median, and unit, and the archive adds an All types/Binary/Numeric filter alongside question, status, and tag filtering. Numeric analytics, type-aware export, and Forecast Reviews remain later v0.2 slices.

The current application can create a binary prediction from a question and any whole-number probability from 0% through 100%. A collapsed **More details** section accepts an optional initial rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags; the complete initial state and first forecast are saved atomically. Prediction Detail displays the current forecast and metadata, supports safe metadata editing, and can append probability revisions with an optional rationale without rewriting earlier forecasts.

Journal entries record evidence or reasoning without changing the forecast. Each entry preserves the forecast that was current when it was written, and revisions and Journal entries appear together in one timeline. Saved Journal text can be transparently corrected: the timeline marks it **Edited** and retains the original and every prior version in a collapsed edit history. Individual Journal entries cannot be deleted.

Prediction Detail also plots every saved forecast revision in a probability-history chart. The vertical scale always spans 0% through 100%, and a step line shows that each probability remains in force until the next revision. The horizontal scale uses the revisions' stored times and displays them locally; Journal entries do not add chart observations. The textual timeline remains the complete nonvisual record of the same forecast history.

Question, Resolution Criteria, and Forecast Deadline edits require tailored confirmation and remain visible in a collapsed Definition history. A Forecast Deadline is inclusive, so normal revisions stop after it passes while new Journal entries remain available. Resolved and Invalid predictions reject new entries, but existing entries can still receive audited corrections. Unchanged probabilities are not recorded as revisions; reasoning that leaves the probability unchanged belongs in the Journal. All of this history persists across restarts.

Open and Locked predictions can now be resolved Yes or No or marked Invalid. Resolution captures the exact final scoring revision plus optional factual notes and a reflective postmortem; invalidation preserves an optional reason and excludes the prediction from future scoring. Both are deliberate, immutable terminal decisions in v0.1. An untouched Open duplicate or test record can instead be permanently deleted after confirmation. Once a prediction is Locked, revised, edited, journaled, Resolved, or Invalid, its normal Delete action is unavailable and meaningful nonterminal history is directed toward Invalid.

The Dashboard now separates active work into overlapping Open, Needs Attention, Ready to Resolve, and Locked sections. Needs Attention uses the latest forecast revision, not Journal activity, and defaults to 14 elapsed days. The threshold persists in the application database and can be changed through the currently minimal Settings screen. Dashboard rows explicitly label Binary or Numeric forecasts, show the matching current forecast summary and update time, and open the corresponding Prediction Detail.

The Predictions screen now browses the complete archive, including Resolved and Invalid history for both forecast types. It supports case-insensitive question-text search plus combined lifecycle-status, forecast-type, and tag filters, shows each result's current type-appropriate forecast and status, and opens a freshly queried Prediction Detail. Search deliberately does not inspect Background, rationales, or Journal text in v0.1.

The Analytics screen scores each Resolved prediction exactly once using the ForecastRevision captured when it resolved; Open, Locked, and Invalid predictions are excluded. It shows the scored count and mean Brier score, a ten-bin calibration diagram with the perfect-calibration reference and visible bin counts, and clearly labeled cumulative mean Brier by resolution time. Lower Brier is better, while movement over time is not presented as proof of skill improvement. One tag filter recomputes all three views over the same subset.

Settings now creates a complete SQLite recovery backup at a chosen destination, verifies it before replacing an existing backup, and remembers the last successful backup time. It also exports a documented ZIP containing nine related CSV files for Binary Predictions, immutable history, lifecycle records, and tags. The CSV bundle is portable analytical data rather than a restoration format; its included README explains every relationship and convention. Until the type-aware CSV format arrives in M20, the application refuses CSV export when Numeric Predictions are present rather than silently omitting their interval data; use a SQLite backup for complete recovery.

The M12 visual pass uses a deliberately small, offline subset of Lucide icons while keeping action text and accessible names. Icons follow the active native Qt palette rather than imposing a custom theme. Development runs identify themselves as **Reckonsolve Dev** and use a separate database from the stable channel. A repeatable private PyInstaller `onedir` build now validates startup, icon resources, prediction creation, revision, Journal history, backup, and restart from the frozen executable. Original application-icon artwork still awaits user direction; a normal installer, signing, and public binary distribution are deliberately deferred.

## Documentation

- [Product specification](docs/product-spec.md) — implemented v0.1 behavior and the approved v0.2 contract, milestones, and acceptance criteria
- [Architecture](docs/architecture.md) — current implementation state and intended technical boundaries
- [Architecture decision records](docs/decisions/README.md) — durable reasoning for consequential technical choices

## Development

Reckonsolve uses Python 3.13, PySide6, SQLite, and `uv`.

```powershell
uv sync --locked
uv run reckonsolve-dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run reckonsolve-dev` is the normal source-development command. Its window title says **Reckonsolve Dev**, and it creates or opens an isolated development database, applies pending schema migrations, and keeps that database available until shutdown. `uv run reckonsolve` remains the stable-channel entry point and must not be used as an interchangeable development command because it opens the stable database location.

## Private Windows build

M12 includes a private smoke build, not an installer or public release:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The script synchronizes the locked `packaging` dependency group, builds `dist\Reckonsolve\Reckonsolve.exe`, copies that onedir bundle to a disposable ignored directory, and runs the frozen executable through an offscreen smoke workflow. The workflow uses only temporary data and checks a pending schema migration with preserved data, create, revise, Journal, backup, and restart persistence. `build\` and `dist\` are generated and must remain untracked. The frozen app intentionally has no original Reckonsolve application icon yet.

## Runtime data

On Windows, Reckonsolve stores its canonical database outside the repository at:

```text
%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3
```

Source-development runs instead use:

```text
%LOCALAPPDATA%\Reckonsolve Dev\reckonsolve.sqlite3
```

Each directory is selected through Qt's per-user local application-data location after its visible application identity is set. Reckonsolve never silently copies the stable database into the development location. Automated tests and frozen-build smoke checks inject temporary database paths and do not open either real user database. The application is local-only and does not require network access.

## License

Reckonsolve is licensed under the [MIT License](LICENSE).

The selected Lucide resources retain their upstream notices in [Third-party notices](THIRD_PARTY_NOTICES.md).
