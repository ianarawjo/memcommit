# Unified delete/remove selector

## Decision

`mem delete SELECTOR` and `mem remove SELECTOR` are complete command aliases.
Both spellings use the same arguments, options, target resolution, authority
checks, mutation paths, and output. A selector can identify either an existing
ordinary Context or one direct item in the active or explicitly supplied
Context.

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

## Selector contract

Without `--context`, one command-start snapshot of the active Context is used
for both candidate domains:

- existing ordinary Contexts use the shared Context locator grammar, including
  `.`, `..`, `./...`, and `../...`;
- direct items use exact UIDs, unambiguous UID prefixes, and the existing exact
  names supported for context-like direct items.

If the same spelling selects both a Context and a direct item, the command
fails closed. `--context CONTEXT` explicitly chooses the direct-item domain and
resolves that containing Context through the existing local/Grant-aware access
path. Context deletion is intentionally local: DELETE permission on a granted
view authorizes deletion of direct authority items, not destruction of the
authority's Context record and history.

The Context confirmation and UID/digest compare-and-delete boundary remain in
place under both command spellings. Direct-item deletion retains the historical
noninteractive behavior of `mem remove`; `--force` matters only when the
resolved target is a Context.

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
contains locally owned ordinary Contexts and their direct items. Granted
direct-item deletion remains available through an explicit selector and
`--context`, preserving its exact Grant-aware authorization boundary without
presenting an authority-owned Context as locally deletable.
