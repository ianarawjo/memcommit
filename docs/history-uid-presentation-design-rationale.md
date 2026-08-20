# History UID presentation design rationale

## Problem

Context history previously placed several unlabelled eight-character values in
the same visual sentence. The leading value was a Checkpoint UID, a value in a
Memory description could be a Memory UID, and Undo or Redo descriptions placed
a restoration receipt UID in the same bracket grammar. A branched Context also
copied its Source history without recording a new Branch checkpoint, so the
location browser counted copied Source commands as if they had been executed
directly against the branch.

The motivating example was `practice/2`, branched from `practice/1`, with an
inherited Add followed by direct Embed, Edit, Remove, Undo, Redo, and Undo
commands. The browser reported seven direct operations and exposed bare UID
prefixes whose namespaces could not be distinguished from the row alone.

## Presentation contract

Every compact history row names the role of each visible identifier:

- `CHECKPOINT` is one persisted Context version and is the selector accepted by
  Revert.
- `MEMORY`, `AFTER MEMORY`, and `BEFORE MEMORY` identify durable Memory objects
  or placement anchors.
- `CONTEXT` identifies the Context object in the creation baseline.
- `RECEIPT` identifies one Undo or Redo restoration action.
- `SOURCE <command>` identifies the original command unit restored by Undo or
  Redo.
- `COMMAND` is reserved for a shared multi-Context command-unit identity, such
  as Update, Meld, Merge, or Replace. It is omitted for ordinary single-
  checkpoint commands and restoration receipts because their more precise
  labels are already visible.

Compact rows show eight-character prefixes for scanning. Focusing a row opens
a read-only `SELECTED COMMAND` detail region with the exact persisted values.
The full Checkpoint UID remains the nested selection receipt; display labels
never become selectors.

Interactive Diff and Revert use the lifecycle label `created`, expose the
focus detail, and pass the exact Checkpoint UID through the nested selection
receipt. Static log compatibility remains outside this presentation change.

## Direct, inherited, and descendant history

The location annotation is
`N direct · M inherited · K descendant commands`.

A checkpoint is direct when its persisted snapshot owner name and UID match the
currently loaded Context. A checkpoint whose snapshot belongs to another
Context is inherited lineage and appears under
`INHERITED HISTORY · source <name>`. Branch deliberately preserves Source
checkpoint and Memory identities, so this comparison retains provenance while
the branch's independently editable Context receives a new UID. Direct rows
always appear before inherited rows. `init` is a creation baseline, remains
visible, and is not counted as a command.

Descendant counts continue to mean commands directly owned by lexical child
Contexts. Inherited commands are not added to either the current Context's
direct count or an ancestor's descendant count. Grant attachment metadata is
not a hierarchy edge.

## Shared command identity

History display and the command restoration stack use
`command_history.command_unit_uid` as the sole command-unit projection. This is
necessary for multi-Context Update, Meld, Merge, and Replace checkpoints: the
same command may produce one physical checkpoint per affected Context but must
count as one command unit. Undo and Redo instead deduplicate on their shared
restoration receipt.

## Boundaries and limitations

Legacy checkpoints without a valid snapshot owner header remain classified as
direct because there is no retained evidence that can safely name an inherited
Source. Exact and subtree Branch histories retain historical snapshot owners,
so current Branch output can be classified without adding a second provenance
registry. Branch creation itself still has no checkpoint row; this change
clarifies copied lineage but does not invent an unrecorded Branch event.

The selected detail region is passive and read-only. It does not change the
current Context, load referenced content, mutate history, or weaken Revert's
existing UID, digest, and approval checks.
