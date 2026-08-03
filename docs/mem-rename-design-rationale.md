# `mem rename` design rationale

## Status and intent

`mem rename` changes the canonical locator of one existing ordinary Context
namespace without changing the identities or contents of the Contexts and
Memories inside it:

```bash
mem rename OLD NEW
mem rename OLD NEW --force
```

The motivating Task 1 case is migration from provisional fixture names such as
`construction-updates` to participant-scoped names such as
`participant/construction-updates`. The same operation is useful whenever a
slash-delimited Context namespace has acquired the wrong organizational name.

This is a graph migration, not merely a directory rename. Context names are
locators while Context UIDs are identities. Moving the directory but leaving
stored owner names, references, current state, or restorable checkpoints at
the old locator would produce a store that is physically present but no longer
semantically coherent.

## Command contract

`OLD` locates an existing ordinary Context. The command captures the current
Context once and resolves `OLD` through the shared existing-Context locator
contract. Thus a bare value is a canonical global name, while `.`, `..`,
`./...`, and `../...` opt into lexical relative resolution.

`NEW` is different: it declares a new canonical Context name. It is validated
as an exact slash-delimited identifier and is never interpreted relative to
the current Context. This follows the same semantic distinction as `mem init
NAME`: a new identity locator must not acquire a different meaning when global
current state changes.

Before mutation, the command builds a read-only plan and displays the resolved
canonical source and destination, the number of Contexts that will move, and
the number of lexical descendants included. Confirmation is required by
default. `-f`/`--force` skips only that prompt; it does not relax name,
collision, integrity, identity, freshness, or rollback checks.

The operation requires an ordinary Context at the exact `OLD` name. It renames
that Context and every stored ordinary Context whose canonical name begins
with the slash-boundary prefix `OLD/`:

```text
team/task              -> participant/task
team/task/access       -> participant/task/access
team/task/access/wiki  -> participant/task/access/wiki
team/taskish           -> unchanged
```

The descendant relationship is lexical and deterministic. The command does
not infer a hierarchy from embedded Context references or Memory contents.

## Identity and content invariants

A successful rename preserves:

- every moved Context UID;
- every Memory UID, Memory content value, and direct-item order;
- every `MemoryRef` UID and target-Memory UID;
- every existing checkpoint UID, timestamp, description, and command record;
  and
- unrelated ordinary Context names and records, except where one of those
  records contains an inbound pointer to a moved Context.

No semantic provider is called. The command does not summarize, translate,
deduplicate, edit, or otherwise reinterpret Memory text. A reverse move is a
later explicit rename with its own plan, confirmation, checks, and checkpoints;
the first operation does not leave a hidden alias or tombstone.

## Live graph migration

The store scans every ordinary Context record and fails closed on malformed or
duplicate identity data before planning the move. For the UIDs in the moved
namespace, it updates only typed locator fields:

| Persisted object | Rename behavior |
| --- | --- |
| moved Context owner | rewrite `name`; preserve Context UID |
| `context_ref` | rewrite `name` when its target UID and exact old name agree |
| `memory_ref` | rewrite `target_context.name` under the same UID/name check |
| current Context state | map the exact source name or lexical descendant |
| ordinary Context outside the subtree | preserve it, but rewrite an inbound ordinary pointer when needed |
| prose, messages, rationales, and arbitrary command arguments | preserve verbatim |

UID and old-name agreement matters. A name is only a locator, so a deleted and
recreated Context at the same path must not capture a stale `context_ref` or
`memory_ref`. If a live typed pointer names a moved Context UID but its stored
name is not the currently expected old name, rename rejects the graph rather
than guessing which field is authoritative. Normal embedded-Context loading
also requires the resolved target UID to match the persisted pointer UID.

Every live ordinary Context record changed by the migration receives one
automatic `rename` checkpoint. This includes moved Contexts and an otherwise
unmoved owner whose inbound reference changed. The checkpoint identifies the
namespace operation and the owner's before/after locator, so the provenance
boundary is visible without treating one graph-wide action as an unexplained
series of edits.

## Checkpoint history

Existing checkpoint directories inside the source namespace move with their
Context directories. Existing checkpoint records keep their UIDs and their
historical owner labels. In particular, an old checkpoint snapshot's top-level
Context name is evidence of what was recorded then; `revert` already restores
that content into the currently addressed live Context and replaces the
snapshot owner UID/name at application time.

Typed pointers inside a restorable checkpoint are different. Rename rewrites
ordinary `context_ref` and `memory_ref.target_context` locator fields in every
checkpoint snapshot, including snapshots recursively stored in
`args.log_snapshot`. Otherwise reverting after a successful rename could
resurrect an ordinary pointer to a locator that deliberately no longer exists.
Free text and unrelated command arguments remain historical evidence and are
not subject to search-and-replace.

## Ground and translation continuity

Two durable derived formats have an explicit, schema-validated migration
contract because they can contain reviewed work that should survive a
metadata-only Context move:

- **named Ground frames:** a frame bound to a changed Context UID follows the
  Context's current name. Its stored digest advances only when it exactly
  matched the pre-rename live record. An already-stale frame remains stale.
- **translation catalogs and legacy translation views:** the source Context
  name follows the matching UID. A stored Context digest, where that format
  has one, advances only from an exact pre-rename match. Curated translations,
  provider variants, review state, and source-Memory bindings remain intact.

This conditional digest update preserves the distinction between a fresh
artifact affected only by locator metadata and an artifact that was already
out of date for an unrelated reason. Rename must not make stale work appear
fresh merely because it encountered the same Context UID.

Other semantic artifacts—including cached Impact/Update, Meld, Compare,
Atomize, and Review state—are not rewritten. Their operation-specific
Context-name and digest checks remain authoritative; after a relevant rename,
the owning command must reject, miss, or regenerate stale state according to
its existing contract. Broadly rewriting every cached provider result was
rejected because these formats have different authority, privacy, and
compare-and-swap semantics, and because preserving an old explanation under a
new locator could falsely imply that it was revalidated.

## Query-only boundary

Rename operates only on the ordinary Context store. It does not open, inspect,
move, copy, or rewrite query-only source files, and it does not change a
`QueryContextRef`. In particular, the command cannot convert an ordinary
Context into the query-only organizational source used by Task 1.

An ordinary destination is not globally rejected merely because an opaque
query-only source uses the same public name: these are separate authority
namespaces in the current prototype. A rename is rejected, however, if its
ordinary pointer rewrite would leave one direct owner with both an ordinary
`context_ref` and a `QueryContextRef` under the same child selector name. That
local ambiguity would make `show`/`find`-style selection unsafe even though
the underlying stores are distinct.

## Planning, concurrency, and failure behavior

Planning freezes a complete graph digest over ordinary Context records,
restorable checkpoints, current state, named Ground records, and translation
artifacts. Application reacquires the graph, Context, current-state, and
Ground locks; rebuilds the plan; and requires it to equal the reviewed plan.
If any participating record, destination claim, or artifact changed after
review, nothing is renamed and the caller must review a new plan.

An exclusive Context-graph lock closes a gap that per-name locks cannot: while
rename scans inbound references, another process must not create a previously
unknown owner containing a new pointer into the source namespace. The final
destination must remain absent. Source/destination equality, overlapping
namespaces such as `a` to `a/b` or `a/b` to `a`, occupied destinations,
case-only or normalization-only aliases of the same filesystem location,
unsafe symbolic links, malformed records, and introduced selector collisions
all fail before publication.

The destination is rechecked immediately before the physical namespace move
while cooperative Context creators remain excluded by the graph lock. Changed
JSON records are then written atomically per file and the result is reloaded
and verified. If an ordinary exception occurs, the store removes checkpoints
created by that attempt, restores the exact pre-operation bytes, and moves the
namespace back. If rollback itself cannot complete, the command raises a
distinct hard failure rather than claiming success. Direct, non-cooperating
filesystem mutation remains outside this local store's coordination contract.

This provides **exception atomicity**, not durable crash atomicity. There is no
write-ahead journal or startup recovery procedure yet. A process or machine
crash after the directory move but before all related files are published can
leave a partial migration that requires manual repair. This limitation is
consistent with the current local research prototype's multi-Context update
transaction, but it must be addressed before rename is used as a remote or
multi-user publication primitive.

## Alternatives rejected

- **Move only the exact root Context.** Slash descendants are part of the
  visible namespace contract; leaving them at the old prefix would split one
  fixture or worktree across two roots.
- **Rename only the directory.** Stored owner names, inbound references,
  current state, and future-restorable checkpoints would still point at the
  old locator.
- **Copy into new Contexts with new UIDs.** This would turn an organizational
  correction into a branch/import operation and break reference, Ground,
  translation, and checkpoint identity.
- **Merge into an occupied destination.** Reconciliation and collision policy
  belong to Meld/merge-like operations; rename has a single unambiguous
  destination and fails closed.
- **Rewrite every occurrence of the old string.** Free text and historical
  command records are evidence, query-only content is outside authority, and
  an equal string is not proof of a typed Context pointer.
- **Leave aliases or automatic redirects.** They would make canonical listing,
  collision checks, relative locators, and later deletion harder to explain.
  Explicit reverse rename is sufficient for this prototype.
- **Silently repair all semantic caches.** Only formats with a focused,
  schema-validated continuity rule are migrated. Other analyses must pass
  their own freshness boundary again.

## Current limitations and non-goals

- The operation renames ordinary Context namespaces, not individual Memories.
  A Memory currently has no independent name; changing its content is an edit.
- Query-only sources, remote systems, publication branches, shell working
  directories, and filesystem paths outside the local store are not renamed.
- Rename does not establish aliases, cross-store redirects, or an upstream
  relationship between the old and new names.
- There is no destination merge, case-only rename, dry-run export format,
  durable crash journal, or automatic repair command for an interrupted move.
- Semantic analyses not covered by the Ground/translation continuity rules
  must be rerun or otherwise handled by their owning command.
