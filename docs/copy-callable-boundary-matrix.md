# Copy callable boundary matrix

## Decision

Copy creates an ordered batch of independent editable ordinary Memories in one
existing local Target while leaving every exact local Source unchanged. Every
current CLI, Python, agent, and MCP route enters the same typed application and
Store runtime. There is no current operand-free TUI route.

## Route matrix

| Route or concern | Owner | Verified invariant |
| --- | --- | --- |
| Request, frozen plan, placement, receipt | `memcommit.memory_transfer_application` | Nonempty unique Source set, exact Target binding, FRESH/PRESERVE policy, output UID uniqueness, typed durable receipt |
| Local locator and Store execution | `memcommit.memory_transfer_runtime` | One command-start current snapshot, strict ordinary-local direct graph, Source binding, Target CAS, write protection, exception-atomic publication |
| CLI | `memcommit.interfaces.cli.memory_transfer` | Positional or repeatable batch, `--from`, `--into/--to`, `--before/--after`, `--preserve-uids`, terminal-safe typed rendering |
| Public Python | `MemCommitClient.copy_memories` | Sequence validation and operation-specific public errors over the same application/runtime |
| Agent | `memcommit.interfaces.agent.memory_transfer` | Strict version-1 JSON schema, public-client-only execution, typed JSON receipt, no provider |
| MCP | registry projection | Mechanical projection of the frozen agent schema and handler |
| History | `memcommit.command_history` | Shared Copy operation UID and complete checkpoint membership form one Undo/Redo unit |

## Authority and effects

Sources and Target must be ordinary local Contexts in the active Store. Copy
binds every selected Source record through the Target commit; only the Target
changes. Store-level Context, Profile, and Memory protection remains
authoritative. Copy does not create a provider, cache entry, saved semantic
session, Reference, Embed, or new Context.

FRESH is the default and creates one new UID per output. PRESERVE is explicit
and fails on any Target direct-item UID collision. Exact duplicate content is
allowed. The complete ordered batch publishes one Target checkpoint or none.

## Evidence

- `tests/test_memory_transfer_application.py` covers ordered fresh Copy,
  preserved identity, collision rejection, placement, Source invariance,
  concurrency rejection, CLI aliases, and validation.
- `tests/test_memory_transfer_public_api.py` covers stable Python DTOs and
  operation-specific errors.
- `tests/test_memory_transfer_agent_adapter.py`, agent registry tests, and MCP
  projection tests cover strict machine schemas and the shared route.
- `docs/memory-transfer-design-rationale.md` records identity, placement,
  authority, history, and intentional non-goals.

