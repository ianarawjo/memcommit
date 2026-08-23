# Find Redundancies callable boundary matrix

## Reviewed scope

Find Redundancies is the public read-only complete-DUN operation. Its direct
CLI freezes one readable direct-item frame, determines same-role exact groups
and conservative direct-Memory surface relations locally, obtains and
validates semantic Memory redundancy evidence for the remaining
representatives, and projects the combined typed report without modifying any
Source. Dedun reuses this analysis but owns the separate deterministic-survivor
and Apply boundary.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem find-redundancies [CONTEXT]` or `--context CONTEXT` | exact one-Context source freeze and `ops.find_redundancies` | immediate one-shot report in TTY and non-TTY environments; no initial selector, review workbench, or Apply handoff |
| Public Python | `MemCommitClient.find_redundancies(...)` | `api._operations.quality_find.find_quality(..., "duplicates")` | typed redundancy findings; no mutation |
| Agent/MCP | `memcommit_quality_find(kind=redundancies)` | the same public Python route | JSON-safe evidence; no mutation |

`ops.find_duplicates` now owns the separate provider-free exact-DUP report.
The complete-DUN report type retains `DuplicateReport` and the provider task
retains `find_duplicates` for schema and evaluation-fixture compatibility;
those internal names do not collapse the two public operation identities.

## Shared behavior evidence

Every current route:

- freezes every directly owned Memory in one exact readable Context exactly
  once and preserves its public Context owner in evidence;
- excludes embedded Context traversal and provider-invisible partial output;
- applies readable-catalog and cross-authority `DERIVE`/`COMBINE` checks before
  provider connection;
- includes typed `EXACT`, `SURFACE_EQUIVALENT`, and
  `SEMANTIC_EQUIVALENT` evidence in one complete DUN forest;
- includes role-aware exact Embed and Reference groups in the one-Context CLI
  frame without disclosing them to the semantic provider;
- never compares different item roles, and keeps provider inference limited to
  directly owned Memories;
- validates the complete typed report before publication;
- leaves Contexts, Memories, checkpoints, global current Context, and durable
  review state unchanged.

The CLI adapter supplies no Apply behavior. The Dedun adapter calls the same
analyzer with operation identity `dedun`, accepts the eligible evidence from
its newly frozen frame, and alone enters the survivor and Apply boundary. This
explicit dependency prevents a read-only Find invocation from gaining mutation
behavior merely because it shares a result model.

The CLI intentionally has no `--select` path. Exact Duplicate and complete-DUN
Redundancy are report commands whose invocation is already sufficient read-only
intent; introducing a target setup would make TTY execution differ from pipes
and would misrepresent the one-exact-Context analysis boundary. Broader
multi-Context judgment remains available only to operations whose public
contract declares it.

The core report retains exact, semantic, and complete connected-group counts.
Human-facing projections keep those layers visibly typed rather than reducing
an exact-only frame to a false clean result. They present the exact equation
`DUN evidence links = DUP / EXACT links + semantic-DUN links` and report
connected cleanup groups separately, because exact and semantic edges may
join the same component.

## Limits

Find Redundancies reports same-role exact groups from the frozen one-Context
direct-item frame and semantic relations only among directly owned Memories.
It does not remove redundancy, synthesize canonical wording, migrate inbound
references, compare roles, deduplicate query-only views, atomize partial
overlaps, persist reviewer notes, or apply a cross-Context consolidation.
Those effects remain owned by Dedup, Atomize, transformation operations, or
Dedun's separate Apply boundary.
