# Translate Application Boundary Matrix

## Reviewed operation

Translate has an operation-owned semantic and persistence core, but its only
current CLI route still assembles several application policies inside
`memcommit.commands.translate`. Its route classification is therefore
`MIXED`, not `CLOSED`.

| Concern | Current owner | Review conclusion |
| --- | --- | --- |
| Provider prompt, batching, decode, translation plan | `memcommit.operations.translate.runtime` | Operation-owned |
| In-memory translated materialization | `memcommit.operations.translate.runtime` | Operation-owned |
| Same-UID provider/curated projection model | `memcommit.operations.translate.view` | Operation-owned |
| Sidecar load, migration, CAS publication | `memcommit.operations.translate.view_store` | Operation-owned |
| Catalog seed/reuse/refresh orchestration | `memcommit.commands.translate` | Not yet migrated |
| Manual edit, verify, reset, import/export policy | `memcommit.commands.translate` | Not yet migrated |
| Source targeting, provider selection, save-as/in-place transaction assembly | `memcommit.commands.translate` | Not yet migrated |
| ANSI rendering and CLI syntax | `memcommit.commands.translate` | Correct adapter concern only where presentation-specific |

## Preserved invariants

- Legacy `memcommit.translate`, `translation_view`, and
  `translation_view_store` paths are identity aliases, not second behavior
  owners.
- Direct Memories are the only provider candidates; References, query-only
  content, and embedded descendants remain opaque.
- Same-UID view publication is CAS-bound and publishes no partial catalog.
- Materialization remains explicit and revalidates the command-start current
  Source before checkpointed graph mutation.

## Remaining migration

A terminal-independent Translate application must own one typed request and
result across saved-view open/create, curated mutations, import/export,
provider refresh, and both materialization modes. Until that orchestration is
removed from the command, ownership relocation alone is not route closure.
