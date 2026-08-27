# Store three-slice extraction rationale

## Status

The flat `memcommit/persistence/store.py` implementation was mechanically divided into
three coarse slices under `memcommit.persistence.store`.
`memcommit.persistence.store.MemoryStore` remains a temporary compatibility
assembly while callers still depend on the original combined method surface.
It is not the target architecture and must be deleted after callers move to
narrower persistence owners.

## Motivating problem

The former module contained 10,118 lines and about 200 `MemoryStore` methods.
Its current layout mixed three broad change axes: working and operation state,
the live Context/Memory graph, and checkpoint recording/restoration. Deciding
every final component boundary at once would combine a physical module move
with semantic redesign across hundreds of importers and tests.

The first extraction therefore preserves method bodies and established call
ordering while making those three axes physically visible:

- `persistence/store/operation_state.py` owns the former lines 1-3,596: shared path,
  atomic-write, protection, and lock mechanics plus Current and operation
  session persistence;
- `persistence/store/context_memory.py` owns the former lines 3,597-7,026: catalog, load,
  rename, save, create, query-source, and deletion behavior for the current
  Context/Memory graph; and
- `persistence/store/record_restore_checkpoint.py` owns the former lines 7,027-10,118:
  checkpoint recording, command archives, operation restoration, and Revert.

The extracted files contain repeated imports and remain larger than the final
desired components. Those are deliberate transitional costs, not evidence
that the three slices are final ownership boundaries.

## Compatibility boundary

`persistence/store/__init__.py` assembles the three method slices through inheritance so
existing `MemoryStore` callers retain their established `self` call graph.
New persistence behavior must not be added to that assembly. A small temporary
module adapter forwards legacy overrides of Store paths and atomic-write
helpers to the defining slices because the existing safety tests use those
overrides for isolated Profile roots and failure injection.

The adapter preserves only the prior root-module mutation behavior. It must be
removed together with `MemoryStore`; it is not a general module-proxy pattern.

## Invariants

- Existing `from memcommit.store import ...` imports remain valid through the
  centralized lazy alias during the migration, while repository code imports
  the canonical persistence owner.
- Active-Profile resolution is still frozen once per Store construction.
- Lock ordering, compare-and-swap checks, atomic replacement, rollback, and
  post-commit failure behavior do not change in this extraction.
- Context and Memory remain named together in the live-record slice; neither
  concept is hidden behind a generic `content` label.
- Checkpoint recording and restoration remain distinguishable even while they
  share one coarse file.
- No new caller may depend on the combined `MemoryStore` surface merely because
  the compatibility assembly remains available.

## Follow-up decomposition

After this mechanical split is stable, extract focused actors from one slice
at a time. Likely owners include path and atomic-write components, lock and
write-protection coordination, operation-specific session stores,
Context/Memory readers and writers, lifecycle actors, checkpoint recorders,
and operation-specific restorers. Migrate each caller to only the actor or port
it needs.

Completion requires all callers to stop importing or constructing
`MemoryStore`, removal of the compatibility forwarding adapter and inheritance
assembly, and deletion of any combined façade export from
`persistence/store/__init__.py`.
The package may remain as the persistence namespace; the façade must not.

## Rejected alternatives

- Renaming the original file without decomposition would not expose its
  independent change axes.
- Creating three newly designed standalone services in one change would
  require simultaneously rewriting their dense cross-slice lock and rollback
  calls, making behavioral regressions difficult to distinguish from the move.
- Keeping `MemoryStore` permanently as a façade would preserve the same broad
  dependency surface under a different filesystem layout.
- Dividing only by an arbitrary 1,500-line limit would separate transactions
  and restoration routines without respecting their safety boundaries.

## Intentional limitation

This stage improves physical navigability, not architectural independence.
The slices still call one another through the temporary combined instance, and
their approximate sizes remain 3,000-3,600 lines. Subsequent work must remove
those cross-slice assumptions instead of treating the current inheritance as
the completed design.
