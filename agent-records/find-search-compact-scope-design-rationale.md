# Find and Search compact scope design rationale

Last reviewed: 2026-08-20.

## Motivating scenario

Provider-free `mem find --tui` used most of a 180×52 terminal to display a
persistent readable-Context tree and a separate five-row scope panel before it
showed a small literal result. Semantic `mem search` repeated the same large
target tree. The common case—search one known Context—therefore looked like a
setup workbench even though the person already had the exact Context name.

The required visual sequence is now:

```text
SCOPE  ->  FIND or SEARCH  ->  RESULTS
```

The query/pattern retains initial keyboard focus even though Scope is rendered
above it. This preserves immediate typing while making the disclosure boundary
visible before the operation input.

## Shared component boundary

`CompactReadableScopeControl` under `memcommit.context_targeting.tui` owns only
operation-neutral mechanics:

- one exact, single-line readable Context input with frozen-catalog completion;
- one `[ BROWSE ]` action whose Profile/multiple tree exists only while open;
- exact-versus-descendant reach and exclude-versus-follow Embed choices;
- the checked Context range, lexical-subtree exclusions, focus surfaces, and
  stable summary text; and
- request projection to one exact effective Context set with loader-side
  descendant expansion disabled.

Find and Search still own their readable catalog and annotations, initial
defaults, request validation, execution, results, clipboard behavior, and
effects. Browse does not load, create, switch, rename, or persist a Context.
Profile remains a process-local shortcut for the frozen readable catalog and
never becomes a storage locator.

Direct input intentionally means exactly one Context. Confirming it replaces a
Profile or multi-Context Browse selection. Multiple targets are edited only in
Browse; Context names are never split on commas or another invented delimiter.
When Browse closes, its checked range remains active and the adjacent state
label reports Profile or root/effective counts even though the input continues
to show one exact representative name.

## Operation projections

Provider-free Find uses a primary-screen compact form rather than an alternate
full-screen application. Its bounded Results frame shows complete wrapped rows
in the established `N [UID] content [Context mX]` form. `mX` remains the frozen
searchable-corpus position; the compact Scope component does not assign it.

Semantic Search keeps a full-screen workbench because a provider turn,
checkable ranked results, Save As, Save Location, and To Do can all be present.
Its setup topology nevertheless uses the same compact Scope above Search.
Checkable Search rows use `N [UID] complete content [Context · kind]` plus any
source annotation or `RELATED` marker. Physical wrapping is allowed; the
application does not insert an ellipsis or discard a content suffix. Search
does not use Find's `mX`, because rank and typed result kind are distinct facts.

## Invariants and rejected alternatives

- The direct field is not a persisted preference. Each launch starts from the
  operation's explicit request/default.
- Browse and direct input share one checked-range state. A parallel command-
  local tree would let visible selection diverge from execution.
- Descendants are projected once into `effective_names`; a request always uses
  `include_descendants=False` so an independently unchecked child cannot be
  reintroduced invisibly.
- Scope edits invalidate stale results. Search additionally locks all scope
  mutation while its frozen background request is running.
- Backspace and ordinary characters remain text editing in both writable
  fields. Escape closes Browse before it invokes the operation-owned back or
  close action.

Reusing the complete Meld Endpoint Setup was rejected. Its named roles, mode
switching, new-Context plans, Memory focus, and exact START review are not part
of read-only retrieval. Copying only Meld's visual rows into each operation was
also rejected because the checked-set and focus semantics would still fork.

## Limitations

Per-root reach mixtures are not encoded: one reach choice applies to the
complete staged root set. Search remains physically hosted under
`memcommit.commands` pending its broader interface-package migration. Find and
Search share Scope mechanics and compact row geometry, not one semantic result
model or one materialization contract.

## Verification evidence

- `tests/test_literal_find_tui.py` covers compact execution, descendants,
  cancellation, and focused/whole copy.
- `tests/test_find_search_workbench.py` covers direct exact Context collapse,
  transient Browse Profile/multiple selection, empty-range rejection,
  descendant exclusions, Embed independence, background freeze, complete
  result rows, Save As, and writable-input protection.
- Ordered 180×52 color PTY records live under
  `agent-records/screenshots/mem-literal-find-reference-rows-20260820` and
  `agent-records/screenshots/mem-search-compact-scope-20260820`.
