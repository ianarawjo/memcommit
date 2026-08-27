# Retained-history application ownership design rationale

## Decision

The retained-history package lives at
`memcommit.application.retained_history`. Its central responsibility is to
interpret persisted checkpoints, operation receipts, Context snapshots, and
lineage evidence in order to reconstruct, validate, and provide usable Memory
and Context history. That is application behavior: persistence supplies the
records and interfaces present the resulting projections.

## Boundary retained by this move

This change establishes one physical owner without changing behavior or
splitting the existing package. The current package still contains storage-
aware checkpoint/catalog code and console-oriented display/review projection;
those dependencies are explicit follow-up seams rather than evidence that the
root package should remain unclassified. Later work may move low-level record
I/O under `persistence` and terminal presentation under `interfaces/console`
after their contracts can be separated without changing reconstruction
semantics.

In particular, persistence Store mixins still call retained-history helpers
while reconstruction services load through `MemoryStore`. This pre-existing
bidirectional seam is preserved rather than disguised by a new facade; a later
split must place record codecs and mutation primitives below the application
service before enforcing a strict one-way dependency gate.

The relocation adds no `memcommit.retained_history` compatibility facade.
Existing historical root aliases such as `memcommit.history` continue to map
directly to the new application owner, while new internal imports use the
canonical package.

## Non-goals

- No checkpoint, lineage, reconstruction, or trace behavior changes.
- No persistence schema or retained-record migration is introduced.
- No display or applied-review API is redesigned in this step.
- The internal reconstruction package remains intact for later responsibility
  analysis.
