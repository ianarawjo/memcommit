# Shared review-to-Apply phase flow rationale

## Status

`memcommit.application_flow` owns the minimal operation-neutral phase order
`PREPARED → REVIEWED/CANCELLED → APPLIED`. Update consumes it through
`memcommit.update_application_flow.UpdateApplicationFlowPort`; Sever is the
second consumer through
`memcommit.sever_application.SeverSessionApplicationFlowPort`.

The second vertical slice establishes that the phase contract can serve both
target mutation and require-new result creation. It still does not claim that
Update, Sever, Meld, Atomize, or Merge share one mutation algorithm or receipt
schema.

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

Its operation-owned `apply()` retains the previous order exactly:

```text
load and compare the accepted session snapshot
  → create the require-new Result Context
  → CAS-save the APPLIED Sever session and receipt
```

The Result creation remains before the session CAS save. Moving that boundary
would change the documented crash and recovery behavior, so the shared flow
does not attempt to make the two writes generically atomic. An already APPLIED
snapshot also retains its existing idempotent `created=False` result without
materializing the output again.

## Preserved boundaries

- Provider planning, hidden prewarm lookup, and session staging happen before
  the shared application flow.
- Review presentation and ownership-aware review policy remain separate from
  the operation-neutral phase order.
- The three Update persistence transactions retain their current locks,
  authority checks, CAS, rollback, checkpoint, and receipt implementations.
- Undo and Redo continue to consume Update checkpoint receipts; the shared
  flow neither implements nor weakens recovery.
- Sever keeps its Source unchanged, require-new output rule, result checkpoint,
  saved-session CAS, and existing recovery boundary.
- No visible TUI state or keyboard path changes in either extraction, so the
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
review revisions, destination changes, stale session rejection, exact output
materialization, idempotence, source preservation, checkpoints, Undo, and
Redo. The next extraction should test a third semantic shape rather than add
operation-specific policy to the common module; Meld is a candidate because
its reviewed result can preserve or replace several source frames.
