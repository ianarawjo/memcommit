# Ordered live Embed placement

## Status

Implemented for both public entry routes:

```text
mem embed
mem embed CHILD [--into CONTEXT | --to CONTEXT] [--before ITEM | --after ITEM]
mem embed --from CHILD [--into CONTEXT | --to CONTEXT] [--before ITEM | --after ITEM]
mem embed MEMORY [--into CONTEXT | --to CONTEXT] [--before ITEM | --after ITEM]
mem embed SOURCE:MEMORY [--into CONTEXT | --to CONTEXT] [--before ITEM | --after ITEM]
```

The flagless form first selects Context or Memory link type. Context mode
presents owned local Contexts plus visible Grant rows as possible Children;
Memory mode presents directly owned ordinary Memories from local Contexts.
Only local owned Contexts can be targets. The explicit forms remain the
non-interactive and scripting routes. `SOURCE:MEMORY` names an exact owner;
a bare public UID/prefix searches every ordinary local direct Context and must
be unique. An omitted ITEM makes `--from SOURCE` a complete Context Source;
existing `MEMORY --from SOURCE` scripts retain their owner-qualified Memory
meaning. Omitting
`--into` uses the command-start current Context; an explicit `--into` overrides
it. `--to` is accepted as a compatibility alias for `--into`, while generated
commands and receipts keep `--into` as the canonical spelling.

The implementation now enters through
`memcommit.operations.embed.application`, with
`memcommit.operations.embed.runtime` owning Store loading, concurrency checks,
checkpoint creation, and persistence. The previous flat module paths are
module-identity compatibility aliases. The plain command adapter is
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
reference. Memory Embed now applies the same ordered-gap contract to the
legacy live `memory_ref` relationship.

Append-only Embed loses part of the direct sequence's meaning. If two adjacent
Memories establish a local reading order, a nested Context may belong between
them rather than after every other item. The missing control was in the public
operation and interaction boundary, not in the storage schema.

## CLI contract

The explicit command accepts at most one direct-item anchor:

```text
mem embed examples --into guide --before 7cc52c10
mem embed examples --into guide --after 191884c4
mem embed examples:a94c120e --into guide --before 7cc52c10
```

`--into TARGET` and `--to TARGET` select the same target role, but a command
must use only one spelling. Even identical values supplied through both flags
are rejected before any Context is loaded or changed. Treating them as one
ordinary Click alias would silently let the last occurrence win, which is an
unsafe ambiguity for a mutating command.

- `--before ITEM` inserts immediately before the direct item resolved by an
  exact UID, unambiguous UID prefix, or an exact embedded/query Context name.
- `--after ITEM` inserts immediately after that item.
- omitting both flags preserves the compatibility default: append at the end.
- passing both flags is a usage error and publishes no mutation.
- the anchor namespace is the target's complete direct-item sequence, not only
  directly owned Memories. Hidden exclusion of pointer slots would make the
  visible gap differ from the persisted position.

The command resolves `CHILD`, a qualified Memory owner, `--from`, and
`--into`/`--to` from one command-start current-Context snapshot. With no ITEM,
`--from` names CHILD; with a Memory ITEM it names that Memory's direct owner. A bare
Memory UID instead searches one strict snapshot of every ordinary local direct
frame and succeeds only when exactly one ordinary Memory matches; the current
Context has no priority. Multiple matches list canonical `CONTEXT:FULL_UID`
candidates and publish nothing. When `--into` is absent, the adapter copies the
snapshot's canonical current Context into the typed request before planning; if
there is no current Context, it fails before loading the Source.
`--before` and `--after` are direct-item
selectors, not Context locators, so relative Context syntax is never applied
to them. Memory Embed requires a directly owned ordinary Source Memory and a
Source Context distinct from the Target; this prevents a recursive live link
back into the record currently being loaded.

The checkpoint records the numeric position and both neighboring full UIDs.
The number explains the realized slot; the neighbors preserve the semantic gap
that was chosen. User-visible completion reports the same beginning, middle,
end, or only-item relationship.

## TUI contract

`mem embed` with no operands opens one top-to-bottom setup form:

1. `LINK TYPE · CONTEXT | MEMORY`
2. conditional `CHILD · EMBED THIS CONTEXT` or
   `SOURCE MEMORY · DIRECTLY OWNED`
3. `INTO + POSITION · CHANGE THIS CONTEXT`
4. compact `COMMAND · RUNNABLE` or `COMMAND · INVALID`

The current local Context is the initial `INTO` choice because it is the only
Context mutated by Embed. Context mode initially selects the first authorized
Child distinct from that target. Memory mode composes the shared Context tree,
lazy direct-item previews, and retained direct-Memory selection; read-only
references, query views, and embedded Context rows remain visible but cannot
be selected as a directly owned Source Memory. It initially opens the current
Target as the Memory Source, matching Reference, so those direct Memories are
immediately inspectable and selectable. Source and Target may remain equal in
the process-local picker and editable command; the exact action rejects that
self-link before returning a frozen plan or publishing durable state.

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
with the next UID prefix through `--before`; an ending gap is encoded with the
previous UID prefix through `--after`; the only gap in an empty Context needs
no anchor. Prefixes start at seven characters and expand only if the frozen
direct-item catalog contains a collision. The adjacent typed review still
records that only the Into Context changes, that the Child Context or Source
Memory retains identity and ownership, and which exact neighbor gap is used;
the compact box does not repeat that prose.

The proposed command is always a one-line input below the setup controls. Its
small frame is blue and titled `COMMAND · RUNNABLE` when valid, or red and
titled `COMMAND · INVALID` with one short reason when invalid. It has no
underline, fill, effects block, usage, flag list, or explanatory heading.
Every complete valid buffer change updates Link Type, Source/Child, Into, and
Position together before Enter; incomplete or invalid text changes no checked
value. Retained changes in those upper controls immediately rebuild the
command below. A single Enter on a runnable synchronized field freezes the
plan. Escape cancels, and Backspace remains ordinary text deletion.

## Safety and concurrency invariants

- Context Embed checks self-embedding, duplicate Context/query names, and the
  exact numeric range before mutation. Memory Embed additionally rejects a
  Source/Target self-link and duplicate logical live link. Neither relies on
  generic insertion clamping because a reviewed gap must not move.
- The TUI receipt freezes canonical Source and Into names, identities, record
  digests, both gap neighbors, and the complete exact-command review. Memory
  mode also freezes the direct Source Memory UID, content, and digest.
- Application reloads the Source and mutation-safe Into Context, then rejects
  identity, content, direct-order, neighbor, or exact-command drift before
  calling the operation-owned mutation.
- The existing target digest compare-and-set and source binding remain the
  final locked persistence boundary. No partial Context order is published
  after a rejected or concurrent change.
- A granted Child additionally requires explicit `EMBED` authority. The
  registry Grant lock and exact authority-source lock remain held through the
  local target compare-and-set, closing revoke-after-review and
  change-after-review races.
- Escape and Backspace cancel from every read-only TUI surface. Cancellation
  does not create a checkpoint or alter the current Context.

## Reuse boundary

`memcommit.interfaces.tui.components.direct_item_placement` owns the
operation-neutral row projection, gap model, separate hover/selection state,
and single moving-line renderer. The neighboring exact-command receipt is a
separate component whose form/draft/editor mechanics are shared under
`interfaces.tui.components.exact_command_review`; Embed owns the argv grammar
and its all-or-none mapping back to controls. The common
`ContextSelectorControl` exposes a narrow
nested-row projection hook so Embed can compose the order under the selected
Context without cloning Context-tree navigation. Embed owns which object is
inserted, its exact command, authority, validation, checkpoint, and success
receipt. Later Add or Reference placement work may reuse the shared gap
component without inheriting Embed semantics.

The component projects only the target's frozen direct-item sequence. It does
not import a command adapter or gain storage, authority, or apply behavior.
The former `memcommit.commands.direct_item_placement` implementation is now a
module-identity compatibility alias to this owner. The relocation deliberately
retains the old import path while removing the second implementation and its
independent globals. Older command screens may still have separate review
helpers: migrating a frozen-plan review requires an operation-owned replan
contract, and Embed does not reach through those screens or reinterpret their
approval boundary.

## Alternatives and intentional non-goals

- A raw `--position N` option was rejected as the primary CLI because an
  ordinal is hard to review and can silently describe another gap after an
  insertion. Stable adjacent item selectors match what the person sees.
- A separate Position picker and a list containing `INSERT EMBED HERE` in every
  gap were rejected because target choice and target order are one semantic
  decision. One moving line inside the shared selector preserves
  `SOURCE → INTO → GAP`, keeps the surrounding Memories legible, and avoids
  repeating an operation label between every item.
- Side-by-side panels were rejected because the repository's shared terminal
  topology is vertical and must remain reconstructable at narrower widths.
- This operation does not reorder existing items, move a Child's own Memories,
  embed a lexical subtree, or infer a namespace relationship. It inserts one
  live Context or Memory pointer into one exact direct-item gap.
- Grant-backed Embed does not copy or cache authority content. It persists a
  typed revocable link and reauthorizes it whenever traversal opens the Child.
- Indirect Embed cycles remain governed by the existing graph behavior. This
  change adds placement, not a new cycle policy.
