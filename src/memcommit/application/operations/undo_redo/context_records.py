"""Prepare the prior or subsequent images of a selected existing-Context command."""

import uuid

from memcommit.application.capabilities.command_recovery.model import (
    CommandRestoreResult,
)
from memcommit.application.capabilities.command_recovery.restore_receipt import (
    command_restore_metadata,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)
from memcommit.persistence.store.context_memory.records import context_record_digest
from memcommit.persistence.store.saving.command_restoration.context_records import (
    save_restored_contexts,
)
from .companion_sessions import prepare_sever_command_restore


def restore_existing_contexts(store, unit, direction) -> CommandRestoreResult:
    names = tuple(change.context_name for change in unit.changes)
    receipt_uid = str(uuid.uuid4())
    restore_metadata = command_restore_metadata(
        receipt_uid=receipt_uid, direction=direction, unit=unit
    )
    original_records = {}
    # Selection, validation, publication and rollback share the original lock span.
    with store._context_graph_lock(exclusive=False):
        with store._context_write_locks(names):
            for change in unit.changes:
                try:
                    current = store.load_direct(change.context_name)
                except FileNotFoundError as error:
                    raise ConcurrentContextUpdateError(
                        f"Affected Context '{change.context_name}' no longer exists."
                    ) from error
                expected = change.after if direction == "undo" else change.before
                if current.uid != change.context_uid or context_record_digest(
                    current
                ) != context_record_digest(expected):
                    raise ConcurrentContextUpdateError(
                        f"Affected Context '{change.context_name}' changed "
                        f"after the command selected for {direction}."
                    )
                original_records[change.context_name] = current.to_dict()

            companion_sessions = None
            companion_session_restore = None
            if unit.command == "sever":
                from memcommit.application.operations.sever.session_store import (
                    SeverSessionStore,
                )

                companion_sessions = SeverSessionStore(store)
                companion_session_restore = prepare_sever_command_restore(
                    store, unit, direction, companion_sessions
                )
            target_records = tuple(
                (
                    change.context_name,
                    change.context_uid,
                    change.before if direction == "undo" else change.after,
                )
                for change in unit.changes
            )
            checkpoints = save_restored_contexts(
                store,
                target_records,
                original_records,
                AutoCheckpointRequest(
                    command=direction,
                    command_details={"command_restore": restore_metadata},
                ),
                companion_session_restore,
                companion_sessions,
            )
    return CommandRestoreResult(unit, direction, receipt_uid, checkpoints)
