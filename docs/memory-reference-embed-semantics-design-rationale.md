# Memory Reference and Embed semantics

## Motivation

The original `mem reference` stored only a Source Context identity and Memory
identity. Loading the Target resolved the current Source content, so the
operation was a live link even though its public name did not say so. This made
Reference and Context Embed differ mainly by granularity and left no durable
way to retain the exact reviewed wording of an external Memory.

The public model now separates time from granularity:

| Operation | Granularity | Time semantics | Ownership |
| --- | --- | --- | --- |
| `reference UID --from SOURCE` | Memory | immutable Source snapshot | read-only value retained by Target |
| `embed UID --from SOURCE` | Memory | live Source resolution | Source remains owner |
| `embed CHILD` | Context | live Child resolution | Child remains owner |

`add`, Branch, and Import remain distinct. Add creates new literal Memory
content without a Source relationship. Branch creates an independently
editable working copy. Import copies a supported MemCommit resource by value.

## Snapshot Reference contract

A new Reference records:

- its own direct-item UID;
- the canonical Source Context name and UID;
- the Source Memory UID;
- the exact Memory content and its digest at creation;
- enough frozen Source and Target state for one atomic Target publication.

The snapshot is read-only. Later Source edits, deletion, rename, or loss of
authority do not rewrite its retained content. A Source change may be reported
as drift by a later inspection feature, but must never refresh the snapshot
implicitly. Refreshing means creating or explicitly replacing a reviewed
snapshot, not background synchronization.

Snapshot retention is a disclosure boundary. A granted Source therefore needs
an operation-owned permission decision before its content may be copied into a
local Target. The first implementation keeps Reference local-only rather than
inferring retention authority from READ visibility.

## Live Memory Embed contract

Memory Embed retains the existing pointer semantics. The Target stores only
the Source Context and Memory identities; loading the Target resolves the
current Source content. The resolved in-memory object is detached so callers
cannot write through it. If the exact Source identity is unavailable, the link
is dangling rather than silently retaining old content or rebinding by name.

The CLI uses `--from` as its discriminator:

```text
mem embed CHILD_CONTEXT --into TARGET
mem embed MEMORY_UID --from SOURCE_CONTEXT --into TARGET
```

This avoids guessing from string shape. Context names may resemble UIDs, and a
command must not change meaning merely because a later Context or Memory makes
an operand ambiguous. TUI, Python, agent, receipt, and application requests
remain explicitly typed even though the CLI stays compact.

## Compatibility

Existing persisted `memory_ref` records and historical `reference`
checkpoints keep their live-link meaning. They cannot be retroactively treated
as snapshots because they deliberately omitted content. New snapshot records
use a distinct serialized discriminator. Existing live records may be shown as
Memory Embeds at public surfaces without rewriting historical bytes.

The existing Context Embed application contract remains valid. Memory Embed
reuses its placement and exact-Target publication mechanics but owns a
different Source binding and request type. Reference receives its own typed
application/runtime boundary instead of reusing the legacy command's direct
Store mutation.

## Consumer boundary

Every direct-item consumer must distinguish ordinary Memory, snapshot
Reference, live Memory Embed, query-only view, and embedded Context. Read-only
inspection may show snapshot content. Mutation operations must never treat a
snapshot or live embed as a directly owned Memory. Semantic inclusion remains
operation-owned; adding a snapshot type does not silently broaden provider
disclosure or permit semantic Apply to edit it.

Edit may use the displayed Source identity to locate the ordinary owner: an
explicit `CONTEXT#UID` selects that Context, while a bare UID searches other
ordinary local Contexts only after it is absent from the current Context. This
is owner selection, not write-through. Supplying the Reference or Embed's own
direct-item UID still fails as read-only, and ambiguous cross-Context matches
require a qualified owner before any mutation.

Reference and Embed themselves use no semantic cache or provider. Any semantic
consumer that deliberately admits either form must include snapshot
content/digest for Reference or the exact resolved Source binding for live
Embed in its evidence identity. A later cache hit must mean the same visible
evidence even after Source state changes.

## Callable adapters

The public Python facade exposes `reference_memory`, `embed_memory`, and
`embed_context` as distinct methods over the same application/runtime graph.
The agent registry exposes one snapshot-only Reference tool and one tagged
`memory`/`context` Embed tool; MCP is a mechanical projection of those frozen
schemas. These routes return typed receipts rather than parsing CLI output.
The no-argument Embed TUI explicitly chooses Context or Memory and prepares
the corresponding frozen plan. Its Memory mode composes the shared direct
Memory picker and the same placement/exact-review components as Context mode;
it does not own a second mutation path.

## Migration and non-goals

- Do not rewrite existing `memory_ref` records merely to normalize naming.
- Do not infer Memory versus Context Embed from operand shape alone.
- Do not add write-through mutation to either Embed form.
- Do not make arbitrary documents or Skills importable as a side effect of
  this change.
- Do not broaden Reference beyond local ordinary Sources until retention
  authority for granted content is separately specified and tested.
