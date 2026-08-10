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
mem branch NEW --source-only
mem branch NEW --source-descendants
```

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

The target root and every mapped descendant must be new. Branch does not merge
into an existing target hierarchy, copy derived analysis/session artifacts, or
promise synchronization with later Source changes.
