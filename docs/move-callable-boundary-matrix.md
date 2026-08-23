# Move callable boundary matrix

## Decision

Move preserves selected ordinary Memory UIDs and content while atomically
changing their direct local owner. Source removal, Target insertion, and any
explicit live-Embed retargets publish as one multi-Context Undo/Redo command.
Every current CLI, Python, agent, and MCP route enters the same typed
application and Store runtime. There is no current operand-free TUI route.

## Route matrix

| Route or concern | Owner | Verified invariant |
| --- | --- | --- |
| Request, frozen plan, link evidence, receipt | `memcommit.memory_transfer_application` | Nonempty unique Source set, UID preservation, distinct Target, BLOCK/RETARGET/BREAK policy, typed complete receipt |
| Complete local graph and Store execution | `memcommit.memory_transfer_runtime` | Strict direct graph freeze, inbound live-Embed classification, full-graph revalidation, Target gap, protection, exception-atomic multi-Context publication |
| CLI | `memcommit.interfaces.cli.memory_transfer` | Positional or repeatable batch, `--from`, `--into/--to`, `--before/--after`, `--retarget-links/--break-links`, mixed-effect rendering |
| Public Python | `MemCommitClient.move_memories` | Sequence and mutually exclusive policy validation with operation-specific public errors |
| Agent | `memcommit.interfaces.agent.memory_transfer` | Strict version-1 JSON schema, public-client-only execution, typed JSON receipt, no provider |
| MCP | registry projection | Mechanical projection of the frozen agent schema and handler |
| History | `memcommit.command_history` | Shared Move operation UID plus complete affected membership restore removals, additions, and retargets together |

## Link and authority boundary

BLOCK rejects any inbound ordinary local live Memory Embed before mutation.
RETARGET rewrites every such link in the same command but refuses a Target-owned
link that would become a self-reference. BREAK leaves every exact old binding
unchanged and reports the resulting dangling count. Immutable snapshot
References never change.

All selected owners, Target, and RETARGET link owners are ordinary local
Contexts. Move binds the complete scanned catalog and every direct record
through publication because absence of another inbound link is part of its
safety claim. Store-level Context, Profile, and Memory protection remains
authoritative.

## Evidence

- `tests/test_memory_transfer_application.py` covers multi-Source Move,
  preserved identity/order, BLOCK, RETARGET, BREAK, self/collision boundaries,
  full-graph drift, no partial publication, and one-unit Undo/Redo.
- `tests/test_memory_transfer_public_api.py` covers stable Python DTOs and
  operation-specific errors.
- `tests/test_memory_transfer_agent_adapter.py`, agent registry tests, and MCP
  projection tests cover strict machine schemas and the shared route.
- `docs/memory-transfer-design-rationale.md` records identity, link,
  atomicity, history, authority, and deliberate-limit decisions.

