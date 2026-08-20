# Exact Dedup application boundary

## Problem and command contract

`dedup` previously meant two different things: finding byte-identical stored
items and applying provider-confirmed semantic equivalence. That made the
obvious command fail for a Context containing two Memories with the same text:
`mem dedup` demanded an opaque finder handoff instead of removing the copy.

`mem dedup [CONTEXT]` and `MemCommitClient.dedup(context_name)` now have one
narrow, provider-free meaning. They examine
direct ordinary Memories, groups content by exact Python string equality,
retains the first UID in the Context's explicit item order, removes every later
UID in that group, and records the whole change in one checkpoint. With no
operand it uses the Context that was current when the command began. Existing
Context locator syntax is resolved through the shared locator boundary.

```text
direct Context
  -> byte-identical content groups
  -> first-in-Context survivor per group
  -> reference and freshness validation
  -> one atomic removal checkpoint
```

There is no semantic provider call, candidate screen, survivor picker,
finding receipt, or second `--apply` invocation. The command invocation is the
approval boundary, matching other immediately Undoable deterministic commands.
A no-op prints that no exact duplicates exist and creates no checkpoint.

## Invariants

- Equality is byte-for-byte stored content equality. Unicode, whitespace,
  punctuation, casing, and line endings are not normalized.
- Only directly owned `Memory` items participate. References, query views, and
  embedded Contexts are neither compared nor removed.
- The earliest direct item retains its exact content, UID, provenance, and
  position. Later byte-identical UIDs are removed.
- Every exact group in the frozen Context is applied together or nothing is
  published. A changed Context digest fails before mutation.
- An inbound `MemoryRef` to any would-be removed UID blocks the whole command.
  Retargeting a reference is not inferred merely because content is equal.
- Granted targets require `READ + DELETE` and are revalidated at the normal
  authorized mutation boundary.
- A successful mutation records contract `exact-dedup-v1`, exact survivor and
  absorbed UIDs, and remains recoverable with `mem undo`.

## Semantic redundancy is Dedun

Different wording that appears interchangeable is not an exact duplicate.
`mem dedun` owns provider-backed discovery, semantic evidence confirmation,
survivor review, and exact Apply. It excludes `EXACT` rows and accepts only
`SURFACE_EQUIVALENT` or `SEMANTIC_EQUIVALENT` evidence. Its review screen and
survivor decision remain distinct from exact Dedup. The old
`find-redundancies`, `find-duplicates`, and `consolidate` spellings are hidden
compatibility aliases; finder and handoff terminology is not part of ordinary
command Help.

## Alternatives and limits

- Automatically running semantic inference from `mem dedup` was rejected:
  model equivalence is evidence requiring a different review and authority
  boundary, while exact equality is complete and deterministic.
- Conservative normalization was rejected for exact Dedup because it would
  silently redefine stored content identity. Surface-equivalent wording stays
  in the semantic redundancy route.
- Automatically migrating inbound references was rejected for version 1. A
  reference names identity, not just current text, so migration needs its own
  reviewed contract.
- Cross-Context grouping is intentionally out of scope. Exact Dedup changes one
  direct Context per invocation.
