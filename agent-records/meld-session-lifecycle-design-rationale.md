# Meld saved-session lifecycle

## Status

Meld's saved-session actions now use one explicit revision contract across the
terminal application boundary, public Python facade, agent adapter, and MCP
projection. `open` returns an opaque canonical-digest version. Every subsequent
mutation must submit that version; a stale action fails before provider
construction, cache execution, session replacement, or target mutation.

## Motivating problem

The terminal workbench already captured the current session digest before each
turn, defer, preservation, destination change, or Apply. The public Python and
agent routes were asymmetric: a free-form comment could omit the version, and
preserve, defer, and Apply reopened whatever revision happened to be current.
An action composed from one reviewed screen could therefore operate on a newer
saved review without naming that change.

The stable nonterminal sequence is now:

```text
open(target) -> session + opaque version
saved mutation(target, expected_version=version, ...)
  -> load current snapshot once
  -> validate the reviewed version
  -> prepare operation-owned action
  -> revalidate authority and frozen inputs
  -> provider/cache work when applicable
  -> CAS-publish one complete session revision or Apply receipt
```

## Action contract

| Action | Version rule | Provider | Durable effect |
| --- | --- | --- | --- |
| Start | target must have no saved session | cache or provider according to the frozen Start plan | create one initial review; symmetric create-target remains atomic |
| Open | none; read-only | never | none |
| Restart | literal current version | only after the old version and complete inputs are frozen | replace one complete review by CAS |
| Comment or exact issue response | literal current version | cached complete branch or one bounded turn | replace one complete assessed revision by CAS |
| Preserve | literal current version | provider-free for the current symmetric schema; otherwise the ordinary bounded turn | replace one complete reviewed revision by CAS |
| Defer | literal current version | never | save `KEPT_REVIEW_ONLY` by CAS; target unchanged |
| Change destination | the typed snapshot's literal version | never | relocate the empty symmetric Result and session together |
| Apply | literal current version, or the exact reviewed predecessor of an already-applied session | never | one operation checkpoint or verified recovery of that same receipt |

Terminal completion releases the target's mutable work slot. `APPLIED` and
`KEPT_REVIEW_ONLY` records remain immutable UID-addressed evidence. A plain,
provably different Source request automatically enters the same typed Restart
and CAS boundary; an exact terminal retry remains provider-free. `--restart`
is still required to reanalyze an indistinguishable request or deliberately
replace unfinished work. The Meld setup launcher's `New` action supplies that
explicit signal when its selected target already has a saved session.

Terminal predecessors are archived only when the replacement is ready to
publish, under `meld-session-history/<target-uid>/<session-uid>.json`. Failed
provider work leaves the predecessor active. Impact and Review resolve both
the target-scoped latest slot and retained terminal UIDs; retained rows are
view-only and cannot be resumed into Apply.

The Apply retry exception is deliberately narrow. An applied Meld retains its
complete typed application receipt. The application layer can clone that saved
session, clear the exact receipt, and hash the reconstructed `READY_TO_APPLY`
predecessor. The original reviewed version is accepted only when it equals that
digest. The runtime then verifies the checkpoint and full post-image and reports
`recovered`; it cannot create a second checkpoint. Arbitrary older versions and
predecessors of comment, preserve, or defer remain stale.

Ready zero-change directional Melds follow the same rule. Apply still records
one operation checkpoint with zero result Memories, and retry verifies and
returns that receipt provider-free. A no-op is therefore explicit completion,
not absence of a session transition.

## Ownership and interface boundary

`meld_session_application.require_meld_session_version` owns the version match
and exact Apply-predecessor reconstruction. The Store adapter still owns the
canonical-digest CAS, Context and Grant revalidation, checkpoint recovery, and
rollback. Interfaces do not compute or interpret versions.

- CLI and TUI continue to carry their typed `MeldSessionSnapshot`; their visible
  flow and key bindings do not change.
- `MemCommitClient` requires `expected_version` for comment, preserve, defer,
  and Apply, matching the existing Restart requirement.
- `memcommit_meld` requires the same field for every saved-session mutation.
  `start` and read-only `open` are the only actions without it.
- The pre-release adapter contract is intentionally forward-only. There is no
  permissive fallback that silently targets the latest session.

## Deliberate non-goals

This slice does not create a generic persisted session schema. Atomize, Meld,
Sever, Fit, and the remaining operations keep their operation-owned records,
digest inputs, visibility, and recovery meaning. A future neutral helper should
be extracted only after the remaining repositories show the same validation
shape without erasing differences such as Meld's reconstructed Apply retry.

This slice also does not change Meld cache equivalence or projection. Those
proofs remain under `CACHE-01`; this lifecycle only guarantees that a cache hit
cannot be published over a different saved revision.

## Verification

- lifecycle unit tests cover exact matches, stale rejection, and the single
  applied-predecessor retry;
- public and agent tests require and forward the opaque version for every saved
  mutation and prove stale requests stop before their execution boundary;
- an end-to-end public API test opens a zero-change review, applies it, and
  replays the original reviewed version while proving one provider call and one
  checkpoint;
- the Meld regression set covers Start, Restart, cache/provider assessment,
  provider-free preservation, zero-change Apply, four authority routes,
  interrupted-receipt recovery, Undo/Redo, CLI/TUI resume, and saved catalogs.
