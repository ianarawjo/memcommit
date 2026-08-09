# Interactive Find search and scope rationale

## Problem

The one-shot `mem find QUERY` contract required a person to know both the query
and the search frame before entering the command. Its default frame combined
three different ideas: one selected Context, lexical namespace descendants,
and explicitly embedded Contexts. `--direct` disabled both descendant and
embed traversal together, and the CLI exposed only one root even though the
candidate collector already accepted multiple roots. The help text described
the result type but did not make that provider-disclosure boundary legible.

## Decision

In a TTY, operand-free `mem find` opens one process-local, read-only search
workbench. It starts with an empty one-line `SEARCH` field focused, the current
or explicit Context checked, and no provider call. `mem find QUERY` remains the
non-interactive one-shot route and retains stable grouped output for scripts,
redirection, and existing callers. Operand-free Find outside a TTY fails with
an explicit query-required message rather than blocking on terminal input.

The workbench presents four visible controls in screen order:

1. `SEARCH`, a one-line query submitted with Enter;
2. `TARGETS`, the frozen readable Context tree with Enter or Space changing
   the checked ordinary local or READ-granted root while focus remains in the
   tree;
3. `SCOPE`, with independent `TARGET SELECTION`, `RANGE`, and
   `EMBEDDED CONTEXTS` choices; and
4. `RESULTS`, grouped by the exact owning Context.

Tab and Shift-Tab move through that same order. The search field owns initial
focus so opening Find feels like opening a search engine rather than entering
a setup wizard. An empty query is UI state, not a request to rank every item.

Target cardinality starts in `MULTIPLE` to preserve the fast path of checking
peers on the first visit to the tree. `SINGLE` makes the next checked row
replace the current target. Changing an existing multi-root selection to
`SINGLE` retains the most recently explicitly checked root rather than silently
returning to the initial current Context. At least one target is always
required. Enter and Space are selection keys in `TARGETS`; `/`, Escape, and
Backspace are the explicit paths back to `SEARCH`. This prevents Enter from
appearing to accept a row while actually abandoning the tree unchanged.

`INCLUDE DESCENDANTS` means canonical lexical namespace descendants only: selecting
`task-1` includes materialized readable names beginning `task-1/`. `FOLLOW`
under `EMBEDDED CONTEXTS` independently controls traversal through explicit
Context objects. The legacy default remains both enabled; `--direct` initializes
both disabled when it is used with operand-free Find. Keeping the controls
independent prevents "below" from silently meaning a graph edge.

Every submission freezes the query, ordered selected roots, range, embed
choice, and limit into one `FindSearchRequest`. Changes to query, targets, or
scope invalidate the visible result set and require another Enter; stale rows
must never appear to describe a new frame. Search work runs outside the
prompt-toolkit event-loop thread while the exact request stays visible and
immutable. Closing during a search waits for that read-only turn to complete.

## Authority and privacy boundaries

The target tree comes from `ReadableContextCatalog`. Each public name retains
its exact `ContextAccess`; a Grant attachment is never treated as a namespace
edge. Query-only views are not selectable ordinary roots. Their already-public
names may still appear as current-state candidates where the selected readable
parent exposes them, but their concealed contents are never opened.

Overlapping roots, namespace descendants, and embeds are deduplicated by
Context identity and logical item identity before ranking. READ-granted roots
may contribute authorized Memory content but never the authority Profile's
private checkpoints, sessions, traces, or rationale artifacts. Temporal
queries remain unavailable for a selected granted root because READ authority
does not expose checkpoint history.

The workbench is read-only and process-local. It does not persist queries,
targets, tree expansion, scope choices, results, or provider dialogue, and it
does not change the current Context. Existing one-shot current/history routing
and provider output validation remain the semantic execution boundaries.

## Reuse and limitations

The workbench reuses the common Context tree state, Context reach control,
horizontal-choice renderer, focused Frame styling, terminal escaping, grouped
search-result presentation, and close-safe background-turn controller.
`ContextTreeState` continues to own only cursor and expansion, while the shared
`ContextSelectionState` owns checked values. Find is the only current operation
that configures that state for multiple roots; the common endpoint and Sever
setups use the same state in single-selection mode. Multi-selection semantics
are not added to the full-screen generic picker or exposed to those operations.

The one-shot `--context` option remains singular, and the range/embed choices
apply uniformly to every checked target. Result inspection and conversational
follow-up remain separate from this Google-like search surface; the retained
legacy Find chat shell is not silently reactivated. Query-only routes remain a
separate authorized interface and never become selectable ordinary roots.
