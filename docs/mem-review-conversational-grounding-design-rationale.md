# Conversational grounding for semantic review

## Status

This note records the implemented atomize-specific conversational loop and the
design direction it is intended to test. The current atomize workbench can
still save a selected reading and freeform response for reviewed reanalysis.
In addition, one selected issue can now open a durable multi-turn **atomize
grounding session** that records reviewer turns, provisional understanding,
concrete downstream effects, follow-up questions, and exact edit/add
proposals.

The implemented command surface is:

```text
mem atomize --evaluate ISSUE [--comment TEXT]
mem atomize --reply TEXT
mem atomize --accept-grounding
mem atomize --keep-review-only
```

`--comment` may be collected interactively from a TTY, but it is required for
non-interactive `--evaluate`. The semantic boundary is stable: `--evaluate`
starts a dialogue anchored to one saved atomize issue, `--reply` contributes
another reviewer turn, and neither command changes a Context. Acceptance
applies the exact ready edit/add proposal in one Context save and one
checkpoint. Keeping review evidence ends the dialogue without changing Memory
content or creating a checkpoint. Bare `mem atomize` renders and resumes an
open saved dialogue provider-free. The Context-bound artifact is stored at:

```text
~/.mem/atomize-groundings/<context-uid>.json
~/.mem/atomize-grounding-history/<context-uid>/<session-uid>.json
```

The first path is the resumable latest slot. When a dialogue becomes
`KEPT_REVIEW_ONLY` or `APPLIED`, its exact terminal record is also written to
the immutable Context-scoped history before a later dialogue may replace the
latest slot. There is not yet a CLI for listing or diffing that history.

`--evaluate` and each `--reply` make exactly one isolated semantic completion.
`--revision confirm|extend|correct|retract` can state how a reply relates to
the preceding turn. All directly owned Memories, their positions in the full
direct-item order, the actionable issue projection, anchor, cumulative turns,
and prior assessment are supplied under opaque aliases; persistent Memory and
issue identities remain local. Reference pointers participate in the local
binding and position calculation, but referenced content is not opened or
sent.

The immediate next TODO after the atomize slice is to generalize this turn
model for the existing `mem ground` operation. That generalization is not
implemented by the atomize work and must not be inferred merely because both
features use the word "grounding."

## Primary design objective

The most important interaction goal is to make agent communication resemble
grounding in ordinary human communication.

People do not normally treat one clarification as an isolated form field.
They update a provisional shared understanding, notice consequences, ask
whether those consequences are intended, accept corrections, and only then
act on the resulting common ground. A useful memory agent should follow the
same pattern:

```text
reviewer comment
→ provisional understanding
→ consequence or scope question
→ reviewer confirmation, correction, or extension
→ revised understanding
→ proposed Memory changes
→ explicit permission
→ one recorded application
```

This objective is stronger than making the interface conversational in tone.
The system state must represent the epistemic stages that the conversation
expresses. User evidence, agent inference, user confirmation, and stored
Memory content are different records and must not be collapsed.

## Motivating interaction

Suppose a reviewer comments on an authentication issue:

```text
The Main Building entrance is unusual: app authentication does not work
there, and only a physical NFC card is accepted. Other buildings differ.
```

The agent should not immediately store that text or merely rerun the selected
item. It should first expose the consequences it currently understands:

```text
CURRENT
The selected issue appears resolved as "use a physical NFC card only."

THEN — REQUIRED CHANGE
Another Memory says students may be told to use the app. Under the supplied
clarification, that guidance appears wrong. Should it be removed?

THEN — FOLLOW-UP
A later Memory says the staff-only entrance uses "the same NFC." Does that
entrance also require a physical card and reject the app?
```

The reviewer may then correct and extend the provisional account:

```text
The earlier app guidance was wrong; do not tell students to use the app.
The staff-only entrance uses the same physical-card-only method.
```

Only after incorporating that reply should the agent summarize its revised
understanding and ask whether to edit the current Memory, edit affected later
Memories, add a reusable policy Memory, or keep the discussion as review
evidence only.

This example motivates a multi-turn session rather than a one-shot
comment-to-change transformation.

## Why this behavior is needed

### Avoid repeated clarification

If a comment resolves several later questions, asking for the same fact again
is wasteful and unlike normal collaborative dialogue. The agent should surface
the possible reuse while the reviewer still remembers why the clarification
was given.

### Make implications correctable

A model may overgeneralize a local rule. Asking "then does this later statement
also mean X?" makes the extension visible and cheap to reject. Applying the
extension silently would convert model inference into apparent user knowledge.

### Permit belief revision

A later turn may correct an earlier source, qualify the first comment, or
withdraw an inferred extension. The implementation must maintain a revisable
working understanding instead of concatenating every comment into one growing
declared frame.

### Promote demonstrated reuse, not speculative reuse

A reviewer comment can be local, tentative, private, or phrased as an
instruction rather than a durable fact. A suggestion to create a Context
Memory becomes appropriate only after the analysis demonstrates that a
stand-alone proposition is needed by another concrete issue. Even then,
promotion requires explicit confirmation.

### Preserve the reason for a change

This repository is a research prototype whose interaction history may support
later analysis. A resulting Memory should be traceable to the anchor issue,
the reviewer's wording, the agent's proposed implication, and the reviewer's
confirmation. Recording only the final text would erase the grounding process
that justified it.

## Conversational state machine

The interaction should be an explicit session. The provider call that analyzes
a turn is transient; the durable states are `AWAITING_REPLY`,
`READY_TO_APPLY`, `KEPT_REVIEW_ONLY`, and `APPLIED`:

```text
evaluate or reply
→ AWAITING_REPLY
→ reply and reassess
→ AWAITING_REPLY
→ ...
→ READY_TO_APPLY
→ APPLIED
```

The reviewer may also leave from `AWAITING_REPLY` or `READY_TO_APPLY` by
choosing `KEEP_REVIEW_ONLY`, which records `KEPT_REVIEW_ONLY`. No Context
mutation occurs in that path.

Each turn contains:

1. the anchor issue and its complete source arity;
2. the selected reading, if any;
3. the reviewer's verbatim response;
4. the active user-supported propositions after superseding corrections;
5. the agent's direct judgment about the anchor;
6. concrete downstream consequences linked to existing issue identities;
7. follow-up questions whose answers would change a judgment or proposal; and
8. provisional edit or addition proposals.

A new answer may confirm, extend, qualify, correct, or retract earlier session
content. Superseded propositions remain in the turn history but must not remain
active evidence. A retracted turn can never support a current proposal. A
partially corrected turn may still support an unaffected fact, but the
proposal must cite both that earlier turn and every correcting turn. This
keeps the repair visible without forcing a reviewer to restate unrelated
facts; citing only the old turn is rejected.

## Atomize grounding-session contract

An atomize grounding session is an operation-specific adapter over the saved
atomize analysis and workbench. It is not a replacement analysis, a global
chat log, or a Context Memory. At minimum, its durable envelope needs:

- the Context UID and digest;
- the source atomize-analysis and workbench UIDs;
- the anchor issue UID and its complete source arity;
- an ordered, append-only list of reviewer and agent turns;
- the current active user-supported propositions, with superseded propositions
  retained only in history;
- direct and downstream judgments tied to exact issue UIDs;
- pending required changes, follow-up questions, and optional helpful checks;
- exact provisional Memory edits and additions, when enough information
  exists to propose them; and
- one explicit lifecycle state.

The adapter should expose four conceptual actions even if the CLI spelling
changes during integration:

| Action | Contract |
| --- | --- |
| evaluate | Anchor the dialogue, record the first reviewer comment, and ask the semantic provider for the current judgment, consequences, and next questions. A TTY may prompt for the comment; a non-TTY caller must supply it. |
| reply | Append reviewer evidence, recompute the active understanding, and return a new complete assessment rather than patching the prior assessment. |
| accept | Revalidate every bound digest and apply only the exact user-confirmed proposal as one logical operation. |
| keep review only | Close or retain the dialogue as noncanonical evidence without editing a Context or creating an application checkpoint. |

The semantic provider receives the complete active understanding on every
turn, not merely the latest sentence. Its response must be strictly validated:
known issue and source identities only, bounded complete replacement or
addition text, explicit effect roles, no duplicate target edit, and no
model-chosen persistent UID. A malformed turn leaves both the prior session
and Context unchanged.

An `EDIT` target must also be a source Memory of at least one issue cited by
that proposal. A valid issue label is not authority to rewrite an unrelated
direct Memory. If an affected Memory has no saved actionable issue in this
first slice, the provider must leave it unchanged rather than manufacture an
unframed edit; representing newly discovered affected issues is deferred.

Rendering an existing turn is provider-free. A new reviewer reply is a new
semantic turn. This distinction keeps remote snapshots stable and prevents
ordinary navigation from silently changing the agent's interpretation.

The stable presentation roles for the first slice are `YOU SAID`,
`MEM UNDERSTANDS`, `CURRENT`, `THEN`, and `READY TO CHANGE`. Entries under
`THEN` carry one of `REQUIRED CHANGE`, `FOLLOW-UP`, or `HELPFUL CHECK`. These
labels expose the dialogue's epistemic function; they are not decorative chat
headings.

Terminal proposal headings must reflect the lifecycle truth. `READY TO CHANGE`
means an exact proposal still awaits permission, `APPLIED CHANGES` means that
proposal was recorded in its checkpoint, and `REVIEW-ONLY PROPOSALS` means it
was retained without mutation. An applied screen must never reuse wording such
as "provisional" or "blocked"; that would contradict the durable receipt.
Exact normalized captures for the main state transition are indexed in
[`mem-atomize-grounding-screen-captures.md`](mem-atomize-grounding-screen-captures.md).

### Why each interaction element exists

| Element | Human-grounding purpose |
| --- | --- |
| Issue anchor | Keeps the conversation about one inspectable breakdown instead of letting a free chat silently redefine the whole Context. |
| `YOU SAID` | Preserves the person's actual contribution so a later paraphrase can be checked against it. |
| `MEM UNDERSTANDS` | Makes the agent's provisional uptake observable and therefore correctable. In ordinary dialogue this is the "so you mean..." move. |
| `CURRENT` | Answers the question that prompted the clarification before branching into wider consequences. |
| `REQUIRED CHANGE` | Performs the ordinary "then this earlier claim cannot stay as written" inference while still asking permission. |
| `FOLLOW-UP` | Tests a plausible extension, such as whether "the same NFC" inherits the clarified rule, without presenting the extension as user knowledge. |
| `HELPFUL CHECK` | Separates useful refinement from a question that blocks safe progress. |
| `--reply` | Supports repair: the reviewer may confirm, qualify, correct, or retract the agent's uptake. One-shot submission cannot model this ordinary conversational behavior. |
| `READY TO CHANGE` | Shows that the parties appear to share an actionable understanding and exposes its exact storage consequences. |
| `--accept-grounding` | Turns conversational agreement into explicit authority for one exact mutation; understanding alone is not permission to write. |
| `--keep-review-only` | Lets useful dialogue remain evidence when the reviewer does not want it promoted to canonical Memory content. |

This mapping is the primary rationale for a structured artifact. If these
stages existed only as prose generated by a model, the system could look
conversational while losing which inference was proposed, which proposition
the user repaired, and which exact change the user authorized.

## Types of agent response

The interface should distinguish at least these roles:

### `CURRENT`

Explains whether the selected issue appears resolved, partially resolved, or
unresolved under the current provisional understanding.

### `REQUIRED CHANGE`

Identifies a concrete existing Memory or judgment that cannot remain as
written if the provisional understanding is accepted. This is an implication
to confirm, not an automatic edit.

### `FOLLOW-UP`

Asks whether a plausible scope extension is intended. A follow-up must name
the affected source or issue and the judgment that depends on the answer.
Generic topical prompts such as "anything else about access?" are insufficient.

### `HELPFUL CHECK`

Offers a non-blocking clarification that would improve later organization or
wording but is not required to produce a safe current result.

### `READY TO CHANGE`

Shows exact complete replacement text and exact proposed new Memory text only
after the required grounding questions have been answered or explicitly
deferred.

These roles are not confidence scores. They describe how one conversational
move contributes to reaching usable common ground.

## Direct and downstream judgments

Each semantic turn may assess the entire selected Context, but downstream
claims must cite stable issue identities. An affected count is derived only
from those stored effect records; the model must not return an unsupported
number or a generic topic label.

The provider omits unaffected issues instead of emitting a long `UNCHANGED`
inventory. A plausible anaphoric dependency is affected even when its scope is
not yet known: a later “same NFC” statement, for example, becomes a
`NEEDS_CONFIRMATION` effect and required follow-up rather than being silently
extended or dismissed.

For each effect, the system should retain:

- the prior issue UID and source UID or UIDs;
- whether the relation is direct or downstream;
- whether the reviewer evidence is required or merely helpful;
- the prior judgment and proposed new judgment;
- the proposed resulting reading;
- an explanation of the dependency; and
- the reviewer's later confirmation, correction, or rejection.

A fresh semantic completion can show that a finding changed after a comment,
but it cannot independently prove that the comment caused the change.
Human-facing text should therefore say that an issue "appears resolved under
this understanding" until the reviewer confirms it and a post-application
analysis verifies the changed Context.

## Evidence-scope boundary

The existing asymmetry between source-local atomization and Context-wide
quality judgment remains intentional.

- A shared clarification can resolve a downstream ambiguity or conflict when
  the complete Context supplies the needed reading.
- The same clarification does not silently make another Memory self-contained
  for source-local atomization.
- A downstream `ATOMIZE UNCERTAINTY` clears only when that Memory receives its
  own traceable frame or accepted rewrite, unless the atomization contract is
  deliberately changed in a separate decision.
- A response to a pairwise conflict retains both source UIDs. It must never be
  flattened into one side's unary declared frame.

This boundary lets the agent reason conversationally across the Context
without hiding which stored Memories still depend on surrounding prose.

## Mutation and promotion

During discussion and turn analysis:

- Memory content is unchanged;
- no Context checkpoint is created;
- proposed additions receive no model-generated persistent identity; and
- the latest proposal remains distinguishable from accepted user knowledge.

At `READY_TO_APPLY`, the reviewer may:

- accept the exact complete proposed edit/add batch;
- revise the understanding or wording through another reply;
- retain the session as review evidence only; or
- in a future selective-review extension, accept only chosen edits or
  additions.

Before applying, the implementation must reload the Context and validate its
UID, digest, source analysis UID, workbench UID, anchor issue UID, and response
digest. All accepted edits and additions must be prepared before the first
mutation and saved as one logical operation with one checkpoint. A failure
must leave no partial edit or addition.

This is exception-atomic in the current prototype: an ordinary write error
rolls back the newly created checkpoint and leaves the prior Context file
unchanged. It is not process-crash-atomic. A process death between checkpoint
creation and Context replacement can leave a ghost post-change checkpoint;
closing that window requires a transaction journal or recovery manifest. The
implemented idempotent recovery covers the later window in which the Context
and checkpoint succeeded but the small grounding receipt did not.

Adding a new Context Memory and rewriting dependent Memories are different
actions. A shared Memory improves retrieval and Context-wide judgment; an
explicit rewrite makes a particular Memory stand alone. The UI should explain
that distinction rather than implying that one action automatically performs
the other.

## Provenance and explanation

An applied grounding session should record enough evidence for `mem trace` and
`mem rationale` to distinguish:

```text
raw source
→ original issue
→ verbatim reviewer turn
→ active user-supported proposition
→ agent-proposed implication
→ reviewer confirmation
→ applied edit or addition
```

The checkpoint should retain:

- the grounding-session and turn identities;
- the source analysis and workbench identities;
- the anchor issue and complete source arity;
- a digest of each verbatim reviewer response;
- every per-turn assessment and downstream issue effect;
- the exact prior questions that the provider judged the latest turn to have
  substantively answered, plus explicit correction/retraction links;
- accepted, rejected, or deferred proposal decisions;
- exact before and after content for edits;
- exact content and locally allocated UID for additions;
- the reason for each proposal; and
- which user confirmation authorized each applied change.

The complete accepted change set is content-addressed and retained in the
checkpoint. Trace validation compares each recorded operation, target,
content, reason, issue link, and supporting turn against that change set
before labeling the rationale `RECORDED`.

Model-proposed reasoning is not labeled as a user rationale until the reviewer
has confirmed it. Unapplied proposals remain analysis evidence, not Memory
history.

## Interaction presentation

A turn may render as:

```text
CURRENT
The selected issue appears resolved as: physical NFC card only.

THEN
[REQUIRED CHANGE] #5 still permits app guidance. Remove that guidance?
[FOLLOW-UP] #10 says the staff entrance uses the same NFC. Does the same
physical-card-only rule apply there?

YOUR RESPONSE
> ________________________________________________________________
```

After the answer is incorporated:

```text
MEM UNDERSTANDS
- Students must be told to use a physical NFC card.
- App authentication is not accepted at the Main Building entrance.
- The staff-only entrance uses the same physical-card-only method.

PROPOSED CHANGES
1. Edit the student guidance Memory.
2. Edit the staff-entrance authentication Memory.
3. Add a reusable Main Building authentication-policy Memory.

Is this understanding and change set correct?

[Apply exact proposal] [Continue discussing] [Keep review only]
```

The interaction may use one provider call per semantic turn. Reopening or
rendering the saved session is provider-free. A correction starts a new turn;
it never silently replaces the prior assessment without retaining its history.

## Rejected alternatives

### Apply after the first comment

Rejected because one clarification may contain a local exception, an error,
or an unexamined consequence. It does not establish shared understanding.

### Add every reusable-looking comment as a Memory

Rejected because wording that helps one analysis is not necessarily a durable
stand-alone fact. This would fill Contexts with speculative or redundant
content.

### Concatenate all comments into one declared frame

Rejected because later turns may retract earlier claims, multiple issues can
have different source arity, and provenance would no longer identify which
turn supported which result.

### Infer downstream effects from disappeared issue counts

Rejected because semantic reruns are not deterministic and a count does not
identify what changed. Effects must refer to exact prior issue identities and
remain subject to reviewer confirmation.

### Treat a shared Context fact as a silent rewrite of every dependent Memory

Rejected because it would weaken source-local atomization and conceal which
Memories cannot stand alone.

### Use a friendly chat transcript without structured state

Rejected because conversational tone alone cannot support stale-input checks,
selective confirmation, atomic application, or traceable rationale.

## Implementation boundary

The implemented slice is limited to one direct Context, one resumable latest
Context-bound grounding session, immutable terminal-session records, and
existing actionable atomize-workbench issues. It does not infer effects in
parent, predecessor, referenced, or query-only Contexts. Query-only and
referenced content is never opened by this workflow.

The one-shot Codex provider is still a research containment mechanism, not a
production confidentiality boundary. Use only fictional or otherwise approved
study data; the broader provider and deployment caveats in
[`query-only-research-prototype.md`](query-only-research-prototype.md) also
apply here.

The first slice accepts only the complete exact proposal. Selective edit/add
acceptance and an individual proposal-review UI remain deferred; a reviewer
must instead reply with a correction and obtain a new complete proposal.

The implementation uses a typed assessment artifact, strict provider-output
validation, multi-turn state, explicit edit/add proposals, atomic confirmed
application, and provenance support. Existing ordinary workbench comments
retain their separate per-issue review semantics and are not retroactively
described as conversational grounding turns. Selective per-proposal acceptance
and a dedicated full-screen dialogue panel remain deferred.

Grounding turns contain verbatim local reviewer text. Deleting a Context
therefore deletes only that Context UID's latest grounding artifact and
terminal-session history. If a dialogue was applied, its promoted comments
also live in the Context's checkpoint provenance and disappear with that
Context history. Another Context's artifacts are not touched.

There is no cross-process lock. Inputs are reloaded after every semantic call
and immediately before application, so detected concurrent changes fail
closed; a writer racing in the remaining check-to-write interval is a known
prototype limitation.

## Superseded generalization TODO and retained boundary

An earlier design expected Atomize and named Ground to become the first two
adapters of one shared dialogue controller. Implementation showed that this
would conflate two different artifacts. Named Ground maintains a reviewable
Goal–Contexts–Rules–Memories–Chat frame and freezes exact commands for
separate approval. Atomize and Meld instead work through replaceable,
operation-bounded issue assessments. Ground therefore remains a distinct
controller rather than an adapter of the shared Resolution Workbench.

The reusable pieces are narrower:

```text
shared turn-lineage and correction vocabulary where semantically valid
+ shared Resolution Workbench view/action/navigation for Meld and Atomize
+ operation-specific provider, persistence, readiness, and application
```

Update uses the same workbench only for read-only planned-change inspection
until a durable Update resolution artifact exists. Future Reconcile may adopt
the view/action contract, but not by inheriting Atomize storage or Ground's
exact-command lifecycle. The current separation remains explicit:

- an atomize grounding session does not make a named Ground complete;
- an accepted atomize clarification is not automatically a Ground Memory or
  Rule;
- an existing named Ground does not become declared Atomize evidence;
- no automatic import, export, or bidirectional synchronization exists; and
- sharing a terminal form never turns a comment into permission to mutate.

The common frontend decision and its dynamic-list rules are recorded in
[`semantic-resolution-workbench-design-rationale.md`](semantic-resolution-workbench-design-rationale.md).
