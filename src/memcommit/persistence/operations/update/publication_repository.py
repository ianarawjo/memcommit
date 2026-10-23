"""Publish a process-local Update plan and its immutable completion receipt."""

from __future__ import annotations

from datetime import datetime

from memcommit.application.capabilities.context_scope_loading import (
    load_context_and_descendants,
)
from memcommit.application.capabilities.semantic.goal_focus import GoalFocusError
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    revalidate_goal_focus,
)
from memcommit.application.operations.update.application import (
    apply_update_to_working_contexts,
)
from memcommit.application.operations.update.checkpoint import build_update_checkpoint
from .receipt_repository import UpdateReceiptRepository
from memcommit.application.operations.update.model import (
    EditOperation,
    RemoveOperation,
    UpdateApplicationReceipt,
    UpdateCheckpointReceipt,
    UpdateError,
    UpdateOperation,
    UpdateContextInputs,
    UpdatePlan,
    UpdateReceipt,
    collect_update_inputs,
    inline_update_source,
    operation_digest,
    update_inputs_match,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.models.context import Context
from memcommit.models.memory import Memory
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_json_atomic,
)


def _load_endpoint(store, name, *, include_descendants, direct=False):
    if direct:
        return (store.load_direct(name),)
    return (
        load_context_and_descendants(store, name)
        if include_descendants
        else (store.load(name),)
    )


def _apply_operations_to_direct(
    direct: Context,
    operations: tuple[UpdateOperation, ...],
) -> Context:
    """Create a physical-name post-image after semantic preflight succeeds."""

    post_image = Context.from_dict(direct.to_dict())
    for operation in operations:
        if isinstance(operation, EditOperation):
            post_image.replace_memory(
                Memory(uid=operation.memory_uid, content=operation.new_content)
            )
        elif isinstance(operation, RemoveOperation):
            post_image.remove(operation.memory_uid)
        else:
            post_image.add(
                Memory(uid=operation.memory_uid, content=operation.new_content)
            )
    return post_image


def _apply_locked(
    active_store: MemoryStore,
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
) -> UpdateReceipt:
    """Apply after all participant records and control-plane state are locked."""

    if UpdateReceiptRepository(active_store).path(plan.uid).exists():
        raise ConcurrentContextUpdateError("This Update was already applied.")
    inline_source = inline_update_source(inputs)
    if inputs.goal_focus is not None:
        try:
            revalidate_goal_focus(active_store, inputs.goal_focus)
        except GoalFocusError as error:
            raise ConcurrentContextUpdateError(
                "The Update Goal focus changed before application."
            ) from error
    source_contexts = (
        (inline_source,)
        if inline_source is not None
        else _load_endpoint(
            active_store,
            inputs.source_name,
            include_descendants=inputs.source_include_descendants,
            direct=inputs.instruction is not None,
        )
    )
    target_contexts = _load_endpoint(
        active_store,
        inputs.target_name,
        include_descendants=inputs.target_include_descendants,
        direct=inputs.instruction is not None and not inputs.target_include_descendants,
    )
    if not update_inputs_match(inputs, source_contexts, target_contexts):
        raise ConcurrentContextUpdateError(
            "The Update Source or Target changed before application."
        )

    result = apply_update_to_working_contexts(plan, target_contexts)
    target_store = active_store
    base_by_identity = {
        (context.uid, context.name): context for context in inputs.target_contexts
    }
    originals: dict[str, dict[str, object]] = {}
    post_images: dict[str, Context] = {}
    for updated_context in result.updated_contexts:
        base = base_by_identity.get(
            (updated_context.context_uid, updated_context.context_name)
        )
        if base is None:
            raise UpdateError("Update owner is outside the recorded Target.")
        physical_name = updated_context.context_name
        direct = target_store.load_direct(physical_name)
        if direct.uid != updated_context.context_uid:
            raise ConcurrentContextUpdateError(
                "An Update Target Context identity changed before application."
            )
        owner_operations = tuple(
            operation
            for operation in plan.operations
            if operation.owner_context_uid == updated_context.context_uid
        )
        originals[physical_name] = direct.to_dict()
        post_images[physical_name] = _apply_operations_to_direct(
            direct,
            owner_operations,
        )

    written_receipts = []
    created_checkpoints: list[tuple[str, str, str]] = []
    written_names: list[str] = []
    try:
        operation_hash = operation_digest(plan.operations)
        for updated_context in result.updated_contexts:
            public_name = updated_context.context_name
            physical_name = public_name
            owner_operations = tuple(
                operation
                for operation in plan.operations
                if operation.owner_context_uid == updated_context.context_uid
            )
            checkpoint = target_store._save_locked(
                post_images[physical_name],
                AutoCheckpointRequest(
                    command="update",
                    command_details=build_update_checkpoint(
                        inputs,
                        plan,
                        operation_hash=operation_hash,
                        owner_uid=updated_context.context_uid,
                        owner_operations=owner_operations,
                        updated_contexts=result.updated_contexts,
                    ),
                ),
            )
            if checkpoint is None:
                raise RuntimeError("Update application created no checkpoint.")
            written_names.append(physical_name)
            created_checkpoints.append((physical_name, public_name, checkpoint.uid))

        source_contexts_after = (
            (inline_source,)
            if inline_source is not None
            else _load_endpoint(
                active_store,
                inputs.source_name,
                include_descendants=inputs.source_include_descendants,
                direct=inputs.instruction is not None,
            )
        )
        target_contexts_after = _load_endpoint(
            active_store,
            inputs.target_name,
            include_descendants=inputs.target_include_descendants,
            direct=inputs.instruction is not None
            and not inputs.target_include_descendants,
        )
        inputs_after = collect_update_inputs(
            source_contexts_after,
            target_contexts_after,
            source_memory_selector=inputs.source_memory_uid,
            instruction=inputs.instruction,
            target_include_descendants=inputs.target_include_descendants,
        )
        checkpoint_by_public = {
            public_name: checkpoint_uid
            for _physical, public_name, checkpoint_uid in created_checkpoints
        }
        receipt = UpdateApplicationReceipt(
            applied_at=datetime.now().astimezone().isoformat(),
            operation_digest=operation_hash,
            target_digest=inputs_after.target_digest,
            target_contexts=inputs_after.target_context_fingerprints,
            checkpoints=tuple(
                UpdateCheckpointReceipt(
                    context_uid=updated_context.context_uid,
                    context_name=updated_context.context_name,
                    checkpoint_uid=checkpoint_by_public[updated_context.context_name],
                )
                for updated_context in result.updated_contexts
            ),
        )
        applied = UpdateReceipt(inputs, plan, receipt)
        repository = UpdateReceiptRepository(active_store)
        path = repository.path(applied.uid)
        if path.exists() or path.is_symlink():
            raise ConcurrentContextUpdateError("This Update was already applied.")
        written_receipts.append(path)
        repository.save(applied)

    except Exception:
        rollback_error: Exception | None = None
        for path in written_receipts:
            try:
                path.unlink(missing_ok=True)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        for name in written_names:
            try:
                _write_json_atomic(target_store._context_file(name), originals[name])
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        for name, _public, checkpoint_uid in created_checkpoints:
            try:
                target_store._remove_checkpoint_uid_locked(name, checkpoint_uid)
            except Exception as candidate:
                rollback_error = rollback_error or candidate
        if rollback_error is not None:
            raise RuntimeError(
                "Update failed and its Target could not be fully rolled back."
            ) from rollback_error
        raise
    return applied


def _source_lock_names(inputs: UpdateContextInputs, plan: UpdatePlan) -> set[str]:
    if inline_update_source(inputs) is not None:
        return set()
    public_names = {context.name for context in inputs.source_contexts}
    public_names.add(inputs.source_name)
    public_names.update(
        source.context_name
        for operation in plan.operations
        for source in operation.source_refs
    )
    return public_names


def _target_lock_names(inputs: UpdateContextInputs) -> set[str]:
    public_names = {context.name for context in inputs.target_contexts}
    public_names.add(inputs.target_name)
    return public_names


def publish_update_transaction(
    active_store: MemoryStore,
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
) -> UpdateReceipt:
    """Publish a pre-authorized Update or leave no partial effect."""

    if not isinstance(inputs, UpdateContextInputs) or not isinstance(plan, UpdatePlan):
        raise TypeError("Expected frozen Update inputs and an exact plan.")
    source_locks = _source_lock_names(inputs, plan)
    target_locks = _target_lock_names(inputs)
    goal_locks = set()
    if inputs.goal_focus is not None and inputs.goal_focus.kind != "INLINE":
        assert inputs.goal_focus.context_name is not None
        goal_locks.add(inputs.goal_focus.context_name)
    with active_store._command_write_lock():
        active_store._assert_profile_write_allowed()
        with active_store._context_write_locks(
            source_locks | target_locks | goal_locks
        ):
            return _apply_locked(active_store, inputs, plan)


__all__ = ["publish_update_transaction"]
