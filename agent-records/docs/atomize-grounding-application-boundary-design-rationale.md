# Retired Atomize Grounding application boundary

Last reviewed: 2026-08-29.

## Current status

Atomize Grounding is no longer an executable operation. The former console,
Python, agent, application, runtime, provider, and Atomize-to-Meld adapter
routes were removed. `mem atomize` no longer accepts `--evaluate`, `--reply`,
`--revision`, `--accept-grounding`, or `--keep-review-only`, and no registered
agent tool can start or advance such a dialogue.

This retirement follows the operation-responsibility decision recorded in
[`atomize-read-only-findings-design-rationale.md`](atomize-read-only-findings-design-rationale.md):
Atomize records structural ambiguity or conflict but does not resolve it.
Resolution or disambiguation belongs to a later independent operation, not to
an Atomize sub-workflow.

## Preserved compatibility boundary

The model package at
`memcommit.application.operations.atomize.grounding` remains solely to decode
and validate records written by earlier versions. Store paths and methods for
the latest session and retained session history also remain. They are used by:

- retained-history and checkpoint verification;
- Undo/Redo restoration of historical Atomize Grounding checkpoints;
- Context deletion cleanup; and
- tests that prove old serialized records still round-trip and fail closed
  when malformed.

No active Atomize command, Python facade, agent adapter, provider path, or Meld
path imports this package to start new work. Compatibility code may restore the
bytes belonging to an old command unit, but it cannot reassess a turn or apply
a new Grounding proposal.

## Invariants

1. New Atomize execution never authors a Grounding session, turn, response,
   decision, proposal, or history record.
2. Loading or restoring legacy Grounding data performs no provider call and
   grants no new mutation authority.
3. Existing Grounding checkpoint payloads remain verifiable; Context deletion
   still removes only the matching Context's legacy artifacts.
4. The absence of a current resolution route is explicit. Atomize does not
   manufacture a handoff schema or silently reinterpret a finding.
5. Historical data is not rewritten or deleted merely because a newer
   Atomize analysis runs.

## Alternatives considered

Keeping a dormant public Grounding facade was rejected because a callable
Start or Reply method would still advertise issue resolution as an Atomize
responsibility. Keeping only the data model draws a testable line between
historical compatibility and current capability.

Automatically translating legacy dialogues into a new resolution record was
also rejected. There is no independently specified consumer contract yet, and
translation could invent provenance or resolution semantics.

Deleting every Grounding type and Store path was rejected because old
checkpoints and research records would become unreadable and restoration could
no longer validate their exact command unit.

## Verification

Ownership tests assert that every executable Grounding module and adapter is
absent while the legacy model remains lazy and concept-owned. Model,
retained-history, Store lifecycle, and restoration suites retain coverage for
old records. Public Python and agent tests assert that no Grounding route is
exported or registered.
