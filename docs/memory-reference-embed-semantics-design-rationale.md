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
| `reference [SOURCE:]UID` | Memory | immutable Source snapshot | read-only value retained by Target |
| `reference SOURCE -d` | one Context direct frame | immutable Source snapshot | read-only value retained by Target |
| `reference SOURCE -r` | lexical descendants + local Embed graph | immutable self-contained snapshot | read-only value retained by Target |
| `embed [SOURCE:]UID` | Memory | live Source resolution | Source remains owner |
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

## Context snapshot scope

Context Reference uses the repository-wide scope presets. `--direct/-d`
freezes the selected Context's exact direct record. An embedded Context row is
retained as opaque identity metadata, but its live content is not opened.
`--recursive/-r` freezes the selected Context, every lexical descendant, and
every ordinary local Context reached through an Embed edge. Those records are
retained in one versioned package and hydrated without consulting live storage.

The package preserves Context and Memory identities, direct order, ordinary
Memory content, immutable Memory snapshots, query-only routing metadata, and
Context placement metadata. A resolved live Memory Embed in the scope becomes
retained immutable evidence inside the outer snapshot; a dangling link remains
dangling provenance. Query-only content and READ-granted content are not
copied. A granted Context edge remains opaque because visibility does not imply
retention authority.

Freeze binds every local Context record whose bytes contribute retained
content. Apply holds those bindings through the Target compare-and-set and
checkpoint, publishing the complete package or no item. The Target may not be
inside the recursive Source scope, avoiding a Context acting as both immutable
Source and mutation Target in one command.

## Live Memory Embed contract

Memory Embed retains the existing pointer semantics. The Target stores only
the Source Context and Memory identities; loading the Target resolves the
current Source content. The resolved in-memory object is detached so callers
cannot write through it. If the exact Source identity is unavailable, the link
is dangling rather than silently retaining old content or rebinding by name.

The compact CLI supports an owner-qualified Memory locator and an unqualified
unique lookup for both operations:

```text
mem embed CHILD_CONTEXT [--into TARGET]
mem embed MEMORY_UID [--into TARGET]
mem embed SOURCE_CONTEXT:MEMORY_UID [--into TARGET]
mem reference SOURCE_CONTEXT --into TARGET --direct
mem reference SOURCE_CONTEXT --into TARGET --recursive
mem reference MEMORY_UID --into TARGET
mem reference SOURCE_CONTEXT:MEMORY_UID --into TARGET
```

`--from SOURCE_CONTEXT` remains a compatibility spelling for an explicitly
owned Memory selector. It cannot be combined with `SOURCE_CONTEXT:MEMORY_UID`.
The single `:` is reserved because it has always been invalid in ordinary
Context names; `#` already has a separate view-handle role elsewhere, and `::`
would add punctuation without adding an ambiguity boundary.

A bare public UID/prefix scans one strict snapshot of every ordinary local
Context's direct frame. There is deliberately no current-Context preference:
exactly one directly owned ordinary Memory must match across the complete
catalog. Zero matches fail as a Memory lookup; multiple matches fail before
publication and print every canonical `CONTEXT:FULL_UID` candidate. MemoryRef,
Context snapshot, embedded-Context traversal, Grant content, and query-only
content are not owners in this scan. A qualified locator searches only its
resolved canonical owner, including relative spellings such as `../3:UID`.

Because Embed and Reference also accept a Context in the same operand slot,
automatic bare-Memory classification starts at the public eight-character UUID
prefix shape. New Context names already reserve that shape. Shorter Memory
prefixes remain available when their type is explicit through `CONTEXT:UID` or
the compatibility `--from` option. Interactive and callable routes remain
explicitly typed and do not infer a unit from display text.

For explicit Embed CLI forms, omitted `--into` means the command-start current
Context. The adapter writes that frozen canonical Target into the typed request;
the application/runtime contract never resolves a later mutable current value.

This avoids guessing from string shape. Context names may resemble UIDs, and a
command must not change meaning merely because a later Context or Memory makes
an operand ambiguous. TUI, Python, agent, receipt, and application requests
remain explicitly typed even though the CLI stays compact.

## Compatibility

Existing persisted `memory_ref` records and historical `reference`
checkpoints keep their live-link meaning. They cannot be retroactively treated
as snapshots because they deliberately omitted content. New snapshot records
use distinct `memory_snapshot_ref` and `context_snapshot_ref` discriminators.
Existing live records may be shown as Memory or Context Embeds at public
surfaces without rewriting historical bytes.

The existing Context Embed application contract remains valid. Memory Embed
reuses its placement and exact-Target publication mechanics but owns a
different Source binding and request type. Reference receives its own typed
application/runtime boundary instead of reusing the legacy command's direct
Store mutation.

## Consumer boundary

Every direct-item consumer must distinguish ordinary Memory, Memory snapshot
Reference, live Memory Embed, Context snapshot Reference, query-only view, and
embedded Context. Read-only inspection may traverse retained snapshot content.
Mutation operations must never treat a snapshot or live embed as directly
owned writable content. Semantic inclusion remains operation-owned; adding a
snapshot type does not silently broaden provider disclosure or permit semantic
Apply to edit it.

An Edit command may separately resolve the directly owned Source with an
explicit `CONTEXT:UID`, or find one unambiguous matching UID across ordinary
local Context direct frames. That is owner selection, not write-through: the
relationship row remains `READ ONLY`, an immutable Reference is not refreshed,
and a live Embed observes the later Source value only through its normal load.

Reference and Embed themselves use no semantic cache or provider. Any semantic
consumer that deliberately admits either form must include snapshot
content/digest for Reference or the exact resolved Source binding for live
Embed in its evidence identity. A later cache hit must mean the same visible
evidence even after Source state changes.

## Callable adapters

The public Python facade exposes `reference_memory`, `reference_context`,
`embed_memory`, and `embed_context` as distinct methods over the same
application/runtime graph. The agent registry exposes tagged
`memory`/`context` Reference and Embed tools; MCP is a mechanical projection of
those frozen schemas. These routes return typed receipts rather than parsing
CLI output. The no-argument Reference TUI explicitly chooses Context or
Memory. Context mode composes the common Context tree, direct/recursive scope,
Target tree, and exact command review; Memory mode reuses the common direct
Memory selector. Both return a typed frozen plan, and Apply remains in the same
runtime used by explicit CLI and callable adapters.
The no-argument Embed TUI explicitly chooses Context or Memory and prepares
the corresponding frozen plan. Its Memory mode reuses the same direct-Memory
selector as Reference and Edit, then composes the shared placement/exact-review
components; it does not own a second mutation path.

## Migration and non-goals

- Do not rewrite existing `memory_ref` records merely to normalize naming.
- Do not prefer the current Context when a bare UID has another local owner;
  ambiguity must remain visible and require `CONTEXT:UID`.
- Do not add write-through mutation to either Embed form.
- Do not make arbitrary documents or Skills importable as a side effect of
  this change.
- Do not broaden Reference beyond local ordinary Sources until retention
  authority for granted content is separately specified and tested.
