# Embed application boundary matrix

## Decision

Embed owns live Context and Memory relationships as two typed requests beside
one shared placement contract. Both application contracts are terminal-,
Store-, and provider-independent. Infrastructure and presentation point
inward to those contracts; the application never calls the CLI or TUI.

The console-specific adapters are co-located under
`memcommit.adapters.console.commands.embed`: `command.py` owns argument grammar
and orchestration, `receipt.py` owns successful human-readable output, and the
`workbench` package owns interactive setup and exact-command review. The former
CLI and operation-specific TUI interface paths are removed without facades so
the command package is the sole console owner. This is an ownership relocation;
request, review, application, and visible terminal behavior remain unchanged.

## Ownership matrix

| Concern | Owner | Invariant |
| --- | --- | --- |
| Context/Memory request, frozen plan, exact gap, durable result | `memcommit.application.operations.embed.application` | Tagged typed values contain no Typer, prompt-toolkit, Store, or provider dependency. |
| Relative locator snapshot, authority binding, direct loads, validation, CAS, source lock, checkpoint | `memcommit.application.operations.embed.runtime` | Local or granted Source and local Into resolve from one current-Context snapshot; Grant and Source reauthorization stays held through all-or-nothing local publication. |
| Argument grammar and orchestration | `memcommit.adapters.console.commands.embed.command` | `CONTEXT:UID` explicitly names one local or READ+EMBED-granted Memory owner; a bare UID/prefix searches ordinary-local direct owners only. With no ITEM, `--from` names a Context Source; with a Memory ITEM, it remains an explicit local-or-public owner qualifier. `--to` is a compatibility alias for canonical `--into`; supplying both is rejected before loading or mutation instead of allowing last-option-wins behavior. Omitted `--into`/`--to` binds the command-start current Context and is copied into the typed request before planning. |
| Successful human-readable output | `memcommit.adapters.console.commands.embed.receipt` | Context and Memory receipts preserve the established relationship identity, Source/target names, and exact gap description. |
| Link-type, Source, target/gap, and exact-command review | `memcommit.adapters.console.commands.embed.workbench` | Context mode reuses the readable Context selector; Memory mode composes the readable direct-Memory picker; the Into catalog remains ordinary-local, both modes return a frozen plan without saving a Store themselves, and the shared editor fixes `mem embed` outside its writable argument buffer. |
| Stable Python projection | `memcommit.adapters.python_api._operations.embed`, `memcommit.adapters.python_api.client` | `embed_memory` and `embed_context` expose different DTOs and never parse terminal text; only an active-Profile client may consult Grants, while an explicitly rooted client remains local-only. |
| Agent and MCP projection | `memcommit.adapters.interfaces.agent.embed`, registry projection | The versioned `memory`/`context` tag prevents operand-shape inference; MCP mechanically projects the same frozen tool contract. |
| Live relationship mutation | `memcommit.application.ops` | Domain validation and in-memory insertion stay reusable below the runtime; Memory and Context links remain distinct durable types. |

The focused `memcommit.application.operations.embed` package is the canonical owner of the
live Context and Memory relationship use case. Production API, CLI, and TUI
adapters import its application and runtime modules directly. The former flat
`memcommit.embed_application` and `memcommit.embed_runtime` paths remain
only in the historical record and are no longer importable. Internal imports,
monkeypatches, and serialized Python globals must name the canonical operation
modules; the durable Embed schema remains unchanged.

Context and Memory Embed stay together because both authorize and publish a
revocable live relationship at one frozen direct-item gap. Immutable Memory
and Context snapshots remain owned by `memcommit.application.operations.reference`; the
shared Source vocabulary and placement presentation do not merge their
authority, durability, or checkpoint meaning.

This relocation intentionally changes no request, Grant permission, live-link
schema, placement, source lock, target CAS, checkpoint receipt, route
classification, or visible terminal state. Existing ordered TUI captures
therefore remain valid and are not regenerated for this ownership-only move.

## Freeze and apply contract

The runtime freezes canonical public and authority Source names when relevant,
the local Into name, Context UIDs and record digests, the target item count, and
the exact neighboring UIDs around the chosen gap. Memory Embed additionally
freezes the direct Source Memory UID, content, and content digest. A granted
Source freezes its authority/grantee Profiles, attachment, resource, Grant UID
and revision, and requires current `READ + EMBED`. The Context interactive
adapter returns its same `FrozenEmbedPlan`; explicit CLI, Python, and agent
routes prepare the matching typed plan through the same runtime.
For the CLI convenience form, the adapter captures current state once and
copies that canonical name into the request when `--into` is omitted. The
application and callable contracts therefore continue to receive an explicit
Target and do not consult mutable global current state during planning.

Before constructing a Memory request, the CLI resolves the shared direct-Memory
locator. A qualified `CONTEXT:UID` or Memory `--from` owner searches only that
canonical local or authorized public direct frame. A bare UID searches one
strict complete snapshot of ordinary-local direct frames, without preferring
the current Context, and succeeds only for one match. The TUI may display
READ+EMBED-granted Memory rows, but a selected public row is serialized with an
explicit owner. An ambiguous local result lists every canonical
`CONTEXT:FULL_UID` candidate and mutates nothing. MemoryRef, snapshots,
embedded bodies, and query-only routes do not enter that ownership catalog.

Apply reloads both Contexts, verifies identity and digest equality, resolves
the frozen neighbors again, and mutates only after every check succeeds.
Memory Embed also revalidates the frozen direct Memory content. Granted Embed
holds registry and authority Source locks through the local target
compare-and-set. Revocation, permission removal, resource replacement, Source
drift, or Target drift publishes neither a relationship nor a checkpoint. A
successful result includes the exact relationship, placement, and checkpoint
UID so Python and agent adapters never parse CLI text.
The checkpoint is also the operation-unit Undo/Redo boundary; restoring a
Memory Embed restores the live identity link, not a copied Source value.

## Compatibility and remaining boundary

Local Embed retains the existing `context_ref` and `memory_ref` schemas. A
granted Child uses `granted_context_ref`; a granted direct Memory uses
`granted_memory_ref`. Both store relationship and authority identity only,
never Source content, and require explicit `READ + EMBED` as documented in
`granted-context-embed-design-rationale.md`; the target remains owned and
local. This separation keeps same-Store locators from being mistaken for
cross-Profile authority bindings.

Live local Memory Embed retains the legacy `memory_ref` pointer schema. A
`granted_memory_ref` reauthorizes the exact Grant, Context, and Memory binding
on every traversal; revision changes may survive only while all identities and
`READ + EMBED` remain effective. It is deliberately separate from
`memory_snapshot_ref`, which belongs to immutable Reference. Existing
`memory_ref` records therefore keep their historical live behavior.

## Composition and laundering boundaries

A Memory Reference, local Memory Embed, or granted Memory Embed is a
relationship record rather than another directly owned Memory. Memory-level
Reference and Embed reject those records as a new relationship Source before
publication, so pointer-to-pointer construction cannot erase the intermediate
UID, time contract, or provenance. Context-level composition remains valid:
an embedded Context may itself contain nested snapshot or Embed relationships,
and each live local or granted edge is traversed with its own identity and
authorization check.

`EMBED` authorizes a revocable live relationship; it never authorizes retained
Copy or Reference. A later operation must resolve the underlying granted
Source and independently obtain its export-and-retention permissions. If a
persisted granted Embed root is revoked or stale, resolved live load fails as a
whole. A narrower effective nested override that lacks `READ + EMBED` is
excluded from the otherwise valid projection instead of inheriting its
parent's permission; direct storage still retains every opaque pointer for
explicit repair or removal. A retained Context Reference deliberately keeps a
granted live edge opaque instead of freezing its bytes under EMBED authority.

Nor may a semantic operation treat the local containing Context as the owner
of a granted Memory or Context edge. The shared semantic-disclosure preflight
used by Compare/Meld, Search, Update, Summarize, and Sever rejects such an edge
before provider connection until it can propagate the exact Grant contributor
and authorize its derived-work capabilities; ordinary recursive read/List/Show
remains allowed. An explicitly rooted public client uses a Store-local
no-Grant-resolution policy, so it can inspect the opaque pointer without
consulting or inheriting the host process's Profile Grants.
The fail-closed semantic rule still applies when the live edge's current Grant
also lists `DERIVE` or `COMBINE`: those flags are not a substitute for carrying
the exact contributor into provider disclosure, result provenance, and later
revalidation. A direct granted root remains supported when the operation owns
that complete authority path.
Search, ordinary Query, and Summarize additionally suppress marker-free
attached-READ catalog projections when loading local provider roots. Those
projections remain available to read-only browsing, while semantic use
requires selecting the granted public name through its operation-aware catalog
binding.

Two public Grant aliases for the same authority Context share one underlying
Context UID. Until the direct-item model has alias-distinct relationship UIDs,
attempting to place both in one Target fails before mutation and reports the
existing and requested aliases; it must never let the second alias silently
replace the first.

## Executable evidence

- `tests/test_granted_embed.py` covers content-free granted Context
  relationships and their Undo/Redo behavior;
  `tests/test_granted_memory_embed_runtime.py` covers exact granted Memory
  relationships, `READ + EMBED`, revision and revocation, deletion/drift,
  local-only Targets, adapter parity, and laundering rejection;
  `tests/test_granted_embed_alias_identity.py` covers same-UID alias rejection
  without partial publication. The ordered 180×52 color PTY path for a granted
  direct-Memory live link is recorded under
  `agent-records/docs/screenshots/granted-memory-embed-20260823/`.
- `tests/test_nested_reference_embed_contract.py` covers Memory relationship
  re-wrap rejection, nested Context Reference values, two-hop live Embed,
  recursive freezing, and cycle termination.
- The grant-composition acceptance matrix proves that Embed-only authority
  cannot be laundered into retained Copy or Reference, while an independently
  authorized retained result remains available after revocation and a live
  Embed fails closed.

The shared direct-item placement renderer lives at
`memcommit.adapters.interfaces.tui.components.direct_item_placement`; the old command
path is only a module-identity compatibility alias. That presentation
dependency remains outside the application/runtime boundary and does not
change the Embed use case.
