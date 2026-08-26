# Show application design rationale

## Motivation

`mem show` was already a deterministic read operation, but its command module
owned five distinct responsibilities: current/relative Context targeting,
READ-Grant resolution, direct-item selection, query-only concealment, and
terminal rendering. Python or agent callers could not inspect the same value
without invoking the CLI or reconstructing those safety rules.

Show is also a useful boundary test because its output can contain complete
Memory text. A reusable route must expose authorized readable content while
making concealed query-only content structurally impossible to return.

## Contract

`memcommit.show_application` owns one `ShowRequest` and one typed `show` use
case. A request contains an optional Context locator, an optional direct-item
selector, independent lexical-descendant and Embed reach, and the command-start
current-Context snapshot. The application loads one ordered immutable Context
scope, then either returns the root Context, exposes every Context as a direct
snapshot, or selects exactly one direct item by UID prefix or exact
embedded/query-view name. Unknown and ambiguous selectors fail visibly.

The result distinguishes ordinary Memories, read-only Memory references,
query views, embedded Context rows, and Context snapshots. Every value carries
typed source access, reach, form, state, and permission facts. A query view has
only route identity and public name: its application and public result types
have no content or concealed-source field.

Show is live and direct by default. `-d/--direct` makes that default explicit;
`-r/--recursive` freezes readable lexical descendants and follows readable
Embed edges. Recursive scope de-duplicates live Context identities reached by
both paths and renders one complete direct-content block per Context rather
than flattening ownership. Context References remain immutable occurrences:
Show traverses only Context records retained in their snapshot package and
does not substitute a same-named live Context.

A selector remains direct-item targeting and therefore rejects recursive
scope. This avoids turning an existing UID-prefix lookup into an implicit
cross-Context search with new ambiguity and authority semantics. Selecting an
embedded Context in direct mode continues to show that Context's direct
contents because it is the selected value.

Neither scope performs semantic inference, reads an analysis cache, creates a
saved session, publishes a receipt or checkpoint, or mutates current state.

## Runtime and authority

`memcommit.show_runtime` captures the Store's current pointer once, resolves
explicit relative locators against that snapshot, and composes the existing
Context/Grant infrastructure. Recursive Profile-backed reads freeze one
`ReadableContextCatalog`; ordinary local and effectively READ-granted public
names therefore share one public lexical namespace while every name retains
its exact access binding. Active-Profile resolution, attached-Grant projection,
scope traversal, and snapshot construction run under one authority-registry
read generation. Grant attachment is authorization metadata rather than a
hierarchy or Embed edge. Narrower QUERY grants remain opaque query-view rows.

An explicit-root `MemCommitClient` is an already selected Store boundary. It
does not consult process-global Profile grants. A Profile-backed client uses
grants only while its frozen Profile and Store still match the live active
Profile. This prevents an explicit library root from accidentally borrowing
authority from unrelated global state and makes a Profile switch fail closed.

Normal Store loading may resolve a `MemoryRef` to a detached current content
copy. That is different from a `QueryContextRef`: Show never calls the query
source loader and never returns its target-source UID, provider route, or
content.

## Interface projections

The plain CLI presenter under `memcommit.interfaces.cli.show` keeps a direct
ordinary-Memory lookup compact as `[Memory CONTEXT:UID] CONTENT`. The owner and
full durable identity remain visible, but the single selected object's metadata
does not consume a separate header block. Structured detail remains appropriate
for Memory references and query views because their relationship, state, or
safe invocation metadata cannot be expressed by the ordinary-Memory line.
Context and recursive output also retain their inventory structure; recursive
output begins with aggregate direct-item counts, then renders the same full
direct Context form once per scoped Context. Reach is shown separately from
access so a granted descendant or embedded Context does not collapse
authorization and traversal into one label. The command module constructs one
typed request, invokes the runtime, maps errors, and renders the result. Show
currently has no interactive TUI route; this scope extension does not invent
one.
The Find dialogue's exact read-only `mem show` subprocess follow-up continues
through the same CLI boundary.

The CLI positional operand now auto-types as an existing Context locator or a
direct item. `mem show task-1` therefore opens Context `task-1` even when the
current Context is `practice/greetings`; `mem show UID` first finds one unique
current ordinary Memory across local and effectively READ-granted public
owners; and `mem show CONTEXT:UID` states the owner explicitly. This makes a
UID printed by Profile-wide Find/List/Search a directly usable read-only
operand. Local and granted candidates have equal standing: ambiguity lists
their public `CONTEXT:UID` coordinates instead of preferring current. For a
bare UUID prefix shorter than the normal eight-character display token, Show
first preserves an exact readable Context with that name. When no such Context
or current readable Memory exists, it searches the complete ordinary-local
direct-item catalog, which retains MemoryRef, embedded-Context, and query-row
selection without opening query-only content. Non-UUID text preserves the
established current direct-name route for embedded Context and query-view rows,
then falls back to Context lookup. `--context` remains the explicit
disambiguator. The CLI normalizes every form into the same `ShowRequest`;
the Python and agent contracts deliberately retain separate `selector` and
`context_name` fields instead of exposing shell-oriented overloading.

`MemCommitClient.show(selector=None, context_name=None)` projects the same
snapshot to immutable public DTOs and stable Show-specific errors. The
version-1 `memcommit_show` agent tool accepts the same optional target and
selector, returns JSON-safe typed source facts, and reports `effect: NONE`.
The existing MCP host projects that agent contract without another operation
implementation.

## Why this design

The application selects over frozen typed rows instead of calling
`memcommit.ops.resolve` on mutable `Context` objects. This keeps prefix and
exact-name semantics testable without a Store while allowing infrastructure
to remain responsible for Context files, embedded/reference loading, Profile
state, and Grant revalidation.

Terminal output was not made the public contract. Formatting concepts such as
colors, shell quoting, the `Ask with:` line, and compact UID display remain in
the CLI presenter. Conversely, returning only rendered text to Python or MCP
was rejected because callers would have to parse prose and could not reliably
distinguish a Memory from an opaque query view.

## Boundaries and non-goals

- Show does not grant QUERY execution; the separate Query operation owns that
  provider and publication lifecycle.
- Show does not search for a selector across recursive Contexts or add history
  semantics. Bare UUID-shaped discovery scans frozen Profile-readable current
  direct owners before the Show request is constructed; it does not follow
  Embed edges, infer lexical reach, or enumerate QUERY-only sources.
- Show does not cache live Context content; each call reads its authorized
  current Store snapshot.
- The public and agent result can legitimately contain complete readable
  Memory text, so callers remain responsible for the transport boundary they
  choose. Query-only content remains structurally absent.
- A future interactive Viewer may consume this application result, but no TUI
  or clipboard behavior is part of this change.

Because the only terminal route retains its prior plain rendering and no TUI
was added or materially changed, this extraction requires no new ordered TTY
screenshot set.
