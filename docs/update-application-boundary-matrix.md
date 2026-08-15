# Update application boundary matrix

## Purpose

This note records the `APPLY-01` verification slice for Update. It separates
the shared review policy from Update's own application semantics so later
operation migrations do not copy an accidental Update-specific rule.

Update consumes one exact staged semantic plan. The mutation boundary follows
the owners of the Target Contexts that the plan will actually change, not the
presence of any Grant in the session and not the ownership of the Source.

## Frozen behavior

| Case | Review behavior | Durable effect | Recovery |
| --- | --- | --- | --- |
| Local Target, one or more operations | Decision-free proposal returns the exact Accept action without opening review | All affected Target owners and the applied session receipt | One operation-unit `mem undo` / `mem redo` |
| Granted Source, local Target | Same as a local Source because the Source remains read-only | Local Target owners and the applied session receipt | One operation-unit `mem undo` / `mem redo` |
| Granted Target, one or more operations | Exact final review remains mandatory in a TTY | Authority Target owners only after approval, plus the local applied receipt | Authority-aware command history; review is retained even when recovery exists |
| Any Target, zero operations | No final review because no Context mutation exists | Applied session receipt only | No Context checkpoint and no Context Undo unit |
| Unanswered required item or pending response | No automatic Accept | None until the item is resolved or the response is incorporated | Not applicable |
| Closed or cancelled authority review | Session remains staged | No Target owner changes | Reopen the staged session |
| Stale Source, Target, Grant, or session revision | Fail before publication | No partial success receipt | Re-run or reopen against current state |

The zero-operation row is deliberately different from Merge. Merge can record
a command-level no-op checkpoint as an explicit graph reconciliation effect.
Update's existing application contract treats an empty operation tuple as a
validated completion receipt and writes no Context at all. The shared policy
therefore classifies it as mutation boundary `NONE`; it does not invent an Undo
checkpoint solely to make operations look alike.

## Integrity and failure boundaries

- Update freezes Source and Target identity, scope, Memory digests, operations,
  and session revision before Apply. The stored session uses compare-and-swap
  when it is revised or marked applied.
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
- Multi-Context exception atomicity is verified. Crash atomicity is not: the
  current prototype has no durable transaction journal spanning several
  Context files. Final approval would not repair that storage limitation, so it
  remains an explicit infrastructure follow-up rather than a review-policy
  condition.

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
