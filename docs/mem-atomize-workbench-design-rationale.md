# `mem atomize` workbench design rationale

## Status

This document records the **implemented user-facing contract** for the
interactive atomize workbench. It preserves decisions reached while evaluating
the Task 1 prototype, including the reasons for individual screen elements and
the alternatives that were rejected. Deferred extensions are listed
separately; they are not implied by the implemented screen.

## Decision summary

Atomization is not adequately reviewed by reporting only how many Memories
were classified or created. The user needs to establish that Mem understood
the source, see how its structure would change, and resolve the limited set of
problems that could change the proposal before any Memory is mutated.

The implemented workflow is therefore:

```text
mem impact atomize
    -> create or resume one stable analysis
    -> show an overview of understanding and transformation
    -> inspect and answer actionable issues

mem atomize
    -> create the first analysis if none exists, otherwise resume the saved one
    -> do not silently generate a different proposal

mem review atomize
    -> resume the same saved review position and responses

mem review
    -> compatibility resume when no older global review owns that command

mem atomize --save
mem atomize --save-as NEW_CONTEXT
    -> apply the reviewed analysis explicitly
```

`mem impact atomize` is the primary discovery entry point because the risky
questions occur before application: Did the operation understand the source?
What will it split? What remains unclear? `mem atomize` is also allowed as a
convenient entry point, but it must join the same compatible saved analysis
rather than creating a second proposal merely because a different command was
used. `mem review atomize` is a compatibility resume surface, not the
conceptual owner of atomization. Bare `mem review` may reach the workbench only
when no older global review is active.

Opening, closing, taking a snapshot of, or re-entering the workbench does not
rerun the semantic provider. A new model completion is permitted only through
`mem impact atomize --refresh` or the reviewed reanalysis boundary
`mem impact atomize --with-review`. An ordinary resume shows the same proposal.

## Why a workbench is needed

The first atomize preview reported results such as:

```text
51 direct Memories -> 61 projected
14 atomic, 7 composite, 15 uncertain, 15 non-propositional
7 proposed splits -> 17 children
```

Those numbers describe scale, not semantic quality. They cannot show whether
an access exception disappeared, whether an unresolved pronoun was guessed,
whether a replacement service was preserved, or whether a composite Memory
was split along useful revision boundaries. Reading every proposed child
would answer those questions, but would make the preview equivalent to
reviewing the entire source again and would not scale to a book-sized import.

The workbench therefore combines:

1. one compact cardinality line;
2. a content-oriented account of what Mem understood;
3. a transformation-oriented account of what changed and remains unresolved;
4. one overview list of actionable issues; and
5. a typed detail view for the selected issue.

This is intended to provide enough evidence for a user to notice a serious
omission or misreading without requiring them to inspect every unchanged
Memory.

## Stable analysis and resume contract

### One analysis, several entry points

The analysis, not the CLI spelling, is the stable object under review.
`impact atomize`, `atomize`, and `review atomize` may present different
entry-point affordances, but they resolve to the same compatible analysis and
saved workbench state.

The persisted workbench is bound to:

- the selected Context's stable UID and name;
- a digest of directly owned Memory UIDs, contents, and canonical order;
- the exact atomize analysis identity;
- the exact issue identities derived from that analysis;
- the current issue cursor and presentation order;
- selected choices and verbatim reviewer responses; and
- enough provenance to identify which analysis was eventually applied.

The current schema stores one latest immutable analysis and one mutable
workbench per Context UID:

```text
~/.mem/atomize-analyses/<context-uid>.json
~/.mem/atomize-workbenches/<context-uid>.json
```

Their exact analysis UID, Context digest, issue projection digest, choice
identities, cursor, sort mode, layout, and responses are validated on load.
A refreshed analysis replaces the latest-analysis slot and creates a fresh
workbench. A revision archive is deliberately deferred.

The initial analysis is one aggregate provider completion. The same response
contains the atomize classification and proposed children for every direct
Memory, the three source-linked overview sections, and typed ambiguity and
conflict issues. The workbench therefore does not launch separate semantic
calls for its summary, issue list, or first detail view.

The concrete one-shot Codex provider receives a five-minute timeout for this
aggregate operation only. The shared two-minute default timed out on the live
51-Memory Task fixture because the request also included the complete bounded
pair frame. Extending every semantic command was rejected: a slow unrelated
query or finder should still fail on its ordinary boundary. The larger window
does not add retries, provider calls, or a guarantee that an arbitrarily large
analysis will finish.

### Two evidence frames must not be conflated

The aggregate completion performs two judgments with deliberately asymmetric
evidence:

- atomize classification remains source-local because neighboring Memories
  cannot become unrecorded child evidence; and
- ambiguity/conflict uses the complete selected Context as its bounded ordinary
  reading frame.

An `UNCERTAIN` atomize result therefore does not imply an ambiguity card. Before
emitting ambiguity, the quality scan must resolve ordinary antecedents,
ellipsis, deixis, and shared scope against every supplied Memory. If the
Context gives one usable reading and no operational decision changes, the
result is clean `SINGLE/NONE` and is omitted. `SINGLE/REQUIRED` remains valid
only when the complete Context still lacks information needed to perform or
reliably verify an explicit operation.

This boundary was added after the first aggregate Task 1 run produced 47 cards:
21 ambiguity, 4 conflict, 15 atomize uncertainty, and 7 split. Every uncertainty
source also received a same-source ambiguity card, showing that the provider
had copied its source-local judgment into the Context-wide scan. A contrastive
calibration case now pairs “the main entrance closes at 5” with “after that
time, a student card is required”; the latter may remain source-locally
uncertain for atomization while being clean for Context-wide ambiguity.

The corrected live rerun produced 25 cards: 5 ambiguity, 1 conflict, 12
uncertainty, and 7 split. Same-source unary overlaps fell from 17 to 2 without
an arbitrary result cap or a storage migration. The remaining two contain
distinct work: one combines a live card/app reading question with a source-local
atomization boundary, and one combines a real split proposal with a missing
relocation destination. If future use still finds those two-card sources too
dense, the next step is a provenance-aware compound card, not silently hiding
one result.

### Staleness is not reanalysis

If the Context UID, direct Memory content, or canonical direct-Memory order no
longer matches the saved analysis, the workbench is stale. It must fail
closed and explain that the source changed. It must not quietly call the
provider and replace the screen with a new result.

This distinction matters because semantic providers are not assumed to be
deterministic. Two plausible runs can propose different children, reasons, or
issue sets. If reopening a screen silently reruns the provider, the user can
no longer tell which proposal they reviewed or which one `--save` will apply.

### Explicit reanalysis

Adding a clarification or comment changes the evidence available to a future
analysis, but must not retroactively alter the currently displayed proposal.
The intended sequence is:

```text
save reviewer evidence
    -> explicitly request reanalysis
    -> create a new, identifiable analysis
    -> show the new overview, proposal, and issues
    -> review
    -> apply explicitly
```

There are two explicit reanalysis paths:

```text
mem impact atomize --refresh
    -> unframed reanalysis

mem impact atomize --with-review
    -> reanalysis with eligible unary workbench responses as declared frames
```

They cannot be combined. Both create a new analysis identity and a fresh
workbench. The current prototype does not archive the replaced analysis or
render a revision-to-revision diff; that is separate future work. Silent rerun
is rejected regardless.

## Overview screen

The first screen should be an overview, not the detail page for issue 1.
A representative shape is:

```text
MEM IMPACT · ATOMIZE · temp/task-1

51 source Memories -> 61 projected
7 proposed splits -> 17 children

WHAT MEM UNDERSTOOD
The notes describe a summer building closure affecting entrances, parking,
routes, stores, dining, visitor services, restrooms, and event reservations,
while preserving staff-access and elevator exceptions and identifying
replacement services elsewhere on campus.

WHAT CHANGED / REMAINS UNRESOLVED
Compound notes were separated into independently revisable closures,
exceptions, alternatives, and continuing services. Unresolved expressions
such as "the same NFC," "after that time," and "this building" were retained
without guessing their referents.

ISSUES · 0/4 answered                             ORDER: SOURCE
> 1. AMBIGUITY · DOMINANT/REQUIRED  "the same NFC..."
     ↳ R1 [DOMINANT] The previously described NFC mechanism applies.
     ↳ R2 [ALTERNATIVE] The previous credential rule also applies.
  2. CONFLICT · MAY                  [...] <-> [...]
     ↳ R1 [COMPETING] Both claims govern the same entrance.
     ↳ R2 [COMPETING] The claims govern different entrances.
  3. ATOMIZE SPLIT                   "The store closes..."
  4. ATOMIZE UNCERTAINTY             "after that time..."
```

The exact wrapping and decoration may vary between terminal widths. The
information hierarchy must remain stable.

### Cardinality line

The count line exists because users still need an immediate sense of scale:
how many source Memories were considered, how many results are projected, and
how many splits and children are proposed. It should remain compact because a
count cannot establish correctness.

The count is a navigation and workload signal, not a quality score. A large
increase is not automatically good atomization, and an unchanged count does
not prove preservation.

### `WHAT MEM UNDERSTOOD`

This block answers the user's first semantic question: "What content did the
operation think was here?" It summarizes the source's major commitments,
including opposite-direction information such as closures and exceptions,
replacements and unavailable services, or restrictions and continuing access.

It exists because transformation rules and example splits can look reasonable
even when a whole subject area was omitted. A concise content account lets the
user detect that omission without reading every result.

The provider is instructed to target a short paragraph, roughly 40-50 English words for
the Task 1-sized fixture, rather than treating a word count as a semantic
invariant. Each overview section cites one or more source Memory identities.
The snapshot keeps those citations collapsed; the saved analysis retains them.

The block must not:

- add a fact absent from the declared evidence;
- turn an unresolved expression into a confident assertion;
- describe only closures while omitting important exceptions or alternatives;
- substitute a list of atomization rules for a summary of the content; or
- claim independent verification merely because the proposal model generated
  the summary.

### `WHAT CHANGED / REMAINS UNRESOLVED`

This block answers a different question: "What did atomization do to that
content?" It identifies meaningful structural changes, such as separating a
closure from its replacement service or preserving a condition with the claim
it scopes. It also names expressions that could not safely be resolved from
the current Context.

It exists because the content summary alone can be correct while the proposed
split is poor. Conversely, a list of split counts cannot explain whether
scope, exceptions, or relations were preserved.

An unresolved referent is not permission to invent a repair. If the operation
cannot identify what "that door," "the same NFC," or "during that period"
means from its declared evidence, it must retain the source and surface the
uncertainty. This gives the user an actionable next step without losing the
original wording.

Meaning loss is not an ordinary transformation category to be reported
alongside "split" or "preserved." No-loss is an invariant. If the operation
detects or cannot rule out a material omission under its validation contract,
application must be blocked or the source retained; the UI must not normalize
loss as an acceptable outcome.

As with the understanding block, this paragraph should be concise and
traceable. The exact hard word limit is deferred.

### `ISSUES`

The overview lists every actionable issue before forcing the user into any
one detail. This lets the user understand the size and shape of the review,
choose where to begin, and return a useful remote snapshot even when no
interactive terminal is attached.

The default issue list should include:

- proposed splits whose result needs inspection;
- atomize uncertainties that block or qualify a proposal;
- ambiguity findings relevant inside the analyzed Context;
- conflict findings relevant inside the analyzed Context; and
- any other explicitly typed, actionable boundary finding added later.

Unchanged, clearly atomic Memories do not need one card each in the default
view. They remain accounted for in the counts and should be inspectable through
an explicit "show all" mode. This is information-density control, not deletion.

Each issue has a durable answered/unanswered status. Returning to the
workbench must restore that status and the current item.

When an ambiguity or conflict already has saved ordinary readings, the issue
list exposes their role and a short text preview beneath the source row. This
lets a reviewer see the model's actual alternatives before opening the detail
panel; a type and source label alone cannot show whether the distinction is
useful. At most two readings are previewed in provider order, followed by an
explicit remainder count when more exist. Each preview is independently
shortened, so one long option cannot hide the next. Long previews retain both
the opening claim and the trailing qualifier around an ellipsis; preserving
only the beginning can hide the very condition that distinguishes two
readings.

These previews are deliberately lossy navigation hints. The full reading text,
choice identity, and selection control remain authoritative in the detail
panel. The list uses only persisted `AtomizeReading` values: it does not turn
an uncertainty reason or proposed split child into a fabricated reading. This
is a rendering change only and therefore does not alter the analysis,
workbench digest, provider-call boundary, or saved review state.

## Ordering

### `SOURCE`

`SOURCE` is the default order. In the current Memory model, it means canonical
direct-Memory order from `Context.order`.

It must not be called chronological order. `Memory` does not currently record
a creation timestamp, and checkpoint times, UUID values, JSON dictionary
order, or grouped `mem ls` output are not valid substitutes. `Context.order`
is used because it is explicit, reproducible, and corresponds to the order in
which the current source frame is encountered.

True creation-time order requires a timestamp field, migration behavior for
older Memories, and branch/merge semantics. That work is deferred.

### `PRIORITY`

The shell may toggle to `PRIORITY`. For ambiguity, the first available
ordering signal is:

```text
REQUIRED -> HELPFUL -> NONE -> Context.order
```

This reflects whether clarification can change or is necessary for an
operational result. It does not claim to measure the number of downstream
Memories affected.

Ranking by concrete downstream impact remains desirable, but requires
structured result identities and counterfactual re-evaluation for each
reading. Until those dependencies exist, the UI must not invent an
`AFFECTED 5` count or use generic topics such as `access` and `parking` as if
they were measured consequences.

## Typed issue contracts

The visual shell is shared, but issue semantics must not be flattened into one
generic `UNCERTAIN / RECONCILE` record. Source arity, evidence, choices, and
future application differ by issue type.

### Atomize split

An atomize-split issue has:

- exactly one source Memory;
- two or more ordered proposed children;
- the atomize classification and reason codes;
- a concise reason for the boundary;
- source evidence spans for every child; and
- any declared-frame evidence shown separately from original-source evidence.

The detail view must show the original and the proposed children together so
the user can inspect coverage, scope, and revision boundaries. Showing only
`COMPOSITE / SPLIT` does not reveal what will actually be stored.

The exact action vocabulary for accepting, refining, retaining unsplit, or
deferring a split has not yet been agreed and must not be accidentally frozen
by a generic UI implementation.

### Ambiguity

An ambiguity issue has exactly one source Memory and retains two independent
judgments:

```text
interpretation: SINGLE | DOMINANT | COMPETING
clarification: NONE | HELPFUL | REQUIRED
```

The first axis describes the structure of ordinary readings. The second
describes whether clarification changes or is needed for the task. They are
not one confidence score and must remain separately visible.

Proposed readings are displayed in English for cross-language comparison,
while the source is displayed verbatim in its original language. Presentation
roles are derived as:

| Interpretation | Reading labels |
|---|---|
| `SINGLE` | `[SINGLE]` |
| `DOMINANT` | first `[DOMINANT]`, later `[ALTERNATIVE]` |
| `COMPETING` | each `[COMPETING]` |

### Conflict

A conflict issue has exactly two source Memories and an actionable conflict
judgment:

```text
YES | MAY
```

Both sources must be visible. `MAY` means that ordinary readings can change
whether the two claims conflict; it is not merely low model confidence.
Collapsing a pair-shaped finding into one source loses the evidence needed to
understand or resolve it. Non-conflicting (`NO`) pairs are omitted from the
actionable issue list.

A response to a conflict remains staged with that two-Memory issue. It is not
converted into a declared frame for either source during
`mem impact atomize --with-review`; doing so would destroy its pair-shaped
meaning. Because the prototype retains only one workbench revision per
Context, `--with-review` fails before calling the provider whenever any
answered pairwise issue is present. Replacing the workbench while merely
skipping that answer would lose evidence. The answer therefore remains in the
current workbench for a future reconcile operation.

### Atomize uncertainty

An atomize-uncertainty issue has exactly one source Memory, the reason that
atomization cannot safely decide its boundary or scope, and a place for the
reviewer to supply clarification evidence.

It is not the only atomize issue type and must not become an adapter that hides
all split, ambiguity, and conflict findings. A response is staged evidence for
explicit reanalysis, not an immediate rewrite of the Memory.

One Memory can have both an ambiguity issue and an atomize-uncertainty issue.
The current provenance record binds a declared frame to one exact issue UID.
If both unary issues are answered, reviewed reanalysis fails closed rather
than concatenating their texts and falsely attributing the result to whichever
issue happened to appear first. The reviewer must consolidate the exact
context into one response and clear the other. Supporting multiple structured
origins would require a later provenance-schema revision.

### Future issue types

Update, reconcile, distill, meld, and sever may reuse the list, detail, choice,
and response controls. They must define their own arity, evidence, mutation,
and trace contracts before being added. Visual similarity is not permission
to erase operation-specific semantics.

## Detail screen

A selected ambiguity might render as:

```text
AMBIGUITY 1/4

SOURCE [uid]
The same NFC is used, but only staff may enter.

CLASSIFICATION
DOMINANT · REQUIRED

WHY THIS IS UNCLEAR
"the same NFC" can refer only to the previously described mechanism or also
to its credential policy. The accepted credential and authorized audience
cannot therefore be determined reliably.

READING OPTIONS
> 1. [DOMINANT] The door uses the previously described NFC mechanism.
  2. [ALTERNATIVE] The same credential and permission rule applies.

REFINE, COMMENT, OR ENTER A DIFFERENT READING
> ________________________________________________________________
```

### Original `SOURCE`

The source exists so the reviewer can detect whether the model misunderstood
the actual wording. It must be displayed verbatim rather than silently
translated or normalized. The number of source blocks follows the typed issue
arity: one for ambiguity and atomize, two for conflict.

### Proposed result

For a split, the proposed children and their evidence must be visible. For an
ambiguity, the proposed readings must be visible. For a conflict, both source
claims and the scope of the possible conflict must be visible. A generic
reason without the proposed result cannot support an informed decision.

### `CLASSIFICATION`

Classification makes the semantic judgment inspectable instead of burying it
in prose. It also supports priority ordering and later regression tests.
Operation-specific labels must remain operation-specific.

### `WHY THIS IS UNCLEAR`

The explanation must say:

1. exactly which readings, referents, scopes, or claims are in tension; and
2. what judgment or proposed result cannot be determined because of that
   uncertainty.

This combines the earlier "why unclear" and "why it matters" requirements
without adding a generic topic list. For `REQUIRED`, it names what cannot be
decided reliably. For `HELPFUL`, it names what can proceed and what would
become more precise. For `NONE`, it explains why the operational result does
not depend on the remaining readings.

### Reading or action choices

Structured choices make keyboard review efficient and preserve what the model
actually proposed. They do not replace freeform clarification. Choices must be
typed for the issue: readings for ambiguity, and a separately agreed action
set for atomize splits.

### One unified response field

The shell has exactly one freeform field:

```text
REFINE, COMMENT, OR ENTER A DIFFERENT READING
```

A reviewer may select the dominant reading and add a condition in the same
answer, for example:

```text
The first reading is correct, but access at this door is restricted to staff.
```

Separate "refine" and "different reading" fields force the user to classify an
answer that can legitimately do both. Treating "enter exact context" as
another numbered reading is also wrong: selecting a proposed interpretation
and supplying new evidence are independent actions and may occur together.

The selected choice identity and the response text must therefore be stored
separately. The text is preserved verbatim; the system must not guess whether
it was a refinement, comment, replacement, or new canonical Memory.

## Terminal and remote interaction

The implemented prompt-toolkit interaction is:

- left/right: previous or next issue;
- up/down or digits: select a reading or other typed choice when available;
- Enter or Tab: focus the unified response field;
- Escape or Tab: return to issue navigation;
- F2 or Ctrl-S: save the current response and move to the next issue;
- `S`: toggle `SOURCE` and `PRIORITY`;
- `L`: toggle split and stacked layouts; and
- `Q` or Ctrl-C: save and close.

Split and stacked layouts are two presentations of the same state, not two
review models. Cursor, choices, and responses must survive a layout switch.

A stable, non-interactive snapshot is part of the contract. It lets a remote
or non-TTY controller show the current overview or selected detail without
inventing a second textual representation. `mem impact atomize`,
`mem atomize`, and `mem review atomize` print that snapshot when they are not
attached to a TTY; `mem review atomize --snapshot` requests it explicitly.
Snapshot generation does not mutate a Context or rerun the provider.

In a Codex-controlled session, a user may say "right," `->`, "choose 4," or
`answer "..."`. The controlling agent observes the current snapshot,
translates that instruction into concrete PTY key events, and returns the new
snapshot. `mem` itself should not implement a Korean- and English-specific
natural-language command parser. Such a parser would be brittle, duplicate
the controller's interpretation, and confuse issue numbers with choice
numbers.

All provider-produced and stored strings are terminal data. Control characters
must be neutralized before rendering so that source text, reasons, readings,
or responses cannot inject terminal behavior.

## Evidence and no-loss boundaries

### Source grounding

Every proposed child must retain literal evidence from its own original source
Memory. A reviewer-supplied declared frame may support a referent or qualifier,
but it is recorded separately and must not create a frame-only child. The
current compact detail view combines cited spans under `EVIDENCE`; the saved
analysis, `mem trace`, and `mem rationale` preserve the source/frame
distinction. Neighboring Memories are not hidden evidence unless a future
contract explicitly declares and traces such a frame.

Overview summaries and transformation descriptions also require trace links.
A link proves where a claim came from; it does not independently prove that
the proposal model interpreted it correctly. Independent semantic validation
remains a distinct boundary.

### No silent loss

Atomization must preserve:

- every source commitment occurrence, including repeated occurrences;
- audience, place, time, modality, negation, conditions, and exceptions;
- focal relations such as alternatives, transitions, comparisons, and causes;
- meaningful non-propositional material as addressable content; and
- unresolved source wording when the evidence is insufficient.

If the operation classifies reconstruction as unsafe, the source remains
unsplit and the issue remains actionable. The UI must not hide a detected
omission behind a favorable projected count or fluent summary. The current
one-shot proposal plus structural validator is not an independent semantic
proof that every possible omission was detected.

### No mutation before apply

Analysis, review, sorting, cursor movement, choice selection, response entry,
snapshot generation, and explicit reanalysis must not edit Context Memory
content or create a Context checkpoint. Only explicit `mem atomize --save` or
`--save-as` crosses the mutation boundary.

Application must bind the checkpoint to the exact reviewed analysis and record
source-to-result lineage, preserved or split status, evidence spans, and
review provenance needed by `mem trace` and `mem rationale`.

Trace metadata v3 binds a declared frame's Memory UID, workbench issue UID,
source-analysis UID, uncertainty reason, and text in one digest. This prevents
an issue identity from being changed while retaining a valid text-only
checksum. Trace metadata v2 remains readable through its legacy text-digest
validator; it is not treated as equivalent proof of the stronger v3 binding.

### Privacy

Reviewer comments may contain operational or private context. Before
application they belong to a replaceable, local review artifact and must not
be exposed through unrelated commands. If a reviewed frame is applied, its
retention in checkpoint provenance is an explicit privacy boundary that the
user and documentation must acknowledge.

Atomize must remain direct-Memory-only unless a later contract changes that
scope. It must not open query-only source contents, traverse referenced
Memories as though they were owned, or leak restricted evidence through the
overview, issue list, snapshot, trace, or rationale.

Deleting or replacing a Context-scoped analysis must define what happens to
its unapplied responses. Comments must not be silently retargeted to a
different analysis or Context.

## Alternatives considered and rejected

### Count-only output

Counts are cheap to scan and useful for scale, but cannot reveal omission,
scope damage, invented referents, or poor split boundaries. Counts remain as
one compact line and are not the review interface.

### Representative or boundary examples only

Representative and difficult examples are useful during developer evaluation,
but a selected sample can look correct while an entire topic disappears.
Examples do not show what the operation understood across the current source.
They remain useful regression fixtures, not a substitute for the overview.

### A relationship map as the primary result

A graph can reveal structural relationships, but it introduces another
semantic transformation and can be persuasive even when its nodes omit source
content. It is also difficult to scan in a terminal or remote snapshot at
book scale. A relationship view may be added later as a secondary inspection,
not as evidence that atomization succeeded.

### Theme grouping

Grouping issues under headings such as `ACCESS`, `PARKING`, or `SERVICES` was
rejected as the primary organization. Sharing a topic does not mean findings
have the same resolution, and a theme label does not say what decision is
blocked. The primary unit is an actionable typed issue. Content themes may
appear in the understanding summary without controlling review order.

### One-at-a-time yes/no prompts

Starting immediately with issue 1 hides the total workload, issue diversity,
and available priorities. Yes/no also cannot represent accepting a reading
with a qualification or supplying missing context. The workbench first shows
the entire issue list, then expands one selected item.

### Separate refinement and replacement fields

Real responses can accept, refine, comment on, and partially replace a reading
at once. Two fields manufacture a distinction before downstream
reconciliation knows how the text should be used. One selected choice plus one
verbatim response preserves the evidence without guessing.

### A narrow uncertainty-only `review atomize` workflow

An adapter that begins at `mem review atomize` and exposes only
`UNCERTAIN / RECONCILE` comments omits the content overview, split proposals,
ambiguities, and conflicts that motivated interactive inspection. Review is
still a useful resume mechanism, but atomization begins conceptually at
`mem impact atomize` and uses the broader typed workbench.

### Silent provider rerun

Automatically rerunning when a command is reopened appears convenient but
breaks the connection between what the user saw, what they answered, and what
will be saved. Semantic nondeterminism makes an implicit replacement unsafe.
Resume is silent and stable; reanalysis is explicit and identifiable.

### Generic `AFFECTED` topics or unsupported counts

`AFFECTED 5: access, parking` looks precise without identifying five concrete
results or proving that a reading changes them. The detail instead states the
actual blocked judgment. Structured impact counts are deferred until
downstream identities and counterfactual checks exist.

### Invented chronology

Using UUIDs, checkpoints, JSON ordering, or grouped display order as creation
time would misrepresent the data. `SOURCE` explicitly means `Context.order`
until timestamps and their lifecycle semantics exist.

## Agreed contract

The following decisions are stable enough to guide implementation and tests:

- `mem impact atomize` is the primary atomize workbench entry point.
- `mem atomize` and `mem review atomize` resume the same compatible saved
  analysis and workbench state without another provider call. Bare
  `mem review` is a compatibility fallback when no older global review is
  active.
- Reopening or taking a snapshot never silently reruns semantic analysis.
- Reanalysis is explicit, and applying it must identify the exact analysis.
- The first screen contains counts, `WHAT MEM UNDERSTOOD`,
  `WHAT CHANGED / REMAINS UNRESOLVED`, and the complete actionable issue list;
  reading-bearing issues include up to two typed, shortened reading previews.
- The count line is a scale signal, not evidence of correctness.
- Understanding and transformation summaries are concise and traceable.
- Unknown referents are retained and reported rather than guessed.
- Meaning loss is a blocking failure, not a successful status.
- Default issue order is `Context.order`; it is not called chronology.
- Priority first surfaces conflicts, atomize uncertainties, and
  `REQUIRED` ambiguities; then `HELPFUL` ambiguities; then `NONE` ambiguities
  and proposed splits, with source order as the tie-breaker.
- The shared shell retains typed issue arity: one source for ambiguity, two
  for conflict, and one source plus proposed children for a split.
- Source text remains verbatim; English readings and explanations provide a
  common comparison language.
- Ambiguity preserves both interpretation and clarification axes.
- Actionable conflict preserves `YES / MAY` and displays both source Memories;
  `NO` pairs are omitted.
- The detail explains both what is unclear and which judgment it blocks.
- Choice selection and freeform evidence are independent.
- The shell uses one field labeled
  `REFINE, COMMENT, OR ENTER A DIFFERENT READING`.
- Left/right navigate issues; up/down or digits select typed choices.
- Split and stacked terminal layouts present the same durable state.
- A stable snapshot supports remote control and non-TTY inspection.
- Natural-language chat instructions are translated by the controlling agent,
  not parsed as a new `mem` command language.
- No Memory mutation or Context checkpoint occurs before explicit save.
- Source, declared-frame, response, and source-to-result provenance remain
  distinguishable.
- Query-only and referenced content stays outside the direct atomize evidence
  frame.

## Deferred decisions

The following must not be accidentally encoded as settled behavior:

- an archive and diff UI for multiple analysis revisions;
- whether more than one concurrent workbench can be retained and how it locks;
- the exact action vocabulary for accepting, refining, keeping, or deferring
  an atomize split;
- a hard word limit for overview paragraphs;
- structured downstream affected-result counts and dependency graphs;
- true creation-time ordering and timestamp migration;
- a relationship-map secondary view;
- the exact read-only interaction offered after an analysis has been applied;
- automatic use of predecessor, parent, or neighboring Contexts as declared
  evidence;
- conflict, update, reconcile, distill, meld, and sever application adapters;
  and
- provider/model pinning and reproducible semantic rerun policy for formal
  evaluation.

## Implemented checklist

These boxes describe the current implementation and its regression boundary.

- [x] Define a persisted atomize-workbench record bound to one exact analysis
      and direct-Context digest.
- [x] Extend the analysis result with source-linked understanding and
      transformation summaries.
- [x] Produce typed actionable issues without flattening their source arity.
- [x] Make `mem impact atomize` create or resume the workbench and render its
      overview.
- [x] Make `mem atomize` resume that same compatible analysis before applying
      it.
- [x] Make `mem review atomize` resume the same cursor, choices, and responses;
      bare `mem review` is a compatibility fallback when available.
- [x] Define and implement explicit `--refresh` and `--with-review`
      reanalysis boundaries that never replace a proposal silently.
- [x] Render counts, both summary blocks, the complete issue list, and one
      typed detail from the same durable state.
- [x] Preview up to two persisted readings per issue in the list, disclose
      hidden alternatives, and retain full reading text in detail.
- [x] Render atomize sources, proposed children, and cited evidence; retain
      source/frame evidence separately in the saved analysis and provenance.
- [x] Render ambiguity and conflict details with their agreed labels and
      arity.
- [x] Support the unified response field and typed choice selection.
- [x] Support left/right, up/down, digits, Enter/Tab, Escape, F2/Ctrl-S, `S`,
      `L`, and `Q` consistently.
- [x] Provide a deterministic, terminal-safe non-interactive snapshot.
- [x] Keep analysis, review, snapshot, and reanalysis non-mutating.
- [x] Bind `--save` and `--save-as` to the exact reviewed analysis and record
      trace/rationale provenance.
- [x] Reject stale Contexts before provider calls, and reject malformed or
      unsupported provider evidence without partial mutation.
- [x] Add tests for stable provider-call counts across all resume entry points.
- [x] Add snapshot tests for information hierarchy, issue order, typed arity,
      source fidelity, and the absence of fabricated affected counts.
- [x] Add PTY tests for navigation, choice selection, unified input, sorting,
      layout, persistence, and remote resume.
- [x] Preserve tests for declared-frame isolation, source grounding, no
      frame-only children, stale review gates, checkpoint lineage, privacy,
      trace, and rationale.
- [x] Update command help and the older atomize/review rationale notes so they
      do not describe an uncertainty-only adapter as the final workbench.

The archive/diff UI, measured downstream-effect scoring, and an independent
semantic validator remain deferred; none is implied by a checked item.
