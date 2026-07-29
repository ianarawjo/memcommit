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
mem trace MEMORY
mem rationale MEMORY
mem rationale MEMORY --recorded-only
```

Both commands accept a current or retained historical direct-Memory UID or
unambiguous prefix. They are read-only with respect to Contexts, checkpoints,
analysis artifacts, and active state.

`mem trace` renders:

- the earliest retained state in the selected lineage component;
- ordered content events;
- saved atomize analyses as separate attachments;
- current descendants, if any;
- explicit limits when history cannot be reconstructed safely.

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
- **INFERRED WITHIN THE CURRENT CONTEXT — not recorded** — a one-shot,
  best-effort ordinary reading.

`--recorded-only` never connects the inference provider.

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
- The one-shot inference provider and atomize provider are not pinned to an
  immutable model version.
