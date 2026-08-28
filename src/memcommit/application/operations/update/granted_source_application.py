"""Apply an Update whose readable source is granted and target is local."""

from __future__ import annotations

from datetime import datetime

from memcommit.application.capabilities.authority.access import (
    GrantedReadStore,
    revalidate_granted_context_binding,
)
from memcommit.core.context import AutoCheckpoint
from memcommit.core.context_targeting.loading import load_context_scope
from memcommit.application.operations.update.granted_application import _authority_name, _remove_checkpoint
from memcommit.application.operations.profile.model import authority_grant_snapshot_lock
from memcommit.persistence.store import (
    ConcurrentContextUpdateError,
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
)
from memcommit.application.operations.update.model import (
    UpdateApplicationReceipt,
    UpdateCheckpointReceipt,
    UpdateError,
    UpdateSession,
    applied_session_matches,
    collect_update_inputs,
    operation_digest,
    session_matches,
)
from memcommit.application.operations.update.application import prepare_update_application


def apply_granted_source_staged_update(
    active_store: MemoryStore,
    session: UpdateSession,
) -> UpdateSession:
    """Apply locally while the exact granted source projection is frozen."""

    if (
        session.status != "staged"
        or session.granted_source is None
        or session.granted_target is not None
    ):
        raise ValueError("Expected a granted-source, local-target update.")
    binding = session.granted_source
    authority_source_names = {
        _authority_name(binding, context.name)
        for context in session.source_contexts
    }
    target_lock_names = {context.name for context in session.target_contexts}

    with authority_grant_snapshot_lock() as registry:
        source_access = revalidate_granted_context_binding(
            binding,
            required_permission="READ",
            registry=registry,
        )
        with source_access.store._context_write_locks(authority_source_names):
            source_store = GrantedReadStore(
                source_access,
                registry=registry,
            )
            source = load_context_scope(
                source_store,
                binding.public_name,
                include_descendants=session.source_include_descendants,
            )
            with active_store._command_write_lock():
                active_store._assert_profile_write_allowed()
                with active_store._update_session_write_lock():
                    current = active_store._load_update_session(
                        active_store.staged_update_file
                    )
                    if current != session:
                        raise ConcurrentContextUpdateError(
                            "The active staged update changed before application."
                        )
                    with active_store._context_write_locks(target_lock_names):
                        target = load_context_scope(
                            active_store,
                            session.target_name,
                            include_descendants=(
                                session.target_include_descendants
                            ),
                        )
                        if not session_matches(
                            session,
                            source,
                            target,
                            granted_source=binding,
                        ):
                            raise ConcurrentContextUpdateError(
                                "The granted source or local target changed "
                                "before application."
                            )
                        result = prepare_update_application(session, target)
                        base_by_identity = {
                            (context.uid, context.name): context
                            for context in session.target_contexts
                        }
                        original_records = {}
                        expected_digests = {}
                        for owner in result.affected_owners:
                            base = base_by_identity.get(
                                (owner.owner_context_uid, owner.owner_context_name)
                            )
                            if base is None:
                                raise UpdateError(
                                    "Update owner is outside the recorded local target."
                                )
                            direct = active_store.load_direct(owner.owner_context_name)
                            if (
                                direct.uid != owner.owner_context_uid
                                or context_record_digest(direct) != base.digest
                            ):
                                raise ConcurrentContextUpdateError(
                                    f"Local target Context "
                                    f"'{owner.owner_context_name}' changed."
                                )
                            original_records[owner.owner_context_name] = direct.to_dict()
                            expected_digests[owner.owner_context_name] = base.digest

                        created_checkpoints = []
                        written_names = []
                        try:
                            operation_hash = operation_digest(session.operations)
                            for owner in result.affected_owners:
                                owner_operations = [
                                    operation
                                    for operation in session.operations
                                    if operation.owner_context_uid
                                    == owner.owner_context_uid
                                ]
                                checkpoint = active_store._save_locked(
                                    owner.post_image,
                                    AutoCheckpoint(
                                        command="update",
                                        args={
                                            "update_session_uid": session.uid,
                                            "operation_digest": operation_hash,
                                            "source_context_uid": session.source_uid,
                                            "source_context_name": session.source_name,
                                            "target_context_uid": session.target_uid,
                                            "target_context_name": session.target_name,
                                            "owner_context_uid": owner.owner_context_uid,
                                            "operation_memory_uids": [
                                                operation.memory_uid
                                                for operation in owner_operations
                                            ],
                                            "granted_source": binding.to_dict(),
                                        },
                                        description=(
                                            "Applied semantic update "
                                            f"{session.uid[:8]} from granted "
                                            f"{session.source_name}."
                                        ),
                                    ),
                                    expected_context_digest=expected_digests[
                                        owner.owner_context_name
                                    ],
                                )
                                if checkpoint is None:
                                    raise RuntimeError(
                                        "Update application created no checkpoint."
                                    )
                                written_names.append(owner.owner_context_name)
                                created_checkpoints.append(
                                    (owner.owner_context_name, checkpoint.uid)
                                )

                            target_after = load_context_scope(
                                active_store,
                                session.target_name,
                                include_descendants=(
                                    session.target_include_descendants
                                ),
                            )
                            inputs_after = collect_update_inputs(source, target_after)
                            checkpoint_by_name = dict(created_checkpoints)
                            receipt = UpdateApplicationReceipt(
                                applied_at=datetime.now().astimezone().isoformat(),
                                operation_digest=operation_hash,
                                target_digest=inputs_after.target_digest,
                                target_contexts=inputs_after.target_context_fingerprints,
                                checkpoints=tuple(
                                    UpdateCheckpointReceipt(
                                        context_uid=owner.owner_context_uid,
                                        context_name=owner.owner_context_name,
                                        checkpoint_uid=checkpoint_by_name[
                                            owner.owner_context_name
                                        ],
                                    )
                                    for owner in result.affected_owners
                                ),
                            )
                            applied = session.with_application(receipt)
                            if not applied_session_matches(
                                applied,
                                source,
                                target_after,
                                granted_source=binding,
                            ):
                                raise RuntimeError(
                                    "Applied local target does not match its receipt."
                                )
                            active_store._save_active_terminal_update(applied)
                        except Exception:
                            rollback_error = None
                            for name in written_names:
                                try:
                                    _write_json_atomic(
                                        active_store._context_file(name),
                                        original_records[name],
                                    )
                                except Exception as error:
                                    rollback_error = rollback_error or error
                            for name, checkpoint_uid in created_checkpoints:
                                try:
                                    _remove_checkpoint(
                                        active_store,
                                        name,
                                        checkpoint_uid,
                                    )
                                except Exception as error:
                                    rollback_error = rollback_error or error
                            if rollback_error is not None:
                                raise RuntimeError(
                                    "Update failed and its local target could not "
                                    "be fully rolled back."
                                ) from rollback_error
                            raise
    return applied
