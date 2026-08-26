# Reckonsolve

Reckonsolve is a local-first personal forecasting journal for Windows. It records binary probabilities and numeric prediction intervals, supports revising beliefs without rewriting history, resolves type-appropriate outcomes, and helps study calibration.

> Reckonsolve now has isolated development data, local action icons, and a validated private Windows build, but it is not ready for normal distribution. Original application-icon artwork, an installer, signing, and public binaries remain deferred.

The completed binary v0.1 baseline remains intact. The staged v0.2 plan is complete: Binary and Numeric Prediction Detail record immutable Forecast Reviews while Open, using **Still at N%** or **Keep this interval**. Each Review preserves the exact retained revision, appears in the timeline, and refreshes Needs Attention without fabricating a revision, chart point, or scoring observation. Type-aware recovery, CSV export, migration, and private-build smoke coverage preserve both forecast models and Reviews.

v0.3 development now includes a command-line companion for reading and creating forecasts. `reckonsolve-cli-dev` shares the isolated development database used by `reckonsolve-dev`; the stable `reckonsolve-cli` command likewise shares the stable GUI database. M21 provides filtered Prediction listings and complete type-aware textual detail/history, and M22 adds interactive Binary and Numeric creation. Other CLI mutations arrive in later v0.3 milestones.

The current application can create a binary prediction from a question and any whole-number probability from 0% through 100%. A collapsed **More details** section accepts an optional initial rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags; the complete initial state and first forecast are saved atomically. Prediction Detail displays the current forecast and metadata, supports safe metadata editing, and can append probability revisions with an optional rationale without rewriting earlier forecasts.

Journal entries record evidence or reasoning without changing the forecast. Forecast Reviews instead record that the user deliberately reconsidered the current forecast and retained it unchanged; an optional Review note can preserve that context. Each event keeps its exact type-appropriate forecast anchor, and revisions, Journals, and Reviews appear together in one timeline. Saved Journal text can be transparently corrected: the timeline marks it **Edited** and retains the original and every prior version in a collapsed edit history. Individual Journal entries and saved Reviews cannot be deleted.

Prediction Detail also plots every saved forecast revision in a probability-history chart. The vertical scale always spans 0% through 100%, and a step line shows that each probability remains in force until the next revision. The horizontal scale uses the revisions' stored times and displays them locally; Journal entries do not add chart observations. The textual timeline remains the complete nonvisual record of the same forecast history.

Question, Resolution Criteria, and Forecast Deadline edits require tailored confirmation and remain visible in a collapsed Definition history. A Forecast Deadline is inclusive, so normal revisions and Forecast Reviews stop after it passes while new Journal entries remain available. Resolved and Invalid predictions reject new entries and Reviews, but existing Journal entries can still receive audited corrections. Unchanged probabilities are not recorded as revisions: use a Forecast Review for deliberate reconsideration and retention, or a Journal entry for ordinary evidence and reasoning. All of this history persists across restarts.

Open and Locked predictions can now be resolved Yes or No or marked Invalid. Resolution captures the exact final scoring revision plus optional factual notes and a reflective postmortem; invalidation preserves an optional reason and excludes the prediction from future scoring. Both are deliberate, immutable terminal decisions in v0.1. An untouched Open duplicate or test record can instead be permanently deleted after confirmation. Once a prediction is Locked, revised, edited, journaled, Resolved, or Invalid, its normal Delete action is unavailable and meaningful nonterminal history is directed toward Invalid.

The Dashboard now separates active work into overlapping Open, Needs Attention, Ready to Resolve, and Locked sections. Needs Attention uses the later of the latest forecast revision or Open-state Forecast Review, never Journal activity, and defaults to 14 elapsed days. The threshold persists in the application database and can be changed through the currently minimal Settings screen. Dashboard rows explicitly label Binary or Numeric forecasts, show the matching current forecast summary and **Forecast last considered** time, and open the corresponding Prediction Detail.

The Predictions screen now browses the complete archive, including Resolved and Invalid history for both forecast types. It supports case-insensitive question-text search plus combined lifecycle-status, forecast-type, and tag filters, shows each result's current type-appropriate forecast and status, and opens a freshly queried Prediction Detail. Search deliberately does not inspect Background, rationales, or Journal text in v0.1.

The Analytics screen scores each Resolved prediction exactly once using the type-appropriate ForecastRevision captured when it resolved; Open, Locked, and Invalid predictions are excluded. Binary views retain mean Brier, ten-bin reliability, and cumulative mean Brier by resolution time. Numeric views show ten-bin containment calibration using actual mean confidence, observed inclusive containment, and visible counts. Unitless containment may combine units; raw median absolute error, interval width, and proper interval score stay unavailable until the Numeric view selects one exact unit. Forecast type, tag, and unit filters recompute every visible value over one consistent subset.

Settings creates a complete SQLite recovery backup at a chosen destination, verifies it before replacing an existing backup, and remembers the last successful backup time. It also exports a documented format-version-two ZIP containing twelve related CSV files for Binary and Numeric Predictions, immutable revisions, Reviews, lifecycle records, and tags. The CSV bundle is portable analytical data rather than a restoration format; its included README explains every relationship, fixed-precision Numeric convention, and timestamp/date convention. Use a SQLite backup for complete application recovery.

The M12 visual pass uses a deliberately small, offline subset of Lucide icons while keeping action text and accessible names. Icons follow the active native Qt palette rather than imposing a custom theme. Development runs identify themselves as **Reckonsolve Dev** and use a separate database from the stable channel. A repeatable private PyInstaller `onedir` build now validates startup, icon resources, prediction creation, revision, Journal history, backup, and restart from the frozen executable. Original application-icon artwork still awaits user direction; a normal installer, signing, and public binary distribution are deliberately deferred.

## Documentation

- [Product specification](docs/product-spec.md) — implemented v0.1/v0.2 behavior and the approved v0.3 CLI contract, milestones, and acceptance criteria
- [Architecture](docs/architecture.md) — current implementation state and intended technical boundaries
- [Architecture decision records](docs/decisions/README.md) — durable reasoning for consequential technical choices

## Development

Reckonsolve uses Python 3.13, PySide6, SQLite, and `uv`.

```powershell
uv sync --locked
uv run reckonsolve-dev
uv run reckonsolve-cli-dev --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

`uv run reckonsolve-dev` is the normal source-development command. Its window title says **Reckonsolve Dev**, and it creates or opens an isolated development database, applies pending schema migrations, and keeps that database available until shutdown. `uv run reckonsolve` remains the stable-channel entry point and must not be used as an interchangeable development command because it opens the stable database location.

The matching CLI reads and creates records in that same development data without opening a window:

```powershell
uv run reckonsolve-cli-dev list
uv run reckonsolve-cli-dev list --search "temperature" --status open --type numeric --tag Personal
uv run reckonsolve-cli-dev show 12
uv run reckonsolve-cli-dev create binary
uv run reckonsolve-cli-dev create numeric
```

`list` defaults to every Prediction and supports case-insensitive Question search plus combined status, forecast-type, and tag filters. Rows identify stable IDs, current type-appropriate forecasts, tags, and attention indicators. `show` accepts one stable Prediction ID and prints current metadata, lifecycle or terminal facts, exact Binary or Numeric history, Journal correction history, Forecast Reviews, and Definition history.

`create binary` and `create numeric` are interactive and write the complete Prediction plus its first revision atomically. Binary probability defaults to 50%; Numeric decimal places default to 0 and confidence defaults to 80%. Both workflows optionally collect a one-line initial rationale, Background, Resolution Criteria, ISO dates, and comma-separated tags. Ctrl+C or end-of-input before creation saves nothing. Use `uv run reckonsolve-cli-dev --help` or a subcommand's `--help` for the complete syntax.

`list` and `show` remain read-only. Use the GUI for revisions and other changes until their owning v0.3 milestones are implemented. As with the GUI, use the `-dev` command during source development: `uv run reckonsolve-cli` intentionally opens the stable database and is not interchangeable with `reckonsolve-cli-dev`.

## Private Windows build

M12 includes a private smoke build, not an installer or public release:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The script synchronizes the locked `packaging` dependency group, builds `dist\Reckonsolve\Reckonsolve.exe`, copies that onedir bundle to a disposable ignored directory, and runs the frozen executable through an offscreen smoke workflow. The workflow uses only temporary data, migrates a real v0.1-shaped database, then checks Binary and Numeric create, revision, Review, terminal records, backup, and restart persistence. `build\` and `dist\` are generated and must remain untracked. The frozen app intentionally has no original Reckonsolve application icon yet.

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

The paired CLI commands resolve these exact same locations. This is direct shared local data, not a background synchronization or replication system: a GUI change appears on the next matching CLI invocation, and a CLI-created Prediction appears when the matching GUI next opens or refreshes.

## License

Reckonsolve is licensed under the [MIT License](LICENSE).

The selected Lucide resources retain their upstream notices in [Third-party notices](THIRD_PARTY_NOTICES.md).
