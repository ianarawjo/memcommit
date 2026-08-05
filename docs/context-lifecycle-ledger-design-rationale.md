# Profile-scoped Context lifecycle ledger

## Decision

An ordinary Context deletion retains one metadata-only
`CONTEXT_DELETED` event under the active Profile's MemoryStore root:

```text
<profile store>/
├── contexts/
└── ledger/
    └── context-events/
        └── <event_uid>.json
```

The Profile is the retention boundary. Deleting one Context removes its live
record, checkpoint history, and Context-scoped derived artifacts, but not its
Profile-owned lifecycle event. A future whole-Profile deletion must remove the
ledger together with the rest of that Profile store.

This initial rollout records deletion only. Creation, branch, rename, switch,
embed, and subtree events remain future lifecycle kinds rather than being
silently inferred from the deletion format.

## Motivation

Context checkpoints are stored inside the Context namespace they describe.
That is appropriate for content recovery but cannot prove that a Context once
existed after `mem delete` removes both `context.json` and `checkpoints/`.
Memory trace events are reconstructed from those snapshots and therefore do
not supply a surviving Context lifecycle record either.

A Profile-level ledger preserves the deletion boundary without weakening the
existing rule that exact Context deletion preserves lexical descendants. It
also separates same-name lifetimes: `context_uid` is the identity, while
`last_context_name` is only the final locator for that identity.

## Event contract

Schema version 1 contains:

- canonical `event_uid` and `operation_id` UUIDs;
- a timezone-aware timestamp and `kind: CONTEXT_DELETED`;
- the deleted Context's opaque, nonempty UID and last canonical name;
- the digest of its last direct Context record;
- `previous_checkpoint_status` with one of `RECORDED`, `NONE`, or `UNREADABLE`;
- the latest checkpoint UID and canonical record digest only for `RECORDED`,
  with two explicit nulls for `NONE` and `UNREADABLE`; and
- `descendants_preserved: true`.

The Context UID remains opaque because legacy stores may contain non-UUID
identities that must still be deletable. Raw Context names and UIDs never enter
event filenames. One UUID-named JSON file per event avoids partial JSONL
appends and permits atomic same-directory publication.

The ledger deliberately retains no Memory content, Context snapshot, provider
dialogue, rationale, or restorable checkpoint. Digests are evidence that bind
the event to the pre-deletion state; they are not recovery copies.

## Commit and failure boundary

The public user deletion path freezes the event metadata while holding the
shared Context-graph lock and exact Context write lock. Deletes of independent
Contexts may preflight and clean up concurrently. A short exclusive lifecycle
lock covers only event publication through the primary unlink, while readers
take that lock shared. Thus a reader cannot observe a provisional final event
that normal rollback later removes. The store then:

1. preflights the Context and all deletion-owned derived artifacts;
2. renames the exact `context.json` and `checkpoints/` to hidden same-directory
   staging paths and fsyncs their Context directory;
3. creates and fsyncs any new Profile ledger directories, then atomically
   publishes and fsyncs the event;
4. unlinks the staged primary Context record; and
5. removes staged history and Context-scoped derived artifacts, then clears the
   current pointer when necessary.

If staging or ledger publication fails, the Context and checkpoint paths are
restored and deletion does not commit. If the primary unlink fails, the event
is removed and both paths are restored. Once the primary record has been
unlinked, the event must remain even if later state or sidecar cleanup fails:
the Context is no longer live, so removing its deletion record would make the
ledger less truthful.

Post-commit cleanup is failure-collecting. A failed sidecar or state operation
does not prevent the store from attempting every other privacy cleanup. The
store then raises `ContextDeletionCommittedError`, which carries the retained
event. The CLI reports “deleted, cleanup incomplete” with that event receipt
rather than implying that deletion rolled back. Internal creation rollback has
no event and surfaces its first cleanup failure normally.

The ledger lock preserves normal-process observation semantics, not a global
ordering across the complete deletion operations. Independent deletes retain
per-Context concurrency, and a concurrent undo/redo history scan can fail
closed on transiently changing history rather than blocking all deletion.

As with the repository's other multi-file operations, this provides normal
exception rollback around the commit boundary, not a crash-recovery journal.
A machine crash between event publication and primary unlink can leave staged
storage and a final-named event that require future repair tooling. Directory
fsync narrows this window but cannot make the multi-directory operation atomic.
The event is intentionally not repurposed as an automatic recovery instruction.

## Internal rollback is not user deletion

`MemoryStore._delete_locked()` is also used to discard a newly created Context
when a larger creation operation fails. That rollback passes no lifecycle
event. Recording it as `CONTEXT_DELETED` would invent a durable user-visible
lifetime for a Context whose creation never committed.

Only the public exact-deletion paths create the event. Successful callers
receive the validated event, and readers can filter the Profile ledger by
stable Context UID, exact historical name, or slash-delimited namespace
prefix. The current CLI reports the short event UID after deletion; a broader
Profile/namespace lifecycle browser is intentionally outside this initial
change.

## Limitations and future work

- The event ledger does not yet contain creation or branch events, so it cannot
  reconstruct a complete Context lifetime on its own.
- If checkpoint history cannot be parsed safely, deletion still records the
  required Context identity and direct-record digest with status `UNREADABLE`.
  It leaves both optional previous-checkpoint fields null and never guesses
  metadata from a malformed record.
- Archival `mem profile import` copies the complete store, including this
  ledger; clean `mem import` and Study initialization deliberately exclude it,
  but its pre-import inspection does not yet validate lifecycle event schemas.
  Ledger reads remain strict and fail closed on malformed event storage.
- There is no `mem profile delete` command yet. When added, it must delete the
  managed Profile store and registry entry together under a Profile-lifetime
  lock, or forbid deletion while any process can still use that store. Existing
  processes intentionally remain bound to the Profile root selected at start
  and could otherwise recreate a supposedly deleted root.
- Directory-style recursive deletion needs its own reviewed command and event
  contract. This event always describes one exact Context and explicitly
  preserves descendants.
