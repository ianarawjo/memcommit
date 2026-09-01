# Checkpoint revision Diff design rationale

## Problem

Checkpoint Viewer previously answered two incomplete questions. Diff showed
only items changed by the selected checkpoint, so a person could not tell what
the complete Context contained afterward. Revert instead compared the current
Context with the selected target and labelled the list `RESTORE IMPACT`; this
hid what the selected revision itself had done and made Diff and Revert tell
different stories about the same checkpoint.

The motivating `practice/2` history contained retained `a`, `b`, and `c`
Memories, one Makemore revision that added three cases, and several later
changes. A current-to-target Revert list correctly described mechanical writes
needed today, but it did not explain the Makemore revision or display the
complete six-Memory result that would be restored.

A later one-shot CLI revision removed Diff's Viewer and also let bare
`mem diff` fall back to the active Update record. That made the common command
both unexpectedly long—because it printed Update reason and provenance blocks—
and semantically unstable: its subject changed according to unrelated
process-local Update state. A subsequent two-checkpoint positional form added
a second time-axis contract even though Context chronology already belongs to
`mem trace CONTEXT`.

Makemore memorizes its semantic result by appending proposals and recording
`effect: ADD`; it cannot edit or remove an existing Memory. Makemore evidence
therefore uses that production memorization capability and can classify only
prior Memories as `KEEP` and generated Cases as `ADD`. The mixed-effect Viewer
evidence uses a production Update application, whose contract actually permits
`EDIT`, `REMOVE`, and `ADD` together.

## Shared revision contract

The checkpoint revision projection freezes:

- the persisted `command_before` image when available, otherwise the preceding
  checkpoint snapshot or the empty creation baseline;
- the selected checkpoint snapshot and its direct-item order;
- the checkpoint action, description, and exact UID.

Every resulting direct item receives exactly one disposition:

- `KEEP` when the UID and stored item are byte-equivalent before and after;
- `ADD` when the UID exists only after the revision;
- `EDIT` when the same UID retains different stored content or metadata.

Items present only before the revision remain inline as `REMOVE`. When common
UIDs retain their relative order, a two-cursor merge places removals and
additions at the transition where they occurred. An order-only change keeps
the complete result order visible and adds an explicit order note rather than
misrepresenting a move as REMOVE plus ADD. The summary counts kept, added,
edited, and removed items independently.

Each displayed physical line begins with a fixed text-visible effect gutter and
disposition: neutral `[KEEP]`, `- [EDIT]` then `+ [EDIT]`, `- [REMOVE]`, or
`+ [ADD]`. The before-side `-` is red and the after-side `+` is green in a
color-capable terminal; the disposition keeps its independent operation color,
so `[ADD]` remains blue. There are no per-item headings or blank spacer rows.
The shared `checkpoint_revision_detail_renderer` retains the complete stream
for Revert, where the whole restoration destination must stay visible.
Diff's `checkpoint_revision_document_fragments` uses the same frozen
classification and line/word diff mechanics but hides `KEEP` rows by default;
the result count and hidden-retained count keep that omission explicit.
`--verbose` restores `KEEP` rows and complete UIDs. Non-Memory direct items are
rendered from their stored record without opening a Reference, embedded
Context, Grant, or provider connection.

## Line-oriented entry contract

Diff exposes one checkpoint revision. Bare `mem diff` uses the current
Context's newest retained checkpoint. `mem diff CONTEXT` and
`mem diff CONTEXT_UID` use that Context's newest checkpoint, while
`mem diff CHECKPOINT_UID` selects one exact revision. The explicit
`mem diff CHECKPOINT --context CONTEXT` and
`mem diff CONTEXT --checkpoint CHECKPOINT` forms remain available for
disambiguation. The revision's implicit before-state is its persisted
`command_before`, preceding checkpoint, or empty creation baseline.

`--stat`, `--raw`, and `--verbose` refine that same selected checkpoint. Stat
prints exact revision counts, raw prints provider-free direct-item unified
diffs, and verbose includes retained rows and full UIDs. No form reads the
active Update slot; reason, owner, and source-provenance inspection belongs to
`mem review update`.

These are selected-transition item counts, not history-command counts. For
example, `1 edited` on an Update checkpoint says that one stable Memory UID
changed between that checkpoint and its predecessor. It does not say that the
Context has only one retained revision, nor does it absorb an earlier creation
baseline or Distill transition into the selected Update. Those earlier
checkpoints remain independently selectable.

A bare Diff operand is completed by the shared typed Context/checkpoint
targeting layer. Relative forms remain Context-only. A bare eight-or-more
character UUID-shaped value is checked against the frozen ordinary-local
checkpoint catalog, so a printed checkpoint prefix can be passed directly as
`mem diff CHECKPOINT`. Exact Context names remain available, but a spelling
that matches both namespaces is rejected with the explicit `--context` and
`--checkpoint` disambiguation forms rather than being guessed. A unique
`--checkpoint` may likewise infer its owning local Context; ambiguity never
prefers the current Context or the newest history.

## One-shot Diff boundary

`mem diff` has no checkpoint picker and no two-checkpoint positional form. A
Context target returns its newest checkpoint revision and a checkpoint target
returns that exact revision. On an interactive terminal the frozen document
opens in the shared full-screen read-only Viewer; Escape, Backspace, or Q
closes it, and no row can be selected or applied. Pipes and ordinary test
runners receive the ANSI-free equivalent. `--raw` and `--stat` always remain
static output so shell composition does not acquire an interactive boundary.

The single-checkpoint header exposes the checkpoint identity, recorded action,
change counts, complete result count, and description without repeating OWNER,
MEMORY UID, REASON, SOURCE REFERENCES, or content hashes for every row. Earlier
checkpoint discovery and whole-Context chronology belong to
`mem trace CONTEXT`, whose rows expose exact checkpoint identities that can be
passed back to Diff. Update explanation belongs to `mem review update`.

## Revert target scope and approval

Bare interactive `mem revert` captures the current Context name once and opens
that Context's History workbench immediately. `--context` resolves one existing
Context against the same command-start snapshot. Revert does not expose a
Profile-wide alternate target tree inside the operation: the mutation subject
is the current or explicit Context, matching bare Diff's requested-scope rule.

The revision Viewer replaces `RESTORE IMPACT`; it intentionally describes the
selected checkpoint relative to its own predecessor. The complete result makes
the restoration destination inspectable without presenting a later current
state as part of the historical revision. This rejects a separate duplicated
current-to-target section, which would make long histories repeat most Memory
bodies and blur revision meaning.

Revert safety remains downstream and unchanged: Items returns the exact full
checkpoint UID, History chooses discard-newer or keep-all, Apply repeats both,
and the Store checks the frozen Context UID, Context digest, checkpoint-history
digest, and exact checkpoint under the write lock before publishing anything.
Closing any screen remains non-mutating.

## Boundaries and limitations

This is a direct stored-item revision view, not a semantic relation analysis.
It does not infer that a removed UID and added UID express one conceptual edit;
only stable UID continuity proves `EDIT`. It does not traverse embedded
Contexts or dereference Memory references. The exact target snapshot may differ
substantially from the current Context because of later revisions; the complete
result is authoritative for what Revert will restore, while the selected
revision dispositions explain how that historical state arose.

## Interaction evidence

The ordered 180×52 true-color PTY capture and read-only byte verification are
recorded in
[`screenshots/mem-diff-single-checkpoint-viewer-20260831/README.md`](screenshots/mem-diff-single-checkpoint-viewer-20260831/README.md).
