# Embed application boundary matrix

## Decision

Embed owns live Context and Memory relationships as two typed requests beside
one shared placement contract. Both application contracts are terminal-,
Store-, and provider-independent. Infrastructure and presentation point
inward to those contracts; the application never calls the CLI or TUI.

There is no compatibility facade under `memcommit.commands`. Keeping one would
make the old command package remain the effective public dependency even after
the implementation moved. All repository callers are migrated in the same
change instead.

## Ownership matrix

| Concern | Owner | Invariant |
| --- | --- | --- |
| Context/Memory request, frozen plan, exact gap, durable result | `memcommit.embed_application` | Tagged typed values contain no Typer, prompt-toolkit, Store, or provider dependency. |
| Relative locator snapshot, direct loads, validation, CAS, source lock, checkpoint | `memcommit.embed_runtime` | Source and Into resolve from one current-Context snapshot; apply publishes all or nothing. |
| Argument grammar and plain success/error rendering | `memcommit.interfaces.cli.embed` | `--from` explicitly selects Memory Embed; its absence selects Context Embed. |
| Link-type, Source, target/gap, and exact-command review | `memcommit.interfaces.tui.operations.embed` | Context mode reuses the shared Context selector; Memory mode composes the shared direct-Memory picker; both return a frozen plan without saving a Store themselves. |
| Stable Python projection | `memcommit.api._operations.embed`, `memcommit.api.client` | `embed_memory` and `embed_context` expose different DTOs and never parse terminal text. |
| Agent and MCP projection | `memcommit.interfaces.agent.embed`, registry projection | The versioned `memory`/`context` tag prevents operand-shape inference; MCP mechanically projects the same frozen tool contract. |
| Live relationship mutation | `memcommit.ops` | Domain validation and in-memory insertion stay reusable below the runtime; Memory and Context links remain distinct durable types. |

## Freeze and apply contract

The runtime freezes canonical Source and Into names, both Context UIDs and
record digests, the target item count, and the exact neighboring UIDs around
the chosen gap. Memory Embed additionally freezes the direct Source Memory UID,
content, and content digest. The Context interactive adapter returns its same
`FrozenEmbedPlan`; explicit CLI, Python, and agent routes prepare the matching
typed plan through the same runtime.

Apply reloads both Contexts, verifies identity and digest equality, resolves
the frozen neighbors again, and mutates only after every check succeeds.
Memory Embed also revalidates the frozen direct Memory content. The Store's
target compare-and-set and source binding remain the final locked boundary. A
successful result includes the exact relationship, placement, and checkpoint
UID so Python and agent adapters never parse CLI text.
The checkpoint is also the operation-unit Undo/Redo boundary; restoring a
Memory Embed restores the live identity link, not a copied Source value.

## Compatibility and remaining boundary

Local Embed retains the existing `context_ref` schema. A granted Child uses the
separate `granted_context_ref` schema and explicit `EMBED` authority documented
in `granted-context-embed-design-rationale.md`; the target remains owned and
local. This separation keeps same-Store locators from being mistaken for
cross-Profile authority bindings.

Live Memory Embed retains the legacy `memory_ref` pointer schema and is local
Source/local Target only in this version. It is deliberately separate from
`memory_snapshot_ref`, which belongs to immutable Reference. Existing
`memory_ref` records therefore keep their historical live behavior.

The shared direct-item placement renderer still lives in the older command
component family because it composes the pre-existing Context preview. That is
a presentation dependency only; the application/runtime boundary is already
independent of it. A later component migration can move that renderer without
changing the Embed use case.
