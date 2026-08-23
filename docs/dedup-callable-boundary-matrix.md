# Dedup callable boundary matrix

## Reviewed scope

This matrix covers every currently exposed provider-free exact-Dedup Apply
route. Missing future TUI or agent adapters are not current routes. Read-only
exact discovery and complete exact-plus-semantic redundancy are reviewed
separately under Find Duplicates, Find Redundancies, and Dedun.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem dedup [CONTEXT]` | shared locator freeze, then `apply_exact_dedup` | short no-op or checkpoint receipt |
| Public Python | `MemCommitClient.dedup(context_name)` | `api._operations.exact_dedup.dedup_exact`, then `apply_exact_dedup` | typed `ExactDedupResult` |

Both routes converge on the pure role-aware detector in
`memcommit.direct_item_duplicates` and the Apply boundary in
`memcommit.exact_dedup`; the compatibility
`memcommit.exact_dedup_application` module re-exports its terminal-independent
grouping and Apply boundary. Neither applying route constructs a provider,
TUI, survivor choice, or semantic receipt.

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

The implementation and tests named in `docs/dedup-design-rationale.md` retain
these invariants. The public Python result and CLI text are projections, not
second application implementations.
