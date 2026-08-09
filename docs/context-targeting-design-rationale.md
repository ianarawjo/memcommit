# Shared Context-targeting design rationale

## Problem

Context selection had become a shared interaction pattern without one clear
code location. Namespace-tree navigation lived in `commands/context_picker`,
exact-versus-descendant controls and checked selection were separate command
helpers, the original single-root loader lived at package root, and Find and
Query shared another search-scope loader under `commands`. The implementations
did not import operation code from one another, but their scattered placement
made ownership hard to discover and duplicated lexical descendant expansion.

The controls also have different lifetimes. Tree cursor and checked values are
process-local. Compare, Update, Meld, and Sever persist the semantic scope in
their own saved-session schemas. A new operation starts from its own defaults;
there is intentionally no profile-wide “last Scope” preference.

## Decision

`memcommit.context_targeting` is the concept package for the shared family:

- `model.py` owns operation-neutral targeting values and cardinality types.
- `resolution.py` owns pure canonical name-prefix expansion.
- `loading.py` loads one root and merges its lexical descendants for existing
  Compare, Update, Meld, and related application paths.
- `search.py` loads one or more searchable roots and independently controls
  embedded-Context traversal and authorized activity artifacts for Find and
  ordinary Query.
- `tui/tree.py` owns frozen namespace topology, cursor, and expansion state.
- `tui/selection.py` owns checked values and single-versus-multiple cardinality.
- `tui/selector.py` composes that cardinality state with the common framed
  namespace tree while callers retain role labels and availability.
- `tui/reach.py` owns the shared exact-versus-descendant segmented control.
- `tui/rendering.py` owns pointer, marker-slot, indentation, branch, escaping,
  annotation, and line-break grammar while operations supply semantic markers.
- `tui/name_editor.py` owns the optional existing-parent locator and composes it
  with the operation-neutral exact-name input from `commands.tui_primitives`.
  Callers supply labels such as Save Location, New Context, or Branch Name.

Find, the common endpoint setup used by Compare/Update/Meld/Atomize, and Sever
import these controls directly. The older `commands/context_picker.py` keeps
its established public and test-facing tree names as imports from the new
module because it still owns full picker receipts, Memory preview rendering,
and terminal orchestration. `memcommit.context_scope` is likewise a thin
compatibility facade; new internal callers use `context_targeting.loading`.

## Invariants

Public Context names determine lexical hierarchy. Missing prefixes do not
become synthetic Contexts, and Grant attachments never become hierarchy edges.
`expand_lexical_context_names` preserves the caller's frozen catalog order and
deduplicates overlapping roots. Loaders retain their authority-bearing store
and deduplicate loaded Context identities before adding the same graph twice.

Lexical descendant reach and embedded graph traversal remain separate. The
merged loader follows its store's normal `load` behavior for compatibility.
Search exposes `follow_embeds` independently and cannot admit query-only
content through the ordinary Context store protocol.

Common controls own mechanics only. Operations still decide selectable names,
role availability, initial scope, validation, provider disclosure, receipts,
and application authority. Sever therefore continues to default to descendant
reach while Compare, Update, and Meld setup default to exact roots. Find keeps
multiple roots and independently configurable embeds.

A MULTIPLE checked-selection control may temporarily contain zero names. This
lets a person clear and rebuild a set without the last row becoming a special
case. The operation enforces its required minimum only when it constructs an
executable request or typed receipt. SINGLE mode still contains exactly one
name; switching an empty MULTIPLE control to SINGLE checks the visible tree
cursor supplied by the composing UI.

Hierarchical group selection is an explicit composition of those two common
controls. The tree supplies the complete frozen subtree and the selection
state toggles that caller-defined group through its anchor row. It does not
infer hierarchy itself, so flat pickers retain ordinary per-row selection. A
checked parent action clears its whole group; an unchecked parent action fills
the whole group and records the parent as the most recent explicit choice.
Find uses this composition so every lexical Context it will search is visibly
checked. Saved-session operations retain their separate descendant-reach
boolean and are not migrated to expanded checked lists.

## Persistence and compatibility boundary

No common control is a durable preference. Repeating searches in one open Find
screen retains its process-local state, but reopening Find starts from explicit
command defaults. Reopening a saved Compare, Update, Meld, or Sever session
continues to restore the operation's own serialized booleans.

Those schemas are intentionally not migrated into one shared JSON structure:
Compare stores a pair, Update stores source and target fields, Meld stores a
possibly legacy per-frame value, and Sever has its own compatibility default.
A common in-memory model does not justify invalidating their digests, CAS
preconditions, or old saved sessions.

## Alternatives

A single large `context_scope.py` was rejected because it joined core loading,
search artifact imports, and prompt-toolkit controls. That structure introduced
an import cycle through comparison session discovery and obscured the different
authority boundaries. Keeping all files where they were with naming comments
was also rejected because it left duplicate descendant expansion and made new
operation-local selection state the easiest path.

The selected package groups the concept physically while retaining narrow
modules and one-way dependencies. Additional operation-specific behavior
should enter through adapters or specs rather than by importing one operation's
shell from another.
