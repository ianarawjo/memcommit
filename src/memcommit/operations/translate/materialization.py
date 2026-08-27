"""Checkpointed in-place and require-new materialization for Translate."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.operations.translate.runtime import (
    AppliedTranslation,
    TranslateError,
    TranslationPlan,
    apply_translation,
    derive_translation_context,
    translation_plan_matches_context,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class TranslationMaterializationResult:
    """Exact destination and Source-to-result mappings published by Apply."""

    plan: TranslationPlan
    destination: Context
    translations: tuple[AppliedTranslation, ...]
    created_context: bool


def apply_translation_materialization(
    store: MemoryStore,
    plan: TranslationPlan,
    *,
    destination_name: str | None,
) -> TranslationMaterializationResult:
    """Publish one prepared provider-backed plan with final source/current CAS."""

    operation_uid = plan.operation_uid
    if not isinstance(operation_uid, str) or not operation_uid:
        raise TranslateError("Materialization identity was not allocated.")
    if store.current_context_name() != plan.context_name:
        raise TranslateError(
            "The current Context changed while translations were being "
            "prepared; no translations were added."
        )
    source = store.load_direct(plan.context_name)
    if destination_name is None:
        result = apply_translation(source, plan)
        store.save(
            source,
            AutoCheckpoint(
                command="translate",
                args=result.checkpoint_args(),
                description=(
                    f"Added {len(result.translations)} "
                    + (
                        "translation"
                        if len(result.translations) == 1
                        else "translations"
                    )
                    + f" to {plan.target_language}"
                ),
            ),
            expected_context_digest=plan.context_digest,
        )
        return TranslationMaterializationResult(
            plan=plan,
            destination=source,
            translations=result.translations,
            created_context=False,
        )

    result = derive_translation_context(source, plan, destination_name)
    created = False
    try:
        store.create_context_with_sources(
            result.baseline,
            AutoCheckpoint(
                command="init",
                args={
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
                        for item in result.baseline.iter_items()
                        if isinstance(item, Memory)
                    ],
                },
                description=(
                    f"Initialized '{destination_name}' from "
                    f"'{plan.context_name}' before translation "
                    f"[{operation_uid[:8]}]"
                ),
            ),
            source_bindings=(
                (
                    plan.context_name,
                    plan.context_uid,
                    plan.context_digest,
                ),
            ),
        )
        created = True
        # The final frame was built from this exact baseline. Carry its just-
        # persisted digest so a concurrent destination writer cannot be lost.
        result.context._store_digest = result.baseline._store_digest
        store.save(
            result.context,
            AutoCheckpoint(
                command="translate",
                args=result.checkpoint_args(),
                description=(
                    f"Replaced {len(result.translations)} source "
                    + (
                        "Memory"
                        if len(result.translations) == 1
                        else "Memories"
                    )
                    + f" with translations to {plan.target_language}"
                ),
            ),
            expected_context_digest=result.baseline._store_digest,
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
            expected_context_digest=result.context._store_digest or "",
        )
    except Exception as error:
        if created:
            # Once published, another process may have switched to or referenced
            # the destination. Deleting it could create a dangling pointer.
            raise TranslateError(
                f"Translation failed ({error}); destination "
                f"'{destination_name}' was preserved for manual inspection "
                "and the source was not changed."
            ) from error
        raise
    return TranslationMaterializationResult(
        plan=plan,
        destination=result.context,
        translations=result.translations,
        created_context=True,
    )
