# Meld modes and shared contract

## Status

This note distills the shared semantic-meld contract and its two authority
modes. The canonical user-facing commands and terminology are maintained in
[`mem-meld-usage.md`](mem-meld-usage.md). This rationale explains why those
entry points differ; it is not a second command manual.

Two public Context-to-Context paths now exist as bounded research prototypes:

```text
# Symmetric: two peers produce the current empty result
mem init RESULT
mem meld LEFT_PEER RIGHT_PEER

# Symmetric: create the result without switching Contexts
mem meld LEFT_PEER RIGHT_PEER --to NEW_RESULT

# Directional: current or explicit incoming enters an existing baseline
mem meld --into BASELINE
mem meld INCOMING --into BASELINE

# Directional convenience: explicit incoming enters the current baseline
mem meld --from INCOMING
```

Both save a resumable relation ledger and workbench, accept issue-scoped or
whole-set comments, support preserve-all and provider-free defer, and apply an
exact ready proposal only after explicit acceptance through the TUI's `A`
action or the `--accept` option. Symmetric Meld imports its initial ordered
ledger and candidate issues provider-free from an exact fresh
`ComparisonAnalysis`; the first user grounding turn is its first semantic
Meld call. Directional Meld performs its own aggregate analysis because
`INCOMING → BASELINE` has a different authority contract. Symmetric meld adds
a complete result to an empty third Context. Directional meld leaves the
incoming Context read-only and applies only exact material `EDIT` and `ADD`
changes to its baseline; a fully represented input may instead produce an
accepted zero-change checkpoint.

Saved Context Melds can also be entered through `mem meld` or
`mem meld --sessions` without restating their Context operands. This is a
catalog and open operation, not a global `switch`: choosing an item does not
install an active Meld that could leak across terminals or agents. The
catalog's stable key is the persisted target Context UID, while its group is
the persisted target Context name. This uses Meld's existing target-scoped
identity instead of introducing an ungrounded project field.

The first ordering is honestly named `RECENTLY MODIFIED` because the current
Meld schema has no durable `created_at` or `updated_at` field. It uses the JSON
file mtime only as display metadata. The catalog also freezes the selected
session UID and canonical record digest. After Enter, the command reloads the
record by target UID, rejects deletion or replacement under that key, and
rechecks every persisted source/target Context UID and digest before opening
the workbench. The displayed explicit argv is useful orientation but is never
blindly executed: doing so could fall through the ordinary create/restart
grammar or reinterpret a relative/current Context. Consequently selection and
cancellation themselves remain read-only; later workbench actions keep their
existing CAS and explicit-acceptance boundaries.

A saved Compare workbench now provides the equivalent guided entry. Pressing
`M` opens a result-target picker instead of merely printing a placeholder
command. It offers only local, empty, session-free Contexts distinct from both
sources, plus one exact-name editor for a new Context. Selecting an existing
target or validating a new name is still process-local. Meld then reloads the
exact ordered Compare UID, source UIDs and digests, grant combination and
derived-transfer policy, and target state before it creates the target-bound
session. A new target and its initial Meld session are written through the
same atomic store boundary; the picker itself never creates a Context.

The earlier local conversational change flow inside atomize grounding is also
retained:

```text
mem atomize --context CONTEXT --evaluate ISSUE --comment TEXT
→ mem atomize --context CONTEXT --reply TEXT
→ mem atomize --context CONTEXT --accept-grounding
```

That flow remains under its existing atomize command and strict schema. It now
reuses the common meld turn-lineage contract and has a lossless
issue-scoped directional adapter view; it is not silently renamed or migrated.
The public Context-wide directional command reuses the common session,
relation, turn, proposal, checkpoint, and provenance machinery without taking
ownership of atomize's issue-specific artifact.

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
| retired legacy `integrate` | Distinguished duplicate, update, and novel input for one assumed Memory. | It assumed the input was already suitable, lacked full ambiguity/conflict grounding, and did not supply the shared provenance or authority contract. |
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
- **Atomize grounding** projects the selected source-grounded candidate as an
  ephemeral `INCOMING` Context frame, binds the containing Context as the
  `BASELINE`, and uses selected readings and user explanations as turn
  evidence for deciding how the proposal and Context should change.

The second operation has the complete meld shape:

```text
select one ambiguity
→ project its source-grounded candidate as an ephemeral incoming Context frame
→ attach the selected reading and free-form clarification as turn evidence
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
therefore clarification evidence attached to the meld rather than a third
Context. The selected issue projection is the incoming frame, and the current
Context is its directional baseline. This is an **issue-scoped directional
meld embedded in the atomize workflow**. The engine remains batch-shaped: its
bounded frame can contain the selected issue, a pair-shaped conflict, and
several downstream issues. “Atomic” describes the initially selected scope,
not another execution mode.

This interpretation does not mean that `mem atomize` should be renamed.
Atomize remains the user-facing operation because it owns source decomposition,
its analysis artifact, and the reason the ambiguity was surfaced. Meld is the
shared semantic change protocol used once an interpretation must be combined
with that artifact. Keeping the entry point while extracting the common
protocol preserves a coherent task narrative and avoids two commands claiming
the same saved atomize session.

### A unit Memory is an ephemeral Context frame

The common meld boundary accepts Context-shaped frames, even when the selected
input is only one atomized Memory. For a unary issue, atomize grounding
therefore projects that Memory as a one-Memory, `EPHEMERAL` `INCOMING` frame
and projects its containing Context as a `BOUND` `BASELINE` frame. The
incoming Memory keeps its original source identity, content digest, and source
position. Its appearance in both the focus projection and baseline is one
piece of evidence viewed at two scopes, not independent corroboration.

“Temporary Context” is a semantic and type-level description here, not a
request to create a normal mutable `Context`. The implementation uses an
immutable frame view with a deterministic session-local frame UID and digest.
It has no durable Context UID or locator, is never passed to `MemoryStore`, is
never current or listed by `mem ls`, and creates no `context.json` or
checkpoint. It is reconstructed from the digest-bound atomize session on each
turn. Only explicit acceptance may checkpoint the exact `EDIT` / `ADD`
consequences in the bound baseline Context.

The baseline projection reads direct owned Memories only. Reference and
query-only slots remain part of the complete Context digest and source
positions, but their targets are never opened or copied into the frame. This
preserves the atomize provider's existing privacy and compare-and-swap
boundary.

The issue's original arity is preserved. A unary candidate produces a
one-Memory frame; a pair-shaped conflict produces one issue-bounded incoming
frame containing both source Memories rather than flattening them into a
synthetic proposition. Composite split children do not yet have durable
Memory identities, so this adapter retains their source Memory and existing
proposed-child metadata instead of pretending that proposed children are
already stored Memories.

This internal normalization does not add `mem meld --atomic`, expose a
Memory-UID command, or create a second public workflow. `mem atomize
--evaluate` remains the owner of analysis identity, dialogue persistence,
approval, and source-local provenance.

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

The bare-New session TTY makes this distinction visible before either session
is prepared. A shared horizontal choice selects `A → B` directional
or `A + B → C` symmetric mode, and a role-based setup shell embeds one
independent Context namespace tree per active operand. Switching away from
symmetric mode may retain a process-local C draft for reversible navigation,
but C is absent from the directional receipt and cannot affect its provider or
target identity. See `session-endpoint-setup-design-rationale.md` for the
presentation, receipt, and validation boundaries.

Symmetric `A + B → C` is the initial and leftmost mode. Directional `A → B`
remains the explicit option to its right in the same horizontal selector.

The A/B source trees use the shared readable public namespace rather than only
the active Profile's ordinary Context records. READ-granted public names are
therefore visible at their public hierarchy position and carry an explicit
`GRANTED · READ SOURCE` annotation. The Grant attachment is not rendered as a
semantic parent. Query-only routes are absent because Meld has no query-source
contract and must not substitute hidden query output for a reviewed source
frame. C remains a local empty or newly created Context. Directional A and B
may each be local or READ-granted. The session freezes each granted endpoint's
exact Profile, attachment, Grant revision, resource, public name, and authority
mapping; a public name by itself is not durable authority.

The same setup shell also owns optional, default-off descendant controls, but
each Meld authority mode enables only scopes it can materialize safely.
Symmetric Meld enables A and B independently because it writes a separate C;
it consumes only a saved ordered Compare whose two scope flags match exactly.
Directional Meld enables descendants for incoming A only. Its B is the
authoritative mutation target, so widening B today could flatten child-owned
Memories into the root baseline. B therefore remains direct and the CLI
rejects `--right-descendants` in directional mode until owner-aware target
materialization exists.

| Mode | Inputs | Authority contract | Target | Representative case | Current status |
| --- | --- | --- | --- | --- | --- |
| **Directional** | Prepared incoming evidence, optionally including its readable lexical descendants, plus one direct existing baseline frame | The baseline is preserved except where accepted incoming evidence explicitly extends or corrects it | The baseline's next state | A physical-card clarification changes student guidance; a parking correction updates an existing closure Memory | Implemented both as atomize's ephemeral issue projection and as public Context-to-Context `mem meld [INCOMING] --into BASELINE`; `mem meld --from INCOMING` is equivalent when the baseline is current |
| **Symmetric** | Two independent Context frames, each optionally including its readable lexical descendants, treated as peers | Neither source wins by default; source-specific scope and unresolved differences remain visible | A distinct new result Context | Two co-advisors' proposal-writing policies | Implemented through an exact saved ordered Compare basis |

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

Task 2 begins with one saved batch Compare analysis. Starting symmetric Meld
copies that exact ordered analysis and its identities into the target-bound
session without another provider call. Opening the compensation issue does not
launch a different atomic engine; it creates an `ISSUE`-scoped turn within the
saved batch. The result returns to the complete relation ledger, where it may
resolve or alter other pending issues. A whole-set comment or preserve-all
action uses `ALL` or `REMAINING` over the same session.

This makes meld compositional rather than merely UI-reusable. The user changes
the turn's **scope**, not the semantic machinery, when moving between overview
and detail.

### Context-to-Context v1 boundary

Public `mem meld` accepts two bounded direct-Memory Context frames under one of
two explicit authority contracts. For Task 2, both sources have the `PEER`
role and the active empty Context is the result target:

```text
mem init jingyue/proposal-writing-policy
mem meld ian/proposal-writing-policy damien/proposal-writing-policy
```

For recurring intake, the first frame is read-only `INCOMING`, the second is
the authoritative `BASELINE`, and that same baseline is the mutation target:

```text
# current Context supplies INCOMING
mem meld --into campus/wiki

# or name both roles explicitly
mem meld construction-updates --into campus/wiki
```

The baseline may already contain Memories. Its exact bound snapshot is
preserved unless an accepted proposal contains a material `EDIT` or `ADD`.
The incoming Context is never mutated.

`--from INCOMING` is only a viewpoint-sensitive convenience spelling when the
current Context is the baseline. It resolves `INCOMING` against the one current
Context snapshot captured at command start, then immediately uses the same
ordered frame pair, target-bound storage key, and provider contract as
`mem meld INCOMING --into BASELINE`. Durable guidance and receipts therefore
remain location-independent. Combining `--from` with `--into` or positional
Contexts is rejected instead of inventing a third authority contract.

This is a useful product boundary, but `Context` should not be the lowest-level
semantic type in the implementation. The core should consume bound
**MeldFrames**: ordered sets of direct Memory records with source identity,
role, digest, and declared authority. The public command deterministically
converts each named Context into one frame. The atomize adapter can construct a
smaller frame from one issue and its demonstrated local dependencies without
materializing a persistent Context record.

That separation permits genuine generalization:

- Context + Context symmetric meld uses two `PEER` frames and a distinct new
  target.
- Context + Context directional meld uses `INCOMING` and `BASELINE` frames and
  may propose a next state for the baseline.
- Atomize grounding uses one ephemeral issue-bounded `INCOMING` frame and one
  bound containing-Context `BASELINE` frame through the same turn and proposal
  contract. `CLARIFICATION` is dialogue evidence attached to the turn, not a
  third frame.

The v1 commands need not expose every adapter. Supporting both Context-wide
authority modes does not require pretending that the issue-scoped atomize
adapter has the same CLI syntax or persistence artifact.

Initial Context-to-Context analysis is intentionally bounded:

- read direct owned Memories only;
- keep both peer sources read-only in symmetric mode and keep `INCOMING`
  read-only in directional mode;
- require the active target to differ from both sources and be empty for the
  first symmetric implementation;
- require directional `INCOMING` and `BASELINE` to be distinct while binding
  the baseline as both source frame and target;
- bind source and target Context UIDs, names, complete direct-record digests,
  and Memory order;
- permit directional `EDIT` and `ADD`, but not `DELETE` or a no-op `EDIT`;
- reject an over-limit source rather than silently truncate it;
- never dereference query-only Contexts or use hidden query content;
- reject Memory references, query-only references, and embedded Contexts
  explicitly in version 1 rather than silently omitting them or treating their
  targets as direct evidence.

### Why directional uses `--into`, not `--to`

The option names reserve different semantic shapes:

```text
mem meld [INCOMING] --into BASELINE
mem meld LEFT_PEER RIGHT_PEER --to RESULT_CONTEXT  # future
```

`--into` says that one existing Context is both the authoritative baseline and
the only possible mutation target. It therefore communicates an asymmetric
authority relation, not merely a destination path. When `INCOMING` is omitted,
the current Context supplies that role; spelling it explicitly does not change
the contract. `--from` reverses only which role is omitted at the CLI boundary:
the current Context supplies `BASELINE`, and the operation is normalized back
to the same `INCOMING --into BASELINE` route.

`--to` is deliberately left unused for now. Its future symmetric meaning is a
distinct result Context selected explicitly rather than through the current
Context. Neither peer would become authoritative or mutable. Making `--to` an
alias for `--into` would collapse the difference between “revise this
baseline” and “write a peer result there,” leaving no unambiguous syntax for
the latter.

Context operands follow the shared existing-Context locator contract. Bare
names are canonical global names. Only `.`, `..`, `./...`, and `../...` opt
into lexical lookup relative to the slash-delimited current Context name; they
do not inspect shell directories or embedding relations. The command captures
the current name once and resolves all relative operands against that same
snapshot before it binds identities, checks equality, or opens a session.
The shared safety and compatibility rationale is recorded in
[`context-locator-design-rationale.md`](context-locator-design-rationale.md).

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
| `ground` / grounding engine | Persist approved Goal, Rules, Ground Memories, and decisions; the current natural-language turn cycle remains ephemeral. |

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

The retired legacy Integrate pipeline approximated the
`DUPLICATE / UPDATE / NOVEL` branch of a directional meld. It assumed its
input was already one suitable Memory and lacked the full atomize, ambiguity,
conflict, grounding, and provenance contracts. Its frozen evaluation path is
evidence for the useful relation split, not a public alternative to Meld.

## Source roles and authority

Every meld input must have a visible role. Content alone must not determine
authority.

| Role | Meaning |
| --- | --- |
| `CLARIFICATION` | User-supplied turn evidence for one selected issue. In atomize grounding it is attached to the directional meld rather than modeled as a Context frame, and is not automatically a global rule. |
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

Directional Context v1 reuses this neutral relation vocabulary while the frame
roles and exact proposal operation carry the authority direction. For example,
an `EQUIVALENT` incoming–baseline relation can justify a resolved zero-change
result, while a materially different supported relation can justify an
`EDIT`. Future evaluation may show that more specific `SAME`, `EXTENDS`, or
`CORRECTS` labels improve explanation, but those labels are not required for
the implemented mutation contract and must never be imposed on equal peers.

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
analysis without changing the target.

Directional Context meld uses the same semantic dispositions but adds an
orthogonal physical operation:

| Operation | Directional contract |
| --- | --- |
| `EDIT` | Materially replace one baseline Memory's content while preserving its UID and position. It names that Memory in the dedicated target field and separately cites incoming evidence. |
| `ADD` | Append a new Memory with a fresh UID, supported by incoming evidence or an explicit user turn. |

There is no directional `DELETE`. Unchanged baseline Memories are absent from
the change list rather than represented as no-op edits. A complete
`EQUIVALENT` analysis may therefore be ready with zero operations. Explicit
acceptance still records one checkpoint and receipt for that semantic
decision, while leaving the baseline's Memory post-image unchanged. A relation
classification alone never authorizes an edit; the exact target UID, content,
source evidence, current baseline digest, and accepted change-set digest must
all validate locally.

The provider-facing JSON Schema deliberately stays within Codex's supported
structured-output subset. In particular, it does not use `uniqueItems`, which
the provider rejects. Duplicate opaque aliases are still rejected by the local
parser. For `EDIT`, the validated baseline target field is authoritative
provenance evidence; the parser folds that target into the saved source-member
set, so the model need not repeat the same alias in both the target and source
arrays. This removes redundant output syntax without relaxing the requirement
for at least one incoming source or the local baseline-role check.

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

The live Meld surface uses the same high-level reading grammar as Compare: a
large `VIEWER` above a compact `ITEMS` navigator, with identical focused-frame
styling. `REPORT` is always the first item and initial selection, so a person
sees the complete understanding, issue summary, and proposed results before
conflict 1. The complete report contains one semantic section for every
conflict and ends with the whole-set strategies. `Tab` moves focus between
`ITEMS` and `VIEWER`; Viewer arrows move section by section with the same
hidden-cursor, minimum-boundary scrolling as Compare. Entering a conflict from
Items replaces the Viewer with that issue's full question, options, and
source-linked blocks. Moving to a conflict or `RESOLVE ALL` section in the
report also selects the corresponding lower row, so the two panes never imply
different current subjects. Merely moving the lower cursor does not open a
different report; `Enter` is the explicit drill-down boundary.
Entering the `REPORT` row also transfers keyboard focus into Viewer, making
`Enter` a direct entry path while retaining `Tab` as the reversible pane
switch.

The opened detail does not repeat the overall report. Its Viewer moves through
only the selected conflict's question, options, evidence, relations, and
proposed result. Symmetric evidence omits the meaningless `PEER` role,
recursive Memory locations appear once, and durable identifiers are shortened
for orientation. Directional roles remain visible because their asymmetry is
part of the operation's meaning.

Each detail section is a separate fixed-width card with a blank line between
cards. Options are nested cards with distinct focused, selected, and
other-direction colors. Evidence and relation bodies receive an additional
content indent inside their cards, so source boundaries remain readable even
when terminal wrapping is dense. The fixed card width is intentionally smaller
than the Viewer at the minimum supported layout rather than tracking every
terminal resize and destabilizing reading position.

Every conflict with bounded choices also exposes one local `Other direction`
row. `Enter` keeps its existing select/clear behavior for a supplied option,
and `C` stages that selection with an optional issue-scoped explanation.
Choosing `Other direction` opens a required free-form resolution directly. It
submits no fabricated option UID, so provider and audit state retain the
difference between accepting a supplied answer and proposing another one.

In the two-pane Meld shell these responses are now staged per conflict rather
than sent to the provider immediately. `Enter` visibly selects a supplied
answer and a second `Enter` clears it; an Other-direction submission returns to
the same workbench as a staged response. The Report remains the evidence-rich
review surface: its conflict cards show staged choices and its final card
shows the current whole-set policy. Once required review is complete, Report
and To Do expose `REVIEW AND APPLY`. Enter opens a compact final confirmation
that summarizes responses and offers either `INCORPORATE RESPONSES` or
`APPLY`; Escape/Backspace returns without acting. Meld deliberately retains a
separate incorporation turn because a provider-created target must be
inspected before exact `ACCEPT`. Thus application remains gated by a ready
exact proposal and can no longer occur from one Enter on To Do.

The one-shot Meld item bound is 500 source Memories. The canonical Task 2
topology contains 150 Memories from each Advisor, so the former total bound of
200 allowed Compare to produce a reviewed relation ledger but made its Meld
impossible to resolve. Raising only the item-count bound admits that intended
300-Memory case without truncation; the independent 400,000-character input
bound, strict output schema, complete source coverage, and single-call contract
remain unchanged.

The aggregate Meld call has a 900-second completion allowance. The canonical
300-Memory Task 2 follow-up exceeded the previous five-minute window while
producing its complete cumulative ledger. This longer timeout is local to Meld;
it does not change other semantic commands, permit multiple hidden calls, or
relax source, response, and compare-seed validation.

A follow-up response may omit a prior relation despite the cumulative-ledger
instruction. Mem carries such a relation forward only when every member of that
prior relation is absent from every newly returned relation. Any partial member
overlap still fails closed, because locally guessing a provider-intended split
or regrouping would change provenance. Exact once-only coverage is rechecked
after this conservative carry-forward step.

## Preservation-first materialization and priority flow

Meld is a merge-like materialization, not a thematic summary. The canonical
Task 2 run demonstrated the failure mode: all 300 source Memories and all 109
relations were technically cited, yet 14 broad synthesized Memories collapsed
independently revisable guidance. Coverage alone therefore does not establish
an acceptable result count or granularity.

New symmetric sessions use schema version 3 and assign every source-derived
result to exactly one primary relation. `EQUIVALENT` yields one coalesced
result, `DISTINCT` preserves each member, and `COMPATIBLE` or `SCOPED` preserves
each source Memory unless a user-grounded decision explicitly permits a
lossless synthesis. A conflict may produce the reviewed result or results, but
cannot absorb unrelated relations. Older schema version 1 and 2 sessions remain
readable so an already reviewed or applied study artifact is not retroactively
invalidated by the stronger materialization contract.

New directional sessions use schema version 4. It preserves the same relation
and proposal model while adding optional frozen Grant bindings for INCOMING
and BASELINE. Local-only directional sessions also use version 4 with null
bindings so one current decoder covers restart and mixed local/granted routes;
legacy version 1 directional sessions remain readable and resumable.

The review queue has two priority bands. Compare's unresolved questions remain
`REQUIRED` and are shown first. Every otherwise resolved `COMPATIBLE` or
`SCOPED` relation that lacks an existing question receives a deterministic
`HELPFUL` materialization question: preserve the members separately or combine
them only when the resulting Memory remains atomic and retains every condition,
scope, audience, modality, rate, and exception. Deterministic identifiers keep
that queue stable across repeated starts from the same Compare artifact.

An earlier issue comment is reusable evidence, not an automatic wildcard. On
the next semantic turn the provider recomputes the full ledger and may apply
that rationale to later `COMPATIBLE`, `SCOPED`, or `CONFLICT` issues only when
the same stated reason materially governs them; resulting proposals cite the
originating turn. This lets one decision settle related lower-priority work
without silently broadening a local answer. The whole-set strategies then act
as a priority threshold: they may preserve or conditionally combine remaining
`HELPFUL` items, but do not decide an outstanding `REQUIRED` conflict.

The host renders an accounting block computed from identities rather than
provider-authored prose: source Memories represented, primary relations
represented, final Memory count by disposition, required/helpful issue counts,
and cross-relation result count. This exposes both omission and over-compression
before apply. It intentionally does not impose one universal final count;
equivalence, explicit synthesis, and reviewed conflicts can legitimately alter
that count while the relation-local invariants remain checkable.

For symmetric schema version 3, `--preserve-all` is provider-free after the
relation ledger exists. The host copies each non-equivalent relation member as
one independently revisable `PRESERVE` result and coalesces each `EQUIVALENT`
relation once, using deterministic result identities and the exact source text.
This operation also resolves conflict members as explicitly retained scoped
alternatives. A 300-Memory provider response proved unreliable even after the
prompt prohibited cross-relation compression: it marked all relations resolved
while omitting material results. Local materialization removes that unnecessary
generation step, while the existing target CAS, source coverage, relation
coverage, readiness review, and separate `--accept` boundary remain intact.

When both symmetric sources come from a `RETAINED` granted Compare artifact,
application validates that immutable artifact and does not try to reopen its
public aliases as ordinary local Contexts. The final write still holds target
CAS and records all source snapshots in the Meld checkpoint. Live ordinary or
grant-bound sources retain their existing revalidation path; this exception is
only for participant-owned retained evidence whose authority state is
deliberately no longer consulted.

For a symmetric Meld seeded from Compare, `REPORT` is not a second Meld-authored
summary. It re-renders the exact saved `ComparisonAnalysis` through Compare's
own compact renderer, preserving `WHAT BOTH CONTAIN`, `WHAT DIFFERS`, both
`ONLY IN` sections, and `POTENTIAL CONFLICTS` verbatim. Meld removes only the
Compare navigation footer that would tell the user to start Meld again, then
appends its current proposed target Memories and whole-set strategy section.
Directional Meld has no Compare seed and therefore keeps its authority-specific
report projection.

Before Apply, Meld also exposes the shared revision-bound Impact surface. For
symmetric Meld this Impact is the saved Compare report itself:
the equal-authority analysis is reused rather than summarized into a second
dialect. Directional Meld deliberately does not call its Impact Compare; it
shows the exact proposed baseline effects because incoming and baseline do not
have peer authority. Impact is provider-free and cannot apply the Meld.

The Resolution report names these endpoints separately from its semantic
understanding. Directional Meld shows `INCOMING` and `BASELINE / TARGET`;
symmetric Meld shows `SOURCE A`, `SOURCE B`, and `RESULT` in the common
non-focusable `CONTEXT LOCATIONS` block. Seeded Compare prose receives the
same block at the top of its first report card, so using Compare's exact report
does not hide where Meld will materialize its result.

An unapplied symmetric Meld then shows a `SAVE LOCATION` card immediately
above Apply. Editing it relocates the already-created empty Result Context and
its target-bound Meld session through the ordinary Context-rename freshness
and rollback boundary, then returns to the same review. The relocation keeps
the Result Context UID, rewrites the target name and metadata digest, and does
not rerun the provider or apply proposed Memories. A target namespace with
descendants is rejected in this inline flow rather than moving unrelated work.
Directional Meld deliberately omits the card: its target is the authoritative
existing baseline, so changing its “save location” would change the operation
rather than merely rename a new symmetric result. Review-only Meld surfaces
also omit the control.

`mem review meld` opens the same saved assessment as an adaptive Review report.
It may record the existing issue or whole-set semantic turns and reassess the
Meld, but its projected capabilities exclude Accept. Applying proposed target
Memories remains available only after leaving Review for the owning Meld flow.

Inside the Meld Viewer, each ordinary seeded report section is rendered as a
smaller bordered card. Potential conflicts instead use separated indented
paragraphs inside one outer group; repeating an inner border around every long
conflict made the dense text harder to scan. This changes only presentation:
the saved Compare prose remains the displayed body. The focused block retains
the shared blue focus treatment. When a conflict option or an
other-direction response is staged, that conflict card gains a blue selection
badge; the whole-set card similarly shows the currently selected policy. These
badges are process-local review state and do not become source evidence or
durable decisions until the normal reviewed semantic turn is submitted.

Potential conflicts are visually one group rather than an empty heading card
followed by unrelated siblings. The outer card reports the immutable Compare
count and the current unresolved count as `original → remaining`; blank lines
separate its individually focusable conflicts. After a semantic turn, a blue outcome badge
is reconstructed only from durable evidence: an option text recorded in a user
turn, an explicit Other-direction turn, or the relation-local proposal
dispositions. User-facing badges expose the actual decision rather than only
its disposition: `CHOSEN · LABEL` for one recorded option and `KEPT BOTH ·
LABEL A + LABEL B` for preserved alternatives. A direct custom resolution
shows a compact excerpt of the durable user instruction after `OTHER
DIRECTION`, while a synthesized or coalesced outcome shows compact proposed
Memory content instead of a generic `APPLIED` or `SYNTHESIZED` status. This
keeps the review surface meaningful without asking the provider to summarize
the decision a second time. An open or merely staged issue is not counted as
resolved.

Viewer position and durable decision state use separate color semantics. The
blue focused section, conflict, result, or option cursor appears only while the
Viewer pane itself owns focus; switching to Items removes that positional
emphasis so the top `MEM COMPARE` card cannot look active. Blue decision badges
and selected-option state remain visible because they report saved or staged
resolution state rather than keyboard focus.

Proposed target Memories are not one giant Viewer section. Each result is an
independently focusable, indented block containing its disposition, complete
Memory text, and reason. Up and Down therefore advance by one short result
block for every discrete tap, including rapid repeated taps. Rate acceleration
to two and then five times the terminal repeat cadence begins only after the
initial auto-repeat delay and sustained short cadence identify a held arrow;
an interrupted cadence or direction change restores single-step movement.
Every intermediate result block is separately visited and rendered rather than
being skipped. This timing and animation comes from the shared TUI
`NavigationAccelerator`, which Switch and the Trace/Rationale picker also use
for read-only Memory viewport stops; each surface continues to own the meaning
of one navigation unit.
Page Up and Page Down advance eight blocks, and End reaches the final
materialize/apply section directly. Result rows reuse the Switch tree-prefix
primitive and color the complete focused Memory and rationale, rather than
only its disposition. The final action card anchors at its bottom so its full
border and action remain visible after a hundreds-result proposal. Once a
proposal is ready, this card also omits the now-inapplicable materialization
strategies; they remain visible only while the proposal still needs to be
materialized.

Every independently focusable report card, conflict, and proposed Memory uses
a trailing viewport anchor. An anchor at the first line allowed prompt-toolkit
to stop scrolling as soon as that one line entered the bottom of the Viewer,
hiding the selected Memory body and rationale. Anchoring after the block keeps
the whole block visible whenever its rendered height fits the Viewer; blocks
larger than the physical pane remain scroll-limited by the terminal itself.

Meld application state participates in command-unit Undo and Redo. The target
Context checkpoint retains the exact session UID, change-set digest, original
application checkpoint, and result Memory identities. Under the same global
command and target locks used for Context restoration, Undo validates that
receipt and changes the matching session from `APPLIED` back to
`READY_TO_APPLY`; Redo restores the exact `APPLIED` receipt. If either side is
stale or belongs to another session, restoration fails before writing. As with
multi-Context command restoration, exception rollback covers both records;
machine-crash atomicity still requires a future transaction journal.

The same companion-artifact restoration hook covers atomize-grounding apply:
its saved dialogue returns from `APPLIED` to `READY_TO_APPLY` on Undo and Redo
restores the exact checkpoint-bound application receipt. Operations whose
"applied" view is derived from the live Context history, rather than stored as
a separate terminal flag, need no companion mutation because restoring the
Context already changes that projection.

There is no permanently visible `MESSAGE` frame. `C` on an opened conflict
opens a temporary `COMMENT ON SELECTED CONFLICT` section inside the
Viewer's existing frame. `G` and the custom whole-set route similarly open
`WHOLE-SET GUIDANCE` in that frame. This makes authoring feel like an extension
of the report being reviewed instead of an unrelated chat window.

`RESOLVE ALL` is the final item after the conflicts and the final section of
the complete report. It offers bounded
whole-set strategies: preserve every remaining distinction; choose the
broadest justified option in each conflict; choose the narrowest useful option;
choose the strongest-supported option independently per conflict; or write
custom guidance. Broad and narrow are scope policies, not permission to exceed
source support or discard compatible distinct information. Every strategy
produces either the existing preserve action or one provider-mediated
whole-set turn; none applies the target. Only the readiness-gated `A` action
or `--accept` crosses the target checkpoint boundary.

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

For symmetric Meld, the initial screen imports the complete relation ledger
and unresolved or consequential decisions from the exact saved Compare
analysis. For directional Meld, its initial one-shot analysis produces that
state directly. The user may then work in either of two ways:

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
not reuse atomize-specific issue types or storage by pretending that two peer
Contexts are one atomization problem. Meld and Atomize have now demonstrated
the same list/detail/comment grammar, so immutable projection, UID-addressed
actions, nested navigation, terminal sanitization, and composer behavior are
extracted into `ResolutionWorkbench`. Their provider schemas, durable sessions,
reanalysis, readiness, and application remain operation-specific.

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
| Context directional | Every direct incoming Memory plus the complete bounded baseline frame, returning relations and exact material `EDIT` / `ADD` changes | One call per user resolution turn; resume, defer, expand, and apply remain provider-free |
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
   Its incoming Context remains read-only; a symmetric meld never mutates
   either peer source.
5. No source Memory is silently removed. Duplicate handling either links
   provenance to an existing representation, records a directional no-change
   result, or coalesces only in a new symmetric target.
6. Required follow-ups block acceptance. Helpful follow-ups remain visible but
   do not automatically block when the operation contract permits proceeding.
7. The complete exact proposal is accepted or retained as review-only. Partial
   application is a later feature and requires a new validated change set.
8. Acceptance rechecks every bound digest immediately before mutation.
   Symmetric version 1 holds the two source locks and target lock in stable
   order across the final source recheck and target checkpoint/write.
   Directional version 1 similarly locks the read-only incoming source and
   uses target compare-and-swap for the baseline snapshot. For granted
   endpoints, the registry snapshot and exact authority records remain locked
   through the write. A granted BASELINE is updated in its authority Profile,
   not copied into the participant Profile; failure to persist the participant
   receipt rolls back the authority record and checkpoint.
   Ordinary exceptions are therefore atomic across the authority Context and
   participant session. As with granted Update, a process crash between those
   two durable stores still needs a future cross-Profile transaction journal;
   the authority checkpoint supports exact retry recovery in the meantime.
9. Each accepted single-target meld creates one operation checkpoint in its
   authorized target. This includes a resolved directional proposal with zero
   material changes: the checkpoint records the accepted semantic decision
   without inventing a no-op `EDIT`. A future operation that mutates several
   targets will require a recoverable linked boundary rather than pretending
   several saves are atomic.
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
  record the scoped incoming–baseline relation
  → identify the exact baseline target
  → inspect affected route or access Memories
  → propose a material EDIT and any required ADD changes
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

The executable recipes are centralized in
[`mem-meld-usage.md`](mem-meld-usage.md). The summary below records the design
boundary and must remain consistent with that guide and CLI help.

```text
# Implemented issue-scoped directional adapter remains under atomize
mem atomize --context CONTEXT --evaluate ISSUE --comment TEXT
mem atomize --context CONTEXT --reply TEXT
mem atomize --context CONTEXT --accept-grounding

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

# Implemented Context-to-Context directional meld
mem meld --into BASELINE_CONTEXT
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT
mem meld --from INCOMING_CONTEXT  # current Context is BASELINE_CONTEXT
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --issue N --choice N --comment TEXT
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --comment WHOLE_SET_GUIDANCE
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --preserve-all
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --defer-all
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --expand ISSUE
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --restart
mem meld INCOMING_CONTEXT --into BASELINE_CONTEXT --accept
```

The plain symmetric or directional command opens the arrow-key workbench in a
terminal and prints a complete snapshot outside a TTY. Omitting the
directional incoming operand uses the current Context; naming it explicitly
creates the same role binding. Repeating the same resolved command resumes
without a provider call. An issue choice/comment, an unscoped `--comment`, and
`--preserve-all` each cause one new aggregate semantic call. `--expand`,
`--defer-all`, resume, and `--accept` are provider-free in both modes.

`--revision {confirm|extend|correct|retract}` records how a semantic comment
relates to earlier dialogue; corrections and retractions identify the affected
prior turn with `--revises-turn UID`. Because symmetric sources have equal
authority, later commands may supply the two source names in either order; the
saved frame order remains stable internally. Directional source order is
authoritative and cannot be reversed on resume. `--defer-all` closes the
current session as review-only. An explicit `--restart` replaces that saved
analysis only after its bound Contexts are revalidated; a failed replacement
analysis leaves the previous session intact.

Directional acceptance applies only material `EDIT` and `ADD` operations to
the baseline and creates one checkpoint. A ready zero-operation assessment
also creates one checkpoint that records the resolved no-change decision.
Neither case mutates the incoming Context. `--to` remains deliberately absent:
it is reserved for a future explicit destination of a symmetric meld rather
than accepted as an alias for the authority-bearing `--into`.

An eventual `mem ingest --paste` may orchestrate raw intake, atomization, and a
directional meld. Import owns the run manifest and resumability; it must call
the same independently testable atomize and meld contracts rather than
embedding a second semantic implementation.

## Reopening terminal Melds

Applied and review-only Meld sessions remain durable artifacts in
`mem meld --sessions`. In a TTY, selecting either terminal state reopens the
same report Viewer in an explicitly read-only presentation: report sections
and any retained conflict details remain navigable, while resolution,
provider-turn, and apply controls are absent. Closing the Viewer returns only a
short confirmation instead of printing the full report into the terminal
scrollback. Outside a TTY, the command still emits the stable text snapshot so
scripts and redirected inspection retain their existing contract.

This split avoids two misleading alternatives. Removing completed sessions
would discard the decision artifact, while reopening the ordinary mutable
workbench could imply that an applied receipt may be edited or applied twice.
The read-only Viewer preserves inspectability without weakening the saved
application and checkpoint boundary.

## Implementation sequence

1. **Completed: stabilize the atomize adapter.** The existing physical-NFC
   flow retains its schema and command while reusing common meld turn-lineage
   validation, exposing a lossless directional/issue adapter view, and
   declaring that adapter contract in each semantic-turn payload.
2. **Completed: implement bounded symmetric Context melding.** Two direct-
   Memory PEER Contexts import one exact ordered Compare ledger and its saved
   issues provider-free. A subsequent grounding or whole-set turn may produce
   exact non-applying target proposals without favoring either peer.
3. **Completed: add shared issue and whole-set interaction.** The terminal
   shell supports issue selection, reading plus free-form refinement,
   whole-set comments, preserve-all, defer-all, provider-free resume, and
   provider-free acceptance.
4. **Completed: apply symmetric results with recorded evidence.** Source and
   target digests are rechecked, results enter an empty target in one
   checkpoint, both peer Contexts remain unchanged, retry can recover from the
   checkpoint, and trace reports recorded `MELDED` evidence.
5. **Completed: implement Context-to-Context directional meld.** The canonical
   `--into` path and current-baseline `--from` convenience reuse the batch
   frame, turn, relation-group, proposal,
   session-CAS, and acceptance machinery while enforcing ordered `INCOMING`
   and `BASELINE` authority, exact material `EDIT` / fresh-UID `ADD`
   validation, provider-free acceptance, and zero-change receipts.
6. **Completed: share the state-free message composer with Ground.** Ground
   and meld now use the same bordered multiline editor with an independently
   named buffer and the same focused-input convention (`Enter` sends;
   `Ctrl-J` inserts a newline).
   Ground focus and exact-command behavior remain Ground-owned.
7. **Completed: share the Resolution Workbench with Atomize and Update.**
   Nested list/detail/option navigation and UID-bound actions are common;
   Meld's provider loop, relation ledger, readiness, persistence, and
   acceptance remain Meld-owned. Update contributes a read-only planned-change
   projection until its own issue-resolution artifact exists.
8. **Later: connect import.** Let a resumable import run invoke atomize and
   directional meld while preserving each stage's preview, approval, and
   provenance.

Context-to-Context v1 deliberately excludes raw input atomization, automatic
reference traversal, query-only sources, deletion, incoming or peer mutation,
unbounded retrieval, and hidden truncation. Symmetric targets must still be
distinct and empty; only directional baselines may be non-empty. Those
behaviors must not be inferred from the word “meld.”

## Shared terminal chrome

Meld now uses the same neutral terminal sanitization and slot-based vertical
frame composition as Ground and review. It also uses Ground's extracted
state-free framed message composer. Meld may relabel the trusted frame as a
whole-set comment while keeping the same editor instance. Inside that editor,
`Enter` submits and `Ctrl-J` inserts a newline; `Ctrl-S` remains a compatibility
submission alias. A lone `Escape` closes one expanded issue first and closes
the Meld on the next press; from the overview or message composer it closes
immediately without submitting or applying anything. `Alt-Enter` is not an
alias because terminals encode it as the same Escape-prefixed sequence needed
for reliable cancellation. The shared state-free back dispatcher routes only
the presentation step; the Meld adapter still owns the final `None` result.
Its issue navigation and reading-choice presentation now use the shared
Resolution Workbench, while the provider-owned outer loop, saved relation
ledger, readiness, and acceptance behavior remain Meld-specific. Sharing the
component therefore does not turn Ground's
Goal–Rules–Memories controller into meld state. In particular, meld's `A` action
does not become a Ground-style exact-argv approval unless a future adapter
explicitly constructs and displays a receipt whose target, session, and
change-set preconditions are enforced at the save boundary. See
[`shared-tui-command-review-design-rationale.md`](shared-tui-command-review-design-rationale.md).
The higher-level boundary is recorded in
[`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md).
