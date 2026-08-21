# 0008: Use selected local icons and a private onedir build

- Status: Accepted
- Date: 2026-08-20

## Context

Milestone 12 needs a coherent offline action-icon layer and evidence that Reckonsolve can run as a frozen Windows application. It does not authorize a public release, normal installer, or permanent application artwork. The source-development channel must also stop sharing an implicit identity and database location with a future stable build.

Fetching icons at runtime would violate the local-first boundary. Shipping the whole Lucide catalog or adding an icon package would add unused material and make licensing less transparent. Platform theme icons are not consistently available on Windows and do not provide one controlled vocabulary across all supported actions. For freezing, an installer would prematurely decide installation, upgrade, uninstall, shortcut, and trust behavior; a one-file executable would add extraction behavior and make initial resource failures harder to inspect.

## Decision

Reckonsolve vendors exactly the selected SVG files it uses from Lucide release 1.33.0. The version, upstream source, selected filenames, and complete applicable ISC/MIT notice live beside the assets; the root third-party notice is included in package metadata and the private frozen bundle. QtSvg renders `currentColor` strokes into multiple native-palette sizes and modes. Navigation and important actions keep visible text, accessible names, and ordinary Qt keyboard behavior; icons supplement rather than replace their labels. Palette changes re-render remembered UI icons.

Stable and development runs use explicit immutable identities. `reckonsolve-dev` sets the visible title and Qt application name to **Reckonsolve Dev** before `AppLocalDataLocation` is resolved, yielding `%LOCALAPPDATA%\Reckonsolve Dev`. Stable entry points retain `%LOCALAPPDATA%\Reckonsolve`. There is no automatic copy, migration, or fallback between them.

PyInstaller 6.22.2 is pinned in a separate locked `packaging` dependency group. A checked-in spec produces a windowed `onedir` bundle and explicitly collects the selected resources and notices. The build script keeps generated files under ignored paths, relocates a copy of the bundle, and launches that frozen executable against disposable paths. Its private smoke route seeds a real v0.1 schema-version-8 database, constructs the actual main window to migrate it through v0.2, exercises Binary and Numeric create/revise/Review/terminal workflows, creates a verified backup, and confirms preserved v0.1 data plus both current forecast types across restart in source and backup databases.

No custom executable or window icon is supplied until the user directs or provides original artwork. The private bundle is not signed, published, installed, or presented as a supported release.

## Consequences

- Icon resources remain deterministic and available offline without a new runtime dependency.
- Only actually used Lucide assets ship, with auditable provenance and license notices.
- Native light/dark palette changes remain legible without a custom theme system.
- Text and accessibility remain authoritative if an icon is unfamiliar or unavailable visually.
- Source development can no longer accidentally open stable data when the documented `reckonsolve-dev` command is used.
- Frozen resource, Qt plugin, persistence, and backup failures are caught by one repeatable executable-level probe.
- Packaging adds a locked build dependency and checked-in spec/script, but no production dependency or release-support promise.
- The generic private executable remains visually incomplete until original Reckonsolve artwork is chosen.

## Alternatives considered

### Use online or system-theme icons

Rejected because runtime downloads break offline operation and Windows theme-icon availability is not a stable cross-machine resource contract.

### Add the full Lucide package or catalog

Rejected because Reckonsolve needs a small known vocabulary. Vendoring the entire catalog would increase artifact size, review surface, and license inventory without user value.

### Compile a Qt resource collection

Deferred because Python package resources plus explicit PyInstaller collection already support source, wheel, and frozen execution with less generated tooling. A compiled resource collection would be justified only by a demonstrated loading or packaging problem.

### Build one file or choose an installer now

Rejected for M12. `onedir` is inspectable and avoids self-extraction, while an installer would force unresolved ownership, upgrade, uninstall, signing, shortcut, and distribution policies.

### Use Briefcase, Nuitka, or another packaging system

Rejected because PyInstaller directly supports the existing Python/PySide6 application and the required private smoke boundary. Evaluating a broader packaging stack is disproportionate before a normal release is authorized.
