# Atomize Grounding public Python API

## Motivation

The Atomize Grounding lifecycle already had a terminal-independent application
contract, but callers still needed to import internal request and Store adapter
modules. A stable Python library entry point should let an agent adapter, MCP
server, notebook, or internal service open and advance the same durable review
without emulating CLI flags or importing command code.

## Public lifecycle

`MemCommitClient` exposes five deliberately separate calls:

- `open_atomize_grounding` reads the latest saved dialogue without provider
  access or mutation.
- `start_atomize_grounding` selects one visible issue and submits the initial
  grounding comment.
- `reply_atomize_grounding` submits one explicit Confirm, Extend, Correct, or
  Retract revision.
- `keep_atomize_grounding` closes the review as evidence without changing
  Memories or creating a checkpoint.
- `apply_atomize_grounding` applies or recovers the exact ready proposal in the
  existing single-checkpoint transaction.

Each method delegates lazily to
`memcommit.api._operations.atomize_grounding`. Importing `memcommit` or
`MemCommitClient` does not load the Grounding runtime, provider decoder, or
Store transaction adapter.

## Public values and errors

The API returns immutable projections rather than domain/session objects. A
session result includes its content digest as `version`, current state,
selected issue, current understanding, follow-up questions, exact proposals,
readiness, and application checkpoint when present. The Apply result adds the
change count and whether an interrupted receipt was recovered.

Caller input, missing Context or saved analysis, provider failure, concurrent
change, storage failure, and other execution failure are projected into the
operation-specific `AtomizeGrounding*Error` hierarchy. Provider objects and
internal command exceptions never become part of the public contract.

## Invariants

1. A relative Context locator is resolved once against the client Store's
   current-Context snapshot. The canonical name is used for every subsequent
   load and durable identity check in that call.
2. Open and Keep never connect a provider. Start and Reply connect exactly
   through the client-owned semantic-provider factory. Apply performs no new
   provider turn.
3. The public adapter reuses the same application runner and
   `MemoryStoreAtomizeGroundingPort` as the CLI. It does not duplicate proposal,
   freshness, checkpoint, or recovery rules.
4. Keep remains review-only: it changes neither Context bytes nor checkpoint
   count.
5. Apply retains the complete one-checkpoint and idempotent recovery contract.
6. Public results contain immutable data only; callers cannot mutate the saved
   domain session through a returned object.

## Chosen boundary and limitation

The first public boundary exposes the Grounding lifecycle, not automatic
Atomize analysis creation. Start and Reply require the Context to already own a
current saved Atomize analysis and workbench. Hiding analysis creation inside
Start would make one apparent operation perform two independently meaningful
provider turns and would blur which analyzed issue frame the dialogue accepted.

A later public Atomize analysis/review API can make this prerequisite convenient
while preserving it as an explicit step. Until then, a CLI/TUI-created saved
analysis is a valid input to the Python Grounding lifecycle.

## Alternatives considered

Exposing the internal request classes directly was rejected because it would
make `MemoryStore`, provider factories, and runtime port construction part of
the stable API.

One overloaded `atomize_grounding(action=...)` method was rejected because its
valid arguments, provider use, and mutation behavior would depend on a string
mode. Separate methods make those effects visible to both people and agents.

Returning the durable session object was rejected because it is mutable and
schema-owned. Immutable projections keep domain evolution behind the adapter
while preserving the information needed for review and subsequent actions.

## Verification

Focused public API and package-boundary tests cover root exports, lazy operation
assembly, provider-free Open, relative Context resolution, review-only Store
preservation, typed Start request assembly, provider-failure projection, and
missing-dialogue/input failures. The wider public API regression set also keeps
Add, Query, and Meld behavior in view.

A wheel built from the same working revision was installed into an isolated
Python 3.13 environment and imported from `site-packages` outside the source
checkout. All five client methods and public DTO identity were present, while
the Grounding operation adapter and runtime remained unloaded until method
selection.
