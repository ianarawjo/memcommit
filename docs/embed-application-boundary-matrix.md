# Embed application boundary matrix

## Decision

Embed is the first mutable Context-relationship slice rebuilt as one typed
application use case. The application contract is terminal-, Store-, and
provider-independent. Infrastructure and presentation point inward to that
contract; the application never calls the CLI or TUI.

There is no compatibility facade under `memcommit.commands`. Keeping one would
make the old command package remain the effective public dependency even after
the implementation moved. All repository callers are migrated in the same
change instead.

## Ownership matrix

| Concern | Owner | Invariant |
| --- | --- | --- |
| Request, frozen plan, exact gap, durable result | `memcommit.embed_application` | Typed values contain no Typer, prompt-toolkit, Store, or provider dependency. |
| Relative locator snapshot, direct loads, validation, CAS, source lock, checkpoint | `memcommit.embed_runtime` | Child and Into resolve from one current-Context snapshot; apply publishes all or nothing. |
| Argument grammar and plain success/error rendering | `memcommit.interfaces.cli.embed` | Explicit CLI output and exit behavior stay compatible. |
| Context/gap navigation and exact-command review | `memcommit.interfaces.tui.operations.embed` | TUI receives callbacks and a frozen catalog; it does not instantiate or save a Store. |
| Context relationship mutation | `memcommit.ops` | Domain validation and in-memory insertion stay reusable below the runtime. |

## Freeze and apply contract

The runtime freezes canonical Child and Into names, both Context UIDs and
record digests, the target item count, and the exact neighboring UIDs around
the chosen gap. The interactive adapter returns that same `FrozenEmbedPlan`
which the application later applies; it does not translate the reviewed state
back into an unfrozen command.

Apply reloads both Contexts, verifies identity and digest equality, resolves
the frozen neighbors again, and mutates only after every check succeeds. The
Store's target compare-and-set and source binding remain the final locked
boundary. A successful result includes the exact relationship, placement, and
checkpoint UID so future Python and agent adapters do not need to parse CLI
text.

## Compatibility and remaining boundary

This slice deliberately preserves local-only Embed authority and the existing
`context_ref` storage schema. Grant-backed Embed is a separate permission and
schema change, so it follows only after this structural migration passes the
existing CLI, TUI, checkpoint, concurrency, undo, and redo tests.

The shared direct-item placement renderer still lives in the older command
component family because it composes the pre-existing Context preview. That is
a presentation dependency only; the application/runtime boundary is already
independent of it. A later component migration can move that renderer without
changing the Embed use case.
