# Dedup callable boundary matrix

## Reviewed scope

This matrix covers every currently exposed provider-free exact-Dedup Apply
route. Missing future TUI or agent adapters are not current routes. Read-only
exact discovery and complete exact-plus-semantic redundancy are reviewed
separately under Find Duplicates, Find Redundancies, and Dedun.

| Route | Public input | Application entry | Result/effect |
| --- | --- | --- | --- |
| CLI | `mem dedup [CONTEXT] [-d\|-r]` | shared locator/scope freeze, then direct or batch `apply_exact_dedup_scope` | short no-op or one atomic command receipt |
| Public Python | `MemCommitClient.dedup(context_name, include_descendants=...)` | `api._operations.exact_dedup.dedup_exact`, then the same scope boundary | typed aggregate `ExactDedupResult` with per-Context effects |

Both routes converge on the pure role-aware detector in
`memcommit.direct_item_duplicates` and the Apply boundary in
`memcommit.operations.exact_dedup.application`. The former
`memcommit.exact_dedup` and `memcommit.exact_dedup_application` paths are
identity-preserving compatibility aliases for that terminal-independent
grouping and Apply owner. Recursive reach enumerates lexical names only,
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

`memcommit.operations.exact_dedup.application` is the canonical owner of the
provider-free exact discovery, scope, receipt, and Apply implementation shared
by exact Dedup and read-only Find Duplicates. The flat
`memcommit.exact_dedup` and `memcommit.exact_dedup_application` paths remain
module-identity aliases, so either import order, existing monkeypatches, and
serialized globals reach the same implementation. Production consumers import
the operation package directly. Keeping this reviewed implementation together
is intentional for this ownership-only relocation; introducing a new port or
runtime split would change more than its implementation home.

`memcommit.operations.dedup.application` and
`memcommit.operations.dedup.runtime` are the canonical owners of the
historically named reviewed-redundancy contracts that Dedun and composite
operations consume. The flat `memcommit.dedup_application` and
`memcommit.dedup_runtime` paths remain identity-preserving compatibility
aliases, so either import order, existing monkeypatches, and serialized globals
reach the same module objects. Production consumers import the operation
package directly.

This ownership-only relocation does not reclassify exact Dedup, merge it with
Find Duplicates, or absorb Dedun. Provider-free exact-key detection remains a
shared primitive in `direct_item_duplicates`, while exact discovery and Apply
are owned by `operations.exact_dedup`; Dedun's analysis, lexical-scope
publication, command, adapters, and evidence remain separate consumers of the
reviewed redundancy core. No relation, survivor, authority, reference,
checkpoint, transaction, interface, or route-state behavior changes.
