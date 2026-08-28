# Update application boundary matrix

## Purpose

This note records the `APPLY-01` verification slice for Update. It separates
the shared review policy from Update's own application semantics so later
operation migrations do not copy an accidental Update-specific rule.

Update consumes one exact staged semantic plan. The mutation boundary follows
the owners of the Target Contexts that the plan will actually change, not the
presence of any Grant in the session and not the ownership of the Source.

## Operation ownership

`memcommit.application.operations.update.application` is the canonical owner of the
deterministic, non-persisting plan application contract. The Store and the
local-, granted-Target-, and granted-Source application paths consume that
contract but retain their own freshness, authority, multi-owner transaction,
checkpoint, and receipt responsibilities. Update has no independent operation
runtime module, so this relocation does not create one or absorb those
consumers into the package.

The former `memcommit.update_application` path remains a behavior-free
module-identity alias for import-order, monkeypatch, and serialized-global
compatibility. This ownership-only relocation changes no semantic plan,
preflight, CAS, authority, checkpoint, or zero-operation behavior and requires
no terminal screenshot refresh.

### Physical model ownership

The historical `memcommit.application.operations.update.model` import remains
the public compatibility facade, while its implementation follows five Update
concepts:

- `changes.py` owns source-linked ADD, EDIT, and REMOVE records, their strict
  parsing, operation digest, and derived Grant permission requirements;
- `receipts.py` owns frozen Context fingerprints and checkpoint/application
  receipts;
- `inputs.py` owns inline Source identity, Grant bindings, Source/Target
  candidates, focused-Memory selection, and exhaustive input collection;
- `session.py` owns persisted session serialization, lifecycle transitions,
  inline reconstruction, and stale/applied input matching;
- `planning.py` owns the provider contract, semantic budget, prompts, output
  schema, response validation, initial planning, and reviewed revision.

The dependency direction is `planning -> session -> inputs -> receipts ->
changes`, with higher layers importing lower concept records directly where
needed. The split deliberately does not alter serialized schemas, provider
payloads, cache identity, application behavior, or the operation-owned
application boundary described above. Explicit facade exports preserve the
former 40-name public surface while making physical ownership testable.

## Frozen behavior

| Case | Execution-decision behavior | Durable effect | Recovery |
| --- | --- | --- | --- |
| Local Target, one or more operations | A decision-free plan advances directly to Apply | All affected Target owners and the applied session receipt | One operation-unit `mem undo` / `mem redo` |
| Granted Source, local Target | Same as a local Source because the Source remains read-only | Local Target owners and the applied session receipt | One operation-unit `mem undo` / `mem redo` |
| Granted Target, one or more operations | Exact authority-sensitive decision remains mandatory in a TTY | Authority Target owners only after approval, plus the local applied receipt | Authority-aware command history; decision evidence is retained even when recovery exists |
| Any Target, zero operations | No additional decision because no Context mutation exists | Applied session receipt only | No Context checkpoint and no Context Undo unit |
| Unanswered required item or pending response | No automatic Accept | None until the item is resolved or the response is incorporated | Not applicable |
| Closed or cancelled authority decision | Session remains staged | No Target owner changes | Reopen the staged session through Update |
| Stale Source, Target, Grant, or session revision | Fail before publication | No partial success receipt | Re-run or reopen against current state |
| Optional Goal focus | Context/Memory/text frame guides relevance but supplies no `source_id` and authorizes no fact | Exact focus receipt is retained in the session and owner checkpoints | Durable Goal pre-image is locked and revalidated before Apply |

The zero-operation row is deliberately different from Merge. Merge can record
a command-level no-op checkpoint as an explicit graph reconciliation effect.
Update's existing application contract treats an empty operation tuple as a
validated completion receipt and writes no Context at all. The shared policy
therefore classifies it as mutation boundary `NONE`; it does not invent an Undo
checkpoint solely to make operations look alike.

## Integrity and failure boundaries

- Update freezes Source and Target identity, scope, Memory digests, optional
  typed Goal focus, operations, and session revision before Apply. The stored
  session uses compare-and-swap when it is revised or marked applied. Goal is
  a relevance/output criterion, never Source evidence.
- Local and granted application revalidate the frozen inputs and relevant Grant
  before the first Target write.
- Every owner is preflighted before mutation. If an ordinary write raises, the
  command restores already-written owners and removes checkpoints created by
  that failed attempt before returning the error.
- A completed multi-owner application is one Undo/Redo command unit even though
  each owner retains its own checkpoint receipt.
- Repeating the exact already-applied Update is idempotent: it reports that the
  plan was already applied, does not call the provider again, and does not add
  checkpoints or rewrite the session.
- A distinct invocation after an applied Update starts a new work unit without
  `--replace-stage`. The prior terminal receipt is migrated to immutable
  UID-addressed storage before the new staged record is published, and record
  compare-and-swap prevents concurrent work from being overwritten. A provider
  or validation failure before publication leaves the prior active receipt in
  place.
- Multi-Context exception atomicity is verified. Crash atomicity is not: the
  current prototype has no durable transaction journal spanning several
  Context files. Final approval would not repair that storage limitation, so it
  remains an explicit infrastructure follow-up rather than a decision-policy
  condition.

The Goal operand and its cross-operation role are defined in
[`goal-focus-operand-design-rationale.md`](goal-focus-operand-design-rationale.md).
This narrow focus binding does not implement the separately documented
multi-turn Update issue-resolution Ground.

## Task 1 replay evidence

On 2026-08-15, an isolated `init-study` store ran the actual command:

```text
mem update -r --from task-1/participant/construction-updates --to task-1/campus-wiki
```

The current exact prewarm wrapper reused the verified plan and printed that the
provider was not called. The granted Target application produced 74 changes:
32 edits, 42 additions, and 0 removals across 6 Target owners. `mem diff --stat`
reported the same totals. Repeating the exact command reported `already applied
locally`; `mem undo` reversed all 74 changes as one command and `mem redo`
restored all 74 as one command.

The automated verification set covers the policy value, Update planning and
application, removals, checkpoint history, granted application, the shared
Resolution shell, and exact Study prewarm installation/reuse.

The in-progress repository worktree passed all 252 tests in that focused set.
The assembled commit tree independently passed its 119 CLI-independent policy,
application, checkpoint, and Resolution-shell tests plus the complete PTY
capture. Collecting the CLI-dependent subset from the assembled tree is blocked
by a pre-existing `QualityFindSourceFrame` import mismatch in current `HEAD`;
that mismatch is repaired by unrelated in-progress worktree changes and is not
part of this Update application slice.

## Prewarm compatibility finding

The first isolated replay exposed a separate compatibility problem: the
checked-in Task 1 Update artifact used Update schema version 6, while the
current in-progress focused-Memory Update model requires version 7. Exact
artifact validation correctly rejected that wrapper before provider connection.
Rebuilding only the prewarm wrapper around the already verified 74-operation
session made the current replay succeed without inference.

This is not an application-policy failure and is intentionally not fixed in
this slice. Before the focused-Memory schema change is released for the study,
the canonical Update prewarm bundle must be rebuilt or given an explicit,
tested compatibility migration. Silently accepting an older schema would make
cache identity and frozen scope ambiguous.

## 2026-08-20 execution-receipt migration

Update's provider plan is internal prepared state. Required interactive
choices produce a decided staged session; local decision-free execution
advances automatically to Apply. Success prints only typed ADD/EDIT/REMOVE
counts, session/checkpoint identities, `mem review update --session UID`, and
recovery. Review accepts only APPLIED or historical UNDONE terminal evidence;
an incomplete staged Update resumes through `mem update`.
