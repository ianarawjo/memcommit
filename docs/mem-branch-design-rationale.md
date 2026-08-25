# Mem Branch design rationale

## Motivation

Task 1 study runs exposed two valid Branch expectations. Branching one Context
can intentionally retain its embedded children as live references, while
branching a hierarchy is expected to create an independently editable copy of
that hierarchy. The old command implemented only the first, shallow meaning.
Branching a Root with no direct Memories therefore appeared successful but
left every meaningful descendant attached to the Source hierarchy.

Branch now makes the Source range explicit:

```text
THIS CONTEXT ONLY
INCLUDE DESCENDANTS
```

The equivalent explicit spelling defaults to compatibility behavior:

```bash
mem branch NEW --source-root-only
mem branch NEW --source-descendants
```

Bare Branch now exposes that same request through the shared compact Endpoint
Setup used by Meld. Only the persistent Source row, require-new target row,
exact command review, and footer remain visible. Source and parent catalogs
open transiently through `BROWSE` and `BROWSE PARENT`; they no longer reserve
the unused remainder of a 180×52 terminal.

```text
 MEM BRANCH · CHOOSE SOURCE AND NEW CONTEXT
› FROM › practice          [ BROWSE ] CURRENT [   INCLUDE DESCENDANTS ]
  TO   › practice/branch   [ BROWSE PARENT ] NEW · CREATE ON START
 COMMAND · RUNNABLE · ENTER TO APPLY
 mem branch practice/branch --from practice --source-root-only
```

The single `BRANCH` shape is not rendered as a MODE row. A mode selector is an
interaction only when an operation has multiple shapes; the stable mode UID
still exists in the typed draft.

## Operation ownership

Branch is now owned by the focused `memcommit.operations.branch` package.
`application.py` owns the terminal-independent `BranchRequest`, the exact or
lexical-subtree Source-to-target name plan, the publication port, and receipt
validation. The request deliberately carries the local Context catalog frozen
at command start: re-listing the namespace after an interactive setup would
silently adopt a descendant created while the picker was open instead of
letting the Store reject the reviewed Source range as stale.

`runtime.py` owns the `MemoryStore` composition. It loads the planned Sources
and their checkpoint histories, asks the domain operations to allocate fresh
Context and Memory identities, constructs the complete Context and Memory
lineage bindings, and publishes them through `create_branch_contexts`. That
Store call remains the owner of graph locks, Source/history/current CAS checks,
target collision checks, rollback, receipts, and whole-tree Undo/Redo. The
application layer validates that the published Source-to-target mapping and
selected current root exactly match its plan; it does not duplicate Store
transaction mechanics.

`memcommit.commands.branch` is consequently only the Typer and optional TUI
adapter: it resolves flags and relative Source syntax against the command-start
current Context, obtains an interactive selection when needed, invokes the
operation, and renders the receipt. `mem checkout -b` continues to call that
same adapter, so its shallow compatibility default is unchanged. There was no
previous public `branch_application` or `branch_runtime` module to preserve as
a facade.

Branch remains separate from direct-Memory Copy and Move. Those operations
transfer selected direct Memories into an existing local target; Branch
requires a new Context root, may clone a complete lexical subtree, projects
checkpoint history and internal pointers, changes the current Context, and
owns one recoverable multi-Context command. Shared lineage and transaction
mechanics stay in domain and Store components rather than making either
operation package depend on the other.

This relocation intentionally changes no visible command, setup screen,
authority rule, identity rule, checkpoint receipt, transaction boundary, or
route classification. Because the terminal states are unchanged, the existing
ordered TUI capture set remains the applicable visual evidence and is not
regenerated for this ownership-only change.

## Compact setup and shared component boundary

Branch's interface adapter lives under
`memcommit.interfaces.tui.operations.branch`. It owns the A/B role labels,
local-only availability, require-new validation, exact command review, and the
typed `BranchEndpointSelection`. The command-layer `branch_dialog` remains a
thin compatibility translation to `BranchCreationReceipt`; it no longer owns
tree rendering or endpoint focus mechanics.

The operation-neutral compact Endpoint Setup now supports a new-only role whose
Context catalog is a parent locator. Selecting a parent reparents only an
untouched suggested name. `ContextNameDraftState` records the first direct
edit, after which Source changes and parent browsing preserve the complete
person-authored target. This keeps the same ownership rule used by Init and
Save Location instead of rebuilding it in Branch.

The shared component also accepts an operation-owned new-name suggester. When
A changes, Branch refreshes `<A>/branch` only while B is untouched. Other
operations can reuse that dependency without importing Branch. Existing
endpoint selection, descendant reach, exact input, transient catalog, focus,
and exact-command rendering remain common controls.

The exact review uses a newly explicit Source form:

```text
mem branch NEW --from SOURCE --source-root-only
mem branch NEW --from SOURCE --source-descendants
```

`--from` is an existing ordinary Context locator and therefore resolves `.`,
`..`, `./...`, and `../...` once against the command-start current Context.
The new target remains a canonical new identifier and is never passed through
the existing-Context resolver. Existing `mem branch NEW` behavior is unchanged:
it still uses the captured current Context as Source. The Branch receipt
already retained `source_root`, so Undo and Redo can now render the complete
reproducible command with `--from` rather than depending on whichever Context
is current later.

`--source-only` remains accepted as a compatibility alias for the canonical
`--source-root-only` spelling.

## Exact Branch compatibility

`THIS CONTEXT ONLY` retains the existing contract. It creates one new Context
identity, copies each direct Memory value into a new independently owned
occurrence with a fresh Memory UID, retains Memory and query references, and
carries embedded Contexts as live references. Only the selected Source history
is inherited. Existing scripts and `mem checkout -b NEW` therefore remain
shallow unless descendant scope is requested explicitly; their copied Memory
selectors no longer collide with selectors in the Source merely because the
Branch exists.

## Lexical-subtree Branch

`INCLUDE DESCENDANTS` freezes the selected local Source root and every
materialized lexical descendant. It does not follow an arbitrary embedded
Context outside that namespace. Every Source name maps by suffix:

```text
source              -> experiment
source/facilities   -> experiment/facilities
source/routes/live  -> experiment/routes/live
```

Each target Context receives a new Context UID because the hierarchy must be
independently editable. Each direct Memory also receives a fresh target UID;
identity denotes one writable occurrence, not an ancestry label. An embedded
Context or MemoryRef targeting a member of the frozen Source set is rewritten
to the corresponding target name, new Context UID, and new target Memory UID.
Pointers outside the selected set retain ordinary shallow Branch live-reference
semantics. Query-only Context pointers are never treated as lexical hierarchy
edges.

The same internal-pointer rewrite applies to inherited checkpoint snapshots,
their `command_before` frames, and nested checkpoint-log snapshots. Otherwise
a later Revert could silently reconnect a branched Root to an original Source
child even though the current Context records were independent.

## Undo and Redo lifecycle

Branch creation is one recoverable command, not merely a copy followed by a
current-Context switch. Immediately after either an exact or subtree Branch,
`mem undo` cancels every Context created by that Branch as one unit and leaves
the Source unchanged. `mem redo` restores the exact archived target records,
Context UIDs, inherited checkpoint histories, and internal subtree mappings.
It must not call Branch again against a Source that may have changed since the
original command, because that would create new identities and a different
result under the same history action.

Every target receives one direct automatic Branch checkpoint after its Source
history is copied. The shared version-1 `branch_tree` receipt freezes:

- one operation UID and the complete Source-to-target Context membership;
- the Source and target roots plus exact-versus-descendant scope;
- every Source and target Context UID and canonical name; and
- the current Context value observed before Branch selected its target root.

Its sibling version-1 `memory_lineage` receipt uses the same operation UID and
records one exact edge for every direct Memory copied at the Branch boundary:

```text
(source Context UID, source Memory UID, source content digest)
    ->
(target Context UID, target Memory UID, target content digest)
```

The Store derives and validates the complete mapping while all Source and
Target records are locked. A subtree Branch repeats that complete edge set on
every target checkpoint, while the checkpoint's own post-image authenticates
the target occurrences it owns. This repetition is deliberate: reverting a
Root checkpoint may need to retarget a live MemoryRef into a sibling target
Context without opening that sibling as mutable state.

Inherited checkpoints are lineage, not evidence that the target existed
before Branch. Command-history reconstruction may assign an absent target
pre-image only to an owned automatic Branch checkpoint whose complete receipt
validates. Every target checkpoint shares the same command membership, so a
partial recursive Undo or Redo is rejected rather than exposed as separate
Context actions. The additional direct Branch checkpoint intentionally raises
the target's physical checkpoint count by one and makes the creation boundary
visible ahead of its inherited history in Log and Status.

Trace consumes both validated receipts instead of treating every copied Source
checkpoint as evidence that Branch was unrecorded. For each direct Memory in
the target post-image it emits one recorded `BRANCHED` event from the Source
occurrence UID to the fresh target occurrence UID. Equal before/after content
therefore means copied ancestry without an Edit. A recursive Branch repeats the
complete command membership on every target, while each per-Memory Trace
projects only its exact Source-to-target route. Receipt-free legacy histories
retain one warning per unexplained Source owner and do not receive a fabricated
Branch event.

Merge reads retained same-Store Branch and Merge lineage as a graph. It follows
that graph transitively, so `main -> feature -> experiment` can still identify
the one current `main` occurrence related to an `experiment` Memory. Equal
content is `UNCHANGED`; divergent content is a normal `CONTENT_DIVERGENCE`;
`TAKE SOURCE` replaces the target value while preserving the target occurrence
UID. A genuinely new Source Memory receives a fresh Target UID, and the Merge
checkpoint records that new edge. Repeating the Merge therefore recognizes the
published target occurrence instead of appending another copy. One-to-many or
many-to-one structural mappings fail closed; semantic combination remains
Meld's separate contract.

Copied Source checkpoints remain authentic historical evidence and retain
their Source-side Memory UIDs. Revert of an inherited checkpoint projects its
Memory values and internal MemoryRef targets into the Branch occurrence
namespace through validated lineage before publication. The Revert receipt
retains the original selected snapshot for history and records the exact
projected restoration post-image separately, so Undo, History, and Trace all
describe the state that was actually written.

Undo freshness-checks every target against the recorded creation post-image
and validates deletion protection before moving any target. It then moves the
exact Context records and checkpoint directories into private command-history
archives and records one shared Undo receipt. Redo requires every destination
name to remain available, moves those same records and histories back, and
records one shared Redo receipt. A newly created Context with the same name is
never overwritten or adopted.

Branch initially selects its target root. Undo restores the frozen prior
selection only while the current pointer still names one of the Branch targets;
if the person has since switched elsewhere, that unrelated selection is
preserved. Redo similarly selects the target root only when the current pointer
still equals the frozen pre-Branch value. The private archive and restoration
checkpoints are recovery metadata, not newly visible replacement Contexts.

Checkpoint-producing work performed after Branch remains newer in the global
command stack and must be undone first. The lifecycle archive covers the
created Context records and their checkpoint histories; it does not claim
arbitrary read-only caches created later as part of the Branch command.

## Transaction boundary

One subtree Branch is one store command. Before publication it rechecks:

- the complete lexical Source membership;
- every Source Context UID and record digest;
- every Source checkpoint-history digest;
- every require-new target path; and
- the command-start current Context.

The store holds the graph lock, all Source and target Context locks, and the
current-state lock through creation, history publication, selection, and
exception rollback. A new or removed descendant makes the reviewed Source
range stale. A collision at any mapped target fails before the first write.
An exception after publication begins removes every Context created by that
Branch while retaining pre-existing namespace descendants.

Undo and Redo hold the command lock, an exclusive Context-graph lock, and all
target Context locks across validation and archive movement. Every record and
checkpoint-directory pair moves together; a failure restores all previously
moved pairs, removes provisional restoration checkpoints, and preserves the
pre-operation current pointer. Recursive recovery therefore has the same
all-target exception boundary as recursive creation.

This prototype guarantees cooperative-process and exception atomicity. Like
the existing multi-Context update and rename paths, it does not yet provide a
durable crash-recovery journal for a host failure between filesystem writes.

## Rejected alternatives and limits

- Making every Branch recursive was rejected because it would change the
  established meaning of scripts that intentionally branch one record while
  keeping live embedded Contexts.
- Following embedded edges recursively was rejected because lexical placement
  and embedded graph traversal are independent axes. It could pull unrelated
  Contexts into the result and make a bounded Source range difficult to review.
- Preserving Context or Memory UIDs was rejected because two independently
  editable ordinary occurrences must not share one writable identity. It also
  makes a bare UID selector unexpectedly ambiguous immediately after Branch.
  Operation-owned checkpoint lineage provides ancestry without conflating
  addresses.
- Copying checkpoint bytes unchanged was rejected for subtree mode because
  future Revert would restore Source-side internal pointers.
- Re-running Branch during Redo was rejected because it would allocate new
  Context UIDs and copy the Source's current state instead of restoring the
  reviewed historical result.
- Treating copied Source checkpoints as the target's pre-Branch history was
  rejected because it would make Undo edit inherited lineage or consume an
  older Source command instead of cancelling target creation.
- Inferring Branch from equal Memory text or a changed Context header was
  rejected because equal wording is not lineage. Trace requires the validated
  owned `branch_tree` receipt before suppressing legacy warnings or emitting a
  recorded Context transition.
- Keeping both Context trees permanently expanded was rejected because Branch
  has only two endpoints and one range choice. Persistent empty canvas made a
  creation dialog look like a session workbench; transient catalogs preserve
  the complete frozen choices without hiding the compact reviewed plan.
- Treating a B parent Browse row as an existing target was rejected because an
  empty existing Context is still owned durable state. Parent selection may
  reposition an untouched exact name but can never change the require-new
  materialization contract.

The target root and every mapped descendant must be new. Branch does not merge
into an existing target hierarchy, copy derived analysis/session artifacts, or
promise synchronization with later Source changes. Lineage is recorded only
for Memories present at the Branch boundary. Reverting a Branch to an inherited
checkpoint containing a Memory that had already disappeared before Branch has
no target occurrence to restore and fails closed instead of resurrecting the
Source UID. Legacy receipt-free same-UID Branch histories remain readable and
retain a narrow Revert compatibility fallback, but new Branch and Merge
operations do not create such duplicate writable identities. Cross-Profile or
Grant-derived Merge does not publish local lineage, because its authority and
disclosure boundary is different from ordinary same-Store ancestry.
