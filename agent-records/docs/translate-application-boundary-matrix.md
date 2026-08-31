# Translate Application Boundary Matrix

## Reviewed operation

Translate's CLI enters one typed terminal-independent application family over
a Core catalog model and a Persistence repository. Its current route
classification is `CLOSED`.

| Concern | Current owner | Review conclusion |
| --- | --- | --- |
| Provider prompt, batching, decode, translation plan | `memcommit.application.operations.translation.translate.runtime` | Operation-owned |
| Pure in-memory translated Context transformations | `memcommit.application.operations.translation.translate.runtime` | Application-owned operation behavior |
| Same-UID provider/curated catalog meaning and invariants | `memcommit.core.memory_translation.catalog` | Core concept, independent of Translate commands and storage |
| Durable catalog record codec | `memcommit.persistence.store.translation_catalog.record_format` | Persistence-owned representation |
| Catalog paths, locks, source revalidation, and CAS publication | `memcommit.persistence.store.translation_catalog.repository` | Persistence-owned storage mechanics |
| Request validation, targeting, reuse/refresh, provider timing | `memcommit.application.operations.translation.translate.application` | Operation-owned |
| Provider plan/catalog conversion | `memcommit.application.operations.translation.translate.provider_catalog` | Operation-owned |
| Catalog seed and curated edit/verify/reset workflow | `memcommit.application.operations.translation.translate.curate_translations` and `application` | Operation-owned |
| Import/export document policy | `memcommit.application.operations.translation.translate.exchange_translations` | Operation-owned |
| Add translations to current Context | `memcommit.application.operations.translation.translate.add_translations_to_current_context` | Operation-owned Context action |
| Create translated Context | `memcommit.application.operations.translation.translate.create_translated_context` | Operation-owned Context action |
| ANSI rendering and CLI syntax | `memcommit.adapters.console.commands.translation.translate.command` | Correct adapter concern only where presentation-specific |

## Preserved invariants

- The removed pre-release scoped-view schema has no compatibility or migration
  route; one authoritative catalog model and record schema remain.
- Direct Memories are the only provider candidates; References, query-only
  content, and embedded descendants remain opaque.
- Same-UID catalog publication is CAS-bound and publishes no partial catalog.
- Context Apply remains explicit and revalidates the command-start current
  Source before checkpointed graph mutation.
- Contradictory modes fail before Store or provider access, and the application
  alone decides whether an exact saved catalog makes a provider call unnecessary.
- Import file reading, export file creation, `$EDITOR`, provider progress, and
  Save Location review are injected adapters; their outcomes enter typed
  application validation before semantic or durable use.

## Adapter boundary

The CLI retains argument declarations, safe file/stdin/stdout mechanics,
terminal rendering, progress presentation, editor launch, and require-new
Save Location review. It does not choose catalog provenance, provider reuse,
curation semantics, import validity, checkpoint contents, or Apply ordering.
No agent, MCP, or high-level public client Translate adapter is currently
exposed; the historical `memcommit.application.capabilities.ops` calls delegate to the same operation
runtime and do not constitute a second route owner.

The filesystem directory remains physically named `translation-views` only to
avoid combining this ownership refactor with a study-fixture layout rewrite.
That path is a persistence detail; no Python model, use case, or compatibility
API retains the old `TranslationView` concept.
