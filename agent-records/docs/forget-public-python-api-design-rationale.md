# Forget public Python API rationale

Last reviewed: 2026-08-16.

## Decision

Expose the complete current Forget lifecycle from `MemCommitClient` as four
typed methods:

```python
review = client.analyze_forget(
    "Forget the old desk location.",
    context_name="campus/wiki",
)
review = client.select_forget(review, candidate_uid, "KEEP")
review = client.revise_forget(review, "Keep every current access detail.")
receipt = client.apply_forget(review)
```

`ForgetReviewResult` is an immutable process-local capability. It contains the
public review projection and privately retains the exact application snapshot
needed for later selection, provider revision, or Apply. It is not JSON,
pickle, or cross-process state and is not stored under `.mem`.

## Why process-local

The existing CLI review disappears when its process closes. Adding a saved
session solely for Python would change cleanup, privacy, resume, and stale-state
semantics. The public object therefore preserves the current lifetime:

- `analyze_forget` freezes one direct local or readable granted Source before
  provider construction;
- `select_forget` changes one reviewed candidate without provider or Store
  effects;
- `revise_forget` performs one new whole-frame provider turn over the original
  Source and dialogue;
- `apply_forget` returns an explicit no-op for all-KEEP, or revalidates
  authority and Source CAS before publishing one checkpoint; and
- losing the Python object loses the review but changes no durable state.

The public review is bound to the exact `MemCommitClient.store_root`. A review
from one client cannot be applied through a client for another Store. This is
checked before any mutation and prevents the private runtime binding inside a
review from redirecting an otherwise innocent caller.

## Public values

`ForgetCandidateResult` exposes the Source UID/content, recommendation,
rationale, current selection, and exact selected result. `ForgetReviewResult`
exposes the review UID, opaque version, Source identity, instruction, complete
candidate set, provider-use receipt, and `PROCESS_LOCAL` retention. It does not
expose provider dialogue, Grant internals, filesystem paths, or an executable
command.

`ForgetApplyResult` exposes exact removed/edited counts, checkpoint identity,
local Undo availability, granted state, and whether Apply changed the Source.
An all-KEEP result has `applied=False`, zero counts, and no checkpoint.

## Error taxonomy

Forget has operation-specific public errors because a destructive Source
revision should not be confused with a read-only generic semantic proposal:

- `ForgetInputError`: malformed requests, actions, or foreign review objects;
- `ForgetContextError`: unavailable Source;
- `ForgetAuthorityError`: local/Profile/Grant denial;
- `ForgetProviderFailure`: provider connection or completion failure;
- `ForgetConflictError`: Source changed before Apply;
- `ForgetStorageError`: durable state could not be read or written safely; and
- `ForgetExecutionError`: a complete requested result was not produced for a
  more operation-specific reason.

Provider response bodies, host paths, and internal tokens do not enter the
stable return values.

## Verification and limits

Focused tests cover Analyze/Select/Revise/Apply, explicit no-op, real Store
checkpoint publication, stale-Source conflict, cross-client Store rejection,
and lazy public exports. The public route calls the same application/runtime
functions as the CLI.

The API intentionally does not provide durable open/resume by UID. A future
saved Forget session would be a new storage contract, not a compatible
extension of this process-local value.
