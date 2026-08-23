# Reference callable boundary matrix

## Decision

Reference retains one exact direct Source Memory version or one direct/
recursive Context scope as an immutable, self-contained snapshot in a local
Target. It is not the live-link operation; that contract belongs to Embed.
Every implemented Reference route enters the same typed application/runtime
boundary.

## Route and ownership matrix

| Concern or route | Owner | Invariant |
| --- | --- | --- |
| Snapshot requests, frozen plans, and durable receipts | `memcommit.reference_application` | Memory and Context units are explicitly typed independently of terminal, Store, provider, and adapter state. |
| Locator snapshot, Source package, content digest, Source locks, Target CAS, checkpoint | `memcommit.reference_runtime` | Every contributing local Context binding and the Target are frozen from one current-name snapshot and publish atomically. |
| Immutable stored values | `memcommit.context.MemoryRef`, `memcommit.context_snapshot.ContextSnapshotRef`, `memcommit.ops` | `memory_snapshot_ref` stores one Memory; `context_snapshot_ref` stores a validated versioned Context package. Neither dereferences live storage after publication. |
| CLI composition | `memcommit.interfaces.cli.reference` | `CONTEXT:UID` explicitly names one Memory owner; a bare public UID/prefix selects Memory mode and must have exactly one ordinary local direct owner. With no ITEM, `--from` names a Context Source; with a Memory ITEM, it remains the owner qualifier. `--into` and `--to` are equivalent Target spellings and duplicates fail before Store access. Other operands are Context locators and `-d/-r` controls their scope. |
| Interactive setup | `memcommit.interfaces.tui.operations.reference` | Explicit Context/Memory unit -> unit-owned Source control -> Context scope when applicable -> Target -> reviewed exact command; the TUI owns no persistence. |
| Stable Python API | `memcommit.api._operations.reference`, `memcommit.api.client` | `reference_memory` and `reference_context` return unit-specific typed receipts and share the public Reference error taxonomy. |
| Agent and MCP | `memcommit.interfaces.agent.reference`, registry projection | Version 2 is a strict tagged `memory`/`context` union; MCP exposes the same schema and result envelope. |
| Read-only inspection | Show/List source projection | Snapshot and live Embed labels differ; snapshot content remains readable after Source change or deletion. |

Bare Reference enters interactive setup only in a terminal. Outside a terminal,
`SOURCE_CONTEXT [-d|-r]` selects Context mode and
`[SOURCE_CONTEXT:]MEMORY_SELECTOR` selects Memory mode. A bare Memory selector
with the public eight-or-more-character UUID-prefix shape is typed without
storage. A shorter hexadecimal prefix preserves an exact local Context name
first, then selects Memory mode only when the complete ordinary-local catalog
has one unique match. Explicit owner syntax and `--from` continue to accept
short prefixes directly. An omitted ITEM plus `--from SOURCE_CONTEXT` selects
Context mode instead, so the same explicit endpoint vocabulary works without
changing the established Memory form.

The shared direct-Memory resolver searches only ordinary local direct records.
A qualified locator resolves its owner against the command-start current
Context and searches only that frame. A bare locator scans one strict complete
local snapshot and requires exactly one match, with no current-Context
preference. Ambiguity fails before Target loading and prints every canonical
`CONTEXT:FULL_UID` candidate. MemoryRef, Context snapshots, embedded traversal,
Grant content, and query-only content never become implicit owners.

## Freeze, authority, and publication contract

Reference captures the active Context name once, resolves relative Source and
Target locators against that snapshot, and currently accepts only ordinary
local Sources. Memory Freeze binds one direct Memory. Context Freeze binds the
root and every local record contributing bytes to the direct or recursive
package. Recursive means lexical descendants plus ordinary local Embed edges;
query-only and granted content remain opaque. Apply revalidates every binding
under Source locks through one Target checkpoint publication, so drift
produces no partial snapshot.
That checkpoint is the operation-unit Undo/Redo boundary: Undo removes only
the Target snapshot, and Redo restores the same retained bytes and identity.
Restoration presentation classifies both snapshot and live records as Memory
references and renders only their pointer identity; it must not fall back to
printing the snapshot record because that record contains the retained bytes.

The operation is deterministic. It constructs no provider, reads or writes no
semantic cache or analysis session, and changes only the Target. The snapshot
is read-only as a direct item: it may be removed by an owning mutation, but its
stored content cannot be edited through the live Source.

## Compatibility and deliberate limits

Historical `memory_ref` and `context_ref` records remain live links. They are
not silently reinterpreted as snapshots. New Reference results serialize as
`memory_snapshot_ref` or `context_snapshot_ref`; Embed continues to serialize
live pointer forms. Source names and identities remain historical provenance,
while retained content survives Source rename, change, or deletion.

Version 2 does not reference granted or query-only Source content and does not
silently make snapshots eligible for every semantic operation. Each consumer
continues to own its disclosure and inclusion policy.

## Executable evidence

- `tests/test_reference_application.py` verifies frozen Source/Target drift,
  qualified and globally unique Memory locators, ambiguity diagnostics,
  compatibility and interactive CLI entry, checkpoint and Undo/Redo behavior,
  and fixed content after Source change.
- `tests/test_context_reference_application.py` verifies direct and recursive
  scope, lexical and Embed retention, Source deletion survival, Context/Memory
  CLI discrimination, Target-inside-scope rejection, and Source drift.
- `tests/test_direct_memory_action_tuis.py` verifies exact Memory/Target choice
  and cancellation before freeze. Ordered real-color PTY evidence for the
  Context/Memory unit choice, direct/recursive scope, exact Apply, Source
  deletion survival, and self-reference rejection lives under
  `docs/screenshots/reference-context-memory-20260820/`; the shared direct
  Memory selector remains covered under
  `docs/screenshots/direct-memory-selector-actions-20260820/`.
- `tests/test_reference_embed_public_api.py` verifies the public snapshot/live
  distinction and operation-specific error projection.
- `tests/test_reference_embed_agent_adapter.py` verifies strict versioned
  machine input, public-client-only calls, tagged semantics, and JSON-safe
  receipts.
- Agent registry and MCP projection tests prove discovery of the same schema;
  domain, Store, merge, branch, and import tests cover round-trip and consumer
  compatibility.
