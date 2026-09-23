# Reckonsolve

Reckonsolve is a local-first personal forecasting journal for Windows. Record probabilities and numeric forecasts, revise beliefs without rewriting history, resolve outcomes, and study calibration. Everything works offline for one user.

> v0.7.0 is the current source version. Original app artwork, an installer, signing, and public binaries remain deferred.

**Compatibility:** This source supports trajectory Binary and five-quantile Numeric forecasts only. A database or backup containing even one pre-v0.7 Binary or interval-v1 Numeric prediction is refused as a whole, before migration or search repair. Nothing is converted, deleted, or partially loaded. Missing, unknown, or mismatched forecast identities are also refused. Keep an unsupported original or backup for a compatible earlier Reckonsolve version. Do not reset your personal database just to test development code.

Supported v0.7 history is preserved on schema 18; supported Binary-only schema-16/17 archives can upgrade. The retirement requires no new schema migration. See the [retirement contract](docs/product-spec.md#353-durable-model-and-cohort-identity) and [technical decision](docs/decisions/0019-retire-legacy-runtime-without-rebuilding-history.md).

## Current features

- **Binary:** any whole percentage from 0% to 100%, with a permanent exact Forecast Deadline. Trajectory Brier scores the standing probabilities over time; final-probability calibration remains a separate diagnostic.
- **Numeric:** five exact percentiles (q05/q25/q50/q75/q95), a permanent unit and precision, continuous-style or whole-number values, and a permanent exact Deadline. Detail shows the elicited central CDF without invented tails, and resolved forecasts have individual WIS scorecards.
- **Honest history:** immutable revisions, reasoning-only Journals with transparent corrections, unchanged-forecast Reviews, definition history, and audited terminal corrections. Reviews refresh Needs Attention without creating a fake revision.
- **Exact lifecycle:** revisions and Reviews stop at the Deadline; Locked predictions still accept Journals. Resolution distinguishes when the outcome became fixed and knowable from when it was recorded. Invalid predictions stay in history outside scoring. Only untouched Open predictions can be deleted after confirmation.
- **Learning:** separate Binary and Numeric analytics, continuous-style versus whole-number calibration, uncertainty ranges, outcome balances, and initial/final feedback. Numeric WIS comparisons stay within one Prediction; unrelated raw scores are never averaged. See the [Analytics guide](docs/analytics-guide.md) for worked examples and review habits.
- **Archive:** explainable local full-text search, optional superseded history, rich filters, dynamic Saved Views, and transactional tag management. The search index is rebuildable from canonical history.
- **Desktop and CLI:** both use the same application operations and matching SQLite database—no synchronization service. Metadata edits, terminal corrections, tag maintenance, and search repair remain desktop workflows.
- **Recovery:** verified SQLite backups preserve the whole supported archive. Relational CSV format 4 exports current-model analytical history with exact deadlines, quantiles, correction chains, and an included data dictionary. CSV is not a restoration format.

The desktop uses a shared palette-aware visual system, local Lucide icons, expanded or compact navigation, responsive workspaces, keyboard shortcuts, and identity-isolated window settings outside canonical history. The stable GUI/CLI share one data identity; the `-dev` pair share a separate development identity.

Desktop Deadline entry starts **Not set**. Choose **End of today**, **End of tomorrow**, **7 days**, **30 days**, or **Custom…**. Shortcuts select 11:59 PM on the corresponding local calendar date; inspect or edit the exact date/time before creating. The picker automatically uses that date's local UTC offset, asks which occurrence you mean during a repeated daylight-saving hour, and rejects nonexistent local times. **Use another UTC offset** permits an explicit override. Switching forecast type keeps the draft deadline; creating successfully clears it for the next prediction.

Effective-time entry and CLI timestamps still require checking the UTC offset for the chosen date, including daylight saving time. Desktop labels normally show minutes while storage retains full precision. CLI accepts offset-bearing ISO timestamps, such as `2099-10-01T18:00:00-07:00`. Choose **use recording time** / `now` only when the outcome became knowable now; an effective time after recording is rejected. An outcome already fixed at or before the first forecast is explicitly unscored.

## Documentation

- [Analytics user's guide](docs/analytics-guide.md) — plain-language chart reading, worked examples, and practical forecasting follow-up
- [Forecasting Rulebook](docs/reckonsolve-forecasting-rulebook-v0.7.md) — durable guidance for deciding whether and how to commit a Reckonsolve forecast
- [Product specification](docs/product-spec.md) — implemented behavior plus the approved staged v0.7 contract and milestones
- [Architecture](docs/architecture.md) — current implementation state and intended technical boundaries
- [Architecture decision records](docs/decisions/README.md) — durable reasoning for consequential technical choices
- [Search evaluation](docs/search-evaluation.md) — privacy-safe relevance coverage and the recorded large-corpus run
- [v0.6 visual verification](docs/v0.6-visual-verification.md) — release-candidate matrix for palettes, scaling, window sizes, data shapes, and interaction states
- [Source release checklist](docs/release-checklist.md) — repeatable verification and GitHub release steps
- [v0.7 release notes](docs/v0.7-release-notes.md) — changes, recovery, and compatibility break

## Before committing a forecast

Use this short check as guidance, not as a required form or stored classification:

- Am I mainly observing this outcome rather than steering it after I forecast?
- If I can materially influence it, have I stated a concrete policy for what I will and will not do?
- Is the question resolvable from a clear source, and is the forecasting cutoff chosen for the real decision window rather than for a preferred score?

The [Forecasting Rulebook](docs/reckonsolve-forecasting-rulebook-v0.7.md) explains the boundary and examples in full. Reckonsolve does not record an A/B/C label or force a checklist attestation.

## Development

Reckonsolve uses Python 3.13, PySide6, SQLite, and `uv`.

```powershell
uv sync --locked
uv run reckonsolve-dev
uv run reckonsolve-cli-dev --help
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python tools/evaluate_search.py --size 2000
```

`uv run reckonsolve-dev` is the normal source-development command. Its window title says **Reckonsolve Dev**, and it creates or opens an isolated development database, applies pending schema migrations, and keeps that database available until shutdown. `uv run reckonsolve` remains the stable-channel entry point and must not be used as an interchangeable development command because it opens the stable database location.

The desktop provides navigation-only global shortcuts: `Ctrl+N` opens New Prediction, `Ctrl+F` opens Predictions and focuses Search, `Ctrl+1`/`Ctrl+2`/`Ctrl+3` open Dashboard/Predictions/Analytics, `Ctrl+,` opens Settings, `Ctrl+B` toggles the sidebar, and `Alt+Left` returns from contextual Prediction Detail. Reckonsolve suppresses these shortcuts while a text editor, editable selector, numeric/date editor, or modal decision owns the input.

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
uv run reckonsolve-cli-dev search "project evidence" --tag Work --tag Research --tag-mode all
uv run reckonsolve-cli-dev search '"old wording"' --include-superseded-history
uv run reckonsolve-cli-dev saved-views
uv run reckonsolve-cli-dev saved-view --name "Work follow-up"
uv run reckonsolve-cli-dev saved-view --id 3
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

`list` defaults to every Prediction and supports case-insensitive Question search plus combined status, forecast-type, and tag filters. `search QUERY` searches the full current/effective journal corpus and supports deliberate All/Any word modes, superseded-history inclusion, repeated tags with All/Any matching, status, type, attention, ISO date-range, and deterministic-sort filters. It prints one explainable row per Prediction, including the best source, a plain-text snippet, and additional-match count; a spelling suggestion or Any-word fallback is advice, never an automatic query change. `saved-views` lists each dynamic configuration, while `saved-view --name NAME` or `--id ID` reruns it against current data. These commands are read-only. `show` accepts one stable Prediction ID and prints current metadata, exact Binary or Numeric forecast history, Journal correction history, Forecast Reviews, and Definition history. For Resolved or Invalid records it also distinguishes the original terminal fact from the current effective value, lists every correction with before/after snapshots, reason and timestamp, preserves the complete Postmortem version chain, and shows any Skip Postmortem completion. Terminal corrections, Skip completion, Saved View mutation, tag-library maintenance, and search repair remain desktop workflows.

`create binary` and `create numeric` are interactive and write the complete Prediction plus its first revision atomically. Binary probability defaults to 50%; Numeric decimal places default to 0. Numeric creation requires all five percentiles and an explicit value constraint; both types require an exact Deadline with UTC offset. Optional prompts collect a one-line initial rationale, Background, Resolution Criteria, Expected Resolution date, and comma-separated tags. Ctrl+C or end-of-input before creation saves nothing. Use `uv run reckonsolve-cli-dev --help` or a subcommand's `--help` for the complete syntax.

`revise`, `journal`, and `review` accept a stable Prediction ID, display the exact current Binary or Numeric forecast, and prompt for one deliberate active-forecast action. Revisions append immutable changed forecasts while Open; Journal entries add reasoning while Open or Locked without changing the forecast or freshness; Forecast Reviews retain the current forecast while Open and refresh Needs Attention. CLI rationales, Journal bodies, and Review notes are intentionally one line for rapid capture, while the desktop app remains available for multiline writing. Ctrl+C or end-of-input saves nothing, and a concurrent change is rejected rather than attached to stale context.

`resolve`, `invalidate`, and `delete` likewise display the reviewed forecast and explain their consequence before an explicit confirmation. Resolution records a Yes/No or exact Numeric outcome, its effective time, and optional factual notes and Postmortem. The current revision is retained as recording context; scoring independently selects the eligible history before the effective cutoff. Invalid preserves complete history outside scoring. Delete permanently removes only a transaction-current untouched Open Prediction; meaningful or Locked history is directed toward Invalid. Blank or negative confirmation cancels without writing, and terminal decisions cannot be reopened or replaced.

`backup` creates the same verified, recoverable SQLite artifact as Settings and records the last successful backup time only after installation succeeds. `export-csv` creates a format-4 ZIP of the supported analytical history with a complete data dictionary. Either command accepts a destination argument; omit it to receive a timestamped filename suggestion at an interactive prompt. Existing destination artifacts remain untouched if generation or installation fails. CSV is not a recovery format—use the SQLite backup for restoration.

`list`, `show`, `search`, `saved-views`, and `saved-view` remain read-only. As with the GUI, use the `-dev` command during source development: `uv run reckonsolve-cli` intentionally opens the stable database and is not interchangeable with `reckonsolve-cli-dev`.

## Private Windows build

Reckonsolve includes a private smoke build, not an installer or public release:

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\build_windows.ps1
```

The script synchronizes the locked `packaging` dependency group, builds `dist\Reckonsolve\Reckonsolve.exe`, copies that onedir bundle to a disposable ignored directory, and runs the frozen executable through an offscreen smoke workflow. The workflow uses only temporary data and no source runtime. It upgrades a supported schema-17 Binary archive, exercises both current forecast models through revisions, Reviews, Resolution, corrections, scorecards, Analytics, search, CSV-4 export, backup, and restart, and refuses a disposable mixed unsupported archive unchanged. It also checks local icons, expanded/compact navigation, primary screens, shortcuts, and responsive sizes. `build\` and `dist\` remain untracked. The frozen app has no original Reckonsolve application icon yet.

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

Each identity also stores disposable shell preferences in a neighboring `presentation.ini`. This file remembers safe normal-window geometry, maximized state, and expanded/compact sidebar mode. It is not forecast data and is not included in SQLite backups or CSV exports.

The paired CLI commands resolve these exact same locations. This is direct shared local data, not a background synchronization or replication system: a GUI change appears on the next matching CLI invocation, and a CLI-created Prediction appears when the matching GUI next opens or refreshes.

## License

Reckonsolve is licensed under the [MIT License](LICENSE).

The selected Lucide resources retain their upstream notices in [Third-party notices](THIRD_PARTY_NOTICES.md).
