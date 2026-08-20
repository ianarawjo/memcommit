# Find Redundancies callable boundary matrix

## Reviewed scope

Find Redundancies is the public read-only semantic-redundancy operation. It
freezes one readable direct-Memory frame, obtains and validates semantic
redundancy evidence, and projects a report without modifying any Source.
Dedun reuses this analysis but owns a separate confirmed-evidence, survivor,
and Apply boundary.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem find-redundancies [--context CONTEXT]` | shared quality-finder source freeze and `ops.find_redundancies` | one-shot report or process-local TTY review; no Apply handoff |
| Hidden CLI alias | `mem find-duplicates [--context CONTEXT]` | exact same callback as the canonical CLI command | identical read-only behavior under the canonical report identity |
| Public Python | `MemCommitClient.find_redundancies(...)` | `api._operations.quality_find.find_quality(..., "duplicates")` | typed redundancy findings; no mutation |
| Agent/MCP | `memcommit_quality_find(kind=redundancies)` | the same public Python route | JSON-safe evidence; no mutation |

The compatibility Python `ops.find_duplicates` name delegates to
`ops.find_redundancies`. Internal report types retain `DuplicateReport` and the
provider task retains `find_duplicates` for schema and evaluation-fixture
compatibility; those names do not change the public operation identity.

## Shared behavior evidence

Every current route:

- freezes every selected directly owned Memory exactly once and preserves its
  public Context owner in evidence;
- excludes embedded Context traversal and provider-invisible partial output;
- applies readable-catalog and cross-authority `DERIVE`/`COMBINE` checks before
  provider connection;
- excludes byte-identical `EXACT` content, which belongs to provider-free
  Dedup;
- validates the complete typed report before publication;
- leaves Contexts, Memories, checkpoints, global current Context, and durable
  review state unchanged; and
- treats TTY reviewer responses as process-local notes only.

The CLI adapter supplies no duplicate handoff handler. The Dedun adapter calls
the same analyzer with operation identity `dedun` and is the only adapter that
supplies the confirmed-evidence handoff. This explicit dependency is the safety
boundary that prevents a read-only Find invocation from gaining survivor or
Apply behavior merely because it shares a result model.

## Limits

Find Redundancies reports only directly owned Memories in the frozen readable
frame. It does not remove exact duplicates, synthesize canonical wording,
migrate inbound references, atomize partial overlaps, persist reviewer notes,
or apply a cross-Context consolidation. Those effects remain owned by Dedup,
Atomize, transformation operations, or Dedun's separately reviewed Apply.
