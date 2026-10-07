# Search evaluation

Reckonsolve treats search quality as a regression-tested product behavior rather than assuming that SQLite FTS5 results are automatically useful. Evaluation is entirely local, synthetic, and privacy-safe. It never opens the stable or development database and records no queries or clicks.

## Relevance corpus

`tests/test_search_quality.py` contains the named end-to-end memory scenarios. Together with the focused domain, application, filter, GUI, and CLI search tests, it covers:

- exact and reordered current Questions;
- terms split across different fragments of one Prediction;
- quoted phrases constrained to one fragment and incremental final-word prefixes;
- case, common Latin diacritics, apostrophes, hyphens, percentages, and FTS-significant punctuation;
- explicit one-edit spelling suggestions and user-controlled acceptance;
- stronger Question matches against overlapping common terms;
- multiple matching fragments grouped into one Prediction row;
- effective and superseded Journal and terminal text;
- Binary and exact Numeric results; and
- structured filters, date/null boundaries, deterministic sorts, migration, restart, independent connections, rollback, corruption reporting, and repair.

Every named intended result must occur in the top three. An unambiguous exact current-Question query must rank its Prediction first. Tests deliberately avoid freezing incidental BM25 floating-point values.

## Large synthetic corpus

Run the disposable benchmark from the repository root:

```powershell
uv run python tools/evaluate_search.py --size 2000
```

The tool creates a temporary database through normal application operations, verifies the complete derived projection, warms each query, reports median retrieval time, and checks full result completeness. It imposes no fixed cross-machine millisecond threshold.

## Coverage and evidence

One-Shot mode filtering, effective/superseded correction text, exactly-once grouping, independent connections, and search repair have focused regression coverage. The large benchmark currently builds an Adaptive corpus; do not claim it benchmarks One-Shot performance.

[Dated benchmark results](../archive/search-benchmarks.md) and [v0.8 validation](../archive/releases/v0.8-validation.md) retain historical evidence. Reduce a sluggish or incomplete case to a synthetic regression before changing matching/ranking rules.
