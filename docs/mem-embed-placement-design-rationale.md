# Ordered Context Embed placement

## Status

Implemented for both public entry routes:

```text
mem embed
mem embed CHILD --into CONTEXT [--before ITEM | --after ITEM]
```

The flagless form is a local-only terminal setup. The explicit form remains the
non-interactive and scripting route.

The implementation now enters through `memcommit.embed_application`, with
`memcommit.embed_runtime` owning Store loading, concurrency checks, checkpoint
creation, and persistence. The plain command adapter is
`memcommit.interfaces.cli.embed`; the interactive adapter is the
`memcommit.interfaces.tui.operations.embed` package. The former
`memcommit.commands.embed` and `memcommit.commands.embed_dialog` modules were
removed instead of retained as compatibility facades.

The representative `180×52` color-PTY interaction against the actual current
Study Participant Profile is retained under
[`screenshots/mem-embed-placement-participant-20260813/`](screenshots/mem-embed-placement-participant-20260813/README.md).
It stages a real retained gap through exact-command review, cancels before
mutation, and proves byte equality for the complete Profile store. The
separate
[`screenshots/mem-embed-placement-20260813/`](screenshots/mem-embed-placement-20260813/README.md)
record uses a disposable store only for the success/apply receipt that would
otherwise contaminate participant research state.

## Motivation

A `Context` is already one ordered sequence of direct `Memory`, `MemoryRef`,
`QueryContextRef`, and embedded `Context` records. `Context.add()` has long
accepted an exact insertion position and the persisted `order` field retains
it. The former public Embed operation did not expose that capability:
`ops.embed()` always called `parent.add(child)` without a position, and
`mem embed CHILD --into CONTEXT` therefore always appended the live Context
reference.

Append-only Embed loses part of the direct sequence's meaning. If two adjacent
Memories establish a local reading order, a nested Context may belong between
them rather than after every other item. The missing control was in the public
operation and interaction boundary, not in the storage schema.

## CLI contract

The explicit command accepts at most one direct-item anchor:

```text
mem embed examples --into guide --before 7cc52c10
mem embed examples --into guide --after 191884c4
```

- `--before ITEM` inserts immediately before the direct item resolved by an
  exact UID, unambiguous UID prefix, or an exact embedded/query Context name.
- `--after ITEM` inserts immediately after that item.
- omitting both flags preserves the compatibility default: append at the end.
- passing both flags is a usage error and publishes no mutation.
- the anchor namespace is the target's complete direct-item sequence, not only
  directly owned Memories. Hidden exclusion of pointer slots would make the
  visible gap differ from the persisted position.

The command resolves `CHILD` and `--into` through the shared existing-Context
locator snapshot. `--before` and `--after` are direct-item selectors, not
Context locators, so relative Context syntax is never applied to them.

The checkpoint records the numeric position and both neighboring full UIDs.
The number explains the realized slot; the neighbors preserve the semantic gap
that was chosen. User-visible completion reports the same beginning, middle,
end, or only-item relationship.

## TUI contract

`mem embed` with no operands opens one top-to-bottom setup form:

1. `CHILD · EMBED THIS CONTEXT`
2. `INTO + POSITION · CHANGE THIS CONTEXT`
3. `TO DO · EXACT COMMAND`

The current local Context is the initial `INTO` choice because it is the only
Context mutated by Embed. The initial Child is the first distinct local
Context. At least two local Contexts are therefore required.

`INTO` is not followed by an unrelated operation-specific picker. Its frame
reuses the checked Context tree and the direct-item preview renderer used by
Switch. The selected target's persisted direct items are expanded immediately
beneath that Context row, so target and placement remain one selector rather
than two lists. A Context selection reloads only this read-only order preview
and resets placement to the explicit `LAST` choice.

The selector does not render `n + 1` repeated insertion commands. Entering its
Position layer adds exactly one separator line to the existing item sequence.
Up/Down moves that line through the `n + 1` legal gaps: `FIRST`, each middle
`POSITION`, and `LAST · DEFAULT`. The actual Memory, MemoryRef, query view, or
embedded Context rows remain fixed around it. An empty target has one
`FIRST = LAST · DEFAULT` line. The moving cursor and checked gap are
independent: Up/Down only inspects a gap; Enter or Space stages it. Tab
preserves the staged value. Append remains the initial selection so both the
TUI and an anchor-free CLI command have the same compatibility default.

Memory content uses the shared Memory-object color. Ordinary labels, Context
pointers, query views, and report prose remain neutral; a MemoryRef retains its
reference treatment. This is an ordering view, so it does not open embedded
Context content or query-only material.

The final frame shows one exact CLI command. A middle or initial gap is encoded
with the next full UID through `--before`; an ending gap is encoded with the
previous full UID through `--after`; the only gap in an empty Context needs no
anchor. The effect block states that only the Into Context changes, that the
Child retains identity and ownership, and which exact neighbor gap is used.

## Safety and concurrency invariants

- `ops.validate_embed()` checks self-embedding, duplicate Context/query names,
  and the exact numeric range before mutation. Embed does not rely on
  `Context.add()`'s generic clamping because a reviewed gap must not move.
- The TUI receipt freezes canonical Child and Into names, identities, record
  digests, both gap neighbors, and the complete exact-command review.
- Application reloads the Child and mutation-safe Into Context, then rejects
  identity, content, direct-order, neighbor, or exact-command drift before
  calling `ops.embed()`.
- The existing target digest compare-and-set and source binding remain the
  final locked persistence boundary. No partial Context order is published
  after a rejected or concurrent change.
- Escape and Backspace cancel from every read-only TUI surface. Cancellation
  does not create a checkpoint or alter the current Context.

## Reuse boundary

`memcommit.commands.direct_item_placement` currently owns the operation-neutral row
projection, gap model, separate hover/selection state, and single moving-line
renderer. It delegates item presentation to Switch's common direct-item
preview renderer. The common `ContextSelectorControl` exposes a narrow nested
row projection hook so Embed can compose that order under the selected Context
without cloning Context-tree navigation. Embed owns which object is inserted,
its exact command, authority, validation, checkpoint, and success receipt.
Later Add or Reference placement work may reuse the shared gap component
without inheriting Embed semantics.

This placement component predates the interface-package migration and still
depends on the older shared Context preview renderer. Moving that common visual
component is intentionally separate from the Embed use-case boundary: neither
the application contract nor the Store runtime imports it.

## Alternatives and intentional non-goals

- A raw `--position N` option was rejected as the primary CLI because an
  ordinal is hard to review and can silently describe another gap after an
  insertion. Stable adjacent item selectors match what the person sees.
- A separate Position picker and a list containing `INSERT EMBED HERE` in every
  gap were rejected because target choice and target order are one semantic
  decision. One moving line inside the shared selector preserves
  `CHILD → INTO → GAP`, keeps the surrounding Memories legible, and avoids
  repeating an operation label between every item.
- Side-by-side panels were rejected because the repository's shared terminal
  topology is vertical and must remain reconstructable at narrower widths.
- This operation does not reorder existing items, move a Child's own Memories,
  embed a lexical subtree, or infer a namespace relationship. It inserts one
  live Context pointer into one exact direct-item gap.
- Indirect Embed cycles remain governed by the existing graph behavior. This
  change adds placement, not a new cycle policy.
