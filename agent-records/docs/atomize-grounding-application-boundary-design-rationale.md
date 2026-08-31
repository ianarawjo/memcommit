# Retired Atomize Grounding application boundary

Last reviewed: 2026-08-30.

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

## Removed compatibility boundary

The former read/restore-only compatibility surface is also removed. There is
no `memcommit.application.operations.semantic_updates.derive.atomize.grounding` model package, Store
path or reader, Context-deletion hook, retained-history validator, companion
Undo/Redo restoration, or exact-command reconstruction for Atomize Grounding.
Keeping those readers made persistence, history, deletion, and restoration
continue to recognize Grounding as an Atomize-owned operation even after its
executable route was retired.

Historical `atomize-grounding` checkpoints still contain ordinary before and
after Context snapshots. Common history reconstruction may therefore report
their Memory changes from snapshots, and command restoration may restore the
Context state without synchronizing a retired companion session. It no longer
validates or projects the Grounding dialogue, proposals, reasons, or exact
resume command.

Existing `atomize-groundings/` and `atomize-grounding-history/` files are left
untouched as inert user artifacts. No current operation reads, writes,
restores, or deletes them. Automatic deletion or migration would be a separate
data-lifecycle decision and is intentionally outside this boundary change.

## Invariants

1. New Atomize execution never authors a Grounding session, turn, response,
   decision, proposal, or history record.
2. Persistence, retained history, Context deletion, and Undo/Redo contain no
   Atomize Grounding-specific branch.
3. Historical Context snapshots remain generic history/restoration input, but
   Grounding-specific payloads have no active decoder or semantic authority.
4. The absence of a current resolution route is explicit. Atomize does not
   manufacture a handoff schema or silently reinterpret a finding.
5. Existing artifact files are not rewritten or deleted merely because the
   compatibility code was removed.

## Alternatives considered

Keeping a dormant public Grounding facade was rejected because a callable
Start or Reply method would still advertise issue resolution as an Atomize
responsibility. Keeping only the data model draws a testable line between
historical compatibility and current capability, but it was ultimately
rejected because the Store and history layers still had to own that model.

Automatically translating legacy dialogues into a new resolution record was
also rejected. There is no independently specified consumer contract yet, and
translation could invent provenance or resolution semantics.

The earlier decision to keep every Grounding type and Store path for legacy
decoding was reconsidered. It preserved operation ownership throughout the
Store, history, restoration, and deletion layers without an active consumer.
Generic Context snapshots retain the durable Memory-state evidence that common
history and restoration need; the Grounding dialogue itself is no longer a
supported runtime contract.

## Verification

Ownership tests assert that every executable, model, persistence, and history
Grounding module is absent. Store, restoration, retained-history, public
Python, and agent tests cover the remaining generic boundaries and assert that
no Grounding route is exported or registered.
