# Copy callable boundary matrix

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

## Decision

Copy creates an ordered batch of independent editable ordinary Memories in one
existing local Target while leaving every exact local or READ-granted Source
unchanged. A granted Source is an export-and-retention boundary, not merely a
readable locator. Every current CLI, TUI, Python, agent, and MCP route enters
the same typed application and Store runtime.

## Route matrix

| Route or concern | Owner | Verified invariant |
| --- | --- | --- |
| Copy application | `memcommit.application.operations.copy.application` | Copy alone owns preparation, application ordering, fresh-output validation, and receipt validation |
| Shared values and Store kernel | `memcommit.application.operations.copy_and_move` | Typed Source/Target/placement values plus one command-start current snapshot, exact direct Source binding, Grant and authority-Source revalidation, Target CAS, write protection, and exception-atomic publication |
| Console command | `memcommit.adapters.console.commands.copy` | Copy alone owns its Typer grammar, Grant-aware setup, application handoff, cancellation, errors, and fresh-UID receipt; a granted Memory requires an explicit public owner and the removed `--preserve-uids` spelling is rejected |
| Shared console mechanics | `memcommit.adapters.console.coordination.copy_and_move` | Copy supplies its authority-specific catalogs and freeze callback to the common MULTIPLE direct-Memory, `INTO + POSITION`, editable exact-command, and placement-receipt mechanics; the workbench performs no direct publication |
| Public Python | `MemCommitClient.copy_memories` | Sequence validation and operation-specific public errors over the same application/runtime; active-Profile clients may use explicit Grants while explicitly rooted clients remain local-only |
| Agent | `memcommit.adapters.agent.copy_and_move` | Strict version-2 JSON schema accepts the same local or public Grant Source names without exposing a second authority policy input; public-client-only execution, typed JSON receipt, no provider |
| History | `memcommit.command_history` | Shared Copy operation UID and complete checkpoint membership form one Undo/Redo unit |

## Authority and effects

The Target must be an ordinary local Context in the active Store. A Source may
be an ordinary local direct Memory or an exact direct Memory exposed through a
READ Grant. A granted Source additionally requires the complete
`READ + DERIVE + EXPORT + SAVE_ANALYSIS` set; when one batch combines more than
one ownership or provenance domain, every granted contributor also requires
`COMBINE`. Visibility or `EXPORT` alone never authorizes the retained local
value.

Copy binds every selected local record or exact Grant/authority record through
the Target commit; only the Target changes. The registry and authority Source
locks remain held through local Target compare-and-set, so revocation,
permission drift, Source replacement, Source-content drift, or Target drift
publishes neither a partial batch nor a checkpoint. Store-level Context,
Profile, and Memory protection remains authoritative. Copy does not create a
provider, cache entry, saved semantic session, Reference, Embed, or new
Context.

Copy always creates one store-wide fresh UID per output. It has no
identity-preservation policy: independently editable copies must not imply
live synchronization or branch continuity merely by sharing an identifier.
Exact duplicate content is allowed. The complete ordered batch publishes one
Target checkpoint or none. Its typed provenance maps each output UID to the
local Source binding or to the public name, authority/grantee Profiles, Grant
UID and revision, resource, Source Context/Memory UIDs, and reviewed content
digest. It does not cache a second copy of Source text in authority metadata.
Once publication succeeds, the new ordinary local Memory is independently
editable and survives later Grant revision or revocation; only creating the
retained value required live authority.

## Evidence

- `tests/test_memory_transfer_application.py` covers ordered fresh Copy,
  rejection of the removed identity flag, placement, Source invariance,
  concurrency rejection, CLI aliases, and validation.
- `tests/test_granted_memory_transfer.py` covers the complete permission intersection,
  multi-domain `COMBINE`, frozen Grant and Source drift, retained provenance,
  revocation after publication, and no-partial Target publication.
- `tests/test_memory_transfer_tui.py` covers multi-Memory checks, exact gap
  staging, editable-command parsing, cancellation, frozen-plan handoff, and
  the bare CLI route. The ordered 180×52 color PTY path from granted Source
  selection through retained local verification is recorded under
  `agent-records/docs/screenshots/granted-copy-memory-transfer-20260823/`.
- `tests/test_memory_transfer_public_api.py` covers stable Python DTOs and
  operation-specific errors.
- `tests/test_memory_transfer_agent_adapter.py`, agent registry tests, and MCP
  projection tests cover strict machine schemas and the shared route.
- `agent-records/docs/copy-and-move-design-rationale.md` records identity, placement,
  authority, history, and intentional non-goals.
