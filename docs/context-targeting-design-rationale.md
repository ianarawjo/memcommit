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

- `model.py` owns operation-neutral targeting values and cardinality types,
  including an exact direct-Memory target as its canonical owner Context name
  plus durable Memory UID.
- `resolution.py` owns pure canonical name-prefix expansion and the shared
  `UID` / `CONTEXT:UID` direct-Memory locator grammar.
- `loading.py` loads one root and merges its lexical descendants for existing
  Compare, Update, Meld, and related application paths. It also resolves a
  direct-Memory locator against a strict complete ordinary-local direct graph.
- `search.py` loads one or more searchable roots and independently controls
  embedded-Context traversal and authorized activity artifacts for Find and
  ordinary Query.
- `catalog.py` freezes public Grant rows for namespace navigation while keeping
  the READ-authorized subset separate from opaque QUERY and other non-READ
  roots. Namespace visibility therefore never becomes ordinary load authority.
- `tui/tree.py` owns frozen namespace topology, cursor, and expansion state.
- `tui/selection.py` owns checked values and single-versus-multiple cardinality.
- `tui/memory_selection.py` owns one retained exact direct-Memory choice. It is
  deliberately independent from the tree's transient preview cursor.
- `tui/direct_memory_selector.py` composes that retained choice with the common
  Context selector and lazy direct-item preview controller. Context focus only
  opens a namespace location; only an exact ordinary Memory row can produce a
  `DirectMemoryTarget`.
- `tui/selector.py` composes that cardinality state with the common framed
  namespace tree while callers retain role labels and availability.
- `tui/range_selection.py` composes the frozen readable tree with a process-local
  Profile shortcut, one-versus-many roots, exact-versus-descendant reach, and
  independently unchecked subtree exclusions. Its common checked-row
  projection also maps the compact root-plus-reach state used by saved-session
  setup screens onto every effective visible Context row.
- `tui/reach.py` owns the shared exact-versus-descendant segmented control.
- `tui/rendering.py` owns pointer, marker-slot, indentation, branch, escaping,
  annotation, and line-break grammar while operations supply semantic markers.
- `tui/name_editor.py` owns the optional existing-parent locator and composes it
  with the operation-neutral interface-owned exact-name input.
  Callers supply labels such as Save Location, New Context, or Branch Name.

Find, ordinary Query, the common endpoint setup used by
Compare/Update/Meld/Atomize, and Sever import these controls directly. The full
picker, receipts, Memory preview rendering, clipboard projection, and terminal
orchestration now live in `context_targeting/tui/picker.py`.
`commands/context_picker.py` keeps its established public and test-facing names
as behavior-free compatibility imports only; production callers import the
neutral owner directly. Its operation-neutral preview controller is also
composed into the common endpoint setup and Sever setup trees: it owns lazy
caches, `m`/`M` visibility, and Memory viewport anchors. A caller must opt a
role and mode into direct-Memory selection before one of those anchors may
produce a `DirectMemoryTarget`; otherwise the same row remains read-only and
cannot change a Context receipt. `memcommit.context_scope` is likewise a thin
compatibility facade; new internal callers use `context_targeting.loading`.
The established `ContextMemorySelection` name used by Delete, Import, Trace,
and Rationale is now a compatibility alias for that same target value, not a
parallel receipt type.
Reference, Edit, and Memory Embed compose `DirectMemorySelectorControl` so
their Source navigation, hover-versus-checked meaning, and rejection of
MemoryRef/Context/query rows do not diverge. Their adapters still own snapshot,
replacement, and live-link meaning respectively.

Their non-interactive adapters share the same owner grammar as well. A single
colon separates an existing Context locator from a Memory UID/prefix because
colon has always been invalid in Context names. Qualified locators resolve
relative Context syntax from the command-start current snapshot and search only
that direct owner. Bare selectors scan every ordinary local direct record in a
single strict load and require exactly one matching Memory. They never prefer
the current Context, traverse embeds, treat a MemoryRef as ownership, or inspect
Grant/query content. Ambiguity reports every canonical `CONTEXT:FULL_UID`
candidate so the next request can state its owner explicitly.

Every tree that exposes the shared preview controller also uses one shared
visibility hint. Lowercase `m` toggles direct-item rows only for the Context at
the tree cursor; uppercase `M` establishes a fresh show-all or hide-all state
for every Context and clears per-Context exceptions. The footer spells those
ranges as `THIS Context` and `EVERY Context` and changes `show` to `hide` from
the effective state. Case alone was rejected as the only visible distinction:
on a one-row or collapsed tree the immediate content change can otherwise look
identical even though the later expansion behavior differs.

## Invariants

Public Context names determine lexical hierarchy. Missing prefixes do not
become synthetic Contexts, and Grant attachments never become hierarchy edges.
`expand_lexical_context_names` preserves the caller's frozen catalog order and
deduplicates overlapping roots. Loaders retain their authority-bearing store
and deduplicate loaded Context identities before adding the same graph twice.

Lexical descendant reach, target cardinality, and embedded graph traversal
remain separate. The
merged loader follows its store's normal `load` behavior for compatibility.
Search exposes `follow_embeds` independently and cannot admit query-only
content through the ordinary Context store protocol.

Common controls own mechanics only. Operations still decide selectable names,
role availability, initial scope, validation, provider disclosure, receipts,
and application authority. Sever therefore continues to default to descendant
reach while Compare, Update, and Meld setup default to exact roots. Find keeps
one-versus-many roots, exact-versus-descendant row behavior, and embedded
traversal as three independently configurable controls. The three flagless
quality finders also start with multiple roots and exact reach, but deliberately
omit embedded traversal; their exact visible checked set becomes one aggregate
direct-Memory judgment frame.

Structural and semantic duplicate checks remain separate. A frozen picker
catalog rejects duplicate Context names or duplicate nested selector IDs because
the cursor could not return an unambiguous receipt. It must not hide an otherwise
authorized row merely because another operation role currently names the same
Context or Memory. Compare, Update, Meld, Merge, Embed, and similar adapters let
the person stage that visible combination, then reject an invalid completed
draft or executable request with the operation's own explanation. This keeps
availability and authorization in the picker while leaving rules such as
`Source != Target` at the result boundary.

Nested preview rows are likewise nonselectable by default. A caller may supply
an exact-selector receipt factory when its operation supports direct nested
selection; Revert uses that opt-in for checkpoint versions. Diff uses the same
rows as an operation overview without enabling that receipt, so shared
presentation does not silently broaden an operation's interaction contract.

A direct-Memory choice and descendant reach are mutually exclusive targeting
shapes. Choosing a Memory selects its exact owner Context and forces exact
reach. Explicitly choosing a Context, proposing a new Context, enabling
descendants, or entering a mode that does not support Memory focus clears the
retained Memory target. Hiding or collapsing its preview clears it for the
same reason. This prevents an invisible UID from surviving after the visible
selector has changed meaning. MemoryRef, embedded-Context, and query rows
never receive a direct-Memory selector merely because they share the preview
renderer.

Presentation labels do not define shared-control ownership. `SAVE LOCATION`,
`FROM CONTEXT`, `CRITERIA`, and `NEW CONTEXT NAME` are adapter-supplied roles;
the common name editor and selector do not infer creation, copying, saving, or
authority from those strings. New Context names remain exact lexical values,
not existing-Context locators, even when their editor also offers an existing
parent tree for placement.

The composed Context-name editor is not the smallest reusable unit. An
`ExactNameInputControl` can be embedded without a box, while
`ExactNameFieldControl` adds the common focused Frame. A
`ContextParentLocatorState` and `ContextParentLocatorControl` can likewise be
used without owning a name field; the control receives an exact value only
when the caller chooses to reparent it. The older `ContextNameEditorState`
spelling remains a compatibility alias rather than the reusable identity.
`ContextNameControl` is the convenience composition of the framed name field
and optional parent locator. This keeps Study Profile names and endpoint drafts
on the shared one-line mechanics without pretending they are Context locators.

A MULTIPLE checked-selection control may temporarily contain zero names. This
lets a person clear and rebuild a set without the last row becoming a special
case. The operation enforces its required minimum only when it constructs an
executable request or typed receipt. SINGLE mode still contains exactly one
name; switching an empty MULTIPLE control to SINGLE checks the visible tree
cursor supplied by the composing UI.

Hierarchical group selection is an explicit composition of the common tree,
selection, and reach controls. The tree supplies the complete frozen subtree;
the selection state does not infer hierarchy, so flat pickers retain ordinary
per-row selection. A checked parent action clears its whole group; an unchecked
parent action fills it. Find and ordinary Query retain selected range roots
plus process-local subtree exclusions so cardinality can still mean one or many
ranges while every effective Context it will search remains visibly checked.
It freezes that effective checked set exactly at execution, preventing a hidden
descendant expansion from reintroducing an independently unchecked row. Saved-session
operations retain their separate descendant-reach boolean and are not migrated
to expanded checked lists. Their setup trees nevertheless project that root and
boolean through the same checked-row path, so Compare, Update, Meld, Branch, and
Sever visibly check every effective lexical descendant. Those descendant marks
are implied range presentation, not independently persisted selections. Rows
that are unavailable to the role, including opaque query-only routes, remain
unselected even when their public name is lexically below the chosen root.

The `PROFILE` row is a process-local shortcut composed above the shared Context
tree. Find, ordinary Query, and the flagless quality finders resolve it to their frozen
`ReadableContextCatalog`; it never becomes a persisted Context or locator and
does not broaden the catalog's existing READ authority. Query-only grant routes
remain a separate typed Source catalog and never enter this ordinary tree.

Profile breadth and selected-Context breadth use separate catalog constructors.
`freeze_profile_readable_context_catalog` anchors discovery at the active
Profile's local attachment when the initial row is granted. This retains that
public granted name as the initial selection while including ordinary local
names and every other valid READ grant. `freeze_readable_context_catalog`
retains its narrower selected-view behavior for explicit Query, explicit Find,
List output and receipts, Rationale, and other operations whose operand defines
their whole executable scope. Top-level `mem list` / `mem ls` and
`mem contexts` are static reports and do not compose a Context tree. Bare
`mem switch` and operation-owned setup screens retain the Profile-wide
interactive navigation form; QUERY-only Grant routes remain visible but
nonmaterialized wherever that form is used.
The blank Find, Query, and individual quality-finder workbenches use the
Profile-wide form because they render `PROFILE · ALL READABLE CONTEXTS` as an
executable target. Durable Audit retains its narrower single exact Source
contract.

## Persistence and compatibility boundary

No common control is a durable preference. Repeating searches or questions in
one open Find or Query screen retains its process-local state, but reopening a
screen starts from explicit command defaults. Reopening a saved Compare,
Update, Meld, or Sever session
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
