# Reckonsolve

Reckonsolve is a local-first personal forecasting journal for Windows. It is designed for recording binary probabilistic predictions, revising beliefs without rewriting history, resolving outcomes, and studying calibration.

> Reckonsolve has reached its searchable prediction-archive milestone, but analytics and data-management workflows are still being built and it is not ready for normal use.

The current application can create a binary prediction from a question and any whole-number probability from 0% through 100%. A collapsed **More details** section accepts an optional initial rationale, Background, Resolution Criteria, Forecast Deadline, Expected Resolution, and tags; the complete initial state and first forecast are saved atomically. Prediction Detail displays the current forecast and metadata, supports safe metadata editing, and can append probability revisions with an optional rationale without rewriting earlier forecasts.

Journal entries record evidence or reasoning without changing the forecast. Each entry preserves the forecast that was current when it was written, and revisions and Journal entries appear together in one timeline. Saved Journal text can be transparently corrected: the timeline marks it **Edited** and retains the original and every prior version in a collapsed edit history. Individual Journal entries cannot be deleted.

Prediction Detail also plots every saved forecast revision in a probability-history chart. The vertical scale always spans 0% through 100%, and a step line shows that each probability remains in force until the next revision. The horizontal scale uses the revisions' stored times and displays them locally; Journal entries do not add chart observations. The textual timeline remains the complete nonvisual record of the same forecast history.

Question, Resolution Criteria, and Forecast Deadline edits require tailored confirmation and remain visible in a collapsed Definition history. A Forecast Deadline is inclusive, so normal revisions stop after it passes while new Journal entries remain available. Resolved and Invalid predictions reject new entries, but existing entries can still receive audited corrections. Unchanged probabilities are not recorded as revisions; reasoning that leaves the probability unchanged belongs in the Journal. All of this history persists across restarts.

Open and Locked predictions can now be resolved Yes or No or marked Invalid. Resolution captures the exact final scoring revision plus optional factual notes and a reflective postmortem; invalidation preserves an optional reason and excludes the prediction from future scoring. Both are deliberate, immutable terminal decisions in v0.1. An untouched Open duplicate or test record can instead be permanently deleted after confirmation. Once a prediction is Locked, revised, edited, journaled, Resolved, or Invalid, its normal Delete action is unavailable and meaningful nonterminal history is directed toward Invalid.

The Dashboard now separates active work into overlapping Open, Needs Attention, Ready to Resolve, and Locked sections. Needs Attention uses the latest forecast revision, not Journal activity, and defaults to 14 elapsed days. The threshold persists in the application database and can be changed through the currently minimal Settings screen. Dashboard rows show the current probability and forecast-update time and open the corresponding Prediction Detail.

The Predictions screen now browses the complete archive, including Resolved and Invalid history. It supports case-insensitive question-text search plus combined lifecycle-status and tag filters, shows each result's current probability and status, and opens a freshly queried Prediction Detail. Search deliberately does not inspect Background, rationales, or Journal text in v0.1.

The Analytics screen remains a placeholder. Scoring analytics, backup, export, broader Settings tools, and Windows packaging are reserved for later milestones.

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
