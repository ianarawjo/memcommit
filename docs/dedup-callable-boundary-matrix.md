# Dedup callable boundary matrix

## Reviewed scope

This matrix covers every currently exposed exact-Dedup route. Missing future
TUI or agent adapters are not current routes. Semantic redundancy routes are
reviewed separately under Dedun.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem dedup [CONTEXT]` | shared locator freeze, then `apply_exact_dedup` | short no-op or checkpoint receipt |
| Public Python | `MemCommitClient.dedup(context_name)` | `api._operations.exact_dedup.dedup_exact`, then `apply_exact_dedup` | typed `ExactDedupResult` |

Both routes converge on `memcommit.exact_dedup_application`, which re-exports
the terminal-independent exact grouping and Apply boundary. Neither route
constructs a provider, finding report, TUI, survivor choice, or semantic
receipt.

## Shared behavior evidence

| Case | Required behavior |
| --- | --- |
| exact group | first direct Context-order UID survives; later byte-identical UIDs are removed |
| different stored wording | remains unchanged, including whitespace-only or Unicode differences |
| no group | no checkpoint and a zero-removal result |
| stale Context | digest mismatch fails before mutation |
| inbound reference | the complete operation fails and creates no checkpoint |
| successful mutation | one `exact-dedup-v1` checkpoint; recovery is `mem undo` |

The implementation and tests named in `docs/dedup-design-rationale.md` retain
these invariants. The public Python result and CLI text are projections, not
second application implementations.
