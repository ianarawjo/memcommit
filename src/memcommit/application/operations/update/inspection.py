"""Inspect retained Update publication evidence without mutation."""

from __future__ import annotations


from dataclasses import dataclass, replace
from typing import Literal

from memcommit.application.capabilities.context_scope_loading import (
    load_context_and_descendants,
)
from memcommit.application.operations.update.model import (
    UpdateReceipt,
    inline_update_source,
    update_inputs_match,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class UpdateInspection:
    """Read-only freshness status of one completed Update."""

    status: Literal["current", "stale"]
    detail: str = ""


def inspect_update(
    active_store: MemoryStore,
    receipt: UpdateReceipt,
) -> UpdateInspection:
    """Revalidate retained inputs against local content and owner membership."""

    inputs = receipt.inputs
    try:
        inline_source = inline_update_source(inputs)
        if inline_source is not None:
            source_contexts = (inline_source,)
        else:
            source_contexts = (
                (active_store.load_direct(inputs.source_name),)
                if inputs.instruction is not None
                else (
                    load_context_and_descendants(active_store, inputs.source_name)
                    if inputs.source_include_descendants
                    else (active_store.load(inputs.source_name),)
                )
            )
        target_contexts = (
            load_context_and_descendants(active_store, inputs.target_name)
            if inputs.target_include_descendants
            else (active_store.load(inputs.target_name),)
        )
        after_inputs = replace(
            inputs,
            target_digest=receipt.application.target_digest,
            target_contexts=receipt.application.target_contexts,
            target_memory_uid=None,
        )
        fresh = update_inputs_match(after_inputs, source_contexts, target_contexts)
        return UpdateInspection("current" if fresh else "stale")
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        return UpdateInspection("stale", str(error))


__all__ = [
    "UpdateInspection",
    "inspect_update",
]
