# Move callable boundary matrix

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Decision

Move preserves selected ordinary Memory UIDs and content while atomically
changing their direct local owner. Source removal, Target insertion, and any
live-Embed retargets publish as one multi-Context Undo/Redo command. Every
current CLI, TUI, Python, agent, and MCP route enters the same typed application
and Store runtime.

## Route matrix

| Route or concern | Owner | Verified invariant |
| --- | --- | --- |
| Move application | `memcommit.application.operations.move.application` | Move alone owns preparation, application ordering, UID preservation, default RETARGET or explicit BREAK, compatible typed BLOCK input, and receipt validation |
| Shared values and Store kernel | `memcommit.application.capabilities.memory_transfer` | Typed Source/Target/placement/link values plus strict direct graph freeze, inbound live-Embed classification, full-graph revalidation, Target gap, protection, and exception-atomic multi-Context publication |
| Console command | `memcommit.adapters.console.commands.move` | Move alone owns its Typer grammar, local-owner setup, application handoff, cancellation, errors, default live-Embed retarget, compatibility `--retarget-links`, explicit `--break-links`, and mixed-effect receipt |
| Shared console workbench | `memcommit.adapters.console.commands.copy_and_move` | Move supplies its local catalogs and freeze callback to the common MULTIPLE direct-Memory, `INTO + POSITION`, and editable exact-command workbench; forms, command codec, and screen are separate modules, and the workbench performs no direct publication |
| Shared console values and helpers | `memcommit.adapters.console.coordination.copy_and_move` | Common operands, frozen setup values, and placement-receipt helpers |
| Public Python | `MemCommitClient.move_memories` | Sequence and mutually exclusive policy validation with operation-specific public errors |
| Agent | `memcommit.adapters.agent.copy_and_move` | Strict version-2 JSON schema, public-client-only execution, typed JSON receipt, no provider |
| History | `memcommit.command_history` | Shared Move operation UID plus complete affected membership restore removals, additions, and retargets together |

## Link and authority boundary

RETARGET is the route default and rewrites every inbound ordinary local live
Memory Embed in the same command, but refuses a Target-owned link that would
become a self-reference. BREAK is an explicit advanced opt-in that leaves every
exact old binding unchanged and reports the resulting dangling count. The
typed BLOCK policy remains input-compatible but is not selected by a current
route. Immutable snapshot References never change.

All selected owners, Target, and RETARGET link owners are ordinary local
Contexts. A public Grant name is never treated as a movable owner: moving it
would delete authority-owned state and therefore requires explicit `DELETE`
plus a durable cross-Profile transaction journal and recovery protocol.
`READ` or `EXPORT` cannot supply either contract. A detected granted Source
fails before planning or publication with an operation-specific explanation
and directs the caller to Copy first, then Move the resulting local Memory.

Move binds the complete scanned local catalog and every direct record through
publication because absence of another inbound link is part of its safety
claim. The TUI continues to expose only ordinary local Source and Target rows;
Python, agent, and MCP routes reach the same typed rejection instead of
silently reporting an authorized public Source as an unknown local Context.
Store-level Context, Profile, and Memory protection remains authoritative.

## Evidence

- `tests/test_memory_transfer_application.py` covers multi-Source Move,
  preserved identity/order, default RETARGET, BREAK, compatible BLOCK,
  self/collision boundaries,
  full-graph drift, no partial publication, and one-unit Undo/Redo.
- Granted-transfer tests prove that a readable or exportable public Source is
  still rejected without Source or Target mutation and that an authorized
  retained Copy can subsequently enter the ordinary local Move contract.
- `tests/test_memory_transfer_tui.py` covers multi-Memory selection, exact gap
  review, default live-Embed following, cancellation, frozen-plan handoff, and
  the bare CLI route.
- `tests/test_memory_transfer_public_api.py` covers stable Python DTOs and
  operation-specific errors.
- `tests/test_memory_transfer_agent_adapter.py`, agent registry tests, and MCP
  projection tests cover strict machine schemas and the shared route.
- `agent-records/docs/copy-and-move-design-rationale.md` records identity, link,
  atomicity, history, authority, and deliberate-limit decisions.
