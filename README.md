# Reckonsolve

Reckonsolve is a local-first personal forecasting journal for Windows. It records binary probabilities and numeric prediction intervals, supports revising beliefs without rewriting history, resolves type-appropriate outcomes, and helps study calibration.

> Reckonsolve now has isolated development data, local action icons, and a validated private Windows build, but it is not ready for normal distribution. Original application-icon artwork, an installer, signing, and public binaries remain deferred.

The completed binary v0.1 baseline remains intact. The staged v0.2 plan is complete: Binary and Numeric Prediction Detail record immutable Forecast Reviews while Open, using **Still at N%** or **Keep this interval**. Each Review preserves the exact retained revision, appears in the timeline, and refreshes Needs Attention without fabricating a revision, chart point, or scoring observation. Type-aware recovery, CSV export, migration, and private-build smoke coverage preserve both forecast models and Reviews.

The completed v0.3 source release includes a command-line companion for reading, creating, actively maintaining, terminating, backing up, and exporting forecasts. `reckonsolve-cli-dev` shares the isolated development database used by `reckonsolve-dev`; the stable `reckonsolve-cli` command likewise shares the stable GUI database. Both interfaces route through the same application operations and canonical SQLite history without a synchronization subsystem.

The completed v0.4 source release strengthens the learning loop after resolution. Original terminal facts stay immutable while confirmed corrections append complete history; Postmortems can be added or revised later; Resolved Prediction Detail shows type-aware scorecards; Analytics compares each eligible initial forecast with its final scoring forecast; and the Dashboard calmly surfaces Resolved predictions that still need a Postmortem decision. CLI `show`, verified backup, and CSV export preserve the same historically honest record.

The current application can create a binary prediction from a question and any whole-number probability from 0% through 100%. A collapsed **More details** section accepts an optional initial rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags; the complete initial state and first forecast are saved atomically. Prediction Detail displays the current forecast and metadata, supports safe metadata editing, and can append probability revisions with an optional rationale without rewriting earlier forecasts.

Journal entries record evidence or reasoning without changing the forecast. Forecast Reviews instead record that the user deliberately reconsidered the current forecast and retained it unchanged; an optional Review note can preserve that context. Each event keeps its exact type-appropriate forecast anchor, and revisions, Journals, and Reviews appear together in one timeline. Saved Journal text can be transparently corrected: the timeline marks it **Edited** and retains the original and every prior version in a collapsed edit history. Individual Journal entries and saved Reviews cannot be deleted.

Prediction Detail also plots every saved forecast revision in a probability-history chart. The vertical scale always spans 0% through 100%, and a step line shows that each probability remains in force until the next revision. The horizontal scale uses the revisions' stored times and displays them locally; Journal entries do not add chart observations. The textual timeline remains the complete nonvisual record of the same forecast history.

Question, Resolution Criteria, and Forecast Deadline edits require tailored confirmation and remain visible in a collapsed Definition history. A Forecast Deadline is inclusive, so normal revisions and Forecast Reviews stop after it passes while new Journal entries remain available. Resolved and Invalid predictions reject new entries and Reviews, but existing Journal entries can still receive audited corrections. Unchanged probabilities are not recorded as revisions: use a Forecast Review for deliberate reconsideration and retention, or a Journal entry for ordinary evidence and reasoning. All of this history persists across restarts.

Open and Locked predictions can be resolved Yes or No or marked Invalid. Resolution captures the exact final scoring revision plus optional factual notes and a reflective Postmortem; invalidation preserves an optional reason and excludes the prediction from future scoring. The terminal state, original timestamp, original terminal record, and scoring revision remain immutable. v0.4 permits only confirmed append-only correction of the outcome or exact actual value, Resolution notes, Postmortem, or Invalid reason; score-affecting corrections require an explanation and every superseded value remains inspectable. An untouched Open duplicate or test record can instead be permanently deleted after confirmation. Once a prediction is Locked, revised, edited, journaled, Resolved, or Invalid, its normal Delete action is unavailable and meaningful nonterminal history is directed toward Invalid.

The Dashboard separates active work into overlapping Open, Needs Attention, Ready to Resolve, and Locked sections. Needs Attention uses the later of the latest forecast revision or Open-state Forecast Review, never Journal activity, and defaults to 14 elapsed days. A separate Resolved-only **Needs Postmortem** section contains exactly the predictions with neither an effective Postmortem nor an immutable Skip completion; skipping remains optional and does not affect score or lifecycle. The threshold persists in the application database and can be changed through the currently minimal Settings screen. Dashboard rows explicitly label Binary or Numeric forecasts, show the matching current forecast or terminal summary, and open the corresponding Prediction Detail.

The Predictions screen now browses the complete archive, including Resolved and Invalid history for both forecast types. It supports case-insensitive question-text search plus combined lifecycle-status, forecast-type, and tag filters, shows each result's current type-appropriate forecast and status, and opens a freshly queried Prediction Detail. Search deliberately does not inspect Background, rationales, or Journal text in v0.1.

The Analytics screen scores each Resolved prediction exactly once using the type-appropriate ForecastRevision captured when it resolved and the latest effective outcome; Open, Locked, and Invalid predictions are excluded. Binary views retain mean Brier, ten-bin reliability, and cumulative mean Brier by resolution time. Numeric views show ten-bin containment calibration using actual mean confidence, observed inclusive containment, and visible counts. Unitless containment may combine units; raw median absolute error, interval width, and proper interval score require one exact Numeric unit. Resolved Prediction Detail shows the same individual type-aware scorecard. The retrospective update view compares one initial/final pair per revised-and-resolved Prediction, counts unrevised resolutions separately, and does not claim that updating caused improvement. Forecast type, tag, and unit filters recompute every visible value over one consistent subset.

Settings creates a complete SQLite recovery backup at a chosen destination, verifies it before replacing an existing backup, and remembers the last successful backup time. It also exports a documented format-version-three ZIP containing sixteen related CSV files for Binary and Numeric Predictions, immutable revisions, Reviews, lifecycle records, terminal corrections, Postmortem completion, and tags. The CSV bundle is portable analytical data rather than a restoration format; its included README explains every relationship, effective-terminal derivation, score-affecting correction, exact fixed-precision Numeric convention, and timestamp/date convention. Use a SQLite backup for complete application recovery.

The M12 visual pass uses a deliberately small, offline subset of Lucide icons while keeping action text and accessible names. Icons follow the active native Qt palette rather than imposing a custom theme. Development runs identify themselves as **Reckonsolve Dev** and use a separate database from the stable channel. A repeatable private PyInstaller `onedir` build now validates startup, icon resources, prediction creation, revision, Journal history, backup, and restart from the frozen executable. Original application-icon artwork still awaits user direction; a normal installer, signing, and public binary distribution are deliberately deferred.

## Documentation

- [Product specification](docs/product-spec.md) — implemented v0.1 through v0.4 behavior, milestones, and acceptance criteria
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

For user-wide access from PowerShell, Command Prompt, Windows Terminal, or Git Bash, install one non-editable snapshot from the repository root:

```powershell
uv tool install .
uv tool update-shell
```

After reopening the shell, `reckonsolve` launches the stable GUI, while `rsc` is the short form of `reckonsolve-cli`. The development shorthand is `rscd` for `reckonsolve-cli-dev`. The long names remain available. Reinstall a later checked-out release with `uv tool install --force .`; a non-editable tool snapshot does not silently follow subsequent source changes.

The matching CLI reads and changes records in that same development data without opening a window:

```powershell
uv run reckonsolve-cli-dev list
uv run reckonsolve-cli-dev list --search "temperature" --status open --type numeric --tag Personal
uv run reckonsolve-cli-dev show 12
uv run reckonsolve-cli-dev create binary
uv run reckonsolve-cli-dev create numeric
uv run reckonsolve-cli-dev revise 12
uv run reckonsolve-cli-dev journal 12
uv run reckonsolve-cli-dev review 12
uv run reckonsolve-cli-dev resolve 12
uv run reckonsolve-cli-dev invalidate 12
uv run reckonsolve-cli-dev delete 12
uv run reckonsolve-cli-dev backup C:\path\to\reckonsolve-backup.sqlite3
uv run reckonsolve-cli-dev export-csv C:\path\to\reckonsolve-export.zip
```

`list` defaults to every Prediction and supports case-insensitive Question search plus combined status, forecast-type, and tag filters. Rows identify stable IDs, current type-appropriate forecasts, tags, and attention indicators. `show` accepts one stable Prediction ID and prints current metadata, exact Binary or Numeric forecast history, Journal correction history, Forecast Reviews, and Definition history. For Resolved or Invalid records it also distinguishes the original terminal fact from the current effective value, lists every correction with before/after snapshots, reason and timestamp, preserves the complete Postmortem version chain, and shows any Skip Postmortem completion. It remains read-only; terminal corrections and Skip completion are desktop workflows in v0.4.

`create binary` and `create numeric` are interactive and write the complete Prediction plus its first revision atomically. Binary probability defaults to 50%; Numeric decimal places default to 0 and confidence defaults to 80%. Both workflows optionally collect a one-line initial rationale, Background, Resolution Criteria, ISO dates, and comma-separated tags. Ctrl+C or end-of-input before creation saves nothing. Use `uv run reckonsolve-cli-dev --help` or a subcommand's `--help` for the complete syntax.

`revise`, `journal`, and `review` accept a stable Prediction ID, display the exact current Binary or Numeric forecast, and prompt for one deliberate active-forecast action. Revisions append immutable changed forecasts while Open; Journal entries add reasoning while Open or Locked without changing the forecast or freshness; Forecast Reviews retain the current forecast while Open and refresh Needs Attention. CLI rationales, Journal bodies, and Review notes are intentionally one line for rapid capture, while the desktop app remains available for multiline writing. Ctrl+C or end-of-input saves nothing, and a concurrent change is rejected rather than attached to stale context.

`resolve`, `invalidate`, and `delete` likewise display the reviewed forecast and explain their consequence before an explicit confirmation. Resolution captures the current revision for scoring and accepts a Yes/No or exact Numeric outcome plus separate optional factual notes and Postmortem. Invalid preserves complete history outside scoring. Delete permanently removes only a transaction-current untouched Open Prediction; meaningful or Locked history is directed toward Invalid. Blank or negative confirmation cancels without writing, and terminal decisions cannot be reopened or replaced.

`backup` creates the same verified, recoverable SQLite artifact as Settings and records the last successful backup time only after installation succeeds. `export-csv` creates the same documented sixteen-file format-version-three analytical ZIP and does not change application state. Either command accepts a destination argument; omit it to receive a timestamped filename suggestion at an interactive prompt. Existing destination artifacts remain untouched if generation or installation fails. CSV is not a recovery format—use the SQLite backup for restoration.

`list` and `show` remain read-only. As with the GUI, use the `-dev` command during source development: `uv run reckonsolve-cli` intentionally opens the stable database and is not interchangeable with `reckonsolve-cli-dev`.

## Private Windows build

Reckonsolve includes a private smoke build, not an installer or public release:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The script synchronizes the locked `packaging` dependency group, builds `dist\Reckonsolve\Reckonsolve.exe`, copies that onedir bundle to a disposable ignored directory, and runs the frozen executable through an offscreen smoke workflow. The workflow uses only temporary data, migrates a real schema-version-12 v0.3 database, then checks Binary and Numeric creation, revision, Review, corrected outcomes, later Postmortems, scorecards, update analytics, Needs Postmortem, verified backup, and restart persistence. `build\` and `dist\` are generated and must remain untracked. The frozen app intentionally has no original Reckonsolve application icon yet.

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
