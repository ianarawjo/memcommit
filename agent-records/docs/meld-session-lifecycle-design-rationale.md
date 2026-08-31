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

## Physical model ownership

The public `memcommit.application.operations.semantic_updates.curate_integrate.meld.model` import remains a
compatibility facade, but its implementation is split by responsibility:

- `source_snapshot.py` freezes source Memories, Context identities, roles,
  digests, and the strict shared value primitives used by later records;
- `integration_proposal.py` owns the relation ledger, issues, proposals,
  assessments, dialogue turns, and Compare/preservation projections;
- `apply_effects.py` owns the exact change set and durable Apply/checkpoint receipts;
- `proposal_session.py` composes those records into construction, lifecycle
  transitions, cross-record validation, and exhaustive source/result
  accounting.

The dependency direction is `proposal_session -> apply_effects ->
integration_proposal -> source_snapshot`. `integration_proposal` uses a
type-only proposal-session reference for its
provider-free preservation projection, so importing the lower-level records
does not construct the session aggregate. This keeps names tied to Meld's
pipeline language while preserving existing serialized schemas and the public
`meld.model` facade. The currently stored aggregate does not yet expose a
separate candidate-context or integration-plan record; those types belong to
the subsequent semantic pipeline change and are not represented by empty
placeholder modules in this ownership-only relocation.

## Physical runtime ownership

The public `memcommit.application.operations.semantic_updates.curate_integrate.meld.runtime` import remains a
compatibility facade, but its Store, Grant, provider, and checkpoint adapters
are split into four Meld-specific owners:

- `source_access.py` owns authorized source loading, exact frozen-frame
  revalidation, target traversal, and the bindings saved in checkpoints;
- `preparation.py` owns shared relation-basis reuse or live creation,
  prewarm selection, and the provider-free/provider-required preparation of
  Start and Restart;
- `session_repository.py` owns saved-session CAS plus preservation and
  destination persistence ports;
- `proposal_iteration.py` owns the provider timeout policy, assessment cache,
  and follow-up execution;
- `apply_transaction.py` owns proposal permission checks, checkpoint records, interrupted
  Apply recovery, post-image verification, locking, rollback, and mutation.

The dependency direction is `preparation -> proposal_iteration ->
session_repository -> apply_transaction -> source_access`, with the phase
adapters importing lower owners directly where needed. The facade contains
re-exports only and preserves the former explicit `__all__`; tests patch
dependencies at their physical owner rather than requiring mutable proxy
behavior from the facade.

`apply_transaction.py` remains the largest module intentionally. Its local target,
local-owner subtree, granted-owner subtree, and granted-target paths differ in
lock ownership, authority revalidation, checkpoint placement, and rollback.
Keeping those transactions beside their recovery evidence makes partial
publication review explicit until a genuinely shared transaction abstraction
exists.

## Physical provider ownership

The provider pipeline is split by the direction in which trusted application
state crosses the semantic provider boundary:

- `contract.py` owns provider limits, wire-contract versions, the provider
  protocol, semantic execution policy, and output schemas;
- `projection.py` assigns stable opaque aliases and projects typed Meld state
  into the provider-visible payload;
- `request.py` binds that payload to the exact prompt, schema, budget, and
  cache/request digest;
- `decoder.py` strictly parses one complete response and reconstructs a typed
  `MeldAssessment` without trusting provider-supplied durable identities;
- `execution.py` owns the bounded initial and repair calls and composes the
  preceding stages.

Unlike `meld.model` and `meld.runtime`, `meld.provider` intentionally has no
compatibility facade. Its package initializer imports and exports nothing;
production consumers use the narrow owning module directly. This is a
forward-only internal boundary: retaining the old aggregate imports would hide
ownership and allow new callers to rebuild the same monolith through a
convenient package root. The physical split itself did not change prompts,
schemas, aliases, request digests, one-shot limits, repair rules, or provider-
call count. The later relation-first Start correction does: a Directional
cache miss now performs one shared relation-analysis call before its separate
materialization call, and the latter uses a schema that cannot return relation
fields.

## Deliberate non-goals

This slice does not create a generic persisted session schema. Atomize, Meld,
Sever, Fit, and the remaining operations keep their operation-owned records,
digest inputs, visibility, and recovery meaning. A future neutral helper should
be extracted only after the remaining repositories show the same validation
shape without erasing differences such as Meld's reconstructed Apply retry.

This slice also does not change Meld cache equivalence or projection. Those
proofs remain under `CACHE-01`; this lifecycle only guarantees that a cache hit
cannot be published over a different saved revision.

The package split deliberately does not redesign records, session transitions,
validation rules, or adapter behavior. It is an ownership refactor whose
compatibility boundary is the existing `meld.model` facade and byte-for-byte
equivalent `to_dict()`/`from_dict()` contracts.

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
- structural verification compares every original model class, decorator, and
  method surface with the split package, and import/serialization smoke tests
  exercise the compatibility facade.
