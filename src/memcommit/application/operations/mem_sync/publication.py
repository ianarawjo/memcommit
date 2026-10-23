from memcommit.application.operations.profile.model._storage import (
    locked_profile_registry,
)

"""Publish accepted external edits through existing Context batch persistence."""

import copy
import json
from dataclasses import asdict, replace
from datetime import datetime
from uuid import uuid4

from memcommit.application.operations.mem_sync.model import SyncResult
from memcommit.application.operations.profile.config import (
    profile_store_dir,
    profile_root_dir,
)
from memcommit.models.context import Context
from memcommit.core.context_navigation import rewrite_context_navigation_names
from memcommit.persistence.import_export.source import (
    read_output_files,
    read_project_documents,
)
from memcommit.persistence.operations.mem_sync.publication import (
    publish_sync_files,
    encode_bytes,
)
from memcommit.persistence.operations.mem_sync.settings_repository import (
    sync_record_path,
)
from memcommit.persistence.store.context_memory.records import (
    context_record_digest,
)


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")


def publish_profile_changes(runtime, plan, request, settings, *, restoration=None):
    """Publish one fully validated frame without a durable pending publication."""
    policies = settings["policies"]
    frame = plan.profile_changes
    store = runtime.store
    changed_files = any(
        effect.action != "UNCHANGED"
        and not (
            effect.action == "REMOVE"
            and dict(export.previous_hashes)[effect.path] is None
        )
        for export in plan.exports
        for effect in export.effects
    )
    agreement_changed = restoration is not None or runtime.agreement_changed(plan)
    if not frame.changes and not changed_files and not agreement_changed:
        managed_names = tuple(
            sorted(
                {
                    name
                    for connection in plan.connections
                    for name in connection.member_names
                }
            )
        )
        return SyncResult(
            managed_names,
            tuple(
                replace(effect, path=str(export.destination / effect.path))
                for export in plan.exports
                for effect in export.effects
            ),
        )
    operation_uid = str(uuid4())
    timestamp = datetime.now().isoformat()
    lifecycle = any(
        change.action in {"ADD", "REMOVE", "RENAME"} for change in frame.changes
    )
    names = set(record["name"] for record in frame.before_records)
    names.update(change.after["name"] for change in frame.changes if change.after)
    with (
        locked_profile_registry() as registry,
        store._context_graph_lock(exclusive=True),
        store._context_write_locks(names),
        store._state_write_lock(),
    ):
        records, checkpoints = _validate_profile_inputs(
            runtime, plan, settings, registry.active
        )
        changes_by_uid = {
            (change.after or change.before)["uid"]: change for change in frame.changes
        }
        mem_targets = _prepare_mem_conflict_targets(
            store, plan, checkpoints, operation_uid
        )
        checkpoint_records = _prepare_sync_checkpoints(
            store,
            changes_by_uid,
            operation_uid,
            lifecycle,
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
        revert_records = _stage_mem_conflict_reverts(
            store,
            plan,
            checkpoint_records,
            mem_targets,
            checkpoints,
            stage,
        )
        before_agreements = runtime.baselines.references()
        after_agreements = (
            _stage_agreement_checkpoints(
                runtime,
                plan,
                {**checkpoint_records, **mem_targets},
                operation_uid,
                before_agreements,
                stage,
            )
            if restoration is None
            else restoration["agreements"]
        )
        _stage_translation_bindings(store, changes_by_uid, moved, stage)
        _stage_profile_metadata(
            runtime, plan, settings, policies, moved, restoration, stage
        )
        external_files = _external_file_versions(plan)
        result = _profile_sync_result(
            runtime,
            plan,
            request,
            operation_uid,
            checkpoint_uids,
            changed_files,
        )
        final_changes = _sync_action_changes(plan)
        action_checkpoints = {
            **checkpoint_uids,
            **{uid: record["uid"] for uid, record in revert_records.items()},
        }
        for change in final_changes:
            uid = (change.after or change.before)["uid"]
            if uid not in action_checkpoints:
                action_checkpoints[uid] = next(
                    member["checkpoint_uid"]
                    for members in after_agreements.values()
                    if members
                    for member in members
                    if member["context_uid"] == uid
                )
        result = replace(
            result,
            conflict_choice=plan.conflict_choice,
            revert_checkpoint_uids=tuple(
                (record["snapshot"]["name"], record["uid"])
                for record in revert_records.values()
            ),
        )
        publication = {
            "version": 2,
            "undoable": bool(final_changes),
            "child_checkpoint_uids": [
                record["uid"]
                for record in (*checkpoint_records.values(), *revert_records.values())
            ],
            "agreement_versions": [before_agreements, after_agreements],
            "lifecycle": lifecycle,
            "store_files": store_files,
            "external_files": external_files,
            "logical_files": external_files,
            "changes": [asdict(change) for change in final_changes],
            "checkpoint_uids": action_checkpoints,
            "result": asdict(result),
            "started_at": timestamp,
            "root": str(runtime.project_root),
            "source_inventory": list(plan.selection.inventory),
            "causing_command": restoration["direction"] if restoration else None,
        }
        if restoration:
            publication["restoration"] = {
                key: restoration[key] for key in ("source_unit_uid", "direction")
            }
        # Keep only restoration metadata in the success record; checkpoint and
        # Context preimages are already represented by their independent history.
        publication["store_files"] = {
            path: versions
            for path, versions in store_files.items()
            if path == "sync/settings.json"
        }
        receipt = {
            **runtime.runs.receipt_record(result, publication["causing_command"]),
            "profile": publication,
        }
        stage(
            sync_record_path(store, "runs", operation_uid + ".json"),
            _json_bytes(receipt),
        )
        publish_sync_files(
            store,
            runtime.project_root,
            {
                "store_files": store_files,
                "external_files": external_files,
            },
        )
    return result


def _validate_profile_inputs(runtime, plan, settings, active_profile):
    frame = plan.profile_changes
    store = runtime.store
    if runtime.profile is not None and (
        active_profile.uid != runtime.profile.uid
        or profile_store_dir(active_profile).absolute() != store.store_dir.absolute()
        or profile_root_dir(active_profile) != runtime.project_root
    ):
        raise ValueError("Active Profile changed before Sync publication.")
    store._assert_profile_write_allowed()
    runtime.revalidate_selection()
    if (
        runtime.settings.load() != settings
        or runtime.baselines.load() != runtime.previous_baselines
    ):
        raise ValueError("Sync agreement changed before publication.")
    if hasattr(runtime, "selected_file_snapshot"):
        if (
            read_output_files(runtime.project_root, runtime.selected_file_snapshot)
            != runtime.selected_file_snapshot
        ):
            raise ValueError("External Sync files changed before publication.")
    elif read_project_documents(runtime.project_root) != frame.snapshot:
        raise ValueError("Project files or .memignore changed before Sync publication.")
    records, checkpoints = store._read_context_graph_for_rename()
    if records != {record["name"]: record for record in frame.before_records}:
        raise ValueError("Sync Context content changed before publication.")
    for change in frame.changes:
        if change.before is None:
            store._assert_context_storage_available(change.after["name"])
        elif change.after is None:
            store._assert_context_deletion_allowed(Context.from_dict(change.before))
        else:
            store._assert_context_record_change_allowed(change.before, change.after)
    return records, checkpoints


def _prepare_mem_conflict_targets(store, plan, checkpoints, operation_uid):
    if plan.conflict_choice != "mem":
        return {}
    conflicted = {uid for conflict in plan.conflicts for uid in conflict.context_uids}
    targets = {}
    for before in plan.profile_changes.before_records:
        uid = before["uid"]
        if uid not in conflicted:
            continue
        retained = next(
            (
                record
                for record in checkpoints[before["name"]].values()
                if record["snapshot"] == before
            ),
            None,
        )
        if retained is None:
            _checkpoint, retained = store._prepare_checkpoint_record(
                Context.from_dict(before),
                command="sync",
                auto=True,
                command_details={
                    "sync_agreement": {"version": 1, "uid": operation_uid}
                },
            )
        targets[uid] = retained
    return targets


def _stage_mem_conflict_reverts(
    store, plan, incoming_records, targets, checkpoints, stage
):
    reverts = {}
    for uid, target in targets.items():
        name = target["snapshot"]["name"]
        history = list(checkpoints[name].values())
        if not any(record["uid"] == target["uid"] for record in history):
            stage(
                store._checkpoints_dir(name) / ("sync-" + target["uid"] + ".json"),
                _json_bytes(target),
            )
            history.append(target)
        incoming = incoming_records.get(uid)
        if incoming is None:
            continue
        before = Context.from_dict(incoming["snapshot"])
        # Use the Store's normal Revert state construction and record builder.
        # Keeping both child records independent must not split the Sync action.
        restored = store._context_for_restoration(
            target["snapshot"],
            context_uid=uid,
            context_name=before.name,
        )
        history.append(incoming)
        history.sort(key=lambda record: record["timestamp"], reverse=True)
        _checkpoint, record = store._prepare_revert_checkpoint_record(
            before, target, history, restored.to_dict()
        )
        stage(
            store._checkpoints_dir(before.name) / ("revert-" + record["uid"] + ".json"),
            _json_bytes(record),
        )
        stage(store._context_file(before.name), _json_bytes(restored.to_dict()))
        reverts[uid] = record
    return reverts


def _sync_action_changes(plan):
    from memcommit.application.operations.mem_sync.model import SyncContextChange

    conflicted = (
        {uid for conflict in plan.conflicts for uid in conflict.context_uids}
        if plan.conflict_choice == "mem"
        else set()
    )
    changes = {
        (change.after or change.before)["uid"]: replace(change, after=change.before)
        if (change.after or change.before)["uid"] in conflicted
        else change
        for change in plan.profile_changes.changes
    }
    changed_paths = {
        effect.path
        for export in plan.exports
        for effect in export.effects
        if effect.action != "UNCHANGED"
    }
    for _owner_uid, agreement in plan.baselines:
        if not set(dict(agreement.files)).intersection(changed_paths):
            continue
        for member in agreement.members:
            changes.setdefault(
                member["uid"],
                SyncContextChange(member, member, "EDIT", tuple(dict(agreement.files))),
            )
    return tuple(changes.values())


def _prepare_sync_checkpoints(
    store, changes_by_uid, operation_uid, lifecycle, restoration
):
    members = [
        {"uid": uid, "name": (change.after or change.before)["name"]}
        for uid, change in changes_by_uid.items()
    ]
    records = {}
    for uid, change in changes_by_uid.items():
        following = change.after or change.before
        command = restoration["direction"] if restoration else "sync"
        details = (
            {
                "sync_restore": {
                    "version": 1,
                    "source_unit_uid": restoration["source_unit_uid"],
                    "direction": command,
                }
            }
            if restoration
            else {
                "command_contexts": members,
                "sync_operation": {
                    "version": 2,
                    "uid": operation_uid,
                    "direction": "inbound",
                    "origin": "external_file_change",
                    "trigger": {"kind": "MANUAL", "operation": "sync"},
                    "files": list(change.paths) or [following["name"]],
                },
            }
        )
        _checkpoint, record = store._prepare_checkpoint_record(
            Context.from_dict(following),
            command=command,
            command_details=details,
            auto=True,
            command_before=change.before,
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


def _stage_agreement_checkpoints(
    runtime, plan, checkpoint_records, operation_uid, previous, stage
):
    """Anchor every final member, reusing an exact snapshot when already retained."""
    following = dict(previous)
    for uid in runtime.removed_connection_uids:
        following[uid] = None
    for owner_uid, agreement in plan.baselines:
        references = []
        for member in agreement.members:
            context_uid = member["uid"]
            retained = checkpoint_records.get(context_uid)
            if retained is None or retained["snapshot"] != member:
                retained = next(
                    (
                        record
                        for record in runtime.store.list_checkpoints(member["name"])
                        if record["snapshot"] == member
                    ),
                    None,
                )
            if retained is None:
                _checkpoint, retained = runtime.store._prepare_checkpoint_record(
                    Context.from_dict(member),
                    command="sync",
                    auto=True,
                    command_details={
                        "sync_agreement": {"version": 1, "uid": operation_uid}
                    },
                )
                stage(
                    runtime.store._checkpoints_dir(member["name"])
                    / ("sync-" + retained["uid"] + ".json"),
                    _json_bytes(retained),
                )
            references.append(
                {"context_uid": context_uid, "checkpoint_uid": retained["uid"]}
            )
        following[owner_uid] = references
    return following


def _stage_translation_bindings(store, changes_by_uid, moved, stage):
    if not moved:
        return
    from memcommit.persistence.store.translation_catalog.record_format import (
        rewrite_translation_context_binding,
    )
    from memcommit.persistence.store.translation_catalog.repository import (
        translation_catalogs_dir,
    )

    renamed = {uid: new_name for uid, (_old_name, new_name) in moved.items()}
    before_digests, after_digests = {}, {}
    for uid, change in changes_by_uid.items():
        if change.before is None or change.after is None:
            continue
        # A simultaneous text edit invalidates provider freshness. Renaming
        # alone may carry a previously fresh translation to the new binding.
        before_memories = {
            key: value
            for key, value in change.before["memories"].items()
            if value["type"] == "memory"
        }
        after_memories = {
            key: value
            for key, value in change.after["memories"].items()
            if value["type"] == "memory"
        }
        if before_memories == after_memories:
            before_digests[uid] = context_record_digest(change.before)
            after_digests[uid] = context_record_digest(change.after)
    for filename, record in store._read_translation_records_for_rename().items():
        post = rewrite_translation_context_binding(
            record,
            context_names=renamed,
            before_digests=before_digests,
            after_digests=after_digests,
        )
        if post != record:
            stage(translation_catalogs_dir() / filename, _json_bytes(post))


def _stage_profile_metadata(
    runtime, plan, settings, policies, moved, restoration, stage
):
    frame = plan.profile_changes
    store = runtime.store
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
    rewrite_context_navigation_names(
        next_state, lambda name: renamed_names.get(name, name)
    )
    if next_state != state:
        stage(store.state_file, _json_bytes(next_state))
    _next_baselines, next_settings = runtime.agreement_records(plan, settings, policies)
    if restoration:
        next_settings = restoration["settings"]
    next_settings = {**next_settings, "revision": settings["revision"] + 1}
    stage(sync_record_path(store, "settings.json"), _json_bytes(next_settings))


def _external_file_versions(plan):
    # Undo restores physical pre-Sync files, including the external B that
    # existed before a conflict choice. The older agreement S is not a preimage.
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
    runtime,
    plan,
    request,
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
        inbound_paths=tuple(
            (change.paths or ((change.after or change.before)["name"],))[0]
            for change in frame.changes
        ),
        context_effects=tuple(
            (
                change.action,
                (change.before or change.after)["name"],
                change.after["name"] if change.action == "RENAME" else None,
            )
            for change in frame.changes
        ),
    )
