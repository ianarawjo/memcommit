# Memory Reference and Embed semantics

> **Authorization contract updated 2026-08-30.** Permission claims below that use `EMBED`, `DERIVE`, `COMBINE`, `EXPORT`, `ACCEPT_DERIVED`, or `SAVE_*` describe the retired contract preserved for design history. The current contract uses `QUERY`, `CREATE`, `READ`, `UPDATE`, and `DELETE`; `READ` covers readable semantic use and Embed traversal, while `SHARE` remains a separate endpoint capability. See `granted-derived-ownership-design-rationale.md`.

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
| `reference SOURCE -r` | lexical descendants + authorized Embed graph | immutable self-contained snapshot | read-only value retained by Target |
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
local Target. `READ` is that boundary: an exact granted Memory requires an
explicit public owner, while a granted Context requires an explicit public root
and direct or recursive scope. Neither form scans the Profile for an implicit
Source. Query-only routes disclose no Memory content and cannot be retained.

## Context snapshot scope

Context Reference uses the repository-wide scope presets. `--direct/-d`
freezes the selected Context's exact direct record. An embedded Context row is
retained as opaque identity metadata, but its live content is not opened.
`--recursive/-r` freezes the selected Context, every admitted lexical
descendant, and every admitted Context reached through an Embed edge. For an
ordinary Source, admission means local ownership. For an explicit granted
Source, it means `READ` through that exact public Grant namespace, including
effective nested overrides. Those records are retained in one versioned
package and hydrated without consulting live storage.

The package preserves Context and Memory identities, direct order, ordinary
Memory content, immutable Memory snapshots, query-only routing metadata, and
Context placement metadata. A resolved live Memory Embed in the selected scope
becomes retained immutable evidence inside the outer snapshot; a dangling link
remains dangling provenance. Query-only content is not copied. A granted live
edge encountered inside an otherwise local or granted graph remains opaque
unless it belongs to the explicitly selected Reference root's admitted public
scope; a wrapper cannot turn incidental Grant visibility into retention.

Freeze binds every local or authority Context record whose bytes contribute
retained content. A granted freeze also records the public-to-authority
coordinate, attachment, Profiles, resource, effective Grant revision/digest,
and every nested override that can affect scope. Apply reauthorizes all of it,
holds every participating Source Store lock through the local Target
compare-and-set and checkpoint, and publishes the complete package or no item.
The Target must be an ordinary local Context and may not be inside a local
recursive Source scope.

## Nested composition contract

Nesting is defined at two different units. A direct Memory Reference or Memory
Embed is a relationship record, not a second directly owned Memory. Reference
and Embed therefore both reject a `MemoryRef` as the Source of another Memory
relationship before Target publication. Following the pointer implicitly would
flatten away the intermediate relationship UID, its live-versus-snapshot time
contract, and its Source provenance. A caller that wants to retain that
relationship as an item can instead Reference or Embed its containing Context.

Context composition preserves the intermediate topology. Referencing a Context
that contains a Memory or Context snapshot retains the nested typed record,
snapshot bytes, digest, and Source identities without consulting those original
Sources later. Embedding a Context that already embeds another Context retains
both live edges; a later load resolves each edge in order, so changes in the
leaf remain visible without pretending that the outer Context directly owns
the leaf. Recursive Context Reference may freeze a multi-hop local or
explicitly READ-granted Embed graph, including an indirect cycle, but records
each canonical public Context once and hydrates the retained package without
live Store access.

This contract does not introduce an arbitrary nesting-depth or serialized-byte
ceiling. Those resource limits require separately chosen public bounds; the
current invariant is semantic and atomic: typed topology is preserved, cycles
terminate through identity tracking, and a failed direct pointer re-wrap writes
neither a Target item nor a checkpoint.

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
mem embed --from CHILD_CONTEXT [--to TARGET | --into TARGET]
mem embed MEMORY_UID [--into TARGET]
mem embed SOURCE_CONTEXT:MEMORY_UID [--into TARGET]
mem reference SOURCE_CONTEXT --into TARGET --direct
mem reference SOURCE_CONTEXT --into TARGET --recursive
mem reference --from SOURCE_CONTEXT [--to TARGET | --into TARGET] --direct
mem reference --from SOURCE_CONTEXT [--to TARGET | --into TARGET] --recursive
mem reference MEMORY_UID --into TARGET
mem reference SOURCE_CONTEXT:MEMORY_UID --into TARGET
```

When ITEM is omitted, `--from SOURCE_CONTEXT` is the complete Context Source;
when a Memory ITEM is present, it remains the compatibility owner qualifier for
that explicit Memory selector. The Memory form cannot be combined with
`SOURCE_CONTEXT:MEMORY_UID`.
The single `:` is reserved because it has always been invalid in ordinary
Context names; `#` already has a separate view-handle role elsewhere, and `::`
would add punctuation without adding an ambiguity boundary.

A bare UID/prefix scans one strict snapshot of every ordinary local
Context's direct frame. There is deliberately no current-Context preference:
exactly one directly owned ordinary Memory must match across the complete
catalog. Zero matches fail as a Memory lookup; multiple matches fail before
publication and print every canonical `CONTEXT:FULL_UID` candidate. MemoryRef,
Context snapshot, embedded-Context traversal, Grant content, and query-only
content are not owners in this scan. A qualified locator or Memory `--from`
owner searches only its resolved canonical local or authorized public owner,
including relative local spellings such as `../3:UID`.

Because Embed and Reference also accept a Context in the same operand slot,
the storage-independent bare-Memory classification starts at the public
eight-character UUID prefix shape. New Context names already reserve that
shape. For a shorter hexadecimal token, an exact authorized Context wins;
otherwise one unique ordinary-local direct-Memory match selects Memory mode.
Zero matches retain the Context route and multiple matches fail closed.
`CONTEXT:UID` and the compatibility `--from` option remain explicit short-prefix
forms. Interactive and callable routes remain explicitly typed and do not
infer a unit from display text.

For explicit Embed and Reference CLI forms, `--into` and `--to` select the same
Target and duplicate spellings fail before Store access. An omitted Target
means the command-start current Context. The adapter writes that frozen
canonical Target into the typed request;
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

Restoration receipts inspect persisted relationship records after the mutation
without reopening an external authority Store. A `granted_memory_ref` whose
content was deliberately not reauthorized is therefore reported as a
`GRANT · READ ONLY · OPAQUE` live relationship, never as `DANGLING`; only an
actual failed resolution may make an ordinary local live pointer dangling.
Undo and Redo keep their compact relationship counts while Revert exposes this
typed state without printing Grant metadata or Source content.

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

Compare deliberately admits owned content, retained References, local live
Memory Embeds, and Context-level readable forms through one typed projection.
It sends their unmodified content as ordinary peer claims, keeps placement,
source form, Source Memory, owner, and live-versus-snapshot freshness as
host-only provenance, and shows that provenance only in its exact ledger. A
Reference remains bound to retained content; a local live Embed is revalidated
against its external owner and a same-content retarget is still a different
evidence identity. Compare Summary reuses the same projection.

A granted live Memory or Context Embed inside a local Context is intentionally
excluded from that semantic projection for now. The local wrapper cannot erase
the embedded `GrantedMemorySource` or `GrantedContextLink`; each consuming
operation must propagate and authorize that contributor explicitly rather than
mistaking the wrapper for ownership. Query-only rows fail for the corresponding
hidden-content reason. None of this grants Compare or a downstream mutation
operation write-through authority over the Source.

## Callable adapters

The public Python facade exposes `reference_memory`, `reference_context`,
`embed_memory`, and `embed_context` as distinct methods over the same
application/runtime graph. The agent registry exposes tagged
`memory`/`context` Reference and Embed tools; MCP is a mechanical projection of
those frozen schemas. These routes return typed receipts rather than parsing
CLI output.

The no-argument Reference TUI is deliberately narrower than those callable and
explicit CLI surfaces. It collects one existing local `TARGET CONTEXT`, then
one `SOURCE MEMORY` together with its explicitly qualified local or READ-granted
owner. There is no Context/Memory mode selector and no whole-Context row in the
Memory picker. Context-wide direct and recursive snapshots remain available
through explicit typed operands, where scope is visible in the submitted
command instead of being hidden behind the bare launcher.

The Source Memory field accepts an owner Context, a bare UID/prefix resolved
only inside the retained owner, or the common single-colon `CONTEXT:UID`
locator. The separate `BROWSE CONTEXT` and `CHOOSE MEMORY` actions expose those
two layers directly. A list choice writes canonical `CONTEXT:FULL_UID` text
back into the field; a complete direct edit updates both owner and Memory. The
field never performs a bare UID scan across granted or unrelated Contexts, and
the common parser continues to reject `::`.

The exact Memory's owner remains part of its typed endpoint value and visible
row annotation. The shared compact Endpoint Setup returns a process-local
draft; the Reference adapter then freezes the exact Source content, Grant,
Memory, and local Target before Apply. Its editable command is the final focus surface and is titled
`PROPOSED COMMAND · ENTER TO PROCEED` when valid. Enter proceeds directly from
that line; there is no second Run button or action row.

Memory Apply retains the established plain terminal receipt:
`Referenced snapshot [MEMORY] from 'SOURCE' as [REFERENCE] in 'TARGET'.`
The typed durable receipt additionally carries Source and Target UIDs, the
Memory content digest, and the checkpoint UID. The ordered color-PTY record in
`screenshots/reference-compact-exact-memory-20260831/` covers entry, owner,
exact Memory choices, selection, proposed-command approval, the success
receipt, and read-only retained verification.

The no-argument Embed TUI explicitly chooses Context or Memory and prepares
the corresponding frozen plan. Its Memory mode reuses the same direct-Memory
selector as Reference and Edit, including `READ` public rows, then
composes the shared placement/exact-review components; it does not own a second
mutation path.
An explicitly rooted `MemCommitClient` additionally disables live Grant
resolution on its Store instance: Show can report the opaque relationship but
cannot inherit and dereference the host Profile's active Grants. Active-Profile
clients retain the normal reauthorizing read behavior.

## Migration and non-goals

- Do not rewrite existing `memory_ref` records merely to normalize naming.
- Do not prefer the current Context when a bare UID has another local owner;
  ambiguity must remain visible and require `CONTEXT:UID`.
- Do not add write-through mutation to either Embed form.
- Do not make arbitrary documents or Skills importable as a side effect of
  this change.
- Do not infer a granted Memory owner from a bare UID or broaden an explicit
  granted Context root to the whole readable Profile. Granted retention stays
  public-rooted, scope-explicit, and local-Target only.

The focused executable contract lives in
`tests/test_nested_reference_embed_contract.py`. It covers live and snapshot
Memory-pointer re-wrap rejection, nested Context snapshot identity retention,
two-hop live Context Embed, recursive freezing of a two-hop graph, and finite
freezing of an indirect Embed cycle.
