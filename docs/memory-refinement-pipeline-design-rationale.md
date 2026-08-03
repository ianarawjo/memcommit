# Memory refinement pipeline

The detailed reasoning behind the three quality judgments—including why
ambiguity is unary, why conflict targets pairs, why duplicate discovery returns
binary relation evidence from a whole-Context pass, why ambiguity uses two
independent axes, and why detection is separated from resolution—is preserved
in
[`memory-quality-judgment-theory-and-decision-history.md`](memory-quality-judgment-theory-and-decision-history.md).
The finder implementation contract is specified separately in
[`memory-quality-finders-design-rationale.md`](memory-quality-finders-design-rationale.md).

## Decision history

### Initial order

The initial plan refined unorganized raw Memories in this order:

```text
deduplicate
→ review conflicts and ambiguities together
→ classify audiences
→ normalize
→ place by category
```

This first design reviewed `conflict` and `ambiguity` in one operation.
In real situations, two descriptions that appear contradictory can both be
true when their audience, time, place, access method, or exception conditions
differ. The prototype therefore does not immediately interpret a practical
conflict as proof that one statement is false. It first treats the conflict as
a state in which the current knowledge cannot explain both descriptions
together. This is an open-world design assumption of the refinement pipeline,
not a universal factual claim.

Here, open-world does not mean inventing unlimited possible worlds. It means a
**bounded open world**: leave room for omitted scope that the selected Context
and an ordinary reading genuinely support, but do not invent arbitrary hidden
premises merely to create or dissolve a conflict.

The later design retains this combination **only at the resolution stage**.
Ambiguity judges one Memory, whereas conflict judges a pair of Memories, so
their detection units and results differ. `find-ambiguities` and
`find-conflicts` are therefore separate read-only detectors; a later
`reconcile` operation can explain or resolve their findings together.

The design also rejects a simple public/private binary for disclosure. It uses
**audience classification** to decide the necessary explanation and level of
detail according to recipients and purposes, such as students, staff,
visitors, or facilities personnel.

### Revised order: atomize before deduplication

Reviewing the Task 1 source showed that one Memory often combines a closure,
alternative location, operating hours, and reason. Deduplicating such a
composite first can incorrectly classify two partly overlapping Memories as
duplicates, or fail to discover a duplicate claim hidden inside them.

The primary pipeline was therefore revised to:

```text
raw intake
→ atomize
→ mechanical dedup
→ semantic dedup
→ reconcile
→ audience
→ normalize
→ dedup verification
→ place
```

The initial order remains in this decision history so later research can trace
why the design moved from treating one raw line as one Memory to refining
atomic claims before comparing them.

### Revised quality analysis: detect before resolving

If names such as `dedup` and `reconcile` combine detection with mutation, they
can imply that merely inspecting a problem may delete or edit content.
Ambiguity is unary, conflict is pairwise, and duplicate discovery returns
binary relation evidence from a whole-Context pass. Combining them in one
opaque quality pass would also make it difficult to verify which unit received
which judgment.

The current working order separates detection from later mutation:

```text
raw intake
→ atomize
→ find-duplicates
→ confirmed dedup
→ find-ambiguities
→ find-conflicts
→ reconcile
→ audience
→ normalize
→ duplicate verification
→ place
```

All three `find-*` commands are read-only and create no checkpoint.
`find-duplicates` reports Memory-pair evidence without choosing a deletion
target, but it does not pre-enumerate every pair as model input.
`find-ambiguities` judges one Memory at a time, while `find-conflicts` judges
Memory pairs. A future mutating `dedup` stage will turn confirmed duplicate
results into a survivor plan, and a future `reconcile` stage will interpret
ambiguity and conflict findings together.

## Intent

`mem add --paste` preserves raw notes without trying to understand them. The
refinement pipeline turns that intake into explainable, audience-appropriate,
rule-conforming Memories without hiding semantic decisions inside a single
opaque cleanup step.

The current primary order is intentional:

1. **Atomize** explicit multi-claim Memories while preserving order and source
   lineage.
2. **Find duplicates** in mechanical and semantic trust tiers without
   removing either member of a reported pair.
3. **Deduplicate only confirmed equivalence findings** through a separate
   stale-safe mutation plan.
4. **Find ambiguities** one Memory at a time under ordinary local reading.
5. **Find conflicts** pairwise, preserving `YES`, `MAY`, and `NO` as semantic
   outcomes rather than confidence scores.
6. **Reconcile the separate findings together** to identify what the current
   knowledge cannot yet explain and which clarification would help.
7. **Classify audiences** so differences caused by applicability, recipient,
   or disclosure purpose become explicit.
8. **Normalize** only after meaning and scope are sufficiently clear.
9. **Verify duplicate relations again** because later qualification and normalization
   can expose new equivalence.
10. **Place by category** after the Memory contents have stable semantics.

These are separable operations with distinct previews, reasons, provenance,
and checkpoints. A single `clean up everything` command would make it hard to
tell whether a Memory disappeared because it was a duplicate, was classified
for an audience, was normalized, or was moved to another category.

## `mem import` as a pipeline orchestrator

`mem add` remains the low-level intake operation: it stores one Memory or a
batch of raw line-based Memory candidates and stops. The working design for
`mem import` is a higher-level envelope around the refinement pipeline:

```text
source intake
→ atomize
→ find-duplicates
→ confirmed dedup
→ find-ambiguities
→ find-conflicts
→ reconcile
→ audience
→ normalize
→ duplicate verification
→ place
```

Import must not hide these stages inside one irreversible model rewrite. It
creates an import-run manifest, preserves the raw intake checkpoint, invokes
the same independently callable stage contracts, and records:

- a locally generated run UUID;
- source identity and content hash;
- destination Context UID and starting fingerprint;
- optional explicit document frame with its own ID and fingerprint;
- ruleset and provider versions;
- each stage's status, plan ID, reasons, and unresolved items;
- the operation IDs of checkpoints created by confirmed stages.

Manifests are per run, not one global active-import slot:

```text
~/.mem/import-runs/<run-uuid>.json
```

The conceptual state machine is:

```text
CREATED
→ INTAKEN
→ PLANNED_<stage>
→ AWAITING_CONFIRMATION_<stage>
→ APPLIED_<stage>
→ ... next stage ...
→ COMPLETED

Any stage may instead become BLOCKED_<stage> or FAILED_RECOVERABLE.
```

The run UUID, stage name, input fingerprint, and plan fingerprint form the
stage idempotency key. Repeating a confirmed apply with that key returns the
recorded result rather than writing a second checkpoint. A new invocation with
the same source creates a new run unless the user explicitly supplies
`--resume <run-uuid>`; silently selecting “the latest” run would be unsafe
when terminals or agents work in parallel.

Each semantic stage retains its own preview and confirmation boundary. A
confirmed stage creates its own checkpoint; the entire import does not become
one opaque checkpoint. If `reconcile` cannot resolve a scope or a later stage
cannot safely mutate several Contexts, the import pauses and can be resumed
from the manifest. It does not guess or mark the run complete.

A convenience form such as `mem import --input notes.txt --through atomize`
means: commit deterministic raw intake, then generate previews through the
named stage and stop at its first required confirmation or block. `--through`
does not auto-approve semantic mutations. The default first implementation
should create the intake plus a previewable manifest rather than silently
applying every semantic proposal. `mem import` orchestrates provenance and
progress; it does not own a second implementation of atomization,
deduplication, or placement.

The intake checkpoint and manifest share the run UUID. The checkpoint is
written first, then the manifest is atomically replaced. If the process fails
between them, the raw intake remains recoverable and a later recovery scan can
reconstruct a `FAILED_RECOVERABLE` manifest from the checkpoint operation ID.
A stage apply is all-or-nothing at the operation's documented mutation
boundary; unresolved items block that stage rather than being silently
skipped. Cross-Context placement still requires the recovery mechanism
described below.

This also gives source-level expressions such as `해당 기간` a safe future
home. An import may declare a document frame, but every stage plan must bind
that frame's fingerprint. Ordinary neighboring Memories remain unavailable as
implicit context.

## Atomization before deduplication

`atomize` is a source-preserving semantic split, not sentence tokenization and
not stylistic rewriting. It separates only explicit multi-claim Memories. The
ordered children must collectively preserve the parent's information without
adding a decision that belongs to reconciliation, audience classification, or
normalization.

If the scope of a qualifier is uncertain, atomization reports the uncertainty
instead of guessing which children inherit it. A heading, question, or process
note is classified and retained rather than silently deleted for not being an
atomic operational fact.

The existing `mem chunk` provides a useful structural primitive but is not the
Task 1 atomizer:

- it splits one Memory by Markdown headers, paragraphs, or an approximate
  English sentence boundary;
- against the current 51 Memories, header and paragraph modes split none, and
  sentence mode splits only one Memory into an operational clause plus the
  incomplete fragment `Main building cafe`;
- it replaces the original with fresh UIDs and preserves child order at the
  original position;
- its checkpoint records the source UID and method, but not source-to-child
  lineage;
- it does not scan for inbound `memory_ref` values before removing the source.

The first `atomize` contract should therefore:

- inspect directly owned Memories as one previewable batch;
- label each item `atomic`, `composite`, `uncertain`, or
  `non-propositional`;
- return an ordered child-content list only for a clear composite;
- bind the plan to the Context UID, source UID, source-content fingerprint,
  and source position;
- allocate fresh UIDs to all confirmed children and replace the source at its
  original position;
- record `source_uid → ordered child UIDs and contents` in the staged plan and
  checkpoint metadata while keeping the base Memory schema at `uid + content`;
- block v1 in-place application when any Context contains a `memory_ref` that
  targets a source selected for one-to-many splitting, because there is no
  single safe automatic retarget; save-as preserves that source and is not
  blocked by its inbound references;
- apply every approved split in one Context-level checkpoint;
- perform no deduplication itself.

The previous checkpoint preserves recoverability, while the explicit mapping
provides operation provenance. If lineage later needs to be queried without
history traversal, that requirement should motivate a separate schema change
rather than silently adding fields during atomization.

The focal-commitment rules, Q/A ledger, size lint, golden cases, and validation
contract are specified separately in the
[`mem atomize` design rationale](mem-atomize-design-rationale.md).

## Duplicate detection in two trust layers

Both mechanical and semantic duplicate detection are necessary, but they are
two visibly different trust layers of the read-only public
`mem find-duplicates` operation. A separate future `mem dedup` operation may
consume confirmed findings and propose mutation; detection itself never
chooses a survivor or removes a UID.

### Mechanical dedup

Mechanical detection has no model dependency. It reports:

- `EXACT`: stored content is identical;
- `SURFACE_EQUIVALENT`: a conservative comparison key is identical after
  line-ending normalization, Unicode NFC, outer trimming, and horizontal
  whitespace normalization that preserves paragraph boundaries.

Comparison normalization never rewrites stored content. It must not remove
negation, question marks, numbers, dates, modality, list markers, or other
potentially meaningful symbols. Case folding, punctuation tolerance,
translation, typo correction, and synonym expansion may produce candidates
for review, but they are not mechanically applicable equivalence.

The implementation builds exact and surface components with keyed lookups and
emits a canonical spanning tree for each component. It does not construct the
quadratic clique of every within-component pair. Only the first representative
of each mechanical component proceeds to semantic discovery.

### Semantic dedup

After deterministic `EXACT`/`SURFACE_EQUIVALENT` grouping, semantic detection
receives every remaining component representative once in one Context-wide
payload. It discovers disjoint semantic-equivalence groups instead of
receiving an enumerated unresolved-pair list. Two claims are semantically
equivalent only when they are mutually substitutable without information loss
under the same:

- subject and applicability;
- predicate or operational state;
- object and place;
- audience and time;
- modality and uncertainty;
- access method, exception, and relevant causal scope.

If one Memory entails the other but contains additional information, its
relation is `OVERLAP`, not a removable duplicate. Missing qualifiers or
uncertain scope make the relation `UNKNOWN`. `OVERLAP`, `UNKNOWN`, and
`DISTINCT` are explicit golden rejection boundaries, but the public
`find-duplicates` output contains only positive duplicate relations. The model
acts as a classifier and reason generator, not as a canonical-text author.

The finder is read-only and creates no checkpoint. A later `dedup` apply path
must independently confirm eligible equivalence findings, keep a stable
existing survivor UID and wording, check inbound references, bind the plan to
a Context fingerprint, reject stale plans, and record every absorbed UID in
one checkpoint. Later normalization owns rewriting.

An optional byte-exact scan can run before atomization as a cheap read-only
diagnostic, but it cannot replace the post-atomization passes. The current
Task 1 intake has zero exact full-record duplicates.

## Why conflict and ambiguity are detected separately

Classical logical contradiction asks whether both `P` and `not P` can be true
under the same interpretation. Operational campus knowledge rarely arrives
with a complete interpretation. Its missing coordinates commonly include:

- audience: student, staff, member, visitor, or facilities operator;
- time: public hours, after hours, a construction phase, or an emergency;
- place: main entrance, rear entrance, parking pedestrian door, or stairwell;
- access method: vehicle, pedestrian, physical card, app, or staff credential;
- exception: accessibility need, urgent use, delivery, or construction work.

For example, these can all be valid at once:

```text
Staff entrances remain open.
The underground-parking stairwell is closed even to staff.
The parking pedestrian door is available only to staff.
```

The statements become contradictory only if they are assumed to describe the
same entrance and conditions. The separate finders therefore preserve the
distinction between:

- a unary ambiguity or underspecification in one Memory; and
- a pairwise conflict whose result is `YES`, `MAY`, or `NO` under ordinary
  reading of the selected Context.

`MAY` means the Context supports an ordinary reading on which the pair
conflicts and another ordinary reading on which it is jointly explainable. It
is not a model-confidence label. This is a bounded open-world stance: lack of
a current explanation is not treated as proof that one statement is false,
but the finder may consider only distinctions supported by the selected
Context and ordinary reading—not arbitrary hidden premises.

The public detectors are `mem find-ambiguities` and `mem find-conflicts`.
They remain separate because their arity, labels, and regression cases differ.
Both are read-only and create no checkpoint.

The later working operation `reconcile` consumes their separate findings and
asks what missing distinction, condition, or evidence would make the relevant
Memories usable or jointly explainable. It must not silently choose a winner.
A later confirmed edit can add missing scope, preserve both scoped facts, or
mark one statement as superseded when evidence actually supports that
decision. `reconcile` combines follow-up reasoning; it does not replace either
finder.

## Audience classification is not merely privacy separation

The design concept is **audience classification**. The working command name is
`audience`, rather than `target`, because target already means several things
in update and reference operations. Audience classification keeps four
questions distinct:

- **subject/applicability:** who or what the fact applies to;
- **intended recipient:** who needs to receive the explanation;
- **purpose/detail:** why they need it and which details support that purpose;
- **disclosure:** who may be allowed to see it.

Initial audience classes for the campus scenario include:

- students;
- staff and faculty;
- authorized members;
- visitors and the general public;
- service-desk and event staff;
- facilities and construction operators.

One underlying event can require different explanations. A visitor needs an
available entrance and public hours. A staff member needs credential and
exception rules. A facilities operator may need the reason for a closure and
its reopening dependency.

Audience classification can inform disclosure decisions, but it is not access
control. A normal Context or `context_ref` does not become confidential merely
because it is labelled for facilities staff. Content that must be technically
hidden still requires a query-only or future access-controlled storage
boundary.

The storage representation remains an implementation decision. Candidate
representations include Memory metadata, audience-specific Contexts, or a
derived audience plan. The first `audience` implementation should not commit
to one representation without testing how multi-audience Memories and
references behave.

## Normalization

`normalize` conforms each atomic Memory to explicit wording and scope rules
while preserving its resolved meaning. It is not another opportunity for
semantic invention.

Candidate rules include:

- use a complete declarative sentence;
- state the affected audience, place, and time when they are necessary;
- replace vague references such as `앞서`, `적절히`, and `등등`;
- use consistent building, entrance, and service names;
- express times and date ranges in an unambiguous format;
- verify that one operational fact remains per Memory, handing residual
  composites back to `atomize`;
- preserve an unresolved placeholder rather than inventing a missing value.

Normalization follows reconciliation and audience classification because a
sentence cannot be made fully explicit until its applicability, intended
recipient, and scope are known. Early atomization establishes the claim
boundaries; normalization later makes the resolved scope explicit without
changing those identities.

## Category placement

The semantic stage name is `place`. It assigns a normalized Memory to its
organizational Context. Later Task 1 fixture work introduced `sort` as a
possible user-facing name for bulk initial classification: `mem impact sort`
would preview the complete partition, while a separately confirmed
`mem sort` would apply structural moves. This vocabulary is not implemented
yet. Help must say “classify and place” if `sort` is adopted, because ordinary
CLI users may otherwise expect lexical ordering.

The Task 1 destination categories are:

```text
construction-updates/building-access
construction-updates/event-relocations
construction-updates/temporary-parking
construction-updates/shop-updates
construction-updates/facility-updates
construction-updates/route-changes
```

Placement is structural, not a rewrite. A deterministic `move` primitive will
likely be required beneath the semantic placement operation. Moving should
preserve the Memory UID, provenance, and relative order where possible. If one
Memory legitimately belongs in several categories, prefer one owning Context
plus `memory_ref` values over copied Memories that can drift apart.

The preview must account for every input exactly once through one destination
or an explicit hold disposition. It should also judge each proposed placement
against the active Goal and applicable Rules rather than treating plausible
category names as sufficient evidence. Whole-Context counts cannot reveal one
misplaced, protected, or irrelevant Memory.

## Proposed operation contracts

The command names below are working names. Their semantic boundaries are more
important than final CLI spelling.

| Stage | Working operation | Primary output | Mutation boundary |
|---|---|---|---|
| Envelope | `mem import` | source manifest, stage progress, linked provenance | preserves raw intake first; delegates every mutation to the confirmed stage contract |
| 1 | `mem impact atomize`; `mem atomize --save`; `mem atomize --save-as NAME` | exhaustive classifications, ordered split proposals, and recorded source-to-child lineage | preview saves a Context-scoped analysis but no Context checkpoint; in-place apply creates one checkpoint; save-as creates an init-like baseline and atomize checkpoint in a fresh Context |
| 2 | `mem find-duplicates` | positive pair evidence discovered from the whole direct Context | read-only; no checkpoint |
| 2a | future `mem dedup` | confirmed survivor and absorbed-UID plan | stale-safe confirmed groups apply as one checkpoint |
| 3 | `mem find-ambiguities` | unary interpretation and clarification findings | read-only; no checkpoint |
| 4 | `mem find-conflicts` | pairwise `YES`/`MAY` conflict findings and questions | read-only; no checkpoint |
| 5 | future `mem reconcile` | combined missing dimensions and clarification proposals | read-only first; edits require a separate confirmed plan |
| 6 | `mem audience` | applicability, recipient, purpose, and disclosure assignments | preview first; storage representation must be explicit |
| 7 | `mem normalize` | named rule violations and full replacement proposals | confirmed batch applies as one checkpoint |
| 8 | `mem find-duplicates` verification | post-normalization mechanical and semantic reclassification | read-only; any removal requires a new `dedup` plan |
| 9 | semantic `place`; proposed `mem impact sort` / `mem sort` surface | exhaustive destination-or-hold plan, Goal/Rule fit, and multi-category references | read-only preview first; staged apply requires a recoverable multi-Context boundary |

### `atomize`

- The implemented `mem impact atomize` inspects every directly owned Memory in
  one provider completion and returns a provisional, Context-ordered report.
- It never follows `context_ref`, `memory_ref`, or query-only sources, and it
  never uses neighboring Memories as hidden evidence for one source.
- Identifies clear composite Memories without resolving ambiguous modifier
  scope.
- Proposes ordered child contents without normalizing their wording.
- The impact report allocates no child UID and writes no Context checkpoint or
  directional `impact-plan.json`; it does persist one digest-bound analysis
  artifact per Context UID.
- Explicit apply gives every split child a fresh UID, records the ordered
  source-to-child mapping in checkpoint provenance, replaces each source at its
  original position, and preserves uncertain/non-propositional items in place.
- In-place apply blocks a `memory_ref` whose target is one of the selected
  Context's split sources; references to unchanged Memories do not block it.
  Save-as preserves the source, creates an init-like Context identity and
  baseline, applies there, and switches only after success.
- Local validation is repeated on load and apply, but an independent second
  semantic judge remains future work.
- Does not perform deduplication, reconciliation, audience inference, or
  deletion of non-propositional notes.

### `find-duplicates` and future `dedup`

- `find-duplicates` runs deterministic `EXACT`/`SURFACE_EQUIVALENT` detection
  before semantic classification and shows the tiers separately.
- Neither trust layer materializes every possible pair. Mechanical keyed
  components and semantic groups are rendered as canonical spanning evidence.
- Semantic duplicate detection emits `SEMANTIC_EQUIVALENT`; its calibration
  boundary distinguishes rejected `OVERLAP`, `UNKNOWN`, and `DISTINCT` pairs.
- The finder reports unordered positive duplicate pairs, not mutation-ready
  groups. If either Memory contains a unique fact, constraint, or exception,
  `OVERLAP` is a rejected calibration result and is not emitted as a duplicate.
- `UNKNOWN` is not a duplicate finding or a dedup outcome to apply.
- A future `dedup` plan keeps one stable survivor UID and its existing wording,
  and names every absorbed source UID. Canonical rewriting belongs to
  `normalize`; combining unique facts is a different integration operation.
- Referenced Memories cannot be removed until inbound references have been
  checked and safely migrated or the group has been blocked.

### `find-ambiguities` and `find-conflicts`

- `find-ambiguities` judges each direct Memory separately while using the
  selected Context as its ordinary-reading frame.
- It crosses `SINGLE`/`DOMINANT`/`COMPETING` interpretation with
  `NONE`/`HELPFUL`/`REQUIRED` clarification need.
- `find-conflicts` judges every unordered pair under the same local frame and
  distinguishes `YES`, `MAY`, and `NO`.
- `MAY` denotes competing ordinary readings with different conflict outcomes,
  not lower model confidence.
- Both operations are read-only, create no checkpoints, and do not propose
  rewritten contents.

### Implemented ambiguity review shell

- `mem review ambiguities` consumes the unary ambiguity report without
  changing the detector's semantics.
- It saves one selected proposed reading plus one untyped freeform response per
  finding; the response can refine, comment on, or replace a proposed reading.
- The session is bound to the Context UID and the complete ordered
  direct-Memory frame, and resume fails when that frame is stale.
- Source order means canonical `Context.order` for the user-study prototype;
  true Memory creation time is unavailable and remains a schema TODO.
- The ambiguity and Atomize controllers established the list/detail/response
  grammar now extracted as the operation-neutral `ResolutionWorkbench` view,
  UID action, and navigation layer. Meld uses its dynamic interactive adapter;
  Update exposes exact planned changes read-only. This is not a shared
  provider, persistence, or mutation engine, and Update semantic issue turns
  remain future work. `reconcile`, `distill`, and `sever` remain future or
  design-only contracts. Symmetric and public Context-directional `mem meld`
  are implemented through the bounded Context workbench.

The focused rationale is
[`memory-review-shell-design-rationale.md`](memory-review-shell-design-rationale.md).

### Future `reconcile`

- Consumes the separate ambiguity and conflict findings instead of replacing
  either detector.
- Treats missing scope as the default hypothesis, not proof that one statement
  is false.
- Records the dimension that could explain the difference and the evidence
  still required.
- Can conclude that two statements are already jointly explainable and need no
  edit.

### `audience`

- Supports several audiences for one Memory.
- Separates applicability, recipient, purpose/detail, and disclosure.
- Distinguishes intended recipient from enforced visibility.
- Records why each audience needs the information and which details they need.
- Must not remove facts merely because one audience should not see them.

### `normalize`

- Uses a named, inspectable rule set.
- Preserves meaning and does not resolve missing facts by guessing.
- Reports which rule caused each proposed edit.
- Operates on atomic Memory contents rather than performing identity-changing
  splits itself.

### `place`

- Chooses among existing organizational Contexts.
- Uses movement for ownership and references for legitimate multi-placement.
- Does not create duplicate content copies as a shortcut.
- Preflights every source and target before any Context is written.
- Updates or blocks every inbound `memory_ref` whose owner locator would change
  when the Memory moves.

The current store writes one Context at a time and does not provide a
multi-Context transaction. Therefore the first `place` implementation must not
claim crash-atomic movement across Contexts. It should remain a staged plan
until a recovery manifest or equivalent transaction boundary exists, or
clearly checkpoint every affected Context with a recoverable partial-failure
procedure.

## Cross-operation invariants

Every refinement operation should:

- be previewable without changing Contexts or checkpoints;
- show source UIDs, proposed result, and a human-readable reason;
- bind any reusable mutation plan to the Context UID and content fingerprint;
- refuse to apply a stale mutation plan;
- record one operation-level history event for a confirmed mutation; a
  multi-Context mutation requires linked checkpoints carrying one shared
  operation ID;
- preserve the raw intake through history or an explicit working branch;
- avoid opening query-only sources or treating model output as trusted IDs;
- preserve staged human clarification separately from canonical Memory
  content until an explicit, provenance-preserving apply contract exists;
- make no silent deletion, conflict resolution, audience inference, or move.

The operations should eventually be idempotent at their intended stage.
Re-running a finder on unchanged input should be evaluated for stability under
the same ruleset and pinned provider/model; this is a research target, not a
current guarantee for one-shot semantic completions. A mutation stage should
report no work when it is given the same already-applied operation ID. Stronger
semantic idempotency—independently deciding that newly created children need no
further split—belongs to the future validator and regression contract.

## Initial graph scope

Version 1 of every refinement operation should inspect only Memories directly
owned by the selected Context. A `memory_ref` is a view of a logical Memory,
not another content candidate, and must not be reported as a duplicate of its
target.

Recursive refinement is deferred until graph traversal has a canonical
logical identity such as `(owner_context_uid, memory_uid)`, visits shared or
cyclic Contexts once, preserves owner information, and folds references into
their target instead of counting them as copied contents.

## Iteration without changing the primary order

Early atomization exposes the claims that the primary dedup pass should
compare. Later reconciliation and audience classification can supply a missing
qualifier that proves a deferred candidate equivalent or distinct.
Normalization can also make two previously different surface forms
mechanically identical. The pipeline therefore includes a deliberate
read-only verification pass:

```text
atomize
→ find-duplicates
→ confirmed dedup
→ find-ambiguities
→ find-conflicts
→ reconcile
→ audience
→ normalize
→ duplicate verification
→ place
```

An `uncertain` atomization is not treated as atomic merely because a finder can
inspect it. Its quality finding records the stored Memory boundary; after a
later clarification supplies the missing scope, that item returns to
`atomize` and then enters the quality-analysis phases. This is a targeted
retry, not permission for atomization or a finder to guess.

Verification does not silently apply previously deferred candidates. Any new
removal requires a new `dedup` plan. This check does not collapse detection
and mutation or change their primary order.

## Current Task 1 implications

The 51 Memories in `temp/task-1` are raw intake, not final fixture data.
Immediate examples are:

- rear-door closure and staff-entrance availability each contain semantic
  dedup candidates, but their instruction-versus-fact and scope differences
  still require review;
- physical-card versus app access may produce ambiguity or conflict findings
  that a later `reconcile` can combine; it is not safe dedup;
- restroom directions differ by visitor and accessibility audience;
- public closure guidance and internal construction reasons need different
  audiences and detail levels;
- long store, restroom, and parking Memories need atomization and
  normalization;
- the final facts belong in the six `construction-updates/*` Contexts.

The saved `mem impact atomize` report, explicit apply paths, trace lineage, and
golden regression harness now implement the preferred source boundary.
`find-duplicates`, `find-ambiguities`, and `find-conflicts` remain separate
read-only commands so that their whole-Context relation discovery, pair-target,
and unary contracts stay observable. Stronger independent atomize validation,
a future `dedup` apply path and `reconcile`, followed by `audience`, `normalize`,
duplicate verification, and `place`, can then be added one at a time. A later
`mem import` may orchestrate those same tested operations without replacing
their visible findings, plans, reasons, or checkpoints.
