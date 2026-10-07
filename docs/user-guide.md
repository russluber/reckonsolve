# User guide

## Install and open the app

Reckonsolve is a Windows desktop app distributed as source. Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run these commands from your checked-out repository:

```powershell
uv tool install .
uv tool update-shell
```

Reopen the terminal and run `reckonsolve`. `rsc --help` opens help for its matching CLI. After updating the checkout, `uv tool install --force .` refreshes the installed commands; installed tools do not automatically follow source edits.

For development, use `uv sync --locked`, then `uv run reckonsolve-dev` or `uv run rscd`. These use a separate development database. [Development and testing](maintainer/development.md) also describes disposable test profiles.

## Choose a mode

**Adaptive** is the default. Use it for an uncertain outcome that will become knowable later. Set a permanent Forecast Deadline, then revise your forecast as evidence changes before that deadline.

**One-Shot** is for an answer that exists but you have not checked. Estimate a tree's height before measuring it, or give a probability that it exceeds 10 metres before checking. You can write the final guess in a phone note and enter it into Reckonsolve later, together with the answer.

In **New Prediction**, the top-right **One-Shot** button opens its tailored form. **Adaptive** switches back. Switching preserves unsaved drafts.

Both modes are for uncertain, objectively resolvable observations. The [forecasting guide](forecasting-guide.md) explains why goals, promises, and controllable results require care.

## Enter a forecast

Choose **Binary** or **Numeric**:

- **Binary:** write a Yes/No question and your probability of Yes, from 0% to 100% in whole percentages.
- **Numeric:** write a question about one quantity; choose its unit, decimal precision, and continuous-style or whole-number constraint; then enter five percentiles.

| Value | Meaning |
| --- | --- |
| q05 | Your 5th percentile. |
| q25 | Your 25th percentile. |
| q50 | Your median, or 50th percentile. |
| q75 | Your 75th percentile. |
| q95 | Your 95th percentile. |

Values must follow `q05 <= q25 <= q50 <= q75 <= q95`; ties are allowed. The middle pair describes a 50% interval; the outside pair describes a 90% interval. For continuous-style quantities, roughly 5% of your uncertainty falls below q05 and 5% above q95. Whole-number forecasts can have genuine ties; the [Analytics guide](analytics-guide.md) explains their interpretation.

Unit, precision, and value constraint are permanent. Quantities are stored as exact decimals. Extra precision and crossed percentiles are rejected rather than silently rounded or reordered.

**Rationale** records why you believe the forecast. **Background** supplies context. Tags organize your archive. These are optional; placeholder prompts are never saved as your text.

### Adaptive: choose a Forecast Deadline

Choose **End of today**, **End of tomorrow**, **7 days**, **30 days**, or **Custom…**. Shortcuts choose 11:59 PM on the corresponding local calendar date. Inspect the selected date/time before saving; shortcuts are conveniences, not recommended horizons.

The deadline must be in the future when Save commits and becomes permanent afterward. The picker uses the local time zone's rules for the selected date, asks which occurrence you mean during a repeated daylight-saving hour, and rejects nonexistent times. **Use another UTC offset** permits an explicit override.

Under **More details**, optionally add Resolution Criteria and Expected Resolution. Criteria describe how the answer will be established. Expected Resolution is an editable planning date that can surface **Ready to Resolve**; it never changes the deadline or score.

### One-Shot: record the final guess and answer

Enter only the final probability or five percentiles settled on before checking. Earlier private drafts do not need to be entered.

Background, Rationale, and Tags are visible in the main Forecast card. Background can describe context and how you checked the answer. Choose the source or measurement convention before looking when possible.

**Record date and time** is optional. It supplies a calendar date picker and segmented time field: type hours, Tab, minutes, Tab, then A or P. Shift+Tab moves backward; Up/Down adjusts the selected section. Dates start at today when enabled. Reported times may be approximate, missing, or equal to the same minute. They document the external record and do not affect scoring. Reckonsolve separately retains when you entered the record into the app.

Select **Include the answer now** to enter the Yes/No answer or measured value in the same form. Save records forecast and answer atomically. Scores appear only after Save. Without an answer, Detail shows **Waiting for answer** and offers **Add answer** later.

One-Shot has no Forecast Deadline, Expected Resolution, ordinary forecast updates, or Forecast Reviews. It is not a deadline bypass for ongoing future-event forecasts.

## Revisit a prediction

Open a prediction from **Dashboard**, **Predictions**, or search. Detail shows the forecast, lifecycle, metadata, and causal Timeline. Back returns to the source view with browsing context.

An Open Adaptive prediction offers:

- **Revise:** append a changed probability or complete five-quantile forecast as an immutable revision.
- **Forecast Review:** record that you reconsidered and kept the forecast. It refreshes Needs Attention without inventing a revision.
- **Journal:** add reasoning or evidence without changing forecast or refreshing Needs Attention.

At the Forecast Deadline, an unanswered Adaptive prediction becomes **Locked**. Revisions and Reviews stop; Journal, Resolve, and Mark Invalid remain available. A waiting One-Shot permits Journal entries and metadata work, but no revision or Review.

## Add an answer

Adaptive **Resolve** asks for the outcome, when it became fixed and ascertainable under your criteria, and optional factual notes and Postmortem. That effective time differs from when you enter the answer. Use recording time only if the answer became knowable now; otherwise enter the defensible earlier time with its correct UTC offset.

Adaptive scoring uses effective time. Forecasts at or after the scoring cutoff stay in history but do not count. An outcome already fixed at or before the first Adaptive forecast is explicitly unscored.

One-Shot **Add answer** records the checked answer and optionally when you checked it. The answer can predate the guess physically; you must have guessed before looking. Documentary times do not create an Adaptive scoring window.

Resolution is a one-way terminal decision. You can add or correct a Postmortem later. **Needs Postmortem** surfaces resolved entries without reflection. **Skip Postmortem** dismisses the queue item while permitting reflection later.

## Correct a mistake

Adaptive belief changes use **Revise** before the deadline. Saved revisions are never overwritten. Terminal corrections can repair an outcome or effective time while preserving the original; score-affecting changes require an explanation.

One-Shot **Correct transcription** repairs a copied probability, percentile, answer, or reported time. The original and each correction remain inspectable. Scoring uses the latest effective facts once. This repairs the record of your earlier guess; it does not add a new guess after seeing the answer.

Journal corrections show the latest body at the original Timeline position. Open **Edit history** for earlier versions. Question and Resolution Criteria clarifications retain Definition history; Background and tags are ordinary editable metadata. A material change to the target, source, threshold, or measurement convention requires preserving the original as Invalid and creating a new prediction.

**Mark Invalid** preserves a question that cannot fairly be resolved and excludes it from scoring. **Delete** is limited to untouched Open creation mistakes; meaningful or terminal history cannot be deleted through the normal interface.

## Find and organize your journal

In **Predictions**, combine search with mode, type, lifecycle, tags, attention, dates, and sorting. Mode offers All, Adaptive, and One-Shot. Deadline filters do not invent dates for One-Shots.

Search uses ordinary words. All words is the default; quoted phrases match within one source. Results explain their matches and group them into one row per prediction. **Include superseded history** searches earlier audited text and labels it accordingly. Opening a historical match reveals the corresponding Timeline or history section.

Save a useful configuration as a **Saved View**. It remains dynamic: new matching predictions appear automatically. Changed controls do not alter the saved configuration until you explicitly update it. Tag management can rename, merge, or delete tags with confirmation without rewriting forecast history.

## Learn from the results

**Analytics** defaults to Adaptive. Select One-Shot for separate summaries. Filters and counts describe the selected mode, type, tags, and Numeric unit.

- Adaptive Binary uses Trajectory Brier to score standing probabilities over time.
- One-Shot Binary uses ordinary Brier for the final guess.
- Numeric Detail uses individual five-quantile WIS in either mode.
- Numeric aggregate views show calibration and outcome balances, separating continuous-style and whole-number questions. Raw WIS is never averaged across questions.

Lower scores are better, but a small sample says little about skill. The [Analytics guide](analytics-guide.md) provides examples, uncertainty, and review habits.

## Back up and export

Use **Settings → Backup** or the matching CLI for a verified SQLite backup. It preserves the complete supported archive, corrections, tags, Saved Views, and database settings. Keep backups outside generated development/build directories.

**Export CSV** creates a format-5 ZIP with relational history and a data dictionary. It includes both modes, exact Numeric values, originals, and corrections. Saved Views, settings, and search-index rows are excluded. CSV is for analysis, not restoration.

For recovery, close the app and matching CLI, preserve the current database, and restore a verified compatible SQLite backup to that identity's database path. Reopen and check the archive; use Settings search repair if the derived index needs rebuilding. Do not restore CSV files as a database or replace stable data with test data.

## Where data lives

| Identity | Desktop / CLI | Database |
| --- | --- | --- |
| Stable | `reckonsolve` / `rsc` | `%LOCALAPPDATA%\Reckonsolve\reckonsolve.sqlite3` |
| Development | `reckonsolve-dev` / `rscd` | `%LOCALAPPDATA%\Reckonsolve Dev\reckonsolve.sqlite3` |

Each identity has a separate `presentation.ini` for window/sidebar preferences outside canonical history and excluded from backups/exports. GUI and CLI share the matching database directly; refresh or reopen the GUI after a CLI change. They do not sync across identities.

Any pre-v0.7 Binary-final or interval-v1 Numeric record prevents an archive from opening in v0.8.0. Mixed archives and missing, unknown, or mismatched identities are also refused before mutation. Nothing is converted or deleted; preserve the original for a compatible earlier version.
