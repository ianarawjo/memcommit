# Dedup callable boundary matrix

## Reviewed scope

This matrix covers every currently exposed provider-free exact-Dedup Apply
route. Missing future TUI or agent adapters are not current routes. Read-only
exact discovery and complete exact-plus-semantic redundancy are reviewed
separately under Find Duplicates, Find Redundancies, and Dedun.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem dedup [CONTEXT] [-d\|-r]` | one `find_duplicates.analyze_exact_duplicate_scope`, then direct or batch `apply_exact_dedup_scope` over that frozen result | short no-op or one atomic command receipt |
| Public Python | `MemCommitClient.dedup(context_name, include_descendants=...)` | `adapters.python_api._operations.dedup.dedup`, then the same scope boundary | typed aggregate `ExactDedupResult` with per-Context effects |

Both routes enter the same read-only analysis owned by
`memcommit.application.operations.quality_resolution.diagnose.find_duplicates.application`, whose pure
role-aware detector remains in `reviewing.direct_item_duplicates`. Dedup then
passes that exact typed result to the Apply-only boundary in
`memcommit.application.operations.quality_resolution.repair.dedup.application`; Apply never rediscovers
the groups. The temporary internal
`memcommit.application.operations.exact_dedup` path is removed without a
facade so the canonical package matches `mem dedup`. Recursive reach enumerates lexical names only,
keeps groups Context-local, and publishes changed records through
`save_context_command_batch` after binding the complete local graph and
namespace. Neither applying route constructs a provider, TUI, survivor choice,
or semantic receipt.

## Shared behavior evidence

| Case | Required behavior |
| --- | --- |
| exact Memory group | first direct Context-order UID survives; later byte-identical Memory UIDs are removed |
| exact Memory Embed group | the complete live Source Context/Memory binding matches; the first occurrence survives |
| exact Memory Reference group | Source identity, snapshot digest, and retained content match; the first occurrence survives |
| exact Context Reference group | Source identity, package, scope, and digest match; the first occurrence survives |
| cross-role equality | never creates a group, even when visible content is identical |
| different stored Memory wording | remains unchanged, including whitespace-only or Unicode differences |
| query-only view | remains outside ordinary Embed/Reference exact cleanup |
| no group | no checkpoint and a zero-removal result |
| stale Context | digest mismatch fails before mutation |
| inbound reference | the complete operation fails and creates no checkpoint |
| successful mutation | one `exact-dedup-v2` checkpoint with typed groups; recovery is `mem undo` |
| recursive grouping | each Context retains an independent earliest UID; equal parent/child content never joins one group |
| recursive freshness | every subtree member, local graph record, and namespace member is frozen before the first write |
| recursive publication | one checkpoint per changed Context, one operation UID, exception rollback, and one command-unit Undo |
| granted boundary | read-only recursive discovery may include readable public descendants; recursive Apply fails before crossing a Grant |

The implementation and tests named in `agent-records/docs/dedup-design-rationale.md` retain
these invariants. The public Python result and CLI text are projections, not
second application implementations.

## Ownership relocation boundary

`memcommit.application.operations.quality_resolution.diagnose.find_duplicates.application` owns the
provider-free exact report and direct-or-lexical analysis. Applying Dedup owns
only mutation validation, receipts, checkpoints, and atomic publication under
`memcommit.application.operations.quality_resolution.repair.dedup.application`. CLI and public Python
compose those owners explicitly in that order.

Semantic redundancy contracts consumed by Dedun and composite operations are
owned separately by `memcommit.application.operations.quality_resolution.repair.dedun.application`,
`.analysis`, and `.runtime`.

This split does not make Find Duplicates and Dedup aliases. Find Duplicates is
read-only and complete after analysis; Dedup consumes that frozen analysis as
Apply intent. A Context UID, complete record digest, lexical membership, or
namespace mismatch fails instead of silently running the detector again.
Authority, inbound-Reference, checkpoint, transaction, and Undo behavior stay
with Dedup.
