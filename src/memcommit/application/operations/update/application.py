"""Apply exact Update plans to detached Target state without persistence."""

from __future__ import annotations


from memcommit.application.operations.update.model import (
    AddOperation,
    UpdatedContext,
    EditOperation,
    RemoveOperation,
    UpdateError,
    UpdatePlan,
    UpdateResult,
)
from memcommit.models.context import Context
from memcommit.models.memory import Memory


class UpdateApplicationError(UpdateError):
    """An exact Update plan cannot be applied to the supplied Target graph."""


def _create_working_copy(context: Context) -> Context:
    working_copy = Context.from_dict(context.to_dict())
    # A later publication boundary may use this immutable load token for CAS.
    return working_copy


def apply_update_to_working_contexts(
    plan: UpdatePlan, target_contexts: tuple[Context, ...]
) -> UpdateResult:
    """Apply a prepared plan to working copies of its unchanged Target.

    Internal planning/composition establishes typed effects, exact owner
    identities and writable Memory targets. Callers supply the matching
    baseline and revalidate frozen state before publication. New Memory UID
    collisions are checked here; neither success nor failure mutates the supplied
    Contexts.
    """

    root_context = target_contexts[0]
    operations_by_context_uid: dict[
        str,
        list[EditOperation | AddOperation | RemoveOperation],
    ] = {context.uid: [] for context in target_contexts}
    for operation in plan.operations:
        operations_by_context_uid[operation.owner_context_uid].append(operation)

    updated_contexts: list[UpdatedContext] = []
    for context in target_contexts:
        context_operations = operations_by_context_uid[context.uid]
        if not context_operations:
            continue
        working_copy = _create_working_copy(context)
        for operation in context_operations:
            if isinstance(operation, EditOperation):
                working_copy.replace_memory(
                    Memory(uid=operation.memory_uid, content=operation.new_content)
                )
            elif isinstance(operation, RemoveOperation):
                working_copy.remove(operation.memory_uid)
            else:
                # Removing an item must not free its UID for a later addition.
                if (
                    operation.memory_uid in context.memories
                    or operation.memory_uid in working_copy.memories
                ):
                    raise UpdateApplicationError(
                        f"Addition uid '{operation.memory_uid}' already exists in "
                        f"Context '{context.name}'."
                    )
                working_copy.add(
                    Memory(uid=operation.memory_uid, content=operation.new_content)
                )
        updated_contexts.append(
            UpdatedContext(
                context_uid=context.uid,
                context_name=context.name,
                post_image=working_copy,
            )
        )
    return UpdateResult(
        plan_uid=plan.uid,
        target_uid=root_context.uid,
        target_name=root_context.name,
        updated_contexts=tuple(updated_contexts),
    )


__all__ = [
    "UpdateApplicationError",
    "apply_update_to_working_contexts",
]
