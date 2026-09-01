# Resolve Audit-to-Update design rationale

Last updated: 2026-08-31.

## Motivation

An Audit issue means the stored Context does not determine one safely
authoritative change. If the missing intention were provable, Resolve would
not need a person. Resolve therefore must neither manufacture an automatic
answer nor ask the person to approve model-authored mutation operations.

Audit already owns discovery. Resolve consumes one immutable completed Audit,
derives a conservative direction for each actionable item, and asks the person
to accept it, replace it with exact intent, or deliberately leave that item
unresolved. The existing Update operation alone determines exact ADD, EDIT,
and REMOVE effects from the complete finalized input. Resolve owns the human
decision, verification, authority, and final publication boundaries.

## Public flow

```text
freeze one exact direct Context and mutation capabilities
-> load the newest Audit matching its exact direct-Memory snapshot
-> if none matches, run and save the complete Audit
   (redundancy, ambiguity, conflict, whole-Context Fit,
    optional Rule conformance)
-> derive exactly one non-mutating direction for every actionable Audit item
-> collect exactly one ACCEPT, INTENT, or LEAVE UNRESOLVED decision per item
-> bind the decisions to the Audit snapshot and Context revision
-> project every accepted direction and exact intent into one process-local Source
-> call ordinary Update once over that Source and the complete Target Context
-> apply the exact UpdatePlan to detached state
-> run the complete Audit over the resulting whole-Context post-image
-> reject every new or unpermitted remaining Audit issue
-> atomically publish the exact UpdatePlan as one Resolve checkpoint
```

The UpdatePlan does not exist before decisions are finalized. `mem impact
resolve` can therefore show the Audit directions and planning boundary, but it
cannot preview speculative edits.

## Audit entry and direction ownership

Resolve matches a saved Audit by exact Context UID and direct-Memory digest.
With an explicit Rules operand it additionally requires the exact frozen Rule
UID/content frame. Without a newly supplied Rules operand, the newest matching
Audit is reused as recorded, including its optional Conformance section. A
missing or stale record causes all three Audit finders, whole-Context Fit for a
multi-Memory Source, and Conformance when requested to run before the completed
immutable record is saved and the decision UI appears. A matching historical
Audit without Fit remains reviewable but is not reused for a current
multi-Memory Resolve run.

Fit retains one judgment over the complete ordered Memory set. `YES` adds no
Resolve item. `MAY` or `NO` adds exactly one `FIT` item whose members are the
ordered material Memories named by the judgment. Resolve does not split it
into pairwise conflicts or one item per Memory, and the direction provider may
not change its verdict or membership.

The Resolve provider receives the complete Context plus the exact immutable
Audit items. Its output schema requires one direction for every supplied item
identity. It cannot add, omit, merge, split, or reclassify findings and cannot
return edits, additions, removals, a post-image, or an UpdatePlan. The direction
is a proposed missing meaning or handling, not proof and not mutation
authority.

## Decision meanings

Each item has three explicit choices:

- `ACCEPT THIS DIRECTION` contributes the displayed conservative direction to
  Update input.
- `ADJUST WITH YOUR INTENT` contributes the person's exact nonblank intent
  instead.
- `LEAVE UNRESOLVED` contributes no semantic evidence. It permits only that
  same exact Audit key to remain and records the unresolved item if it still
  exists after verification.

There is no automatic Resolve choice. Finalization requires a valid decision
for every displayed item and preserves Audit order. Each issue is bound to the
Audit snapshot digest and each complete decision set to the frozen Resolve
revision, so a changed Audit, Context, or authority frame invalidates the turn.

## Console focus and draft behavior

The visible choice topology is always:

```text
1 <-> 2 <-> 3
```

The inline `YOUR INTENT` field is visually attached to choice 2 but is not a
fourth Up/Down row. Moving onto choice 2 immediately activates its neutral
one-line editor and requests a blinking beam caret. Left/Right then moves the
text caret rather than changing Audit items. Enter or Escape freezes the draft
and returns to choice 2; Up or Down freezes it and moves directly to choice 1
or 3. Merely traversing an unchanged retained draft does not select choice 2.
A blank draft does not satisfy choice 2 and does not make Finalize ready. If
the person later selects choice 1, the draft remains process-local for
reversible editing but is excluded from finalized input.

Previous and next item controls are explicit selectable actions immediately
above `FINALIZE DECISIONS`. Left/Right also changes items. This placement makes
the traversal discoverable without putting navigation in the header or
inserting the text field into the decision sequence.

The mechanics remain in the shared compact shell, but this choice-bound mode
is enabled only by Resolve. Existing Meld and other callers retain their
independent optional note field until they adopt the same application
semantics; UI reuse alone does not transfer Resolve ownership.

## Update ownership and one-shot Context planning

Resolve constructs one process-local Source Context containing one Memory per
accepted direction or supplied intent. Each Source Memory names the target
Context, exact Audit item identity and classification, member Memory identities,
the accepted meaning, and the preservation requirement. The Source is never
persisted. LEAVE UNRESOLVED decisions are excluded because control state must
not authorize unrelated semantic edits.

Resolve calls ordinary Update once with the complete process-local Source,
complete frozen Target, exact allowed target uses, and staged status. A single
person input may therefore clarify other Memories, repair multiple Audit
items, enrich previously unflagged information, or introduce a new issue. A
Memory selector controls which Audit items are actionable; it does not shrink
the Target passed to Update or the post-image verification frame.

Resolve has no parallel candidate, effect, post-image, or UpdatePlan generator.
It consumes the canonical `UpdatePlan` and the canonical detached application
functions. This keeps Update responsible for how supplied information changes
Memory while Resolve retains its distinct decision and safety semantics.

## Complete post-image Audit

The exact UpdatePlan is applied to a detached Target and materialized as one
complete resulting Context. Resolve then runs the same complete Audit
application over that post-image. If the source Audit included Conformance,
the exact recorded Rules frame is reconstructed for the post-image check.

A remaining issue is allowed only when its exact semantic key belongs to a
LEAVE UNRESOLVED decision. Every other duplicate, ambiguity, conflict, Fit, or
Rule judgment—including a new issue involving another Memory—blocks
publication.
An unresolved decision is written to the receipt only when that exact key still
appears; incidental repair removes it from unresolved state.

This gate proves neither global truth nor that the model inferred the person's
intent. Fit is ordinary-reading compatibility, not factual verification. The
gate proves only that the reviewed post-image has no unpermitted Audit issue
under the same bounded checks. It is not a special `Fit == YES` hard gate:
the same exact `FIT` key may remain only through the ordinary explicit
LEAVE UNRESOLVED decision.

## Authority, freshness, and publication

The Resolve revision covers the contract, Context identity and digest,
canonical display target, actionable Memory identities, requested effects,
and guidance. Freshness is checked before Update planning, after the Update
and Audit semantic turns, and again under the mutation lock.

The Store adapter accepts only an UpdatePlan naming the frozen target and
operations owned by that target. Every operation must fit the frozen CREATE,
UPDATE, or DELETE capability set. DELETE remains opt-in, requires nonblank
grounding guidance, and fails when an inbound `MemoryRef` targets a removed
Memory.

Publication uses one command lock and Context-digest compare-and-swap. The
resulting checkpoint retains the UpdatePlan identity and digest, exact
operations, every finalized input and effective content, still-unresolved
item identities, guidance, and Grant identity when applicable. A turn that
only leaves items unresolved has an empty UpdatePlan but may still write this
reviewed checkpoint; that history write requires mutation authority.

## Adapter contract

The console owns only decision collection. After finalization it presents
bounded Update-planning and complete post-image Audit stages, then renders a
receipt only after atomic publication. A non-interactive invocation prints the
Audit directions and never assumes decisions; the immutable completed Audit
may already have been saved, but no Resolve checkpoint is created.

Python and agent adapters use the same typed items and decision list. The
Python safety wrapper preserves provider/model provenance so Audits created
through public adapters remain durable and attributable. Agent analysis is
cached only process-locally by revision, and Apply requires the matching
revision plus complete decisions.

## Alternatives rejected

Generating a complete post-image inside Resolve was rejected because it would
duplicate Update's application responsibility. Passing the person's text only
as Update planner guidance was rejected because guidance is not Source evidence
and cannot retain one exact decision per Audit item.

Applying each issue independently was rejected because one input can affect
other Memories and relationships. The finalized inputs are therefore sent in
one Update against the complete Target, followed by one complete Audit.

Re-running conflict discovery directly inside Resolve was rejected because it
would bypass Audit's application ownership and omit redundancy, ambiguity,
Fit, and Conformance. Treating LEAVE UNRESOLVED text as Source was rejected because a
request to tolerate uncertainty must never authorize changes.

Making the intent field a fourth navigation row was rejected because it turns
the semantic sequence into `2 <-> input <-> 3`. The field is instead an editor
mode owned by choice 2. Applying that behavior globally to every compact-shell
caller was also rejected: Meld's current free-form note is semantically
independent and retains its existing topology.

## Remaining boundaries

- The runtime publishes operations only to the one direct Context owner frozen
  by Resolve; cross-Context Update plans fail closed.
- Audit and direction provider judgments may conservatively over- or
  under-report semantic relations.
- Resolve decision drafts are process-local until a final checkpoint is
  written. Closing before finalization publishes no Resolve mutation.
- Meld, Atomize, Forget, and other operations may later adopt this
  Audit-to-Update shape, but both semantic adoption and presentation ownership
  must be explicit.
