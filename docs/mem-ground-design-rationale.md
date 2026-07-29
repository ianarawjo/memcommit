# Named common-grounding sessions

## Status

The implementation has two explicit stages. It first creates or resumes a
named empty version-1 scaffold, then an explicit binding action upgrades that
scaffold to a version-2 workbench:

```bash
mem ground task-1-fixture \
  --goal "Agree on the wiki and local Task 1 Memory contents." \
  --scope campus-wiki \
  --scope construction-updates \
  --snapshot

mem ground task-1-fixture --snapshot

mem ground task-1-fixture \
  --description "Use verified Main Building changes to update the wiki." \
  --raw-context temp/task-1 \
  --derived-context temp/task-1-atomized \
  --publication-target campus-wiki \
  --placement-target construction-updates/building-access \
  --snapshot
```

The bound workbench can select a candidate, propose a Working Rule by itself,
attach multiple fit, boundary, or contrast cases to one rule, retain the
earlier combined rule/case shortcut, accept/refine/defer/reject a proposal, and
revise its Goal or one target criterion. Refining an accepted rule or case
reopens it as `PROPOSED`; it must be accepted again. The workbench does not yet
run a semantic provider, open a TUI, perform semantic regression
automatically, approve the whole contract, or edit any Context. The empty
scaffold remains intentional: no rule or example is generated merely because
a session was created.

### Immediate next integration TODO

The atomize workbench now has the first implemented adapter for a structured,
multi-turn conversational grounding loop. The immediate next task is to
extract its reusable turn engine into `mem ground`. This integration is not
implemented by the current deterministic named-ground workbench.

The reusable portion should cover append-only turns, active and superseded
user-supported propositions, agent implications, follow-up questions,
corrections, explicit permission, and stale-frame checks. Atomize-specific
issue identities, source arity, and edit proposals must remain in its adapter;
named-ground Goals, Working Rules, Cases, Decisions, and regression checks
remain in the `ground` adapter.

The reason for this ordering is methodological as well as architectural.
Atomize provides a bounded concrete interaction in which a reviewer can say,
in effect, "if that is true, this later statement must also change," correct
the agent's extension, and then approve the resulting change set. That pattern
resembles grounding in ordinary human communication. `mem ground` should
generalize the proven pattern rather than begin with an abstract chat layer
whose epistemic stages have not been exercised.

No current atomize grounding session is a named ground, and no named ground
automatically contributes evidence to atomization. Artifact migration,
cross-operation import/export, and a shared schema are deferred until their
compatibility and provenance boundaries are designed. The focused rationale
is recorded in
[`mem-review-conversational-grounding-design-rationale.md`](mem-review-conversational-grounding-design-rationale.md).

## Decision

`ground` is the session-level operation for a person and an agent to establish
and maintain a local judgment or data-design contract. The contract grows
through concrete cases, readable rules, corrections, boundary examples, and
explicit decisions.

The long-term loop is:

```text
present one concrete case
→ judge it against the currently accepted contract
→ retrieve a supporting case and a materially close contrast
→ apply the contract, curate a case, or induct a rule delta
→ show the rule and case diff
→ let the user accept, correct, supply context, or enter a closer case
→ regression-check previously accepted cases
→ repeat
```

Retrieval of supporting and contrast cases, semantic regression, and
whole-contract approval are not yet automated.

The operation is complete only locally: reviewed cases in the named scope are
adequately explained, unresolved boundaries remain explicit, regression checks
pass, and the user explicitly approves the contract. Neither the model nor a
count threshold may infer approval.

## Operation hierarchy

The discussion originally gave `induct` too much responsibility. The revised
hierarchy is:

| Concept | Responsibility |
| --- | --- |
| `ground` | Persist and orchestrate the complete interactive common-grounding loop. |
| contract check | Judge whether the current rules and accepted cases already explain a candidate. This is a stage, not a new public `fit` command. |
| `induct` | Propose a reusable rule, exception, narrowing, or broadening from reviewed cases. |
| case curation | Find, enter, or retain fit, boundary, and contrast cases. It is initially an internal grounding action rather than a public command. |
| regression check | Show whether a proposed rule or case decision changes previously accepted judgments. |
| `fill` | Use an established requirement/evidence contract to propose missing target content. |
| `dream` | Perform background discovery or consolidation; it may enqueue a grounding candidate but cannot approve it. |
| `review` | Provide a reusable interaction surface for an already defined finding adapter; it is not the semantic grounding process. |

The earlier `fit` notes use `YES / MAY / NO` for whether Memories fit together
inside a Context. Reusing the public name for case-to-rule coverage would make
those polarities ambiguous. Grounding documentation may use the ordinary
phrase "fit the current rule," but the first CLI should call that stage a
contract or coverage check.

## Why the name is `ground`

The name comes from the project's own research history rather than only from
an external analogy.

- IdeenKasten `20260324193916` explicitly calls iterating rules with an AI a
  "common grounding" step.
- `20260324193907`–`20260324193910` describes the human providing approximate
  intent, the AI proposing a readable logical rule, the human reviewing it,
  and the system showing a rule diff.
- `20260324193917` turns the `all-too-common` cloze failure into a concrete
  boundary case that corrects an overly broad exception.
- `20260427090004`–`20260427090010` repeats the same sequence: expected
  input/output examples, a proposed rule, a failure revealing an incorrect
  boundary, a correction, and a rerun. `20260427090007` explicitly requires
  repetition.
- `20250922034205` observes that collecting Memories without a user-editable
  grounding and review process is insufficient.
- `20251112083908` describes common ground as a network the user and AI build
  together to prevent interpretation errors from accumulating.

The relevant local, non-vendored archive is:

```text
IdeenKasten/gum_projects/using_ideenkasten/my_GUM_data.json
```

`calibrate` was considered as the public name. It describes adjusting a fixed
boundary, but it does not comfortably include forming new rules, establishing
vocabulary, or constructing shared task knowledge. `teach` and `train` make
the interaction sound one-directional or like parameter training. `align` is
too broad and collides with AI-alignment terminology. `ground` preserves the
mutual, longitudinal meaning already present in the local record.

## Common grounding versus evidence grounding

Memcommit also uses "grounding" to mean that an atomized claim is supported by
a source span. These meanings must remain explicit:

- **evidence grounding** asks whether a stored claim is supported by its
  declared source;
- **common grounding** asks whether the user and agent have established a
  shared, inspectable local contract for interpreting and judging cases.

One does not prove the other. A source-supported sentence can still be
interpreted differently, and a mutually accepted rule can still lack adequate
source evidence.

## Agent-suggested external precedents

The following readings were introduced by the agent during the naming and
workflow discussion. They are saved for later reading as external design
precedents, not as user-provided requirements, adopted dependencies, or proof
that memcommit should copy their representations.

1. Gonzalo Ramos et al.,
   [Interactive machine teaching: a human-centered approach to building
   machine-learned models](https://www.microsoft.com/en-us/research/publication/interactive-machine-teaching-a-human-centered-approach-to-building-machine-learned-models/).
   The relevant resemblance is an iterative human-guided process that produces
   inspectable task behavior. Memcommit grounding is broader and need not train
   model weights.
2. Debbie Richards,
   [Two decades of Ripple Down Rules
   research](https://doi.org/10.1017/S0269888909000241).
   The relevant resemblance is case-triggered rule refinement that preserves
   previously accepted case judgments through contrastive cases. Memcommit
   does not adopt the RDR tree format.

Each new session records these references with:

```text
provenance = AGENT_SUGGESTED_EXTERNAL_PRECEDENT
reading_status = UNREAD
```

This preserves who introduced the material and prevents an unread reference
from silently becoming part of the accepted grounding contract.
`UNREAD` specifically means that the user has not marked the saved reference
as read in memcommit; it does not claim that no agent, author, or other person
has read the source.

## Named-session contract

Grounding is not bound to the global current Context. A Task 1 contract may
cover `campus-wiki` plus several local construction-update Contexts, while a
different agent works on Task 2. Therefore sessions are named and independent:

```text
~/.mem/ground-sessions/
├── task-1-fixture.json
├── task-2-fixture.json
└── task-3-fixture.json
```

The portable contract name is restricted to:

```text
[a-z0-9][a-z0-9._-]{0,127}
```

It is an identity label, not a path. `/`, `..`, uppercase letters, spaces,
control characters, Windows device names such as `con` and `nul`, and
symbolic-link storage are rejected. Running the same name again resumes the
same UID without rewriting its bytes. Creation options cannot silently
redefine an existing contract; `--replace-ground` is the explicit
destructive/recovery boundary.

There is deliberately no active-ground pointer. Requiring the contract name
avoids a global switch whose state could collide across terminals or agents.
The command is intentionally create-or-resume, so `--snapshot` also creates an
empty contract when the supplied name does not exist. A mistyped name can
therefore create an extra empty file; listing, renaming, and archiving named
grounds remain future CLI work.

## Schema

Version 1 saves:

- a canonical session UUID;
- portable contract name;
- goal and completion criterion;
- descriptive scope labels;
- `OPEN` status and revision zero;
- an empty item list reserved for future `RULE`, `CASE`, `ISSUE`, and
  `DECISION` records;
- attributed methodological references.

The schema describes the intended shape of future items—origin (`USER`,
`AGENT`, or `JOINT`), status, iteration, rationale, expected result, and
related-item references—but version 1 rejects every non-empty item list. It
also rejects `GROUNDED`, nonzero revisions, substituted references, and even a
boolean masquerading as schema version `1`. This fail-closed boundary prevents
hand-edited JSON from impersonating user approval before decision and
regression invariants exist.

Version 2 is introduced only by explicit frame binding. It additionally saves:

- a copied, content-digested source brief;
- exact raw, derived, publication-target, and placement-target Context frames;
- an editable Goal and editable per-target requirements;
- proposed or reviewed rules, cases, and decisions;
- structured source-Memory and target-Context references;
- a rule provenance of `USER_STATED`, `DISTILLED_FROM_GOAL`,
  `INDUCED_FROM_CASES`, or `JOINTLY_REVISED`; and
- one durable candidate cursor.

Version 1 remains fail-closed and is never silently reinterpreted as version
2. A saved rule/case proposal and a review decision each advance the semantic
revision exactly once. Moving the cursor does not.

The whole serialized object is strictly revalidated before atomic replacement.
Load rejects duplicate JSON keys, unknown fields, malformed UUIDs, unknown
references, invalid names, and symbolic links.

## Confirmed Task 1 frame

The Task 1 grounding surface has two deliberately different regions. This is a
data-model distinction, not merely a proposed screen layout.

The **upper region is the editable contract**, expressed in three layers:

1. `GOAL`: the top-level result the fixture and operation should achieve;
2. `WORKING RULES — DISTILLED / INDUCED`: generalizations distilled
   top-down from the Goal, induced bottom-up from cases, stated by the user,
   or jointly revised; and
3. `CASES — FIT / BOUNDARY / CONTRAST`: proposed or reviewed examples that
   fit or challenge the current rules. Only explicitly accepted cases are
   golden regression anchors.

The copied Task description is displayed above these layers as a fixed source
brief. It is evidence about why the workbench exists, not the entire editable
contract. Target-specific success criteria are displayed inside the Goal layer,
not as a fourth semantic layer. The Goal and those criteria may change when
lower cases expose a poor category, impossible requirement, or missing
distinction. Such a change is a new revision with its reason recorded; it is
not a silent edit.

The upper region says what must exist when the fixture is adequate, what is
currently missing, which decisions have been approved, and which gaps remain.
It contains:

- the fixed Task 1 source brief and editable Goal;
- the expected `campus-wiki` organizational baseline and publication role;
- the six required local destination slots;
- each slot's ledger-derived `EMPTY`, `PARTIAL`, or `COVERED` state, or its
  explicitly recorded `BLOCKED` state;
- working rules and accepted golden cases that justify coverage; and
- unresolved requirements that must not be filled by invention.

The required local slots are:

```text
construction-updates/building-access
construction-updates/event-relocations
construction-updates/temporary-parking
construction-updates/shop-updates
construction-updates/facility-updates
construction-updates/route-changes
```

The initial `campus-wiki` Context and all six local Contexts currently contain
zero direct Memories. In particular, the scenario describes `campus-wiki` as
an extensive organizational source, but that baseline fixture has not been
provided. The Task 1 session therefore records an explicit `BLOCKED` reason
for that target; it must not silently treat the construction notes as the
pre-existing wiki or synthesize a baseline. `ground` displays this recorded
judgment but does not infer it from the empty Context alone.

The four target states are a derived display, not a fourth contract layer:

| State | Meaning |
| --- | --- |
| `EMPTY` | No accepted `INCLUDE` case backed by an accepted Working Rule satisfies the slot. |
| `PARTIAL` | Some such distinct source cases satisfy the slot, but the recorded minimum is not met. |
| `COVERED` | The recorded minimum is met by accepted `INCLUDE` cases backed by accepted Working Rules, counting each source Memory once per target. |
| `BLOCKED` | The session records a judgment that continuing requires missing evidence. This is not inferred automatically. |

These are grounding-ledger states, not a count of files in a directory.
`EMPTY`, `PARTIAL`, and `COVERED` are derived from the reviewed ledger;
`BLOCKED` is currently an explicit criterion field. For example, the current
notes describe event closures and parking closures but do not give a concrete
relocated event destination or replacement parking location. The session may
record those targets as blocked until evidence or the criterion changes.

The **lower region is the evidence-to-target workbench**. Its bound frames are:

```text
raw evidence       temp/task-1                    51 Memories
working candidates temp/task-1-atomized           54 Memories
targets            campus-wiki + six child Contexts
```

The 51-to-54 change identifies the inspected input and derived candidate set;
it is not by itself evidence that atomization succeeded. The current schema
content-addresses each case to exactly one Memory in the working-candidate
Context. It does **not** yet persist the candidate-to-raw span mapping, so the
snapshot does not claim to show a raw trace. The workbench can select a
candidate, propose targets and expected wording, attach it to an existing
Working Rule, and accept, refine, defer, or reject it. `REFINE` currently
changes rule wording or a case's expected output; changing a case's targets,
role, disposition, rationale, or raw provenance remains follow-up work. A
proposed placement may name `campus-wiki`, one of the six local slots, or both
when their distinct source-of-change and publication roles justify the
duplication.

The upper contract must not be mixed into the lower candidate list. The top
answers “what are we trying to achieve, what rules currently express it, and
which reviewed cases support those rules?” The bottom answers “what evidence
and derived candidates can justify or revise a particular target decision?”

This is deliberately bidirectional. A Goal or rule may suggest how to judge a
lower case, while a stubborn or awkward lower case may justify revising the
rule or even the Goal. An accepted rule can be refined and reopened. Because
only accepted rules support coverage, its accepted cases stop contributing to
`COVERED` until the revised rule is accepted again. A Goal or target-criterion
revision is recorded with a reason, but automatic semantic regression of
prior cases remains follow-up work.

## Proposed cases, golden cases, and the first review round

An agent-produced case is `PROPOSED`. It has no contractual authority, does
not count toward `COVERED`, and is not a regression anchor. A **golden case**
is the user-approved form of a concrete judgment: its evidence trace, target
slot, expected target content or disposition, and rationale have all been
reviewed. Golden cases may be tagged as fit, boundary, or contrast evidence,
but the tag does not replace explicit approval.

The implemented deterministic slice supports the following recorded actions:

```text
select one of the 54 bound working candidates
→ show its wording and candidate UID/digest
→ propose a Working Rule alone, or attach a case to an existing rule
→ propose target Contexts, expected wording, disposition, and rationale
→ let the user accept, refine expected wording, defer, or reject
→ save that decision only in the named ground session
→ recalculate target status from accepted INCLUDE cases and accepted rules
```

If the user refines the proposed expected output, the revised proposal must be
accepted before it may become a golden case. A deferred case becomes
`DEFERRED` and does not improve target coverage. Missing-context entry,
target/disposition correction, and automatic regression reporting are not yet
part of the case-review action; a target criterion can instead be revised
explicitly with a recorded reason.

This vertical slice establishes one bound candidate, one content-addressed
candidate reference, one target decision, one explicit approval boundary, and
one derived status change. It deliberately does not claim a raw trace or
semantic regression result. Subsequent fixture work should establish at least
one approved seed case for each coverable target slot rather than assuming
that an empty slot is explained by its name.

## Bound frames and stale work

A semantic ground session must bind every frame it reads rather than repeatedly
consulting mutable current Context state. The planned binding records the
Context UID, locator, canonical digest, and direct-Memory count for the raw,
candidate, and target frames. The Task 1 description should be copied into or
content-addressed by the contract so that moving an attachment does not change
the brief being reviewed.

Before a provider call and again before saving a round, all bound digests must
match. A change to any bound raw, candidate, or target Context marks the
workbench `STALE`. Prior proposals and reasoning remain inspectable as history,
but stale work cannot:

- be promoted to a golden case;
- change a slot to `COVERED`;
- approve the contract; or
- be exported for later target application.

There is no refresh/fork command in this slice. Today the reviewer must create
a new named contract, or deliberately use `--replace-ground` and repeat the
explicit binding. A future non-destructive refresh should create a new
revision and require affected proposals to be checked against the new frame;
it must not silently rebase an old judgment onto changed evidence.

The current binding hashes the Context projection returned by the store
loader. A broken or unresolved `context_ref` can be omitted before that
projection is digested, so version 2 does not prove that every serialized
pointer was resolvable at binding time. The Task 1 frames use directly owned
Memories, but a future reference-aware contract must hash the raw stored item
ledger as well as the resolved projection and report unresolved references
explicitly.

## First snapshot

An empty snapshot intentionally exposes absence rather than inventing a
starting rule:

```text
GROUND · task-1-fixture · OPEN
Revision: 0

GOAL
  Agree on the wiki and local Task 1 Memory contents.

COMPLETION
  The reviewed cases in the current scope are adequately explained ...

SCOPE  campus-wiki, construction-updates
RULES 0 · CASES 0 · UNRESOLVED 0 · DECISIONS 0

No grounding material has been recorded.
The session is ready for jointly reviewed rules and cases.
```

The snapshot also shows the two agent-suggested readings and their `UNREAD`
status. Terminal control characters are neutralized.

## Mutation, privacy, and approval boundaries

Creating or resuming an unbound ground does not read a Context. Binding and
rendering a bound workbench do load its recorded direct Context projections
to calculate and verify digests. Across both paths, `ground`:

- does not require a current Context;
- does not connect to a semantic provider;
- never opens a query-only source; a bound snapshot may display the selected
  direct working-candidate Memory;
- does not alter `state.json`, a Context, or a checkpoint;
- does not claim that any rule or case has been approved.

This non-mutation boundary remains in force for the implemented workbench.
Reviewing a placement, promoting a proposal to a golden case, changing an
upper-region status, or even marking the contract `GROUNDED` changes only the
named grounding artifact. It must not add, edit, or delete a Memory in
`campus-wiki`, `construction-updates`, or either temporary source Context, and
must not create a target checkpoint. Materializing approved decisions into
target Contexts is a separate, explicit future action with its own preview and
checkpoint boundary.

When semantic rounds are added, query-only content must remain opaque. Direct
Context evidence must be fingerprinted before a provider call and checked
again before a round is saved. A changed frame may leave prior reasoning
inspectable, but it must block new promotion. The current recovery is a new
named contract or explicit replacement/rebinding; refresh/fork remains future
work.

`GROUNDED` will require explicit user approval, no unresolved required
boundaries, at least one accepted rule or case, and a regression report for
the approved revision. A provider cannot set this status by itself.

## Task 1 use

The first contract is `task-1-fixture`. Its goal is to establish which
Memories belong in the missing `campus-wiki` fixture and which belong in the
six local Task 1 construction-update Contexts. The organizational wiki and
local updates have different roles, so an explicitly justified fact may appear
in both; identical content is not automatically an accidental duplicate.

Within the eventual semantic review loop, the workbench should submit one
concrete placement or content case, show its raw trace plus the nearest
supporting and contrast cases, then let the user:

- apply the current contract;
- correct the proposed judgment;
- refine or add a rule;
- retain the case as fit, boundary, or contrast evidence;
- enter a closer case or missing context; or
- defer the candidate.

The current deterministic slice records rules, cases, candidate-level
references, and explicit decisions. Raw trace retrieval, nearest-case
retrieval, automatic batch generation, and whole-contract approval remain
future work.

## Alternatives and intentional limitations

- Reusing `ReviewSession` was rejected because its schema and rendering are
  specifically tied to ambiguity findings, reading choices, one Context
  digest, and one response field.
- A single active `ground-session.json` was rejected because Task 1, Task 2,
  and multiple agents would overwrite or switch shared global state.
- Automatically seeding rules from the external readings was rejected because
  methodological resemblance is not accepted domain knowledge.
- Automatically binding the empty ground to current Context bytes was rejected.
  Binding is now explicit because the Task 1 contract spans multiple Contexts
  and the source/target choices are part of the experiment.
- Treating the 51 raw Memories and 54 candidates as the target contract was
  rejected because evidence availability and fixture requirements answer
  different questions.
- Inferring a plausible `campus-wiki` baseline was rejected because it would
  conceal the target fixture's current absence and make before/after update
  behavior impossible to audit.
- Writing approved ground decisions directly into target Contexts was rejected
  because review, contract approval, and data materialization need separate
  failure and consent boundaries.
- Treating every provider proposal as a golden example was rejected because it
  would let generated judgments bootstrap their own apparent coverage.
- A TUI with arrow-key navigation, chat-to-TUI remote control, provider round,
  semantic regression evaluator, target materialization action, compare-and-
  swap concurrency guard, whole-contract approval action, and archive/fork
  workflow are not implemented in this slice.
- Importance ordering, creation-time ordering, affected-decision estimates,
  automatic batch generation, inherited or predecessor Context handling, and
  integrated ambiguity/conflict resolution remain deferred. The first
  user-study slice may preserve the original Memory order.
- Frame digests currently cover the store-loaded projection, not a separate
  raw serialized pointer ledger; unresolved `context_ref` detection is
  deferred to a reference-aware binding version.
