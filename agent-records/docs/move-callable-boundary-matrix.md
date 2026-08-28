# Move callable boundary matrix

## Decision

Move preserves selected ordinary Memory UIDs and content while atomically
changing their direct local owner. Source removal, Target insertion, and any
live-Embed retargets publish as one multi-Context Undo/Redo command. Every
current CLI, TUI, Python, agent, and MCP route enters the same typed application
and Store runtime.

## Route matrix

| Route or concern | Owner | Verified invariant |
| --- | --- | --- |
| Request, frozen plan, link evidence, receipt | `memcommit.application.operations.memory_transfer.application` | Nonempty unique Source set, UID preservation, distinct Target, default RETARGET or explicit BREAK policy, compatible typed BLOCK input, typed complete receipt |
| Complete local graph and Store execution | `memcommit.application.operations.memory_transfer.runtime` | Strict direct graph freeze, inbound live-Embed classification, full-graph revalidation, Target gap, protection, exception-atomic multi-Context publication |
| Console command | `memcommit.adapters.console.commands.move` | Move alone owns its Typer grammar, local-owner setup, application handoff, cancellation, errors, default live-Embed retarget, compatibility `--retarget-links`, explicit `--break-links`, and mixed-effect receipt |
| Shared console mechanics | `memcommit.adapters.console.coordination.memory_transfer` | Move supplies its local catalogs and freeze callback to the common MULTIPLE direct-Memory, `INTO + POSITION`, editable exact-command, and placement-receipt mechanics; the workbench performs no direct publication |
| Public Python | `MemCommitClient.move_memories` | Sequence and mutually exclusive policy validation with operation-specific public errors |
| Agent | `memcommit.adapters.agent.memory_transfer` | Strict version-2 JSON schema, public-client-only execution, typed JSON receipt, no provider |
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
- `agent-records/docs/memory-transfer-design-rationale.md` records identity, link,
  atomicity, history, authority, and deliberate-limit decisions.
