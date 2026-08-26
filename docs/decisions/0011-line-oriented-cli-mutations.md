# 0011: Keep CLI mutations line-oriented and route them through application operations

- Status: Accepted
- Date: 2026-08-25

## Context

The v0.3 companion needs fast interactive capture while sharing every historical and concurrency rule with the desktop application. Milestone 23 introduces revision rationales, Journal bodies, and Forecast Review notes, raising whether the terminal should support multiline composition and whether a CLI framework or editor launcher is warranted.

Predlog uses Typer for command parsing, but its ordinary prompt is line-oriented and Predlog contains no multiline Journal implementation. Click can launch an external editor, but that would add a production dependency, temporary-editor behavior, and a window transition to workflows intended mainly for quick terminal capture.

The active commands also hold reviewed forecast context while the user types. Writing directly through repositories or SQL would risk weakening the existing revision, metadata-version, deadline, lifecycle, anchor, and transaction checks.

## Decision

Keep the v0.3 CLI on standard-library `argparse` and an injectable line-oriented prompt session. Each substantive prompt consumes one terminal line. Revision rationales, Journal bodies, and Forecast Review notes are therefore single-line in the CLI; optional fields remain skippable. This is a presentation constraint only. Domain validation and canonical storage continue to accept multiline text, and the desktop interface remains the long-form editor.

For `revise`, `journal`, and `review`, load and display the current type-aware Prediction, retain its current revision identifier and metadata version through prompting, then call exactly one existing application operation. The application and repository transaction remain authoritative for validation, immutable appends, lifecycle and deadline eligibility, forecast anchoring, freshness, and optimistic-concurrency rejection. The CLI performs no direct SQL.

## Consequences

The common CLI path stays quick, dependency-free, deterministic under tests, and usable in ordinary PowerShell and Windows Terminal sessions. EOF and Ctrl+C have unambiguous cancellation semantics, and no prompt progress becomes product data. GUI and CLI mutations share the same canonical history rather than merely imitating one another's rules.

The CLI is not comfortable for composing paragraphs. Users can perform long-form Journal and Review writing in the desktop app, and CLI-authored records can still coexist with multiline desktop-authored records. A later explicitly scoped editor option can be added without a schema migration because canonical text was never restricted to one line.

## Alternatives considered

- **Adopt Typer for multiline prompts:** rejected because Typer's normal prompt is still single-line and changing the command framework would add dependency and compatibility work without solving the text-entry issue.
- **Use Click's external-editor launcher:** deferred because it adds a dependency and editor/window lifecycle for a companion intended primarily for rapid capture.
- **Use a multiline terminal sentinel:** rejected for v0.3 because paragraph composition is not important enough to the expected CLI usage to justify an additional input convention.
- **Write directly through repositories or SQL:** rejected because it would duplicate or weaken the application operations' historical and concurrency guarantees.
- **Introduce an application service or synchronization API:** rejected because both local interfaces already share one SQLite database and no server or replication layer is needed.
