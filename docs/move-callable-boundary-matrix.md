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
| Request, frozen plan, link evidence, receipt | `memcommit.memory_transfer_application` | Nonempty unique Source set, UID preservation, distinct Target, default RETARGET or explicit BREAK policy, compatible typed BLOCK input, typed complete receipt |
| Complete local graph and Store execution | `memcommit.memory_transfer_runtime` | Strict direct graph freeze, inbound live-Embed classification, full-graph revalidation, Target gap, protection, exception-atomic multi-Context publication |
| CLI | `memcommit.interfaces.cli.memory_transfer` | Positional or repeatable batch, `--from`, `--into/--to`, `--before/--after`, default live-Embed retarget, compatibility `--retarget-links`, explicit `--break-links`, mixed-effect rendering |
| TUI | `memcommit.interfaces.tui.operations.memory_transfer` | Shared MULTIPLE direct-Memory checks, Embed-style `INTO + POSITION`, no redundant normal policy frame, compact editable exact command, frozen-plan handoff without direct publication |
| Public Python | `MemCommitClient.move_memories` | Sequence and mutually exclusive policy validation with operation-specific public errors |
| Agent | `memcommit.interfaces.agent.memory_transfer` | Strict version-1 JSON schema, public-client-only execution, typed JSON receipt, no provider |
| MCP | registry projection | Mechanical projection of the frozen agent schema and handler |
| History | `memcommit.command_history` | Shared Move operation UID plus complete affected membership restore removals, additions, and retargets together |

## Link and authority boundary

RETARGET is the route default and rewrites every inbound ordinary local live
Memory Embed in the same command, but refuses a Target-owned link that would
become a self-reference. BREAK is an explicit advanced opt-in that leaves every
exact old binding unchanged and reports the resulting dangling count. The
typed BLOCK policy remains input-compatible but is not selected by a current
route. Immutable snapshot References never change.

All selected owners, Target, and RETARGET link owners are ordinary local
Contexts. Move binds the complete scanned catalog and every direct record
through publication because absence of another inbound link is part of its
safety claim. Store-level Context, Profile, and Memory protection remains
authoritative.

## Evidence

- `tests/test_memory_transfer_application.py` covers multi-Source Move,
  preserved identity/order, default RETARGET, BREAK, compatible BLOCK,
  self/collision boundaries,
  full-graph drift, no partial publication, and one-unit Undo/Redo.
- `tests/test_memory_transfer_tui.py` covers multi-Memory selection, exact gap
  review, default live-Embed following, cancellation, frozen-plan handoff, and
  the bare CLI route.
- `tests/test_memory_transfer_public_api.py` covers stable Python DTOs and
  operation-specific errors.
- `tests/test_memory_transfer_agent_adapter.py`, agent registry tests, and MCP
  projection tests cover strict machine schemas and the shared route.
- `docs/memory-transfer-design-rationale.md` records identity, link,
  atomicity, history, authority, and deliberate-limit decisions.
