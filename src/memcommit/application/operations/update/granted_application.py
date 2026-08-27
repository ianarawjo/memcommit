"""Apply one frozen granted UpdateSession to its authority-owned Contexts."""

from __future__ import annotations

import json
from contextlib import ExitStack
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from memcommit.application.authority.access import (
    GrantedReadStore,
    freeze_granted_context_binding,
    revalidate_granted_context_binding,
    resolve_context_access,
)
from memcommit.context import Context, Memory
from memcommit.context_targeting.loading import load_context_scope
from memcommit.retained_history.command_history import CommandRestoreResult
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.application.operations.profile.model import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.persistence.store import (
    AutoCheckpoint,
    ConcurrentContextUpdateError,
    MemoryStore,
    _reject_duplicate_json_keys,
    _write_json_atomic,
    context_record_digest,
)
from memcommit.application.operations.update.model import (
    AddOperation,
    EditOperation,
    GrantedUpdateTarget,
    RemoveOperation,
    UpdateApplicationReceipt,
    UpdateCheckpointReceipt,
    UpdateError,
    UpdateSession,
    applied_session_matches,
    collect_update_inputs,
    operation_digest,
    required_grant_permissions,
    session_matches,
)
from memcommit.application.operations.update.application import prepare_update_application


def _authority_name(binding: GrantedUpdateTarget, public_name: str) -> str:
    if not (
        public_name == binding.public_name
        or public_name.startswith(binding.public_name + "/")
    ):
        raise UpdateError("A planned owner is outside the granted target namespace.")
    return binding.resource_name + public_name[len(binding.public_name) :]


def _public_name(binding: GrantedUpdateTarget, authority_name: str) -> str:
    if not (
        authority_name == binding.resource_name
        or authority_name.startswith(binding.resource_name + "/")
    ):
        raise UpdateError(
            "An authority recovery Context is outside the granted namespace."
        )
    return binding.public_name + authority_name[len(binding.resource_name) :]


@dataclass(frozen=True)
class GrantedUpdateInspection:
    """Read-only status of a saved granted UpdateSession."""

    status: Literal["current", "stale", "revoked"]
    detail: str = ""


def inspect_granted_update(
    active_store: MemoryStore,
    session: UpdateSession,
) -> GrantedUpdateInspection:
    """Revalidate saved endpoint Grants while keeping the diff inspectable."""

    if session.granted_source is None and session.granted_target is None:
        raise ValueError("Expected a granted UpdateSession.")
    try:
        with authority_grant_snapshot_lock() as registry:
            if session.granted_source is None:
                source = load_context_scope(
                    active_store,
                    session.source_name,
                    include_descendants=session.source_include_descendants,
                )
            else:
                source_access = revalidate_granted_context_binding(
                    session.granted_source,
                    required_permission="READ",
                    registry=registry,
                )
                source_reader = GrantedReadStore(
                    source_access,
                    registry=registry,
                )
                source = load_context_scope(
                    source_reader,
                    session.granted_source.public_name,
                    include_descendants=session.source_include_descendants,
                )
            if session.granted_target is None:
                target = load_context_scope(
                    active_store,
                    session.target_name,
                    include_descendants=session.target_include_descendants,
                )
            else:
                target_access = _resolve_exact_access(
                    active_store,
                    session.granted_target,
                    registry,
                )
                target_reader = GrantedReadStore(
                    target_access,
                    registry=registry,
                )
                target = load_context_scope(
                    target_reader,
                    session.granted_target.public_name,
                    include_descendants=session.target_include_descendants,
                )
            fresh = (
                applied_session_matches(
                    session,
                    source,
                    target,
                    granted_source=session.granted_source,
                    granted_target=session.granted_target,
                )
                if session.status == "applied"
                else session_matches(
                    session,
                    source,
                    target,
                    granted_source=session.granted_source,
                    granted_target=session.granted_target,
                )
            )
            return GrantedUpdateInspection(
                status="current" if fresh else "stale"
            )
    except ProfileError as error:
        return GrantedUpdateInspection("revoked", str(error))
    except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
        return GrantedUpdateInspection("stale", str(error))


def _public_restore_result(
    result: CommandRestoreResult,
    binding: GrantedUpdateTarget,
) -> CommandRestoreResult:
    changes = tuple(
        replace(
            change,
            context_name=_public_name(binding, change.context_name),
        )
        for change in result.unit.changes
    )
    return replace(result, unit=replace(result.unit, changes=changes))


def restore_granted_update(
    active_store: MemoryStore,
    session: UpdateSession,
    direction: Literal["undo", "redo"],
) -> CommandRestoreResult:
    """Restore the exact authority command named by a participant receipt."""

    restorable_statuses = {"applied"} if direction == "undo" else {
        "applied",
        "undone",
    }
    if (
        session.status not in restorable_statuses
        or session.granted_target is None
        or session.application is None
    ):
        raise ValueError("Expected one restorable granted UpdateSession.")
    binding = session.granted_target
    expected_unit_uid = (
        f"update:{session.uid}:{session.application.operation_digest}"
    )
    with authority_grant_snapshot_lock() as registry:
        access = _resolve_exact_access(active_store, binding, registry)
        _validate_operation_permissions(session, registry)
        active_store._assert_profile_write_allowed()
        result = access.store.restore_recent_context_command(
            direction,
            expected_unit_uid=expected_unit_uid,
        )
        restored_session = (
            session.with_restored_application(applied=False)
            if direction == "undo"
            else session.with_restored_application(applied=True)
            if session.status == "undone"
            else session
        )
        if restored_session != session:
            try:
                active_store.save_staged_update(
                    restored_session,
                    expected_current=session,
                )
            except Exception:
                # The authority command and participant receipt are one
                # operation. Reverse the just-recorded restoration before
                # exposing a partial cross-Profile result.
                access.store.restore_recent_context_command(
                    "redo" if direction == "undo" else "undo",
                    expected_unit_uid=expected_unit_uid,
                )
                raise
    return _public_restore_result(result, binding)


def _operation_permission(
    operation: EditOperation | AddOperation | RemoveOperation,
) -> str:
    if isinstance(operation, EditOperation):
        return "UPDATE"
    if isinstance(operation, AddOperation):
        return "CREATE"
    return "DELETE"


def _resolve_exact_access(
    active_store: MemoryStore,
    binding: GrantedUpdateTarget,
    registry: ProfileRegistry,
):
    try:
        access = resolve_context_access(
            active_store,
            binding.public_name,
            current_name=binding.attachment_context_name,
            required_permission="READ",
            registry=registry,
        )
    except FileNotFoundError as error:
        # This route starts from a persisted exact Grant binding, so loss of
        # the public route is revocation rather than an ordinary missing input.
        raise ProfileError(
            "The granted update target is no longer available."
        ) from error
    current = freeze_granted_context_binding(access)
    if current != binding:
        raise ConcurrentContextUpdateError(
            "The granted update target changed before application."
        )
    if access.view is None:
        raise UpdateError("Expected a granted update target.")
    authority_source = access.view.authority.source or {}
    if (
        access.view.authority.name.casefold() == "study-baseline"
        or authority_source.get("kind") == "STUDY_BASELINE"
    ):
        raise UpdateError("The fixed study-baseline Profile cannot be updated.")
    return access


def _validate_operation_permissions(
    session: UpdateSession,
    registry: ProfileRegistry,
) -> None:
    binding = session.granted_target
    if binding is None:
        raise UpdateError("Expected a granted update target.")
    if not set(required_grant_permissions(session.operations)).issubset(
        binding.permissions
    ):
        raise ProfileError(
            "The frozen grant does not contain every permission required by "
            "the planned operations."
        )
    for operation in session.operations:
        view = resolve_granted_context_view(
            operation.owner_context_name,
            attachment_name=binding.attachment_context_name,
            required_permission=_operation_permission(operation),
            registry=registry,
        )
        if (
            view.grant.uid != binding.grant_uid
            or view.grant.revision != binding.grant_revision
            or view.authority.uid != binding.authority_profile_uid
            or view.grantee.uid != binding.grantee_profile_uid
        ):
            raise ProfileError(
                "A planned owner is controlled by a different or changed grant."
            )


def _remove_checkpoint(
    store: MemoryStore,
    context_name: str,
    checkpoint_uid: str,
) -> None:
    for path in store._checkpoints_dir(context_name).glob(
        f"*-{checkpoint_uid[:8]}.json"
    ):
        if path.is_symlink() or not path.is_file():
            continue
        with open(path, encoding="utf-8") as file:
            value = json.load(file, object_pairs_hook=_reject_duplicate_json_keys)
        if value.get("uid") == checkpoint_uid:
            path.unlink()
            return
    raise RuntimeError("Update checkpoint could not be found during rollback.")


def apply_granted_staged_update(
    active_store: MemoryStore,
    session: UpdateSession,
) -> UpdateSession:
    """Apply a staged plan while freezing grant and both Profile stores.

    Registry revocation, source drift, permission loss, and authority drift are
    checked under locks before the first authority write. Ordinary exceptions
    restore every authority record and checkpoint already written. As with the
    local multi-owner path, process-crash atomicity still requires a journal.
    """

    if session.status != "staged" or session.granted_target is None:
        raise ValueError("Expected one staged granted UpdateSession.")
    binding = session.granted_target
    source_binding = session.granted_source
    authority_lock_names = {
        _authority_name(binding, context.name)
        for context in session.target_contexts
    }

    with authority_grant_snapshot_lock() as registry:
        access = _resolve_exact_access(active_store, binding, registry)
        _validate_operation_permissions(session, registry)
        authority_store = access.store
        if source_binding is None:
            source_access = None
            source_store = active_store
            source_lock_names = {
                context.name for context in session.source_contexts
            } | {
                source.context_name
                for operation in session.operations
                for source in operation.source_refs
            }
        else:
            source_access = revalidate_granted_context_binding(
                source_binding,
                required_permission="READ",
                registry=registry,
            )
            source_store = source_access.store
            source_lock_names = {
                _authority_name(source_binding, context.name)
                for context in session.source_contexts
            } | {
                _authority_name(source_binding, source.context_name)
                for operation in session.operations
                for source in operation.source_refs
            }

        def load_source() -> Context:
            if source_access is None:
                return load_context_scope(
                    active_store,
                    session.source_name,
                    include_descendants=session.source_include_descendants,
                )
            source_reader = GrantedReadStore(
                source_access,
                registry=registry,
            )
            return load_context_scope(
                source_reader,
                source_binding.public_name,
                include_descendants=session.source_include_descendants,
            )

        with active_store._update_session_write_lock():
            current = active_store._load_update_session(
                active_store.staged_update_file
            )
            if current != session:
                raise ConcurrentContextUpdateError(
                    "The active staged update changed before application."
                )
            active_store._assert_profile_write_allowed()
            with ExitStack() as source_locks:
                if source_store.store_dir != authority_store.store_dir:
                    source_locks.enter_context(
                        source_store._context_write_locks(source_lock_names)
                    )
                with authority_store._command_write_lock():
                    authority_store._assert_profile_write_allowed()
                    combined_authority_locks = set(authority_lock_names)
                    if source_store.store_dir == authority_store.store_dir:
                        combined_authority_locks.update(source_lock_names)
                    with authority_store._context_write_locks(
                        combined_authority_locks
                    ):
                        source = load_source()
                        target_reader = GrantedReadStore(
                            access,
                            registry=registry,
                        )
                        target = load_context_scope(
                            target_reader,
                            binding.public_name,
                            include_descendants=session.target_include_descendants,
                        )
                        if not session_matches(
                            session,
                            source,
                            target,
                            granted_source=source_binding,
                            granted_target=binding,
                        ):
                            raise ConcurrentContextUpdateError(
                                "The update source or granted target changed "
                                "before application."
                            )
                        result = prepare_update_application(session, target)
                        originals: dict[str, dict[str, object]] = {}
                        post_images: dict[str, Context] = {}
                        expected_digests: dict[str, str] = {}
                        for owner in result.affected_owners:
                            authority_name = _authority_name(
                                binding,
                                owner.owner_context_name,
                            )
                            direct = authority_store.load_direct(authority_name)
                            if direct.uid != owner.owner_context_uid:
                                raise ConcurrentContextUpdateError(
                                    "An authority Context identity changed before "
                                    "application."
                                )
                            post_image = Context.from_dict(direct.to_dict())
                            post_image._store_digest = direct._store_digest
                            for operation in session.operations:
                                if operation.owner_context_uid != direct.uid:
                                    continue
                                if isinstance(operation, EditOperation):
                                    post_image.replace(
                                        Memory(
                                            uid=operation.memory_uid,
                                            content=operation.new_content,
                                        )
                                    )
                                elif isinstance(operation, RemoveOperation):
                                    post_image.remove(operation.memory_uid)
                                else:
                                    post_image.add(
                                        Memory(
                                            uid=operation.memory_uid,
                                            content=operation.new_content,
                                        )
                                    )
                            originals[authority_name] = direct.to_dict()
                            post_images[authority_name] = post_image
                            expected_digests[authority_name] = context_record_digest(
                                direct
                            )

                        created_checkpoints: list[tuple[str, str, str]] = []
                        written_names: list[str] = []
                        try:
                            operation_hash = operation_digest(session.operations)
                            for owner in result.affected_owners:
                                public_name = owner.owner_context_name
                                authority_name = _authority_name(binding, public_name)
                                owner_operations = [
                                    operation
                                    for operation in session.operations
                                    if operation.owner_context_uid
                                    == owner.owner_context_uid
                                ]
                                checkpoint = authority_store._save_locked(
                                    post_images[authority_name],
                                    AutoCheckpoint(
                                        command="update",
                                        args={
                                            "update_session_uid": session.uid,
                                            "operation_digest": operation_hash,
                                            "source_context_uid": session.source_uid,
                                            "source_context_name": session.source_name,
                                            "target_context_uid": session.target_uid,
                                            "target_context_name": session.target_name,
                                            "authority_target_context_name": (
                                                binding.authority_context_name
                                            ),
                                            "owner_context_uid": owner.owner_context_uid,
                                            "public_owner_context_name": public_name,
                                            "authority_grant": {
                                                "uid": binding.grant_uid,
                                                "revision": binding.grant_revision,
                                                "grantee_profile_uid": (
                                                    binding.grantee_profile_uid
                                                ),
                                                "public_context": binding.public_name,
                                            },
                                            "granted_source": (
                                                None
                                                if source_binding is None
                                                else source_binding.to_dict()
                                            ),
                                            "operation_memory_uids": [
                                                operation.memory_uid
                                                for operation in owner_operations
                                            ],
                                            # Command history is reconstructed
                                            # inside the authority store, so its
                                            # membership must use physical names.
                                            # Public names remain in the participant
                                            # receipt and presentation layer.
                                            "command_contexts": [
                                                {
                                                    "uid": affected.owner_context_uid,
                                                    "name": _authority_name(
                                                        binding,
                                                        affected.owner_context_name,
                                                    ),
                                                }
                                                for affected in result.affected_owners
                                            ],
                                        },
                                        description=(
                                            "Applied granted semantic update "
                                            f"{session.uid[:8]} from "
                                            f"{session.source_name}."
                                        ),
                                    ),
                                    expected_context_digest=expected_digests[
                                        authority_name
                                    ],
                                )
                                if checkpoint is None:
                                    raise RuntimeError(
                                        "Update application created no checkpoint."
                                    )
                                written_names.append(authority_name)
                                created_checkpoints.append(
                                    (authority_name, public_name, checkpoint.uid)
                                )

                            source_after = load_source()
                            target_reader_after = GrantedReadStore(
                                access,
                                registry=registry,
                            )
                            target_after = load_context_scope(
                                target_reader_after,
                                binding.public_name,
                                include_descendants=(
                                    session.target_include_descendants
                                ),
                            )
                            inputs_after = collect_update_inputs(
                                source_after,
                                target_after,
                            )
                            checkpoint_by_public = {
                                public: checkpoint_uid
                                for _authority, public, checkpoint_uid
                                in created_checkpoints
                            }
                            receipt = UpdateApplicationReceipt(
                                applied_at=datetime.now().astimezone().isoformat(),
                                operation_digest=operation_hash,
                                target_digest=inputs_after.target_digest,
                                target_contexts=(
                                    inputs_after.target_context_fingerprints
                                ),
                                checkpoints=tuple(
                                    UpdateCheckpointReceipt(
                                        context_uid=owner.owner_context_uid,
                                        context_name=owner.owner_context_name,
                                        checkpoint_uid=checkpoint_by_public[
                                            owner.owner_context_name
                                        ],
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
                                granted_target=binding,
                            ):
                                raise RuntimeError(
                                    "Applied authority target does not match its "
                                    "receipt."
                                )
                            active_store._save_active_terminal_update(applied)
                        except Exception:
                            rollback_error: Exception | None = None
                            for name in written_names:
                                try:
                                    _write_json_atomic(
                                        authority_store._context_file(name),
                                        originals[name],
                                    )
                                except Exception as candidate:
                                    rollback_error = rollback_error or candidate
                            for name, _public, checkpoint_uid in created_checkpoints:
                                try:
                                    _remove_checkpoint(
                                        authority_store,
                                        name,
                                        checkpoint_uid,
                                    )
                                except Exception as candidate:
                                    rollback_error = rollback_error or candidate
                            if rollback_error is not None:
                                raise RuntimeError(
                                    "Granted update failed and the authority "
                                    "target could not be fully rolled back."
                                ) from rollback_error
                            raise
    return applied
