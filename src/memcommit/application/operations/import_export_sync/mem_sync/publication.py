"""Publish accepted external edits through existing Context batch persistence."""

import copy
import json
from dataclasses import replace
from datetime import datetime
from uuid import uuid4

from memcommit.application.operations.import_export_sync.mem_sync.model import (
    SyncResult,
)
from memcommit.models.context import Context
from memcommit.persistence.import_export.source import (
    read_project_documents,
)
from memcommit.persistence.operations.mem_sync.publication import (
    publish_sync_files,
    encode_bytes,
)
from memcommit.persistence.operations.mem_sync.run_repository import (
    SyncRunRepository,
    sync_record_path,
)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def publish_profile_changes(
    store,
    project_root_dir,
    plan,
    *,
    restoration=None,
):
    """Publish one fully validated frame without a durable pending publication."""
    frame = plan.profile_changes
    changed_files = any(
        effect.action != "UNCHANGED"
        and not (
            effect.action == "REMOVE"
            and dict(export.previous_hashes)[effect.path] is None
        )
        for export in plan.exports
        for effect in export.effects
    )
    operation_uid = str(uuid4())
    timestamp = datetime.now().isoformat()
    names = set(record["name"] for record in frame.before_records)
    names.update(change.after["name"] for change in frame.changes if change.after)
    with (
        store._context_graph_lock(exclusive=True),
        store._context_write_locks(names),
        store._state_write_lock(),
    ):
        records, checkpoints = _validate_profile_inputs(
            store, project_root_dir, plan, restoration
        )
        changes_by_uid = {
            (change.after or change.before)["uid"]: change for change in frame.changes
        }
        checkpoint_changes = dict(changes_by_uid)
        if restoration is None:
            from .model import SyncContextChange

            for _uid, baseline in plan.baselines:
                for member in baseline.members:
                    checkpoint_changes.setdefault(
                        member["uid"], SyncContextChange(member, member, "UNCHANGED")
                    )
        checkpoint_records = _prepare_sync_checkpoints(
            store,
            checkpoint_changes,
            operation_uid,
            restoration,
        )
        checkpoint_uids = {
            uid: record["uid"] for uid, record in checkpoint_records.items()
        }
        moved = {
            uid: (change.before["name"], change.after["name"])
            for uid, change in changes_by_uid.items()
            if change.before
            and change.after
            and change.before["name"] != change.after["name"]
        }
        store_files = {}

        def stage(path, after):
            relative = path.relative_to(store.store_dir).as_posix()
            before = path.read_bytes() if path.exists() else None
            previous = store_files.get(relative)
            store_files[relative] = [
                previous[0] if previous else encode_bytes(before),
                encode_bytes(after),
            ]

        _stage_context_history(
            store,
            frame,
            records,
            checkpoints,
            changes_by_uid,
            moved,
            checkpoint_uids,
            checkpoint_records,
            operation_uid,
            restoration,
            stage,
        )
        for uid, record in checkpoint_records.items():
            if uid not in changes_by_uid:
                stage(
                    store._checkpoints_dir(record["snapshot"]["name"])
                    / ("sync-" + record["uid"] + ".json"),
                    _json_bytes(record),
                )
        _stage_profile_metadata(store, plan, moved, stage)
        external_files = _external_file_versions(plan) if restoration is None else {}
        result = _profile_sync_result(
            plan,
            operation_uid,
            checkpoint_uids,
            changed_files,
        )
        result = replace(
            result,
            conflict_choice=plan.conflict_choice,
            checkpoint_uids=tuple(
                (record["snapshot"]["name"], record["uid"])
                for record in checkpoint_records.values()
            ),
        )
        publication = {
            "undoable": bool(frame.changes),
            "started_at": timestamp,
            "root": str(project_root_dir),
            "excluded_names": list(frame.excluded_names),
        }
        if restoration:
            publication["restoration"] = {
                key: restoration[key] for key in ("source_unit_uid", "direction")
            }
        receipt = {
            **SyncRunRepository(store).receipt_record(
                result, restoration["direction"] if restoration else None
            ),
            "profile": publication,
        }
        stage(
            sync_record_path(store, "runs", operation_uid + ".json"),
            _json_bytes(receipt),
        )
        publish_sync_files(
            store,
            project_root_dir,
            {
                "store_files": store_files,
                "external_files": external_files,
            },
        )
    return result


def _validate_profile_inputs(store, project_root_dir, plan, restoration):
    frame = plan.profile_changes
    if (
        restoration is None
        and read_project_documents(project_root_dir) != frame.snapshot
    ):
        raise ValueError("Project files or .memignore changed before Sync publication.")
    records, checkpoints = store._read_context_graph_for_rename()
    for change in frame.changes:
        if change.before is None:
            store._assert_context_storage_available(change.after["name"])
    return records, checkpoints


def _prepare_sync_checkpoints(store, changes_by_uid, operation_uid, restoration):
    records = {}
    for uid, change in changes_by_uid.items():
        following = change.after or change.before
        command = restoration["direction"] if restoration else "sync"
        details = (
            {
                "sync_restore": {
                    "source_unit_uid": restoration["source_unit_uid"],
                    "direction": command,
                }
            }
            if restoration
            else {"sync_operation": {"uid": operation_uid, "action": change.action}}
        )
        _checkpoint, record = store._prepare_checkpoint_record(
            Context.from_dict(following),
            command=command,
            command_details=details,
            auto=True,
            command_before=change.before if change.action != "UNCHANGED" else None,
        )
        records[uid] = record
    return records


def _stage_context_history(
    store,
    frame,
    records,
    checkpoints,
    changes_by_uid,
    moved,
    checkpoint_uids,
    checkpoint_records,
    operation_uid,
    restoration,
    stage,
):
    history_paths = {}
    for old_name, record in records.items():
        change = changes_by_uid.get(record["uid"])
        after = change.after if change else record
        if after is None:
            archive = store._command_context_archive_path(
                checkpoint_uids[record["uid"]]
            )
            target_history = archive / "checkpoints"
            stage(archive / "context.json", _json_bytes(record))
            stage(
                archive / "manifest.json",
                _json_bytes(
                    {
                        "version": 1,
                        "command": "sync",
                        "unit_uid": "sync:" + operation_uid,
                        "context_uid": record["uid"],
                        "context_name": old_name,
                        "checkpoint_uid": checkpoint_uids[record["uid"]],
                    }
                ),
            )
        else:
            target_history = store._checkpoints_dir(after["name"])
        history_paths[record["uid"]] = target_history
        for filename, checkpoint in checkpoints[old_name].items():
            rewritten = checkpoint
            old_path = store._checkpoints_dir(old_name) / filename
            target = target_history / filename
            if target != old_path:
                stage(old_path, None)
                stage(target, _json_bytes(rewritten))
            elif rewritten != checkpoint:
                stage(target, _json_bytes(rewritten))
        if change:
            if after is None or after["name"] != old_name:
                stage(store._context_file(old_name), None)
            if after is not None:
                stage(store._context_file(after["name"]), _json_bytes(after))
    for uid, change in changes_by_uid.items():
        following = change.after or change.before
        if change.before is None:
            stage(store._context_file(following["name"]), _json_bytes(following))
        history = history_paths.get(uid, store._checkpoints_dir(following["name"]))
        archive_uid = (restoration or {}).get("archive_sources", {}).get(uid)
        if archive_uid:
            archive, _manifest, _context, _entries = (
                store._load_command_context_archive(archive_uid)
            )
            for path in sorted((archive / "checkpoints").iterdir()):
                rewritten = json.loads(path.read_bytes())
                stage(history / path.name, _json_bytes(rewritten))
                stage(path, None)
            stage(archive / "context.json", None)
            stage(archive / "manifest.json", None)
        checkpoint = checkpoint_records[uid]
        stage(
            history / ("sync-" + checkpoint_uids[uid] + ".json"),
            _json_bytes(checkpoint),
        )


def _stage_profile_metadata(store, plan, moved, stage):
    frame = plan.profile_changes
    state = store._read_state()
    next_state = copy.deepcopy(state)
    renamed_names = {old: new for old, new in moved.values()}
    removed_names = {
        change.before["name"] for change in frame.changes if change.after is None
    }
    current = state.get("current")
    next_state["current"] = (
        None if current in removed_names else renamed_names.get(current, current)
    )
    if next_state != state:
        stage(store.state_file, _json_bytes(next_state))


def _external_file_versions(plan):
    # These bytes exist only for this call's publication/exception rollback.
    # Successful Sync never retains a workspace backup for Undo or Revert.
    external_files = {}
    for export in plan.exports:
        output = {file.path: file.data for file in export.files}
        for relative in output.keys() | set(export.removals):
            path = export.destination / relative
            actual = path.read_bytes() if path.exists() else None
            external_files[relative] = [
                encode_bytes(actual),
                encode_bytes(output.get(relative)),
            ]
    return external_files


def _profile_sync_result(
    plan,
    operation_uid,
    checkpoint_uids,
    changed_files,
):
    frame = plan.profile_changes
    final_names = {record["name"] for record in frame.before_records}
    for change in frame.changes:
        if change.before:
            final_names.discard(change.before["name"])
        if change.after:
            final_names.add(change.after["name"])
    return SyncResult(
        tuple(sorted(final_names - set(frame.excluded_names))),
        tuple(
            replace(effect, path=str(export.destination / effect.path))
            for export in plan.exports
            for effect in export.effects
        ),
        run_uid=operation_uid,
        checkpoint_uids=tuple(
            (
                (change.after or change.before)["name"],
                checkpoint_uids[(change.after or change.before)["uid"]],
            )
            for change in frame.changes
        ),
        memory_effects=frame.memory_effects,
        direction="mixed"
        if changed_files and frame.changes
        else "inbound"
        if frame.changes
        else "outbound",
        context_effects=tuple(
            (
                change.action,
                (change.before or change.after)["name"],
                change.after["name"] if change.action == "RENAME" else None,
            )
            for change in frame.changes
        ),
    )
