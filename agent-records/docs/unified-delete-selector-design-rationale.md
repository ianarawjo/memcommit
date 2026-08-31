# Unified delete/remove selector

## Decision

`mem delete SELECTOR...` and `mem remove SELECTOR...` are complete command aliases.
Both spellings use the same arguments, options, target resolution, authority
checks, mutation paths, and output. Each selector can identify either an
existing ordinary Context or one uniquely owned local direct item, and one
explicit invocation may mix both target kinds in argv order. `--context`
remains an optional owner qualifier for ambiguity, exact Context-like item
names, and Grant-backed deletion; when supplied, it qualifies every selector
as a direct item and disables ordinary Context selection. It is not required
merely because a known UID belongs to a noncurrent Context.

This unifies two deletion verbs without erasing the underlying safety boundary:
deleting a Context still removes its complete checkpoint history and records a
Profile lifecycle event, while removing a direct item still saves the owning
Context through its normal automatic-checkpoint and Grant-aware mutation path.

With no selector, both spellings enter the same shared Context tree used by
the other Context-browsing commands. Direct items are selectable navigation
rows within that tree. The picker reuses held-arrow acceleration, tree
expansion, viewport cursor anchoring, the `›` focus pointer, and scrollbar
arrows instead of defining deletion-specific movement or scroll state. It
returns an exact Context name or Context-plus-full-item-UID receipt; display
text is never re-parsed as a destructive target.

The no-selector form is a continuing curation session rather than a one-shot
Apply flow. Enter on a direct item commits that exact deletion inside the
long-lived picker application, refreshes the affected Context rows in place,
and places focus on the nearest surviving item. The canvas does not close or
flash a separate success screen; the footer alone shows the latest typed
`REMOVED` receipt until the next interaction. The action and removed-item
description share the semantic REMOVE color while the close hint remains
neutral. Escape or `q` closes the session; it does not apply, roll back, or
group the deletions that already succeeded.
Closing before the first deletion retains the historical
`Deletion cancelled.` receipt. Context deletion retains its separate exact
confirmation and catalog-refresh boundary because it removes the Context and
its history rather than one row in a still-live Context.

Each accepted deletion remains one independently committed operation. Direct
item deletion therefore writes one normal `remove` checkpoint per Enter and
Undo restores those selections one at a time in reverse order. This preserves
the existing checkpoint, Grant-authority, and failure boundaries: a later
selection can fail without misrepresenting earlier successful deletions as
rolled back. Treating a whole interactive curation session as one atomic Undo
unit remains an intentional non-goal until a command-group transaction and its
partial-failure semantics are designed explicitly.

The explicit variadic form follows the same independent-commit contract. It
first resolves and freezes every selector without mutation, rejects duplicate
targets, and rejects a batch that selects both an ordinary Context and one of
its direct items. A missing, ambiguous, unauthorized, or overlapping selector
therefore prevents every requested effect. Different ordinary Contexts and
direct items from different owners may be mixed freely; lexical parent and
descendant Contexts remain independent records because deleting a parent
preserves descendants.

If the frozen batch contains one or more ordinary Contexts, the human CLI
prints the irreversible warning for every such Context and asks for one shared
confirmation before the first effect. After that approval it revalidates every
Context identity/digest and direct-item owner/UID/content projection before
publishing anything. `--force` skips only this shared human confirmation; it
does not skip resolution, authority, protection, or freshness checks.

Apply then follows argv order. Each direct item still creates its own normal
checkpoint and each ordinary Context still creates its own lifecycle event.
Multiple items in one owner are reloaded by their frozen full UID after each
preceding checkpoint so their sequential CAS saves compose without selector
retargeting or lost updates. This is deliberately not one atomic command group:
if a later target changes concurrently or fails during Apply, earlier successful
targets remain committed and their individual receipts remain truthful. A
future atomic batch would need a durable transaction spanning Context records,
checkpoint histories, lifecycle events, and derived-artifact cleanup; variadic
argv alone does not imply that contract.

## Selector contract

Without `--context`, one command-start snapshot of the active Context is used
to resolve relative Context spellings, while the candidate domains remain
deliberately distinct:

- existing ordinary Contexts use the shared Context locator grammar, including
  `.`, `..`, `./...`, and `../...`;
- direct-item UIDs and UID prefixes use the shared strict ordinary-local
  direct-item locator, which searches every local owner with no priority for
  Current and returns one exact `DirectItemTarget` only when the owner
  coordinate is unique;
- the existing exact-name grammar for embedded Context and Query View rows is
  retained as a Delete-specific fallback in Current, or within the owner named
  by `--context`, because those names also occupy the combined Context selector
  namespace.

If the same spelling selects both a Context and a direct item, the command
fails closed. `--context CONTEXT` explicitly chooses the direct-item domain and
resolves that containing Context through the existing local/Grant-aware access
path. Context deletion is intentionally local: DELETE permission on a granted
view authorizes deletion of direct authority items, not destruction of the
authority's Context record and history.

A unique bare UID therefore removes a noncurrent local item without changing
global Current. If a prefix matches multiple direct items, Remove reports every
candidate as `CONTEXT:UID`, publishes no mutation, and requires an explicit
owner qualification. An exact full UID wins over longer prefix matches, but
Current never wins an ambiguity merely because one candidate happens to be
active.

This lookup is not a Profile-wide content search. Its frozen catalog contains
only ordinary local direct records, never resolved MemoryRef targets, embedded
bodies, restorable snapshots, or Grant authority content. A malformed or
unreadable local record fails the complete scan instead of silently shrinking
the deletion namespace. Granted direct items still require `--context`, after
which the established Grant-aware DELETE authorization path resolves and
revalidates the authority owner.

The Context confirmation and UID/digest compare-and-delete boundary remain in
place under both command spellings. Direct-item deletion retains the historical
noninteractive behavior of `mem remove`; `--force` matters only when the
resolved target is a Context.

## Application and callable boundary

Both effects now enter `memcommit.application.operations.direct_changes.delete.application` through
`memcommit.application.operations.direct_changes.delete.runtime` rather than being implemented by the
command module. The former top-level paths remain true module aliases for
compatibility. Direct-item removal first compiles either a bare UID or a picker
receipt into the same operation-neutral exact `DirectItemTarget`, then freezes
the authorized owner and full item UID before one normal checkpointed save.
Context deletion first freezes a
canonical local name, Context UID, record digest, and an effect-bound plan
digest; Apply passes those values to the existing compare-and-delete Store
primitive. The CLI/TUI, public Python, agent, and MCP routes project those same
typed plans and receipts.

Approval deliberately remains outside the application contract. A human CLI
prints the exact frozen irreversible effects and asks y/N unless `--force` is
present. Agent/MCP projection instead exposes read-only planning and destructive
Apply as separate tools. MCP advertises standard effect annotations, allowing
the host to request permission before the Apply call without making the server
read terminal input. Host full-access or approval-never policy can skip that
dialogue; exact target identity, authority, protection, and freshness checks
still apply.

Direct-item removal is advertised as mutable but non-destructive because it
creates a normal Undoable checkpoint. Context Apply is destructive and
non-Undoable. A deletion whose primary commit succeeded but whose ancillary
cleanup failed returns `APPLIED_WITH_CLEANUP_WARNING`; it must not be retried as
though no deletion occurred. The CLI keeps a nonzero operator-attention exit,
while machine adapters preserve a committed success receipt and warning.

## Namespace directories

No separate cleanup operation is required for an empty lexical path. Context
deletion already prunes empty namespace directories from the deleted leaf
toward the Context storage root. Pruning stops as soon as a directory contains
a surviving descendant or an ordinary Context record, which is required by the
promise that deleting a Context preserves descendants.

## Intentional limits

The combined selector applies only to destructive CLI target selection. It
does not make Memory UIDs into Context locators, reinterpret new Context names,
or authorize deletion through a query-only route. The initial picker catalog
contains locally owned ordinary Contexts and their direct items; its
Context-plus-full-UID receipt is normalized into the same exact target used by
an explicit selector. Granted
direct-item deletion remains available through an explicit selector and
`--context`, preserving its exact Grant-aware authorization boundary without
presenting an authority-owned Context as locally deletable.
