# `mem atomize` workbench design rationale

## 2026-08-29 responsibility revision

Atomize findings are now read-only operation evidence. The workbench no longer
accepts comments or reading selections, creates declared frames from responses,
reanalyzes responses, or incorporates them into Apply. `mem review atomize` is
provider-free and read-only after Apply; it has no Responses frame.

The current flow is analysis → exact structural Apply/Save As → complete
one-line unresolved-issue receipt → read-only Review. Atomize Grounding and its
console, Python, agent, provider, runtime, and Meld adapter routes are retired.
Legacy response fields remain serialized but unused. Grounding model,
persistence, history, cleanup, and restoration compatibility were removed on
2026-08-30; only generic Context snapshot history/restoration remains.

The detailed response, `--with-review`, and Grounding sections below are
retained as a historical implementation record. They are not current behavior
or callable routes. The authoritative current rationale is
[`atomize-read-only-findings-design-rationale.md`](atomize-read-only-findings-design-rationale.md).

## Exact Study tutorial prewarm

For the fixed user-study tutorial only, `init-study` may validate a declared
exact `AtomizeAnalysisSession` and install a hidden entry-key receipt. It does
not write the Context-bound production slot or create a workbench. Eligibility
binds the complete direct Source ledger, tutorial-description digest, semantic
ruleset, provider contract, and exact provider/model/reasoning provenance. The
first explicit
matching Atomize command installs the prepared analysis through the ordinary
boundary and creates a blank run-local workbench. It imports no review
responses, grounding state, application state, or checkpoints. The CLI
discloses a first-use auto-Apply as
`ANALYSIS · EXACT PREWARM · INITIAL ANALYSIS REUSED`; Dedun and final
normal-form verification still run before publication. Advanced preview routes
retain the `EXACT PREWARM · CURRENT` origin. Explicit refresh and any changed input
retain the ordinary live path. Within the shared Study cache-quality contract,
an exact or component-wise higher cached Codex identity may satisfy the
configured request; lower and incomparable identities miss. This keeps
latency preparation separate from both participant history and mutation
authority.

When a current Study description also reconstructs an older compatible
description digest, the current-exact digest wins before provider-quality
ranking. This prevents two same-quality historical artifacts from becoming an
arbitrary registry-order choice while preserving the narrowly enumerated
legacy migration path.

An exact Memory selection may reuse that prewarm only when its actionable UID
set is extensionally identical to the prepared analysis. This covers the Study
tutorial's one-direct-Memory Source while preserving the visible focused
selection. If a whole-Context prewarm contains any additional direct Memory,
focused selection discards it and follows the live provider path rather than
silently widening the person's target. A setup Input with zero direct Memories
is rejected before this lookup, which prevents an empty parent Context from
opening an apparently successful no-result Atomize session.

### Observed previously-applied-session edge

An older or already exercised Profile can retain an `APPLIED` Atomize analysis
for a Context even after command Undo restores that Context's pre-Apply Memory
frame. This is intentional one-shot application history, not an ephemeral
cache. Choosing `New Atomize` and selecting that same Input currently resolves
the existing Context-scoped latest-analysis slot, so it reopens the `APPLIED`
session instead of creating a new analysis. The label can therefore suggest a
fresh session when the actual behavior is resume-by-Context; explicit
reanalysis still requires `mem impact atomize --refresh`, while restoration of
the undone application requires `mem redo`.

This edge does not block a newly initialized Study run. `init-study` leaves the
Atomize catalog empty. The first explicit tutorial Atomize command materializes
the prewarm with a blank run-local workbench and no application state or
checkpoints, so the new session begins as `EXACT PREWARM · CURRENT` and its
reviewed result remains eligible for one Apply. The older-Profile launcher case
is retained as a known interaction issue; this change records it without
altering the current session or application contract.

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

mem impact atomize --session UID
    -> reopen one exact saved analysis without provider work or refresh

mem impact atomize --sessions
    -> browse only saved Atomize analyses through the Impact launcher

mem impact --sessions
    -> browse every durable artifact inspectable through Impact

mem atomize
    -> target the complete current Context without opening a session
    -> create or reuse the compatible saved analysis
    -> apply it in place as one checkpoint
    -> print representative source/child UIDs, full content, and review counts

mem review atomize
    -> resume the same saved analysis and responses
    -> remain read-only after that analysis has been applied

mem review
    -> in a TTY, browse all saved Review-capable sessions
    -> choosing Atomize resumes this exact analysis and workbench
    -> non-TTY and explicit snapshot/response forms retain compatibility resume

mem atomize --context INPUT
mem atomize --save
mem atomize --save-as NEW_CONTEXT
mem atomize --sessions
    -> retain advanced explicit workbench, destination, and saved-work routes

mem atomize [INPUT | MEMORY | INPUT:MEMORY]
mem impact atomize [INPUT | MEMORY | INPUT:MEMORY]
    -> share one auto-typed positional target; a Memory form focuses one exact
       directly owned source occurrence
```

`mem impact atomize` is the primary preview entry point because the risky
questions occur before application: Did the operation understand the source?
What will it split? What remains unclear? `mem atomize` is also allowed as a
direct current-Context action: it joins the same compatible saved analysis and
applies it without opening the workbench. `mem review atomize` is the durable
inspection surface for the complete result and unresolved findings. In a TTY,
bare `mem review` reaches Atomize
through the aggregate saved-session launcher and revalidates the selected
analysis UID. Non-interactive or explicit snapshot/response compatibility
forms may still reach the current Context's workbench only when no older global
review is active. Once applied, the terminal workbench and exact checkpoint
authorize read-only reopening even though a split necessarily changed the
current direct-Memory digest; response and replacement actions are rejected.
Memory has no separate name field, so the Review list identifies each finding
as `[uid-prefix] content preview`; its detail retains the exact UID and full
content. SOURCE ordinals describe evidence arity only and are never presented
as Memory names.
The common seeded-report shell treats a trusted report with no child focus
markers as one whole-report Viewer section instead of indexing an empty focus
topology. In read-only item detail it hides an unanswered blank Responses
frame and removes edit/send hints; an answered saved response may still appear
as inspection evidence, but its target remains non-editable.

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

The current schema stores one mutable latest analysis/workbench pair per
Context UID, plus immutable displaced pairs by analysis UID:

```text
~/.mem/atomize-analyses/<context-uid>.json
~/.mem/atomize-workbenches/<context-uid>.json
~/.mem/atomize-session-history/<context-uid>/<analysis-uid>.json
```

Their exact analysis UID, Context digest, issue projection digest, choice
identities, cursor, sort mode, layout, and responses are validated on load.
A refreshed analysis replaces the latest-analysis slot and creates a fresh
workbench only after retaining the displaced pair. The active workbench may
continue to change, while a retained history pair is immutable and read-only.

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
Its information hierarchy is the first concrete adapter for the
operation-neutral contract in
[`semantic-result-workbench-design-rationale.md`](semantic-result-workbench-design-rationale.md).
Atomize still owns its classifications, complete issue list, response state,
reanalysis, and application boundary. Result explanation and case inspection
use `ResultWorkbench`; the actionable list/detail/reading/comment interaction
now uses the separate shared `ResolutionWorkbench`. Neither asset owns the
Atomize provider, issue digest, durable response, or application.

A representative shape is:

```text
RESULT · atomize · temp/task-1
STATUS · READ-ONLY PREVIEW · sources=51 · projected=61 · splits=7 · children=17

WHAT MEM UNDERSTOOD
The notes describe a summer building closure affecting entrances, parking,
routes, stores, dining, visitor services, restrooms, and event reservations,
while preserving staff-access and elevator exceptions and identifying
replacement services elsewhere on campus.

WHAT HAPPENED
Compound notes were separated into independently revisable closures,
exceptions, alternatives, and continuing services.

WHAT REMAINS UNRESOLVED
Expressions such as "the same NFC," "after that time," and "this building"
were retained without guessing their referents.

REPRESENTATIVE / BOUNDARY CASES
> REPRESENTATIVE · Split a compound closure from its replacement service
  BOUNDARY       · Retain "the same NFC" pending an exact local referent

ISSUES · 0/4 answered                             ORDER: SOURCE
> 1. AMBIGUITY · DOMINANT/REQUIRED  "the same NFC..."
     WHY · The phrase may name only the mechanism or also the credential rule.
     ↳ R1 · Use the prior NFC mechanism
     ↳ R2 · Apply the prior credential rule
  2. CONFLICT · MAY                  [...] <-> [...]
     WHY · The entrance scope determines whether the two claims conflict.
     ↳ R1 · Same entrance
     ↳ R2 · Different entrances
  3. SUGGESTED SPLIT                 "The store closes..."
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

The provider is instructed to target one short paragraph per section, normally
roughly 40-50 English words at most, under the shared result-workbench
attention budget. This is a readability target rather than a semantic
invariant or truncation rule. Each overview section cites one or more source
Memory identities.
The snapshot keeps those citations collapsed; the saved analysis retains them.
For a nonempty candidate frame, the flat strict provider schema requires at
least one source ID even when the section text is empty. This is the safe
schema-level approximation of the intended conditional—nonempty prose must
have evidence—because the aggregate provider contract deliberately avoids a
union schema. The local decoder still accepts a legacy empty-text/empty-source
section, but it never accepts nonempty ungrounded prose. This asymmetry keeps
older saved analyses readable without allowing a schema-valid live response
to fail only after the provider call. The same strict-schema boundary cannot
declare `uniqueItems`; repeated overview aliases are therefore collapsed in
first-seen order because citations have set semantics. Unknown aliases still
fail closed, and coverage-bearing Atomize items and quality issues retain
their stricter duplicate validation.
All three overview sections follow the natural-language report contract in
[`semantic-result-workbench-design-rationale.md`](semantic-result-workbench-design-rationale.md):
one short English paragraph in complete sentences, with no bullets, numbered
list, embedded heading, key-value record, raw ID, or telegraphic enumeration.
Counts remain in the metadata line, and the complete issue records remain in
the separate actionable list.

The block must not:

- add a fact absent from the declared evidence;
- turn an unresolved expression into a confident assertion;
- describe only closures while omitting important exceptions or alternatives;
- substitute a list of atomization rules for a summary of the content; or
- claim independent verification merely because the proposal model generated
  the summary.

### `WHAT HAPPENED` and `WHAT REMAINS UNRESOLVED`

The first block answers a different question: "What did atomization do to that
content?" It identifies meaningful structural changes, such as separating a
closure from its replacement service or preserving a condition with the claim
it scopes. The second names expressions that could not safely be resolved from
the current Context. They are separate because a successful structural result
must not visually absorb or soften the uncertainty that still blocks a
judgment.

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

An unresolved quality finding is not itself proof that the exact structural
proposal loses content. The workbench therefore does not turn silence into a
deferment decision or require one response per finding. Answered unary
responses must first be incorporated in one complete reanalysis turn. With no
incorporable response pending, the exact local proposal applies without opening
the workbench because every finding is optional and the application checkpoint
is recoverable with `mem undo`. The success receipt still discloses unresolved
findings, and saved analysis remains available for read-only inspection. A
saved unary response disables the shortcut and requires its complete
incorporation turn. Applying
uses every current `COMPOSITE` split, preserves `UNCERTAIN` sources because
they have no children, and leaves Conflict semantics unresolved. The action
records those findings as `UNRESOLVED AT APPLY` rather than `RESOLVED`,
`SKIPPED`, or `DEFERRED`.

The report also names its operation frame independently of this semantic
summary. A typed `CONTEXT LOCATIONS` block identifies Source and Output,
marking an unchanged Output as `IN PLACE` and a planned fresh Output as `NOT
CREATED`. That complete report remains available through Impact and Review,
but applying Atomize does not wrap a pending decision in the report workbench.
The execution surface shows only the current finding, operation-authored
choices, the exact Output, and compact actions. Location remains a visible row
because it changes materialization, but it has no `L` shortcut: `Up`/`Down`
focuses the row and `Enter` opens the shared one-line exact-name input. The
same Enter-only rule applies to unnumbered choices and Apply; numeric choice
keys and direct `A` are inert. Validation failure retains the input, Escape
returns one level, and a valid change is persisted by the Atomize controller
before the same compact revision reopens. This keeps Output editing adjacent
to the applying decision without restoring a second large viewer or a
redundant post-review location prompt.

The ordered 180×52 color-PTY evidence in
[`agent-records/docs/screenshots/atomize-compact-execution-20260822/`](screenshots/atomize-compact-execution-20260822/)
records entry, selection, valid and invalid exact-name transitions, Apply
receipt, and read-only result verification.

As with the understanding block, each of these two sections is its own concise,
traceable natural-language report paragraph. The shared 40-50-word soft target
applies; exact hard enforcement remains intentionally deferred because
preserving a material qualification takes priority over word-count compliance.

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

When an ambiguity or conflict has saved ordinary readings, its list row adds
one longer `WHY` sentence from the issue reason and compact `R1`/`R2` labels.
The first line explains the tension and operational consequence; the labels
carry only the contrast needed to choose an interpretation. This hierarchy is
more useful than repeating two explanatory paragraphs as choices. At most two
labels are previewed in provider order, followed by an explicit remainder
count when more exist.

Each persisted `AtomizeReading` therefore separates:

- `label`: a parallel action or claim phrase, normally 2-10 English words and
  never more than 20; and
- `text`: the complete ordinary reading used by the detail view and reviewed
  reanalysis.

The label is a navigation aid, not a substitute for semantic evidence.
Selecting `R1` or `R2` continues to place the full `text`, never the label,
into the declared frame. The provider must generate both in the same aggregate
analysis; deterministic head/tail truncation cannot reliably identify which
clause distinguishes two readings. The list does not turn an uncertainty
reason or proposed split child into a fabricated reading.

Analysis schema v4 stores the label/text distinction. A v3 analysis remains
loadable without a provider call by using its complete text as a visibly
longer fallback label. Obtaining a genuine semantic label for such an analysis
requires explicit `mem impact atomize --refresh`; ordinary resume never
silently reinterprets saved work.

The first explicit v4 refresh of `temp/task-1`, analysis `d12a0f99…`, produced
11 labels across seven reading-bearing cards. Every label used four to seven
English words, while each corresponding full reading remained separately
stored. Representative pairs were `Require only a physical card` versus
`Allow a card or app`, and `Give students a physical card` versus `Tell
students to use card or app`. Reopening that analysis did not call the
provider. The semantic rerun also changed some issue membership, which is why
adding labels to an old analysis silently would have been dishonest: only an
explicit refresh may replace the immutable proposal.

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

### Suggested split

The durable `ATOMIZE_SPLIT` issue, displayed as `SUGGESTED SPLIT`, has:

- exactly one source Memory;
- two or more ordered proposed children;
- the atomize classification and reason codes;
- a concise reason for the boundary;
- source evidence spans for every child; and
- any declared-frame evidence shown separately from original-source evidence.

The detail view must show the original and the proposed children together so
the user can inspect coverage, scope, and revision boundaries. Showing only
`COMPOSITE / SPLIT` does not reveal what will actually be stored.

Proposed children are a compact ordered Memory list. Each `[n] content` row is
one Viewer navigation stop; Evidence is hidden until Enter expands that exact
row. The list does not repeat raw child UIDs or place every evidence span under
every child by default, because both forms obscure comparison across children.

Suggested splits are optional review rows. Leaving one unanswered does not
exclude it from application: Review and Apply offers `APPLY AS IS` for the
current children. A typed response is incorporable unary evidence and changes
the final action to `INCORPORATE AND APPLY`; the inline Response route remains
the non-applying `INCORPORATE RESPONSES` alternative.

### Ambiguity

An ambiguity issue has exactly one source Memory and retains two independent
judgments:

```text
interpretation: SINGLE | DOMINANT | COMPETING
clarification: NONE | HELPFUL | REQUIRED
```

The first axis describes the structure of ordinary readings. The second
describes whether clarification changes or is needed for the task. They are
not one confidence score and must remain separately visible. The shared Viewer
therefore renders the values with their axis names (`INTERPRETATION · ...` and
`CLARIFICATION · ...`). A bare `SINGLE · REQUIRED` would make the clarification
classification look like the independent REQUIRED/OPTIONAL review obligation.

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
current workbench for a future reconcile operation. It does not, however,
block `APPLY AS IS`: Atomize may apply its exact current structural proposal
while retaining and auditing the still-unresolved pairwise finding.

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

### Other operation adapters

Update, reconcile, distill, and sever may reuse the list, detail, choice, and
response controls, but must define their own arity, evidence, mutation, and
trace contracts before being added. Context-to-Context symmetric meld now
reuses the interaction grammar in a separate workbench with its own peer
relation ledger. Visual similarity is not permission to erase
operation-specific semantics.

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
> 1. [DOMINANT] Use the prior NFC mechanism
     The door uses the previously described NFC mechanism.
  2. [ALTERNATIVE] Apply the prior credential rule
     The same credential and permission rule applies.

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

- `V`: toggle between the common semantic-result view and Atomize's complete
  actionable issue workbench;
- in the common result view, up/down selects a sampled representative or
  boundary case, Enter expands its saved
  evidence--judgment--outcome/unresolved trace, and Escape/Backspace collapses
  it or returns to the issue workbench;
- up/down at the issue level: previous or next issue, matching the vertical
  list;
- Enter at the issue level: expand that issue inline with its complete typed
  detail and reading text;
- up/down inside an expanded issue: move over its available readings;
- Enter on a reading: select it, or clear it when it was already selected,
  then return to the issue level;
- Enter again on an expanded issue with no reading choices: collapse it;
- Escape or Backspace: collapse the expanded issue without changing the
  semantic selection;
- left/right: compatibility aliases for previous or next issue;
- Tab: focus the unified response field;
- Escape or Tab from that field: return to list navigation;
- F2 or Ctrl-S: save the current response and move to the next issue;
- `S`: toggle `SOURCE` and `PRIORITY`; and
- `Q` or Ctrl-C: save and close.

Earlier builds used left/right for issue movement and up/down for choices.
That spatial split made an up arrow move within the current issue instead of
to the visibly preceding issue. An intermediate design moved issues vertically
but retained numbered choice shortcuts. That still required the reviewer to
map a number to a collapsed reading instead of navigating the visible
structure. The workbench now uses Enter to drill into one expanded issue,
up/down to move within that level, and Enter again to toggle the reading.
Left/right remain issue aliases so existing remote controllers do not break.

Expansion and the hovered reading are ephemeral presentation state. Reopening
the shell starts at the durable issue cursor in a collapsed list, while the
selected reading and freeform response remain saved. Persisting a half-open
terminal layout would add no semantic evidence and could restore poorly at a
different terminal size.

The result view is also ephemeral and read-only. It samples the first
source-order validated outcome per realized Atomize result class and at most
one saved example per quality-boundary kind, preferring actionable findings.
This is deterministic outcome coverage, not a claim that the examples are
statistically typical or semantically hardest. The complete `ACTIONABLE
ISSUES` list remains authoritative and must not be replaced by the sample.

The common Resolution Session is the sole live presentation. Historical
`SPLIT` and `STACKED` values remain readable in serialized workbench state for
compatibility, but both project to the same one-column frame sequence. Cursor,
choices, and responses therefore survive old-session resume without reviving a
second visual grammar.

The older standalone `ResultWorkbench` application was also removed after its
last production caller migrated here. `ResultWorkbenchView`, digest-bound case
detail, and the pure snapshot/fragment renderers remain the exact result
evidence contract embedded in Atomize Review and non-TTY output; they no longer
claim an independent full-screen route. Keeping the projection while deleting
the orphan host preserves evidence validation without leaving another large
viewer for future callers to accidentally revive.

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

Trace metadata v4 adds provisional result contents, typed Dedun evidence,
absorbed-to-survivor mappings, and the final validation digest so a hidden
split→absorb transition remains reconstructible from the single outer
checkpoint. Trace metadata v3 binds a declared frame's Memory UID, workbench issue UID,
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
Final Apply is a separate advertised semantic boundary: it reuses the saved
proposal but runs Dedun discovery and normal-form verification on an
unpublished projection. The CLI keeps one transient progress line alive across
that complete provider-backed boundary. It starts lazily so exact checkpoint
recovery remains provider-free and visibly silent.

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
- `mem impact atomize --session UID` is the exact provider-free reopen route,
  while `mem impact atomize --sessions` is its filtered launcher and
  `mem impact --sessions` is the cross-operation durable Impact launcher.
- A newly created or resumed Impact analysis prints its exact reopen route and
  both launcher routes. The compact UID remains a recognition label; the full
  UID in the command is the executable identity.
- `mem atomize` and `mem review atomize` resume the same compatible saved
  analysis and workbench state without rerunning the initial analysis. Apply
  separately runs its normal-form provider calls; Review does not. TTY bare
  `mem review` selects among all saved Review-capable sessions; its Atomize row
  resumes the exact selected analysis. Non-TTY and explicit snapshot/response
  forms retain the older compatibility fallback.
- Reopening or taking a snapshot never silently reruns semantic analysis.
- Reanalysis is explicit, and applying it must identify the exact analysis.
- One analysis identity crosses Apply at most once. After its Context
  checkpoint exists, the Source-owned workbench stores the applied Output and
  checkpoint UID as a terminal receipt. This is not merely evidence that the
  Context still equals the immediate post-Apply bytes. Later edits, a conflict
  in a created Output, or loss of that Output therefore do not re-enable
  `APPLY AS IS`, `INCORPORATE AND APPLY`, or any other second application of
  that session. Whole-command Undo of a Save As creation is the explicit
  exception: it removes the created Context and reverses the Source receipt;
  Redo restores both sides under exact-state checks. Reopening a still-applied
  session keeps item comments editable for review evidence but removes
  whole-set and Apply capabilities.
- Unanswered Ambiguity, Atomize Uncertainty, and Conflict findings do not
  require per-item responses; they select one explicit `APPLY AS IS` boundary.
- Answered unary responses still require one batch incorporation turn. The
  final `INCORPORATE AND APPLY` action may authorize that turn and the normal
  validated Apply path together; inline incorporation remains non-applying.
  Silence is not incorporated as an answer or policy.
- Apply-as-is records the issue UID, kind, source arity, classification,
  reason, visible response state, workbench UID, and response-state digest in
  the application checkpoint without copying an unapplied free-form response.
- The first screen contains counts, `WHAT MEM UNDERSTOOD`, `WHAT HAPPENED`,
  `WHAT REMAINS UNRESOLVED`, sampled representative/boundary cases, and the
  complete actionable issue list; reading-bearing issues include one
  explanatory `WHY` line and up to two compact reading labels.
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
- Up/down navigate the current list level; Enter expands an issue or toggles
  its focused reading, while Escape/Backspace returns one presentation level.
- Left/right remain issue-navigation compatibility aliases.
- The shared live shell uses one consistent inline drill-down layout. Legacy
  split/stacked values remain serialized for compatibility but no longer
  define separate semantic states.
- A stable snapshot supports remote control and non-TTY inspection.
- Natural-language chat instructions are translated by the controlling agent,
  not parsed as a new `mem` command language.
- No Memory mutation or Context checkpoint occurs before explicit save.
- Source, declared-frame, response, and source-to-result provenance remain
  distinguishable.
- Query-only and referenced content stays outside the direct atomize evidence
  frame.

## Implemented conversational-grounding slice

Multi-turn resolution of one selected workbench issue is now implemented as an
atomize-specific interaction contract. The goal is to make semantic review
resemble grounding in ordinary human communication:

```text
comment
→ provisional understanding
→ concrete consequence or follow-up question
→ correction or confirmation
→ revised understanding
→ explicit change proposal
→ permission
```

The command contract is:

```text
mem atomize --evaluate ISSUE [--comment TEXT]
mem atomize --reply TEXT
mem atomize --accept-grounding
mem atomize --keep-review-only
```

Evaluation and reply build a durable atomize grounding session and may call
the provider; rendering or resuming it does not. Acceptance is the only path
that may apply its exact confirmed edit/add proposal. Keeping review evidence
does not mutate a Context.

This is not permission to make every response a global declared frame.
The implementation preserves source arity, distinguishes agent inference
from user assertion, retains corrections rather than concatenating conflicting
turns, and preserves A06's separation between Context-wide quality judgment and
source-local atomization. Exact downstream issue identities may be shown only
when a structured assessment records them; promotion or mutation remains
optional and explicitly confirmed.

The complete design rationale is
[`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md).
The atomize dialogue now reuses the common meld turn-lineage invariant and
declares itself as `DIRECTIONAL` / `ISSUE`. It projects the selected
source-grounded issue as an ephemeral `INCOMING` Context frame, the containing
Context as the bound `BASELINE`, and `CLARIFICATION` as turn evidence rather
than a third frame. Unary issues therefore use a one-Memory temporary Context
projection; pair issues retain both source Memories. The projection is never
stored or checkpointed. This remains a lossless adapter: artifact migration
and a generic cross-operation persistence schema are outside the atomize slice.

## Deferred decisions

The following must not be accidentally encoded as settled behavior:

- an archive and diff UI for multiple analysis revisions;
- whether more than one concurrent workbench can be retained and how it locks;
- a future per-split selective keep/defer contract; the current response,
  incorporation, and whole-proposal Apply vocabulary is settled;
- a hard word limit for overview paragraphs;
- migration of atomize grounding into a generic cross-operation persistence
  schema; its current lossless meld adapter deliberately preserves the
  atomize-specific artifact;
- true creation-time ordering and timestamp migration;
- a relationship-map secondary view;
- richer history and comparison UI for an applied analysis beyond its current
  terminal inspection and comment-editing surface;
- automatic use of predecessor, parent, or neighboring Contexts as declared
  evidence;
- semantic Update resolution, Reconcile, Distill, and Sever application
  adapters; Update currently has only a read-only planned-change projection;
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
      TTY bare `mem review` selects the exact workbench through the aggregate
      launcher, while non-TTY and explicit snapshot/response forms retain the
      compatibility fallback.
- [x] Define and implement explicit `--refresh` and `--with-review`
      reanalysis boundaries that never replace a proposal silently.
- [x] Render counts, both summary blocks, the complete issue list, and one
      typed detail from the same durable state.
- [x] Preview one issue reason and up to two persisted reading labels, disclose
      hidden alternatives, and retain full reading text for detail and
      reviewed reanalysis.
- [x] Render atomize sources, proposed children, and cited evidence; retain
      source/frame evidence separately in the saved analysis and provenance.
- [x] Render ambiguity and conflict details with their agreed labels and
      arity.
- [x] Support the unified response field and typed choice selection.
- [x] Support vertical issue navigation, Enter-based inline drill-down and
      choice toggling, Escape/Backspace return, left/right compatibility
      aliases, Tab, F2/Ctrl-S, `S`, `L`, and `Q`.
- [x] Provide a deterministic, terminal-safe non-interactive snapshot.
- [x] Keep analysis, review, snapshot, and reanalysis non-mutating.
- [x] Bind `--save` and `--save-as` to the exact reviewed analysis and record
      trace/rationale provenance.
- [x] Publish Save As only after the transform succeeds, as one final
      `atomize` creation checkpoint; recover a published-but-unreceipted exact
      output without duplicating it, and restore its Context/analysis/receipt
      lifecycle through one Undo/Redo command unit.
- [x] Persist one Context-bound, multi-turn atomize grounding session with
      unary/pair anchor arity, reviewer turns, provisional understanding,
      downstream effects, and required/helpful follow-ups.
- [x] Preserve terminal grounding dialogues in immutable Context-scoped
      history so `--keep-review-only` evidence is not overwritten by the next
      evaluation; history listing/diff UI remains deferred.
- [x] Implement `--evaluate`, provider-free bare resume, `--reply` with
      confirm/extend/correct/retract revision labels, and
      `--keep-review-only`.
- [x] Validate opaque provider identifiers, generate ADD UUIDs locally, and
      reject stale or malformed semantic proposals before persistence.
- [x] Apply the complete ready EDIT/ADD proposal only through
      `--accept-grounding`, with one Context save, one checkpoint,
      idempotent receipt recovery, and trace/rationale evidence.
- [x] Bind the full direct-item order, including reference slots, reject stale
      inputs before and after provider calls, and reject malformed or
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

The shared workbench also owns Atomize's process-independent Output plan.
Schema v2 stores `output_context_name`; schema v1 normalizes to the Input
Context name, preserving its original in-place behavior. Output routing is
excluded from the response digest and issue projection because it changes
where an accepted exact result is materialized, not what the semantic
analysis or reviewed answers mean. Explicit refresh carries the Output plan
to the replacement workbench while still replacing issue responses under the
existing fresh-analysis rule.

A require-new Apply persists an immutable analysis copy under the Output
Context for provenance, but the mutable shared workbench remains Input-owned.
Opening the applied Output may construct a process-local read-only workbench
projection; it must never save that projection as a second session owner. The
session catalog collapses same-UID Input/Output analysis copies through the
Source terminal application receipt, with the legacy Source-to-Output route as
a compatibility fallback. If neither relation identifies exactly one Source,
discovery still fails closed. Historical derived Output workbench files are
ignored rather than deleted, keeping picker recovery non-destructive.
