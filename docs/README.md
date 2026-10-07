# Documentation

## Using Reckonsolve

Start with the [user guide](user-guide.md) for choosing a mode, entering forecasts, adding answers, correcting mistakes, and backing up your journal.

| Guide | Purpose |
| --- | --- |
| [User guide](user-guide.md) | Desktop workflows and data locations. |
| [CLI guide](cli-guide.md) | Terminal commands and GUI/CLI boundaries. |
| [Forecasting guide](forecasting-guide.md) | Admissible questions and forecasting windows. |
| [Analytics guide](analytics-guide.md) | Scores, charts, uncertainty, and worked examples. |
| [Adaptive Rulebook](reckonsolve-forecasting-rulebook-v0.7.md) | Detailed rules for observational forecasting. |
| [One-Shot Rulebook](reckonsolve-one-shot-rulebook-v0.8.md) | Judgments made before checking an existing answer. |
| [Changelog](../CHANGELOG.md) | Release changes and compatibility. |

Version numbers in the detailed Rulebook filenames identify the contracts' origins. Both apply to v0.8.0: One-Shot adds an explicit exception to Adaptive timing rules.

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
| [Binary scoring design](maintainer/design/binary-trajectory-v0.7.md) | Trajectory derivation and design rationale. |
| [Numeric forecasting design](maintainer/design/numeric-forecasting-v0.7.md) | Quantile, WIS, and calibration derivations. |

The specification governs behavior. Guides explain it; architecture and decisions explain implementation. Historical design promises are subject to the current compatibility boundary and One-Shot contract.

## Development history

[The archive](archive/README.md) preserves completed milestone plans, earlier architecture descriptions, release-note drafts, and dated validation evidence. These are context, not current implementation instructions. They remain public GitHub files; archiving does not make them private or remove Git history.

Runtime databases, exports, backups, generated build output, local audit reports, and personal notes belong outside tracked documentation.
