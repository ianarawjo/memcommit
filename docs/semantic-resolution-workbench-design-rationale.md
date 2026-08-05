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
  option UIDs, and operation-authored detail blocks;
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

### Atomize

Atomize joins its immutable analysis findings with the existing durable
workbench cursor, selected reading, and free-form response.  Its unary versus
pair evidence arity, issue digest, response persistence, explicit reanalysis,
and Context application remain Atomize-owned.  Editing a response is not a
full assessment replacement and therefore does not reset common navigation.

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
The embedded Impact is the exact local outbound draft and is explicitly
labelled `NOT SENT`; Apply materializes the local output only.

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
