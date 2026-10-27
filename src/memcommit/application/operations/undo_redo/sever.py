"""Prepare Sever Context and review-session state for Undo or Redo."""

from __future__ import annotations

import uuid

from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.context_memory.records import context_record_digest

from memcommit.persistence.store.saving.command_restoration.sever import (
    save_sever_undo,
    save_sever_redo,
)


def restore_sever_context_creation(store, unit, direction: str):
    """Undo/Redo one Sever output creation and its saved review.

    Undo moves the complete Context record and checkpoint directory into a
    private command archive instead of destroying them. Redo can therefore
    restore the same identity and history, including every restoration
    receipt, without copying Memory text into lifecycle metadata.
    """
    from memcommit.application.capabilities.command_recovery import (
        CommandRestoreResult,
        command_restore_metadata,
    )
    from memcommit.application.operations.sever.model import (
        SeverApplication,
        sever_record_digest,
    )
    from memcommit.application.operations.sever.session_store import (
        SeverSessionStore,
    )

    if (
        unit.command != "sever"
        or len(unit.changes) != 1
        or unit.changes[0].before is not None
        or unit.changes[0].after is None
    ):
        raise ValueError(
            "Only an exact Sever Context creation can use lifecycle restoration."
        )
    change = unit.changes[0]
    receipt_uid = str(uuid.uuid4())
    restore_metadata = command_restore_metadata(
        receipt_uid=receipt_uid,
        direction=direction,
        unit=unit,
    )
    sessions = SeverSessionStore(store)
    checkpoint: Checkpoint | None = None

    with store._context_graph_lock(exclusive=True):
        with store._context_write_lock(change.context_name):
            if direction == "undo":
                try:
                    current = store.load_direct(change.context_name)
                except FileNotFoundError as error:
                    raise ConcurrentContextUpdateError(
                        f"Affected Context '{change.context_name}' no longer exists."
                    ) from error
                if current.uid != change.context_uid or context_record_digest(
                    current
                ) != context_record_digest(change.after):
                    raise ConcurrentContextUpdateError(
                        f"Affected Context '{change.context_name}' changed "
                        "after the command selected for undo."
                    )
                source_checkpoint = next(
                    (
                        entry
                        for entry in store.list_checkpoints(change.context_name)
                        if entry.get("uid") == change.checkpoint_uid
                    ),
                    None,
                )
                args = (
                    source_checkpoint.get("command_details")
                    if isinstance(source_checkpoint, dict)
                    else None
                )
                sever_receipt = args.get("sever") if isinstance(args, dict) else None
                session_uid = (
                    sever_receipt.get("session_uid")
                    if isinstance(sever_receipt, dict)
                    else None
                )
                if not isinstance(session_uid, str) or not session_uid:
                    raise ValueError("Sever checkpoint has no valid session receipt.")
                session = sessions.load(session_uid)
                application = session.application
                if (
                    session.state != "APPLIED"
                    or application is None
                    or session.output_name != change.context_name
                    or application.output_context_uid != change.context_uid
                    or application.checkpoint_uid != change.checkpoint_uid
                    or tuple(current.memories) != application.result_memory_uids
                ):
                    raise ValueError(
                        "Sever session does not match the restored command."
                    )
                reviewing = session.clear_application(
                    output_context_uid=change.context_uid,
                    checkpoint_uid=change.checkpoint_uid,
                )
                session_before_digest = sever_record_digest(session)
                reviewing_digest = sever_record_digest(reviewing)
                checkpoint = save_sever_undo(
                    store,
                    change,
                    current,
                    restore_metadata,
                    sessions,
                    session,
                    reviewing,
                    session_before_digest,
                    reviewing_digest,
                    manifest=(
                        {
                            "version": 1,
                            "command": "sever",
                            "unit_uid": unit.uid,
                            "context_uid": change.context_uid,
                            "context_name": change.context_name,
                            "checkpoint_uid": change.checkpoint_uid,
                            "session_uid": session.uid,
                            "application": application.to_dict(),
                            "reviewing_session_digest": reviewing_digest,
                        }
                    ),
                )
            else:
                if store.context_exists(change.context_name):
                    raise ConcurrentContextUpdateError(
                        f"Affected Context '{change.context_name}' already exists."
                    )
                archive, manifest, archived_context, _entries = (
                    store._load_command_context_archive(change.checkpoint_uid)
                )
                if (
                    archived_context.uid != change.context_uid
                    or archived_context.name != change.context_name
                    or context_record_digest(archived_context)
                    != context_record_digest(change.after)
                ):
                    raise ConcurrentContextUpdateError(
                        "The archived Sever result changed before Redo."
                    )
                session_uid = manifest["session_uid"]
                assert isinstance(session_uid, str)
                session = sessions.load(session_uid)
                if sever_record_digest(session) != manifest["reviewing_session_digest"]:
                    raise ConcurrentContextUpdateError(
                        "The Sever session changed before Redo."
                    )
                application = SeverApplication.from_dict(manifest["application"])
                applied = session.with_application(application)
                session_before_digest = sever_record_digest(session)
                checkpoint = save_sever_redo(
                    store,
                    change,
                    archive,
                    archived_context,
                    restore_metadata,
                    sessions,
                    applied,
                    session_before_digest,
                )
    assert checkpoint is not None
    return CommandRestoreResult(
        unit=unit,
        direction=direction,
        receipt_uid=receipt_uid,
        checkpoints=(checkpoint,),
    )
