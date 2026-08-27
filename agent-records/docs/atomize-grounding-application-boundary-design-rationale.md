# Atomize Grounding application boundary

## Motivation

Atomize Grounding began as one command module that selected a finding, opened
and revised provider-backed dialogue, checked durable freshness, applied Memory
changes, created a checkpoint, recovered interrupted receipts, and rendered the
CLI transcript. That made `mem atomize` the only practical entry point even
though none of those semantics inherently require a terminal. It also made the
one-checkpoint application and retry boundary difficult to review separately
from presentation code.

The extraction keeps the existing operation behavior while making the same
Grounding lifecycle callable by a future Python API, TUI adapter, or agent tool
adapter without importing `memcommit.commands`.

## Boundary

The Grounding slice is now divided into four responsibilities:

- `memcommit.application.operations.atomize.grounding_application` owns typed Start, Reply,
  Keep, and Accept requests, the port contract, application receipts, and
  result checks.
- `memcommit.application.operations.atomize.grounding_runtime` adapts that contract to
  `MemoryStore`, the semantic provider, CAS-style freshness checks, Context
  mutation, checkpoint recovery, and durable dialogue receipts.
- `memcommit.interfaces.cli.atomize_grounding` renders a saved dialogue without
  provider or Store access.
- `memcommit.commands.atomize.grounding` preserves the historical Python import
  surface as a thin compatibility facade. `memcommit.commands.atomize.command` uses the
  typed application/runtime boundary directly.

The former flat `memcommit.atomize_grounding_application` and
`memcommit.atomize_grounding_runtime` paths remain behavior-free
module-identity aliases for old imports, monkeypatch targets, and serialized
globals. Production consumers use the canonical operation package directly.
Co-location under `operations.atomize` does not merge Grounding with primary
Atomize application/materialization or with the Analysis open/cache slice:
each keeps its existing request, provider, authority, Apply, and receipt
contract. Consolidating those distinct contracts is an explicit non-goal of
this ownership-only relocation.

The CLI supplies its transient provider-progress wrapper when it constructs the
runtime port. Consequently the runtime can use progress in `mem atomize` while
remaining independent of terminal modules and command code.

## Invariants

1. Start and Reply each perform exactly one semantic assessment and publish no
   saved turn if the Context, analysis, workbench, saved response, or dialogue
   revision changes during that call.
2. Keep Review Only persists dialogue evidence but never changes a Context or
   creates a checkpoint.
3. Accept validates the complete accepted change set before mutating its
   in-memory Context and commits all grounded edits/additions in one Context
   save and one checkpoint.
4. A retry after the Context/checkpoint save but before the small dialogue
   receipt save recovers the exact checkpoint by session and change-set digest;
   it does not apply the changes twice.
5. Grounding opens only directly owned Memories for mutation. Child Context and
   `MemoryRef` target content do not enter this transaction.
6. The CLI transcript is a provider-free projection of durable state. Opening
   or rendering it cannot silently reassess the dialogue.
7. Existing command-level call signatures remain available through the facade,
   but new internal callers use typed requests and the runtime port.

## Alternatives considered

Keeping the 900-line command module and exposing it as the Python API was
rejected because it would make command progress, Typer-era naming, Store
details, and rendering part of the public application contract.

Moving the entire module to a differently named file without typed requests was
also rejected. That would change import paths without creating an enforceable
boundary for future adapters.

Putting provider progress inside the runtime was rejected because progress is a
terminal presentation concern. Injecting the progress wrapper retains the
current CLI feedback without making non-terminal callers emulate a TTY.

## Compatibility and limitations

This change deliberately does not alter provider prompts, saved Grounding
schema, session selection, proposal semantics, checkpoint payloads, error text,
or CLI transcript content. The existing `memcommit.commands.atomize.grounding`
functions remain supported during the migration.

The Store adapter still contains the existing transaction mechanics as one
focused runtime module. A later repository abstraction may split dialogue CAS
from Context materialization, but doing so here would widen the behavioral
change beyond an interface extraction.

The pre-existing Atomize workbench screen fixture currently describes older
classification wording. That golden-screen mismatch is not caused or repaired
by this boundary change; the underlying Grounding lifecycle tests remain the
behavioral authority until that presentation fixture is updated separately.
