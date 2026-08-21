# Checkpoint revision Diff design rationale

## Problem

Checkpoint Viewer previously answered two incomplete questions. Diff showed
only items changed by the selected checkpoint, so a person could not tell what
the complete Context contained afterward. Revert instead compared the current
Context with the selected target and labelled the list `RESTORE IMPACT`; this
hid what the selected revision itself had done and made Diff and Revert tell
different stories about the same checkpoint.

The motivating `practice/2` history contained retained `a`, `b`, and `c`
Memories, one Elaborate revision that added three cases, and several later
changes. A current-to-target Revert list correctly described mechanical writes
needed today, but it did not explain the Elaborate revision or display the
complete six-Memory result that would be restored.

Elaborate is itself a semantic Add: its publication path appends proposals and
records `effect: ADD`; it cannot edit or remove an existing Memory. Elaborate
evidence therefore uses that production Add primitive and can classify only
prior Memories as `KEEP` and generated Cases as `ADD`. The mixed-effect Viewer
evidence uses a production Update application, whose contract actually permits
`EDIT`, `REMOVE`, and `ADD` together.

## Shared revision contract

`checkpoint_revision_detail_renderer` is the sole interactive checkpoint
detail renderer for ordinary local Diff and Revert. For one checkpoint it
freezes:

- the persisted `command_before` image when available, otherwise the preceding
  checkpoint snapshot or the empty creation baseline;
- the selected checkpoint snapshot and its direct-item order;
- the checkpoint action, description, and exact UID.

The Viewer renders one compact unified direct-item stream. Every resulting
direct item receives exactly one disposition:

- `KEEP` when the UID and stored item are byte-equivalent before and after;
- `ADD` when the UID exists only after the revision;
- `EDIT` when the same UID retains different stored content or metadata.

Items present only before the revision remain inline as `REMOVE`. When common
UIDs retain their relative order, a two-cursor merge places removals and
additions at the transition where they occurred. An order-only change keeps
the complete result order visible and adds an explicit order note rather than
misrepresenting a move as REMOVE plus ADD. The summary counts kept, added,
edited, and removed items independently.

Each physical line begins with a fixed text-visible effect gutter and
disposition: neutral `[KEEP]`, `- [EDIT]` then `+ [EDIT]`, `- [REMOVE]`, or
`+ [ADD]`. The before-side `-` is red and the after-side `+` is green in a
color-capable terminal; the disposition keeps its independent operation color,
so `[ADD]` remains blue. There are no per-item headings or blank spacer rows.
Each displayed direct item remains one `ITEM` navigation unit, so an EDIT pair
advances once. Memory bodies reuse the shared line/word diff mechanics.
Non-Memory direct items are rendered from their stored record without opening
a Reference, embedded Context, Grant, or provider connection.

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
