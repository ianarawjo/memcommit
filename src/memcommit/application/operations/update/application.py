"""Apply exact Update plans to detached Target state without persistence."""

from __future__ import annotations

import copy

from memcommit.application.operations.update.model import (
    AddOperation,
    AppliedOwner,
    EditOperation,
    RemoveOperation,
    UpdateError,
    UpdatePlan,
    UpdateResult,
    UpdateSession,
)
from memcommit.core.context import Context, Memory, MemoryRef, QueryContextRef


class UpdateApplicationError(UpdateError):
    """An exact Update plan cannot be applied to the supplied Target graph."""


def _walk_target_contexts(root: Context) -> tuple[Context, ...]:
    contexts: list[Context] = []
    visited: set[str] = set()

    def visit(context: Context) -> None:
        if context.uid in visited:
            return
        visited.add(context.uid)
        contexts.append(context)
        for item in context.iter_items():
            if isinstance(item, Context):
                visit(item)

    visit(root)
    return tuple(contexts)


def _detached_direct_copy(context: Context) -> Context:
    post_image = Context.from_dict(context.to_dict())
    # A later publication boundary may use this immutable load token for CAS.
    post_image._store_digest = context._store_digest
    return post_image


def _read_only_type(item: object) -> str:
    if isinstance(item, MemoryRef):
        return "MemoryRef"
    if isinstance(item, QueryContextRef):
        return "QueryContextRef"
    if isinstance(item, Context):
        return "embedded Context"
    return type(item).__name__


def apply_update(plan: UpdatePlan, target: Context) -> UpdateResult:
    """Validate one exact plan and return detached Target owner post-images.

    The caller owns review and durable publication. Neither success nor
    failure mutates ``target`` or any embedded Context.
    """

    if not isinstance(plan, UpdatePlan):
        raise TypeError("Expected an UpdatePlan.")
    if not isinstance(target, Context):
        raise TypeError("Expected a target Context.")
    if plan.target_uid != target.uid or plan.target_name != target.name:
        raise UpdateApplicationError(
            "The Update plan Target does not match the supplied Context."
        )

    target_contexts = _walk_target_contexts(target)
    context_by_uid = {context.uid: context for context in target_contexts}
    operations_by_owner: dict[
        str,
        list[EditOperation | AddOperation | RemoveOperation],
    ] = {}
    operation_targets: set[tuple[str, str]] = set()

    # Validate the unchanged graph completely before constructing a post-image.
    for operation in plan.operations:
        if not isinstance(operation, (EditOperation, AddOperation, RemoveOperation)):
            raise UpdateApplicationError(
                "The staged update contains an unsupported operation."
            )
        owner = context_by_uid.get(operation.owner_context_uid)
        if owner is None:
            raise UpdateApplicationError(
                "The staged update names a target Context that is not in "
                "the supplied target graph."
            )
        if owner.name != operation.owner_context_name:
            raise UpdateApplicationError(
                "The staged update owner identity does not match the target "
                "Context graph."
            )
        identity = (owner.uid, operation.memory_uid)
        if identity in operation_targets:
            raise UpdateApplicationError(
                "The staged update targets the same owner item more than once."
            )
        operation_targets.add(identity)

        current = owner.memories.get(operation.memory_uid)
        if isinstance(operation, EditOperation):
            if current is None:
                raise UpdateApplicationError(
                    f"Edit target '{operation.memory_uid}' does not exist in "
                    f"Context '{owner.name}'."
                )
            if not isinstance(current, Memory):
                raise UpdateApplicationError(
                    f"Edit target '{operation.memory_uid}' is a "
                    f"{_read_only_type(current)} and cannot be modified."
                )
            if current.content != operation.old_content:
                raise UpdateApplicationError(
                    f"Edit target '{operation.memory_uid}' no longer matches "
                    "the staged old content."
                )
        elif isinstance(operation, RemoveOperation):
            if current is None:
                raise UpdateApplicationError(
                    f"Removal target '{operation.memory_uid}' does not exist "
                    f"in Context '{owner.name}'."
                )
            if not isinstance(current, Memory):
                raise UpdateApplicationError(
                    f"Removal target '{operation.memory_uid}' is a "
                    f"{_read_only_type(current)} and cannot be removed."
                )
            if current.content != operation.old_content:
                raise UpdateApplicationError(
                    f"Removal target '{operation.memory_uid}' no longer "
                    "matches the staged old content."
                )
        elif current is not None:
            raise UpdateApplicationError(
                f"Addition uid '{operation.memory_uid}' already exists in "
                f"Context '{owner.name}'."
            )
        operations_by_owner.setdefault(owner.uid, []).append(operation)

    affected: list[AppliedOwner] = []
    for owner in target_contexts:
        owner_operations = operations_by_owner.get(owner.uid)
        if not owner_operations:
            continue
        post_image = _detached_direct_copy(owner)
        for operation in owner_operations:
            if isinstance(operation, EditOperation):
                post_image.replace(
                    Memory(uid=operation.memory_uid, content=operation.new_content)
                )
            elif isinstance(operation, RemoveOperation):
                post_image.remove(operation.memory_uid)
            else:
                post_image.add(
                    Memory(uid=operation.memory_uid, content=operation.new_content)
                )
        affected.append(
            AppliedOwner(
                owner_context_uid=owner.uid,
                owner_context_name=owner.name,
                post_image=post_image,
            )
        )
    return UpdateResult(
        plan_uid=plan.uid,
        target_uid=target.uid,
        target_name=target.name,
        affected_owners=tuple(affected),
    )


def materialize_update_post_image(
    result: UpdateResult,
    target: Context,
) -> Context:
    """Recompose the complete detached Target graph after exact application.

    ``UpdateResult`` keeps owner post-images separate so publication can retain
    each Context's CAS boundary. Semantic callers such as Resolve instead need
    one complete graph for whole-frame verification. This helper joins those
    views without mutating either the frozen Target or the result records.
    """

    if not isinstance(result, UpdateResult):
        raise TypeError("Expected an UpdateResult.")
    if not isinstance(target, Context):
        raise TypeError("Expected a target Context.")
    if result.target_uid != target.uid or result.target_name != target.name:
        raise UpdateApplicationError(
            "The Update result Target does not match the supplied Context."
        )

    root = copy.deepcopy(target)
    owner_by_uid = {context.uid: context for context in _walk_target_contexts(root)}
    for affected in result.affected_owners:
        owner = owner_by_uid.get(affected.owner_context_uid)
        if owner is None or owner.name != affected.owner_context_name:
            raise UpdateApplicationError(
                "The Update result names an owner outside the supplied Target graph."
            )
        expected_memories = {
            item.uid: item
            for item in affected.post_image.iter_items()
            if isinstance(item, Memory)
        }
        for uid, item in tuple(owner.memories.items()):
            if isinstance(item, Memory) and uid not in expected_memories:
                owner.remove(uid)
        for uid, memory in expected_memories.items():
            replacement = Memory(uid=uid, content=memory.content)
            if uid in owner.memories:
                owner.replace(replacement)
            else:
                owner.add(replacement)
    return root


def apply_staged_update_plan(
    session: UpdateSession,
    target: Context,
) -> UpdateResult:
    """Apply the exact plan carried by one staged direct-Update session."""

    if not isinstance(session, UpdateSession):
        raise TypeError("Expected an UpdateSession.")
    if session.status != "staged":
        raise UpdateApplicationError(
            "Update application requires a staged update session."
        )
    return apply_update(
        session.plan,
        target,
    )


__all__ = [
    "UpdateApplicationError",
    "apply_staged_update_plan",
    "apply_update",
    "materialize_update_post_image",
]
