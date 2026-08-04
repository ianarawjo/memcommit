"""Apply one frozen granted UpdateSession to its authority-owned Contexts."""

from __future__ import annotations

import json
from datetime import datetime

from memcommit.commands.granted_context import (
    GrantedReadStore,
    freeze_granted_update_target,
    resolve_context_access,
)
from memcommit.context import Context, Memory
from memcommit.profile_config import ProfileRegistry
from memcommit.profiles import (
    ProfileError,
    authority_grant_snapshot_lock,
    resolve_granted_context_view,
)
from memcommit.store import (
    AutoCheckpoint,
    ConcurrentContextUpdateError,
    MemoryStore,
    _reject_duplicate_json_keys,
    _write_json_atomic,
    context_record_digest,
)
from memcommit.update import (
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
from memcommit.update_application import prepare_update_application


def _authority_name(binding: GrantedUpdateTarget, public_name: str) -> str:
    if not (
        public_name == binding.public_name
        or public_name.startswith(binding.public_name + "/")
    ):
        raise UpdateError("A planned owner is outside the granted target namespace.")
    return binding.resource_name + public_name[len(binding.public_name) :]


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
    access = resolve_context_access(
        active_store,
        binding.public_name,
        current_name=binding.attachment_context_name,
        required_permission="READ",
        registry=registry,
    )
    current = freeze_granted_update_target(access)
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
    source_lock_names = {
        context.name for context in session.source_contexts
    } | {
        source.context_name
        for operation in session.operations
        for source in operation.source_refs
    }
    authority_lock_names = {
        _authority_name(binding, context.name)
        for context in session.target_contexts
    }

    with authority_grant_snapshot_lock() as registry:
        access = _resolve_exact_access(active_store, binding, registry)
        _validate_operation_permissions(session, registry)
        authority_store = access.store
        with active_store._update_session_write_lock():
            current = active_store._load_update_session(
                active_store.staged_update_file
            )
            if current != session:
                raise ConcurrentContextUpdateError(
                    "The active staged update changed before application."
                )
            active_store._assert_profile_write_allowed()
            with active_store._context_write_locks(source_lock_names):
                with authority_store._command_write_lock():
                    authority_store._assert_profile_write_allowed()
                    with authority_store._context_write_locks(authority_lock_names):
                        source = active_store.load(session.source_name)
                        target = GrantedReadStore(
                            access,
                            registry=registry,
                        ).load(binding.public_name)
                        if not session_matches(
                            session,
                            source,
                            target,
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
                                            "operation_memory_uids": [
                                                operation.memory_uid
                                                for operation in owner_operations
                                            ],
                                            "command_contexts": [
                                                {
                                                    "uid": affected.owner_context_uid,
                                                    "name": affected.owner_context_name,
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

                            source_after = active_store.load(session.source_name)
                            target_after = GrantedReadStore(
                                access,
                                registry=registry,
                            ).load(binding.public_name)
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
                                granted_target=binding,
                            ):
                                raise RuntimeError(
                                    "Applied authority target does not match its "
                                    "receipt."
                                )
                            active_store._save_update_session(
                                active_store.staged_update_file,
                                applied,
                            )
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
