# Private storage permission design rationale

## Status

MemCommit now creates ordinary private Store/Profile directories with POSIX
mode `0700` and JSON/byte artifacts with mode `0600`.  A content-preserving
migration helper can harden an existing legacy or managed Profile tree.  It
changes mode bits only: no Context, session, cache, checkpoint, or retained
analysis is deleted or rewritten.

## Threat boundary

This is defense in depth for a personally assigned workstation.  It prevents
other non-privileged local accounts from listing or reading MemCommit storage.
It does not protect data from the current user, a process already running as
that user, system administrators, `root`, MDM/endpoint software, backups, or an
upstream semantic provider.  Filesystem permissions are not encryption.

Durable retention and current application authority remain separate.  A
retained Grant-bound cache may remain on disk after Grant revocation, but an
operation must revalidate the exact live Grant and frozen source before it may
display, disclose, reuse, or Apply that artifact.  Revocation is not specified
as secure erasure in this research prototype.

## Invariants

- New Store and Profile control directories are owner-only (`0700`).
- Common atomic Store JSON and byte writes create owner-only files (`0600`)
  before any content is written; replacement preserves that mode.
- Existing directory modes are hardened when a write uses that directory.
- Explicit tree migration preflights every entry and refuses symbolic links or
  special files rather than following a path outside the selected root.
- Migration preserves every file byte and is idempotent.
- Read-only `MemoryStore(create=False)` construction does not silently migrate
  or create storage.  Migration is an explicit maintenance action; ordinary
  writes progressively harden the directories and files they own.
- Cache possession never bypasses operation-owned authority, digest, decoder,
  revision, CAS, or Apply validation.

## Limitations

The shared `CACHE-01` audit remains separate.  Provider identity completeness,
Grant-bound cache visibility after revocation, and exact/equivalent/projected
reuse still require operation-by-operation verification.  This permission
change narrows local filesystem exposure but does not claim those semantic
cache contracts are complete.
