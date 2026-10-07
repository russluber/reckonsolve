# Documentation

## Using Reckonsolve

Start with the [user guide](guides/user-guide.md) for choosing a mode, entering forecasts, adding answers, correcting mistakes, interpreting results, and backing up your journal.

| Guide | Purpose |
| --- | --- |
| [User guide](guides/user-guide.md) | Desktop workflows, scores, charts, uncertainty, worked examples, and data locations. |
| [CLI guide](guides/cli-guide.md) | Terminal commands and GUI/CLI boundaries. |
| [Forecasting guide](guides/forecasting-guide.md) | Admissible questions, forecasting windows, and detailed Adaptive/One-Shot rules. |
| [Changelog](../CHANGELOG.md) | Release changes and compatibility. |

The forecasting guide contains the detailed Rulebook and One-Shot rules. The user guide's [analytics section](guides/user-guide.md#learn-from-the-results) explains scores and calibration. Adaptive timing rules do not apply to One-Shot.

## Maintaining Reckonsolve

| Reference | Purpose |
| --- | --- |
| [Repository instructions](../AGENTS.md) | How to work in this repository. |
| [Product specification](product-spec.md) | Authoritative scope, invariants, and acceptance criteria. |
| [Architecture](architecture.md) | Current implementation and dependency boundaries. |
| [Architecture decisions](decisions/README.md) | Technical reasoning and current applicability. |
| [Development and testing](maintainer/development.md) | Setup, checks, disposable visual review, and private builds. |
| [Search evaluation](maintainer/search-evaluation.md) | Relevance requirements and a reproducible benchmark. |
| [Release checklist](maintainer/release-checklist.md) | Repeatable source-release verification and publication. |
| [Binary scoring](maintainer/design/binary-scoring.md) | Ordinary and Trajectory Brier, diagnostics, calibration, and uncertainty. |
| [Numeric scoring](maintainer/design/numeric-scoring.md) | Quantile semantics, WIS, calibration, and implied-distribution limits. |

The specification governs behavior. Guides explain it; the scoring references explain current mathematics for Adaptive and One-Shot; architecture and decisions explain implementation. Release-specific design proposals are preserved in the archive.

## Development history

[The archive](archive/README.md) preserves completed milestone plans, earlier architecture descriptions, release-note drafts, and dated validation evidence. These are context, not current implementation instructions. They remain public GitHub files; archiving does not make them private or remove Git history.

Runtime databases, exports, backups, generated build output, local audit reports, and personal notes belong outside tracked documentation.
