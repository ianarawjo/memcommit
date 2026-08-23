# Direct Memory Copy and Move design rationale

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

## Command contract

Both operations accept one or more direct-Memory locators in caller order:

```text
mem copy [CONTEXT:]UID... [--from SOURCE] [--into TARGET | --to TARGET]
mem move [CONTEXT:]UID... [--from SOURCE] [--into TARGET | --to TARGET]
```

A bare UID or prefix is resolved against one strict snapshot of every ordinary
local Context and must have exactly one direct owner. `CONTEXT:UID` chooses an
explicit owner. `--from SOURCE` applies one owner to every unqualified selector
and cannot be combined with a qualified selector. Source and Target relative
locators share the current Context captured once at command start.

The positional list and repeatable `--memory/-m` form are equivalent ordered
batch inputs but cannot be combined. Target defaults to the command-start
current Context. `--before` and `--after` select one exact Target direct-item
gap; omitting both appends the complete batch. Every selector, collision, gap,
Source binding, and Target binding is validated before publication.

In a TTY, bare Copy and Move open one full-screen setup shaped by the current
Embed workbench rather than a compact endpoint form. The Source frame extends
the shared direct-Memory selector to `MULTIPLE`; checked Memories are projected
in explicit check order, and a valid exact-command edit replaces that order
atomically. The Target frame composes the
shared Context tree with Embed's direct-item placement projection, so exactly
one movable `POSITION · n/total` line represents the current gap instead of a
duplicated BEFORE/AFTER row for every item. Neither operation adds a normal
policy frame: Copy has one fixed new-identity meaning, while Move follows live
Embeds unless Break is explicitly typed into the exact command.

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
reconciliation contract. That ambiguity belongs in a future explicit Branch
operation, not in ordinary Copy. Existing stores that already contain
same-UID Memories in different Contexts remain readable; this change does not
rewrite historical data, but Copy can no longer create another such pair.

Removing the field is an intentional callable-contract break. The strict
Memory-transfer agent schema advances to version 2 so a version-1 caller
cannot mistake the narrower Copy contract for the former policy-bearing one.

The checkpoint retains only Source/Target identities, UID mappings, placement,
the fixed `NEW_UIDS` invariant, and plan digest. It does not duplicate Memory
content into searchable command metadata because the Context pre/post images
already retain the exact values.

## Move identity and live links

Move preserves every selected Memory UID and content while changing its direct
owner. Target must be distinct from every selected Source owner, and no Target
direct item may already use a selected UID. Same-UID copies from different
branch Contexts cannot be moved into one Target because one Context cannot own
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

Immutable Memory snapshot References never change. Cross-Profile or concealed
query-only links do not enter the local graph and are not inferred as writable
transfer targets.

## Atomicity, protection, and history

Copy binds every selected Source and the Target through publication. Move binds
the complete scanned local graph so a new or changed inbound Embed cannot race
the reviewed link policy. The Store locks affected Contexts in deterministic
name order, validates all record digests and write-protection rules before the
first write, then publishes one checkpoint per affected Context with exception
rollback.

Every checkpoint in one operation carries the same generated operation UID,
plan digest, complete affected-Context membership, UID mapping, placement, and
policy. Command history groups those checkpoints as one Copy or Move unit.
Undo and Redo therefore restore Source removals, Target additions, and any live
Embed retargets together rather than exposing a half-moved state. Durable crash
journaling remains the same deferred boundary as the Store's existing
multi-Context command batch primitive; exception atomicity is implemented.

Write protection remains authoritative at Store commit. Copy changes only the
Target, while Move changes every Source owner, Target, and RETARGET link owner.
Version 1 accepts ordinary local Sources and one ordinary local Target only;
it does not infer Grant permissions for cross-Profile ownership transfer.

## Callable and presentation boundaries

CLI, public Python, agent, and MCP routes enter the same
`memory_transfer_application` contract and `MemoryStoreMemoryTransferPort`.
The application returns typed placements, UID mappings, plan digests, link
counts, and per-Context checkpoints. Machine routes do not parse terminal
output and report that no semantic provider was used.

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
  embedded Context rows as Source Memories.
- Move does not implement same-Context reordering.
- Version 1 has no recursive Context scope, content filter, stdin locator file,
  cross-Profile transfer, or new-Target creation.
- Copy does not retain a structured Source relation in the Memory model; its
  provenance is the operation checkpoint and UID mapping.
- Move retargets only ordinary local live Memory Embeds. A later cross-Profile
  ownership protocol must define authority and revocation separately.
