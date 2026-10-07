# Reckonsolve

A personal forecasting journal for Windows. Record uncertain judgments, preserve your reasoning, resolve answers, and study calibration. Reckonsolve works offline and stores your data locally.

## Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run these commands from the repository root:

```powershell
uv sync --locked
uv run reckonsolve-dev
```

This opens the isolated development database. For everyday use, install the checkout as a local tool:

```powershell
uv tool install .
uv tool update-shell
```

Reopen your terminal, then use `reckonsolve` for the desktop or `rsc` for the CLI. After updating your checkout, refresh installed commands with `uv tool install --force .`.

Reckonsolve uses Python 3.13, PySide6, and SQLite. [v0.8.0](https://github.com/russluber/reckonsolve/releases/tag/v0.8.0) is a source release; no installer or public executable is distributed.

## Two ways to forecast

| Mode | Use it for | How it works |
| --- | --- | --- |
| **Adaptive** | An uncertain outcome that will become knowable later | Set a permanent Forecast Deadline; revise or review before it passes. |
| **One-Shot** | An answer that exists but you have not checked | Record your final guess and add the answer now or later. A phone note can be transcribed afterward. |

Both support Binary Yes/No probabilities and Numeric q05/q25/q50/q75/q95 forecasts. Adaptive is the default in **New Prediction**; the top-right **One-Shot** button switches modes.

Immutable forecasts, audited corrections, Journals, and Postmortems preserve the learning record. Search, filters, tags, and Saved Views help you find it again. Analytics keeps modes separate; Numeric WIS is an individual score, never a pooled personal skill score.

## Documentation

- [User guide](docs/user-guide.md) - setup, forecasts, answers, corrections, analytics, and recovery.
- [CLI guide](docs/cli-guide.md) - commands, examples, and interface boundaries.
- [Forecasting guide](docs/forecasting-guide.md) - admissible questions and detailed Adaptive/One-Shot rules.
- [Documentation index](docs/README.md) - forecasting rules, maintainer references, and development history.
- [Changelog](CHANGELOG.md) - release changes and compatibility notes.

## Data and compatibility

The stable desktop and `rsc` share `%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3`. Development desktop and `rscd` share a separate database under `%LOCALAPPDATA%\Reckonsolve Dev`. Switching commands never copies data between them.

Use verified **SQLite backups** for recovery. CSV format 5 is analytical history with a data dictionary; it cannot restore the application. Window/sidebar preferences live separately in `presentation.ini` and are excluded from SQLite backups.

Supported v0.7 archives upgrade through schema 20 unchanged. Any pre-v0.7 Binary or interval-v1 Numeric prediction causes the whole archive to be refused before migration or repair. Missing, unknown, or mismatched identities are also refused. Nothing is converted, deleted, or partially loaded; preserve unsupported originals for a compatible earlier version.

## Development

See [development and testing](docs/maintainer/development.md) for quality checks, disposable visual profiles, and private builds. [The specification](docs/product-spec.md) governs scope; [AGENTS.md](AGENTS.md) contains repository working instructions.

## License

[MIT](LICENSE). Bundled Lucide resources retain their upstream [third-party notices](THIRD_PARTY_NOTICES.md).
