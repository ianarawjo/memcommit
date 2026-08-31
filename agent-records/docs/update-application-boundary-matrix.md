# Update application boundary matrix

## Purpose

This note records the `APPLY-01` verification slice for Update. It separates
the shared report-Apply mechanics from Update's own application semantics so later
operation migrations do not copy an accidental Update-specific rule.

Update consumes one exact staged semantic plan. The mutation boundary follows
the owners of the Target Contexts that the plan will actually change, not the
presence of any Grant in the session and not the ownership of the Source.

## Operation ownership

`memcommit.application.operations.update.application` is the callable
application boundary for deterministic, non-persisting local Update. It
accepts an exact session-independent `UpdatePlan` and returns detached Target
owner post-images as an `UpdateResult`. A composing operation can therefore
apply Update to its own working Target without constructing a terminal
`UpdateSession`, opening an Update review, or publishing durable state.

`materialization.py` retains the exact preflight and detached-copy mechanics.
Its historical `prepare_update_application(UpdateSession, Context)` entry
remains a compatibility adapter for direct `mem update`, while new operation
composition enters through `application.apply_update`. The Store and the
local-, granted-Target-, and granted-Source publication paths retain freshness,
authority, multi-owner transaction, checkpoint, and durable receipt
responsibilities.

The remaining terminal-independent modules are named by responsibility:
`execution.py` sequences an exact decision to Apply, `granted_target.py` owns a Target
whose authority Store is mutated, and `granted_source.py` owns a granted
read-only Source feeding a local Target. These are mechanical renames only;
they do not add Memory Issue verification or change source/target authority.

This first composition boundary changes no semantic plan, preflight, CAS,
authority, checkpoint, review, or zero-operation behavior. It is intentionally
non-persisting so a Meld, Sever, Resolve, Forget, or Atomize session can own
the meaning and ordering of its local Update steps. Direct console review and
durable publication remain a separate adapter/application path.

### Memory Issue Analysis boundary review

Update has no dependency on the Compare operation. Its planning provider owns
a directional Source-to-Target change proposal and currently mentions
duplicates and conflicts only as constraints on that proposal. The persisted
session contains exact changes, not a complete ambiguity/redundancy/conflict
artifact, and the local decision-free route has no issue-resolution iteration.

The correct integration point for richer operations is the detached Target
post-image created by `materialization.prepare_update_application`. A composing
operation may analyze that complete post-image and iterate its own proposal,
but direct Update remains a local patch primitive: one provider-built proposal,
one report, and one Apply action. Escape cancels the interactive invocation; it
is navigation, not a persisted semantic decision. Update does not own questions,
responses, or proposal revision.

### Physical model ownership

The historical `memcommit.application.operations.update.model` import remains
the public compatibility facade, while its implementation follows five Update
concepts:

- `changes.py` owns source-linked ADD, EDIT, and REMOVE records, their strict
  parsing, operation digest, and required Target Context uses;
- `receipts.py` owns frozen Context fingerprints and checkpoint/application
  receipts;
- `inputs.py` owns inline Source identity, Source/Target candidates,
  focused-Memory selection, and exhaustive input collection. The operation-
  neutral frozen Grant binding lives under `application.context_access`;
- `plan.py` owns the session-independent exact Target and operation contract;
- `result.py` owns detached affected-owner post-images returned to composing
  application operations;
- `session.py` owns persisted direct-command serialization, lifecycle transitions,
  inline reconstruction, and stale/applied input matching;
- `planning.py` owns the provider contract, semantic budget, prompts, output
  schema, response validation, and the single initial plan.

The dependency direction is `planning -> session -> inputs -> receipts ->
changes`, with higher layers importing lower concept records directly where
needed. The split deliberately does not alter serialized schemas, provider
payloads, cache identity, application behavior, or the operation-owned
application boundary described above. Explicit facade exports preserve the
former 40-name public surface while making physical ownership testable.

## Context-use-constrained planning

Update authorizes Source `READ` and Target `READ` before provider connection.
The Target authorization also returns its complete ordinary-use set, from
which planning derives the available mutation vocabulary: `CREATE`, `UPDATE`,
and `DELETE`. The prompt and JSON schema expose only those effects. A forbidden
array has `maxItems: 0`, and decoding independently rejects any forbidden
effect, so a provider cannot substitute another mutation merely to bypass a
missing capability. A Target with no mutation use fails before provider
connection.

This ordering makes authorization an input to planning instead of a late
publication veto. Installed or cached plans are reused only when their exact
effects fit the current Target authorization; otherwise Update replans through
the constrained contract. Publication still reauthorizes the exact staged
effects under the Grant snapshot lock because provider latency and persisted
plans are not authorization leases. Local Contexts expose the complete use set,
so their existing provider contract and serialized session shape are unchanged.

`ContextUseAuthorization` deliberately carries both the resolved
`ContextAccess` and the complete allowed set. A separate permission-query API
would permit planning and validation to observe different Grant snapshots; one
authorization result keeps the successful check and the planning vocabulary
together. `READ` implies the weaker mediated `QUERY` use, while `QUERY` alone
does not disclose content and therefore cannot serve as an Update Source or
Target.

## Frozen behavior

| Case | Execution-decision behavior | Durable effect | Recovery |
| --- | --- | --- | --- |
| Direct interactive `mem update`, local Target, one or more operations | The report exposes one `APPLY` action; Esc cancels without a separate confirmation or revision turn | Apply changes all affected Target owners; cancellation leaves the staged proposal intact | Applied work has one operation-unit `mem undo` / `mem redo`; cancellation creates no checkpoint or receipt |
| Direct interactive `mem update`, granted Source and local Target | Same single Apply action; the Source remains read-only | Local Target owners on Apply; cancellation leaves the staged proposal intact | Applied work has one operation-unit `mem undo` / `mem redo` |
| Granted Target, one or more operations | The same exact Apply action remains mandatory in a TTY | Authority Target owners only after Apply; cancellation creates no authority mutation | Authority-aware command history after Apply |
| Meld, Sever, Resolve, Forget, or Atomize application composition | No Update-owned terminal review; the enclosing operation already owns semantic review | Detached working Target only until the enclosing operation publishes | Enclosing operation owns cancellation, final checkpoint, and receipt |
| Any Target, zero operations | The same explicit `APPLY` action keeps direct Update's contract uniform; Esc still cancels | Apply creates a terminal completion receipt only | No Context checkpoint and no Context Undo unit |
| Escape or terminal close without Apply | Session remains staged | No Target owner changes, checkpoint, or terminal receipt | Reopen the staged session through Update |
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
  session uses compare-and-swap when it is marked applied. Goal is
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
choices produce a decided staged session. Success prints only typed
ADD/EDIT/REMOVE counts, session/checkpoint identities,
`mem review update --session UID`, and recovery. Review accepts only APPLIED or
historical UNDONE terminal evidence; an incomplete staged Update resumes
through `mem update`.

## 2026-08-30 direct report Apply and composed application

Direct interactive `mem update` owns one report-first pre-Apply boundary
because it has no enclosing semantic session. The Report and its single
`APPLY` action are one screen. Esc cancels the invocation while leaving the
proposal staged and creates no checkpoint or terminal receipt. Cancellation is
therefore a control-flow exit rather than a second semantic outcome. A future
permanent rejection would need a separately named `DISCARD` contract instead
of overloading cancellation. The former `--comment` / `--expect-session`
revision turn and the separate Apply-confirmation screen were removed. This is
intentional: iteration belongs to Meld, Atomize, Resolve, or another composing
operation that owns the larger semantic session, while Update remains an exact
local patch application. Non-interactive compatibility routes cannot open a
terminal and continue to apply the exact staged request supplied by their
caller.

This console policy does not enter `application.apply_update`. Meld, Sever,
Resolve, Forget, and Atomize call that application boundary against their own
working Target after their operation-specific review. They receive a typed
result but no Update screen, console text, checkpoint, or hidden durable write.
