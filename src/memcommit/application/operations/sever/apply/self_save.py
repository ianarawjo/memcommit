"""Apply, recover, and compensate an exact in-place Source-owner batch."""

from __future__ import annotations

from dataclasses import replace

from memcommit.application.operations.sever.application import (
    SeverApplicationError,
)
from memcommit.application.operations.sever.apply.checkpoints import (
    build_checkpoint_args,
    checkpoint_args_match,
)
from memcommit.application.operations.sever.apply.projection import (
    self_save_contexts,
    self_save_source_receipts,
)
from memcommit.application.operations.sever.model import (
    SeverApplication,
    SeverCheckpointReceipt,
    SeverSession,
)
from memcommit.core.context import (
    AutoCheckpoint,
    Context,
)
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.persistence.store import (
    MemoryStore,
    _write_json_atomic,
    context_record_digest,
)


def recover_self_save(store: MemoryStore, session: SeverSession) -> SeverSession | None:
    """Adopt an exact self-save committed before its session receipt."""

    source_receipts = self_save_source_receipts(session)
    checkpoints: list[dict[str, object]] = []
    originals: list[Context] = []
    snapshots: list[Context] = []
    for name, _uid, _digest in source_receipts:
        matches = []
        for checkpoint in store.list_checkpoints(name):
            args = checkpoint.get("args")
            sever = args.get("sever") if isinstance(args, dict) else None
            if (
                checkpoint.get("command") == "sever"
                and isinstance(checkpoint.get("uid"), str)
                and isinstance(checkpoint.get("command_before"), dict)
                and isinstance(checkpoint.get("snapshot"), dict)
                and isinstance(sever, dict)
                and sever.get("session_uid") == session.uid
            ):
                matches.append(checkpoint)
        if len(matches) != 1:
            return None
        checkpoint = matches[0]
        try:
            originals.append(Context.from_dict(checkpoint["command_before"]))
            snapshots.append(Context.from_dict(checkpoint["snapshot"]))
        except (KeyError, TypeError, ValueError):
            return None
        checkpoints.append(checkpoint)

    try:
        expected, result_uids, sources = self_save_contexts(
            session,
            tuple(originals),
        )
    except (SeverApplicationError, TypeError, ValueError):
        return None
    expected_args = build_checkpoint_args(session, expected[0], sources)
    current = tuple(store.load_direct(name) for name, _uid, _digest in source_receipts)
    if any(
        not checkpoint_args_match(
            checkpoint.get("args"), expected_args, save_mode=session.save_mode
        )
        or snapshot.uid != output.uid
        or context_record_digest(snapshot) != context_record_digest(output)
        or live.uid != output.uid
        or context_record_digest(live) != context_record_digest(output)
        for checkpoint, snapshot, live, output in zip(
            checkpoints,
            snapshots,
            current,
            expected,
        )
    ):
        return None
    receipts = tuple(
        SeverCheckpointReceipt(
            context_uid=output.uid,
            context_name=output.name,
            checkpoint_uid=checkpoint["uid"],
        )
        for output, checkpoint in zip(expected, checkpoints)
    )
    return session.with_application(
        SeverApplication(
            output_context_uid=receipts[0].context_uid,
            checkpoint_uid=receipts[0].checkpoint_uid,
            result_memory_uids=result_uids,
            checkpoints=receipts,
        )
    )


def materialize_self_save(store: MemoryStore, session: SeverSession) -> SeverSession:
    """Apply the reviewed projection to every Source owner in place."""

    source_receipts = self_save_source_receipts(session)
    source_names = {name for name, _uid, _digest in source_receipts}
    catalog = tuple(store.list_context_names())
    if session.source.include_descendants:
        live_lexical_names = expand_lexical_context_names(
            ContextScope.create(
                (session.source.root_name,),
                include_descendants=True,
            ),
            catalog,
        )
        if not set(live_lexical_names) <= source_names:
            raise SeverApplicationError(
                "The Source Context subtree changed after review. Re-run Sever."
            )
    elif source_receipts != (
        (
            session.source.root_name,
            session.source.root_uid,
            session.source.contexts[0][2],
        ),
    ):
        raise SeverApplicationError(
            "A direct in-place Sever must bind exactly its Source root."
        )

    originals = tuple(
        store.load_direct(name) for name, _uid, _digest in source_receipts
    )
    outputs, result_uids, sources = self_save_contexts(
        session,
        originals,
    )
    command_args = build_checkpoint_args(session, outputs[0], sources)
    description = (
        f"Severed Source scope '{session.source.root_name}' in place under "
        f"'{session.criteria.root_name}': {len(source_receipts)} Contexts, "
        f"{len(result_uids)} kept, "
        f"{len(session.candidates) - len(result_uids)} forgotten"
    )
    criteria_bindings = (
        session.criteria.contexts if session.criteria.granted is None else ()
    )
    checkpoints = store.save_context_command_batch(
        tuple(
            (
                output,
                AutoCheckpoint(
                    command="sever",
                    args=command_args,
                    description=description,
                ),
                expected_digest,
            )
            for output, (_name, _uid, expected_digest) in zip(
                outputs,
                source_receipts,
            )
        ),
        source_bindings=criteria_bindings,
        expected_context_catalog=(
            catalog if session.source.include_descendants else None
        ),
    )
    receipts = tuple(
        SeverCheckpointReceipt(
            context_uid=output.uid,
            context_name=output.name,
            checkpoint_uid=checkpoint.uid,
        )
        for output, checkpoint in zip(outputs, checkpoints)
    )
    if not receipts or receipts[0].context_uid != session.source.root_uid:
        raise SeverApplicationError(
            "In-place Sever produced no primary Source checkpoint."
        )
    return session.with_application(
        SeverApplication(
            output_context_uid=receipts[0].context_uid,
            checkpoint_uid=receipts[0].checkpoint_uid,
            result_memory_uids=result_uids,
            checkpoints=receipts,
        )
    )


def rollback_self_save(store: MemoryStore, applied: SeverSession) -> None:
    """Restore every exact Source-owner pre-image after failed persistence."""

    application = applied.application
    if application is None:
        raise SeverApplicationError("Self-save rollback requires an application.")
    reviewed = replace(
        applied,
        revision=applied.revision - 1,
        state="REVIEWING",
        application=None,
    )
    source_receipts = self_save_source_receipts(reviewed)
    if application.checkpoints:
        receipt_by_name = {
            receipt.context_name: receipt for receipt in application.checkpoints
        }
        if tuple(receipt_by_name) != tuple(
            name for name, _uid, _digest in source_receipts
        ):
            raise SeverApplicationError(
                "The in-place Sever receipt does not cover its Source owners."
            )
    elif len(source_receipts) == 1:
        name, uid, _digest = source_receipts[0]
        receipt_by_name = {
            name: SeverCheckpointReceipt(
                context_uid=uid,
                context_name=name,
                checkpoint_uid=application.checkpoint_uid,
            )
        }
    else:
        raise SeverApplicationError(
            "Recursive in-place Sever requires owner checkpoint receipts."
        )

    names = tuple(name for name, _uid, _digest in source_receipts)
    with store._command_write_lock():  # noqa: SLF001
        with store._context_graph_lock(  # noqa: SLF001
            exclusive=reviewed.source.include_descendants
        ):
            if reviewed.source.include_descendants:
                live_lexical_names = expand_lexical_context_names(
                    ContextScope.create(
                        (reviewed.source.root_name,),
                        include_descendants=True,
                    ),
                    store.list_context_names(),
                )
                if not set(live_lexical_names) <= set(names):
                    raise SeverApplicationError(
                        "The Source subtree changed before rollback."
                    )
            with store._context_write_locks(names):  # noqa: SLF001
                with store.profile_write_guard():
                    current: list[Context] = []
                    checkpoints: list[dict[str, object]] = []
                    originals: list[Context] = []
                    snapshots: list[Context] = []
                    for name in names:
                        live = store.load_direct(name)
                        receipt = receipt_by_name[name]
                        checkpoint = next(
                            (
                                item
                                for item in store.list_checkpoints(name)
                                if item.get("uid") == receipt.checkpoint_uid
                            ),
                            None,
                        )
                        before = (
                            checkpoint.get("command_before")
                            if isinstance(checkpoint, dict)
                            else None
                        )
                        snapshot = (
                            checkpoint.get("snapshot")
                            if isinstance(checkpoint, dict)
                            else None
                        )
                        if not isinstance(before, dict) or not isinstance(
                            snapshot,
                            dict,
                        ):
                            raise SeverApplicationError(
                                "An in-place checkpoint cannot restore its owner."
                            )
                        current.append(live)
                        checkpoints.append(checkpoint)
                        originals.append(Context.from_dict(before))
                        snapshots.append(Context.from_dict(snapshot))

                    expected, result_uids, sources = self_save_contexts(
                        reviewed,
                        tuple(originals),
                    )
                    expected_args = build_checkpoint_args(
                        reviewed,
                        expected[0],
                        sources,
                    )
                    if application.result_memory_uids != result_uids or any(
                        live.uid != output.uid
                        or snapshot.uid != output.uid
                        or context_record_digest(live) != context_record_digest(output)
                        or context_record_digest(snapshot)
                        != context_record_digest(output)
                        or not checkpoint_args_match(
                            checkpoint.get("args"),
                            expected_args,
                            save_mode=reviewed.save_mode,
                        )
                        for live, snapshot, output, checkpoint in zip(
                            current,
                            snapshots,
                            expected,
                            checkpoints,
                        )
                    ):
                        raise SeverApplicationError(
                            "The in-place Sever result changed before rollback."
                        )

                    written: list[Context] = []
                    try:
                        for original in originals:
                            _write_json_atomic(
                                store._context_file(original.name),  # noqa: SLF001
                                original.to_dict(),
                            )
                            written.append(original)
                        for name in names:
                            store._remove_checkpoint_uid_locked(  # noqa: SLF001
                                name,
                                receipt_by_name[name].checkpoint_uid,
                            )
                    except Exception:
                        for output in expected[: len(written)]:
                            _write_json_atomic(
                                store._context_file(output.name),  # noqa: SLF001
                                output.to_dict(),
                            )
                        raise
