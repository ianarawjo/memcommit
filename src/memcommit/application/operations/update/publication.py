"""Publish one exact UpdateSession across its resolved Context stores."""

from __future__ import annotations

from contextlib import ExitStack, nullcontext
from datetime import datetime

from memcommit.application.authorization import ContextUse, authorize_context_use
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    GrantedReadStore,
    revalidate_granted_context_binding,
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
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.application.operations.update.materialization import (
    prepare_update_application,
)
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    RemoveOperation,
    UpdateApplicationReceipt,
    UpdateCheckpointReceipt,
    UpdateError,
    UpdateOperation,
    UpdateSession,
    applied_session_matches,
    collect_update_inputs,
    inline_update_session_source,
    operation_digest,
    required_update_context_uses,
    session_matches,
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
) -> Context:
    store = _reader(active_store, access, registry=registry)
    return load_context_scope(
        store,
        binding.public_name if binding is not None else name,
        include_descendants=include_descendants,
    )


def _operation_use(operation: UpdateOperation) -> ContextUse:
    if isinstance(operation, AddOperation):
        return ContextUse.CREATE
    if isinstance(operation, EditOperation):
        return ContextUse.UPDATE
    if isinstance(operation, RemoveOperation):
        return ContextUse.DELETE
    raise TypeError("Unsupported Update operation.")


def authorize_granted_target_operations(
    session: UpdateSession,
    access: ContextAccess,
    *,
    registry,
) -> None:
    """Authorize every public owner against the same frozen Target Grant."""

    binding = session.granted_target
    if binding is None or access.view is None:
        raise UpdateError("Expected a granted Update Target.")
    uses_by_owner: dict[str, set[ContextUse]] = {}
    for operation in session.operations:
        uses_by_owner.setdefault(operation.owner_context_name, set()).add(
            _operation_use(operation)
        )
    for public_name, uses in uses_by_owner.items():
        view = resolve_granted_context_view(
            public_name,
            attachment_name=binding.attachment_context_name,
            required_permission="READ",
            registry=registry,
        )
        owner_access = ContextAccess(
            store=access.store,
            context_name=view.authority_context_name,
            display_name=public_name,
            attachment_name=binding.attachment_context_name,
            permission="READ",
            view=view,
        )
        authorize_context_use(
            owner_access,
            frozenset(uses) | {ContextUse.READ},
        )
        if (
            view.grant.uid != binding.grant_uid
            or view.grant.revision != binding.grant_revision
            or view.authority.uid != binding.authority_profile_uid
            or view.grantee.uid != binding.grantee_profile_uid
        ):
            raise ProfileError(
                "An Update owner is controlled by a different or changed Grant."
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
            post_image.replace(
                Memory(uid=operation.memory_uid, content=operation.new_content)
            )
        elif isinstance(operation, RemoveOperation):
            post_image.remove(operation.memory_uid)
        else:
            post_image.add(
                Memory(uid=operation.memory_uid, content=operation.new_content)
            )
    return post_image


def _checkpoint_args(
    session: UpdateSession,
    *,
    operation_hash: str,
    owner_uid: str,
    owner_operations: tuple[UpdateOperation, ...],
    affected_owners,
) -> dict[str, object]:
    target_binding = session.granted_target
    args: dict[str, object] = {
        "update_session_uid": session.uid,
        "operation_digest": operation_hash,
        "source_context_uid": session.source_uid,
        "source_context_name": session.source_name,
        "target_context_uid": session.target_uid,
        "target_context_name": session.target_name,
        "goal_focus": (
            None
            if session.goal_focus is None
            else session.goal_focus.receipt_record()
        ),
        "owner_context_uid": owner_uid,
        "operation_memory_uids": [
            operation.memory_uid for operation in owner_operations
        ],
        # Authority history is reconstructed from physical Context records;
        # participant receipts retain the public names separately.
        "command_contexts": [
            {
                "uid": owner.owner_context_uid,
                "name": _physical_name(
                    target_binding,
                    owner.owner_context_name,
                ),
            }
            for owner in affected_owners
        ],
    }
    if session.granted_source is not None:
        args["granted_source"] = session.granted_source.to_dict()
    if target_binding is not None:
        args.update(
            {
                "authority_target_context_name": (
                    target_binding.authority_context_name
                ),
                "authority_grant": {
                    "uid": target_binding.grant_uid,
                    "revision": target_binding.grant_revision,
                    "grantee_profile_uid": target_binding.grantee_profile_uid,
                    "public_context": target_binding.public_name,
                },
            }
        )
    return args


def _apply_locked(
    active_store: MemoryStore,
    session: UpdateSession,
    *,
    registry,
    source_access: ContextAccess | None,
    target_access: ContextAccess | None,
) -> UpdateSession:
    """Apply after all participant records and control-plane state are locked."""

    source_binding = session.granted_source
    target_binding = session.granted_target
    inline_source = inline_update_session_source(session)
    if session.goal_focus is not None:
        try:
            revalidate_goal_focus(active_store, session.goal_focus)
        except GoalFocusError as error:
            raise ConcurrentContextUpdateError(
                "The Update Goal focus changed before application."
            ) from error
    source = inline_source or _load_endpoint(
        active_store,
        source_access,
        source_binding,
        session.source_name,
        include_descendants=session.source_include_descendants,
        registry=registry,
    )
    target = _load_endpoint(
        active_store,
        target_access,
        target_binding,
        session.target_name,
        include_descendants=session.target_include_descendants,
        registry=registry,
    )
    if not session_matches(
        session,
        source,
        target,
        granted_source=source_binding,
        granted_target=target_binding,
    ):
        raise ConcurrentContextUpdateError(
            "The Update Source or Target changed before application."
        )

    result = prepare_update_application(session, target)
    target_store = active_store if target_access is None else target_access.store
    base_by_identity = {
        (context.uid, context.name): context for context in session.target_contexts
    }
    originals: dict[str, dict[str, object]] = {}
    post_images: dict[str, Context] = {}
    expected_digests: dict[str, str] = {}
    for owner in result.affected_owners:
        base = base_by_identity.get(
            (owner.owner_context_uid, owner.owner_context_name)
        )
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
            for operation in session.operations
            if operation.owner_context_uid == owner.owner_context_uid
        )
        originals[physical_name] = direct.to_dict()
        post_images[physical_name] = _apply_operations_to_direct(
            direct,
            owner_operations,
        )
        expected_digests[physical_name] = context_record_digest(direct)

    created_checkpoints: list[tuple[str, str, str]] = []
    written_names: list[str] = []
    try:
        operation_hash = operation_digest(session.operations)
        for owner in result.affected_owners:
            public_name = owner.owner_context_name
            physical_name = _physical_name(target_binding, public_name)
            owner_operations = tuple(
                operation
                for operation in session.operations
                if operation.owner_context_uid == owner.owner_context_uid
            )
            checkpoint = target_store._save_locked(
                post_images[physical_name],
                AutoCheckpoint(
                    command="update",
                    args=_checkpoint_args(
                        session,
                        operation_hash=operation_hash,
                        owner_uid=owner.owner_context_uid,
                        owner_operations=owner_operations,
                        affected_owners=result.affected_owners,
                    ),
                    description=(
                        f"Applied semantic update {session.uid[:8]} from "
                        f"{session.source_name}."
                    ),
                ),
                expected_context_digest=expected_digests[physical_name],
            )
            if checkpoint is None:
                raise RuntimeError("Update application created no checkpoint.")
            written_names.append(physical_name)
            created_checkpoints.append(
                (physical_name, public_name, checkpoint.uid)
            )

        source_after = inline_source or _load_endpoint(
            active_store,
            source_access,
            source_binding,
            session.source_name,
            include_descendants=session.source_include_descendants,
            registry=registry,
        )
        target_after = _load_endpoint(
            active_store,
            target_access,
            target_binding,
            session.target_name,
            include_descendants=session.target_include_descendants,
            registry=registry,
        )
        inputs_after = collect_update_inputs(source_after, target_after)
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
        applied = session.with_application(receipt)
        if not applied_session_matches(
            applied,
            source_after,
            target_after,
            granted_source=source_binding,
            granted_target=target_binding,
        ):
            raise RuntimeError("Applied Update does not match its receipt.")
        active_store._save_active_terminal_update(applied)
    except Exception:
        rollback_error: Exception | None = None
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


def _source_lock_names(session: UpdateSession) -> set[str]:
    binding = session.granted_source
    if inline_update_session_source(session) is not None:
        return set()
    public_names = {context.name for context in session.source_contexts}
    public_names.add(session.source_name)
    public_names.update(
        source.context_name
        for operation in session.operations
        for source in operation.source_refs
    )
    return {_physical_name(binding, name) for name in public_names}


def _target_lock_names(session: UpdateSession) -> set[str]:
    binding = session.granted_target
    public_names = {context.name for context in session.target_contexts}
    public_names.add(session.target_name)
    return {_physical_name(binding, name) for name in public_names}


def _assert_current_session(active_store: MemoryStore, session: UpdateSession) -> None:
    current = active_store._load_update_session(active_store.staged_update_file)
    if current != session:
        raise ConcurrentContextUpdateError(
            "The active staged Update changed before application."
        )


def apply_staged_update(
    active_store: MemoryStore,
    session: UpdateSession,
) -> UpdateSession:
    """Apply one staged Update through a single authorization/publication flow.

    Local and granted endpoints select stores, public-name projection, and lock
    topology. They do not select different Update semantics: every route uses
    the same exact-effect authorization, materialization, checkpoint, receipt,
    rollback, and post-application verification body.
    """

    if not isinstance(session, UpdateSession) or session.status != "staged":
        raise ValueError("Expected one staged UpdateSession.")
    source_binding = session.granted_source
    target_binding = session.granted_target

    grant_lock = (
        authority_grant_snapshot_lock()
        if source_binding is not None or target_binding is not None
        else nullcontext(None)
    )
    with grant_lock as registry:
        source_access = (
            None
            if source_binding is None
            else revalidate_granted_context_binding(
                source_binding,
                required_permission="READ",
                registry=registry,
                active_store=active_store,
            )
        )
        if source_access is not None:
            authorize_context_use(source_access, ContextUse.READ)
        target_access = (
            None
            if target_binding is None
            else revalidate_granted_context_binding(
                target_binding,
                required_permission="READ",
                registry=registry,
                active_store=active_store,
            )
        )
        if target_access is not None:
            authorize_context_use(
                target_access,
                required_update_context_uses(session.operations),
            )
            authorize_granted_target_operations(
                session,
                target_access,
                registry=registry,
            )

        source_store = active_store if source_access is None else source_access.store
        target_store = active_store if target_access is None else target_access.store
        source_locks = _source_lock_names(session)
        target_locks = _target_lock_names(session)
        goal_locks: set[str] = set()
        if session.goal_focus is not None and session.goal_focus.kind != "INLINE":
            assert session.goal_focus.context_name is not None
            goal_locks.add(session.goal_focus.context_name)

        if target_store.store_dir == active_store.store_dir:
            with ExitStack() as external_source:
                if source_store.store_dir != active_store.store_dir:
                    external_source.enter_context(
                        source_store._context_write_locks(source_locks)
                    )
                with active_store._command_write_lock():
                    active_store._assert_profile_write_allowed()
                    with active_store._update_session_write_lock():
                        _assert_current_session(active_store, session)
                        local_locks = target_locks | goal_locks
                        if source_store.store_dir == active_store.store_dir:
                            local_locks.update(source_locks)
                        with active_store._context_write_locks(local_locks):
                            return _apply_locked(
                                active_store,
                                session,
                                registry=registry,
                                source_access=source_access,
                                target_access=target_access,
                            )

        with active_store._update_session_write_lock():
            _assert_current_session(active_store, session)
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
                            session,
                            registry=registry,
                            source_access=source_access,
                            target_access=target_access,
                        )


__all__ = ["apply_staged_update", "authorize_granted_target_operations"]
