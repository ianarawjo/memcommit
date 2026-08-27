# Show application boundary matrix

Last reviewed: 2026-08-25.

## Closure statement

Every currently implemented Show route enters one terminal-independent typed
inspection boundary. The operation performs one live authorized read and has
no provider, cache, session, Apply, receipt, checkpoint, Undo, or current-state
mutation lifecycle.

## Package ownership

The canonical terminal-independent implementation now lives under
`memcommit.application.operations.show`. `application.py` owns the typed request, frozen
Context and item result contracts, direct selection, and read-only validation;
`runtime.py` owns current-snapshot and locator resolution, readable catalog and
Grant projection, traversal, direct-item lookup, and Store-backed freezing.
CLI, Python, agent, MCP, and presentation adapters import those modules
directly.

The historical `memcommit.show_application` and `memcommit.show_runtime`
paths remain behavior-free module-identity aliases. They preserve old imports,
monkeypatch targets, and serialized globals without creating a second
implementation owner, and importing `memcommit.application.operations.show` alone remains
lazy.

This relocation changes physical ownership only. It does not alter readable
authority, query-only concealment, Context or Memory targeting, traversal,
projection, public results, or the no-provider and no-durable-effect boundary.
The in-progress readable direct-item resolution remains part of the same
canonical runtime rather than being split across the compatibility path.

| Route | Entry | Application path | Projection | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Current Context | `mem show` | command-start current snapshot → `execute_show` → `show` | Existing direct Context text | None | `TestShow`, application tests |
| Explicit Context | `mem show --context NAME` | one existing-Context locator and READ resolution | Same direct Context text | None | CLI and context-operand tests |
| Explicit direct scope | `mem show -d` | common DIRECT preset → both traversal axes false | Byte-identical default direct Context text | None | Show scope CLI tests |
| Recursive Context scope | `mem show -r [--context NAME]` | common RECURSIVE preset → frozen readable lexical names + readable Embed traversal → UID de-duplication | Aggregate counts followed by one complete direct-content block per Context | None | Show scope, snapshot-reference, and authority/catalog tests |
| Direct Memory | `mem show UID` | frozen unique direct UID-prefix selection; short bare prefixes preserve an exact same-named Context first, then search every ordinary-local direct owner without current preference | Compact `[Memory CONTEXT:UID] CONTENT` line with full owner, UID, and Memory text | None | CLI, application, public tests |
| Embedded Context | `mem show NAME` | exact direct embedded-name selection | Selected Context's direct contents | None | CLI, application, public tests |
| Memory reference | `mem show UID` | direct reference snapshot with detached resolved content or dangling state | Existing reference detail | None | Memory-ref regression tests |
| Query view | `mem show UID/NAME` | opaque query-view row; no query-source load | Metadata and separate Query instruction only | None | query-only, public, and agent tests |
| READ-granted Context | CLI or Profile-backed Python/agent request | effective READ resolution and complete snapshot under one registry generation | Public name, grant facts, readable content, narrower QUERY rows | None | authority-grant CLI/public tests |
| Python | `MemCommitClient.show` | `_operations.show` → runtime/application | Immutable typed Context/item DTO | None | public and import-boundary tests |
| Agent | `ShowAgentAdapter.invoke` | exact public client call | Version-1 JSON envelope with `effect: NONE` | None | agent and registry tests |
| MCP | default registry → MCP projection | exact agent adapter above | Official tool discovery/call envelope | None | MCP projection and installed stdio smoke |
| Find read follow-up | reviewed exact `mem show` subprocess | normal Show CLI route | Captured plain read result | None | existing Find dialogue/runner tests |

## Invariants

1. Current orientation is captured once. Omitted Context and every explicit
   relative locator resolve against that same snapshot.
2. A bare Context operand remains a canonical global name. Only explicit
   relative syntax opts into current-relative lookup.
3. Selection is direct: UID prefix for every item and exact name only for
   embedded Contexts and query views. A short UUID-shaped bare operand first
   preserves an exact same-named Context; otherwise all ordinary-local direct
   owners participate and ambiguity never guesses or prefers current state.
4. Context item order is preserved. Recursive output preserves ownership by
   rendering separate direct-content blocks; it never silently flattens child
   content into the root.
5. Recursive lexical names and Embed edges are independent. A live Context
   reached through both has one block, while an immutable Context Reference is
   traversed only within its retained package and never replaced by live state.
6. Every READ-granted snapshot belongs to one authority-registry generation.
   An explicit-root client never borrows global Profile grants. Grant
   attachment metadata never becomes a lexical hierarchy edge; when the exact
   local Context displays an attached top-level READ row, recursive Embed reach
   resolves that row through its exact Grant binding. QUERY-only rows remain
   opaque.
7. A query-view result has no content or concealed-source identity field and
   Show never opens query-source storage.
8. A successful call performs no provider connection and publishes no Context,
   checkpoint, session, receipt, cache entry, or current-pointer change. A
   Profile-backed read may briefly use the shared authority coordination lock;
   that lock is infrastructure coordination, not a Show result artifact.
9. CLI, Python, agent, and MCP project one typed result; none reconstructs
   targeting or authority policy. Recursive item selection is rejected rather
   than reinterpreting the direct selector contract.

## Intentional exclusions

Show has no current interactive TUI. A future read-only Viewer, historical
snapshot, or bulk selector is a new contract rather than an implicit extension
of this inspection route. Provider-mediated one-shot answering remains owned
by Query.
