# Semantic history search, selection, and restoration

## Decision

History is not only a list of Context checkpoints. The searchable model has
three distinct projections:

| Projection | Meaning | Restorable directly? |
| --- | --- | --- |
| Context checkpoint | one retained direct Context snapshot and its operation metadata | only while active in the physical checkpoint log |
| versioned Memory state | one directly owned Memory's content at a reconstructable state | only through an active checkpoint containing that occurrence |
| Memory transition | an add, edit, removal, or restoration edge between reconstructable Context states | no; it is an event boundary |

This model is shared by the semantic and static `mem log` routes, semantic
checkpoint selection for `mem revert`, and the state comparison used by
`mem undo`. Sharing the model prevents each history operation from inventing
a different meaning for “before,” “after,” “latest,” or “the previous state.”

Log and Trace additionally share `memcommit.temporal_history` for direct-Memory
delta extraction. The common layer compares adjacent direct frames by UID and
returns only `CREATED`, `EDITED`, and `REMOVED`. A removal and addition in the
same checkpoint remain independent changes: only recorded or deterministically
reconstructable provenance may connect distinct UIDs as `SPLIT`, `ABSORB`, or
translation lineage. Log may display those enriched edges, while Trace follows
them from one selected Memory and filters out unrelated changes.

`mem search` always searches the frozen current readable Memory graph. Query
words such as `before`, `after`, `during`, `when`, `latest`, `동안`, or `이후`
remain ordinary semantic content; they never switch the command to checkpoint
history or expand the disclosed evidence. Natural-language History Search is
entered explicitly through `mem log QUERY`. This operation boundary keeps a
sentence about current content from silently enumerating retained checkpoints
and makes the source of a historical answer visible in the command itself.

## Reconstructable history

An active Context checkpoint is the authoritative stored restoration address.
An archived checkpoint recovered from `log_snapshot` remains searchable but is
not directly restorable. Each checkpoint snapshot is projected into directly
owned Memory states. Adjacent reconstructable states produce transitions:

- a new Memory UID produces an addition;
- the same Memory UID with different content produces an edit; and
- a previously present Memory UID that is absent produces a removal.

The corresponding searchable event kinds are `CREATED`, `EDITED`, and
`REMOVED`. A reconstructed revert edge uses `RESTORED` for every Memory change
caused by restoring the target snapshot, so it is not misrepresented as a new
ordinary authoring action.

An uncheckpointed live state may be shown as a current history gap, but it is
not assigned a fabricated checkpoint UID and is not a restoration target.
Historical search must distinguish “present now but not checkpointed” from a
retained version that can actually be restored.

All Memory changes represented by one checkpoint are temporally tied. Their
serialized order is presentation order, not evidence that one happened before
another. Consequently, “after the shuttle notice changed” means a later
checkpoint, not another change recorded in the same checkpoint. Operations
that record multiple owner checkpoints may be treated as one logical tie only
when their shared session metadata and operation digest prove that
relationship; timestamp coincidence alone proves nothing. This logical tie
does not imply crash-atomic storage.

## Anchor and relation queries

A temporal request is interpreted as an anchor, a host-verifiable relation,
and an optional selection rule:

```text
semantic anchor
→ PRESENT / ABSENT
  or WHILE_PRESENT / WHILE_ABSENT
  or BEFORE / IMMEDIATELY_BEFORE / AFTER / IMMEDIATELY_AFTER
→ RANKED / EARLIEST / LATEST / ALL
→ checkpoint, Memory-state, or transition results
```

`PRESENT` and `ABSENT` qualify state-shaped results against a selected Memory
lineage. `WHILE_PRESENT` and `WHILE_ABSENT` qualify Memory transitions using
the state immediately before each transition. `BEFORE` and `AFTER` are strict,
same-Context relations; their immediate variants require the adjacent state or
change. `RANKED` preserves the provider's validated semantic order after local
filtering, `EARLIEST` and `LATEST` reduce locally per Context while retaining
same-step ties, and `ALL` retains every locally qualifying subject up to the
command's result limit.

For example:

- “셔틀 공지가 아직 있을 때 마지막으로 업데이트된 메모리” first
  identifies the shuttle-notice Memory lineage, derives the retained interval
  in which that notice is present, restricts candidate transitions to that
  interval, and selects the latest directly changed Memory.
- “셔틀 공지 변동 이후에 바뀐 것들” identifies the relevant
  shuttle-notice transition and returns direct Memory transitions at later
  checkpoints. Changes tied to the anchor checkpoint are not classified as
  later changes.
- “X 직전 버전” resolves to the predecessor checkpoint of the matching
  transition; “X 직후 버전” resolves to the resulting checkpoint.
- “X가 없던 마지막 버전” filters retained states in which X is absent and
  then chooses the most recent qualifying checkpoint.

If an anchor is ambiguous, the result remains a candidate set for inspection.
The host must not turn the provider's confidence or the existence of only one
returned result into an implicit mutation.

## Provider and host responsibilities

The semantic provider receives bounded projections under invocation-local,
opaque aliases. It may return only a strict plan made from enumerated aliases
and allowlisted result kinds, relations, and selection rules. It does not
receive authority to return a durable checkpoint UID, construct a command, or
choose arbitrary stored paths.

The provider may interpret which direct Memory content or transition is the
semantic anchor. The host remains responsible for:

1. validating every returned alias against the exact local corpus;
2. resolving aliases back to canonical local identities;
3. computing checkpoint adjacency and Memory-presence intervals;
4. applying the requested temporal relation and tie rules;
5. applying `EARLIEST` or `LATEST` reduction, or retaining `RANKED` or `ALL`,
   locally; and
6. rendering canonical local content and checkpoint UIDs.

This division treats natural-language interpretation as semantic ranking, not
as temporal authority. A provider cannot claim that one event occurred after
another when the retained checkpoint graph does not support that relation.
Malformed, unknown, cross-kind, or relation-incompatible plans fail closed.

Provider interpretation is still heuristic. The prototype can validate the
structure and chronology of a plan, but it cannot formally prove that the
phrase “셔틀 공지” denotes the intended Memory. The visible candidates and
their evidence are therefore part of the interaction contract.

## Command contracts

### `mem search`

```text
mem search
mem search "parking information"
mem search "notices that apply during construction"
```

A query-less invocation in a TTY opens the process-local Find search
workbench with a blank, focused one-line query. The person may check multiple
readable Context roots and independently choose whether to include lexical
namespace descendants and follow explicit embeds. It sends nothing to a
provider until a nonblank query is submitted. Outside a TTY, a query remains
required so scripts never wait for an interactive selector.

Every query keeps the current-state Search privacy boundary. Search defaults
to the selected Context only; `-r/--recursive` adds every materialized ordinary
namespace descendant and reachable explicit embed. Time-oriented wording can
match a current Memory that contains that wording, but it cannot return a
version, transition, or checkpoint.

`agent-records/docs/screenshots/search-current-only-temporal-20260823/` records the complete
interactive boundary at `180 × 52`: entry, time-oriented query text, ordinary
Search execution, a current Memory result, staged checking, and read-only close
verification. The color PTY stream confirms that removing implicit History
routing did not introduce a parallel or visually hidden Search mode.

### `mem log`

```text
mem log
mem log "the last version before the detour ended"
mem log --memory MEMORY
mem log --memory MEMORY --context CONTEXT
mem log --manual
mem log --plain
```

`mem log` is a terminal-independent report. With no target it prints the
current Context's retained checkpoint rows; `--context` prints only the
resolved explicit Context. It never opens a Context selector or checkpoint
picker, so the same invocation has the same interaction contract in a TTY,
through redirection, and in automation. `--manual` filters that fixed report to
manually created checkpoints, while a natural-language query prints the
locally resolved checkpoint matches instead of opening the matches in a
picker.

`--memory` selects the Memory-lineage projection of the same retained Context
history. It accepts a current or historical direct-Memory UID or unambiguous
prefix and prints the same bounded vertical lineage document as
`mem trace MEMORY --plain`. Its existing `--limit` option bounds the newest
visible operations and states the exact older count when anything is omitted.
Each lineage block begins with the same typed compact History row as ordinary
Log—action, named UID badges, timestamp, and summary. Direct Add/Remove stop at
that row because the summary already names their only content-bearing endpoint;
Edit, restoration, and structural or mixed operations add Trace's forward
`−`/`+` diff. Direct Edit omits its generic summary so that diff alone explains
the content change. Compact output does not repeat an effect/evidence suffix; verbose
Trace expands every diff and exposes provenance as a separate `Lineage:`
detail. Both adapters consume the same adapter-neutral row segments; this is
shared presentation structure, not merely two strings that happen to look
alike. Trace does not add separate `NOW` or `ORIGIN` bands around those rows.
`mem trace MEMORY` remains the discoverable interactive inspection route in a
TTY; `--all` is the explicit complete human-readable route, while JSON remains
complete independently of presentation bounds. The two commands share
retained-history access, direct-Memory delta extraction, operation grouping,
and ANSI-free projection rather than recursively invoking one CLI command from
the other.

`--plain` remains accepted as a compatibility no-op so existing scripts do not
break merely because static output became the only Log presentation. Detailed
interactive checkpoint and lineage inspection remains available through
`mem diff`, `mem trace`, and the reviewed `mem revert` flow; Log itself owns no
terminal UI.

### `mem diff`

```text
mem diff
mem diff CONTEXT
```

In a TTY, bare Diff snapshots the current Context and opens that Context's
checkpoint transitions directly. It does not display the Profile-wide Context
tree or allow a second Context choice inside the session. An explicit existing
Context operand resolves once against the same command-start current snapshot
and opens that exact Context without changing the global current pointer.

This follows List's requested-scope rule. Showing siblings and unrelated roots
in gray would still expose Switch navigation inside a command whose subject is
already known. Removing those rows makes the heading, visible history, and
keyboard scope agree. Revert now follows the same current-or-explicit target
rule; its mutation safety review is the exact checkpoint, complete revision
result, history policy, and final Apply rather than a second Context choice.

The exact route reads the ordinary name catalog only to validate the resolved
target. It opens checkpoint and Context records for that target alone; it does
not scan unrelated Context histories merely to build annotations for a tree
that will not be shown.

Diff reuses the shared full-screen Viewer/Items history session. Current-only
scope does not imply a compact viewport: omitting the Profile-wide Context
tree removes an unrelated navigation choice, while the selected Context's
directional detail still benefits from the same large inspection surface as
other history workbenches. The standard alternate-screen buffer also restores
the preceding terminal after Diff closes.

The focused Viewer footer reports the logical change under its cursor as
`CHANGE n/total`. Renderers provide change-start line anchors, so wrapped
Memory prose and multi-line reasons do not turn the indicator into a misleading
raw line count; `Home` resolves to the first change and `End` to the final
change. Details and histories remain scrollable and are never truncated. Full
checkpoint UIDs, directional details, escaping, read-only behavior, and exact
explicit-Context resolution are unchanged.

The ordered `180×52` PTY evidence under
`agent-records/docs/screenshots/mem-diff-current-fullscreen-20260820/` records current entry,
checkpoint navigation, Viewer focus, exact-operand entry, close receipts,
final read-only verification, and the entry/Viewer/End states of one
150-change Update fixture.

### `mem revert`

```text
mem revert
mem revert --context task-1/participant
mem revert 2f98a740
mem revert 2f98a740 --context ../participant
mem revert "the version before the shuttle notice was removed"
mem revert --keep
mem revert 2f98a740 --discard-newer
```

An exact checkpoint UID or unambiguous UID prefix remains the deterministic
command-line restoration path. Its optional `--context/-c` operand uses the
shared existing-Context locator and freezes the active Context base once, so
relative spellings such as `../participant` cannot change meaning before the
write.

In a TTY, operand-free Revert captures the command-start current Context once
and opens that exact Context's History workbench directly. `--context` resolves
one existing Context against the same snapshot and opens it without switching
the global current pointer. Siblings and unrelated roots are not alternate
targets inside this operation. A Context with no checkpoints still opens an
explicit `0/0` history screen, but closing it ends Revert instead of broadening
the mutation scope. A readable Grant is not mutation authority.

Every retained checkpoint remains an independently selectable exact version.
Repeated Update or restoration operation identities are not folded, and a
creation-time Init and Atomize remain separate when they persisted separate
snapshots. The full checkpoint UID is the process-local selection receipt even
though Items shows only its compact prefix.

Viewer uses the shared complete revision renderer described in
`agent-records/docs/checkpoint-revision-diff-design-rationale.md`. It shows what the selected
checkpoint's command changed relative to its own predecessor and the complete
direct-item result at that revision; it no longer labels a current-to-target
change list as `RESTORE IMPACT`. `KEEP ALL` is the default History policy.
Enter on an Items row checks that exact full checkpoint UID and moves directly
to an editable `PROPOSED COMMAND` such as
`mem revert UID --context NAME --keep`. The History choice remains visible and
stages either `KEEP ALL` or `DISCARD NEWER`; changing it rewrites the command,
while editing a valid command UID or explicit policy moves the checked Items
row and History choice back to the same state. The editable selector may be a
full UID or any prefix that uniquely identifies one checkpoint in the frozen
review; Apply resolves it to the full UID receipt, while an ambiguous prefix
remains invalid. History renders only the two policy labels because their
meaning is already carried by the explicit command flags and review effects.
`--keep` remains an explicit
compatibility spelling for the default, and `--discard-newer` is the deliberate
destructive-retention route. Only Enter on the valid command returns the local
receipt and permits the ordinary store restoration path. The selection, policy
change, command edit, and Apply are process-local until that last action.

The ordered `180×52` PTY evidence under
`agent-records/docs/screenshots/revert-editable-command-20260823/` records the current
keep-all default, direct Items-to-command transition, both synchronization
directions including a unique UID-prefix edit, exact Apply, durable receipt, and
read-only post-Revert
verification. The earlier
`agent-records/docs/screenshots/revert-revision-result-20260821/` set remains the focused
complete-revision Viewer baseline; its former policy/Apply frames are
superseded by the 2026-08-23 set.

A natural-language selector keeps its current- or explicitly selected-Context
scope and opens the same staged Revert workbench after semantic candidate
reduction. The semantic phase produces candidates only and never chooses or
mutates by itself.

A natural-language query never mutates directly, even if the provider returns
one candidate. The current non-TTY command refuses semantic selection and
points the caller to `mem log "QUERY"` followed by an exact UID. An omitted
selector outside a TTY is also an error. This avoids an implicit “select the
first result” policy in scripts.

Before the History screen opens, the adapter freezes the canonical Context
name, Context UID, canonical Context digest, digest of the complete visible
checkpoint list, and initial history policy. The final receipt carries the
exact selected UID and reviewed policy. The store then acquires the Context
write lock, reloads the Context and checkpoint history, rechecks all three
freshness values, and resolves the exact target before changing anything. A
save, checkpoint, revert, or checkpoint-history copy through the public store
API participates in the same Context lock discipline, so it cannot change the
reviewed frame between validation and mutation.

### `mem undo`

```text
mem undo
mem redo
```

Undo and Redo are global command-oriented shortcuts, not aliases for “restore
the current Context's adjacent checkpoint.” Navigation does not change their
target. For example, `mem update --to ../to` may leave the current pointer on
the source while changing one or more target owners. The next `mem undo`
selects that Update command and restores its target owners; it does not inspect
the current source merely because a later `mem switch` selected it.

The stack is reconstructed from retained direct-Context checkpoints. One
ordinary automatic checkpoint is one command unit. Checkpoints created by the
same semantic Update share `update_session_uid` and `operation_digest`, so all
of its affected owner Contexts form one unit even though each Context retains
its own checkpoint. New Update checkpoints also repeat the complete
`command_contexts` membership list, so a missing owner receipt fails closed
instead of making a partial Update look like a smaller valid command.
Inherited branch checkpoints establish the branch's base state but do not
become newly entered commands. Initialization, manual/no-op checkpoints, and
checkpoints whose direct state did not change are likewise not placed on the
stack.

Revert and command Undo/Redo share the narrow direct-snapshot restoration
primitive: it normalizes the target under the live Context UID/name, attaches
the same compare-and-set digest, enforces write protection through the common
locked save path, and preserves opaque direct pointers. Their history policies
remain deliberately separate. Revert selects one arbitrary Context checkpoint
and may replace its visible log; Undo/Redo selects one global command unit,
may restore several owners and companion semantic artifacts, and always
appends shared restoration receipts. Neither CLI recursively invokes the
other.

New automatic checkpoints retain a top-level `command_before` direct snapshot.
This makes the exact pre-image available even when a programmatic caller had
no earlier baseline checkpoint. Older histories remain usable: their pre-image
is reconstructed from the preceding effective state, including the implicit
target state of a retained Revert receipt. The post-image remains the ordinary
checkpoint snapshot. Neither image resolves MemoryRefs, embedded Contexts, or
query-only sources.

`snapshot` and `command_before` are the shared future-restorable Context-frame
roles of one persisted checkpoint record. Revert `log_snapshot` values recurse
through the same complete record shape. Identity-preserving graph operations
must traverse those roles through `memcommit.checkpoint_frames` rather than
keeping operation-local field inventories. This boundary matters even though
Revert and command Undo/Redo retain distinct history policies: a renamed
post-image can make Revert succeed while an unmigrated pre-image makes the
global command chain fail closed.

Legacy records already split by that historical Rename defect are repaired
only through `scripts/repair_rename_checkpoint_history.py`. Its default is a
read-only plan. Apply requires the exact reviewed plan digest, matching Rename
evidence and live UID ownership over the same frozen Context/checkpoint graph,
rewrites no prose or Context content, and
verifies complete Undo/Redo stack reconstruction before releasing its locks.
The reader does not silently normalize or ignore a mismatch because doing so
would weaken exact pre-image and CAS evidence for unrelated corruption.

Every successful Undo or Redo writes an automatic checkpoint in each affected
Context. Those checkpoints share a restoration receipt UID, direction, source
command-unit UID, source command name, and the complete affected Context
identity list. Replaying original-command and restoration receipts in time
order yields conventional LIFO undo and redo stacks. A newly entered recorded
command clears the redo stack; another Undo does not. `mem redo` therefore
reapplies the most recently undone unit, including all owners of an Update,
without rerunning a provider or regenerating a semantic plan.

Future checkpoint-producing commands take one store-wide command-order lock
outside their Context locks. Undo/Redo holds that lock while rebuilding the
stack, then takes every affected Context lock in deterministic name order. It
rechecks each stable Context UID and exact expected pre/post digest before the
first write. If any ordinary owner write fails, already-written Context files
and newly created restoration checkpoints are rolled back before the error is
reported. This provides exception atomicity for multi-Context Update undo and
redo, while retaining the prototype's documented lack of crash atomicity
across several files.

An uncheckpointed or externally modified Context is not silently swept into a
command Undo. If it no longer equals the selected command's expected post-image
(or pre-image for Redo), restoration fails without changing any affected
Context. This is preferable to undoing an older unrelated command or
overwriting an unrecorded concurrent change.

### Restoration receipts

The success receipt is action- and impact-oriented. A checkpoint UID and time
alone identify a storage boundary but do not tell a person what was reversed.
`mem undo` and `mem redo` therefore reconstruct a canonical effective `mem …`
command from retained checkpoint arguments and pair it with exact affected
Context and Memory counts. `mem revert` retains its more detailed confirmation
because selecting an older state is a separate inspection workflow. Receipt
and exact checkpoint identifiers remain secondary history/recovery details
rather than the primary explanation.

Impact is reconstructed from the two local direct-Context snapshots, not from
command arguments. This makes the receipt work for older checkpoints and for
commands whose metadata does not enumerate every change. A retained UID is
reported as added, edited, or removed in the direction the restoration just
performed. Direct Memory edits show `before → restored`; MemoryRef and Context
reference changes show pointer metadata without resolving or reading their
targets. Relative order is compared only among surviving direct items, so an
insertion or removal does not falsely report every shifted item as reordered.

`mem trace` remains the separate public interactive route for Log's read-only
Memory-lineage data projection. Its projection groups shared receipts into
newest-first inline diff blocks, links a restoration to its source operation,
and needs no secondary operation-selection surface after the Memory is known.
It is not used to choose or authorize Undo/Redo: restoration still requires the
complete command-unit pre/post frames described above, whereas a Trace
intentionally contains only the selected lineage's local effect.

Undo and Redo use a single-line terminal receipt containing only the source
action and affected Context and Memory counts with `+`/`~`/`-` effect totals.
Supported receipts reconstruct their canonical effective operands from frozen
checkpoint metadata, including Update's `--from` and `--to`, so they omit a
redundant affected-location list. Content-bearing Add/Edit operands and
Forget instructions and historical Integrate instructions use typed
placeholders: the action shape remains visible without repeating private text.
For a direct Memory Edit, Remove, or Chunk operand, the compact terminal
receipt projects the shortest collision-free prefix of at least eight
characters from the command unit's frozen single-Context pre/post catalog.
This projection never consults live current state. A multi-Context unit, a
legacy record without the relevant catalog, or an operand whose owning scope
cannot be reconstructed retains its persisted full UID. Exact-command review,
checkpoint metadata, structured interfaces, and durable identity continue to
use the full UID; compact prefixes are presentation only.
The Integrate receipt reconstructs a retired action and is not an executable
recommendation. Missing legacy operands fail down to
the recorded command name. Receipts do not repeat restored Memory content,
descriptions, receipt UIDs, or inverse-command guidance. Revert retains its
bounded detailed confirmation: at most twelve changed direct items are
expanded, with per-field preview limits and exact totals. Newlines, terminal
controls, bidi controls, and backslashes in displayed names or Revert content
remain escaped so data cannot imitate another receipt heading. Neither form
opens embedded Contexts nor resolves MemoryRefs or query-only sources. A future
unbounded or machine-readable restoration diff should be a separate explicit
command or output mode.

## Restoration and recoverability

The default Revert behavior keeps every checkpoint file active and appends the
pre-Revert Context state as a recovery checkpoint. `--discard-newer` is the
explicit alternative: it removes active checkpoint files newer than the
selected target after first recording that recovery checkpoint. The recovery
record carries a bounded `log_snapshot`, allowing the displaced local log to
be reconstructed with its displayed exact recovery command. History
enumeration may include records recoverable through this metadata rather than
pretending that the visible checkpoint directory is an append-only ledger.

Nested `log_snapshot` values are deliberately thinned to prevent recursive
growth. Therefore, “recoverable history” means the history reconstructable
from the currently retained checkpoints and their supported recovery
metadata. It is not an immutable audit log, and it is not permission to
restore an arbitrary intermediate Memory version. Restoration always ends at
an exact retained checkpoint boundary.

The default `KEEP ALL` choice, or the compatible explicit `--keep` spelling,
leaves every currently visible checkpoint file in place and appends only the
pre-Revert recovery checkpoint. This changes retention, not the restored
Context snapshot or the ability of command-unit Undo to reverse the Revert.

Discard is therefore not immediate unrecoverable erasure: the newer files
leave the active directory, but the new recovery checkpoint retains their
supported flattened metadata and the receipt spells the exact
`mem revert RECOVERY --discard-newer` reconstruction route. It is still not an
immutable archive. Nested snapshots are deliberately thinned, so a person who
must preserve every checkpoint as an independently active boundary should use
the keep-all default rather than relying on later recovery metadata.

Revert treats checkpoint snapshots as direct persistence records. It rebuilds
them without resolving embedded Contexts or MemoryRef targets, so an
unavailable pointer is restored rather than silently erased. The replacement
history is validated and prepared before destructive changes, every checkpoint
write uses atomic same-directory replacement, and an ordinary exception
restores the exact original Context and checkpoint bytes. This is exception
atomicity, not a durable multi-file crash transaction.

## Content and privacy boundary

Semantic history covers directly owned ordinary `Memory` values only.
Checkpoint snapshots may contain pointers, but historical search must not use
them as authority to open other stores:

- query-only source content is never opened or transmitted;
- a `QueryContextRef` contributes no hidden historical content;
- historical target content behind a `MemoryRef` is not resolved or loaded;
  and
- an embedded Context is not recursively treated as part of the containing
  Context's checkpoint snapshot.

Current-state `mem find` retains its separately documented handling of current
resolved MemoryRefs and public query-only Context names. That behavior must not
be generalized into historical target reads. A user may search the directly
owned history of the target Context only when that Context is independently
available and selected under ordinary access rules.

## Limitations and non-goals

- Natural-language anchor selection is provider-mediated semantic
  interpretation, not a formal query language or proof of entailment.
- Semantic version and transition search is limited to directly owned Memory
  content. MemoryRef targets, query-only sources, and remote wiki history are
  outside the corpus.
- A restore target must be an exact retained checkpoint. A matching Memory
  state or transition is evidence for choosing that checkpoint, not a
  separately restorable object.
- Context and checkpoint files use atomic per-file replacement and
  cooperative locking, not a durable transaction journal. A process or
  machine crash during log truncation, log restoration, or a multi-Context
  operation can still leave a partial local result.
- Checkpoint timestamps do not establish a causal total order across
  Contexts. Same-checkpoint changes are tied, and cross-Context ties require
  explicit shared operation metadata. Future commands share a global ordering
  lock; retained older histories whose multi-Context intervals overlap fail
  closed rather than guessing an order.
- Command Undo/Redo covers checkpoint-producing changes to existing ordinary
  Context direct state, including grouped semantic Updates and exact Reverts.
  It additionally covers the narrowly receipted Context creation performed by
  Sever: the absent Result and its checkpoint history live in a private command
  archive until Redo. Other lifecycle/navigation commands such as `init`,
  `branch`, `rename`, `delete`, or `switch` remain outside command Undo, as do
  unrelated Ground/session artifacts and shared publication. Semantic requests
  for a particular historical condition still belong to `mem revert "…"`,
  followed by explicit candidate selection.

These boundaries keep the first implementation useful for the study scenario
without presenting a local snapshot prototype as a complete version-control
or audit system.
