# Persistence ownership design rationale

## Status

The flat `memcommit/persistence/store.py` implementation was first divided into
coarse slices. Its physical owners are now explicit: shared mechanics and the
Context/Memory graph live under `memcommit.persistence.store`, while persisted
state belonging to Audit, Atomize, Meld, Review, and Update lives under
`memcommit.persistence.operations.<operation>`. `MemoryStore` remains the public
composition surface for existing callers, but it no longer gives operation state
one false shared physical owner.

## Motivating problem

The former module contained 10,118 lines and about 200 `MemoryStore` methods.
Its current layout mixed three broad change axes: working and operation state,
the live Context/Memory graph, and checkpoint recording/restoration. Deciding
every final component boundary at once would combine a physical module move
with semantic redesign across hundreds of importers and tests.

The first extraction therefore preserves method bodies and established call
ordering while making those three axes physically visible:

- `persistence/store/infrastructure/` owns shared paths, atomic-write primitives,
  protection, and lock mechanics;
- `persistence/store/context_memory/current.py` owns the current Context pointer,
  and `persistence/store/context_memory/` owns the rest of the live Context/Memory
  graph;
- `persistence/operations/{audit,atomize,meld,review,update}/` owns persistence
  whose schema and lifecycle belong to that exact operation;
- `persistence/store/context_memory/` owns the former lines 3,597-7,026: discovery,
  loading, rename, saving, creation, lifecycle, and query-source behavior for the
  current Context/Memory graph; and
- `persistence/store/checkpoint/` owns checkpoint recording, reading, and Revert,
  while `persistence/store/command_restoration/` owns command archives, Undo/Redo
  orchestration, and operation-specific restoration handlers. The former
  `record_restore_checkpoint.py` remains only as a compatibility composition.

The extracted files contain repeated imports and some remain larger than the final
desired components. Those are deliberate transitional costs, not evidence that the
three initial slices or the seven Context/Memory modules are final service boundaries.

## Context/Memory package decomposition

The second-stage split follows independently named persistence actions rather than an
arbitrary line limit:

- `catalog_scan.py` scans record headers into the ordinary Context catalog and reports
  typed omissions without following unsafe namespace entries;
- `addressing.py` resolves Context and checkpoint paths under one guarded storage root;
- `occupancy.py` decides whether a Context exists or a name can be created without
  colliding with pre-existing storage;
- `loading.py` owns direct, referenced, current, graph, and locked snapshot reads;
- `rename.py` plans and commits Context graph renames together with every persisted
  reference that must move atomically;
- `saving.py` owns ordinary, batch, Meld-target, and source-bound saves;
- `creation.py` owns create, branch, and create-missing transactions;
- `lifecycle.py` records lifecycle events and performs guarded deletion; and
- `query_source.py` stores and loads the separate Query Source record type.

These modules remain mixins because their existing transactions still collaborate
through one Store instance. `context_memory/__init__.py` composes them as
`ContextMemoryStoreMixin`, so existing imports and method resolution remain stable.
It also forwards legacy test overrides of atomic-write helpers to the defining modules;
that forwarding is a compatibility boundary, not a new persistence abstraction.

This change intentionally does not redesign transaction ordering, factor shared helper
calls into services, or alter record formats. Its purpose is to expose cohesive change
axes first, so a later extraction can introduce narrower actors without again moving a
3,500-line source file at the same time.

## Operation persistence and infrastructure decomposition

The former `operation_state.py` combined three dependency levels. Its second-stage
split assigns them as follows:

- `infrastructure/paths.py`, `atomic_io.py`, `protection.py`, and `locking.py` own the
  Store-wide persistence mechanics used by more than one record or session family;
- `context_memory/models.py` and `records.py` own Context transaction values, record
  validation, pointer rewriting, and canonical digests, while `query_source.py` now
  owns its own value objects and parsers; and
- `context_memory/current.py` owns navigation and the active Context pointer;
- `operations/update/state_repository.py`,
  `operations/review/state_repository.py`,
  `operations/meld/state_repository.py`, and
  `operations/atomize/state_repository.py` own their corresponding persisted
  working state; and
- `operations/audit/record_repository.py` owns immutable completed Audit records,
  while `application.operations.quality_resolution.diagnose.audit.repository` owns the repository port.

`MemoryStore` composes the common infrastructure, Context/Memory owner, operation
repository mixins, and checkpoint/restoration owner directly. There is no
`operation_state` package or `OperationStateStoreMixin`. The move preserves record
schemas, lock acquisition order, transaction meaning, and the established root
failure-injection surface.

The important dependency correction is that Context/Memory and checkpoint persistence
no longer import their record models, validators, and digests from a module named after
operation state. Context-aware protection and locking still consume those pure Context
contracts, and all components still collaborate through one combined Store instance;
that remaining coupling is explicit and intentionally deferred.

## Checkpoint and command-restoration decomposition

The former `record_restore_checkpoint.py` name combined a noun with two actions that
were not three peer responsibilities. Recording and listing are persistence operations
over the same checkpoint repository, while Revert applies one selected checkpoint or
checkpoint unit. Command restoration is a different workflow: it reconstructs a global
Undo/Redo unit and restores every affected Context and companion operation session.

The physical boundary now follows that distinction:

- `checkpoint/repository.py` records individual and batch checkpoints, lists them, and
  removes a provisional checkpoint during rollback;
- `checkpoint/revert.py` restores a selected Context snapshot or complete checkpoint
  unit while preserving Context identity and freshness checks;
- `command_restoration/archive.py` retains exact records and histories for commands
  whose Undo removes newly created Contexts, allowing Redo to restore the original
  identities rather than rerunning a changed Source;
- `command_restoration/engine.py` selects one ordered command unit, coordinates locks,
  commits Context and companion-session changes, and rolls the complete attempt back
  after an exception; and
- `command_restoration/handlers/` owns Branch, Merge, Atomize, Sever, and companion
  session restoration rules without moving their operation-specific receipts into the
  generic engine.

`record_restore_checkpoint.py` composes `CheckpointStoreMixin` and
`CommandRestorationStoreMixin` and forwards legacy failure-injection overrides. It owns
no checkpoint or restoration behavior. Every moved method body, lock boundary, CAS
check, archive format, checkpoint record, and rollback order remains unchanged.

## Compatibility boundary

`persistence/store/__init__.py` assembles the physical owners through inheritance so
existing `MemoryStore` callers retain their established `self` call graph.
New operation persistence belongs under `persistence/operations/<operation>` rather
than in that assembly. A small module adapter forwards established overrides of Store paths and atomic-write
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

The remaining architectural task is to replace mixin-to-mixin `self` calls with
narrow persistence actors or ports. Context-aware locking and protection should
receive an explicit record contract rather than reaching through the combined Store,
and operation adapters should depend on their operation repository rather than the
full `MemoryStore` surface.

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
The focused modules still call one another through the temporary combined instance,
and `infrastructure` still contains Context-aware coordination. Subsequent work must
remove those cross-slice assumptions instead of treating the current inheritance as
the completed design.
