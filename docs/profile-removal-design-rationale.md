# Permanent Profile removal design rationale

## Motivation

Repeated Study runs register a participant Profile and a granted-memory
Profile, so old sessions eventually crowd the Profile selector and retain
substantial checkpoint history. People need two explicit scopes: deleting one
focused child without deleting its sibling, and deleting the complete Study by
targeting its header.

Deletion is intentionally permanent. A Profile store owns its Memories,
workflow sessions, command history, and Context checkpoints. Removing that
whole directory reclaims the complete run and means `mem` has no source from
which it could restore the content.

## Command and interaction contract

- `mem profile remove PROFILE` permanently deletes only that Profile store and
  removes every Grant whose authority or grantee endpoint is the Profile.
- `mem profile remove-study STUDY` permanently deletes every current or legacy
  member store and every Grant connected to those members.
- In the Profile TUI, Study headers are keyboard rows. `D` on a header reviews
  `remove-study`; `D` on a Profile child reviews `remove`.
- The review lists store, Memory, session, checkpoint, and Grant deletion and
  says that `mem` cannot undo or recover it. `Enter` or `A` applies only the
  exact frozen command; Escape returns without mutation.
- A successful deletion returns to the refreshed Profile selector with a green
  in-selector receipt. It does not exit `mem profile`. Each subsequent deletion
  starts from a newly loaded registry generation and visible Profile catalog.
- While recursive deletion is running, the frozen review remains visible and
  the shared `.`, `..`, `…` busy cadence appears in the header and footer.
  Deletion runs in the shared non-cancellable background executor so the TUI
  can repaint without allowing a second mutation. Escape or Ctrl-C requests a
  close only after the already approved deletion finishes.
- Direct `mem profile remove ...` and `mem profile remove-study ...` commands
  remain one-shot CLI operations and print their full permanent-deletion
  receipts before exiting.
- Enter continues to select a Profile while the selector is not in review. A
  Study header is a grouping and deletion target, never an implicit Profile
  selection.

Registry schema version 3's `removed_profile_uids` remains as an identity
tombstone. The corresponding store is not retained. Keeping the Profile entry
and Study provenance lets a surviving Study child retain its header and makes
a completed deletion distinguishable from a missing or corrupt live store.
The tombstone is display metadata, not a trash or restore mechanism.

## Invariants

1. The fixed `authoring` and `study-baseline` Profiles cannot be deleted.
2. The active Profile cannot be deleted. A Study containing it cannot be
   deleted; the person must select another Profile first.
3. Study membership is resolved from validated provenance and stable Study UID,
   never from a Profile-name suffix.
4. Removing one Study child deletes only that store. The other child stays
   visible beneath the same Study header.
5. Every Grant connected to a deleted Profile is removed in the same registry
   generation, so no live Grant references a store that no longer exists.
6. The reviewed registry generation and target UID are revalidated under the
   registry lock before deletion begins.
7. Every target store is fully validated as a plain, non-symlink tree before
   any recursive deletion can occur.
8. The whole UID-rooted store is destroyed. This includes all Context records,
   Memories, workflow sessions, command receipts, and checkpoints inside it.
9. After a TUI deletion, the reviewed picker instance is discarded. The next
   selector screen is built from the post-deletion registry and cannot reuse a
   stale target UID, generation, inventory, or Study row.
10. Progress claims only that local deletion is still running. The animation
    does not estimate bytes, checkpoint count, percentage, or remaining time.

## Publication and failure boundary

Target stores first move to a private batch directory beneath the managed
stores parent. The move uses exact, validated UID paths on the same filesystem.
The registry generation then publishes the tombstones and removes incident
Grants. If publication did not occur, the batch is moved back to the canonical
UID paths before the registry lock is released.

After publication, the batch is recursively destroyed and the stores directory
is fsynced. There is deliberately no post-publication rollback: restoring the
old registry after any bytes had been destroyed could expose an incomplete
Profile as live. A failure after publication is therefore reported as a failed
cleanup with no supported `mem` recovery route, never as a successful atomic
restore.

This registry lock serializes cooperative Profile mutations, but it is not a
lease held by already-running commands. A process that resolved the deleted
store before approval may fail when it next accesses that path. The exact
review's permanent-deletion warning is the boundary chosen for this research
prototype.

## Compatibility

Registry versions 1 and 2 still load with an empty tombstone set and migrate on
the next registry write. A version 3 tombstone must identify a registered
managed Profile and cannot identify `authoring` or the active Profile. A store
left behind by the earlier selector-only implementation can be permanently
purged by naming that Profile directly or deleting its complete Study; a
tombstone whose store is already absent is treated as completed deletion.

`archive-study` retains its existing legacy detach behavior. It writes an
archive manifest and preserves stores, so it remains semantically distinct
from permanent `remove-study`.

## Alternatives considered

Keeping every store and hiding only its selector row was the first
implementation. It protected in-flight readers and preserved Grants, but did
not reclaim sessions or checkpoints and contradicted the intended permanent
cleanup contract.

Unregistering a deleted child entirely was rejected. Current Study validation
requires both provenance roles, and removing the metadata would make the
surviving child lose the Study header. A metadata-only tombstone preserves the
display relationship without preserving content.

Treating any child deletion as whole-Study deletion was rejected because the
visible hierarchy communicates two different target scopes. The focusable
header owns whole-Study deletion; its child owns only itself.

Mutating one long-lived picker's row collection in place was rejected. The
command-owned loop instead closes the reviewed picker, reloads the registry,
and opens a fresh picker with the success receipt. This keeps storage and
deletion logic out of the presentation component and makes the new generation
the only source for the next selection, at the cost of a brief terminal-screen
refresh between the two picker instances.

## Intentional non-goals

There is no trash, restore, undo, or checkpoint-based recovery for Profile or
Study deletion. External exports and copies outside the managed Profile store
are not discovered or deleted. Secure overwrite guarantees are also outside
scope: filesystem snapshots, backups, and storage-level recovery may exist
outside `mem`'s control.
