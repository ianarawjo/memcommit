# Direct Memory Copy and Move design rationale

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Motivation

MemCommit previously exposed several adjacent meanings without a general
direct-Memory ownership transfer:

- Reference retains an immutable read-only snapshot.
- Embed retains Source ownership through a live link.
- Branch copies a complete Context or subtree.
- Import copies a Memory from another Profile while preserving its identity.
- Search Save As can create fresh ordinary Memories, but only inside a new
  Result Context.

None of those operations copies selected ordinary Memories into an existing
local Context, and none atomically removes selected Memories from their old
owners while adding them to a new owner. Copy and Move fill that exact gap;
they do not reinterpret Reference, Embed, Branch, Import, Merge, or Search.

## Operation-package ownership and Branch boundary

Copy and Move are separate Help operations and own separate application entry
packages. Their shared data vocabulary and Store transaction kernel use the
conventional paired name `copy_and_move`:

```text
memcommit/application/operations/copy/
  application.py
  runtime.py
memcommit/application/operations/direct_changes/move/
  application.py
  runtime.py
memcommit/application/operations/copy_and_move/
  application.py  # shared typed values and validation primitives
  runtime.py      # shared graph freeze and atomic Store mechanics
```

Copy owns `prepare_copy`/`run_copy` and its Copy-specific runtime port; Move
owns `prepare_move`/`run_move` and its Move-specific runtime port. The paired
kernel composes Store, Grant, protection, link, checkpoint, and atomic
multi-Context publication without presenting itself as a third operation.
Console and machine adapters enter the operation-specific application
functions. No physical `memory_transfer` package remains.

The persisted checkpoint field `memory_transfer`, versioned agent fallback
code `memory_transfer_failed`, and published `MemoryTransfer*` Python
error/receipt names remain compatibility contracts. Renaming those serialized
and public values would not improve package navigation and would prevent older
checkpoints or clients from being read.

Branch remains a separate operation owner even though it also copies Memory
values. Branch creates a new Context or lexical subtree, copies and projects
checkpoint histories, records Context and Memory lineage, changes the current
Context, and owns whole-tree Undo/Redo archives. Copy and Move instead transfer
selected direct Memories into an already existing Target and never create or
inherit a Context history. Their common fresh-identity, lineage, and atomic
storage mechanics stay in shared domain/Store infrastructure; similarity of
those mechanisms is not a reason to merge the two transaction contracts.

This is an ownership-only relocation. It changes no Copy/Move route state,
authority, identity, placement, link policy, checkpoint schema, terminal
interaction, or evidence membership. Existing ordered TUI captures therefore
remain valid and are not refreshed.

## Command contract

Both operations accept one or more direct-Memory locators in caller order:

```text
mem copy [CONTEXT:]UID... [--from SOURCE] [--into TARGET | --to TARGET]
mem move [CONTEXT:]UID... [--from SOURCE] [--into TARGET | --to TARGET]
```

A bare UID or prefix is resolved against the strict ordinary-local Source
catalog and must have exactly one direct owner. A granted Copy Source is
available only through an explicit public owner in `CONTEXT:UID` or
`--from SOURCE`; Move recognizes that same explicit form only to report why
external deletion is forbidden. `--from SOURCE` applies one owner to every
unqualified selector and cannot be combined with a qualified selector. Source
and Target relative locators share the current Context captured once at command
start. An existing local Target is required for both operations.

The positional list and repeatable `--memory/-m` form are equivalent ordered
batch inputs but cannot be combined. Target defaults to the command-start
current Context. `--before` and `--after` select one exact Target direct-item
gap; omitting both appends the complete batch. Every selector, collision, gap,
Source binding, and Target binding is validated before publication.

In a TTY, bare Copy and Move open one full-screen setup shaped by the current
Embed workbench rather than a compact endpoint form. The Source frame extends
the shared direct-Memory selector to `MULTIPLE`; Copy exposes effectively
local and retained-Copy-authorized granted direct Memories while Move exposes
only ordinary local owners. A granted TUI selection is projected with its
public owner, so it never broadens the bare-UID lookup contract. Checked
Memories are projected in explicit check order, and a
valid exact-command edit replaces that order atomically. The Target frame
composes the shared Context tree with Embed's direct-item placement projection,
so exactly one movable `POSITION · n/total` line represents the current gap
instead of a duplicated BEFORE/AFTER row for every item. Neither operation adds
a normal policy frame: Copy has one fixed new-identity meaning, while Move
follows live Embeds unless Break is explicitly typed into the exact command.

The last frame is the same compact editable `COMMAND · RUNNABLE` control used
by Embed. Edits are parsed and resolved completely before the Source checks,
Target, gap, or policy state changes. Enter freezes an exact application plan,
returns it to the CLI, and the CLI applies that same plan once. The TUI never
publishes storage itself. Outside a TTY, bare Copy and Move return stable
`CONTEXT:MEMORY --into TARGET` guidance.

## Copy identity

Copy leaves every Source unchanged and creates ordinary editable Memories in
the existing Target. Every output receives a store-wide fresh UID, matching
the meaning of an independently editable duplicate and the existing Search
Save As Copy contract. Copy permits Source and Target to be the same Context,
which is an explicit duplicate operation. Exact duplicate content is allowed;
content deduplication remains the separate Dedup/Dedun concern.

The earlier `PRESERVE` option was removed from the TUI, editable command, CLI,
Python facade, typed receipt, agent schema, and MCP projection. A Copy that
keeps the Source UID creates two independently editable Memories that appear
to share one identity without any synchronization, branch owner, or later
reconciliation contract. Branch now avoids the same ambiguity: it allocates a
fresh occurrence UID and records Source-to-target ancestry in its checkpoint
receipt, which structural Merge can follow without making two writable objects
share an address. Existing stores that already contain same-UID Memories in
different Contexts remain readable; this change does not rewrite historical
data, but neither Copy nor new Branch/Merge additions create another such pair.

Removing the field is an intentional callable-contract break. The strict
Memory-transfer agent schema advances to version 2 so a version-1 caller
cannot mistake the narrower Copy contract for the former policy-bearing one.

The checkpoint retains only Source/Target identities, UID mappings, placement,
the fixed `NEW_UIDS` invariant, and plan digest. It does not duplicate Memory
content into searchable command metadata because the Context pre/post images
already retain the exact values.

## Granted Copy and retained ownership

Copy may select an exact direct Memory from a READ-granted public Context. That
use is a permanent value transfer, not a live relationship, so every granted
contributor requires `READ + DERIVE + EXPORT + SAVE_ANALYSIS`. A batch spanning
more than one ownership or provenance domain additionally requires `COMBINE`
from every granted contributor. The permission set is intersected; one
permissive Grant never waives a restriction on another Source.

The frozen Source binding records the public and authority Context names,
authority and grantee Profiles, attachment and resource identities, Grant UID
and revision, Source Context/Memory UIDs, and reviewed content digest. Apply
holds the registry and exact authority Source locks through the local Target
compare-and-set. Revocation, permission drift, Source replacement, content
drift, or Target drift therefore publishes no partial Memory or checkpoint.

A successful Copy creates a fresh ordinary local UID. Its receipt and
checkpoint retain the Source-to-output provenance mapping, while the new
Memory remains independently editable and available after the Grant is later
changed or revoked. Copy neither creates a live pointer nor claims branch or
merge lineage; it copies selected values into an existing local Context and
does not create a new Context.

## Move identity and live links

Move preserves every selected Memory UID and content while changing its direct
owner. Target must be distinct from every selected Source owner, and no Target
direct item may already use a selected UID. Same-UID copies from different
legacy Contexts cannot be moved into one Target because one Context cannot own
two direct items with the same key.

A live Memory Embed binds both Source Context identity and Memory identity. Its
meaning is live ownership-following, while a Reference is the immutable form.
Move therefore freezes the complete ordinary local direct graph and applies
one of two normal dispositions:

- `RETARGET` is the default. It atomically rewrites every local inbound live
  Embed to the new owner while preserving the Embed item's UID and order.
  `--retarget-links` remains accepted as a compatibility spelling but does not
  alter the default. A Target-owned inbound Embed is rejected because
  retargeting it would create a forbidden self-link; remove that Embed first or
  choose Break.
- `BREAK`, selected by `--break-links`, deliberately leaves existing live
  Embeds bound to the old Source identity. They become dangling after Move and
  the receipt reports their exact count.

The application retains the typed `BLOCK` value only for compatibility with
already constructed internal requests; no current CLI, TUI, Python, agent, or
MCP route chooses it by default. A normal Move that cannot write one known live
Embed owner fails the complete Store batch before its first durable write.

Immutable Memory snapshot References never change. Cross-Profile, granted, or
concealed query-only links do not enter Move's local graph and are not inferred
as writable transfer targets.

## Atomicity, protection, and history

Copy binds every selected Source and the Target through publication. Local
Sources use ordinary Store locks; granted Sources additionally retain the
registry and exact authority record locks through local Target publication.
Move binds the complete scanned local graph so a new or changed inbound Embed
cannot race the reviewed link policy. The Store locks affected Contexts in
deterministic name order, validates all record digests and write-protection
rules before the first write, then publishes one checkpoint per affected
Context with exception rollback.

Every checkpoint in one operation carries the same generated operation UID,
plan digest, complete affected-Context membership, UID mapping, placement, and
policy. Command history groups those checkpoints as one Copy or Move unit.
Undo and Redo therefore restore Source removals, Target additions, and any live
Embed retargets together rather than exposing a half-moved state. Durable crash
journaling remains the same deferred boundary as the Store's existing
multi-Context command batch primitive; exception atomicity is implemented.

Write protection remains authoritative at Store commit. Copy changes only the
local Target, while Move changes every Source owner, Target, and RETARGET link
owner. Copy's granted Source is read-only and therefore does not require a
cross-Store write transaction. Move remains ordinary-local: deleting an
authority-owned Source would require explicit `DELETE` plus a durable
cross-Profile transaction journal and recovery protocol, neither of which is
inferred from `READ` or `EXPORT`. A detected granted Move fails with that
specific boundary and directs the caller to Copy first, then Move the new local
Memory.

## Callable and presentation boundaries

CLI, public Python, agent, and MCP routes enter Copy through
`memcommit.application.operations.copy` and Move through
`memcommit.application.operations.direct_changes.move`. Both ports subclass the shared
`memcommit.application.operations.copy_and_move.runtime.MemoryStoreCopyAndMovePort`
kernel. Typed values remain shared, while operation ordering and receipt
validation stay independently owned. Machine routes do not parse terminal
output and report that no semantic provider was used.

The console surface nevertheless has two command owners. Copy's grammar,
Grant-aware setup, execution handoff, and fresh-UID receipt live under
`adapters.console.commands.copy`; Move's grammar, local-owner setup, link
policy, execution handoff, and mixed-effect receipt live under
`adapters.console.commands.direct_changes.move`. They share only the direct-Memory selection,
Target-gap placement, editable exact-command, common operand, and placement
receipt mechanics under `adapters.console.coordination.copy_and_move`. The former
combined CLI module and operation-specific TUI package are removed without
facades. This keeps Help operations navigable by their public names without
duplicating one workbench or inventing a generic Transfer operation.

Copy is presented with the shared ADD color because it creates ordinary Target
Memories. Move is deliberately not assigned one action color: it is a mixed
REMOVE-plus-ADD effect, so its receipt colors only those two shortest typed
tokens. Plain and no-color output retains the same labels and ordering.

The TUI intentionally reuses Embed's full-screen source/target/placement and
compact exact-command grammar. Reference's larger explanatory To Do report was
rejected here because Copy and Move already expose their complete mechanical
effects in the exact command and final typed receipt; duplicating that report
would make the first screen denser without adding a distinct review boundary.

## Deliberate limits

- Copy and Move do not accept MemoryRef, snapshot Reference, query view, or
  embedded Context rows as Source Memories. Copy alone accepts exact direct
  ordinary Memories reached through an authorized READ Grant.
- Move does not implement same-Context reordering.
- Version 1 has no recursive Context scope, content filter, stdin locator file,
  granted Move, granted Target, or new-Target creation. Granted Copy is a
  read-only cross-Profile Source followed by one local Target write, not a
  cross-Profile ownership move.
- Copy does not retain a structured Source relation in the Memory model; its
  provenance is the operation checkpoint and UID mapping.
- Move retargets only ordinary local live Memory Embeds. A later cross-Profile
  ownership protocol must define authority and revocation separately.
