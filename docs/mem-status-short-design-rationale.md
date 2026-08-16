# Status overview and short Context orientation

## Problem

The original `mem status` mixed two incompatible ideas. Its counts and recent
checkpoints were useful for orientation, but its `Recent memories` section
showed the last five persisted rows and therefore looked like a change report
without proving recency or modification. It also scattered Memory references,
query views, and embedded Contexts into operation-authored sections while
leaving attached Grants implicit. The command owned storage, authority, scope,
application policy, and terminal rendering in one module.

Git `status` reports worktree and index differences. Mem has no equivalent
staging boundary: its durable checkpoints report which operations were
recently applied, while `mem diff` owns exact before/after inspection and
`mem log` owns full history. Status therefore needs a compact overview rather
than a false Git-worktree analogy.

## Report contract

Detailed Status answers three bounded questions:

1. **Inventory:** how many ordinary Memories, Memory references, query views,
   embedded Contexts, attached Grants, and checkpoints are present.
2. **Preview:** what the current Context begins with, using at most the first
   five ordinary direct Memories in persisted order.
3. **Recent changes:** which five newest checkpoints were recorded, using
   their operation and content-free description.

The preview is explicitly labelled `first N of M`. It is stable orientation,
not a representative sample or a claim that those Memories changed recently.
Memory references, query views, embedded Contexts, and attached Grants remain
typed relationships and never enter the ordinary-Memory preview. A Memory
reference is not dereferenced merely to render Status.

Relationship rows appear only when present. An owned Profile-backed Context
may show Grants attached to it by public name, revision, and permissions. A
current READ-granted Context instead shows its exact access projection and
does not expose authority checkpoints. Query-only routes remain opaque.

The latest checkpoint rows summarize applied operations but do not claim to
show the exact changes. The checkpoint UID is retained as the handoff to
`mem diff` or `mem log`.

## Scope and compact forms

- `mem status` and `mem status -d` show the current exact Context.
- `mem status -r` adds aggregate and per-Context direct counts for readable
  lexical descendants and embedded Contexts. The Memory preview and detailed
  relationship rows remain anchored to the current Context, so recursive
  orientation cannot silently become a body dump.
- `mem status -s` emits one line per Context with canonical name, access, and
  direct counts.
- `mem status -sr` emits the compact row for every Context in the frozen
  recursive scope.
- `mem status -b` adds active Profile and `>`-separated Context namespace
  lineage. `-sb` retains the familiar `##` orientation shape without claiming
  that a Context is a Git branch.

Recursive Status freezes one readable public-name catalog under one Profile
and Grant-registry generation. Lexical descendants and explicit embed edges
remain independent axes. Context UID de-duplication prevents a Context reached
through both from being counted twice, and Grant attachment metadata never
becomes a hierarchy edge.

## Application boundary

`StatusRequest` carries lexical and embed reach independently.
`MemoryStoreStatusSource` freezes current orientation, authority, direct item
facts, attached Grants, and checkpoint summaries. `inspect_status` owns the
five-Memory and five-checkpoint limits and returns a typed `StatusResult`.
The CLI adapter parses flags and the CLI presenter renders that result; neither
reconstructs scope or authority policy.

Status is a deterministic, read-only operation. It has no provider, semantic
cache, saved analysis session, receipt, Apply, mutation checkpoint, Undo, or
current-pointer effect. Those are reviewed non-applicable boundaries rather
than unimplemented semantic lifecycle phases.
