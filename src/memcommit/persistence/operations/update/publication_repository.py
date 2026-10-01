"""Publish a process-local Update plan and its immutable completion receipt."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime

from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
)
from memcommit.application.capabilities.context_scope_loading import load_context_scope
from memcommit.application.capabilities.semantic.goal_focus import GoalFocusError
from memcommit.application.capabilities.semantic.goal_focus_runtime import (
    revalidate_goal_focus,
)
from memcommit.application.context_access import (
    GrantedContextBinding,
    authority_context_name,
)
from memcommit.application.operations.update.application import apply_update
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
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
)


def _physical_name(
    binding: GrantedContextBinding | None,
    public_name: str,
) -> str:
    if binding is None:
        return public_name
    try:
        return authority_context_name(binding, public_name)
    except ValueError as error:
        raise UpdateError(
            "An Update owner is outside its frozen granted namespace."
        ) from error


def _reader(
    active_store: MemoryStore,
    access: ContextAccess | None,
    *,
    registry,
):
    if access is None:
        return active_store
    return GrantedReadStore(access, registry=registry)


def _load_endpoint(
    active_store: MemoryStore,
    access: ContextAccess | None,
    binding: GrantedContextBinding | None,
    name: str,
    *,
    include_descendants: bool,
    registry,
    direct: bool = False,
) -> Context:
    store = _reader(active_store, access, registry=registry)
    if direct:
        return store.load_direct(binding.access_name if binding is not None else name)
    return load_context_scope(
        store,
        binding.access_name if binding is not None else name,
        include_descendants=include_descendants,
    )


def _apply_operations_to_direct(
    direct: Context,
    operations: tuple[UpdateOperation, ...],
) -> Context:
    """Create a physical-name post-image after semantic preflight succeeds."""

    post_image = Context.from_dict(direct.to_dict())
    post_image._store_digest = direct._store_digest
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
    *,
    registry,
    source_access: ContextAccess | None,
    target_access: ContextAccess | None,
) -> UpdateReceipt:
    """Apply after all participant records and control-plane state are locked."""

    if UpdateReceiptRepository(active_store).path(plan.uid).exists():
        raise ConcurrentContextUpdateError("This Update was already applied.")
    source_binding = inputs.granted_source
    target_binding = inputs.granted_target
    inline_source = inline_update_source(inputs)
    if inputs.goal_focus is not None:
        try:
            revalidate_goal_focus(active_store, inputs.goal_focus)
        except GoalFocusError as error:
            raise ConcurrentContextUpdateError(
                "The Update Goal focus changed before application."
            ) from error
    source = inline_source or _load_endpoint(
        active_store,
        source_access,
        source_binding,
        inputs.source_name,
        include_descendants=inputs.source_include_descendants,
        direct=inputs.instruction is not None,
        registry=registry,
    )
    target = _load_endpoint(
        active_store,
        target_access,
        target_binding,
        inputs.target_name,
        include_descendants=inputs.target_include_descendants,
        direct=inputs.instruction is not None,
        registry=registry,
    )
    if not update_inputs_match(
        inputs,
        source,
        target,
        granted_source=source_binding,
        granted_target=target_binding,
    ):
        raise ConcurrentContextUpdateError(
            "The Update Source or Target changed before application."
        )

    result = apply_update(plan, target)
    target_store = active_store if target_access is None else target_access.store
    base_by_identity = {
        (context.uid, context.name): context for context in inputs.target_contexts
    }
    originals: dict[str, dict[str, object]] = {}
    post_images: dict[str, Context] = {}
    expected_digests: dict[str, str] = {}
    for owner in result.affected_owners:
        base = base_by_identity.get((owner.owner_context_uid, owner.owner_context_name))
        if base is None:
            raise UpdateError("Update owner is outside the recorded Target.")
        physical_name = _physical_name(target_binding, owner.owner_context_name)
        direct = target_store.load_direct(physical_name)
        if direct.uid != owner.owner_context_uid:
            raise ConcurrentContextUpdateError(
                "An Update Target Context identity changed before application."
            )
        if target_binding is None and context_record_digest(direct) != base.digest:
            raise ConcurrentContextUpdateError(
                f"Update Target Context {owner.owner_context_name!r} changed."
            )
        owner_operations = tuple(
            operation
            for operation in plan.operations
            if operation.owner_context_uid == owner.owner_context_uid
        )
        originals[physical_name] = direct.to_dict()
        post_images[physical_name] = _apply_operations_to_direct(
            direct,
            owner_operations,
        )
        expected_digests[physical_name] = context_record_digest(direct)

    written_receipts = []
    created_checkpoints: list[tuple[str, str, str]] = []
    written_names: list[str] = []
    try:
        operation_hash = operation_digest(plan.operations)
        for owner in result.affected_owners:
            public_name = owner.owner_context_name
            physical_name = _physical_name(target_binding, public_name)
            owner_operations = tuple(
                operation
                for operation in plan.operations
                if operation.owner_context_uid == owner.owner_context_uid
            )
            checkpoint = target_store._save_locked(
                post_images[physical_name],
                AutoCheckpoint(
                    command="update",
                    args=build_update_checkpoint(
                        inputs,
                        plan,
                        operation_hash=operation_hash,
                        owner_uid=owner.owner_context_uid,
                        owner_operations=owner_operations,
                        affected_owners=result.affected_owners,
                    ),
                    description=(
                        f"Applied semantic update {plan.uid[:8]} from "
                        f"{inputs.source_name}."
                    ),
                ),
                expected_context_digest=expected_digests[physical_name],
            )
            if checkpoint is None:
                raise RuntimeError("Update application created no checkpoint.")
            written_names.append(physical_name)
            created_checkpoints.append((physical_name, public_name, checkpoint.uid))

        source_after = inline_source or _load_endpoint(
            active_store,
            source_access,
            source_binding,
            inputs.source_name,
            include_descendants=inputs.source_include_descendants,
            direct=inputs.instruction is not None,
            registry=registry,
        )
        target_after = _load_endpoint(
            active_store,
            target_access,
            target_binding,
            inputs.target_name,
            include_descendants=inputs.target_include_descendants,
            direct=inputs.instruction is not None,
            registry=registry,
        )
        inputs_after = collect_update_inputs(
            source_after,
            target_after,
            source_memory_selector=inputs.source_memory_uid,
            instruction=inputs.instruction,
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
                    context_uid=owner.owner_context_uid,
                    context_name=owner.owner_context_name,
                    checkpoint_uid=checkpoint_by_public[owner.owner_context_name],
                )
                for owner in result.affected_owners
            ),
        )
        applied = UpdateReceipt(inputs, plan, receipt)
        # Evidence stays with the initiating Profile. Copying it into a granted
        # authority would disclose participant-only inline instructions and also
        # make that authority misidentify its own local Undo as a granted route.
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
    binding = inputs.granted_source
    if inline_update_source(inputs) is not None:
        return set()
    public_names = {context.name for context in inputs.source_contexts}
    public_names.add(inputs.source_name)
    public_names.update(
        source.context_name
        for operation in plan.operations
        for source in operation.source_refs
    )
    return {_physical_name(binding, name) for name in public_names}


def _target_lock_names(inputs: UpdateContextInputs) -> set[str]:
    binding = inputs.granted_target
    public_names = {context.name for context in inputs.target_contexts}
    public_names.add(inputs.target_name)
    return {_physical_name(binding, name) for name in public_names}


def publish_update_transaction(
    active_store: MemoryStore,
    inputs: UpdateContextInputs,
    plan: UpdatePlan,
    *,
    registry,
    source_access: ContextAccess | None,
    target_access: ContextAccess | None,
) -> UpdateReceipt:
    """Publish a pre-authorized Update or leave no partial effect."""

    if not isinstance(inputs, UpdateContextInputs) or not isinstance(plan, UpdatePlan):
        raise TypeError("Expected frozen Update inputs and an exact plan.")
    source_store = active_store if source_access is None else source_access.store
    target_store = active_store if target_access is None else target_access.store
    source_locks = _source_lock_names(inputs, plan)
    target_locks = _target_lock_names(inputs)
    goal_locks: set[str] = set()
    if inputs.goal_focus is not None and inputs.goal_focus.kind != "INLINE":
        assert inputs.goal_focus.context_name is not None
        goal_locks.add(inputs.goal_focus.context_name)

    if target_store.store_dir == active_store.store_dir:
        with ExitStack() as external_source:
            if source_store.store_dir != active_store.store_dir:
                external_source.enter_context(
                    source_store._context_write_locks(source_locks)
                )
            with active_store._command_write_lock():
                active_store._assert_profile_write_allowed()
                local_locks = target_locks | goal_locks
                if source_store.store_dir == active_store.store_dir:
                    local_locks.update(source_locks)
                with active_store._context_write_locks(local_locks):
                    return _apply_locked(
                        active_store,
                        inputs,
                        plan,
                        registry=registry,
                        source_access=source_access,
                        target_access=target_access,
                    )

    active_store._assert_profile_write_allowed()
    with ExitStack() as non_target_locks:
        active_goal_locked = False
        if source_store.store_dir != target_store.store_dir:
            source_and_goal = set(source_locks)
            if source_store.store_dir == active_store.store_dir:
                source_and_goal.update(goal_locks)
                active_goal_locked = True
            non_target_locks.enter_context(
                source_store._context_write_locks(source_and_goal)
            )
        if goal_locks and not active_goal_locked:
            non_target_locks.enter_context(
                active_store._context_write_locks(goal_locks)
            )
        with target_store._command_write_lock():
            target_store._assert_profile_write_allowed()
            combined_target_locks = set(target_locks)
            if source_store.store_dir == target_store.store_dir:
                combined_target_locks.update(source_locks)
            if target_store.store_dir == active_store.store_dir:
                combined_target_locks.update(goal_locks)
            with target_store._context_write_locks(combined_target_locks):
                return _apply_locked(
                    active_store,
                    inputs,
                    plan,
                    registry=registry,
                    source_access=source_access,
                    target_access=target_access,
                )


__all__ = ["publish_update_transaction"]
