# Canonical History ownership design rationale

## Problem

The former `application.capabilities.retained_history` package mixed six
different responsibilities: checkpoint schema traversal, state reconstruction,
operation receipt correlation, Memory/Reference lineage, Undo/Redo stack
recovery, and terminal presentation. Trace also owned a second graph assembly
under its operation package. That layout made Log, Trace, and Rationale appear
to have different historical sources even though they were projections of the
same persisted evidence.

The motivating product model is now explicit: Log is the Profile-wide view of
what a person did; Trace is a Context or subject slice of that history; and
Rationale is an explanatory projection derived from the same evidence. Trace
and Rationale therefore consume History. They are not alternative owners of
history reconstruction.

## Decision

`memcommit.application.capabilities.history` is the sole canonical owner of
operation, state, effect, occurrence, relation, and evidence reconstruction.
Its physical responsibilities are named for what they do:

- `model/topology.py` owns immutable `HistoryGraph`, operation, step,
  occurrence, effect, and relation values.
- `reconstruction/history_graph_reconstruction.py` owns the complete assembly
  order and graph invariants.
- `reconstruction/checkpoint_state_projection.py` maps verified checkpoint
  frames to ordered Context states and direct Memory transitions.
- `reconstruction/operation_record_correlation.py` derives a logical operation
  identity only from explicit receipt fields, falling back to the physical
  checkpoint identity when a shared identity is not proven.
- `model/memory_event.py` owns the immutable Memory event vocabulary.
- `reconstruction/memory_history_reconstruction.py` walks retained checkpoints,
  Branch ancestry, restoration steps, and the current unrecorded frame.
- `reconstruction/memory_effects/derivation.py` orders evidence application and
  tracks which direct deltas have already been explained. Its `recorded.py`
  projects verified operation relations; `snapshot.py` projects remaining
  differences; `model.py` carries events, consumed identities, and warnings.
- `reconstruction/reference_occurrence_derivation.py` derives MemoryRef
  occurrences and relationship events without opening an unauthorized target.
- `history_evidence_source.py` is the read-only port for already authorized raw
  evidence. It contains no storage implementation.
- `query/` owns Context and Memory slicing plus semantic History queries.
- `verification/` owns retained-frame and operation-specific receipt checks.

`application.operations.log`, `application.operations.trace`, and
`application.operations.rationale` own their request/result semantics and
consume these History values. Log now has a typed Profile operation-timeline
boundary; the existing Context checkpoint and Memory routes remain compatible
while the broader Profile-default UX is decided separately.

## Reassembled adjacent responsibilities

The former package was removed rather than retained as a facade. Its remaining
parts moved to their actual owners:

- immutable applied checkpoint evidence belongs to
  `application.operations.review.applied_checkpoint`; terminal formatting
  belongs to `adapters.console.commands.review.applied_checkpoint_report`;
- History row display DTOs and styling belong to
  `adapters.console.terminal.components.history.display`;
- checkpoint-unit mutation belongs to `application.operations.revert`;
- Undo/Redo models, stack reconstruction, receipt metadata, and route selection
  belong to `application.capabilities.command_recovery`;
- Context snapshots and the checkpoint catalog remain independent application
  capabilities because neither is a History projection;
- checkpoint frame mapping and Context lifecycle schemas live beside their
  persistence records; and
- the reviewed rename-history repair belongs to the Rename operation.

This is reassembly, not semantic deletion. No checkpoint, receipt, Context
snapshot, recovery unit, Memory event, Reference occurrence, or public report
schema is removed.

## Invariants

1. Human-readable command descriptions and Memory text never determine graph
   connectivity or logical operation identity.
2. One logical operation may have several checkpoint evidence steps; a
   checkpoint UID is not promoted to a shared operation UID without a verified
   receipt.
3. The same Memory UID may have several state-anchored occurrences.
4. Grant is authorization metadata, not a History hierarchy or lineage edge.
5. A MemoryRef occurrence and its target Memory remain separate identities;
   target content is opened only through its own authorized route.
6. History reconstruction is read-only. Revert and Undo/Redo consume evidence
   but own their mutation and freshness boundaries.
7. Existing persisted schemas and on-disk data require no migration for this
   ownership change.

## Alternatives and limitations

Keeping `retained_history` as a facade was rejected because it would preserve
an ambiguous second owner and allow new imports to rebuild the old coupling.
Making Trace own the graph was rejected because Log and Rationale would then
depend on one projection operation instead of the common evidence model.
Treating Trace as merely a text filter was also rejected: it is a typed slice
that carries occurrence, relation, and authority semantics.

The current Log CLI still defaults to the historical current-Context report;
only its Profile operation route has been lifted behind the new Log
application contract. Making Profile Log the default is a separate product and
compatibility decision, not hidden inside this structural refactor. History's
read port is structural today: `MemoryStore` satisfies it directly, while a
dedicated persistence adapter can be introduced later without changing the
canonical reconstruction contracts.


## Memory effect responsibility split (2026-09-05)

The 1,520-line `memory_effect_derivation.py` still combined receipt-schema
validation, event construction, delta consumption, and temporal traversal after
the original History relocation. Changes to Translate schemas, Atomize review
evidence, or restoration ordering therefore required editing the same module.
The focused split completes those internal boundaries without changing History's
canonical ownership or persisted records.

Existing `verification/validators/add.py`, `atomize.py`, `chunk.py`, and
`branch.py` now own the corresponding integrity checks previously embedded in
event derivation. `translate.py` validates both retained translation schemas;
`command_operation.py` verifies Undo/Redo and Update command membership.
Translate, Chunk, and Atomize return operation-specific evidence values, not
`MemoryHistoryEvent` instances. Branch Source recovery also remains with its
validator so the event projector cannot invent an exact historical Source from
an older inherited snapshot. Reconstruction imports the narrow owners directly.

`memory_effects/derivation.py` keeps evidence precedence explicit: restoration
short-circuits ordinary interpretation; Atomize relations consume their proven
before/after identities; Translate and Context/legacy Chunk explain remaining
add/remove differences; ordinary snapshot effects follow; shared Update command
membership is attached last. Atomize Save As baseline events precede its
transformation events. A generic handler registry was not introduced because
this order and the different consumption rules are semantic contracts, not
interchangeable plugins.

Compatibility and safety boundaries:

- Context Chunk accepts its complete verified split set or none. Atomize retains
  valid individual changes even if another change is invalid; invalid reviewed
  evidence can degrade independently from a proven lineage relation.
- Normal-form Atomize may share a surviving result across proven changes.
  Consumed UID bookkeeping suppresses duplicate generic effects without rejecting
  that intentional relation topology.
- Event ordering, serialized fields, evidence levels, warning text, restored
  frame ordering, and HISTORY_GAP behavior remain unchanged. Verification neither
  opens additional Contexts nor writes state or calls a semantic provider.
- The old physical module is removed; source and test consumers import the
  event model or the temporal reconstruction entry point directly. This is an
  internal Python-path change, not an on-disk or public CLI schema migration.
- Existing frame/evidence models and unrelated graph reconstruction remain in
  their current owners. Remaining snapshot command-specific classification and
  Meld annotations are intentionally preserved; no new historical inference is
  introduced by this refactor.

Regression coverage includes explicit-relation consumption versus snapshot
fallback, independent Atomize degradation, atomic Context Chunk verification,
and restoration short-circuiting in `tests/test_memory_effect_boundaries.py`,
plus the existing History, Trace, Translate, restoration, and ownership suites.


Validation of this split:

- Primary checkout: `PYTHONPATH=src python -m pytest -q
  tests/test_memory_effect_boundaries.py tests/test_trace_lineage.py
  tests/test_trace_application.py tests/test_trace_rationale.py
  tests/test_translate.py tests/test_history_model.py tests/test_temporal_history.py
  tests/test_revert_history.py tests/test_update_checkpoint_history.py` — 123 passed.
- An isolated export of baseline `c83fc3bcc` with only the focused code/test
  changes ran 32 History/Trace/Rationale/Translate/Chunk/ownership test files:
  379 passed; the standalone-without-Ground import test failed identically on
  the unchanged baseline through Distill → Summarize → Meld → Resolve → Audit.
- A temporary differential test wrapper compared ordered event `to_dict()`
  values and warning lists against the pre-split transition implementation
  across 110 existing tests; all passed. The old implementation is not retained
  as a production facade or duplicate source in this repository.
- The broader primary ownership run also encountered a concurrently removed
  `study_scenarios/legacy/prewarm/atomize.py` path in its existing source
  inventory test (131 passed, one failed). That unrelated migration was left
  untouched; the functional History run above passed in the primary checkout.
- Focused Ruff undefined/unused-name checks, focused `git diff --check`, and
  `python scripts/verify_operation_evidence.py --check` passed.
