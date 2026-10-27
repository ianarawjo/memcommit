"""Prepare operation-owned records coupled to a creation with new ancestors."""

import json
from dataclasses import replace


def prepare_creation_companion_changes(store, unit, direction, archive):
    if unit.command not in {"sever", "atomize"}:
        return ()
    if direction == "redo":
        if unit.command == "atomize":
            receipt = unit.checkpoint_command_details[0]["atomize_save_as"]
            analysis = store.load_atomize_analysis(receipt["source_context"]["uid"])
            if analysis is None or analysis.uid != receipt["source_analysis_uid"]:
                raise ValueError("Source Atomize analysis changed before Redo.")
        records = json.loads((archive / "companion-records.json").read_text())
        changes = []
        for record in records:
            path = store.store_dir / record["path"]
            if not path.resolve().is_relative_to(store.store_dir.resolve()):
                raise ValueError("Creation companion is outside the Store.")
            actual = path.read_text() if path.exists() else None
            if actual != record["after"]:
                raise ValueError("Creation companion changed before Redo.")
            changes.append((path, record["after"], record["before"]))
        return tuple(changes)

    creation = next(
        details["context_creation"] for details in unit.checkpoint_command_details
    )
    change = next(
        change
        for change in unit.changes
        if change.context_uid == creation["context_uid"]
    )
    if unit.command == "sever":
        from memcommit.application.operations.sever.session_store import (
            SeverSessionStore,
        )

        details = next(details["sever"] for details in unit.checkpoint_command_details)
        sessions = SeverSessionStore(store)
        session = sessions.load(details["session_uid"])
        application = session.application
        if (
            application is None
            or session.state != "APPLIED"
            or application.output_context_uid != change.context_uid
            or application.checkpoint_uid != change.checkpoint_uid
        ):
            raise ValueError(
                "Sever session does not match the creation being restored."
            )
        reviewing = session.clear_application(
            output_context_uid=change.context_uid,
            checkpoint_uid=change.checkpoint_uid,
        )
        path = sessions._path(session.uid)
        return (
            (
                path,
                path.read_text(),
                json.dumps(reviewing.to_dict(), ensure_ascii=False, indent=2),
            ),
        )

    from memcommit.persistence.store.loading.atomize_archive_records import (
        load_creation_receipt,
    )
    from .atomize.preparation import prepare_undo

    receipt = load_creation_receipt(store.list_checkpoints(change.context_name), change)
    prepared = prepare_undo(
        store,
        replace(unit, changes=(change,)),
        store.load_direct(change.context_name),
        receipt,
    )
    analysis_path = store._atomize_analysis_path(change.context_uid)
    changes = [(analysis_path, analysis_path.read_text(), None)]
    if prepared.workbench_after is not None:
        path = store._atomize_workbench_path(receipt.source_context_uid)
        changes.append(
            (
                path,
                path.read_text(),
                json.dumps(
                    prepared.workbench_after.to_dict(), ensure_ascii=False, indent=2
                ),
            )
        )
    return tuple(changes)
