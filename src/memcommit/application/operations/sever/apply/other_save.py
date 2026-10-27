"""Apply, recover, and compensate legacy require-new Result Contexts."""

from __future__ import annotations

import uuid

from memcommit.application.operations.sever.application import (
    SeverApplicationError,
)
from memcommit.application.operations.sever.apply.checkpoints import (
    build_checkpoint_command_details,
    checkpoint_command_details_match,
)
from memcommit.application.operations.sever.apply.projection import (
    result_context,
)
from memcommit.application.operations.sever.model import (
    SeverApplication,
    SeverSession,
)
from memcommit.persistence.store.checkpoint.requests import AutoCheckpointRequest
from memcommit.persistence.store import (
    ProfileStore,
    context_record_digest,
)


def recover_other_save(
    store: ProfileStore, session: SeverSession
) -> SeverSession | None:
    """Adopt only an untouched Result produced by this exact review.

    A process can stop after the atomic Context/checkpoint creation but
    before the private session CAS. The exact checkpoint is sufficient to
    restore that missing receipt; an unrelated occupant remains an ordinary
    require-new name collision.
    """

    if not store.context_exists(session.output_name):
        return None
    current = store.load_direct(session.output_name)
    expected, result_uids, sources = result_context(
        session,
        output_uid=current.uid,
    )
    if context_record_digest(current) != context_record_digest(expected):
        return None
    checkpoints = store.list_checkpoints(session.output_name)
    if len(checkpoints) != 1:
        return None
    checkpoint = checkpoints[0]
    expected_args = build_checkpoint_command_details(session, expected, sources)
    if (
        checkpoint.get("command") != "sever"
        or not checkpoint_command_details_match(
            checkpoint.get("command_details"), expected_args, save_mode=session.save_mode
        )
        or not isinstance(checkpoint.get("uid"), str)
    ):
        return None
    return session.with_application(
        SeverApplication(
            output_context_uid=current.uid,
            checkpoint_uid=checkpoint["uid"],
            result_memory_uids=result_uids,
        )
    )


def materialize_other_save(
    store: ProfileStore,
    session: SeverSession,
    *,
    expected_context_catalog: tuple[str, ...],
) -> SeverSession:
    output, result_uids, sources = result_context(
        session,
        output_uid=str(uuid.uuid4()),
    )

    local_bindings = tuple(
        dict.fromkeys((*session.source.contexts, *session.criteria.contexts))
    )
    auto_checkpoint = AutoCheckpointRequest(
        command="sever",
        command_details=build_checkpoint_command_details(session, output, sources),
    )
    checkpoint = store.create_context_with_sources(
        output,
        auto_checkpoint,
        source_bindings=local_bindings,
        expected_context_catalog=expected_context_catalog,
    )
    if checkpoint is None:
        raise SeverApplicationError("Sever output creation produced no checkpoint.")
    return session.with_application(
        SeverApplication(
            output_context_uid=output.uid,
            checkpoint_uid=checkpoint.uid,
            result_memory_uids=result_uids,
        )
    )


def rollback_other_save(store: ProfileStore, applied: SeverSession) -> None:
    """Compensate only the exact save named by an uncommitted receipt."""

    application = applied.application
    if applied.state != "APPLIED" or application is None:
        raise SeverApplicationError(
            "Only an applied Sever receipt can roll back its Result."
        )
    expected, expected_uids, _sources = result_context(
        applied,
        output_uid=application.output_context_uid,
    )
    if expected_uids != application.result_memory_uids:
        raise SeverApplicationError(
            "The Sever receipt does not identify its exact Result Memories."
        )
    expected_digest = context_record_digest(expected)

    # This is compensation for an outcome that never committed, not a
    # user-visible deletion. Hold the same Store boundaries as creation
    # and intentionally avoid publishing a lifecycle event.
    with store._context_graph_lock(exclusive=False):  # noqa: SLF001
        with store._context_write_lock(applied.output_name):  # noqa: SLF001
            current = store.load_direct(applied.output_name)
            if (
                current.uid != application.output_context_uid
                or context_record_digest(current) != expected_digest
            ):
                raise SeverApplicationError(
                    "The new Sever Result changed before rollback."
                )
            checkpoints = store.list_checkpoints(applied.output_name)
            if (
                len(checkpoints) != 1
                or checkpoints[0].get("uid") != application.checkpoint_uid
            ):
                raise SeverApplicationError(
                    "The new Sever Result checkpoint changed before rollback."
                )
            store._delete_locked(applied.output_name)  # noqa: SLF001
