# Retained-history application ownership design rationale

## Decision

The retained-history package lives at
`memcommit.application.capabilities.retained_history`. Its central responsibility is to
interpret persisted checkpoints, operation receipts, Context snapshots, and
lineage evidence in order to reconstruct, validate, and provide usable Memory
and Context history. That is application behavior: persistence supplies the
records and interfaces present the resulting projections.

## Boundary retained by this move

The original relocation established one physical owner without changing behavior or
splitting the existing package. At that point, the package still contained storage-
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
- At the time of the original relocation, the internal reconstruction package
  remained intact for later responsibility analysis.

## Follow-up: retained-record verification boundary

The retained-record verifier now keeps its historical
`memory_history_reconstruction.retained_record_verification` import path as a
thin package facade while assigning physical ownership by concern:

- `model.py` owns evidence values and schema-version constants;
- `frame.py` owns Context snapshot normalization and frame comparison;
- `checkpoint.py` owns checkpoint catalog and common-field decoding; and
- `validators/` owns one module per operation-specific receipt contract,
  including separate owners for Add, Atomize, Branch, Chunk, Grounding, Meld,
  and Merge.

This split preserves the existing fail-closed contract: identities, digests,
receipt completeness, and before/after snapshots must still agree before a
claim becomes recorded evidence. It changes neither persisted schemas nor
history reconstruction semantics. Existing callers continue through the
facade so the structural refactor does not force an unrelated migration of
Trace, Rationale, Compare, Log, or console adapters.

A renamed monolith behind wrapper modules was rejected because it would change
the file layout without establishing real ownership. A combined Branch/Merge
validator was also rejected: both connect Context histories, but their receipt
schemas, disposition rules, and snapshot invariants are independent. The
remaining limitation is that the compatibility facade still re-exports
underscored helpers used by the two reconstruction stages; those imports may be
migrated to narrow owner modules separately once that internal API change is
deliberate.
