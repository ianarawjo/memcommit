"""Translate provider-plan integration with the core translation catalog."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid

from memcommit.core.context import Context
from memcommit.core.memory_translation import (
    MemoryTranslationCatalog,
    TRANSLATION_CATALOG_CONTRACT_VERSION,
    TRANSLATION_ORIGIN_PROVIDER,
    TranslationCatalogEntry,
    TranslationCatalogError,
    TranslationProviderVariant,
    direct_source_memories,
    order_catalog_entries,
    translation_content_digest,
)
from memcommit.persistence.store import context_record_digest

from .runtime import (
    TranslationPlan,
    TranslationProposal,
    translation_plan_matches_context,
)


def update_catalog_from_translation_plan(
    plan: TranslationPlan,
    context: Context,
    *,
    existing: MemoryTranslationCatalog | None = None,
    created_at: str | None = None,
) -> MemoryTranslationCatalog:
    """Replace provider variants while preserving person-curated variants."""
    if not isinstance(plan, TranslationPlan):
        raise TranslationCatalogError("Translation catalog requires a TranslationPlan.")
    if not isinstance(context, Context) or not translation_plan_matches_context(
        plan,
        context,
    ):
        raise TranslationCatalogError(
            "The translation plan is stale because the Context changed."
        )
    if plan.provider_response_sha256 is None:
        raise TranslationCatalogError(
            "Provider catalog updates require a provider response digest."
        )
    memories = direct_source_memories(context, plan.selected_memory_uid)
    if memories is None or len(memories) != len(plan.proposals):
        raise TranslationCatalogError(
            "The translation plan does not cover its exact source scope."
        )
    if existing is not None:
        if existing.context_uid != context.uid or existing.context_name != context.name:
            raise TranslationCatalogError(
                "The translation catalog does not belong to this Context."
            )
        if existing.target_language != plan.target_language:
            raise TranslationCatalogError(
                "The translation plan target does not match the catalog."
            )
    timestamp = created_at or datetime.now(timezone.utc).isoformat()
    by_uid = (
        {entry.source_uid: entry for entry in existing.entries}
        if existing is not None
        else {}
    )
    for memory, proposal in zip(memories, plan.proposals, strict=True):
        if (
            not isinstance(proposal, TranslationProposal)
            or proposal.source_uid != memory.uid
            or proposal.source_content != memory.content
        ):
            raise TranslationCatalogError(
                "The translation plan does not match its source Memories."
            )
        previous = by_uid.get(memory.uid)
        by_uid[memory.uid] = TranslationCatalogEntry(
            source_uid=memory.uid,
            provider=TranslationProviderVariant(
                source_sha256=translation_content_digest(memory.content),
                context_digest=plan.context_digest,
                translated_content=proposal.translated_content,
                response_sha256=plan.provider_response_sha256,
                generated_at=timestamp,
            ),
            curated=None if previous is None else previous.curated,
        )
    prior_order = (
        tuple(entry.source_uid for entry in existing.entries)
        if existing is not None
        else ()
    )
    return MemoryTranslationCatalog(
        context_uid=plan.context_uid,
        context_name=plan.context_name,
        target_language=plan.target_language,
        created_at=timestamp if existing is None else existing.created_at,
        updated_at=timestamp,
        revision=1 if existing is None else existing.revision + 1,
        contract_version=TRANSLATION_CATALOG_CONTRACT_VERSION,
        entries=order_catalog_entries(context, by_uid, prior_order),
    )


def build_translation_plan_from_catalog(
    catalog: MemoryTranslationCatalog,
    context: Context,
    selector: str | None = None,
) -> TranslationPlan:
    """Build a fresh Apply identity from current effective translations."""
    context_digest = context_record_digest(context)
    if not catalog.covers(context, context_digest, selector):
        raise TranslationCatalogError(
            "The translation catalog has missing or stale translations."
        )
    memories = direct_source_memories(context, selector)
    assert memories is not None
    effective_by_uid = {
        entry.source_uid: entry
        for entry in catalog.effective_entries(
            context,
            context_digest,
            selector,
        )
    }
    effective = tuple(effective_by_uid[memory.uid] for memory in memories)
    provider_digests = {
        item.evidence_sha256
        for item in effective
        if item.origin == TRANSLATION_ORIGIN_PROVIDER
        and item.evidence_sha256 is not None
    }
    # Verification moves provider text into the curated layer. Its historical
    # origin no longer proves one untouched provider batch for Apply evidence.
    provider_only = all(
        item.origin == TRANSLATION_ORIGIN_PROVIDER and not item.curated
        for item in effective
    )
    provider_digest = (
        next(iter(provider_digests))
        if provider_only and len(provider_digests) == 1
        else None
    )
    return TranslationPlan(
        operation_uid=str(uuid.uuid4()),
        context_uid=catalog.context_uid,
        context_name=catalog.context_name,
        context_digest=context_digest,
        target_language=catalog.target_language,
        selected_memory_uid=selector,
        proposals=tuple(
            TranslationProposal(
                source_uid=memory.uid,
                source_content=memory.content,
                translated_content=effective_by_uid[memory.uid].translated_content,
            )
            for memory in memories
        ),
        provider_response_sha256=provider_digest,
    )
