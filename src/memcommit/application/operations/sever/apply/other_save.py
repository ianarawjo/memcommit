"""Apply, recover, and compensate legacy require-new Result Contexts."""

from __future__ import annotations

import uuid

from memcommit.application.operations.sever.application import (
    SeverApplicationError,
)
from memcommit.application.operations.sever.apply.checkpoints import (
    build_checkpoint_args,
    checkpoint_args_match,
)
from memcommit.application.operations.sever.apply.projection import (
    result_context,
)
from memcommit.application.operations.sever.model import (
    SeverApplication,
    SeverSession,
)
from memcommit.core.context import (
    AutoCheckpoint,
)
from memcommit.persistence.store import (
    MemoryStore,
    context_record_digest,
)


def recover_other_save(
    store: MemoryStore, session: SeverSession
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
    expected_args = build_checkpoint_args(session, expected, sources)
    if (
        checkpoint.get("command") != "sever"
        or not checkpoint_args_match(
            checkpoint.get("args"), expected_args, save_mode=session.save_mode
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


def materialize_other_save(store: MemoryStore, session: SeverSession) -> SeverSession:
    output, result_uids, sources = result_context(
        session,
        output_uid=str(uuid.uuid4()),
    )

    local_bindings: list[tuple[str, str, str]] = []
    for binding in (session.source, session.criteria):
        if binding.granted is None:
            local_bindings.extend(binding.contexts)
    deduplicated = tuple(dict.fromkeys(local_bindings))
    auto_checkpoint = AutoCheckpoint(
        command="sever",
        args=build_checkpoint_args(session, output, sources),
        description=(
            f"Created local Sever result '{session.output_name}' from "
            f"'{session.source.root_name}' under '{session.criteria.root_name}'; "
            "source unchanged"
        ),
    )
    if deduplicated:
        checkpoint = store.create_context_with_sources(
            output,
            auto_checkpoint,
            source_bindings=deduplicated,
        )
    else:
        # Granted frames are retained snapshots and have no local Context
        # path to lock while the require-new local output is published.
        checkpoint = store.create_context(output, auto_checkpoint)
    if checkpoint is None:
        raise SeverApplicationError("Sever output creation produced no checkpoint.")
    return session.with_application(
        SeverApplication(
            output_context_uid=output.uid,
            checkpoint_uid=checkpoint.uid,
            result_memory_uids=result_uids,
        )
    )


def rollback_other_save(store: MemoryStore, applied: SeverSession) -> None:
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
    with store._command_write_lock():  # noqa: SLF001
        with store._context_graph_lock(exclusive=False):  # noqa: SLF001
            with store._context_write_lock(applied.output_name):  # noqa: SLF001
                with store.profile_write_guard():
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
