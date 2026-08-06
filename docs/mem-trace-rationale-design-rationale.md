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
mem trace
mem trace MEMORY
mem rationale
mem rationale MEMORY
mem rationale MEMORY --recorded-only
mem rationale MEMORY --refresh
```

Both commands accept a current or retained historical direct-Memory UID or
unambiguous prefix. Neither command changes Contexts, checkpoints, saved
semantic analyses, proposals, or active state. `mem rationale` may update a
replaceable provider-inference cache after a successful validated inference;
`mem trace` and `mem rationale --recorded-only` remain storage-read-only.

In an interactive terminal, omitting `MEMORY` opens the common read-only
Context/Memory tree selector rather than a trace/rationale-specific flat list.
It begins on the command's current or explicitly scoped Context row, including
when that row has no direct Memory. Rationale places every eligible Memory
beneath its actual owner in the readable public hierarchy; a Grant attachment
is never treated as a hierarchy edge. Trace retains its single-Context scope.
Context rows browse or collapse the tree, while only an exact Memory row can
complete selection.

Each eligible UID appears once: currently present Memories first in canonical
Context order, followed by historical-only Memories using their last retained
content. `HISTORICAL` means only that the UID is no longer directly present;
it can identify a removed Memory, a split parent, or another retained earlier
state. Equal text never collapses distinct UIDs, and edits of one UID never
create multiple picker rows. Up/Down, Left/Right, held-arrow acceleration, and
wrapped scrolling all come from the common Context/Memory selector rather
than a second operation-specific navigation grammar.

The picker returns the exact full UID and then enters the same command path as
an explicit selector. It does not perform per-row semantic inference or open
Memory references, embedded Contexts, or query-only sources. `mem rationale`
connects its optional inference provider only after Enter selects a Memory;
canceling therefore performs no provider call. After the full-screen picker
closes, the command reloads the direct Context before reconstructing the report
so it does not combine a pre-picker live frame with post-picker history.
The selected-card detail names the resulting scope before Enter: Trace covers
the full retained lineage from earliest retained evidence through the current
Context, while Rationale covers recorded evidence, saved analysis, and current
interpretation. This shared first-stage picker is the interactive boundary for
choosing a Memory; it does not silently choose an operation subrange.

Rationale renders its complete interactive report inside the common framed,
wrapped, read-only `VIEWER`, whether its Memory was selected interactively or
passed explicitly. Bare Trace continues from the common selector into that
same Viewer so the no-operand interaction is one coherent flow; explicit Trace
remains a direct stdout report for shell inspection and piping. The Viewer
shares Up/Down, PageUp/PageDown, Home/End, and Escape/Backspace/Q close
behavior. Non-TTY and JSON output retain their stable non-full-screen forms.

Outside a TTY, omission fails instead of silently selecting the first Memory;
automation must pass an explicit UID or prefix. `--json` also requires an
explicit selector so machine-readable stdout is never preceded by terminal
selection traffic. Escape, `q`, and Ctrl-C cancel the picker without changing
the store. If no current or retained historical direct Memory exists, the
command reports that boundary without opening an empty UI.

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
- `mem revert` restores one reviewed checkpoint;
- `mem undo` and `mem redo` restore one global command unit;
- `mem trace` shows operations that affected one Memory lineage; and
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
Contexts. Selecting a Context freezes that Context plus every materialized
lexical descendant in the shared readable public namespace. The public name,
not the Grant attachment, determines hierarchy, so a local `task-1` scope can
contain both `task-1/participant` and a granted `task-1/campus-wiki` sibling.
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

Within a composed participant Study run, local Trace is additionally limited
to the `task-3` subtree. Task 3 deliberately studies local/personal-memory history;
Tasks 1 and 2 do not. Normal authoring stores retain Trace. `mem ls` and the
Switch picker render `RATIONALE SUBTREE` together with `TRACE ALLOWED` or
`TRACE BLOCKED` so the difference is visible before a participant selects an
operation.

Recursive inference is not cached yet. Publishing a reusable result safely
would require one freshness boundary over every Context in the subtree, while
the current cache publication validates one direct Context. Recomputing is
preferred to retaining a result whose supporting descendant changed during the
provider turn.

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
