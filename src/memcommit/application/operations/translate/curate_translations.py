"""Load and publish person-curated Memory translation catalog changes."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.core.context import Context
from memcommit.core.memory_translation import MemoryTranslationCatalog
from memcommit.persistence.store import MemoryStore, context_record_digest
from memcommit.persistence.store.translation_catalog import (
    load_translation_catalog,
    save_translation_catalog,
    translation_catalog_record_digest,
)


@dataclass(frozen=True)
class TranslationCatalogSeed:
    """Current catalog plus its exact compare-and-swap expectation."""

    catalog: MemoryTranslationCatalog
    logical_digest: str | None
    expected_record_digest: str | None
    requires_save: bool


def load_translation_catalog_seed(
    context: Context,
    target_language: str,
) -> TranslationCatalogSeed:
    """Load and prune one catalog without publishing the candidate."""
    existing = load_translation_catalog(context.uid, target_language)
    if existing is None:
        return TranslationCatalogSeed(
            catalog=MemoryTranslationCatalog.empty(context, target_language),
            logical_digest=None,
            expected_record_digest=None,
            requires_save=False,
        )
    if existing.context_name != context.name:
        raise ValueError("Saved translation catalog does not match its source Context.")
    logical_digest = translation_catalog_record_digest(existing)
    pruned = existing.without_removed_sources(context)
    return TranslationCatalogSeed(
        catalog=pruned,
        logical_digest=logical_digest,
        expected_record_digest=logical_digest,
        requires_save=pruned != existing,
    )


def save_curated_translation_catalog(
    *,
    store: MemoryStore,
    context: Context,
    catalog: MemoryTranslationCatalog,
    seed: TranslationCatalogSeed,
    source_digests: dict[str, str],
) -> None:
    """Publish one curated candidate against its source and catalog seed."""
    save_translation_catalog(
        store,
        catalog,
        expected_record_digest=seed.expected_record_digest,
        expected_context_digest=(
            context_record_digest(context) if seed.requires_save else None
        ),
        required_source_digests=source_digests,
    )
