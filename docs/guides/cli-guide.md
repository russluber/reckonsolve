# CLI guide

## Choose the matching identity

`rsc` is the shortcut for `reckonsolve-cli` and shares the stable desktop database. `rscd` is the shortcut for `reckonsolve-cli-dev` and shares the separate development database.

From a checkout, use `uv run rscd ...`. For commands installed with `uv tool install .`, use the bare command. Refresh an installed snapshot after updating source with `uv tool install --force .`. Use `uv tool update-shell` and reopen the terminal if commands are not on PATH.

```powershell
rsc --version
rsc --help
rsc create --help
rsc search --help
```

These examples use development data:

```powershell
uv run rscd list
uv run rscd list --mode adaptive
uv run rscd list --mode one-shot
uv run rscd show 1
uv run rscd search "remembered words" --mode one-shot --include-superseded-history
uv run rscd saved-views
uv run rscd saved-view --name "Needs a postmortem"
```

`--mode deadline` remains an alias for `--mode adaptive`. List and search default to All modes. Each command's help describes its status, type, tag, attention, date, and sorting flags; list and search have different filter surfaces. Search groups matches by prediction and identifies their source. `--include-superseded-history` also searches earlier audited text. Saved Views are maintained in the desktop and executed read-only in the CLI.

## Create a prediction

```powershell
uv run rscd create binary
uv run rscd create numeric
uv run rscd create binary --one-shot
uv run rscd create numeric --one-shot
```

Creation is interactive. Binary defaults to 50% Yes; Numeric defaults to zero decimal places and requires unit, value constraint, and all five quantiles. Adaptive requires an exact Forecast Deadline. One-Shot offers an answer in the same command and optional documentary times. Text and tags remain optional.

Adaptive timestamps use offset-bearing ISO input, such as `2099-10-01T18:00:00-07:00`. Check the offset for the selected date. Resolution `now` means the outcome became knowable at recording time; otherwise enter the defensible effective time. One-Shot reported wall minutes are documentary and never affect scoring.

Blank optional prompts skip the field. Ctrl+C or end of input cancels an unfinished interaction without partial history. Creation commits the forecast and optional answer atomically.

## Work with an existing prediction

```powershell
uv run rscd revise 1
uv run rscd review 1
uv run rscd journal 1
uv run rscd resolve 1
uv run rscd invalidate 1
uv run rscd delete 1
```

`revise` appends a changed Adaptive forecast; `review` retains it unchanged. Both stop at the Deadline and reject One-Shots. `journal` adds reasoning while nonterminal without changing forecast or freshness. `resolve` records an Adaptive outcome or adds an answer to a waiting One-Shot, dispatching from the saved contract.

Lifecycle commands show current context and require confirmation. Invalid preserves history outside scoring. Delete requires an untouched Open record and rejects meaningful or terminal history.

CLI rationale, Journal, and Review-note prompts are single-line; the desktop supports multiline text. `show` displays exact values, original/effective terminal facts, Journal/Definition/correction history, Postmortem completion, and individual scores. One-Shot scores use the effective corrected guess and answer once.

## Backup and export

```powershell
uv run rscd backup .\reckonsolve-dev-backup.sqlite3
uv run rscd export-csv .\reckonsolve-dev-export.zip
```

Omit the destination to be prompted. Both use Settings' verified transfer operations. SQLite backup is complete recovery; format-5 CSV is analytical history with a data dictionary. A failed artifact operation preserves the prior destination.

## Desktop-only actions

Use the desktop for metadata edits, Journal corrections, terminal corrections, One-Shot Correct transcription, later Postmortem editing/Skip, Saved View maintenance, global tag maintenance, and search repair. The CLI inspects their history but has no correction or metadata mutation command.

## Shared data and failures

GUI and matching CLI open the same local SQLite database. A GUI change appears on the next CLI invocation; a CLI change appears when the desktop next opens or refreshes. Stable and development commands never copy or fall back between identities.

Simultaneous reads are supported; prefer sequential writes. Locks and stale reviewed context fail clearly instead of overwriting or merging. Inspect the current record and retry deliberately. Unsupported archives are refused before migration or repair, as described in the [user guide](user-guide.md#where-data-lives).

The CLI is a human interface. JSON output, bulk mutations, synchronization, and a stable scripting API are outside current scope.
