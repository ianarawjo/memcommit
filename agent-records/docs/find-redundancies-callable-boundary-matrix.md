# Find Redundancies callable boundary matrix

## Reviewed scope

Find Redundancies is the public read-only complete-DUN operation. Its direct
route freezes one readable direct-item frame, while recursive reach freezes a
readable lexical subtree as independent direct-item frames. Each frame
determines same-role exact groups and conservative direct-Memory surface
relations locally, obtains and
validates semantic Memory redundancy evidence for the remaining
representatives, and projects the combined typed report without modifying any
Source. Dedun reuses this analysis but owns the separate deterministic-survivor
and Apply boundary.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem find-redundancies [CONTEXT] [-d\| -r]` or `--context CONTEXT` | exact root or readable lexical source freeze and per-Context `ops.find_redundancies` | immediate complete report in TTY and non-TTY environments; no initial selector, review workbench, or Apply handoff |
| Public Python | `MemCommitClient.find_redundancies(..., include_descendants=...)` | `api._operations.quality_find.find_quality(..., "duplicates")` | aggregate typed result plus per-Context results; no mutation |
| Agent | `memcommit_quality_find(kind=redundancies, include_descendants=...)` | the same public Python route | JSON-safe aggregate and conditional per-Context evidence; no mutation |

`ops.find_duplicates` now owns the separate provider-free exact-DUP report.
The complete-DUN report type retains `DuplicateReport` and the provider task
retains `find_duplicates` for schema and evaluation-fixture compatibility;
those internal names do not collapse the two public operation identities.

## Shared behavior evidence

Every current route:

- freezes every directly owned Memory in each selected readable Context exactly
  once and preserves its public Context owner in evidence;
- excludes embedded Context traversal and provider-invisible partial output;
- applies readable-catalog and per-frame `DERIVE` checks before provider
  connection; recursive siblings are not combined and do not require
  cross-domain `COMBINE` merely because they share a command scope;
- includes typed `EXACT`, `SURFACE_EQUIVALENT`, and
  `SEMANTIC_EQUIVALENT` evidence in one complete DUN forest;
- includes role-aware exact Embed and Reference groups in each direct frame
  without disclosing them to the semantic provider;
- never compares different item roles, and keeps provider inference limited to
  directly owned Memories;
- validates the complete typed report before publication;
- leaves Contexts, Memories, checkpoints, global current Context, and durable
  review state unchanged.

The CLI adapter supplies no Apply behavior. The Dedun adapter calls the same
analyzer with operation identity `dedun`, accepts the eligible evidence from
its newly frozen direct frame, and alone enters the survivor and Apply
boundary. This explicit dependency prevents a read-only Find invocation from
gaining mutation behavior merely because it shares a result model.

The CLI intentionally has no `--select` path. Exact Duplicate and complete-DUN
Redundancy are report commands whose invocation is already sufficient read-only
intent; introducing a target setup would make TTY execution differ from pipes
and would misrepresent the immediate report boundary. Recursive breadth is one
root's readable lexical subtree and keeps every Context independent; the
existing public multi-Context direct call remains one deliberately combined
semantic frame for compatibility.

The core report retains exact, semantic, and complete connected-group counts.
Human-facing projections keep those layers visibly typed rather than reducing
an exact-only frame to a false clean result. They present the exact equation
`DUN evidence links = DUP / EXACT links + semantic-DUN links` and report
connected cleanup groups separately, because exact and semantic edges may
join the same component.

## Limits

Find Redundancies reports same-role exact groups from each frozen direct-item
frame and semantic relations only among Memories directly owned by that same
Context. Recursive reach does not imply atomic mutation; it is read-only.
It does not remove redundancy, synthesize canonical wording, migrate inbound
references, compare roles, deduplicate query-only views, atomize partial
overlaps, persist reviewer notes, or apply a cross-Context consolidation.
Those effects remain owned by Dedup, Atomize, transformation operations, or
Dedun's separate Apply boundary.
