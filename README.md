# Reckonsolve

Reckonsolve is a local-first personal forecasting journal for Windows. It is designed for recording binary probabilistic predictions, revising beliefs without rewriting history, resolving outcomes, and studying calibration.

> Reckonsolve has reached its Prediction Detail and metadata-editing milestone, but most forecasting workflows are still being built and it is not ready for normal use.

The current application can create a binary prediction from a question and any whole-number probability from 0% through 100%. Prediction Detail displays its current forecast, status, tags, dates, Background, and Resolution Criteria. These details can be edited; changes to the Question, Resolution Criteria, or Forecast Deadline require confirmation and remain visible in a collapsed Definition history. Data persists across restarts.

The Dashboard, Predictions, Analytics, and Settings screens remain placeholders. Revising a forecast, adding journal entries, resolving, and invalidating are also reserved for later milestones.

## Documentation

- [Product specification](docs/product-spec.md) — v0.1 scope, behavior, invariants, and acceptance criteria
- [Architecture](docs/architecture.md) — current implementation state and intended technical boundaries
- [Architecture decision records](docs/decisions/README.md) — durable reasoning for consequential technical choices

## Development

Reckonsolve uses Python 3.13, PySide6, SQLite, and `uv`.

```powershell
uv sync --locked
uv run reckonsolve
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Running the application creates or opens its SQLite database, applies any pending schema migrations, and keeps that database available until the application shuts down.

## Runtime data

On Windows, Reckonsolve stores its canonical database outside the repository at:

```text
%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3
```

The directory is selected through Qt's per-user local application-data location. Automated tests inject temporary database paths and do not open the real user database. The application is local-only and does not require network access.

## License

Reckonsolve is licensed under the [MIT License](LICENSE).
