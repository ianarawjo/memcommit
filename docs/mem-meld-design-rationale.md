# Meld modes and shared contract

## Status

This note distills the shared semantic-meld contract and its two authority
modes. The first public Context-to-Context symmetric path now exists as a
bounded research prototype:

```text
mem init RESULT
mem meld LEFT_PEER RIGHT_PEER
```

It performs one aggregate analysis, saves a resumable relation ledger and
workbench, accepts issue-scoped or whole-set comments, supports preserve-all
and provider-free defer, and applies an exact ready proposal only through
`--accept`.

The earlier local conversational change flow inside atomize grounding is also
retained:

```text
mem atomize --evaluate ISSUE --comment TEXT
→ mem atomize --reply TEXT
→ mem atomize --accept-grounding
```

That flow remains under its existing atomize command and strict schema. It now
reuses the common meld turn-lineage contract and has a lossless
issue-scoped directional adapter view; it is not silently renamed or migrated.
A public Context-to-Context directional command remains unimplemented.

## Why meld is needed

Users rarely add only a new, independent sentence to an already curated
Context. Recurring intake commonly contains a mixture of:

- a fact already represented under different wording;
- a supported extension of an existing fact;
- an explicit correction;
- a distinct new fact;
- an unresolved reference or qualifier;
- a claim that appears incompatible until time, place, audience, authority, or
  another missing scope is supplied.

Treating all of those as literal `add` operations produces duplicate,
overlapping, or conflicting Memories. Re-running whole-Context atomization
does not solve the problem: atomization establishes the boundaries of claims,
but it does not decide how newly prepared claims relate to an existing
baseline.

The existing commands each cover only part of the required behavior:

| Existing operation | Useful responsibility | Remaining gap |
| --- | --- | --- |
| `add` | Deterministically preserves literal input and source order. | It does not interpret, compare, or reconcile the input. |
| `atomize` | Produces source-grounded atomic candidates and preserves uncertainty. | It does not decide whether a candidate is already represented, corrects a target, or belongs in a peer result. |
| `merge` | Copies direct items whose UIDs are new to a target. | UID novelty is not semantic novelty, and the command performs no reconciliation. |
| `impact` / `update` | Plans a directional publication-style update from verified A to target B. | It assumes source authority and does not express peer authority, case-level clarification, or a reusable meld relation ledger. |
| legacy `integrate` | Distinguishes duplicate, update, and novel input for one assumed Memory. | It assumes the input is already suitable, lacks full ambiguity/conflict grounding, and does not supply the shared provenance or authority contract. |
| atomize grounding | Demonstrates clarification, downstream effects, exact edits/additions, and explicit acceptance. | It is deliberately anchored to one atomize issue rather than a general incoming or peer Context. |

Without a meld operation, a person must manually atomize new notes, search for
related Memories, compare meanings, decide whether to add or edit, investigate
ambiguity and conflict, preserve provenance, and verify downstream effects.
That repeated explanation is precisely the burden a semantic memory operation
is intended to reduce. Meld compresses those steps without hiding which
semantic judgment caused each result.

The need appears at three scales:

1. **Local clarification.** One user explanation changes an issue and possibly
   several downstream Memories.
2. **Recurring intake.** New atomic candidates must enter a trusted baseline
   without reprocessing unrelated knowledge.
3. **Peer combination.** Independent Contexts with equal authority must be
   combined without silently favoring either source.

These are not three unrelated features. Each requires source roles, relation
judgments, consequential follow-up, an exact proposed change set, explicit
permission, and source-to-result provenance. Treating them as meld adapters
lets the prototype test one shared semantic contract at increasing scale.

## Why the operation is called meld

The name was selected from the behavior required by three initially separate
scenarios, not by renaming an existing `merge` command:

1. **Atomize clarification** showed that one explanation may reinterpret one
   selected issue, correct a current Memory, add a missing Memory, and change
   the reading of other issues.
2. **Incremental local intake** showed that new atomic Memories cannot simply
   be appended. They must be related to a baseline as duplicate, extension,
   correction, independent knowledge, conflict, or unresolved scope.
3. **Task 2 peer combination** requires two co-advisors' policy Contexts to be
   combined without favoring either advisor. Equivalent policies should be
   consolidated, scoped policies should retain their conditions, and
   incompatible policies should either be reconciled with the user's help or
   preserved with an explanation.

`add` describes only insertion, `merge` in the current implementation describes
UID-based copying, and `update` implies an authoritative direction. `Reconcile`
describes only the unresolved part. None names the complete act in all three
scenarios.

`meld` was chosen because the common act is to **form an explicit target from
memory-bearing inputs after deciding their semantic relationships, without
assuming that either input must disappear or win**. It permits consolidation
where support exists, preserves distinctions where scope matters, and exposes
questions where no justified combination is yet available.

The three motivating scenarios therefore share one operation rather than
merely sharing a UI:

```text
bind sources, roles, target, and authority
→ propose a complete relation ledger
→ surface decisions that need human grounding
→ propagate each explanation across the bounded frame
→ present an exact revised change set
→ apply only explicitly accepted outcomes
→ retain source-to-result provenance
```

Issue-scoped directional, Context-wide directional, and symmetric adapters
differ in source cardinality, authority, and mutation target. Their semantic
relation ledger, conversational turns, proposal review, acceptance boundary,
and provenance requirements are the same. That shared contract is the reason
to generalize them as meld.

## Atomize grounding is already an issue-scoped meld

The distinction is between atomization itself and the interactive grounding
that follows it.

- **Atomization** transforms a raw source Memory into source-grounded atomic
  candidates while preserving anything it cannot justify splitting or
  interpreting.
- **Atomize grounding** takes a selected ambiguity, one proposed reading or a
  new user explanation, and the current local analysis frame, then decides how
  that explanation changes the existing proposal and Context.

The second operation has the complete meld shape:

```text
select one ambiguity
→ treat the selected reading or free-form explanation as incoming evidence
→ relate it to the source Memory, current proposal, and affected local Memories
→ confirm, extend, correct, retract, or leave the interpretation unresolved
→ produce exact EDIT / ADD consequences
→ ask about newly exposed consequences
→ apply the accepted change set to the existing Context
```

Choosing an offered reading is not merely setting a UI flag. It confirms one
semantic relationship and may invalidate an existing proposal. Entering a new
reading may add a missing distinction or correct both the selected Memory and
other Memories that depended on the same assumption. The explanation is
therefore a small memory-bearing input, and the current Context is its
directional baseline. This is an **issue-scoped directional meld embedded in
the atomize workflow**. The engine remains batch-shaped: its bounded frame can
contain the selected issue, a pair-shaped conflict, and several downstream
issues. “Atomic” describes the initially selected scope, not another execution
mode.

This interpretation does not mean that `mem atomize` should be renamed.
Atomize remains the user-facing operation because it owns source decomposition,
its analysis artifact, and the reason the ambiguity was surfaced. Meld is the
shared semantic change protocol used once an interpretation must be combined
with that artifact. Keeping the entry point while extracting the common
protocol preserves a coherent task narrative and avoids two commands claiming
the same saved atomize session.

## Conversation as repeated grounding and meld

The design conversation that produced this contract follows the same pattern.
Each user turn may confirm an earlier interpretation, correct it, add a
constraint, preserve an alternative, or reveal that a proposed generalization
was too broad. The agent compares that turn with the current shared artifact,
describes its consequences, and changes the implementation or rationale only
after the intended reading is sufficiently grounded.

Not every conversational sentence becomes a persistent Memory, and the model
must not treat mere recency as authority. The reusable unit is an accepted
semantic contribution together with:

- the artifact or decisions it relates to;
- whether it confirms, extends, corrects, distinguishes, or leaves them
  unresolved;
- the consequences inferred across the current bounded frame; and
- the exact artifact changes the user accepted.

`ground` and `meld` describe complementary parts of this interaction:

- **Ground** negotiates the shared goal, rules, readings, and representative
  cases until the parties have enough common understanding to act.
- **Meld** incorporates an accepted contribution into the current artifact
  under explicit source, authority, target, and provenance constraints.

A turn may alternate between them several times: ground a reading, preview its
meld consequences, discover a new question, ground the answer, and finally
accept the resulting meld. This explains why both atomize clarification and
Task 2 peer-policy combination can reuse the same list/detail/comment/impact/
accept interaction even though their source roles differ.

Meld is also necessary for negative outcomes to remain intelligible. If an
incoming statement does not appear as a new Memory, the user and later
`trace`/`rationale` operations must be able to distinguish:

- it was already represented;
- it was incorporated by an accepted edit;
- it was coalesced only in a new target;
- it remains unresolved or deferred; or
- it was rejected.

A summary such as “three Memories added” cannot preserve those distinctions.

## Distilled definition

**Meld combines memory-bearing inputs into an explicit target while preserving
supported distinctions, source identity, and the user's authority over
unresolved interpretation.**

Meld is not concatenation. It must determine whether an incoming proposition:

- is already represented;
- extends or corrects an existing Memory;
- is compatible but independently useful;
- conflicts under an ordinary local reading; or
- cannot yet be placed because its reading or scope is unresolved.

The model may propose those judgments. It may not approve them, silently
delete source content, invent a missing fact, or treat an unexplained
difference as evidence that either side is false.

## Authority modes and turn scope

Meld has two actual modes. They describe authority and target direction:

| Mode | Inputs | Authority contract | Target | Representative case | Current status |
| --- | --- | --- | --- | --- | --- |
| **Directional** | Prepared incoming evidence plus an existing baseline frame | The baseline is preserved except where accepted incoming evidence explicitly extends or corrects it | The baseline's next state | A physical-card clarification changes student guidance; a parking correction updates an existing closure Memory | Atomize grounding shares turn-lineage validation and a lossless `DIRECTIONAL` / `ISSUE` adapter projection; public Context-to-Context form remains future |
| **Symmetric** | Two independent Context frames treated as peers | Neither source wins by default; source-specific scope and unresolved differences remain visible | A distinct new result Context | Two co-advisors' proposal-writing policies | Implemented for two direct-Memory Contexts |

`atomic` and `batch` are not additional modes. The semantic call always
receives one complete bounded batch. What changes during interaction is the
scope of the user turn:

| Turn scope | Meaning |
| --- | --- |
| `ISSUE` | The user addresses one selected issue, while the provider still recomputes consequences across the complete bounded batch. |
| `REMAINING` | One instruction, such as preserve-all, governs every still-unresolved relation. |
| `ALL` | One comment may revise the interpretation of the complete relation ledger. |

An “atomic” case is therefore the special case in which the selected scope has
one primary issue or proposition. It may still affect several downstream
Memories. Unary ambiguity and pair-shaped conflict are both valid issue scopes.

Task 2 begins with one batch symmetric analysis. Opening the compensation issue
does not launch a different atomic engine; it creates an `ISSUE`-scoped turn
within the saved batch. The result returns to the complete relation ledger,
where it may resolve or alter other pending issues. A whole-set comment or
preserve-all action uses `ALL` or `REMAINING` over the same session.

This makes meld compositional rather than merely UI-reusable. The user changes
the turn's **scope**, not the semantic machinery, when moving between overview
and detail.

### Context-to-Context v1 boundary

The first public `mem meld` deliberately supports only two named source
Contexts. For Task 2, both sources have the `PEER` role and the active empty
Context is the result target:

```text
mem init jingyue/proposal-writing-policy
mem meld ian/proposal-writing-policy damien/proposal-writing-policy
```

This is a useful product boundary, but `Context` should not be the lowest-level
semantic type in the implementation. The core should consume bound
**MeldFrames**: ordered sets of direct Memory records with source identity,
role, digest, and declared authority. The public command deterministically
converts each named Context into one frame. The atomize adapter can construct a
smaller frame from one issue and its demonstrated local dependencies without
creating a fake persistent Context.

That separation permits genuine generalization:

- Context + Context symmetric meld uses two `PEER` frames and a distinct new
  target.
- Context + Context directional meld uses `INCOMING` and `BASELINE` frames and
  may propose a next state for the baseline.
- Atomize grounding uses one `CLARIFICATION` frame and one issue-bounded
  `BASELINE` frame through the same turn and proposal contract.

The v1 command need not expose every adapter. Supporting Task 2's symmetric
Context-to-Context path first does not require pretending that the
issue-scoped atomize adapter has the same CLI syntax.

Initial Context-to-Context analysis is intentionally bounded:

- read direct owned Memories only;
- keep both source Contexts read-only;
- require the active target to differ from both sources and be empty for the
  first symmetric implementation;
- bind source and target Context UIDs, names, complete direct-record digests,
  and Memory order;
- reject an over-limit source rather than silently truncate it;
- never dereference query-only Contexts or use hidden query content;
- reject Memory references, query-only references, and embedded Contexts
  explicitly in version 1 rather than silently omitting them or treating their
  targets as direct evidence.

Relations should be represented as groups of source aliases, not as a
pre-enumerated Cartesian product of Memory pairs. One policy on one side may
correspond to several narrower policies on the other, and several Memories may
jointly support one scoped result. Pair-only storage would lose that structure
and reproduce the scaling problem avoided by the one-shot analysis.

The common core therefore generalizes the **process and invariants**, not every
mode-specific judgment label. Symmetric mode cannot use “the incoming source
corrects the baseline” without introducing a false authority direction.
Directional and symmetric adapters may expose different allowed relation and
resolution labels while sharing frame binding, issue navigation, dialogue,
impact propagation, proposal validation, acceptance, checkpoint, and
provenance machinery.

## Operation hierarchy

The surrounding operations have separate responsibilities:

| Operation or stage | Responsibility |
| --- | --- |
| `import` | Preserve raw intake, run identity, stage progress, and provenance. |
| `atomize` | Turn explicit source content into source-grounded atomic candidates without resolving unsupported ambiguity. |
| `meld` | Decide how prepared inputs combine with a target under an explicit authority contract. |
| `reconcile` | Handle ambiguity, conflict, or missing scope that blocks a meld decision. |
| `ground` / grounding engine | Persist approved Goal, Rules, Cases, and decisions; the current natural-language turn cycle remains ephemeral. |

The complete recurring-intake flow is:

```text
raw source
→ atomize incoming content
→ compare incoming candidates with the target frame
→ reconcile only the unexplained cases
→ produce an exact meld proposal
→ obtain explicit acceptance
→ materialize the accepted target change
```

`reconcile` is therefore a substage of meld, not a synonym for the complete
operation. Grounding is the interaction protocol used when reconciliation or
another consequential judgment needs user participation.

The current legacy `integrate` operation already approximates the
`DUPLICATE / UPDATE / NOVEL` branch of a directional meld. It assumes its
input is already one suitable Memory and lacks the full atomize, ambiguity,
conflict, grounding, and provenance contracts. It is evidence for the useful
relation split, not the final meld implementation.

## Source roles and authority

Every meld input must have a visible role. Content alone must not determine
authority.

| Role | Meaning |
| --- | --- |
| `CLARIFICATION` | User-supplied context for one selected issue. It may resolve or revise demonstrated local consequences but is not automatically a global rule. |
| `INCOMING` | New evidence or prepared candidate content entering a baseline Context. |
| `BASELINE` | Existing knowledge preserved unless an accepted incoming claim explicitly extends or corrects it. |
| `PEER` | A source with equal authority to the other peer inputs; no default winner is allowed. |

A clarification that appears reusable must trigger a scope question:

```text
Does this apply only to the selected case, or should it become a Working Rule
for later cases?
```

The answer determines whether the system records a case-local judgment, a
reusable rule proposal, or both. It must not generalize merely because several
Memories contain similar words.

## Relation and outcome are different

A meld first records a semantic relation, then proposes an action. Keeping the
two fields separate makes it possible to explain why no new Memory appeared.

### Candidate relations

The authority adapters may use different relation vocabularies. Symmetric v1
uses:

| Relation | Meaning |
| --- | --- |
| `EQUIVALENT` | The peers express the same operational claim under the same relevant scope. |
| `COMPATIBLE` | Both claims can remain without adding a missing scope distinction. |
| `SCOPED` | The difference is explained by an explicit condition that must be retained. |
| `CONFLICT` | Ordinary scope-aligned readings cannot yet be jointly maintained. |
| `DISTINCT` | One peer contributes an independently useful claim. |
| `UNCLEAR` | Referent, qualifier scope, or evidence is insufficient for safe placement. |

Future directional Context melding may additionally need `SAME`, `EXTENDS`,
and `CORRECTS`. Those labels must not be imposed on equal peers because they
would manufacture an authority direction.

### Proposed outcomes

Every accepted symmetric v1 result is physically an `ADD` to the empty target,
but its semantic disposition remains explicit:

| Disposition | Meaning |
| --- | --- |
| `COALESCE` | One result represents equivalent support from multiple sources. |
| `PRESERVE` | A source-supported distinction remains independently visible. |
| `SYNTHESIZE` | One standalone result combines compatible or explicitly scoped details. |
| `USER_ADD` | The user's turn contributes a new standalone result; it must cite that user turn and is not attributed to either peer. |

`DEFER` is a session decision rather than a result Memory. It retains the
analysis without changing the target. A future public Context-directional
adapter will additionally need exact `EDIT` proposals, but a `CORRECTS`
relation will never authorize an edit by itself.

## Shared conversational frame

Both authority modes should expose the same conceptual frame even when
their terminal layouts differ:

```text
SOURCES
  exact inputs, roles, digests, and source provenance

ACTIVE UNDERSTANDING
  currently effective user-supported propositions

RELATIONS
  mode-appropriate semantic relation groups

CURRENT
  what the current contract can and cannot decide

THEN
  concrete consequences for the selected and affected Memories

FOLLOW-UPS
  REQUIRED or HELPFUL questions, each naming the blocked judgment

PROPOSED CHANGE SET
  exact additions, edits, target coalescence, or preserved differences

DECISION
  confirm, extend, correct, retract, accept, defer, or keep review-only
```

A follow-up is consequential only when it states which relation, target
outcome, or downstream proposal cannot be settled without the answer. A bare
request for “more context” is insufficient.

One semantic provider call may analyze a complete bounded turn. Rendering,
resuming, and accepting an already exact proposal must be provider-free.

## Overview attention budget

The current Meld artifact has one top-level semantic overview. It should be
one short English natural-language report paragraph, normally roughly 40-50
words at most. This is the same ballpark attention budget used by the shared
result workbench: the first explanation should be short enough to read in full
before the user enters the relation, issue, and proposal detail.

The target is deliberately soft. It is not a parser limit and must never
truncate a material exception, unresolved condition, or user-supported
distinction. Relations, issues, proposed Memories, source evidence, and
grounding dialogue are complete records and do not inherit the overview's word
budget. If Meld later adopts the full three-section result workbench, each
standard section receives the shared 40-50-word target while the complete
first-frame report remains near the shared 120-150-word envelope.

## Interactive workbench

Task 2 should not force the user to decide every cross-Context relationship
before seeing the whole analysis, nor should it hide all decisions behind one
bulk approval. Meld should reuse the interaction grammar already established
by the atomize workbench:

```text
overview and pending-issue list
→ select an issue
→ inspect exact source Memory or Memories
→ inspect why the distinction matters and what it affects
→ choose a proposed handling or enter a comment
→ reanalyze the complete bounded frame
→ review the resulting edits, additions, preserved distinctions, and questions
```

The initial one-shot analysis produces the complete relation ledger and a list
of the unresolved or consequential decisions. The user may then work in either
of two ways:

- **Issue-by-issue.** Move through the list, open one issue, inspect both
  sources and rationale, choose a proposed resolution, or refine, comment on,
  or enter a different reading. Returning to the list must preserve position
  and prior decisions.
- **Whole-set guidance.** Enter one instruction that applies to the remaining
  set, preserve all remaining distinctions, or defer all remaining issues for
  this run. The model reanalyzes the bounded frame once and shows the proposed
  consequences before anything is accepted.

“Ignore all” must mean **defer the remaining issues in this meld session**. It
must not delete sources, silently mark conflicts as resolved, or make an
incomplete proposal appear complete. “Keep all” must mean preserve the source
claims as explicitly scoped or unresolved alternatives with provenance; it
must not concatenate them into an apparently consistent rule. A whole-set
comment is semantic evidence for a new analysis turn, not permission to apply
all resulting edits.

An optional bulk acceptance may be offered only for proposals that are already
exact, non-conflicting, and free of required questions. Its review screen must
still enumerate what will be added, edited, linked, coalesced, preserved, or
deferred. Required issues cannot be bypassed by an accept-all action.

Task 2 provides the strongest initial demonstration. A first screen may contain
roughly a dozen policy relationships. The user can open the participant
compensation issue, inspect the two advisor Memories and their rationales, and
comment that the hourly rate, travel-time condition, and all supported payment
methods should be retained. The next analysis may resolve that issue and any
other issue governed by the same explanation, while identifying any remaining
scope question. The user does not have to repeat the explanation for every
affected Memory.

The workbench should therefore share atomize's interaction grammar: list,
detail, free-form comment, impact, resume, and explicit acceptance. It should
not reuse atomize-specific issue types, controllers, or storage by pretending
that two peer Contexts are one atomization problem. Neutral sanitization and
frame composition sit below mode-specific adapters and persisted session
schemas; additional controller components should be extracted only after two
operations demonstrate the same state semantics.

## Provider-call strategy: bounded one-shot analysis

The first implementation uses **one aggregate semantic call per bounded
analysis or conversational reply**, not one call for every possible
Memory pair. It does not use one opaque call for the entire
analysis–conversation–application lifecycle.

The boundary is:

```text
deterministically collect and bind a bounded frame
→ call the provider once for that analysis turn
→ locally validate exhaustive source coverage and strict structured output
→ save a non-applying assessment and exact provisional proposal
→ render or resume without another provider call
→ call once again only when the user contributes a new semantic turn
→ accept an already exact proposal without a provider call
```

The representative adapters use this rule differently:

| Adapter | Initial bounded one-shot | Later calls |
| --- | --- | --- |
| Atomize directional (`ISSUE`) | One selected issue, user clarification, current local frame, and known affected findings | One call for each corrective, extending, confirming, or retracting user turn |
| Context directional (future) | Every incoming candidate admitted by the bounded run plus the complete bounded baseline frame | Only unresolved conversational turns; resume and apply remain provider-free |
| Context symmetric | Two bounded peer Context frames and their authority contract, returning a relation ledger and unresolved issues | One call per user resolution turn; final materialization remains provider-free |

This strategy was selected because relations are Context-dependent. Independent
pair calls can produce mutually inconsistent decisions, miss that one
clarification applies to several candidates, and multiply prompt and latency
costs. A complete bounded call lets the model compare the same local frame,
apply one rubric, and propose cross-item consequences together. It also matches
the prototype observation that one strong aggregate judgment often gives a
more coherent result than many isolated small judgments.

One-shot does not mean unconstrained:

- Every source Memory or incoming candidate receives a call-local opaque ID.
- The provider returns exactly one primary disposition or unresolved status
  for every source candidate covered by the mode; it does not enumerate every
  possible pair.
- Relation groups and affected-item links use only known aliases.
- Local parsing rejects missing, duplicate, unknown, over-limit, or
  structurally incompatible results.
- Exact and surface-equivalent matches may be derived mechanically before the
  provider call, but they remain visible in the relation ledger.
- The provider cannot create persistent identities, set approval, choose
  hidden source authority, or apply a change.
- Required questions stop the proposal from becoming acceptable.
- Input and target digests are checked before the call, after the call, and
  immediately before any accepted mutation.

The initial bounded prototype rejects an input that exceeds its complete
frame limit rather than truncating it. Retrieval, sharding, hierarchical
relation summaries, and cross-shard regression are later scale mechanisms;
they must not be smuggled into the first contract as lossy top-k evidence.

An aggregate provider response is still a proposal, not an independent proof
that the meld preserved every fact or chose the correct reading. Golden
scenarios, local schema and coverage validation, user review, and later
independent semantic regression remain separate trust layers.

## Provenance and mutation invariants

1. Every input Context, Memory, issue, rule, and raw source used by a meld is
   bound by stable local identity and digest.
2. Provider calls use call-local opaque aliases. Provider-generated UIDs,
   paths, commands, approval states, and target authority are rejected.
3. New or replacement content must cite source Memory evidence or an explicit
   user turn. A `USER_ADD` result cites that turn and must not claim false peer
   support. Existing Context may resolve a referent or supply a declared frame,
   but it cannot become hidden evidence for an invented incoming fact.
4. A directional meld may edit only the explicitly authorized target Context.
   A symmetric meld never mutates either peer source.
5. No source Memory is silently removed. Duplicate handling either links
   provenance to an existing representation or coalesces only in a new target.
6. Required follow-ups block acceptance. Helpful follow-ups remain visible but
   do not automatically block when the operation contract permits proceeding.
7. The complete exact proposal is accepted or retained as review-only. Partial
   application is a later feature and requires a new validated change set.
8. Acceptance rechecks every bound digest immediately before mutation.
   Symmetric version 1 holds the two source locks and target lock in stable
   order across the final source recheck and target checkpoint/write.
9. Each accepted single-target meld, including symmetric version 1, creates one
   operation checkpoint in its authorized target. A future operation that
   mutates several targets will require a recoverable linked boundary rather
   than pretending several saves are atomic.
10. Query-only source content remains opaque. A meld may use only the public
    name and the authorized query interface, never the raw hidden store.
11. The checkpoint records input roles, relations, accepted outcomes, exact
    source-to-result links, user-supported understanding, proposal digest, and
    operation identity for `trace` and `rationale`. It retains the bounded
    source Memory snapshots and binds visible turn fields into the accepted
    change-set digest so later trace output can reconstruct the actual claims
    even if a source Context changes.
12. If the target checkpoint succeeds but the session receipt write is
    interrupted, a later `--accept` verifies the exact target shape and
    checkpoint before recording the missing receipt. An `APPLIED` flag alone
    is never treated as proof that the current target still matches.

## The three initial golden scenarios

### 1. Issue-scoped directional: physical NFC clarification

```text
Issue:
  Student guidance permits a physical card or app.

Clarification:
  The Main Building exceptionally accepts only a physical NFC card.

Expected progression:
  understand physical-card-only
  → propose an edit to student guidance
  → ask whether “same NFC” extends to the staff-only entrance
  → accept exact student and staff edits in one checkpoint
```

This scenario tests correction, downstream effect discovery, a consequential
scope question, multi-turn grounding, and explicit permission.

### 2. Directional: parking access correction

```text
Baseline:
  The underground-parking stairwell is closed.

Incoming:
  The parking stairwell remains open; only the vehicle entrance and exit are
  closed.

Expected progression:
  classify CORRECTS
  → identify the exact baseline target
  → inspect affected route or access Memories
  → propose the full replacement and any required downstream changes
  → preserve unrelated baseline knowledge
```

This scenario tests baseline authority, explicit correction, targeted editing,
and the difference between vehicle and pedestrian access.

### 3. Symmetric: co-advisor compensation policies

```text
Peer A:
  Budget CAD 20–30 per hour in cash, including participation and travel time.

Peer B:
  After the study, compensate participants by e-transfer or an
  equivalent-value gift card.

Supporting context:
  The payment method need not be finalized at the proposal stage.

Expected progression:
  preserve the supported rate and travel-time scope
  → retain cash, e-transfer, and gift-card options
  → avoid selecting one advisor as the default winner
  → create a traceable result supported by both peer Contexts
```

This scenario tests equal authority, compatible combination, source-specific
scope, and result creation without source mutation.

## Command contracts

```text
# Implemented issue-scoped directional adapter remains under atomize
mem atomize --evaluate ISSUE --comment TEXT
mem atomize --reply TEXT
mem atomize --accept-grounding

# Implemented Context-to-Context symmetric meld
mem init RESULT_CONTEXT
mem meld PEER_A PEER_B
mem meld PEER_A PEER_B --issue N --choice N --comment TEXT
mem meld PEER_A PEER_B --comment WHOLE_SET_GUIDANCE
mem meld PEER_A PEER_B --preserve-all
mem meld PEER_A PEER_B --defer-all
mem meld PEER_A PEER_B --expand ISSUE
mem meld PEER_A PEER_B --restart
mem meld PEER_A PEER_B --accept

# Future directional meld
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT
```

The plain symmetric command opens the arrow-key workbench in a terminal and
prints a complete snapshot outside a TTY. Repeating it resumes without a
provider call. An issue choice/comment, an unscoped `--comment`, and
`--preserve-all` each cause one new aggregate semantic call. `--expand`,
`--defer-all`, resume, and `--accept` are provider-free.

`--revision {confirm|extend|correct|retract}` records how a semantic comment
relates to earlier dialogue; corrections and retractions identify the affected
prior turn with `--revises-turn UID`. Because symmetric sources have equal
authority, later commands may supply the two source names in either order; the
saved frame order remains stable internally. `--defer-all` closes the current
session as review-only. An explicit `--restart` replaces that saved analysis
only after the current target is revalidated as empty; a failed replacement
analysis leaves the previous session intact.

An eventual `mem import --paste` may orchestrate raw intake, atomization, and a
directional meld. Import owns the run manifest and resumability; it must call
the same independently testable atomize and meld contracts rather than
embedding a second semantic implementation.

## Implementation sequence

1. **Completed: stabilize the atomize adapter.** The existing physical-NFC
   flow retains its schema and command while reusing common meld turn-lineage
   validation, exposing a lossless directional/issue adapter view, and
   declaring that adapter contract in each semantic-turn payload.
2. **Completed: implement bounded symmetric Context melding.** Two direct-
   Memory PEER Contexts produce one complete primary relation ledger, saved
   issues, and exact non-applying result proposals.
3. **Completed: add shared issue and whole-set interaction.** The terminal
   shell supports issue selection, reading plus free-form refinement,
   whole-set comments, preserve-all, defer-all, provider-free resume, and
   provider-free acceptance.
4. **Completed: apply with recorded evidence.** Source and target digests are
   rechecked, results enter an empty target in one checkpoint, source Contexts
   remain unchanged, retry can recover from the checkpoint, and trace reports
   recorded `MELDED` evidence.
5. **Next: implement Context-to-Context directional meld.** Reuse the batch
   frame, turn, relation-group, proposal, session-CAS, and acceptance machinery
   while introducing explicit `INCOMING` and `BASELINE` authority and exact
   `EDIT` validation.
6. **Completed: share the state-free message composer with Ground.** Ground
   and meld now use the same bordered multiline editor with an independently
   named buffer and the same focused-input convention (`Enter` sends;
   `Ctrl-J` or `Alt-Enter` inserts a newline).
   Focus, issue navigation, semantic actions, provider calls, and persistence
   remain adapter-owned. The atomize schema remains independent; future
   controller views must not pretend its issue artifact is a
   Context-to-Context relation ledger.
7. **Later: connect import.** Let a resumable import run invoke atomize and
   directional meld while preserving each stage's preview, approval, and
   provenance.

Symmetric v1 deliberately excludes raw input atomization, non-empty targets,
automatic reference traversal, query-only sources, source deletion, source
mutation, unbounded retrieval, and hidden truncation. Those behaviors must not
be inferred from the word “meld.”

## Shared terminal chrome

Meld now uses the same neutral terminal sanitization and slot-based vertical
frame composition as Ground and review. It also uses Ground's extracted
state-free framed message composer. Meld may relabel the trusted frame as a
whole-set comment while keeping the same editor instance. Inside that editor,
`Enter` submits and `Ctrl-J` or `Alt-Enter` inserts a newline; `Ctrl-S` remains
a compatibility submission alias. Its issue navigation, reading choices,
provider-owned outer loop, saved relation ledger, and acceptance behavior
remain meld-specific. Sharing the component therefore does not turn Ground's
Goal–Rules–Cases controller into meld state. In particular, meld's `A` action
does not become a Ground-style exact-argv approval unless a future adapter
explicitly constructs and displays a receipt whose target, session, and
change-set preconditions are enforced at the save boundary. See
[`shared-tui-command-review-design-rationale.md`](shared-tui-command-review-design-rationale.md).
