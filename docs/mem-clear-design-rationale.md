# Immediate Context clear design rationale

Clear's request/result contract and all authority, subtree-freeze, checkpoint,
and durable mutation behavior are owned by `memcommit.operations.clear`.
`memcommit.commands.clear` now retains only argument syntax, one current-name
snapshot, and terminal presentation. The focused boundary and preserved
compatibility are recorded in `clear-application-boundary-matrix.md`.

## Problem

`mem clear` used to print the number of direct items in one Context and require
a second `y` confirmation before removing them. That extra approval duplicated
the safety boundary already provided by command history: a successful clear is
saved as one `clear` checkpoint and can be restored with `mem undo`, then
reapplied with `mem redo`.

The exact-only command also left no direct way to empty a lexical Context
subtree. A person could list one with `mem ls -r`, but `mem clear ROOT -r`
failed during option parsing. Repeating exact clear commands manually would
publish several independently ordered commands, permit a failure after an
earlier Context had changed, and require several Undo turns. That does not
preserve the meaning of one entered recursive command.

The prompt also made the operation look equivalent to permanent deletion.
Those effects have different recovery properties. Context clear retains the
Context and its checkpoint history, while Context deletion and Profile or
Study removal destroy recovery state and therefore retain their existing
review or confirmation boundaries.

## Command contract

- `mem clear` resolves the current Context once, and `mem clear LOCATOR`
  resolves one explicit existing Context through the shared locator rules.
- A nonempty exact Context is cleared immediately after target and DELETE
  authority validation. The command invocation is the complete approval.
- `mem clear LOCATOR -r`, `-R`, or `--recursive` freezes the canonical local
  root and every materialized lexical descendant from one command-start
  catalog. It clears their direct items immediately without another prompt.
- Recursive clear never follows embedded Context edges. If the public subtree
  would cross a granted Context boundary, it fails before mutation instead of
  silently omitting or partially applying another authority store.
- Every changed Context is preflighted and saved through one exception-atomic
  batch. Its checkpoint carries the same operation identity and complete
  changed-Context membership, so command history reconstructs the batch as one
  `mem clear ROOT --recursive` unit for one-turn Undo and Redo.
- Already-empty subtree members remain locked and digest-checked through the
  batch but receive no no-change checkpoint. If the complete subtree is empty,
  the command remains a non-mutating no-op.
- Success saves one `AutoCheckpoint` with command `clear`, the canonical
  Context name, the removed direct-item count, and any exact Grant checkpoint
  facts. Recursive checkpoints additionally retain their root, operation
  identity, and command membership.
- An already-empty Context remains a non-mutating no-op with its existing
  receipt.
- The former `-f`/`--force` option remains accepted as a hidden no-op so old
  scripts do not fail merely because the prompt was removed. New Help and
  reconstructed command receipts omit it.

## Safety boundary

Exact clear remains limited to the direct items of one Context. Recursive clear
changes the direct items of its frozen local lexical subtree, but neither form
deletes a Context, checkpoint history, or the containing Profile. Recursive
scope is name-based: embedded Contexts outside the root namespace are not
targets. Existing authority checks, write protection, canonical targeting,
and mutation error handling still run before publication.

This rationale does not relax permanent deletion. `mem delete CONTEXT` still
reviews deletion of that Context and its checkpoint history. `mem profile
remove PROFILE` and `mem profile remove-study STUDY` still show the affected
store scope and require confirmation because mem cannot restore their deleted
Memories, sessions, or checkpoints.

## Alternatives and limitations

Keeping the confirmation but recommending `--force` was rejected because it
would preserve two public interaction paths for an operation whose recovery
contract is already uniform. Recursive breadth does not reintroduce a prompt:
the entered `--recursive` flag is explicit intent, and the resulting batch has
the same one-command recovery contract. Removing `--force` outright was also
rejected for now because existing automation uses it; hiding and accepting it
preserves compatibility without teaching obsolete syntax.

Calling exact clear once per descendant was rejected because it would expose
partial success and several command-history units. Following embeds was also
rejected: an embed is a stored graph edge, not lexical ownership, and may cross
namespace or authority boundaries. Granted recursive mutation remains an
intentional limitation until a cross-authority command can publish and restore
one complete command unit.

Undo is not a substitute for external backup. It succeeds only while the
recorded command remains the applicable history unit and the Context has not
drifted beyond the history revalidation rules. Multi-Context publication has
exception atomicity and rollback but no durable crash journal, so a machine
failure may still interrupt several file replacements. Those limitations do
not make a second prompt useful for ordinary clear, but operations that destroy
their own recovery history retain a stronger review boundary.
