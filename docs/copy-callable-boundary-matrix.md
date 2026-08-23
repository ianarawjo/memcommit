# Copy callable boundary matrix

## Decision

Copy creates an ordered batch of independent editable ordinary Memories in one
existing local Target while leaving every exact local Source unchanged. Every
current CLI, TUI, Python, agent, and MCP route enters the same typed application
and Store runtime.

## Route matrix

| Route or concern | Owner | Verified invariant |
| --- | --- | --- |
| Request, frozen plan, placement, receipt | `memcommit.memory_transfer_application` | Nonempty unique Source set, exact Target binding, store-wide fresh output UID uniqueness, typed durable receipt |
| Local locator and Store execution | `memcommit.memory_transfer_runtime` | One command-start current snapshot, strict ordinary-local direct graph, Source binding, Target CAS, write protection, exception-atomic publication |
| CLI | `memcommit.interfaces.cli.memory_transfer` | Positional or repeatable batch, `--from`, `--into/--to`, `--before/--after`, terminal-safe typed rendering; the removed `--preserve-uids` spelling is rejected |
| TUI | `memcommit.interfaces.tui.operations.memory_transfer` | Shared MULTIPLE direct-Memory checks, Embed-style `INTO + POSITION`, compact editable exact command, frozen-plan handoff without a redundant identity frame or direct publication |
| Public Python | `MemCommitClient.copy_memories` | Sequence validation and operation-specific public errors over the same application/runtime |
| Agent | `memcommit.interfaces.agent.memory_transfer` | Strict version-2 JSON schema with no identity-policy input or output, public-client-only execution, typed JSON receipt, no provider |
| MCP | registry projection | Mechanical projection of the frozen agent schema and handler |
| History | `memcommit.command_history` | Shared Copy operation UID and complete checkpoint membership form one Undo/Redo unit |

## Authority and effects

Sources and Target must be ordinary local Contexts in the active Store. Copy
binds every selected Source record through the Target commit; only the Target
changes. Store-level Context, Profile, and Memory protection remains
authoritative. Copy does not create a provider, cache entry, saved semantic
session, Reference, Embed, or new Context.

Copy always creates one store-wide fresh UID per output. It has no
identity-preservation policy: independently editable copies must not imply
live synchronization or branch continuity merely by sharing an identifier.
Exact duplicate content is allowed. The complete ordered batch publishes one
Target checkpoint or none.

## Evidence

- `tests/test_memory_transfer_application.py` covers ordered fresh Copy,
  rejection of the removed identity flag, placement, Source invariance,
  concurrency rejection, CLI aliases, and validation.
- `tests/test_memory_transfer_tui.py` covers multi-Memory checks, exact gap
  staging, editable-command parsing, cancellation, frozen-plan handoff, and
  the bare CLI route.
- `tests/test_memory_transfer_public_api.py` covers stable Python DTOs and
  operation-specific errors.
- `tests/test_memory_transfer_agent_adapter.py`, agent registry tests, and MCP
  projection tests cover strict machine schemas and the shared route.
- `docs/memory-transfer-design-rationale.md` records identity, placement,
  authority, history, and intentional non-goals.
