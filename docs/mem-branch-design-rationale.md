# Mem Branch design rationale

## Motivation

Task 1 study runs exposed two valid Branch expectations. Branching one Context
can intentionally retain its embedded children as live references, while
branching a hierarchy is expected to create an independently editable copy of
that hierarchy. The old command implemented only the first, shallow meaning.
Branching a Root with no direct Memories therefore appeared successful but
left every meaningful descendant attached to the Source hierarchy.

Branch now makes the Source range explicit:

```text
THIS CONTEXT ONLY
INCLUDE DESCENDANTS
```

The equivalent explicit spelling defaults to compatibility behavior:

```bash
mem branch NEW --source-root-only
mem branch NEW --source-descendants
```

`--source-only` remains accepted as a compatibility alias for the canonical
`--source-root-only` spelling.

## Exact Branch compatibility

`THIS CONTEXT ONLY` retains the existing contract. It creates one new Context
identity, copies direct Memories as independent objects with stable Memory
UIDs, retains Memory and query references, and carries embedded Contexts as
live references. Only the selected Source history is inherited. Existing
scripts and `mem checkout -b NEW` therefore remain shallow unless descendant
scope is requested explicitly.

## Lexical-subtree Branch

`INCLUDE DESCENDANTS` freezes the selected local Source root and every
materialized lexical descendant. It does not follow an arbitrary embedded
Context outside that namespace. Every Source name maps by suffix:

```text
source              -> experiment
source/facilities   -> experiment/facilities
source/routes/live  -> experiment/routes/live
```

Each target Context receives a new Context UID because the hierarchy must be
independently editable. Direct Memory UIDs remain stable so Merge and Meld can
recognize common lineage. An embedded Context or MemoryRef targeting a member
of the frozen Source set is rewritten to the corresponding target name and
new Context UID. Pointers outside the selected set retain ordinary shallow
Branch live-reference semantics. Query-only Context pointers are never treated
as lexical hierarchy edges.

The same internal-pointer rewrite applies to inherited checkpoint snapshots,
their `command_before` frames, and nested checkpoint-log snapshots. Otherwise
a later Revert could silently reconnect a branched Root to an original Source
child even though the current Context records were independent.

## Undo and Redo lifecycle

Branch creation is one recoverable command, not merely a copy followed by a
current-Context switch. Immediately after either an exact or subtree Branch,
`mem undo` cancels every Context created by that Branch as one unit and leaves
the Source unchanged. `mem redo` restores the exact archived target records,
Context UIDs, inherited checkpoint histories, and internal subtree mappings.
It must not call Branch again against a Source that may have changed since the
original command, because that would create new identities and a different
result under the same history action.

Every target receives one direct automatic Branch checkpoint after its Source
history is copied. The shared version-1 `branch_tree` receipt freezes:

- one operation UID and the complete Source-to-target Context membership;
- the Source and target roots plus exact-versus-descendant scope;
- every Source and target Context UID and canonical name; and
- the current Context value observed before Branch selected its target root.

Inherited checkpoints are lineage, not evidence that the target existed
before Branch. Command-history reconstruction may assign an absent target
pre-image only to an owned automatic Branch checkpoint whose complete receipt
validates. Every target checkpoint shares the same command membership, so a
partial recursive Undo or Redo is rejected rather than exposed as separate
Context actions. The additional direct Branch checkpoint intentionally raises
the target's physical checkpoint count by one and makes the creation boundary
visible ahead of its inherited history in Log and Status.

Undo freshness-checks every target against the recorded creation post-image
and validates deletion protection before moving any target. It then moves the
exact Context records and checkpoint directories into private command-history
archives and records one shared Undo receipt. Redo requires every destination
name to remain available, moves those same records and histories back, and
records one shared Redo receipt. A newly created Context with the same name is
never overwritten or adopted.

Branch initially selects its target root. Undo restores the frozen prior
selection only while the current pointer still names one of the Branch targets;
if the person has since switched elsewhere, that unrelated selection is
preserved. Redo similarly selects the target root only when the current pointer
still equals the frozen pre-Branch value. The private archive and restoration
checkpoints are recovery metadata, not newly visible replacement Contexts.

Checkpoint-producing work performed after Branch remains newer in the global
command stack and must be undone first. The lifecycle archive covers the
created Context records and their checkpoint histories; it does not claim
arbitrary read-only caches created later as part of the Branch command.

## Transaction boundary

One subtree Branch is one store command. Before publication it rechecks:

- the complete lexical Source membership;
- every Source Context UID and record digest;
- every Source checkpoint-history digest;
- every require-new target path; and
- the command-start current Context.

The store holds the graph lock, all Source and target Context locks, and the
current-state lock through creation, history publication, selection, and
exception rollback. A new or removed descendant makes the reviewed Source
range stale. A collision at any mapped target fails before the first write.
An exception after publication begins removes every Context created by that
Branch while retaining pre-existing namespace descendants.

Undo and Redo hold the command lock, an exclusive Context-graph lock, and all
target Context locks across validation and archive movement. Every record and
checkpoint-directory pair moves together; a failure restores all previously
moved pairs, removes provisional restoration checkpoints, and preserves the
pre-operation current pointer. Recursive recovery therefore has the same
all-target exception boundary as recursive creation.

This prototype guarantees cooperative-process and exception atomicity. Like
the existing multi-Context update and rename paths, it does not yet provide a
durable crash-recovery journal for a host failure between filesystem writes.

## Rejected alternatives and limits

- Making every Branch recursive was rejected because it would change the
  established meaning of scripts that intentionally branch one record while
  keeping live embedded Contexts.
- Following embedded edges recursively was rejected because lexical placement
  and embedded graph traversal are independent axes. It could pull unrelated
  Contexts into the result and make a bounded Source range difficult to review.
- Preserving Context UIDs was rejected because two independently editable
  ordinary Contexts must not claim one Context identity. Stable Memory UIDs
  provide the needed Merge/Meld lineage instead.
- Copying checkpoint bytes unchanged was rejected for subtree mode because
  future Revert would restore Source-side internal pointers.
- Re-running Branch during Redo was rejected because it would allocate new
  Context UIDs and copy the Source's current state instead of restoring the
  reviewed historical result.
- Treating copied Source checkpoints as the target's pre-Branch history was
  rejected because it would make Undo edit inherited lineage or consume an
  older Source command instead of cancelling target creation.

The target root and every mapped descendant must be new. Branch does not merge
into an existing target hierarchy, copy derived analysis/session artifacts, or
promise synchronization with later Source changes.
