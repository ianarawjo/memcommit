# Translate Application Boundary Matrix

## Reviewed operation

Translate's CLI and historical in-memory compatibility routes now enter one
typed terminal-independent application family. Its current route
classification is `CLOSED`.

| Concern | Current owner | Review conclusion |
| --- | --- | --- |
| Provider prompt, batching, decode, translation plan | `memcommit.operations.translate.runtime` | Operation-owned |
| In-memory translated materialization | `memcommit.operations.translate.runtime` | Operation-owned |
| Same-UID provider/curated projection model | `memcommit.operations.translate.view` | Operation-owned |
| Sidecar load, migration, CAS publication | `memcommit.operations.translate.view_store` | Operation-owned |
| Request validation, targeting, reuse/refresh, provider timing | `memcommit.operations.translate.application` | Operation-owned |
| Catalog seed, curated edit/verify/reset, import/export policy | `memcommit.operations.translate.catalog_application` and `application` | Operation-owned |
| In-place/save-as checkpoints and final CAS | `memcommit.operations.translate.materialization` | Operation-owned |
| ANSI rendering and CLI syntax | `memcommit.commands.translate.command` | Correct adapter concern only where presentation-specific |

## Preserved invariants

- Legacy `memcommit.translate`, `translation_view`, and
  `translation_view_store` paths are identity aliases, not second behavior
  owners.
- Direct Memories are the only provider candidates; References, query-only
  content, and embedded descendants remain opaque.
- Same-UID view publication is CAS-bound and publishes no partial catalog.
- Materialization remains explicit and revalidates the command-start current
  Source before checkpointed graph mutation.
- Contradictory modes fail before Store or provider access, and the application
  alone decides whether an exact saved view makes a provider call unnecessary.
- Import file reading, export file creation, `$EDITOR`, provider progress, and
  Save Location review are injected adapters; their outcomes enter typed
  application validation before semantic or durable use.

## Adapter boundary

The CLI retains argument declarations, safe file/stdin/stdout mechanics,
terminal rendering, progress presentation, editor launch, and require-new
Save Location review. It does not choose catalog provenance, provider reuse,
curation semantics, import validity, checkpoint contents, or Apply ordering.
No agent, MCP, or high-level public client Translate adapter is currently
exposed; the historical `memcommit.ops` calls delegate to the same operation
runtime and do not constitute a second route owner.
