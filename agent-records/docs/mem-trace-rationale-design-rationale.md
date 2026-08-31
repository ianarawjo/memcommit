# `mem trace`, `mem rationale`, and saved atomize provenance

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

> **Atomize route update (2026-08-30):** Trace and Rationale continue to read
> Atomize analysis/application evidence, but the producing console route is
> now one-shot `mem atomize [TARGET]`; Atomize `--save`/`--save-as` examples
> below are historical.

## Motivation

Raw intake can produce a Memory whose wording is incomplete, and semantic
atomization can later replace one source UID with several child UIDs. Showing
only the current text does not answer two provenance questions:

1. What retained source occurrence did this Memory come from?
2. Which recorded operations changed its content or identity?
3. Which independently writable occurrence did a later Merge create or reuse?

Rationale freezes retained Trace evidence, then asks one bounded semantic turn
to express that evidence as compact natural-language provenance. Only when a
structurally valid first draft exceeds the hard presentation bound may the same
frozen Trace enter one bounded compression turn. The narrative must explain the
selected content's source context, recorded derivation, and later lifecycle
without inventing author intent or importing present-day purpose. If history is
absent or hidden, no provider is connected.

## Command contract

```text
mem log --memory MEMORY
mem trace
mem trace MEMORY
mem rationale
mem rationale MEMORY
```

Explicit Memory-targeted routes accept a current or retained historical direct
Memory or MemoryRef UID, an unambiguous prefix, or a qualified `CONTEXT:UID`
locator. A bare explicit UID first resolves current ordinary Memories across
the frozen Profile-readable local and READ-granted namespace. This is the same
UID namespace printed by Find/List/Search, so a granted result can be pasted
directly into either report. Local and granted collisions list public
`CONTEXT:UID` candidates instead of preferring the current Context. Only when
no current readable Memory matches does the route consult ordinary-local
retained items and MemoryRefs. A qualified locator is exact and never broadens
into descendants. `mem trace MEMORY` is the
public interactive route for `mem log --memory MEMORY` when the target is a
direct local Memory; both use the same retained-history controller and compact
projection rather than invoking another CLI command. Log always prints that
projection, while Trace may open its interactive workbench in a TTY.
Neither command changes Contexts, checkpoints, saved semantic analyses,
proposals, active state, or provider-derived caches. Rationale gives the exact
whole retained Trace to an initial provider turn under the versioned
natural-provenance ruleset and validates one bounded paragraph. A valid
over-limit draft may cause exactly one operation-owned repair turn over that
same Trace; no first draft is published. Compare's source-row Rationale action
enters the same ruleset, payload, schema, decoder, and repair boundary.

### Recorded Merge UID handoff

Merge deliberately gives a newly copied Target Memory a fresh UID, so the
Source UID must remain valid for its owning Context while the Target UID names
an independently writable occurrence. The existing version-1
`memory_lineage` receipt records that exact Source Context/Memory coordinate,
Target Context/Memory coordinate, and both content digests under the Merge
lock. Trace now consumes that receipt bidirectionally: selecting either
occurrence joins the Source's earlier retained operations to the Merge event,
and selecting Source also exposes its recorded downstream Target uses.

This handoff is part of the existing Trace, not a new UID-map command or a
large Merge success receipt. The ordinary row remains compact:

```text
[merge] [CHECKPOINT 604759a1] [MEMORIES 2]  facility-updates → transform-scratch/source · Memory content unchanged
  Source: [cd518767] Wiki update draft: ...
  Target: [423582d8] Wiki update draft: ...
```

The relation is admitted only for an automatic, same-Store Merge checkpoint
whose operation UID, target ownership, command pre-image, post-image, Target
content digest, decision record, and Source/Target edge validate together.
`NEW`, `ALREADY_PRESENT`, `TAKE_SOURCE`, and `KEEP_TARGET` remain distinct typed
dispositions. A malformed receipt leaves the ordinary target-local diff
visible, adds a limit for the affected Target occurrence, and never joins the
owners. Cross-Profile and Grant transfers publish no local lineage receipt and
therefore do not broaden through this path.

Alternatives were rejected for contract and usability reasons. Printing every
mapping plus follow-up commands after Merge makes the common receipt scale with
the full frame; requiring Atomize failure or global re-search makes a durable
relationship discoverable only by accident; and treating equal text as
lineage would connect independent Memories. Reusing the retained typed receipt
keeps bare and qualified UID lookup unchanged and makes both Trace and
Rationale consume one provenance authority.

### Typed Reference and granted-current reports

A MemoryRef is an occurrence with its own UID, owner, position, and lifecycle;
it is not an alias for the target Memory's identity. Reference Trace therefore
has two explicit layers:

1. **REFERENCE OCCURRENCE** reconstructs creation, removal, restoration,
   retargeting, and reorder evidence from the owning Context's retained raw
   snapshots.
2. **TARGET MEMORY** follows a live reference only when its local target Context
   UID resolves uniquely, then renders the target's ordinary direct-Memory
   Trace as a distinct report. A snapshot reference retains its captured
   content and never reopens a live target. A missing live target remains a
   visible limit rather than being guessed.

Reference Rationale always renders that deterministic relationship and
occurrence provenance. When a live target is locally readable, it may also run
the existing target-Memory semantic provenance projection. Provider failure
does not discard the already proven relationship, and a snapshot reference
never connects a provider merely to reinterpret its retained copy. Neither
route opens query-only content.

An explicit qualified selector or a unique Profile-wide bare UID resolving to
a READ-granted Context may produce a different typed Trace: **CURRENT GRANTED
VIEW**. It shows the currently readable Memory,
the public Context name, owner Profile, Grant UID and revision, grantee,
resource, and effective permissions. Its history section is always
`HISTORY HIDDEN`: construction must not call the authority Profile's checkpoint
API. Granted Rationale shows the same access route and keeps its semantic
history projection provider-free and hidden. `mem log --memory` and other
retained-history controllers continue to reject the granted route.

This first slice deliberately does not create a local observation ledger for a
Grant. Consequently it can explain the current access path but cannot prove
when externally owned content changed between observations. A future version
would need an explicit `HISTORY`/`AUDIT` capability or a privacy-reviewed,
content-lifecycle-bound observation ledger; READ alone must not silently gain
either power.

In an interactive terminal, omitting `MEMORY` first opens the common session
picker as a Recents launcher. Recent rows are scoped to the current operation,
ordered newest first, and deduplicated by public Context name, Memory UID, and
exact-versus-descendant range.
The pinned `SELECT A MEMORY` action opens the common read-only exact/subtree
Context/Memory tree directly on the command-start current Context. Trace freezes
that ordinary local root and its lexical descendants. Rationale freezes the
Profile-readable local and READ-granted catalog for authorization, then projects
only the current public root and its lexical descendants into the target tree;
an unrelated readable Context is not an implicit alternative location. When the
operation has no recent rows, the empty Recents catalog is skipped and this
current-root target tree opens directly; no saved-session-shaped decision exists
in that case. An explicit `--context` bypasses Recents and anchors the same
target tree at that canonical Context. Selecting a different non-current root is
therefore an explicit CLI decision rather than a required first TUI step.

Recents are derived only from completed command-attempt records. A record
stores the operation, public or scoped Context name, Memory UID, and the
content-free descendant boolean; it never copies Memory content, inferred
rationale, Grant material, or provider data.
Trace Recents also include completed `mem log --memory` attempts because that
route reads the same Memory-lineage data.
Failed and cancelled attempts are not offered. Selecting a recent row freezes
and revalidates its command-attempt receipt, then enters the ordinary command
path, where current Context existence, UID resolution, and effective
permissions are checked again. A recent row is therefore navigation history,
not retained read authority or a report snapshot.

The shared target launcher begins with `THIS CONTEXT ONLY` and `INCLUDE
DESCENDANTS` projected through the common
`ContextReachState`, then the common Context/Memory tree. It begins on the
current or explicitly scoped Context row, including when that exact row and
its complete descendant range contain no Memory at all. Changing range and
choosing a Memory never changes global current Context state.
Rationale places every eligible Memory beneath its actual owner in the readable
public hierarchy; a Grant attachment is never treated as a hierarchy edge.
Trace may discover a Memory in a locally owned lexical descendant, but the
resulting lineage still opens only that exact owner Context's history. Context
rows are navigation only: Left/Right browse or collapse the tree, and Enter on
a Context leaves the picker open with the red textual receipt `CONTEXT NOT
SELECTABLE`. Only Enter on an exact Memory row can complete selection. This
explicit rejection prevents a Context cursor from being mistaken for a staged
Context-wide report target.

Immediately before report construction, Rationale refreezes and revalidates a
bare selection through the same Profile-readable namespace breadth, then
reprojects the reviewed root and range. It does not silently narrow a granted
root to a grant-only catalog after review. Trace likewise carries the canonical
selected local owner through its final history load; raw relative operands
never become picker or session identity.

The two controls are composed through the same service-wide terminal chrome,
not through an operation-owned Trace/Rationale shell. `RANGE` and `CONTEXTS &
MEMORIES` reuse `build_focused_frame`; their top-to-bottom layout reuses
`build_tui_frame`, and the shared terminal theme supplies the light-blue heavy
focused border and retained-choice fill. `SurfaceFocusController` owns
Tab/Shift-Tab, boundary-aware vertical movement, and Enter dispatch across the
two frames, while the existing reach and tree adapters retain their semantic
actions. The unscoped Context browser used by Switch retains its existing
single-surface presentation. This avoids manufacturing a parallel
picker merely to reproduce frame lines or focus color.

The target launcher freezes the current or explicit root's eligible descendant
catalog but starts with exact reach. It therefore remains open both when the
root has zero direct candidates and descendants do have candidates, and when
the complete exact-plus-descendant range is empty. Candidate absence is visible
selector state. Leaving the target selector cancels the command; it does not
insert or return to a second Context-location screen. A person who intentionally
wants another root can reopen with `--context NAME` without changing the global
current Context.

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
shows `[UID][r0]`, never a negative result produced by subtracting a synthetic
row. The compact `rN` badge means N recorded lineage-changing operations; it is
separate from the UID badge so the two values remain independently scannable.
`CURRENT` is omitted because it is the default state. Only an exceptional
retained-only row adds `[historical]`, yielding
`[historical][UID][rN]`. Its badge alone uses a muted warm taupe; UID, revision,
and Memory text retain the shared light lavender Memory-object color. Row focus
still replaces both colors with the shared blue treatment. A granted Rationale
row shows
`[UID][history unavailable]` rather than treating withheld owner history as
zero or deriving a count from current content. Up/Down, Left/Right,
held-arrow acceleration, and wrapped scrolling all come from the common Context/Memory selector rather
than a second operation-specific navigation grammar.

The picker renders the first eight UID characters as a compact identity badge,
but that badge is presentation only. It returns the exact root, owner Context,
descendant boolean, and full UID, then enters the same report-building path as
an explicit selector. Explicit CLI selectors continue to accept either that
full UID, an unambiguous prefix, or `CONTEXT:UID`; ambiguity is rejected rather
than guessed. The interactive picker and Recents deliberately remain a direct
Memory launcher in this slice. They do not perform per-row semantic inference
or open Memory references,
embedded Contexts, or query-only sources. `mem rationale` has no provider
connection before target selection and never sends the readable picker catalog.
After the full-screen picker
closes, the command reloads the direct Context before reconstructing the report
so it does not combine a pre-picker live frame with post-picker history.
The selected row names its recorded-change count before Enter: Trace covers
the full retained lineage from earliest retained evidence through the current
Context, while Rationale covers the selected Memory's source context,
derivation, and compact ordered lifecycle.
This shared target launcher is the interactive boundary
for choosing both reach and Memory; it does not silently broaden exact reach.

Rationale uses the full-screen target selector only when a target is omitted.
After selection it restores the ordinary terminal and prints one compact
receipt; an explicit operand prints the same receipt directly. Its usual
Memory-plus-lifecycle result does not justify a second Viewer or a close key.
Trace prints the bounded lineage document directly. Bare, recent, and explicit
targets share that result contract; selecting a target does not cause a second
automatic full-screen transition. The former compact receipt indirection and
`--plain`/`--tui` presentation switches are retired. JSON retains the complete
structured Trace and the validated bounded provenance projection.

The full document renders every visible newest-first operation as the same
typed compact History row used by Log, followed immediately by its inline `−
before` / `+ after` Memory diff. `NOW` and `ORIGIN` endpoint bands are
intentionally omitted: the newest diff's after side and the oldest visible
diff's before side already carry that state, while the shared `[command]
[CHECKPOINT …] [MEMORY …]  time · summary` grammar gives the operation the same
scan landmarks as Log. Historical Viewer component evidence remains useful for
the shared wrapped-row mechanics, but the direct Trace command no longer opens
that Viewer.
Rationale reuses the same target and Trace projection, then synthesizes only a
compact natural-language account grounded in that Trace; it does not inherit
Trace's owner-history authority when the target is granted.

Outside a TTY, omission fails instead of silently selecting a Context or the
first Memory;
automation must pass an explicit UID or prefix. `--json` also requires an
explicit selector so machine-readable stdout is never preceded by terminal
selection traffic. Escape, `q`, and Ctrl-C cancel the picker without changing
the store or connecting a provider. In a TTY, even an empty current Context
still opens its exact target range and offers `INCLUDE DESCENDANTS`.

By default, `mem trace` bounds its human projection to the newest twenty
lineage-affecting command units. `--limit N` selects another bound up to 200,
while `--all` explicitly requests the complete retained lineage. Truncation is
never silent: the heading states `SHOWING n OF total`, and a marker between the
visible operations and attachments names the exact older count omitted.
`--json` always keeps the complete report. Operations remain newest-first, but
compact transition detail is deliberately asymmetric. A direct Add or Remove
is one Log-style row because its action, Memory badge, and `created/removed
"content"` summary already name the only content-bearing endpoint; rendering
`− ∅` / `+ Memory` or `− Memory` / `+ ∅` would only repeat it. Edit,
restoration, reorder, and structural or mixed commands retain their forward
`− before` / `+ after` diff because the relationship between two states is the
information being requested. A direct Edit row therefore stops after its
timestamp instead of adding the generic `content changed · Memory identity
preserved`; its diff owns the content explanation. `--verbose` expands every
operation, including direct Add/Remove, for audit completeness.

The compact row also does not repeat `CREATED · RECORDED`, `EDITED · RECORDED`,
or another effect/evidence suffix after its already sufficient action and
summary. When that provenance distinction is needed, `--verbose` adds a
separate `Lineage:` detail such as `RESTORED/REMOVED · RECORDED`; JSON remains
authoritative.

Presentation groups events by retained command-unit receipt, then explicit
operation identity, with checkpoint UID only as the legacy fallback when no
stronger operation identity exists. Several events from one operation become
one row. Trace adapts that group to `HistoryDisplayRow` and both Log and Trace
consume `history_display_row_segments`; command, typed UID badges, timestamp,
summary spacing, and semantic action styling therefore cannot drift through
parallel format strings. Trace alone appends the lineage diff; verbose Trace
also adds typed effect/evidence detail because those are not properties of an
ordinary compact Context Log row.
Compact restoration rows filter before/after states to the selected
lineage because a command-unit receipt may describe other changed Memories or
Contexts. Multiline and control-bearing content is display-escaped inside each
wrapped Memory line. Checkpoint identity, descriptions, citations, complete
UIDs, and saved-analysis detail move to `--verbose`; `--json` keeps the
chronological structured event order for programmatic consumers. The TUI uses
the shared terminal palette: Memory objects remain lavender; typed
ADD/EDIT/REMOVE and restoration tokens carry their semantic roles; mixed
operations such as Atomize remain neutral while their child diff markers carry
the proven effect color. Stripping color leaves identical labels and ordering.

Thus the human-facing scopes remain distinct:

- `mem log` prints one Context's checkpoint states and restoration addresses;
- `mem log --memory` prints that retained history for one proven UID lineage;
- `mem revert` restores one reviewed checkpoint;
- `mem undo` and `mem redo` restore one global command unit;
- `mem trace` interactively inspects Log's Memory-lineage data projection; and
- `mem rationale` explains one Memory's retained origin context, derivation,
  and lifecycle as a compact natural-language receipt.

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
history is available and skips provider connection.

That no-provider boundary is based on reportable retained events, not merely
on a nonempty Trace event tuple. `HISTORY_GAP · UNRECORDED` remains visible in
Trace as evidence of a boundary, but it is not a retained provenance event. A
gap-only Rationale therefore returns an `EMPTY` projection with blank text and
renders `PROVENANCE — no retained history` without constructing a provider. If
recorded, reconstructed, or structurally inferred retained events precede a
gap, only those retained events and their latest retained state enter the
semantic turn. The live unrecorded state is omitted, while the Trace warning
and an explicit unrecorded-boundary marker tell the provider and the human
receipt not to infer the missing transition.

The default human Rationale projection is deliberately smaller than its
evidence model. It shows the selected **MEMORY** and one **PROVENANCE**
paragraph. For the motivating `practice/source` trace, the expected receipt is:

```text
“Um...” began as a hesitation between a minimal-change instruction and its
“distribute, not divide” example. Sentence chunking made it a standalone
Memory; undo removed it, redo restored it, and remove later deleted it.
```

The whole Trace component enters the initial provider call and, only after a
validated length overflow, the one allowed repair call. Parent and sibling
states may establish the origin context, but an event containing only sibling
UIDs is not narrated as a selected-Memory transition. The prose preserves
recorded chronology while omitting raw event labels, arrows, transition counts,
timestamps, checkpoint IDs, and an operation inventory. A textual role such as
`hesitation` is permitted when the selected wording and its placement support
it; `placeholder intent`, usefulness judgments, and unrecorded removal reasons
remain forbidden.

The ordinary human bound is 40 whitespace-delimited words. `--limit N` changes
the positive hard bound up to 100,000 and `--unit characters|bytes|words`
chooses the measurement. Every first draft receives the generalized preferred
target `max(1, floor(limit × 0.9))`: 40 aims for 36 words, 80 for 72, and 120
for 108, while a complete result between that soft target and the hard bound
remains valid. A structurally valid draft above the hard bound is not clipped
or published: Rationale sends its measured length, rejected draft, and the
complete frozen Trace through one freshly preflighted compression turn.
The repair uses the same provider snapshot, ruleset, schema, and decoder; a
second overflow fails closed. Invalid JSON, non-narrative text, transport
failure, and other errors do not trigger repair. Punctuation-only output and
null sentinels such as `/`, `null`, `:null`, and `undefined` likewise cannot
turn absent provenance into an apparently available receipt. JSON keeps the
complete typed Trace and the final validated `provenance_projection`, including
its ruleset version, hard bound, unit, and measured length.

Within that bound, discriminating evidence has an explicit priority. The
narrative first preserves short exact before-and-after excerpts, then the
material operation, Context movement, and selected-Memory lifecycle. Generic
purpose, justification, and `remains current and unchanged` prose are omitted
first. An excerpt must be a contiguous substring of retained content; it may be
shorter than the complete Memory but must not silently rewrite quoted wording.
This prioritization lets a split say what one parent became instead of spending
the receipt on an abstract explanation of why independent revision is useful.
For a long edit run, complete lineage means reading every event while expressing
each material chronological phase, not allocating one clause to every event.
Wording-only revisions collapse into the phase; every disappearance and return
stays ordered. Numeric positions are omitted unless changed order or neighboring
placement is itself necessary to understand the provenance.

### Versioned natural-provenance rules and exact cases

`application/operations/history_recovery/inspection/rationale/fixtures/rationale.json` is the sole authored Rationale ruleset.
`memcommit.rationale_rules` strictly checks its version, named rules, complete
Trace case shapes, exact expected narratives, linked rule IDs, bounds, and
known-wrong narratives. `rationale_ruleset_prompt_payload()` then places every
rule, exact case, and known-wrong boundary into every production Rationale turn,
matching Resolve's consumed-calibration structure. These are deliberately
`PROVIDER_VISIBLE`; they are regression or calibration contracts, never
independent holdout evidence.

The first exact case is the real `c9e05f9a` scenario: the complete longer source
instruction, the three sentence chunks, Chunk → Undo → Redo → Remove, and two
later sibling-only Atomize events. Its exact 33-word answer must preserve the
instruction/example origin context and selected lifecycle while excluding the
sibling events. A second case covers direct Add → Remove → Undo, and a final
authority case freezes the Grant-hidden no-provider boundary.

Ruleset version 2 adds three calibration cases selected from actual Rationale
receipts. They are not output-specific templates. Together they establish the
general operation grammar that a parent split becomes the selected and relevant
sibling results, a derived-then-edited Memory exposes its first retained content
before its replacement, and branch inheritance names origin and destination
separately from content change. The case inputs now include the selected Context
and retained Trace warnings because both are production evidence. A validated
Branch instead enters the event stream as a typed `BRANCHED` Context transition;
warnings remain evidence only for receipt-free or invalid legacy history and
must not be promoted into a recorded event. Prose still may not invent
unretained source content or an unrecorded reason.

The exact version-2 calibration outputs fit the ordinary bound: the real
Atomize parent-to-two-results case uses 38 words, Distill-then-Edit uses 27, and
branch inheritance uses 16. Before calibration, the same Atomize request
exceeded 40 words by spending budget on independently-revisable and unchanged
status prose; the Distill receipt abstracted the first Rule; and the inherited
Memory was described only as a direct Add. Production re-execution after the
ruleset update returned all three exact expected outputs within 40 words.

Ruleset version 3 adds a 15-event long-history calibration produced through the
real Add, ten Edit, Remove, Undo, Redo, and second Undo command paths. Before the
new rule, the ordinary 40-word and an expanded 60-word request both failed the
strict decoder; a 120-word request produced an accurate but event-enumerating
87-word paragraph. Version 3 keeps all 15 events in the production request but
collapses the edits into one material expansion/rewording phase and the four
presence operations into one ordered `remove–undo–redo–undo` clause. The actual
provider then returned the exact 37-word canonical paragraph under the unchanged
40-word default. Raising the default would have hidden the missing compression
contract and was therefore rejected.

Ruleset version 4 adds Source-selected and Target-selected Merge calibrations
from the `facility-updates → transform-scratch/source` failure. Context movement
now explicitly means distinct Source and Target occurrences, and a new Merge
disposition rule prevents `NEW` from sounding like a move, `ALREADY_PRESENT`
from sounding like a creation, `TAKE_SOURCE` from hiding replacement, or
`KEEP_TARGET` from claiming that Source content was materialized. The provider
receives the complete connected Trace with opaque Memory aliases and the typed
disposition, while exact durable UIDs remain in Trace JSON and the human Trace
row rather than being copied into generated prose.

Ruleset version 5 separates the generalized 90% first-draft target from the hard
acceptance bound and adds one explicit full-Trace repair for length overflow.
Its direct Add → Remove → Undo calibration now includes a grounded but rejected
41-word adjacent narrative and the exact 14-word compact result. The repair
draft is untrusted output, not new provenance evidence. Narratives such as the
existing 37- and 38-word exact cases remain valid under the 40-word hard bound;
missing a soft target alone never spends a second provider turn.

`tests/test_rationale_rules.py` proves that every authored item enters the
general production prompt, executes all eight available-history canonical cases
through the production payload/schema/decoder, carries Context and warnings,
keeps all 15 long-history events provider-visible, and rejects raw event chains.
It also proves generalized 90% target rounding, one 41-word-to-14-word
whole-Trace repair, one-call acceptance above the soft target, no retry for
malformed output, and fail-closed rejection after a second overflow.

#### `EXAMPLE-01` coverage

These rows apply the shared
[example contract](operation-example-contract-design-rationale.md). The exact
cases are both executable regressions and consumed production calibration;
they must not be counted as unseen evaluation evidence.

| Example ID | Boundary | Input form | Output variant | Exposure | Artifact and oracle |
| --- | --- | --- | --- | --- | --- |
| `rationale.provenance.um-origin-lifecycle` | whole Trace → semantic prompt/schema/decoder | real split child, parent source, undo/redo/remove, sibling-only events | exact 33-word natural provenance with origin context | `PROVIDER_VISIBLE` | ruleset case `um-sentence-chunk-lifecycle`; production-payload regression |
| `rationale.provenance.direct-restore` | whole Trace → semantic prompt/schema/decoder | direct Add, Remove, and Undo | compact chronological natural provenance | `PROVIDER_VISIBLE` | ruleset case `direct-add-remove-undo`; public-command integration test |
| `rationale.provenance.atomize-parent-results` | whole Trace → semantic prompt/schema/decoder | copied compound instruction, selected child, sibling child | exact source excerpt → two-result contrast within 40 words | `PROVIDER_VISIBLE` | ruleset case `atomize-parent-to-selected-and-sibling`; actual-command re-execution |
| `rationale.provenance.distill-edit` | whole Trace → semantic prompt/schema/decoder | Distill from named Source Context followed by Edit | exact first derived excerpt → current replacement | `PROVIDER_VISIBLE` | ruleset case `distilled-rule-then-edited`; actual-command re-execution |
| `rationale.provenance.branch-inheritance` | whole Trace + recorded Context transition → semantic prompt/schema/decoder | Add retained unchanged across a validated Branch receipt | origin → destination separated from content change | `PROVIDER_VISIBLE` | ruleset case `branch-inherited-unchanged-memory`; actual-command re-execution |
| `rationale.provenance.merge-source-use` | connected Source Trace + validated Merge edge → semantic prompt/schema/decoder | Move, Replace, then `NEW` Merge into a fresh Target UID | Source lifecycle followed by downstream copy while Source remains | `PROVIDER_VISIBLE` | ruleset case `merge-source-copied-to-fresh-target`; bidirectional Trace regression |
| `rationale.provenance.merge-target-origin` | connected Target Trace + validated Merge edge → semantic prompt/schema/decoder | fresh Target UID selected after Source Move and Replace | Source history followed by this Target occurrence's creation | `PROVIDER_VISIBLE` | ruleset case `merge-target-inherits-source-history`; bidirectional Trace regression |
| `rationale.provenance.long-material-phases` | 15-event whole Trace → semantic prompt/schema/decoder | Add, ten Edits, Remove/Undo/Redo/Undo | exact 37-word origin → material edit phase → presence-cycle narrative | `PROVIDER_VISIBLE` | ruleset case `long-edit-run-with-remove-undo-redo`; isolated actual-command re-execution |
| `rationale.provenance.grant-hidden` | readable granted Memory → application receipt | owner history unavailable | `hidden by Grant`, zero provider calls | `HOST_ONLY` | ruleset case `grant-hidden-history`; authority test |
| `rationale.provenance.decoder-chain-rejection` | provider response → strict decoder | raw event-label arrow chain | rejected as non-narrative | `HOST_ONLY` | `test_provider_output_must_be_complete_narrative_within_the_exact_bound` |
| `rationale.provenance.overflow-repair` | initial response + same whole Trace → repair prompt/schema/decoder | grounded 41-word Add/Remove/Undo draft above a 40-word hard bound | exact 14-word compact provenance, with the first draft unpublished | `PROVIDER_VISIBLE` | ruleset case `direct-add-remove-undo`; `test_over_limit_draft_gets_one_complete_trace_length_repair` |
| `rationale.provenance.second-overflow-rejection` | repair response → strict decoder | second complete-looking paragraph beyond the requested unit | rejected without clipping or a third turn | `HOST_ONLY` | `test_length_repair_runs_at_most_once` |

The [180×52 compact Rationale capture](screenshots/mem-rationale-compact-20260820/README.md)
records target selection, the direct natural-provenance receipt, and read-only store
verification.

The [180×52 Merge lineage capture](screenshots/mem-merge-lineage-trace-20260823/README.md)
records the actual task-1 Source and Target UID routes, the complete
Move/Replace/Merge chain, and a plain read-only verification with the current
Context unchanged.

The focused capture verifies the 180×52 color selector, the ordinary one-turn
under-limit path after target confirmation, the compact receipt, and read-only
store verification. The overflow repair has no intermediate TUI state and is
therefore an exact prompt/decoder contract rather than a synthetic screen.
No path reads or writes the legacy contextual-inference cache, and Context
content remains unchanged.

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
Current Context-scoped Chunk checkpoints instead record every exact Source UID
and ordered child-UID list; Trace reports those relations as `RECORDED` only
after the complete identity map, order, method, optional literal/size controls,
and reproduced contents agree.

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

## Retired Context inference design

Earlier prototypes added a provider-created contextual interpretation after
provenance. That route is now retired: the CLI neither freezes neighboring
Memory candidates nor connects a provider, and it never renders an inferred
purpose. The details below are retained as design history for the still-readable
legacy cache format and tests; they do not describe current `mem rationale`
execution.

The inference layer is called **inference within the current Context**, not
“surrounding-context inference.” The interpretation frame is all directly owned
ordinary Memories in that Context when it fits the input limit. Order and
distance provide cues; they do not define the evidence boundary. Only an
explicit size limit may reduce the frame, and that reduction must be reported.

The provider receives opaque candidate IDs and must cite only allowlisted IDs.
Unknown or duplicate IDs invalidate the response. It returns one paragraph
that combines the best-supported ordinary reading, its contextual flow, and
what remains unresolved. The request schema carries the dynamic character
limit described above. Validation NFC-normalizes the explanation and rejects
an over-limit result, a line or control break, or a second output field that
could recreate the former multi-section explanation. A shorter paragraph
remains valid when the frame supports only a narrow statement. The paragraph
cannot claim to recover the author's actual intention or the historical reason
the Memory was created.

### Follow-up example design TODO

Do not add prompt examples until representative cases and expected artifacts
are chosen together. For each case below, create one minimal Context fixture,
one expected paragraph below that fixture's dynamic character limit, one
assertion identifying which supplied Memory IDs may support it, and one compact
terminal capture paired with JSON evidence verification:

- unchanged Memory with a clear local reading and no material uncertainty;
- edited Memory whose current wording differs from its earliest retained form;
- split or absorbed lineage where the provenance paragraph must express the
  structural transition without inventing a semantic cause;
- historical-only or removed Memory whose current lineage endpoint is absent;
- locally supported reading with one concrete unresolved referent, boundary,
  or exception;
- insufficient local evidence that skips provider connection, provider
  failure, and rejected over-character-limit or multi-paragraph output;
- current saved analysis or an unapplied proposal that remains visible in JSON
  but is not repeated in the compact human report;
- granted READ and readable-descendant scopes, including hidden authority
  history and size-limited candidate frames.

The examples should be selected for boundary coverage, not copied into the
prompt merely to improve prose style. NFC code-point length is deliberately
language-neutral; grapheme or display-cell limits remain a separate evaluation
question.

For a historical UID that is no longer present in the current frame, rationale
still uses the current directly owned Memories as its interpretation frame. It
anchors distance to the historical position retained for the target. After a
reorder or a one-to-many split, that numerical neighborhood is only an
approximation; it does not reconstruct the neighbors that surrounded the
Memory at the historical moment. The full-frame inference may still cite
relevant current Memories, but “nearby” fallback output must not be read as
historical provenance.

The retired route excluded stale ambiguity reviews from provider evidence. The
current route does not inspect reviews when constructing human prose.

## Legacy Context-inference cache

Current Rationale neither reads nor writes this cache. The format remains
loadable because existing search artifacts and Context-deletion cleanup may
encounter records written by an earlier prototype. Keeping compatibility is a
data-lifecycle boundary, not an invitation to resume inference implicitly.

The retired writer cached only validated provider-created `ContextInference`,
not the complete `RationaleReport`. Current receipt construction still rebuilds
trace events from live local state on every invocation.

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

The version-3 cache persists only the validated, NFC-canonical single-paragraph
explanation and the supporting ordinary Memory UIDs. Version-1 multi-field and
version-2 word-budget entries are ordinary cache misses rather than migration
inputs. Explanation text can quote or paraphrase
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

The retired writer ran provider work without holding a long Context lock and
briefly revalidated the Context before publication. Current Rationale has no
equivalent publication path.
Deleting a Context preflights and removes its inference subtree because the
derived explanation shares the source Context's privacy lifetime.

## Readable subtree Rationale and Study Trace boundary

Rationale does not perform a semantic search across arbitrary sibling or global
Contexts. Exact-versus-descendant reach controls only which Memory may be
selected from the shared readable public namespace. Once selected, report
construction starts from that exact owner. It may read same-Store local
checkpoint receipts to follow a validated Branch or Merge edge, then includes
only the owners and Memory occurrences in that connected Trace component; text
similarity, namespace proximity, and an unrelated readable sibling never join
the component. The public name, not the Grant attachment, still determines
picker hierarchy.

A granted READ view permits the current Memory projection but does not imply
authority to inspect the source Profile's checkpoints, command receipts, saved
reviews, or atomize attachments. Granted Rationale therefore labels provenance
`hidden by Grant` and never connects a provider. An explicit granted Trace may
show only the current Memory and typed access route; its retained-history
section remains hidden and its construction never calls the owner checkpoint
API. A locally owned target sends only its receipt-connected Trace component
after selection; it does not send the picker's readable catalog or unrelated
neighboring Contexts. Same-Profile ordinary local history inspection is not a
Grant-derived `COMBINE` route. Cross-Profile and granted Merge paths do not
publish the local lineage receipt and therefore cannot use this expansion.

Every locally owned ordinary Context may inspect its own retained history,
including every task namespace in a composed participant Study run. Task names
are research organization, not an authority primitive. Granted READ remains
different: it exposes the reviewed current content projection but not the
authority Profile's checkpoints, command receipts, or saved history artifacts.
Only Grant rows therefore need a visible `TRACE BLOCKED` analysis boundary;
that existing compact label means retained Trace history is blocked, not that
the new current-access report is unavailable. Local Study rows no longer
repeat task-dependent Trace annotations. Renaming this shared TUI label is a
separate presentation migration because its recorded interaction snapshots
must change atomically with the visible flow.

The executable request does not preserve the selected range as an inference
scope. Its only multi-Context expansion is a validated occurrence graph, which
prevents provenance lookup from becoming a hidden namespace-wide disclosure
operation while still explaining an exact recorded Merge use.

## Query-only boundary

Trace, rationale, atomize preview, and both apply modes never open a
`QueryContextRef` source. The public pointer can be retained in a derived
Context, but concealed source text is not trace evidence, provenance evidence,
an atomize candidate, or a copied Memory.

This is a tested command-path invariant, not operating-system confidentiality.

## Context as a report subject

An explicit positional existing Context is a complete Trace or Rationale
subject. This is not descendant selection and does not collapse the Context
into one synthetic Memory. `mem trace CONTEXT` projects every retained
checkpoint operation, every direct-Memory change under that operation,
zero-change checkpoints, any final unrecorded live-state gap, and the current
direct state. Its primary axis is the Context's operation chronology; the same
mechanical Memory diff renderer may be reused inside an event without changing
that subject.

The positional grammar remains typed and backward compatible. An existing
Context name wins; a bare UUID-shaped value remains a Memory selector;
`CONTEXT:UID` and `UID --context CONTEXT` remain exact Memory coordinates. A
non-UUID value that is not an existing Context fails as a Context locator and
may show canonical `Did you mean?` candidates from the frozen visible catalog,
but similarity never selects a target. Omitting the positional operand keeps
the established Memory-selection flow.

`mem rationale CONTEXT` applies `WHOLE_FRAME_ONLY` semantic execution to that
complete Context Trace. It explains material evolution rather than summarizing
current content, and it may attribute a reason only when a recorded command,
description, or before/after relationship supports it. Checkpoint order alone
does not prove intent. An authority-owned local Context can expose retained
history; a granted READ view can expose only current content and must return a
hidden-history projection without connecting a provider.

Context Trace reads one bounded lineage document and does not open a checkpoint
picker: browsing a sequence of pairwise checkpoint results would duplicate
Diff's subject instead of presenting the Context-wide time axis. Diff remains
the exact one-checkpoint-versus-predecessor inspection tool.

## Alternatives rejected

- **Text-similarity lineage:** rejected because equal wording does not establish
  derivation.
- **Treating preview as history:** rejected because analysis can be stale or
  never applied.
- **Using a model to fill missing provenance:** rejected. The semantic turn may
  express only retained Trace evidence; absent or Grant-hidden history skips
  provider connection instead of asking for a plausible origin.
- **Copying all source checkpoints into save-as:** rejected because the new
  Context needs a clear local baseline, not inherited history with the wrong
  Context identity.
- **Putting raw source metadata into every Memory:** rejected to keep Memory
  minimal and operation provenance centralized.
- **Keeping current-purpose inference beside provenance:** rejected because a
  present-day usefulness judgment competes with the historical question. The
  active semantic turn is instead constrained to natural-language expression
  of the complete retained Trace.

## Remaining limitations

- Checkpoints are whole-Context snapshots rather than a canonical event ledger.
- A Context with no retained checkpoint has no provable creation boundary; its
  current Memory can be the earliest observable lineage state.
- `RECORDED` metadata is structurally checked but unsigned and therefore not
  tamper-evident.
- Old branch histories can retain source Context identities without a recorded
  branch-creation event. Trace reports one limit per unexplained Source owner;
  it cannot backfill a typed Context transition without a valid receipt.
- Legacy operations without explicit trace metadata may be reconstructable only
  at a coarse level.
- Only the latest atomize analysis per Context UID is retained. A later preview
  can replace preview-only evidence that was not copied into an apply
  checkpoint.
- Literal source-span validation does not independently prove full semantic
  entailment of a generated child.
- Bare interactive selection reconstructs the retained history once to build
  its candidate catalog and again after selection to produce a fresh report.
  This favors one authoritative selector domain and post-picker freshness over
  caching private frame objects; very large retained histories can therefore
  make the interactive path slower than an explicit UID.
- MemoryRef and granted-current reports are explicit-selector, plain/JSON
  routes in this slice. They are not added to Recents, the interactive picker,
  or the read-only Trace Viewer.
- A granted-current report has no local observation ledger. It cannot prove
  when or why an owner changed content outside the grantee Profile; READ shows
  current content and the access route, while retained history remains hidden.
