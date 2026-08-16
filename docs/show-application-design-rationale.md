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
selector, and the command-start current-Context snapshot. The application
loads one immutable `ShowContextSnapshot`, then either returns that Context or
selects exactly one direct item by UID prefix or exact embedded/query-view
name. Unknown and ambiguous selectors fail visibly.

The result distinguishes ordinary Memories, read-only Memory references,
query views, embedded Context rows, and Context snapshots. Every value carries
typed source access, reach, form, state, and permission facts. A query view has
only route identity and public name: its application and public result types
have no content or concealed-source field.

Show is direct and live. It does not recurse through lexical descendants,
perform semantic inference, read an analysis cache, create a saved session,
publish a receipt, checkpoint, or mutate current state. Selecting an embedded
Context shows that Context's direct contents because it is the selected value;
merely listing its parent does not flatten or retain the child's loaded body in
the returned direct snapshot.

## Runtime and authority

`memcommit.show_runtime` captures the Store's current pointer once, resolves
explicit relative locators against that snapshot, and composes the existing
Context/Grant infrastructure. Local Contexts are loaded through the selected
Store. Active-Profile calls may resolve an effective READ Grant; resolution,
projection, and snapshot construction run under one authority-registry read
generation. Narrower QUERY grants remain opaque query-view rows.

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

The existing `mem show` syntax and text are preserved by a plain CLI presenter
under `memcommit.interfaces.cli.show`. The command module now constructs one
typed request, invokes the runtime, maps errors, and renders the result. Show
currently has no interactive TUI route; this extraction does not invent one.
The Find dialogue's exact read-only `mem show` subprocess follow-up continues
through the same CLI boundary.

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
- Show does not add recursive, descendant, history, or search semantics.
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
