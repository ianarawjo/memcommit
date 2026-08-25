# Shared review-to-Apply phase flow rationale

## Status

`memcommit.application_flow` owns the minimal operation-neutral phase order
`PREPARED → REVIEWED/CANCELLED → APPLIED`. Update consumes it through
`memcommit.update_application_flow.UpdateApplicationFlowPort`; Sever is the
second consumer through
`memcommit.operations.sever.application.SeverSessionApplicationFlowPort`;
Meld is the third consumer through
`memcommit.meld_application_flow.MeldApplicationFlowPort`.

These vertical slices establish that the phase contract can serve target
mutation, require-new result creation, and multi-owner reconciliation. They
still do not claim that Update, Sever, Meld, Atomize, or Merge share one
mutation algorithm or receipt schema.

## Motivation

Update previously joined its review and persistence branches directly in the
CLI command. The command selected interactive review, incorporated an optional
new revision, then chose one of three application functions:

- local Source and local Target;
- granted Source with a local Target; or
- a granted Target, optionally with a granted Source.

Each persistence function already performs the difficult operation-specific
work: exact session comparison, authority and freshness revalidation, complete
plan preflight, locks, CAS, rollback, checkpoints, and an application receipt.
Moving those transactions into a generic helper would erase meaningful safety
differences. The reusable part is the smaller phase boundary: cancellation
must stop before Apply, a revised review must replace the prepared revision,
and success must expose a receipt-bearing result.

## Contract

The shared flow accepts one opaque prepared value and one operation adapter:

```text
prepared
  → adapter.review(prepared)
      → None: CANCELLED, adapter.apply is unreachable
      → reviewed revision
  → adapter.apply(reviewed revision)
      → durable operation-owned receipt
  → APPLIED result
```

The common module imports no CLI, TUI, Store, provider, authority, or operation
module. It owns only phase ordering and typed terminal evidence. An exception
from review or Apply propagates and cannot be projected as an `APPLIED` flow
result.

The port's `apply()` call is the atomic semantic boundary. Before returning it
must revalidate the exact reviewed value and durably publish its operation's
receipt, or publish no effect. The common flow cannot manufacture CAS,
rollback, checkpoints, or Undo merely from a generic callback.

## Update adapter

The Update adapter is terminal-independent and receives all integrations as
injected callables. The command composes it with the existing review function
and the three existing persistence functions.

| Reviewed Update ownership | Existing transaction selected |
| --- | --- |
| local Target | `MemoryStore.apply_staged_update` |
| granted Source, local Target | `apply_granted_source_staged_update` |
| granted Target | `apply_granted_staged_update` |

A granted Target takes precedence when both endpoints are granted because it
identifies the Context graph that will actually be mutated. A granted Source
alone remains read-only evidence and routes to the local Target transaction.

Noninteractive Update returns the staged session as its reviewed value, which
preserves the existing plain CLI behavior. Interactive review may return a new
staged session after comment incorporation; only that returned revision enters
Apply. Cancellation leaves the staged session available and does not call any
applier.

The adapter verifies that the returned Update is `APPLIED`, has an application
receipt, and differs from the reviewed session only by lifecycle status and
that receipt. The persistence functions retain their stronger in-transaction
freshness and receipt validation.

## Sever adapter

Sever has a different review lifecycle. Candidate choices and destination
changes are persisted as optimistic-CAS session revisions while the workbench
is open. By the time the person chooses final Apply, the prepared value is
therefore already the exact reviewed `SeverSessionSnapshot`. The Sever
adapter's `review()` is intentionally an identity handoff rather than a second
UI or review loop.

Its operation-owned `apply()` keeps Result creation before the private receipt:

```text
load and compare the accepted session snapshot
  → recover an exact Result left by an interrupted prior Apply, or
    create the require-new Result Context
  → CAS-save the APPLIED Sever session and receipt
```

The two stores still cannot share one filesystem transaction, so the Sever port
owns operation-specific compensation and recovery. A synchronous session-CAS
failure re-reads the session: a receipt that actually committed is returned as
success, an unchanged REVIEWING session causes deletion of only the exact
untouched Result and checkpoint created by this attempt, and an indeterminate
or concurrently changed state fails closed without deleting anything. After a
process interruption, a later Apply adopts an existing Result only when its
Context digest and sole Sever checkpoint exactly match the accepted session;
an unrelated occupant remains a require-new name collision. An already APPLIED
snapshot remains idempotent with `created=False`.

Local Source and Criteria snapshots are checked under the local output-creation
lock. Granted inputs additionally revalidate the frozen Profile, Grant UID,
revision, permissions, public/resource mapping, and complete projected frame
immediately before and after Result creation while the grant registry is
frozen. A change during that boundary rolls the exact new Result back before
any session receipt is published.

## Meld adapter

Meld is the first consumer whose reviewed session is intentionally mutable.
The workbench persists every provider assessment, issue response, and optional
destination move before final acceptance. The accepted `MeldSession` must then
be the same object mutated to `APPLIED`, because existing command and recovery
callers observe that lifecycle transition after the transaction returns. The
adapter therefore performs an identity review handoff and does not clone or
reinterpret the session.

The common flow calls one Meld-owned dispatcher, which retains four distinct
application transactions:

| Reviewed Meld shape | Existing transaction retained |
| --- | --- |
| symmetric or legacy single Target | one Target checkpoint and session receipt |
| directional owner-aware local subtree | per-owner checkpoints with rollback |
| directional granted Target | authority-owned checkpoint and participant receipt |
| granted owner-aware subtree | per-owner authority checkpoints with rollback |

The adapter validates only the returned boundary evidence: the session reached
`APPLIED`, its application checkpoint matches the returned checkpoint, and its
recorded result count matches the receipt. Locks, Grant revalidation, source
freshness, target CAS, rollback, recovery, and checkpoint composition remain
inside the existing operation dispatcher.

## Preserved boundaries

- Provider planning, hidden prewarm lookup, and session staging happen before
  the shared application flow.
- Review presentation and ownership-aware review policy remain separate from
  the operation-neutral phase order.
- The three Update persistence transactions retain their current locks,
  authority checks, CAS, rollback, checkpoint, and receipt implementations.
- Undo and Redo continue to consume Update checkpoint receipts; the shared
  flow neither implements nor weakens recovery.
- Sever keeps its `SELF-SAVE` versus `OTHER-SAVE` location rule: self-save
  updates one exact local Source identity, while other-save keeps Source
  unchanged and publishes a require-new Result. Both routes retain their
  checkpoint, saved-session CAS, exact compensation, and interrupted-Apply
  recovery boundaries.
- Meld keeps all four application transactions distinct, including its
  granted-source lock recursion and owner-aware rollback boundaries.
- No visible TUI state or keyboard path changes in these extractions, so the
  previously captured operation interactions remain the applicable UI
  evidence.

## Verification and next consumer

Pure flow tests cover ordering, cancellation, missing values, and Apply
failure. Update adapter tests cover all ownership routes, revised-session
handoff, cancellation, invalid lifecycle values, and mismatched receipts. The
existing Update suite exercises the connected path across local and granted
application, no-op, stale CAS, multi-owner rollback, checkpoints, idempotence,
Undo, and Redo.

The Sever application tests exercise the second connected path across saved
review revisions, destination changes, local and granted input freshness,
Grant revision and revocation, name races, all-KEEP materialization, exact
output compensation, interrupted-Apply recovery, late-success detection,
idempotence, Source preservation, checkpoints, Undo, and Redo. Meld adapter
and command tests exercise the third connected path across
symmetric and directional modes, local and granted ownership, multi-owner
rollback, stale inputs and targets, crash recovery, idempotent acceptance,
checkpoints, Undo, and Redo.

The next extraction should either move one complete Meld transaction behind a
terminal-independent storage port, or test another operation's review adapter.
It should not add operation-specific mutation policy to the common phase
module.
