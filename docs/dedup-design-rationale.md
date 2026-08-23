# Exact Dedup application boundary

## Problem and command contract

`dedup` previously meant two different things: finding byte-identical stored
items and applying provider-confirmed semantic equivalence. That made the
obvious command fail for a Context containing two Memories with the same text:
`mem dedup` demanded an opaque finder handoff instead of removing the copy.

`mem dedup [CONTEXT]` and `MemCommitClient.dedup(context_name)` have one
provider-free meaning. Direct reach examines one Context; recursive reach
freezes the selected local lexical subtree and examines every member as an
independent direct frame. In either shape, Dedup uses a role-specific exact
identity key, retains the first occurrence UID in each Context's explicit item
order, and removes every later occurrence in that Context-local group. With no
operand the command uses the Context that was current when the command began.
Existing Context locator syntax is resolved through the shared locator
boundary.

```text
direct Context or frozen local lexical subtree
  -> independent direct frame per Context
  -> same-role exact identity groups
  -> first-in-Context survivor per group
  -> complete graph reference and freshness validation
  -> one atomic command unit, with one checkpoint per changed Context
```

There is no semantic provider call, candidate screen, survivor picker,
finding receipt, or second `--apply` invocation. The command invocation is the
approval boundary, matching other immediately Undoable deterministic commands.
A no-op prints that no exact duplicates exist and creates no checkpoint.
Recursive publication is exception-atomic and binds all changed checkpoints
with one operation UID, so `mem undo` restores the command as one unit.

## Invariants

- Equality begins with role. A directly owned Memory, live Embed, and immutable
  Reference never share a DUP edge merely because their visible content is
  equal.
- Memory equality is byte-for-byte stored content equality. Unicode,
  whitespace, punctuation, casing, and line endings are not normalized.
- Live Memory Embed equality requires the same Source Context UID/name and
  Source Memory UID. Memory Reference equality additionally requires snapshot
  mode, the same retained content, and the same snapshot digest.
- Context Reference equality requires the same Source identity, complete
  snapshot package, scope, and digest. Context Embed equality includes its
  complete local or Grant binding; the current direct-item map already
  prevents two occurrences with the same target UID from coexisting.
- Query-only views remain outside ordinary Embed/Reference cleanup because
  their authorization and execution contract is distinct.
- The earliest direct occurrence retains its exact role, UID, provenance, and
  position. Later same-role exact occurrences are removed.
- Every exact group in the frozen direct or lexical scope is applied together
  or nothing is published. A changed Context digest or subtree membership
  fails before mutation.
- An inbound `MemoryRef` to any would-be removed owned Memory UID blocks the
  whole command. Retargeting a reference is not inferred merely because
  content is equal.
- Granted targets require `READ + DELETE` and are revalidated at the normal
  authorized mutation boundary.
- A successful mutation records contract `exact-dedup-v2`, item role, exact
  survivor and absorbed UIDs, and remains recoverable with `mem undo`.

## Semantic redundancy finder and Dedun

Differently stored wording is not an exact duplicate. `mem find-duplicates`
owns the provider-free, read-only exact-DUP report. `mem find-redundancies`
owns the complete exact-plus-semantic DUN report, and `mem dedun` reuses that
analysis before applying the earliest-existing-UID survivor rule to all
role-aware exact groups and eligible Memory `EXACT`, `SURFACE_EQUIVALENT`, and
`SEMANTIC_EQUIVALENT` evidence. There is no separate singular operation:
`find-redundancy` resolves to the canonical `find-redundancies` operation.
Hidden `consolidate` remains only the exact Dedun review replay route.

## Alternatives and limits

- Comparing items across roles was rejected: ownership, live update, retention,
  and authority behavior are part of identity rather than incidental metadata.
- Automatically running semantic inference from `mem dedup` was rejected:
  model equivalence is evidence requiring a different review and authority
  boundary, while exact equality is complete and deterministic.
- Conservative normalization was rejected for exact Dedup because it would
  silently redefine stored content identity. Surface-equivalent wording stays
  in the semantic redundancy route.
- Automatically migrating inbound references was rejected for version 1. A
  reference names identity, not just current text, so migration needs its own
  reviewed contract.
- Cross-Context grouping is intentionally out of scope. Recursive Dedup may
  change several Context records in one invocation, but the direct items in
  each Context form a separate identity frame; matching content in a parent
  and child never creates one group.
- Recursive Apply never follows Embed or Reference edges and never crosses a
  granted public namespace boundary. Read-only Find Duplicates may report
  readable granted lexical descendants, while mutating them requires separate
  exact invocations because one command cannot claim atomicity across authority
  stores.
