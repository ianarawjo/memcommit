# Shared semantic Resolution Workbench

## Status and scope

Meld, Atomize, Update, and Sever now project their operation-owned artifacts
into one interactive Resolution Workbench presentation contract.  A future
Reconcile implementation is expected to use the same contract.  Ground
deliberately does not: its Goal–Contexts–Rules–Memories–Chat frame, draft
lifecycle, and exact command approval are a different interaction.

The shared workbench is not a shared semantic session.  It owns only an
immutable view projection, UID-addressed action envelope, terminal-safe
list/detail/comment presentation, and ephemeral navigation.  Each operation
continues to own its provider schema, durable state, evidence rules,
reanalysis, readiness, concurrency checks, application, and provenance.

Its optional `ImpactController` is likewise a presentation controller, not a
mutation controller. It supplies a provider-free immutable effect projection
bound to the same operation, artifact UID, and revision as the active view.
The shell renders that projection immediately before the operation-aware
Apply card and rejects stale or cross-artifact projections.
When an Impact projection repeats the view's result rows exactly, the report
renders those rows only in Impact. This keeps one authoritative full list and
avoids doubling potentially hundreds of rows; the operation's overview or
report summary remains responsible for the compact totals above it. An Impact
whose entries differ from the result rows does not trigger this suppression.
Result-backed Impact entries use the `mem ls` hanging-row shape: treatment,
short UID, and content share the first line, while wrapped content aligns to
the same content column. The treatment field is padded outside its brackets to
the widest visible treatment in that Impact list, keeping UID, content, and
expanded Rule/Why columns stable without altering the label itself. Rows have
no decorative blank line between them.
Impact markers and treatment tags use treatment-specific colors while the
resting Memory content retains the shared lavender. Impact deliberately makes
one narrow exception to the common blue focus: a focused Impact Memory's UID,
content, and expanded Rule/Why follow its treatment color, keeping the exact
effect visually bound to its marker and tag. Other Viewer Memory focus remains
blue. `KEEP`, `REDACT`, `SUMMARIZE`, `REFRAME`, `FORGET`, and `CUSTOM`
therefore remain distinguishable without coloring report chrome.
Each entry is its own stable Viewer section, so a large result remains
block-navigable. Influencing Rules and rationale are deliberately absent from
the resting list; Enter on the focused Impact Memory toggles that entry's
`RULE` and `WHY` detail together.
This expansion is process-local presentation state and never changes the
artifact, selection, Impact projection, or Apply readiness.

Located mutation Impact uses the semantic `mem diff` shape instead of the
single-result hanging row. Its header names the treatment, owning Context
location, and actual Memory UID; its body renders the frozen transition as
`- before` and `+ after`. ADD has only `+ after`, REMOVE has only `- before`,
and an unchanged cross-Context projection uses one `= value` line. Exact
rationale and Rules remain collapsed until Enter. Update names the target
owner it will mutate. Sever instead names `Source → Result`, because it creates
a new Result and never deletes or rewrites Source.

The shared diff renderer is deliberately mechanical. It derives presentation
only from the frozen `before` and `after` strings: exact equality becomes `=`,
a missing side becomes one-sided `+` or `-`, and two unequal sides are aligned
by deterministic line and whitespace-preserving word-token matching. Equal
spans retain the base line color while unequal spans receive bold treatment.
Operation labels such as EDIT, KEEP, or SUMMARIZE do not influence hunk
calculation and the renderer never infers semantic equivalence. Consequently,
Update continues to reject an exact no-op EDIT before presentation, while
Sever may intentionally show `= KEEP` because unchanged inclusion in a newly
created Result is an operation-owned decision.

Interactive Resolution rendering derives its content width from the current
terminal on every projection. Viewer report rows, nested option boxes, seeded
Compare/Meld cards, final-review cards, and the Items hanging rows wrap against
that live inner frame width rather than independent 68/72/76/100-column
constants. Items continuation lines align to the title column and are not
ellipsized merely because the window is narrower; terminal resize therefore
reflows both Viewer and Items under the same frame boundary.

The same workbench can host an adaptive `ReviewReport`, but Review applies a
different capability boundary: its controller removes `ACCEPT`, preserves only
operation-owned semantic response actions, and never renders target Apply as
a report action. Compare may supply exact report prose, while Meld, Sever,
Atomize, and Update reuse their existing view blocks.

This distinction follows the same successful boundary as the read-only
`ResultWorkbench`, but the two assets have different responsibilities:

| Asset | Responsibility |
| --- | --- |
| `ResultWorkbench` | Read-only explanation and representative/boundary inspection of one bounded result. |
| `ResolutionWorkbench` | Browse a complete actionable or reviewable list, inspect one item, select an option, submit an item or whole-set comment when supported, and hand an explicit semantic action back to the owning controller. |

They retain separate state, authority, and detail contracts. They share the
same Viewer chrome, focus treatment, neutral report prose, lavender Memory
objects, and blue option selection vocabulary. Result detail remains a
read-only evidence-to-outcome trace. Actionable Resolution detail instead
uses a quality-issue contract derived from the ambiguity review workflow:

```text
issue identity
classification
source-linked evidence
type-specific reason
clarification or resolution question
proposed readings or resolutions
response
operation-specific proposed result, when present
```

The question is provider-authored guidance about what must be decided; it is
not an input field. Proposed readings or resolutions are operation-authored
answers. Because the question has no independent action, the Viewer combines
it with those proposed answers into one navigable Decision section. The
selected option and free-form response remain independent, so a
person may choose and qualify an option, or supply a different answer without
selecting one. Sharing presentation primitives preserves visual consistency
without pretending that a read-only result and an actionable session are the
same artifact.

The Response is a focusable input affordance rather than another semantic
report paragraph. Adapter-authored response guidance remains model metadata;
the resting Viewer shows a neutral Enter affordance, and the inline editor
starts blank unless a durable draft already exists.

## Motivation

Meld and Atomize independently implemented the same interaction grammar:

```text
list of items
→ arrow to one item
→ Enter to inspect its detail
→ arrow through operation-authored options
→ Enter to select or clear one option
→ optionally add a comment
→ return one explicit action to the operation controller
```

Duplicating that grammar made key behavior, terminal escaping, back navigation,
and dynamic-list handling drift.  Update had no corresponding interactive
inspection surface even though its exact edit, add, and remove records have the
same list/detail shape.  Sharing only low-level panes and composers did not
address this higher interaction layer.

## Common contract

`ResolutionWorkbenchView` is a complete immutable projection of one operation
revision.  It supplies:

- operation, artifact, and revision identities;
- title, route, status, and locally computed metrics;
- an adapter-owned list label;
- ordered items with opaque UIDs, status, priority, title, summary, question,
  option UIDs, operation-authored detail blocks, optional trace references,
  and an optional typed actionable-issue presentation containing exact
  source Memories, classification, and type-specific labels;
- exact proposed or applied results when the operation has them;
- explicit capabilities for item comments, whole-set comments, preserve,
  defer, and accept; and
- adapter-owned readiness and input-lock state.

The list uses the neutral term **item** internally.  Meld calls its items
`ISSUES`, Atomize calls them `ACTIONABLE FINDINGS`, and Update calls them
`PLANNED CHANGES`.  Calling a conflict-free Update operation an issue would
incorrectly claim that the current Update planner produced an unresolved
assessment.

The common shell emits only the following UID-bound semantic actions:

```text
SUBMIT_ITEM(item_uid, option_uid?, comment?)
SUBMIT_ALL(comment)
PRESERVE_ALL
DEFER
ACCEPT
CLOSE
```

Visible ordinals are navigation aids and never semantic addresses.  Number
keys do not select options; nested arrows and Enter are the common grammar.
`CLOSE`, Escape, browsing, expansion, and option hovering never imply
acceptance or application.

An item's `n/total` is likewise only its position in the ordered review set.
The Viewer separately reports total REQUIRED and OPTIONAL items. Only an
unanswered REQUIRED item blocks review-and-apply; OPTIONAL items can be
inspected and answered but may remain unanswered under the operation's
remaining-item materialization policy.

## Dynamic list replacement

An operation response may replace its complete bounded assessment.  Items may
therefore be added, removed, reordered, or rewritten after any semantic turn.
The shell preserves only safe presentation continuity:

1. If the selected item UID survives, it remains selected even when its
   ordinal changes.
2. If it disappears, the prior ordinal is clamped into the replacement list
   rather than resetting blindly to the first item.
3. An empty replacement has no cursor; a later non-empty replacement becomes
   selectable again.
4. Expanded detail and option state are cleared across a full revision
   replacement.  Current Meld option UIDs are derived from their visible
   order, so retaining an old option could reinterpret a previous selection
   after options change.
5. The owning adapter must reject a stale item or option UID before turning a
   shell action into a semantic turn.

One submitted comment creates at most one operation-owned semantic turn.  A
Meld controller then replaces the whole assessment, not just the selected row.
Navigation itself is provider-free.

## Operation adapters

### Meld

Meld is the reference dynamic adapter.  Its projection retains source roles,
source Memories, relation reasons, affected proposals, exact result operations,
whole-set actions, REQUIRED readiness, explicit defer, and provider-free
acceptance.  The command controller still records the turn, performs one
aggregate provider call, saves the replacement assessment under CAS, and
applies only the exact accepted change set.

Each Meld relation is kept as one evidence group rather than flattening all
issue evidence into one list and rendering relation judgments elsewhere. A
block names its relation, shows its classification first, then groups its
members by source frame as
`CLAIM N · FROM Context`. Each claim lists its supporting Memories as an
indented `[short UID] exact content` row. The Context is shown once per claim
instead of once per Memory, and the full UID remains in the typed projection
for action identity and provenance rather than dominating the reading view.
The type-specific reason follows the claims. Actual `CONFLICT` relations use
`MEMORY COLLISION` and
`WHY THESE MEMORIES CONFLICT`. An issue may aggregate several relations, but
each collision therefore remains visibly connected to the exact Memories that
participate in it. `RESOLUTION QUESTION` and `PROPOSED RESOLUTIONS` follow
those source-linked judgments; the proposed result follows the decision
control. Trace identities remain validated projection metadata but are not
shown as a Result-style terminal trace while the person is solving the issue.

This grouping also reflects Meld's semantic boundary. Every non-`DISTINCT`
relation must include members from both source frames. Meld may attach several
Memories from either frame to one cross-frame relation, but it does not run a
separate within-frame conflict scan. Atomize remains the operation that can
surface a same-Context conflict pair.

### Atomize

Atomize joins its immutable analysis findings with the existing durable
workbench cursor, selected reading, and free-form response.  Its unary versus
pair evidence arity, issue digest, response persistence, explicit reanalysis,
and Context application remain Atomize-owned.  Editing a response is not a
full assessment replacement and therefore does not reset common navigation.

Atomize identifies unary versus pair evidence before the decision control and
includes the analysis Context in every source label. Ambiguity uses
`CLARIFICATION QUESTION` and `PROPOSED READINGS`; conflict uses
`RESOLUTION QUESTION` and `PROPOSED RESOLUTIONS`. Both retain the original
independent selected-choice and free-response state. `mem impact atomize`
continues to use the separate read-only Result detail grammar.

### Dedup

Dedup is deliberately deferred. The current command is a read-only candidate
finder and has no durable review response, reanalysis, or Apply contract. Its
duplicate groups also have component arity rather than the unary/pair shape of
the current actionable quality issues. Adding it to this UI now would make a
shared-looking resolution control with no authoritative operation behind it.

Atomize's separate multi-turn grounding artifact remains available for deeper
semantic clarification.  Reusing the common presentation does not merge that
artifact into `MeldSession` or named Ground.

### Update

The current Update provider returns exact `EDIT`, `ADD`, and `REMOVE`
operations only.  It does not return exhaustive source dispositions,
unresolved issues, semantic turns, or readiness.  The Update adapter therefore
projects those operations as read-only `PLANNED CHANGES` with exact owner,
before/after content, reason, and source-reference digests.  It exposes no
comment or accept capability and explicitly does not claim that no unresolved
issue exists.

The report overview summarizes those planned items rather than enumerating
them a second time. Items remains the navigation hub for exact owner,
provenance, reason, and full before/after inspection. Impact is the single
effect ledger and uses the same located transition contract as `mem diff`.
The operation kind belongs to the shared row prefix, so an Update title does
not repeat it as `ADD n · ADD …`.

`mem impact --to` uses the common interactive drill-down in a terminal and a
deterministic snapshot outside one. In a TTY, `mem update --to` stages the
ready plan, embeds that same exact Impact projection, and requires a distinct
Apply action; closing leaves the receipt staged and the target unchanged. The
non-TTY explicit command retains its deterministic scripted application
behavior. Its multi-owner locks, rollback, checkpoints, operation digest, and
application receipt remain unchanged.

A general Update resolution loop still requires a separate durable
`UpdateResolutionSession`, stable issue and operation keys, a provider contract
that returns complete issues and readiness, source/target fingerprint binding,
and an export step that creates the existing `UpdateSession` only after every
REQUIRED issue is resolved.  It must not overload the current impact cache or
staged-update file and must not delegate physical application to Meld, because
Update supports embedded multi-owner targets, resolved `MemoryRef` evidence,
removal, and linked rollback boundaries that Context Meld does not.

### Sever

Sever projects each outbound candidate and its operation-owned choices through
the common Resolution Workbench after its separate Source–Criteria–Output
setup. The Sever controller continues to own the scoped source snapshots,
candidate selection semantics, exact output, durable session digest, and final
local application. Sharing the workbench does not make the setup screen or the
saved-session listing common, and it does not relax Sever's rule that reviewed
output is never transmitted by the Sever operation.
The embedded Sever Impact is the exact proposed local Result and is explicitly
labelled `SOURCE UNCHANGED`; Apply materializes a new Context without editing
the Source.
It compares every Source Memory with its reviewed Result representation. KEEP
renders one equality line; redaction, summary, reframe, and custom wording
render a two-sided transition; FORGET renders only the Source-side `-` line.
The directional location makes clear that FORGET omits material from Result
while Source remains unchanged.

### Save location before Apply

Operations that materialize a distinct new local Result may supply one
operation-owned `SAVE LOCATION` value to the common report. The shell renders
it as a focusable card immediately before the final Apply card and returns one
exact `CHANGE_DESTINATION` action from the inline direct editor. The shell does
not persist, rename, create, or apply anything itself; the owning operation
validates and commits the new name, then supplies a replacement revision.

Sever uses this action to update its unapplied session output name. Symmetric
Meld uses it to relocate its already-created empty target and target-bound
session. Directional Meld does not expose it because its target is an existing
authoritative baseline. Read-only and review-only projections omit it. This is
an operation capability, not a fourth durable workbench pane: the shared
`VIEWER → ITEMS → TO DO` topology and Apply gating remain unchanged.

The same visual and exact-name review contract is reused by the older
text-report materialization paths for Atomize `--save-as` and Translate
`--save-as`. Those commands do not acquire a synthetic Resolution session;
the card only edits their already-explicit fresh destination immediately
before Apply. In-place Atomize/Translate, Forget, Update, and directional Meld
remain target-bound and therefore do not expose a misleading save-as control.

### Reconcile

Reconcile has no public semantic backend yet.  The common projection and
action contract are reserved for it, but this is not evidence that a
`mem reconcile` command, provider schema, durable session, or application path
exists.

## Invariants

- Ground is not a Resolution Workbench adapter.
- Impact never grants an adapter an Apply capability and never performs an
  operation mutation itself.
- A common view never becomes semantic authority or durable operation state.
- A full adapter revision is replaced atomically; the shell does not patch
  provider results row by row.
- Item and option actions use opaque UIDs, never visible ordinals.
- Adapter-supplied readiness is authoritative.  Zero items can mean ready,
  unassessed, or simply no planned changes depending on the adapter.
- REQUIRED work cannot be bypassed through accept, preserve, close, or a
  capability the adapter did not expose.
- Untrusted adapter text is terminal-sanitized before rendering.
- A trace-bearing generic detail requires both evidence and judgment
  references. Actionable issue detail must instead supply at least one exact
  source-linked evidence group and explicit type-specific labels.
- Closing, expanding, hovering, and commenting do not authorize mutation.
- Provider calls, persistence, CAS, locks, checkpoints, rollback, application,
  and publication remain operation-specific.

## Alternatives rejected

One generic durable session was rejected because the operations have different
source arity, evidence, mutation, and recovery contracts. Making Update call
public Context Meld was rejected because the current public command combines
two peers into a distinct result Context, while Update can traverse a writable
Context graph, cite resolved references, remove Memories, and checkpoint
several owners. Reusing Ground's five-pane controller was rejected because a
named Ground records a reviewable Goal–Rules–Memories frame and exact commands,
not a replaceable operation issue ledger. Sharing only terminal panes was also
insufficient because it left list identity, nested navigation, semantic action
addressing, and replacement behavior duplicated.
