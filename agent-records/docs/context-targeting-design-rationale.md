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

`memcommit.core.context_targeting` is the concept package for the shared family:

- `model.py` owns operation-neutral targeting values and cardinality types,
  including a raw existing-Context operand, a canonical Context target, an
  exact direct-Memory target, and the broader direct-item coordinate used by
  read operations. Exact item targets always retain their canonical owner
  Context rather than leaving owner discovery implicit.
- `resolution.py` owns pure canonical name-prefix expansion and the shared
  `UID` / `CONTEXT:UID` direct-Memory locator grammar. It also owns the pure
  storage-independent classifier for an overloaded `Context | Memory`
  positional operand.
- `loading.py` loads one root and merges its lexical descendants for existing
  Compare, Update, Meld, and related application paths. It also resolves a
  direct-Memory locator against a strict complete ordinary-local direct graph,
  completes a local auto-typed Context/Memory target, and offers the sibling
  all-direct-item owner lookup needed by Show.
- `application.operations.search.source` loads one or more searchable roots
  and independently controls embedded-Context traversal and authorized
  activity artifacts for Search, Find, and ordinary Query. It belongs to the
  Search operation because those roots are immediately projected into
  Search-owned candidates rather than remaining operation-neutral Context
  targets.
- `application.capabilities.authority.readable_contexts` owns the Store-backed
  read facade that unifies ordinary local and effectively READ-granted public
  Contexts. It remains outside core because it reads Profile and persistence
  state, resolves exact authority, and projects process-local readable edges.
- `application.capabilities.memory_report_targeting` resolves exact current,
  retained, referenced, local, or READ-granted Memory coordinates for shared
  read-only reports. It remains outside core because it composes authority,
  history reconstruction, reference provenance, and physical Store access.
- `application.capabilities.authority.granted_context_navigation` freezes
  public Grant rows from the active Profile and Store while keeping the
  READ-authorized subset separate from opaque QUERY and other non-READ roots.
  This owner is an application capability rather than core targeting because
  it performs live attachment revalidation and applies Grant visibility policy.
  Namespace visibility therefore never becomes ordinary load authority.
- `tui/tree.py` owns frozen namespace topology, cursor, and expansion state.
- `tui/selection.py` owns checked values and single-versus-multiple cardinality.
- `tui/memory_selection.py` owns one retained exact direct-Memory choice. It is
  deliberately independent from the tree's transient preview cursor.
- `tui/range_selection.py` composes the frozen readable tree with a process-local
  Profile shortcut, one-versus-many roots, exact-versus-descendant reach, and
  independently unchecked subtree exclusions. Its common checked-row
  projection also maps the compact root-plus-reach state used by saved-session
  setup screens onto every effective visible Context row.
- `tui/reach.py` owns the shared exact-versus-descendant segmented control.
- `adapters.console.terminal.components.operation_context_scope_editor`
  owns the prompt-toolkit component family: existing-Context selection,
  direct-Memory selection, new exact Context-name editing, compact readable
  scope editing, and the shared tree-row rendering grammar. Context focus in
  the direct-Memory selector only opens a namespace location; only an exact
  ordinary Memory row can produce a `DirectMemoryTarget`. Callers still supply
  role labels, availability, and labels such as Save Location, New Context, or
  Branch Name.

Find, ordinary Query, the common endpoint setup used by
Compare/Update/Meld/Atomize, and Sever import these controls directly. The full
picker, receipts, Memory preview rendering, clipboard projection, and terminal
orchestration live in
`adapters/console/terminal/components/context_picker`. Core Context targeting
retains the frozen tree, reach, selection, name-draft, and typed-target
contracts, but no longer owns prompt-toolkit controls or the complete terminal
picker application. Inside the terminal package, `model.py`, `projection.py`,
`preview.py`, and `rendering.py` expose
the reusable picker component contracts, while `dialog.py` alone owns the
full-screen key bindings, layout, and application lifecycle. The picker
preview controller is also
composed into the common endpoint setup and Sever setup trees: it owns lazy
caches, `m`/`M` visibility, and Memory viewport anchors. A caller must opt a
role and mode into direct-Memory selection before one of those anchors may
produce a `DirectMemoryTarget`; otherwise the same row remains read-only and
cannot change a Context receipt. `memcommit.context_scope` is likewise a thin
compatibility facade; new internal callers use `context_targeting.loading`.
The established `ContextMemorySelection` name used by Delete, Import, Trace,
and Rationale is a terminal compatibility alias for that same core target
value, not a parallel receipt type. `ContextSubtreeSelection` similarly aliases
the operation-neutral `ContextSubtreeTarget`.
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
candidate together with its JSON-quoted exact content so a person can recognize
the intended Memory without probing candidates one at a time. Control characters
remain escaped onto that single candidate line. The final instruction says to
rerun with the chosen candidate's displayed `CONTEXT:UID` value rather than using
the less explicit phrase "one qualified locator."

The overloaded positional grammar is now one typed pipeline rather than a
collection of command-local boolean branches. `parse_auto_typed_context_memory_operand`
first returns either `ExistingContextOperand` or `DirectMemoryLocator` without
reading storage. New Context roots reserve the public eight-or-more-character
UUID-prefix shape and Context names forbid `:`, so this first classification
does not depend on which Contexts happen to exist. A local-only caller may then
use `resolve_local_context_memory_target` to obtain either a canonical
`ContextTarget` or an exact `DirectMemoryTarget`.

The storage-backed completion also accepts the shorter UID prefixes people may
type from a compact display. It preserves an exact Context name first, then
tries the complete ordinary-local direct-Memory owner catalog. A unique match
becomes an exact owner/UID coordinate, no match returns to the operation's
established missing-Context or literal behavior, and multiple matches fail with
every canonical `CONTEXT:UID` candidate. Grant-aware adapters preserve an exact
authorized public Context before this local fallback. Mutating and semantic
source adapters never enumerate Grant contents from a bare short prefix.
Read-only Show, Trace, and Rationale are the deliberate exception described
below. Compare, Resolve, Lock and Unlock, Embed, Reference,
Fit, Conformance, Atomize, Impact Atomize, Chunk, Translate, and Show consume
this common classification and fallback rather than setting their own minimum
prefix length.

This reuse has three deliberate semantic domains:

- ordinary `Context | directly owned Memory` operands use the common typed
  parser and an operation-appropriate resolver;
- Show and Delete may select any direct item, so they retain operation-owned
  name and destructive-ambiguity policy while reusing the common owner/UID
  coordinate mechanics; and
- Fit and Conformance additionally accept literal text, so `text:` and the
  final literal fallback remain their adapter responsibility after the common
  Context/Memory shape classification.

Show applies the same short-prefix precedence to its broader direct-item
catalog. It first resolves current ordinary Memories across the frozen
Profile-readable local and READ-granted catalog so a UID printed by
Find/List/Search can be used directly. If no current readable Memory matches,
it falls back to the ordinary-local direct-item catalog, where it may select
MemoryRefs, embedded Context rows, and query rows. That final lookup remains
operation-owned. Both stages require one unique public owner and never prefer
the current Context.

A bare Memory-shaped operand may enumerate only strict ordinary-local direct
records and must have one unique owner. A qualified owner may instead be
resolved by an operation's Grant-aware access port. The shared local resolver
does not enumerate Grants, follow Embed edges, open MemoryRefs or query-only
content, or confer mutation authority. This split prevents a convenient
positional grammar from silently broadening the operation's readable or
writable namespace.

Read-only Show, Trace, and Rationale additionally compose a Profile-readable
report resolver before that local fallback. It enumerates only current direct
ordinary Memories under effective READ access, keeps the exact `ContextAccess`
for the winning public name, and reports local/Grant collisions as explicit
`CONTEXT:UID` ambiguity. It never opens QUERY-only content or owner history.
Trace and Rationale consult retained local Memories and MemoryRefs only when no
current readable Memory matches. This asymmetry is intentional: result UIDs
round-trip through reports without granting bare-UID mutation or hidden-history
authority.

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
An exact local Context may nevertheless display top-level READ grants attached
to it as process-local source rows. When an operation follows embeds, the
readable catalog resolves those already-visible rows through their exact Grant
bindings. This does not add the granted names to the local lexical subtree,
does not make attachment metadata a namespace parent, and never opens a
QUERY-only source.

Lexical descendant reach, target cardinality, and embedded graph traversal
remain separate. The
merged loader follows its store's normal `load` behavior for compatibility.
Search exposes `follow_embeds` independently and cannot admit query-only
content through the ordinary Context store protocol. Excluding embeds also
keeps an attached READ projection out of the executable content frame, even
though static authority presentation may still disclose that the route exists.

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

Automatic positional typing applies only when an operation explicitly accepts
the union of existing Context and direct Memory. A Context-only operand, a
Memory-only option, a new Context identifier, provider output, and a persisted
canonical name keep their declared types and do not pass through the automatic
classifier. Where an operation exposes explicit role options, they remain the
escape hatch when a legacy UUID-shaped Context name or a short Memory prefix
cannot be inferred safely from shape; qualification supplies the same escape
hatch for a short Memory selector on commands such as Translate.

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
retains its narrower selected-view behavior for ordinary explicit Query/Find
roots, List output and receipts, Rationale, and other operations whose operand
defines their whole executable scope. Explicit `mem find`, `mem search`, and
ordinary `mem query` `-a/--all`, plus the Ambiguity/Conflict finder forms with
that flag, instead opt into the Profile-wide constructor and freeze its concrete
canonical names as the exact request target set. Top-level `mem list`,
`mem ls`, and `mem contexts` are static reports and do not compose a Context
tree. Bare
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
