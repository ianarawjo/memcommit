# Reference callable boundary matrix

## Decision

Reference retains one exact direct Source Memory version as an immutable,
self-contained snapshot in a local Target. It is not the live-link operation;
that contract belongs to `mem embed MEMORY --from SOURCE`. Every implemented
Reference route now enters the same typed application/runtime boundary.

## Route and ownership matrix

| Concern or route | Owner | Invariant |
| --- | --- | --- |
| Snapshot request, frozen plan, and durable receipt | `memcommit.reference_application` | Terminal-, Store-, provider-, and adapter-independent typed values. |
| Locator snapshot, direct Source read, content digest, Source lock, Target CAS, checkpoint | `memcommit.reference_runtime` | Source and Target are frozen from one current-Context snapshot and publish atomically. |
| Immutable stored value | `memcommit.context.MemoryRef`, `memcommit.ops.reference_memory` | `memory_snapshot_ref` stores content plus its validated SHA-256 digest and never dereferences the live Source. |
| Explicit CLI | `memcommit.interfaces.cli.reference` | `MEMORY --from SOURCE [--into TARGET]` renders only the typed receipt. |
| Stable Python API | `memcommit.api._operations.reference`, `memcommit.api.client` | `reference_memory` returns `MemoryReferenceResult` and maps failures to the public Reference taxonomy. |
| Agent and MCP | `memcommit.interfaces.agent.reference`, registry projection | The versioned `snapshot` kind is explicit; MCP exposes the exact same schema and result envelope. |
| Read-only inspection | Show/List source projection | Snapshot and live Embed labels differ; snapshot content remains readable after Source change or deletion. |

Reference has no separate interactive TUI route in the reviewed scope. This
is a missing future adapter, not a second application path. Adding one later
must prepare and apply `FrozenReferencePlan` rather than own persistence.

## Freeze, authority, and publication contract

Reference captures the active Context name once, resolves relative Source and
Target locators against that snapshot, and currently accepts only ordinary
local Contexts. Freeze binds Source and Target UIDs and record digests, the
direct Source Memory UID and exact content, and a SHA-256 digest of that
content. Apply reopens and revalidates every binding before creating the
snapshot. The source lock and Target compare-and-set are held through one
checkpoint publication, so drift produces no partial snapshot.

The operation is deterministic. It constructs no provider, reads or writes no
semantic cache or analysis session, and changes only the Target. The snapshot
is read-only as a direct item: it may be removed by an owning mutation, but its
stored content cannot be edited through the live Source.

## Compatibility and deliberate limits

Historical `memory_ref` records remain live links. They are not silently
reinterpreted as snapshots. New Reference results serialize as
`memory_snapshot_ref`; new Memory Embed results continue to serialize as
`memory_ref`. The Source name and identities remain provenance, while the
snapshot content is self-contained and survives Source rename, change, or
deletion.

Version 1 does not reference granted or query-only Source content and does not
silently make snapshots eligible for every semantic operation. Each consumer
continues to own its disclosure and inclusion policy.

## Executable evidence

- `tests/test_reference_application.py` verifies frozen Source/Target drift,
  CLI publication, checkpoint shape, and fixed content after Source change.
- `tests/test_reference_embed_public_api.py` verifies the public snapshot/live
  distinction and operation-specific error projection.
- `tests/test_reference_embed_agent_adapter.py` verifies strict versioned
  machine input, public-client-only calls, tagged semantics, and JSON-safe
  receipts.
- Agent registry and MCP projection tests prove discovery of the same schema;
  domain, Store, merge, branch, and import tests cover round-trip and consumer
  compatibility.
