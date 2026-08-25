# Reference callable boundary matrix

## Decision

Reference retains one exact direct local or READ-granted Source Memory version,
or one local direct/recursive Context scope, as an immutable, self-contained
snapshot in a local Target. Grant support is deliberately Memory-exact; whole
granted Context retention remains outside this version. Reference is not the
live-link operation; that contract belongs to Embed. Every implemented
Reference route enters the same typed application/runtime boundary.

## Route and ownership matrix

| Concern or route | Owner | Invariant |
| --- | --- | --- |
| Snapshot requests, frozen plans, and durable receipts | `memcommit.operations.reference.application` | Memory and Context units are explicitly typed independently of terminal, Store, provider, and adapter state. |
| Locator snapshot, Source package, authority binding, content digest, Source locks, Target CAS, checkpoint | `memcommit.operations.reference.runtime` | Every contributing local Context or exact Grant/authority Memory binding and the Target are frozen from one current-name snapshot and publish atomically. |
| Immutable stored values | `memcommit.context.MemoryRef`, `memcommit.context_snapshot.ContextSnapshotRef`, `memcommit.ops` | `memory_snapshot_ref` stores one Memory; `context_snapshot_ref` stores a validated versioned Context package. Neither dereferences live storage after publication. |
| CLI composition | `memcommit.interfaces.cli.reference` | `CONTEXT:UID` explicitly names one local or public Grant Memory owner; a bare UID/prefix searches ordinary-local direct owners only. With no ITEM, `--from` names a local Context Source; with a Memory ITEM, it remains an explicit local-or-public owner qualifier. `--into` and `--to` are equivalent Target spellings and duplicates fail before Store access. Other operands are local Context locators and `-d/-r` controls their scope. |
| Interactive setup | `memcommit.interfaces.tui.operations.reference` | Explicit Context/Memory unit -> unit-owned Source control -> Context scope when applicable -> local Target -> reviewed exact command; Memory mode admits authorized public Sources while Context mode remains local, and the TUI owns no persistence. |
| Stable Python API | `memcommit.api._operations.reference`, `memcommit.api.client` | `reference_memory` and `reference_context` return unit-specific typed receipts and share the public Reference error taxonomy; only an active-Profile client may consult Grants, while an explicitly rooted client remains local-only. |
| Agent and MCP | `memcommit.interfaces.agent.reference`, registry projection | Version 2 is a strict tagged `memory`/`context` union; MCP exposes the same schema and result envelope. |
| Read-only inspection | Show/List source projection | Snapshot and live Embed labels differ; snapshot content remains readable after Source change or deletion. |

The focused `memcommit.operations.reference` package is the canonical owner of
the durable Memory and Context Reference use case. Production API, CLI, and TUI
adapters import its application and runtime modules directly. The previous
flat `memcommit.reference_application` and `memcommit.reference_runtime` paths
remain module-identity aliases, not parallel implementations. This preserves
legacy import order, monkeypatch targets, and serialized Python globals while
making new code discover the implementation through the operation package.

Query Reference remains a Query-owned read boundary under
`memcommit.operations.query`. It selects concealed Source material for one
answer and publishes no durable snapshot, so sharing the word “reference” does
not make it part of this package. Conversely, Memory and Context Reference stay
together here because both freeze retained immutable bytes and publish one
local Target checkpoint under the same authority and CAS lifecycle.

This relocation intentionally changes no request, Grant permission, snapshot
schema, Source or Target validation, transaction, checkpoint receipt, route
classification, or visible terminal state. Existing ordered TUI captures
therefore remain valid and are not regenerated for this ownership-only move.

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

The shared direct-Memory resolver searches ordinary local direct records. A
qualified locator or Memory `--from` owner may resolve one exact authorized
public Grant frame; the operation does not enumerate Grant content to guess an
owner from a UID. A bare locator scans one strict complete ordinary-local
snapshot and requires exactly one match, with no current-Context preference.
Ambiguity fails before Target loading and prints every canonical
`CONTEXT:FULL_UID` candidate. The interactive picker may display authorized
Grant rows, but every selected row becomes an owner-qualified request.
MemoryRef, Context snapshots, embedded traversal, and query-only content never
become implicit owners.

## Freeze, authority, and publication contract

Reference captures the active Context name once and resolves relative Source
and Target locators against that snapshot. Memory Freeze binds one direct local
or granted Memory; Context Freeze remains local and binds the root and every
local record contributing bytes to the direct or recursive package. Recursive
means lexical descendants plus ordinary local Embed edges; query-only and
granted content reached incidentally through that graph remain opaque.

Retaining an exact granted Memory requires the complete
`READ + DERIVE + EXPORT + SAVE_ANALYSIS` set. The frozen binding includes
public/authority names, authority and grantee Profiles, attachment, resource,
Grant UID and revision, Source Context/Memory UIDs, and content digest. Apply
holds the registry and authority Source locks through one local Target
checkpoint publication, so revocation, permission or Source drift, and Target
drift produce no partial snapshot.
That checkpoint is the operation-unit Undo/Redo boundary: Undo removes only
the Target snapshot, and Redo restores the same retained bytes and identity.
Restoration presentation classifies both snapshot and live records as Memory
references and renders only their pointer identity; it must not fall back to
printing the snapshot record because that record contains the retained bytes.

The operation is deterministic. It constructs no provider, reads or writes no
semantic cache or analysis session, and changes only the local Target. The
snapshot is read-only as a direct item: it may be removed by an owning
mutation, but its stored content cannot be edited through the live Source. A
successful granted snapshot is a retained export and therefore remains
readable after later Grant revision or revocation; the creation-time binding
stays as immutable provenance rather than a live authorization dependency.

## Nested composition boundary

A Memory snapshot or live Memory Embed is a relationship record, not a directly
owned Source Memory. Memory-level Reference and Embed therefore reject either
relationship as another Memory relationship Source, preserving the
intermediate UID, time semantics, and provenance instead of flattening a
pointer-to-pointer chain. The containing Context is the supported composition
unit: a Context Reference may retain nested snapshot records as typed values,
and recursive Context Reference may freeze a local multi-hop Embed graph while
recording each canonical Context once. A granted live edge remains opaque
unless the exact operation separately authorizes retention; Embed authority
cannot be laundered into Reference authority.

## Compatibility and deliberate limits

Historical `memory_ref` and `context_ref` records remain live links. They are
not silently reinterpreted as snapshots. New Reference results serialize as
`memory_snapshot_ref` or `context_snapshot_ref`; Embed continues to serialize
live pointer forms. Source names and identities remain historical provenance,
while retained content survives Source rename, change, or deletion.

Version 2 references only an exact direct granted Memory after the explicit
retention permission check above. Whole granted Context scopes and query-only
Source content remain unsupported, and a retained snapshot is not silently
eligible for every semantic operation. Each consumer continues to own its
disclosure and inclusion policy.

## Executable evidence

- `tests/test_reference_application.py` verifies frozen Source/Target drift,
  qualified and globally unique Memory locators, ambiguity diagnostics,
  compatibility and interactive CLI entry, checkpoint and Undo/Redo behavior,
  and fixed content after Source change.
- `tests/test_granted_reference.py` verifies permission intersection, exact Grant and
  authority binding, revocation before and after publication, immutable
  provenance retention, public/API/agent error parity, and no-partial failure.
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
- `tests/test_granted_reference_tui.py` verifies the granted-Memory/local-role
  split, complete retention permission filter, local-only fallback, and frozen
  public owner. Its ordered 180×52 color PTY flow is recorded under
  `docs/screenshots/granted-memory-reference-20260823/`.
- `tests/test_reference_embed_public_api.py` verifies the public snapshot/live
  distinction and operation-specific error projection.
- `tests/test_reference_embed_agent_adapter.py` verifies strict versioned
  machine input, public-client-only calls, tagged semantics, and JSON-safe
  receipts.
- Agent registry and MCP projection tests prove discovery of the same schema;
  domain, Store, merge, branch, and import tests cover round-trip and consumer
  compatibility.
