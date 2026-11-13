# 0023: Coordinate native journal relocation and explicit recovery

- Status: Accepted for the authorized fourth redesign slice; source verification complete, user review pending
- Date: 2026-11-12

## Context

[Section 38.13](../product-spec.md#3813-authorized-fourth-implementation-slice-journal-relocation)
authorizes Settings Choose folder → review → Move and restart. GUI and CLI must agree
on one active journal. Older installed snapshots ignore a new locator, and filesystem
changes across several files are not one SQLite transaction. Neither a lease known
only to new clients nor renaming away the old pathname is sufficient.

## Decision

Keep a fixed bootstrap for each existing identity. Format-1 identity, active-location
and move records live there beside a shared-access lock; `presentation.ini` stays
separate from those records. Explicit database injection bypasses user bootstrap;
tests can instead inject an entirely disposable managed bootstrap. Existing managed
locations use SQLite `mode=rw` with recognized-history preflight: an empty, unrelated
or missing configured file cannot be initialized as a replacement. Only a genuinely
new, uninitialized default profile can create its first database. Supported older
backups retain their ordinary recovery-backed upgrade/refusal rules.

Ordinary GUI/CLI runtimes hold a shared Windows byte-range lease. Movement/recovery
requires its nonblocking exclusive form; ordinary concurrent use remains supported.
The initiating GUI drains its own read workers and closes SQLite before releasing its
lease. Failure before protection reopens that same database object in place, keeping
its application repositories valid. Uncertain authority blocks data actions instead.

Under the exclusive lease, a native source handle requests read/write access while
sharing reads only. This refuses existing writable handles, including clients that
know nothing about the lease, and excludes new writers/deletion. Read-only admission,
integrity/foreign-key checks and serialization capture the complete supported SQLite
image, including committed WAL pages. Distinct recovery and destination files are
flushed and verified by full-image hashes and database admission. A destination
reservation binds identity, journal token, bootstrap and move generation; existing
journals, notices and reserved files are never overwritten.

Persist the move record and companion old-path notice, then set/flush the source's
native read-only attribute **before** changing its header. The already-open fenced
handle can write/flush a non-SQLite notice and truncate the former body without a
missing-path window. Persistent read-only protection matters even when WAL could
supply an older valid page one. Older ordinary entry points cannot write the source
or create a writable empty replacement. The distinct full SQLite recovery remains.

Atomically install flushed metadata, re-resolve and verify the destination through
the shared location boundary, then record completion. Reconstruct the whole GUI
runtime with the same identity after closing the old window. This uses the existing
QApplication process and a fresh window/database/workspace rather than reconstructing
shell commands or guessing the installed launcher. Appearance/geometry remain;
transient retrieval, report and draft state start fresh.

### Interrupted phases

Ordinary startup refuses pending moves. The GUI offers one state-appropriate explicit
action; CLI directs recovery to the updated GUI, without choosing a copy:

- Before persistent source protection, **Keep current location** validates the
  current source and cancels the pending switch. Later legacy commits remain in that
  source; recovery never rolls them back to an earlier snapshot.
- After protection, **Verify and finish move** checks file identities, paired image
  hashes/admission, generation/ownership, read-only protection, the known original or
  partial notice bytes and canonical sidecar hashes. It never temporarily unprotects
  the old pathname. If interruption preceded header retirement, the old location may
  retain a read-only original with its companion notice; it is not a writable journal.
- Missing, changed or ambiguous evidence stops recovery and retains all artifacts.
  Completed recovery/staging copies are not automatically purged. No operation log,
  arbitrary journal switcher or import workflow is added.

This is coordination for ordinary application entry points, not authentication
against manual file/permission tampering. SQL schema 21, immutable migrations, scoring,
projection 3, CSV 6 and production dependencies remain unchanged. SQLite backups still
contain the complete journal; host location/appearance metadata is separate.

## Storage and evidence limits

Support is bounded to unsynchronized local fixed NTFS folders on Windows. Reject UNC,
removable/non-NTFS storage, reparse aliases, hard-linked journals and known OneDrive
roots. Arbitrary third-party synchronization cannot be detected reliably; the user
must choose an unsynchronized folder. A previous notice is retained rather than
overwritten when selecting a destination. Another unused folder is supported.

Tests kill a separate process at each durable boundary, exercise committed WAL and
historical GUI/CLI snapshots, and verify exact images and explicit recovery. Native
captures use the actual Qt widgets. See the [dated evidence](../archive/releases/2026-11-12-journal-relocation-verification.md)
for source, device and test limits. Process-interruption tests do not prove every
physical power-loss/controller configuration or every Windows scaling condition.

The Win32 sharing and read-only semantics follow
[CreateFileW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-createfilew)
and [SetFileAttributesW](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-setfileattributesw).
Metadata installation uses [MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw)
after flushing the file; the protocol retains phase-aware recovery rather than claiming
joint atomicity across those files and SQLite.
