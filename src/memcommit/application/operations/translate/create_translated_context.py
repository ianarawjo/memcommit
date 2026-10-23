"""Checkpointed creation and selection of a translated derived Context."""

from __future__ import annotations


from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.memory import Memory
from memcommit.persistence.store import MemoryStore

from .context_translation_result import ContextTranslationResult
from .runtime import (
    TranslateError,
    TranslationPlan,
    derive_translation_context,
    translation_plan_matches_context,
)


def create_translated_context(
    store: MemoryStore,
    plan: TranslationPlan,
    destination_name: str,
) -> ContextTranslationResult:
    """Create one translated Context and select it after final Source CAS."""
    operation_uid = plan.operation_uid
    if not isinstance(operation_uid, str) or not operation_uid:
        raise TranslateError("Translation Apply identity was not allocated.")
    if store.current_context_name() != plan.context_name:
        raise TranslateError(
            "The current Context changed while translations were being "
            "prepared; no translated Context was created."
        )
    source = store.load_direct(plan.context_name)
    result = derive_translation_context(source, plan, destination_name)
    created = False
    try:
        store.create_context_with_sources(
            result.baseline,
            AutoCheckpointRequest(
                command="init",
                command_details={
                    "name": destination_name,
                    "source_context": {
                        "uid": plan.context_uid,
                        "name": plan.context_name,
                        "digest": plan.context_digest,
                    },
                    "operation_uid": operation_uid,
                    "target_language": plan.target_language,
                    "memory_uids": [
                        item.uid
                        for item in result.baseline.iter_memories()
                        if isinstance(item, Memory)
                    ],
                },
            ),
            source_bindings=(
                (
                    plan.context_name,
                    plan.context_uid,
                ),
            ),
        )
        created = True
        # Carry the just-persisted baseline digest so a concurrent destination
        # writer cannot be lost between create and replacement.
        store.save(
            result.context,
            AutoCheckpointRequest(
                command="translate",
                command_details=result.checkpoint_command_details(),
            ),
        )
        latest_source = store.load_direct(plan.context_name)
        if not translation_plan_matches_context(plan, latest_source):
            raise TranslateError(
                "The source Context changed while the translated Context was "
                "being created; the destination was not selected."
            )
        if store.current_context_name() != plan.context_name:
            raise TranslateError(
                "The current Context changed while the translated Context was "
                "being created; the destination was not selected."
            )
        store.set_current_context_if(
            plan.context_name,
            destination_name,
            expected_context_uid=result.context.uid,
        )
    except Exception as error:
        if created:
            # A published destination may already have been observed by a caller.
            # A late reporting failure must not silently delete durable data.
            raise TranslateError(
                f"Translation failed ({error}); destination "
                f"'{destination_name}' was preserved for manual inspection "
                "and the source was not changed."
            ) from error
        raise
    return ContextTranslationResult(
        plan=plan,
        destination=result.context,
        translations=result.translations,
        created_context=True,
    )
