# Show application boundary matrix

## Closure statement

Every currently implemented Show route enters one terminal-independent direct
inspection boundary. The operation performs one live authorized read and has
no provider, cache, session, Apply, receipt, checkpoint, Undo, or current-state
mutation lifecycle.

| Route | Entry | Application path | Projection | Effect | Evidence |
| --- | --- | --- | --- | --- | --- |
| Current Context | `mem show` | command-start current snapshot → `execute_show` → `show` | Existing direct Context text | None | `TestShow`, application tests |
| Explicit Context | `mem show --context NAME` | one existing-Context locator and READ resolution | Same direct Context text | None | CLI and context-operand tests |
| Direct Memory | `mem show UID` | frozen direct UID-prefix selection | Complete Memory text | None | CLI, application, public tests |
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
   embedded Contexts and query views. Ambiguity never guesses.
4. Context item order is preserved. Whole-Context output never silently
   flattens lexical descendants or embedded content.
5. Every READ-granted snapshot belongs to one authority-registry generation.
   An explicit-root client never borrows global Profile grants.
6. A query-view result has no content or concealed-source identity field and
   Show never opens query-source storage.
7. A successful call performs no provider connection and publishes no Context,
   checkpoint, session, receipt, cache entry, or current-pointer change. A
   Profile-backed read may briefly use the shared authority coordination lock;
   that lock is infrastructure coordination, not a Show result artifact.
8. CLI, Python, agent, and MCP project one typed result; none reconstructs
targeting or authority policy.

## Intentional exclusions

Show has no current interactive TUI. A future read-only Viewer, recursive
scope, historical snapshot, or bulk selector is a new contract rather than an
implicit extension of this direct inspection route. Provider-mediated
one-shot answering remains owned by Query.
