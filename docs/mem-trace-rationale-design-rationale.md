# `mem trace`, `mem rationale`, and saved atomize provenance

## Motivation

Raw intake can produce a Memory whose wording is incomplete, and semantic
atomization can later replace one source UID with several child UIDs. Showing
only the current text does not answer three different questions:

1. What retained source occurrence did this Memory come from?
2. Which recorded operations changed its content or identity?
3. Why might this wording make sense inside the current Context?

The first two are provenance questions. The third is an interpretation
question. They must remain visibly separate: a plausible model explanation is
not a historical record, and a saved semantic preview is not evidence that a
change was applied.

## Command contract

```text
mem log --memory MEMORY
mem trace
mem trace MEMORY
mem trace MEMORY --plain
mem rationale
mem rationale MEMORY
mem rationale MEMORY --recorded-only
mem rationale MEMORY --refresh
```

All Memory-targeted routes accept a current or retained historical direct-Memory
UID or unambiguous prefix. `mem trace MEMORY` is the public shorthand for
`mem log --memory MEMORY`; both enter the same retained-history controller and
projection rather than invoking another CLI command. Neither command changes
Contexts, checkpoints, saved
semantic analyses, proposals, or active state. `mem rationale` may update a
replaceable provider-inference cache after a successful validated inference;
`mem trace` and `mem rationale --recorded-only` remain storage-read-only.

In an interactive terminal, omitting `MEMORY` first opens the common session
picker as a Recents launcher. Recent rows are scoped to the current operation,
ordered newest first, and deduplicated by public Context name, Memory UID, and
exact-versus-descendant range.
The pinned `SELECT A MEMORY` action then opens the common read-only
Context/Memory tree. This keeps repeated inspection quick without replacing
the complete namespace route needed for a new target. When the operation has no
recent rows, the empty catalog is skipped and the Context/Memory tree opens
directly; no saved-session-shaped decision exists in that case.

Recents are derived only from completed command-attempt records. A record
stores the operation, public or scoped Context name, Memory UID, and the
content-free descendant boolean; it never copies Memory content, inferred
rationale, Grant material, or provider data.
Trace Recents also include completed `mem log --memory` attempts because that
route is the same Memory-lineage view.
Failed and cancelled attempts are not offered. Selecting a recent row freezes
and revalidates its command-attempt receipt, then enters the ordinary command
path, where current Context existence, UID resolution, and effective
permissions are checked again. A recent row is therefore navigation history,
not retained read authority or a report snapshot.

The shared execution launcher begins with `THIS CONTEXT ONLY` and
`INCLUDE DESCENDANTS` projected through the common `ContextReachState`, then
the common Context/Memory tree. It begins on the command's current or
explicitly scoped Context row, including when that exact row has no direct
Memory. Changing range never changes global current Context state. Rationale
places every eligible Memory beneath its actual owner in the readable public
hierarchy; a Grant attachment is never treated as a hierarchy edge. Trace may
discover a Memory in a locally owned lexical descendant, but the resulting
lineage still opens only that exact owner Context's history. Context rows
browse or collapse the tree, while only an exact Memory row can complete
selection.

The two controls are composed through the same service-wide terminal chrome,
not through an operation-owned Trace/Rationale shell. `RANGE` and `CONTEXTS &
MEMORIES` reuse `build_focused_frame`; their top-to-bottom layout reuses
`build_tui_frame`, and the shared terminal theme supplies the light-blue heavy
focused border and retained-choice fill. `SurfaceFocusController` owns
Tab/Shift-Tab, boundary-aware vertical movement, and Enter dispatch across the
two frames, while the existing reach and tree adapters retain their semantic
actions. The unscoped Context browser used by Switch and Log retains its
existing single-surface presentation. This avoids manufacturing a parallel
picker merely to reproduce frame lines or focus color.

The launcher freezes the eligible descendant catalog before it opens but
starts with exact reach. It therefore remains open when the root has zero
direct candidates and descendants do have candidates: the person can move to
`INCLUDE DESCENDANTS` instead of receiving a premature empty-scope error.
When the complete frozen exact-plus-descendant catalog has no candidate, it
still fails before opening an empty selector.

Each eligible UID appears once per owner Context: currently present Memories
first in canonical Context order, followed by historical-only Memories using
their last retained content. `HISTORICAL` means only that the UID is no longer directly present;
it can identify a removed Memory, a split parent, or another retained earlier
state. Equal text never collapses distinct UIDs, and edits of one UID never
create multiple picker rows. Every locally owned row also shows the number of
distinct recorded operations retained for that lineage. Creation, edit,
removal, reorder, and restoration can each contribute once per retained command
identity. A synthetic `HISTORY_GAP` remains visible after opening Trace but is
excluded from this count because it proves only that the current state is not
reconstructable; it does not prove one recorded change. Such a row therefore
shows `0 RECORDED CHANGES`, never a negative result produced by subtracting a
synthetic row. A granted Rationale row shows `HISTORY UNAVAILABLE` rather than
treating withheld owner history as zero or deriving a count from current
content. Up/Down, Left/Right,
held-arrow acceleration, and wrapped scrolling all come from the common Context/Memory selector rather
than a second operation-specific navigation grammar.

The picker returns the exact root, owner Context, descendant boolean, and full
UID, then enters the same report-building path as an explicit selector. It
does not perform per-row semantic inference or open Memory references,
embedded Contexts, or query-only sources. `mem rationale`
connects its optional inference provider only after Enter selects a Memory;
canceling therefore performs no provider call. After the full-screen picker
closes, the command reloads the direct Context before reconstructing the report
so it does not combine a pre-picker live frame with post-picker history.
The selected row names its recorded-change count before Enter: Trace covers
the full retained lineage from earliest retained evidence through the current
Context, while Rationale covers recorded evidence, saved analysis, and current
interpretation. This shared first-stage launcher is the interactive boundary
for choosing both reach and Memory; it does not silently broaden exact reach.

Rationale renders its complete interactive report inside the common framed,
wrapped, read-only `VIEWER`, whether its Memory came from Recents, the tree, or
an explicit operand. Trace uses the shared temporal `ITEMS + VIEWER` workbench
also used by Log and Diff: Items are lineage-affecting command units and Viewer
shows the selected before/after evidence together with the complete lineage
endpoints. Bare, recent, and explicit Trace targets all enter this workbench in
a TTY. `--plain`, non-TTY, and JSON routes retain stable non-full-screen output.
Both the standalone Rationale Viewer and the temporal Viewer move by visible
wrapped rows through the common cursor-backed read pane; a hidden fixed cursor
must not reset the viewport to its first logical line. The temporal workbench
additionally uses shared Surface boundary traversal between Viewer and Items.
Rationale reuses the same target and Trace projection, then adds its
interpretation sections; it does not inherit Trace's owner-history authority
when the target is granted.

Outside a TTY, omission fails instead of silently selecting the first Memory;
automation must pass an explicit UID or prefix. `--json` also requires an
explicit selector so machine-readable stdout is never preceded by terminal
selection traffic. Escape, `q`, and Ctrl-C cancel the picker without changing
the store. If no current or retained historical direct Memory exists anywhere
in the frozen exact-plus-descendant catalog, the command reports that boundary
without opening an empty UI.

By default, `mem trace` renders the entire selected lineage as compact
operation rows. The current endpoint comes first, followed by operations in
newest-first order, and the earliest retained origin comes last. A trusted
range label states both directions explicitly: rows run downward into older
history, while every row's `before → after` arrow still points forward in
time. Creation is `∅ → Memory`; removal is `Memory → ∅`; a Revert, Undo, or
Redo that removes a Memory is labeled `RESTORED/REMOVED` instead of relying on
a bare minus sign.

Presentation groups events by retained command-unit receipt, then explicit
operation identity, with checkpoint UID only as the legacy fallback when no
stronger operation identity exists. Several events from one operation become
one row. Compact restoration rows filter before/after states to the selected
lineage because a command-unit receipt may describe other changed Memories or
Contexts. Multiline and control-bearing content is display-escaped and bounded
inside the row. Checkpoint identity, descriptions, citations, complete UIDs,
and saved-analysis detail move to `--verbose`; `--json` keeps the chronological
structured event order for programmatic consumers.

Thus the human-facing scopes remain distinct:

- `mem log` browses Context checkpoint states and restoration addresses;
- `mem log --memory` filters that retained history to one proven UID lineage;
- `mem revert` restores one reviewed checkpoint;
- `mem undo` and `mem redo` restore one global command unit;
- `mem trace` is the shorthand for Log's Memory-lineage projection; and
- `mem rationale` adds recorded reasons, saved analysis, and contextual
  interpretation to that lineage.

Trace must not become the execution authority for Undo or Redo. A per-Memory
lineage can include reconstructed or unrecorded events and cannot prove the
complete before/after frame of a multi-Context command. Undo/Redo therefore
continue to use their exact command-unit snapshots and receipts. Trace links
them in presentation as, for example, `mem undo ← mem add`, so the restoration
and its source operation remain visible without coupling a read-only report to
the mutation boundary.

“Earliest retained” is deliberately weaker than “created here.” When the
Context has no checkpoint, the earliest state available to trace is the
current state itself. The UI shows it only under `CURRENT` and leaves
`ORIGINAL` unavailable, because it cannot establish when, where, or by whom
that Memory was created; `mem rationale` therefore reports that no retained
creation event was found.

`mem rationale` layers:

- **RECORDED ORIGIN** — command/checkpoint evidence about intake;
- **RECORDED RATIONALE** — reasons explicitly stored by a transformation;
- **SAVED ANALYSIS — not a creation cause** — current ambiguity review;
- **SAVED ATOMIZE ANALYSIS** — current, stale, or applied preview;
- **UNAPPLIED PROPOSALS** — update/impact material that has not changed this
  Memory;
- **INFERRED WITHIN THE CURRENT CONTEXT — not recorded** — a best-effort
  ordinary reading, freshly generated or reused from an exact-input cache.

`--recorded-only` neither reads nor writes the inference cache and never
connects the inference provider. `--refresh` bypasses a matching cache entry
and replaces it only after a new provider response passes normal validation;
combining the two options is rejected.

## Evidence labels

Trace never creates lineage from text similarity. Independent Memories may
legitimately contain identical content.

| Label | Meaning |
|---|---|
| `RECORDED` | The command contract or explicit trace metadata names the relation. |
| `RECONSTRUCTED` | Adjacent Context snapshots plus deterministic operation arguments are sufficient to reproduce the relation. |
| `INFERRED` | A snapshot transition is visible, but its precise operation-level origin was not recorded. This is structural inference, not an LLM semantic judgment. |
| `UNRECORDED` | Current Context state differs from the last retained checkpoint state. |

Only UID continuity and explicit or deterministically reconstructable
`SPLIT`/`ABSORB` relations connect lineage components. Legacy `chunk` can be
reconstructed only when its named method, source UID, exact children, and
positions all agree. Otherwise trace reports a limit instead of guessing.

These labels describe agreement with the retained local files, not
tamper-evidence. Checkpoint snapshots and their trace metadata are unsigned and
can be edited together by a process with filesystem access. Even
`RECORDED` means that the stored command contract and metadata validate
structurally; it is not cryptographic proof that the event occurred or that
the author was authentic.

Revert needs asymmetric treatment. A pre-revert checkpoint records the state
that existed immediately before the revert; the target checkpoint records the
restored state. Retained `log_snapshot` data is read so undo-revert history can
be reconstructed without treating the pre-revert snapshot as the result of the
revert.

### Command-unit Undo/Redo events

An Undo or Redo is rendered as the command that actually ran, not as a generic
Revert. Its `RESTORED · RECORDED` event retains the shared restoration receipt
UID, the original command-unit UID and command name, and the complete affected
Context identity list repeated by that receipt. Consequently, tracing a Memory
in either owner of a multi-Context Update shows the same Undo/Redo operation
boundary even though the content diff remains local to the selected Memory's
Context.

The original Update event carries its shared Update session/digest unit and
the same affected-Context membership. Undo/Redo `source_uid` therefore points
back to an operation identity visible on the source Update event rather than
only to one owner's checkpoint.

The trace does not collapse several owners' Memory changes into one synthetic
cross-Context lineage. That would mix otherwise independent provenance graphs.
Instead, the shared operation identity correlates the per-Context events while
each event continues to show only its owner's before/after content. Receipt
metadata must match the checkpoint command, include the traced Context, and
contain unique, structurally valid Context identities; otherwise Trace falls
back to snapshot reconstruction and reports the invalid metadata as a limit.

## Raw add provenance

New `add`, `add --input`, and `add --paste` checkpoints retain:

- ordered created Memory UIDs;
- input mode and parser version;
- exact raw intake text;
- a SHA-256 integrity value for that text.

Memory remains the minimal `{uid, content}` record. Intake provenance belongs
to the operation checkpoint, not every Memory.

For line-based intake, trace can report the physical source line and item
ordinal. It labels this `RECORDED` only when the declared UID order matches the
Context order and the raw-text hash verifies. A damaged hash or reordered UID
ledger degrades to `RECONSTRUCTED`; it does not continue claiming that an exact
raw occurrence was retained.

Older checkpoints can often recover normalized order from the snapshot, but
cannot retroactively prove the exact raw bytes.

## Atomize preview versus content history

`mem impact atomize` does not mutate a Context or create a checkpoint. It does
persist the latest digest-bound preview for that Context UID at:

```text
~/.mem/atomize-analyses/<context-uid>.json
```

That artifact records classifications, reasons, proposed children, and literal
source spans. Loading it repeats the local grounding, count, uniqueness, and
projected-size checks used for the provider response.

The path is a latest-only slot, not an analysis log. Running another preview
for the same Context UID replaces the previous artifact. Applied checkpoints
retain the analysis/operation UID, source-to-result relation, result contents,
reason, and reason codes, but do not retain every preview field. Consequently,
an overwritten applied preview can lose its original `created_at`, lint, and
literal source-span details even though its content transformation remains in
checkpoint history.

A trace attachment has one of three states:

- `CURRENT`: its source digest matches the Context and no matching applied
  snapshot is current;
- `STALE`: the direct-Memory frame changed after analysis;
- `APPLIED`: a checkpoint with the same analysis/operation UID has a snapshot
  equal to current direct-Memory state.

The current-snapshot condition matters after `revert --keep`. A matching
operation somewhere in retained history does not by itself mean the current
Context is still atomized.

## Apply destinations

The preview and transformation have deliberately separate commands:

```text
mem impact atomize
mem atomize --save
mem atomize --save-as NEW_CONTEXT
```

`--save` applies to the selected existing Context/branch and creates one
atomize checkpoint. It blocks an inbound `memory_ref` only when that reference
targets the selected Context and one of the Memories that would be split;
there is no safe automatic one-to-many retarget. References to unchanged
Memories do not block application.

`--save-as` preserves the source and creates a fresh Context identity, like an
init-based derived workspace. It:

1. copies the source frame with stable direct Memory UIDs;
2. records that unmodified frame as an `init` checkpoint, including the source
   Context identity and ordered Memory UIDs;
3. binds the saved preview to the new Context identity;
4. applies atomization and records an atomize checkpoint;
5. switches only after all writes succeed.

This gives the new Context an inspectable `source-form → atomized-form`
history without copying the source's unrelated checkpoint log. Split children
receive fresh UIDs. Unsplittable, uncertain, atomic, and non-propositional
Memories retain their UID and content. External references to the source remain
valid because the source is unchanged.

If a save-as phase fails, the exact new Context and its copied analysis are
removed. The active-state JSON is replaced atomically so a failed final switch
leaves the prior selection readable and permits that rollback. No global
transaction or lock spans the Context, checkpoint, analysis, and active-state
files, so process crashes and concurrent writers remain a research-prototype
limitation.

## Rationale inside the current Context

The inference layer is called **inference within the current Context**, not
“surrounding-context inference.” The interpretation frame is all directly owned
ordinary Memories in that Context when it fits the input limit. Order and
distance provide cues; they do not define the evidence boundary. Only an
explicit size limit may reduce the frame, and that reduction must be reported.

The provider receives opaque candidate IDs and must cite only allowlisted IDs.
Unknown or duplicate IDs invalidate the response. The explanation may state a
best-supported ordinary reading, describe contextual flow, and list what
remains unresolved. It cannot claim to recover the author's actual intention
or the historical reason the Memory was created.

For a historical UID that is no longer present in the current frame, rationale
still uses the current directly owned Memories as its interpretation frame. It
anchors distance to the historical position retained for the target. After a
reorder or a one-to-many split, that numerical neighborhood is only an
approximation; it does not reconstruct the neighbors that surrounded the
Memory at the historical moment. The full-frame inference may still cite
relevant current Memories, but “nearby” fallback output must not be read as
historical provenance.

A stale ambiguity review is not presented as current evidence. Provider
failure or invalid output falls back to a deterministic Context window while
preserving all recorded sections.

## Context-inference cache

Only the validated provider-created `ContextInference` is cached. The complete
`RationaleReport` is not: trace events, recorded reasons, saved analysis,
atomize attachments, and unapplied proposals are rebuilt from current local
state on every invocation. Consequently a proposal or recorded provenance
change appears immediately without forcing an unrelated provider call.

The active profile keeps one replaceable slot per Context UID and selected
Memory UID under its own MemoryStore root (the authoring profile uses
`~/.mem`):

```text
<active-store>/rationale-inferences/<context-uid>/<sha256(memory-uid)>.json
```

The raw Memory UID is hashed for the filename because legacy identities are
data, not safe path components. The record is bound to both exact identities
and to a canonical SHA-256 digest of the inference contract, provider-contract
namespace, exact prompt, and exact output schema. The prompt already contains
the target content and retained position, the ordered current direct-Memory
frame or deterministic size-limited subset, and the current saved-analysis
fields that inference can use. Editing, adding, removing, or reordering one of
those Memories, changing the target frame, or changing those analysis fields
therefore causes a cache miss. Display mode, picker use, trace-only evidence,
and proposal-only state do not affect provider input and do not invalidate the
entry.

The cache persists only normalized explanation text, unresolved items, and
the supporting ordinary Memory UIDs. Explanation text can quote or paraphrase
an ordinary Memory, which is why deletion shares the Context's privacy
lifetime. The record does not persist the prompt, a separate candidate-frame
payload, raw provider response, complete report, references, or query-only
material. On a hit, support UIDs are mapped back through the current opaque
candidate allowlist and the reconstructed response passes the same strict
length, shape, duplicate, and unknown-evidence validation as a fresh response.
A malformed, oversized, identity-mismatched, or symlinked cache is never
rendered; it is treated as a miss and the command can still use a fresh
provider or deterministic fallback. Cache read or publication failure remains
a visible limit but does not discard an otherwise valid report.

Provider work runs without holding a long Context lock. Before publishing a
new entry, the command briefly locks and rechecks the exact direct Context
identity and digest, then writes through an atomic same-directory replace. A
late response for a changed or deleted Context is not published. Concurrent
same-input misses may still duplicate a provider call; avoiding that would
require holding an interprocess lock across an unbounded external request.
Deleting a Context preflights and removes its inference subtree because the
derived explanation shares the source Context's privacy lifetime.

## Readable subtree Rationale and Study Trace boundary

Rationale does not perform an outbound search into arbitrary sibling or global
Contexts. Selecting exact range freezes only that Context; selecting
descendant range additionally freezes every materialized lexical descendant
in the shared readable public namespace. The public name, not the Grant
attachment, determines hierarchy, so a local `task-1` scope can contain both
`task-1/participant` and a granted `task-1/campus-wiki` sibling.
Each Context retains its own local or grant-bound access object; the hierarchy
does not merge ownership. The target UID may belong to any direct Context in
that subtree, and inference candidates retain their public owner Context names.
Query-only pointers, MemoryRef targets, and narrower query-only overrides never
broaden this frame. This matches recursive Find's namespace expectation while
keeping the disclosure boundary deterministic.

A granted READ view permits this content interpretation but does not imply
authority to inspect the source Profile's checkpoints, command receipts, saved
reviews, or atomize attachments. Granted Rationale therefore constructs a
history-free current-Memory projection, labels authority history as withheld,
and keeps its inference ephemeral. An inference confined to one exact granted
resource needs READ; an inference that combines local and granted ownership or
distinct Grants additionally requires every contributing Grant to authorize
`DERIVE` and `COMBINE`. This check happens before the provider is connected, so
missing combination authority cannot leak candidate content. `--recorded-only`
is rejected when the selected target itself is granted because it would request
precisely the history that READ does not expose; a local target can still show
its retained local evidence without invoking the provider. Trace is always
rejected for a granted target.

Every locally owned ordinary Context may inspect its own retained history,
including every task namespace in a composed participant Study run. Task names
are research organization, not an authority primitive. Granted READ remains
different: it exposes the reviewed current content projection but not the
authority Profile's checkpoints, command receipts, or saved history artifacts.
Only Grant rows therefore need a visible `TRACE BLOCKED` analysis boundary;
local Study rows no longer repeat task-dependent Trace annotations.

Multi-Context inference is not cached yet. Publishing a reusable result safely
would require one freshness boundary over every Context in the selected
range, while the current cache publication validates one direct Context.
Recomputing is preferred to retaining a result whose supporting descendant
changed during the provider turn. Exact one-Context inference retains the
existing validated cache path.

## Query-only boundary

Trace, rationale, atomize preview, and both apply modes never open a
`QueryContextRef` source. The public pointer can be retained in a derived
Context, but concealed source text is not a trace candidate, rationale
candidate, atomize candidate, or copied Memory.

This is a tested command-path invariant, not operating-system confidentiality.

## Alternatives rejected

- **Text-similarity lineage:** rejected because equal wording does not establish
  derivation.
- **Treating preview as history:** rejected because analysis can be stale or
  never applied.
- **Using a model to invent missing provenance:** rejected; semantic inference
  is shown in a separate section.
- **Copying all source checkpoints into save-as:** rejected because the new
  Context needs a clear local baseline, not inherited history with the wrong
  Context identity.
- **Putting raw source metadata into every Memory:** rejected to keep Memory
  minimal and operation provenance centralized.
- **Caching the complete rationale report:** rejected because recorded and
  proposed evidence has independent freshness requirements.
- **Keeping an unbounded content-addressed rationale archive:** rejected to
  avoid silently accumulating provider-derived copies of private Context
  material. The cache is an optimization, not historical evidence.

## Remaining limitations

- Checkpoints are whole-Context snapshots rather than a canonical event ledger.
- A Context with no retained checkpoint has no provable creation boundary; its
  current Memory can be the earliest observable lineage state.
- `RECORDED` metadata is structurally checked but unsigned and therefore not
  tamper-evident.
- Old branch histories can retain source Context identities without a recorded
  branch-creation event.
- Legacy operations without explicit trace metadata may be reconstructable only
  at a coarse level.
- Historical rationale neighborhoods become approximate after reordering,
  removal, or one-to-many replacement because inference is deliberately framed
  by the current Context rather than a reconstructed historical frame.
- Only the latest atomize analysis per Context UID is retained. A later preview
  can replace preview-only evidence that was not copied into an apply
  checkpoint.
- Literal source-span validation does not independently prove full semantic
  entailment of a generated child.
- The rationale and atomize providers are not pinned to an immutable model
  version. A rationale cache can therefore continue serving a valid result
  across a backend change until its explicit contract version changes or the
  person runs `--refresh`.
- Bare interactive selection reconstructs the retained history once to build
  its candidate catalog and again after selection to produce a fresh report.
  This favors one authoritative selector domain and post-picker freshness over
  caching private frame objects; very large retained histories can therefore
  make the interactive path slower than an explicit UID.
