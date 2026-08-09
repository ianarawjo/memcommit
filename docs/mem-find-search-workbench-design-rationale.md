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
2. `TARGETS`, the frozen readable Context tree with Space toggling one or more
   ordinary local or READ-granted roots;
3. `SCOPE`, with independent `RANGE` and `EMBEDDED CONTEXTS` choices; and
4. `RESULTS`, grouped by the exact owning Context.

Tab and Shift-Tab move through that same order. The search field owns initial
focus so opening Find feels like opening a search engine rather than entering
a setup wizard. An empty query is UI state, not a request to rank every item.

`INCLUDE BELOW` means canonical lexical namespace descendants only: selecting
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

The workbench reuses the common Context tree state, horizontal-choice renderer,
focused Frame styling, terminal escaping, and progress animation. Find owns the
meaning of its target union and search results; those semantics are not added
to the generic picker.

The first version exposes multi-target selection in the interactive surface.
The one-shot `--context` option remains singular, and the range/embed choices
apply uniformly to every checked target. Result inspection and conversational
follow-up remain separate from this Google-like search surface; the retained
legacy Find chat shell is not silently reactivated.
