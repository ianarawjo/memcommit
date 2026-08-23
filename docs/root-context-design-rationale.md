# Root Context Design Rationale

- Status: Implemented
- Scope: Context storage, slash namespaces, exact deletion, and the
  `construction-updates` hierarchy

## 1. Decision

A Context may exist at a namespace node that also contains descendant
Contexts.

For example, all of the following are valid and independent Contexts:

```text
construction-updates
construction-updates/building-access
construction-updates/event-relocations
```

`construction-updates` is called a Root Context because of its role in this
hierarchy. It is not a separate class, a privileged singleton, or a hard-coded
name. Any ordinary Context may occupy a namespace root.

## 2. Why There Is No Special `main`

The previous prototype used:

```text
construction-updates/main
```

as an index Context that embedded the six update Contexts. The index had no
atomic memories of its own and existed only because a namespace node could not
also be a Context.

That design had three drawbacks:

1. `main` suggested Git branch semantics even though the hierarchy behaves
   more like directory navigation.
2. The physical `construction-updates/` namespace and the logical `main`
   index duplicated the same organizational role.
3. Every child addition had to be reflected in a separate index Context.

Allowing a Context directly at `construction-updates` removes this adapter.
The name `main` remains a valid ordinary Context name; it is simply no longer
special or needed for this hierarchy.

## 3. Physical Layout

The existing directory-backed store can represent a Context and descendant
namespaces at the same node:

```text
~/.mem/contexts/construction-updates/
├── context.json
├── checkpoints/
├── building-access/
│   ├── context.json
│   └── checkpoints/
├── event-relocations/
│   ├── context.json
│   └── checkpoints/
└── route-changes/
    ├── context.json
    └── checkpoints/
```

The Root Context owns only:

```text
construction-updates/context.json
construction-updates/checkpoints/
```

Each descendant Context owns the corresponding artifacts in its own
directory. No Context owns the entire directory subtree.

## 4. Creation Order Is Symmetric

Both creation orders are supported.

Root first:

```bash
mem init construction-updates
mem init construction-updates/building-access
```

Descendant first:

```bash
mem init construction-updates/building-access
mem init construction-updates
```

When a Root Context is created after descendants, the existing descendant
directories, Context UIDs, memories, and checkpoint histories are preserved.

A pre-existing exact target directory may be adopted as a Root Context only
when its direct entries are real namespace directories. Unexpected files,
reserved storage artifacts, and symbolic links cause initialization to fail
without overwriting them.

### Opt-in parent materialization

Plain `mem init NAME` retains the one-name contract above. A participant who
wants shell-like upward navigation may instead ask initialization to ensure
every lexical prefix:

```bash
mem init --parents test/update/from
mem init -p test/update/to
```

The first command creates the missing Contexts `test`, `test/update`, and
`test/update/from`. The second reuses the first two unchanged and creates only
`test/update/to`. Re-running either command is idempotent: existing Context
UIDs, direct contents, and checkpoint histories are preserved, and the
requested leaf becomes current.

Every newly materialized prefix is an ordinary empty Context with its own
initial checkpoint. Creation holds all prefix write locks from preflight
through the final current-Context state write. If any Context, checkpoint, or
state write fails, only the Contexts created by that invocation are rolled
back; reused prefixes and descendants are preserved.

This is an in-process exception transaction, not a durable multi-file journal.
A process or machine crash between prefix writes can leave a partial
hierarchy. Re-running the same idempotent `mem init --parents NAME` repairs the
missing prefixes without replacing Contexts that were already persisted.

`--parents` is opt-in because automatically changing every slash-delimited
creation into several visible, UID-bearing Contexts would silently alter
existing scripts and picker contents. It is a creation convenience, not a
permanent “all ancestors exist” invariant: exact parent deletion may still
leave a descendant addressable. Missing parents can be materialized again by
re-running `mem init --parents` for that descendant.

## 5. Path Hierarchy Is Navigation, Not Logical Membership

Path prefixes are addresses and physical organization:

```text
construction-updates
construction-updates/building-access
```

They do not automatically create an embed relationship. `mem ls` nevertheless
uses this lexical hierarchy for read-only navigation: an existing Context
exactly one segment below the listed Context appears as a child row, and
`mem ls -R` can descend through that row.

An explicit operation is still required when that descendant must become a
persisted logical item of the Root Context:

```bash
mem embed construction-updates/building-access \
  --into construction-updates
```

This distinction is intentional:

- namespace placement does not silently mutate Context contents;
- `mem ls` can show discoverable children without changing the Root digest,
  order, checkpoints, or direct items;
- the Root Context still controls which descendants belong in its persisted
  logical view;
- a Root Context may embed a Context from another namespace;
- an unembedded path descendant remains independently addressable and visible
  for list navigation;
- only materialized immediate Contexts appear: a deeper descendant does not
  synthesize a missing intermediate Context;
- `mem ls -R` traverses both these exact namespace edges and the explicit
  embed graph, while other semantic operations retain their existing scope.

## 6. Ordinary Context Operations Apply to Roots

Because a Root Context is an ordinary Context, existing commands work without
special cases:

```bash
mem switch construction-updates
mem add "Campus-wide construction overview."
mem ls
mem ls -R
mem show
mem status
mem checkpoint "Reviewed update hierarchy"
```

The Root Context may directly contain:

- atomic Memory records;
- MemoryRef records;
- embedded Context references.

Its direct item order and checkpoint history remain independent from all
descendant Contexts.

## 7. `clear` and `delete` Are Exact-Context Operations by Default

`mem clear construction-updates` removes the Root Context's direct Memory,
MemoryRef, and embedded Context entries. It does not delete descendant Context
files.

The explicit recursive form empties the materialized local lexical subtree as
one checkpointed command:

```bash
mem clear construction-updates --recursive
```

It removes the direct items of `construction-updates` and each existing
`construction-updates/...` Context while retaining every Context and its
checkpoint history. It does not follow embedded Context edges, and one
`mem undo` restores every changed member as one command unit. The root itself
must exist; clear never synthesizes a missing namespace parent from a path
prefix.

`mem delete construction-updates` removes only:

```text
construction-updates/context.json
construction-updates/checkpoints/
```

It preserves:

```text
construction-updates/building-access/
construction-updates/event-relocations/
...
```

If the deleted Root Context is current, the current Context is cleared. If a
descendant is current, that descendant remains current.

Deletion remains exact-only. It stages the exact Context file and checkpoint directory under temporary
names in the same directory before removing them. Descendant directories are
never passed to recursive deletion.

Deleting an embedded descendant may leave a raw Context reference in the
parent's stored JSON until that parent is loaded and saved again. The loader
treats an unavailable child as unresolved and does not infer a replacement
merely from a shared path prefix. Context references do not yet enforce their
stored target UID when an exact same-name Context is deleted and recreated;
that pre-existing identity limitation is outside this storage change.

## 8. Reserved Path Segments

The physical representation reserves these Context path segments:

```text
context.json
checkpoints
```

They are rejected at every path depth and with case-insensitive comparison.
Examples:

```text
context.json
root/context.json
checkpoints/child
root/Checkpoints
```

This prevents a descendant Context path from colliding with a Root Context's
owned storage artifacts, including on case-insensitive filesystems.

Because older prototypes did not reserve these names, an upgrade should check
for pre-existing Contexts that use them before migration.

## 9. Checkpoint and Branch Semantics

Root and descendant histories are independent:

```text
construction-updates/checkpoints/
construction-updates/building-access/checkpoints/
```

A Root revert restores only the Root Context's direct snapshot. It does not
rewind a descendant's current memories or checkpoint log.

A branch may create a Context at an ancestor namespace that already contains
descendants. For example, branching to `review` is valid when
`review/existing-child` already exists. Branch rollback removes only the new
`review` Context artifacts and preserves the existing descendant. Creation,
source UID/digest and history-digest revalidation, checkpoint copy, and final
current-state compare-and-swap share one deterministic source/target lock set.
Rollback therefore occurs only while the exact require-new identity remains
locked; it cannot delete a replacement or another writer's completed update.
A concurrent current selection aborts branch creation instead of being
overwritten.

Checkpoint inheritance is private to this branch transaction. The earlier
public copy-only store choreography was removed because create, copy, and
selection as separate calls could reintroduce the race this boundary closes.

This exact-Context behavior remains the default. Branch may additionally
freeze the Source's lexical descendants and map the whole set under a fresh
target root. That subtree form creates new Context identities, remaps internal
Context and Memory references in both current records and inherited checkpoint
frames, and publishes or rolls back the complete mapped hierarchy as one
command. See `mem-branch-design-rationale.md` for the range and identity
contract.

Creating a checkpoint for an unsaved Context is rejected. Initial auto
checkpoints are allowed only as part of the internal `save` operation, avoiding
orphan checkpoint directories.

Checkpoint filenames include a short checkpoint UID in addition to their
timestamp and description slug. This prevents rapid repeated operations, such
as embedding several children in one second, from overwriting earlier history.

## 10. Safety Rules

Root Context support retains the slash namespace safety rules:

- absolute paths are rejected;
- `.` and `..` path segments are rejected;
- leading, trailing, and repeated slashes are rejected;
- backslashes, drive-style colons, and control characters are rejected;
- namespace and checkpoint symbolic links are not followed;
- resolved paths must remain under the Context store;
- malformed or path-mismatched `context.json` files are not listed as valid
  Contexts;
- unexpected files in a prospective Root directory are preserved and block
  Root initialization.

## 11. `construction-updates` Migration

The safe migration sequence is:

1. Create the new Root Context.
2. Embed all six existing descendant Contexts into it.
3. Verify direct and recursive listing.
4. Switch to the Root Context.
5. Delete the obsolete `construction-updates/main` Context last.

Deleting `main` last preserves it as a fallback if any earlier step fails.
The descendant Contexts are never recreated, so their UIDs and histories remain
unchanged.

## 12. Validation Scenarios

The implementation is tested for:

- root-first and descendant-first creation;
- opt-in, idempotent parent materialization and all-or-nothing rollback;
- independent UIDs, memories, and checkpoint histories;
- root and descendants appearing in `mem contexts`;
- no persisted implicit embed from a slash prefix;
- read-only immediate-child navigation in `mem ls` and `mem ls -R`;
- explicit-embed deduplication when the same Context is also a namespace
  child;
- root `switch`, `add`, `clear`, checkpoint, and revert behavior;
- unique files for rapid same-description checkpoints;
- branch creation at an existing ancestor namespace;
- branch rollback preserving existing descendants;
- root deletion preserving descendant content, identity, and history;
- child deletion preserving root and siblings;
- root deletion and recreation without changing descendants;
- reserved storage segments at every path position;
- checkpoint and namespace symlink protection;
- checkpoint artifacts not being misidentified as descendant Contexts.

Related implementation and tests:

- [`memcommit/store.py`](../memcommit/store.py)
- [`memcommit/commands/list_memories.py`](../memcommit/commands/list_memories.py)
- [`tests/test_context_namespaces.py`](../tests/test_context_namespaces.py)
- [`mem ls design rationale`](mem-ls-design-rationale.md)
