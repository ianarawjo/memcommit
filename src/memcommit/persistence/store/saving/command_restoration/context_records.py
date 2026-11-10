"""Save prepared Context images and their companion session as one attempt."""

from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic

from .companion_sessions import write_companion_session_restore


def save_restored_contexts(
    store,
    target_records,
    original_records,
    checkpoint_request,
    companion_session_restore=None,
    companion_sessions=None,
) -> tuple[Checkpoint, ...]:
    """Publish prepared images; the caller retains command/graph/Context locks."""
    created_checkpoints: list[tuple[str, Checkpoint]] = []
    written_names: list[str] = []
    companion_session_written = False
    try:
        for context_name, context_uid, target_record in target_records:
            restored = store._context_for_restoration(
                target_record,
                context_uid=context_uid,
                context_name=context_name,
            )
            checkpoint = store._save_locked(
                restored,
                checkpoint_request,
            )
            if checkpoint is None:
                raise RuntimeError("Command restoration created no checkpoint.")
            written_names.append(context_name)
            created_checkpoints.append((context_name, checkpoint))
        if companion_session_restore is not None:
            session_path, _session_before, session_after = companion_session_restore
            write_companion_session_restore(
                store,
                session_path,
                expected=_session_before,
                value=session_after,
                sever_sessions=companion_sessions,
            )
            companion_session_written = True
    except Exception:
        rollback_error: Exception | None = None
        if companion_session_written and companion_session_restore is not None:
            try:
                session_path, session_before, _session_after = companion_session_restore
                write_companion_session_restore(
                    store,
                    session_path,
                    expected=_session_after,
                    value=session_before,
                    sever_sessions=companion_sessions,
                )
            except Exception as candidate:  # noqa: BLE001 -- Finish all inverses before reporting failure.
                rollback_error = rollback_error or candidate
        for name in written_names:
            try:
                _write_json_atomic(
                    store._context_file(name),
                    original_records[name],
                )
            except Exception as candidate:  # noqa: BLE001 -- Finish all inverses before reporting failure.
                rollback_error = rollback_error or candidate
        for name, checkpoint in created_checkpoints:
            try:
                try:
                    store._remove_checkpoint_uid_locked(name, checkpoint.uid)
                except RuntimeError as error:
                    # Preserve this restoration route's missing-checkpoint cause.
                    raise RuntimeError(
                        "Restoration checkpoint could not be found during rollback."
                    ) from error
            except Exception as candidate:  # noqa: BLE001 -- Finish all inverses before reporting failure.
                rollback_error = rollback_error or candidate
        if rollback_error is not None:
            raise RuntimeError(
                "Command restoration failed and its Contexts "
                "could not be fully rolled back."
            ) from rollback_error
        raise

    return tuple(checkpoint for _, checkpoint in created_checkpoints)
