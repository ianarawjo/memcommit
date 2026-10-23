"""Checkpointed addition of translated Memories to the current Context."""

from __future__ import annotations

from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store import MemoryStore

from .context_translation_result import ContextTranslationResult
from .runtime import TranslateError, TranslationPlan, apply_translation


def add_translations_to_current_context(
    store: MemoryStore,
    plan: TranslationPlan,
) -> ContextTranslationResult:
    """Publish translated siblings into the exact current source Context."""
    operation_uid = plan.operation_uid
    if not isinstance(operation_uid, str) or not operation_uid:
        raise TranslateError("Translation Apply identity was not allocated.")
    if store.current_context_name() != plan.context_name:
        raise TranslateError(
            "The current Context changed while translations were being "
            "prepared; no translations were added."
        )
    source = store.load_direct(plan.context_name)
    result = apply_translation(source, plan)
    store.save(
        source,
        AutoCheckpointRequest(
            command="translate",
            command_details=result.checkpoint_command_details(),
        ),
    )
    return ContextTranslationResult(
        plan=plan,
        destination=source,
        translations=result.translations,
        created_context=False,
    )
