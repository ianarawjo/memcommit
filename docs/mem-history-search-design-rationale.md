# Semantic history search, selection, and restoration

## Decision

History is not only a list of Context checkpoints. The searchable model has
three distinct projections:

| Projection | Meaning | Restorable directly? |
| --- | --- | --- |
| Context checkpoint | one retained direct Context snapshot and its operation metadata | only while active in the physical checkpoint log |
| versioned Memory state | one directly owned Memory's content at a reconstructable state | only through an active checkpoint containing that occurrence |
| Memory transition | an add, edit, removal, or restoration edge between reconstructable Context states | no; it is an event boundary |

This model is shared by temporal `mem find`, interactive `mem log`, semantic
checkpoint selection for `mem revert`, and the state comparison used by
`mem undo`. Sharing the model prevents each command from inventing a different
meaning for “before,” “after,” “latest,” or “the previous state.”

Ordinary `mem find` remains a search over the current Context graph. It must
not silently enumerate or transmit history for every query. The history path
is activated only when the query contains a supported temporal or
version-oriented marker. The bounded English detector recognizes
before/after/during/while/when, latest/earliest/previous, supported “last …”
and “first …” forms, history/historical, checkpoint/version, as-of/at-the-time,
used-to, until, and since language. The Korean detector recognizes
`직전`, `직후`, `이전`, `이후`, `전에`, `후에`, `전의`, `후의`, `동안`,
`당시`, `시점`, `버전`, `체크포인트`, `과거`, `히스토리`, `마지막`,
`최초`, `그때`, supported 있을/없을-때 forms, `하기 전`, `한 뒤`,
`변동 이후`, and `변경 이후`. Marker recognition selects the history
pipeline; it does not by itself decide the query's semantic answer.

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

### `mem find`

```text
mem find
mem find "parking information"
mem find "things changed after the shuttle notice changed"
mem find "셔틀 공지가 있을 때 마지막으로 업데이트된 메모리"
```

A query-less invocation in a TTY opens the process-local Find search
workbench with a blank, focused one-line query. The person may check multiple
readable Context roots and independently choose whether to include lexical
namespace descendants and follow explicit embeds. It sends nothing to a
provider until a nonblank query is submitted. Outside a TTY, a query remains
required so scripts never wait for an interactive selector.

A non-temporal query keeps the existing current-state Find behavior and
privacy boundary. A temporal query may return versioned direct Memory states
or direct Memory transitions as well as checkpoints when the wording asks for
one. Both paths use the selected Context plus every materialized ordinary
namespace descendant and reachable explicit embed by default; `--direct`
limits either path to the selected Context. History results must identify their
Context, checkpoint or transition boundary, relation to the anchor, and
whether they are restorable.

In a TTY, temporal results are inspectable with the shared history
presentation. Enter inspects a selected result; it never changes the Context.
Outside a TTY, results are printed as ordinary read-only output suitable for
inspection, not as a persisted selection receipt.

### `mem log`

```text
mem log
mem log "the last version before the detour ended"
mem log --manual
mem log --plain
```

In a TTY, operand-free `mem log` first opens the shared complete Context tree.
Selecting a location opens the shared history picker for that Context. Contexts
with zero eligible checkpoints remain selectable and open an explicit empty
history view; only Escape or `q` closes it. Up and down move through populated
entries, Enter toggles the selected entry's details, and Escape or `q` closes
the view. Closing or inspecting a Context or log entry has no write effect.

Outside a TTY, `mem log` retains plain checkpoint rows. This preserves shell
redirection and automation and avoids requiring terminal key input.

### `mem revert`

```text
mem revert
mem revert 2f98a740
mem revert "the version before the shuttle notice was removed"
mem revert --keep
```

An exact checkpoint UID or unambiguous UID prefix remains the deterministic
command-line restoration path. In a TTY, an omitted selector or a
natural-language selector may open the same history picker in restoration
mode. The semantic phase produces candidates only. Pressing Enter returns a
local receipt containing the frozen Context name and exact full checkpoint
UID; the command then invokes the ordinary store restoration path for that
UID.

A natural-language query never mutates directly, even if the provider returns
one candidate. The current non-TTY command refuses semantic selection and
points the caller to `mem log "QUERY"` followed by an exact UID. An omitted
selector outside a TTY is also an error. This avoids an implicit “select the
first result” policy in scripts.

The picker freezes the Context UID, canonical Context digest, and digest of the
complete visible checkpoint list. After Enter, the command first checks that
reviewed frame and passes all three preconditions to the store. The store then
acquires the Context write lock, reloads the Context and checkpoint history,
rechecks all three values, and resolves the exact target before changing
anything. A save, checkpoint, revert, or checkpoint-history copy through the
public store API participates in the same Context lock discipline, so it
cannot change the reviewed frame between validation and mutation.

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

New automatic checkpoints retain a top-level `command_before` direct snapshot.
This makes the exact pre-image available even when a programmatic caller had
no earlier baseline checkpoint. Older histories remain usable: their pre-image
is reconstructed from the preceding effective state, including the implicit
target state of a retained Revert receipt. The post-image remains the ordinary
checkpoint snapshot. Neither image resolves MemoryRefs, embedded Contexts, or
query-only sources.

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

`mem trace` remains a separate read-only Memory-lineage view over these
operations. Its default terminal projection groups shared receipts into
newest-first one-line command rows and links a restoration to its source
operation. It is not used to choose or authorize Undo/Redo: restoration still
requires the complete command-unit pre/post frames described above, whereas a
Trace intentionally contains only the selected lineage's local effect.

Undo and Redo use a single-line terminal receipt containing only the source
action and affected Context and Memory counts with `+`/`~`/`-` effect totals.
Supported receipts reconstruct their canonical effective operands from frozen
checkpoint metadata, including Update's `--from` and `--to`, so they omit a
redundant affected-location list. Content-bearing Add/Edit operands and
Forget instructions and historical Integrate instructions use typed
placeholders: the action shape remains visible without repeating private text.
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

The default revert behavior truncates checkpoints newer than the selected
target and first records the pre-revert Context state. That pre-revert
checkpoint carries a bounded `log_snapshot`, allowing the displaced local log
to be reconstructed when the person reverts back to it. History enumeration
may include records recoverable through this metadata rather than pretending
that the visible checkpoint directory is an append-only ledger.

Nested `log_snapshot` values are deliberately thinned to prevent recursive
growth. Therefore, “recoverable history” means the history reconstructable
from the currently retained checkpoints and their supported recovery
metadata. It is not an immutable audit log, and it is not permission to
restore an arbitrary intermediate Memory version. Restoration always ends at
an exact retained checkpoint boundary.

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
