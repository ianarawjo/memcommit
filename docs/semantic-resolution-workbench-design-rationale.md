# Shared semantic Resolution Workbench

## Status and scope

Meld, Atomize, Update, Sever, and Fit-repair Resolve now project their
operation-owned artifacts into one interactive Resolution Workbench
presentation contract. Ground
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
The same projection may be opened independently with `mem impact update`,
`mem impact meld`, or `mem impact sever`. That standalone host keeps its Viewer
and Items read-only: it reloads the saved operation artifact and renders the
identical revision-bound Impact ledger without response or mutation
capabilities. For a nonterminal artifact, To Do additionally shows `APPLY?`.
This action exits Impact and hands the saved identity to the owning operation;
it does not authorize mutation. The owning workflow must reload or resolve its
live inputs, repeat its ordinary authority, freshness, and CAS checks, and
present its distinct real Apply action. Backing out of that final Apply
reloads the exact saved artifact and returns to the standalone Impact host;
the handoff is therefore a reversible navigation stack until the owning
operation becomes terminal. Close still leaves everything unchanged, and
terminal artifacts expose Close only.
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
the resting list. Enter on the focused Impact Memory toggles that entry's
`RULE` and `WHY` detail together; Right opens it and Left closes it. Opening a
new row replaces the one process-local expansion, so large Update and Sever
Impact lists can be inspected with arrows without accumulating expanded
detail throughout the report. An expandable row places a compact disclosure
marker before its operation marker—for example `▸ ~ [EDIT]` or
`▸ + [ADD]`—and changes it to `▾` while open. A row without Rule or Why detail
uses `·` rather than falsely advertising expansion.
This expansion is process-local presentation state and never changes the
artifact, selection, Impact projection, or Apply readiness.

Located mutation Impact uses the semantic `mem diff` shape instead of the
single-result hanging row. Its header names the treatment, owning Context
location, and actual Memory UID; its body renders the frozen transition as
`- before` and `+ after`. ADD has only `+ after`, REMOVE has only `- before`,
and an unchanged cross-Context projection uses one `= value` line. Exact
rationale and Rules remain collapsed until Enter; once expanded they use
neutral report-prose styling rather than inheriting a legacy result-row style.
Update names the target owner it will mutate. Sever instead names
`Source → Result`, because it creates a new Result and never deletes or
rewrites Source.

The shared diff renderer is deliberately mechanical. It derives presentation
only from the frozen `before` and `after` strings: exact equality becomes `=`,
a missing side becomes one-sided `+` or `-`, and two unequal sides are aligned
by deterministic line and whitespace-preserving word-token matching. Equal
spans and the explicit `-`/`+` markers are white. Unequal Source-only spans are
red and underlined, while unequal Result-only spans are green and underlined,
regardless of wrapping or vertical placement.
Coloring only the changed spans answers what actually disappeared or appeared
without tinting a whole Memory line. One-sided ADD or REMOVE content is entirely
unequal and therefore receives the corresponding changed-span treatment.
The located Context and Memory identity stay lavender, while EDIT, ADD, and
REMOVE tags use green, blue, and red respectively. This distinguishes updating
an existing Memory, creating a new one, and removing one without borrowing the
warning-like yellow treatment.
Operation labels such as EDIT, KEEP, or SUMMARIZE do not influence hunk
calculation and the renderer never infers semantic equivalence. Consequently,
Update continues to reject an exact no-op EDIT before presentation, while
Sever may intentionally show `= KEEP` because retaining that Memory in the
reviewed self-saved Source or other-saved Result is an operation-owned
decision.

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
evidence-group identity, when an issue contains multiple assessments
classification
source-frame identity
source-linked evidence
type-specific reason
operation-specific proposed result, when present
```

The question is provider-authored guidance about what must be decided; it is
not an input field. Proposed readings or resolutions are operation-authored
answers. Because the question has no independent action, the Responses frame
combines it with those proposed answers into one navigable Decision section. The
selected option and free-form response remain independent, so a
person may choose and qualify an option, or supply a different answer without
selecting one. Sharing presentation primitives preserves visual consistency
without pretending that a read-only result and an actionable session are the
same artifact.

Question, proposed readings or resolutions, and free-form Response are
projected into the independent common `RESPONSES` frame rather than repeated
as report paragraphs. The Viewer therefore remains evidence and outcome
reading space. Adapter-authored response guidance remains model metadata; the
resting Response section shows a neutral Enter affordance, and its inline
editor starts blank unless a durable draft already exists.

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

The migration boundary is now structural as well as behavioral. Atomize and
Meld each retain exactly one live operation host, and both delegate their
interactive decision topology to the shared Resolution Session. Their former
prompt-toolkit applications, private cursor grammars, and full-screen renderers
were removed instead of being kept behind `_run_legacy_*` aliases. Thin command
facades may preserve the public host import during migration, but they must not
re-export deleted private renderers or become a second implementation. Static
boundary tests count the live host definitions so a future compatibility edit
cannot silently restore a shadow application.

Execution and report inspection are separate hosts over the same typed view.
Meld, Update, Forget, Sever, Atomize, and verified Fit-repair Resolve use the
report-free compact decision surface when the current command can advance or
apply semantic state. Explicit Review and Impact retain the complete Viewer,
evidence, Items, and Responses
topology. The compact host may receive an operation-owned Save Location. It
renders the frozen exact value beside the decision and uses the shared
single-line exact-name control when the visible Location row is activated; it
returns a typed destination-change action and never persists or validates
operation meaning itself. Backspace and
printable keys remain editor input, invalid values keep the editor open, and
Escape retreats from the editor before it can close the decision surface.

The compact surface intentionally has one visible grammar: `Left`/`Right`
changes the semantic item, `Up`/`Down` changes the visible row, and `Enter`
activates that row. Choice numbers and `L` may remain undisclosed accelerators;
direct `A`, `D`, and `P` actions are inert. This prevents issue ordinals from
being mistaken for choice ordinals and keeps Location and Apply discoverable
as ordinary rows. A unique operation-authored recommendation may be checked
process-locally on entry; closing saves no newly changed selection, while the
separated Apply row is the single explicit mutation boundary. The complete
report remains a Review concern and
does not reappear as a second confirmation screen.

## Common contract

`ResolutionWorkbenchView` is a complete immutable projection of one operation
revision.  It supplies:

- operation, artifact, and revision identities;
- title, route, status, and locally computed metrics;
- zero or more typed Context locations, each with an operation-owned role,
  exact public name, and optional state such as `NOT CREATED` or `IN PLACE`;
- an adapter-owned list label;
- ordered items with opaque UIDs, status, display priority, semantic role,
  response obligation and state, title, summary, question, option UIDs,
  durable response text, operation-authored detail blocks, optional trace
  references, and an optional typed actionable-issue presentation containing
  exact source Memories, classification, distinct evidence-group/source-frame
  labels, and type-specific labels;
- exact proposed or applied results when the operation has them;
- explicit capabilities for item comments, whole-set comments, preserve,
  defer, and accept; and
- adapter-owned readiness, acceptance mode, and input-lock state.

The list uses the neutral term **item** internally.  Meld calls its items
`ISSUES`, Atomize calls them `ACTIONABLE FINDINGS`, and Update calls them
`PLANNED CHANGES`.  Calling a conflict-free Update operation an issue would
incorrectly claim that the current Update planner produced an unresolved
assessment.

When typed Context locations are present, the report renders one neutral,
non-focusable `CONTEXT LOCATIONS` block directly below its title and before
`WHAT MEM UNDERSTOOD`. The block answers where the operation reads and where
it will write; it is orientation metadata, not part of the provider's
understanding. Adapters therefore use semantic roles instead of parsing the
display route: Atomize exposes Source and Output, directional Meld exposes
Incoming and Baseline/Target, symmetric Meld exposes both Sources and Result,
Sever exposes Source, Criteria, and Result, Update exposes Source and Target,
and Forget exposes Source. Legacy projections without typed endpoints may
still render their route, but new operation adapters must not make the shell
infer Context identity from prose.

The shell renders an item's human-facing kind label as the row prefix. The
durable kind token remains available for command logic, but an adapter may
supply a clearer `kind_label` so tokens such as `ATOMIZE_SPLIT` do not leak
into the UI. Adapter titles contain semantic identity or a source preview
rather than repeating the label; for example
`SUGGESTED SPLIT · “source…”`, not
`ATOMIZE SPLIT · ATOMIZE SPLIT`.

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
The Viewer separately reports total REQUIRED and OPTIONAL reviews. Only an
open REQUIRED response blocks review-and-apply; OPTIONAL reviews can be
inspected and answered but may remain open under the operation's
remaining-item materialization policy.

Acceptance has two presentation modes while retaining the same UID-bound
`ACCEPT` action. Both appear only inside `REVIEW AND APPLY`: `CHANGES` renders
`APPLY`, while `AS_IS` renders `APPLY AS IS`, counts still-open Decision
findings separately from unvisited optional proposal reviews, and states that the unresolved
findings will be recorded at application. The adapter, not the shell, selects
this mode. It is approval of the exact current proposal, not a synthetic
answer, deferment decision, or permission to invent a missing result.

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
members under the neutral `SOURCE CLAIMS` frame as
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

Atomize separates semantic attention from progression obligation. Its
high-attention Ambiguity, Uncertainty, and Conflict rows are OPTIONAL for
progression: unanswered rows do not force a provider turn. An answered unary
response still disables exact acceptance until one complete incorporation
turn has produced a fresh proposal, but Atomize may authorize the explicit
compound `INCORPORATE_AND_APPLY` action. With no such response pending,
detected unresolved meaning or an open suggested-split review selects
`AS_IS`; only a proposal with no open review keeps ordinary `CHANGES`.
Pairwise Conflict responses remain retained
review evidence because Atomize cannot truthfully consume them as unary
declared frames, but their presence does not prevent applying the current
structural proposal.

Atomize identifies unary versus pair evidence before the decision control and
includes the analysis Context in every source label. Ambiguity uses
`CLARIFICATION QUESTION` and `PROPOSED READINGS`; conflict uses
`RESOLUTION QUESTION` and `PROPOSED RESOLUTIONS`. Both retain the original
independent selected-choice and free-response state. `mem impact atomize`
continues to use the separate read-only Result detail grammar.

The shared evidence contract keeps an optional relation/assessment
`group_heading` separate from its required `sources_heading`. Both are neutral
structural chrome: the group heading stays with Classification, while the
source heading stays with the first exact source card. An adapter therefore
cannot place `SOURCE MEMORY` above Classification and leave the actual Memory
under a later, apparently unrelated `SOURCE 1` card.

Classification, each criterion, each whole source Memory, and the type-specific
Why are independent Viewer stops. Enter on a source Memory opens nested reading;
visually wrapped lines are presentation-only offsets within that stable Memory
identity rather than outer focus stops. This preserves evidence arity and avoids
persisting terminal-width fragments. The item kind, ordinal, title, status,
review-set counts, evidence-group heading, and source-frame heading are visible
report chrome, not stops; opening a detail therefore begins at Classification.

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
projects those operations as `PLANNED CHANGES` with exact owner, before/after
content, reason, and source-reference digests. It explicitly does not claim
that no unresolved issue exists. Standalone Impact and applied/undone receipts
remain read-only. Only the owning staged Update marks these no-obligation
change rows as commentable and exposes whole-set guidance.

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

### Ownership-aware decision-free policy

An owning workbench derives one decision-free behavior only after its adapter
declares the proposal applicable and no `REQUIRED` decision remains unanswered.
A reversible mutation confined to the active Profile returns the exact Accept
action without rendering a report or confirmation surface; its normal command
checkpoint makes `mem undo` the recovery boundary. A mutation of a granted
authority Context starts at exact final review instead. Read-only workbenches
never auto-accept.

The mutation target, not the input catalog, determines this policy. Update and
directional Meld may read a granted Source and still auto-apply to a local
Target, while a granted Target retains confirmation. Atomize writes only local
Inputs or planned local Outputs. Sever always creates a local Result and leaves
local or granted Sources unchanged. Forget distinguishes its local Source from
a granted authority Source. An incorporation turn, destination correction, or
unanswered required Conflict prevents the shortcut. The focused rationale and
operation matrix live in
`docs/ownership-aware-application-review-design-rationale.md`.

The staged host offers both `G` whole-set guidance and `RESPONSE` on an opened
Items change. An expanded located Impact row exposes the same response through
`C`; it does not create a second comment identity. Because Update rows carry
no REQUIRED or OPTIONAL obligation, unanswered rows never gate Apply. Once a
nonempty change comment exists, however, Review and Apply offers
`INCORPORATE RESPONSES` instead of applying the stale proposal. Incorporation
is a complete provider replan over the frozen Source, Target, alias-expressed
current proposal, and reviewed guidance. The strict existing operation decoder
validates the replacement, record CAS installs it as a new staged receipt, and
the workbench reopens for review before any physical application.

A general issue-oriented Update resolution loop still requires a separate durable
`UpdateResolutionSession`, stable issue and operation keys, a provider contract
that returns complete issues and readiness, source/target fingerprint binding,
and an export step that creates the existing `UpdateSession` only after every
REQUIRED issue is resolved.  It must not overload the current impact cache or
staged-update file and must not delegate physical application to Meld, because
Update supports embedded multi-owner targets, resolved `MemoryRef` evidence,
removal, and linked rollback boundaries that Context Meld does not.
The implemented comment pass is intentionally narrower: comments are
process-local until incorporated, the durable result is the replacement
`UpdateSession`, and it does not invent an issue ledger or per-row completion
state.

### Sever

Sever projects each outbound candidate and its operation-owned choices through
the common Resolution Workbench after its separate Source–Criteria–Output
setup. The Sever controller continues to own the scoped source snapshots,
candidate selection semantics, exact output, durable session digest, and final
local application. Sharing the workbench does not make the setup screen or the
saved-session listing common, and it does not relax Sever's rule that reviewed
output is never transmitted by the Sever operation.
The embedded Sever Impact is the exact proposed local Result and identifies
`SELF-SAVE` or `OTHER-SAVE`. Self-save removes or edits reviewed Memories in
the exact Source root; other-save creates a new Context without editing Source.
It compares every Source Memory with its reviewed Result representation. KEEP
renders one equality line; redaction, summary, reframe, and custom wording
render a two-sided transition; FORGET renders only the Source-side `-` line.
In self-save, FORGET removes the Source Memory. In other-save, FORGET omits it
from Result while Source remains unchanged.

### Save location before Apply

Operations that select a self- or other-save Result may supply one
operation-owned `SAVE LOCATION` value to the common workbench. The shell
renders it as a compact conditional frame between `ITEMS` and `TO DO`, outside
the report Viewer, and returns one exact `CHANGE_DESTINATION` action from the
frame's one-line direct editor. The resting row shows the current exact name,
its operation-owned state, and `Enter to change`. The shell does not persist,
rename, create, or apply anything itself; the owning operation validates and
commits the new name, then supplies a replacement revision.

When the operation supplies a frozen local Context catalog, Enter expands the
same frame into a shared parent tree above the prefilled direct-name field. The
field retains initial focus. Choosing a parent explicitly preserves the final
name segment and returns to direct editing; browsing does not switch, create, or
load a Context. The operation-specific validator still decides whether the
resulting exact name is legal. The interaction and safety boundary are recorded
in `docs/save-location-control-design-rationale.md`.

Sever uses this action to update its unapplied session output name. Symmetric
Meld uses it to relocate its already-created empty target and target-bound
session. Directional Meld does not expose it because its target is an existing
authoritative baseline. Read-only and review-only projections omit it. This is
an optional shared control, not a review item: when present, visible Tab order
is `VIEWER → RESPONSES → ITEMS → SAVE LOCATION → TO DO` while an answerable
item is open, and `VIEWER → ITEMS → SAVE LOCATION → TO DO` otherwise. It never
enters Items or bypasses Apply gating.

Atomize's durable planned-Output flow now uses this same card and persists a
validated destination change back to its workbench before application. This
removes the second standalone `y/e/n` location receipt that formerly appeared
after the person had already chosen Review and Apply. Symmetric Meld and Sever
continue to use the same shared card. An explicit one-shot Atomize
`--save-as` does not enter the saved Resolution workbench, and Translate
`--save-as` has no such session. They retain the older standalone
exact-location receipt rather than inventing a synthetic review step.
Those non-full-screen paths share the same save-location model and neutral card
renderer while retaining their prompt-oriented approval grammar.
In-place Atomize/Translate, Forget, Update, and directional Meld remain
target-bound and therefore do not expose a misleading save-as control.

### Resolve

Resolve keeps terminal outcomes such as `ALREADY_FIT`, `NEEDS_INPUT`, and
`NEEDS_AUTHORITY` in the shared read-only Viewer. A verified Fit-repair
proposal instead projects its one independently checked candidate into the
same compact execution form as Meld. The candidate is visibly selected, and
the separate Apply row is the sole confirmation. This is also the form opened
by a conflict Find handoff, so that handoff does not revive Resolve's former
large Viewer/Responses/Items/To Do stack.

The compact adapter neither regenerates candidates nor writes storage. It
returns the selected candidate UID to the Resolve application callback, which
applies the already verified process-local analysis after authority and
freshness revalidation. Candidate and revision identity still bind the
application contract even though the TUI does not add a second exact-command
review page. Multiple Pareto-incomparable candidate selection remains outside
this single-candidate compact route rather than being implied by positional
choice order.

## Invariants

- Ground is not a Resolution Workbench adapter.
- Impact never grants an adapter an Apply capability and never performs an
  operation mutation itself. Its `APPLY?` action is only a transition into the
  owning operation's separately validated Apply flow.
- A common view never becomes semantic authority or durable operation state.
- A full adapter revision is replaced atomically; the shell does not patch
  provider results row by row.
- Item and option actions use opaque UIDs, never visible ordinals.
- Adapter-supplied readiness is authoritative.  Zero items can mean ready,
  unassessed, or simply no planned changes depending on the adapter.
- REQUIRED work cannot be bypassed through accept, preserve, close, or a
  capability the adapter did not expose. A high display priority is not a
  REQUIRED obligation; adapters must project that distinction explicitly.
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
