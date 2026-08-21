# Immediate Context clear design rationale

## Problem

`mem clear` used to print the number of direct items in one Context and require
a second `y` confirmation before removing them. That extra approval duplicated
the safety boundary already provided by command history: a successful clear is
saved as one `clear` checkpoint and can be restored with `mem undo`, then
reapplied with `mem redo`.

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
- Success saves one `AutoCheckpoint` with command `clear`, the canonical
  Context name, the removed direct-item count, and any Grant checkpoint facts.
  Undo and Redo therefore restore or reapply the complete clear as one command
  unit.
- An already-empty Context remains a non-mutating no-op with its existing
  receipt.
- The former `-f`/`--force` option remains accepted as a hidden no-op so old
  scripts do not fail merely because the prompt was removed. New Help and
  reconstructed command receipts omit it.

## Safety boundary

Immediate clear is limited to the direct items of one exact Context. It does
not delete the Context, descendants, checkpoint history, or the containing
Profile. Existing authority checks, write protection, canonical targeting,
and mutation error handling still run before publication.

This rationale does not relax permanent deletion. `mem delete CONTEXT` still
reviews deletion of that Context and its checkpoint history. `mem profile
remove PROFILE` and `mem profile remove-study STUDY` still show the affected
store scope and require confirmation because mem cannot restore their deleted
Memories, sessions, or checkpoints.

## Alternatives and limitations

Keeping the confirmation but recommending `--force` was rejected because it
would preserve two public interaction paths for an operation whose recovery
contract is already uniform. Removing `--force` outright was also rejected for
now because existing automation uses it; hiding and accepting it preserves
compatibility without teaching obsolete syntax.

Undo is not a substitute for external backup. It succeeds only while the
recorded command remains the applicable history unit and the Context has not
drifted beyond the history revalidation rules. That limitation does not make a
second prompt useful for ordinary clear, but it is why operations that destroy
their own recovery history keep a stronger review boundary.
