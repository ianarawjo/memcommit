"""Restore one Sync lifecycle through the same frozen publication journal."""

import json
from datetime import datetime
from pathlib import Path

from memcommit.application.capabilities.command_recovery.model import (
    CommandRestoreResult,
)
from memcommit.application.capabilities.import_export.export_documents import (
    plan_export_documents,
)
from memcommit.application.capabilities.import_export.model import OutputFile
from memcommit.application.operations.mem_sync.model import (
    ProfileDocumentChanges,
    SyncContextChange,
    SyncPlan,
    SyncRequest,
    SyncSelection,
)
from memcommit.application.operations.mem_sync.publication import (
    publish_profile_changes,
)
from memcommit.application.operations.mem_sync.runtime import SyncRuntime
from memcommit.models.checkpoint import Checkpoint
from memcommit.persistence.import_export.source import (
    read_output_files,
    read_project_documents,
)
from memcommit.persistence.operations.mem_sync.publication import decode_bytes
from memcommit.persistence.operations.mem_sync.run_repository import SyncRunRepository
from memcommit.persistence.store.context_memory.models import (
    ConcurrentContextUpdateError,
)


def restore_sync_command(store, unit, direction):
    source_uid = unit.uid.removeprefix("sync:")
    source = next(
        (
            record
            for record in SyncRunRepository(store).profile_history()
            if record["uid"] == source_uid
        ),
        None,
    )
    if source is None:
        raise ValueError("Sync restoration source receipt is unavailable.")
    frame = source["profile"]
    runtime = SyncRuntime(store)
    if Path(frame["root"]) != runtime.project_root:
        raise ValueError("Sync restoration belongs to a different project root.")
    records = {
        context.name: context.to_dict()
        for context in store.load_direct_context_graph_strict()
    }
    by_uid = {record["uid"]: record for record in records.values()}
    archives = {}
    root = store.command_context_archives_dir
    if root.exists():
        for path in root.iterdir():
            archive, manifest, context, entries = store._load_command_context_archive(
                path.name
            )
            archives[context.uid] = (manifest["checkpoint_uid"], context.to_dict())
    index = 0 if direction == "undo" else 1
    changes = []
    archive_sources = {}
    for original in frame["changes"]:
        expected = original["after"] if direction == "undo" else original["before"]
        target = original["before"] if direction == "undo" else original["after"]
        uid = (expected or target)["uid"]
        actual = by_uid.get(uid)
        if actual != expected:
            raise ConcurrentContextUpdateError(
                f"Context changed after the Sync selected for {direction}: {uid}"
            )
        if expected is None and target is not None:
            archived = archives.get(uid)
            if archived is None:
                raise ValueError("Sync restoration Context archive is unavailable.")
            if target["name"] in records:
                raise ConcurrentContextUpdateError(
                    "Sync restoration destination is occupied."
                )
            archive_sources[uid] = archived[0]
        action = (
            "ADD"
            if expected is None
            else "REMOVE"
            if target is None
            else "RENAME"
            if expected["name"] != target["name"]
            else "EDIT"
        )
        changes.append(
            SyncContextChange(expected, target, action, tuple(original["paths"]))
        )
    logical = frame["logical_files"]
    current_files = read_output_files(runtime.project_root, logical)
    expected_index = 1 - index
    if any(
        current_files[path] != decode_bytes(versions[expected_index])
        for path, versions in logical.items()
    ):
        raise ConcurrentContextUpdateError(
            "External files changed after the Sync selected for restoration."
        )
    output = tuple(
        OutputFile(path, decode_bytes(versions[index]))
        for path, versions in logical.items()
        if versions[index] is not None
    )
    removals = tuple(
        path for path, versions in logical.items() if versions[index] is None
    )
    export = plan_export_documents(
        runtime.project_root, output, current_files, removals=removals
    )
    selection = SyncSelection(
        tuple(sorted(records)),
        None,
        "all",
        tuple(sorted((name, record["uid"]) for name, record in records.items())),
    )
    runtime.selection = selection
    runtime.previous_baselines = runtime.baselines.load()
    runtime.removed_connection_uids = ()
    runtime.had_errors = False
    profile = ProfileDocumentChanges(
        read_project_documents(runtime.project_root),
        tuple(records.values()),
        tuple(changes),
        (),
        (),
        (),
    )
    plan = SyncPlan(selection, (export,), (), (), (), profile)
    settings = runtime.settings.load()
    restoration = {
        "source_unit_uid": unit.uid,
        "direction": direction,
        "archive_sources": archive_sources,
        "agreements": frame.get("agreement_versions", ({}, {}))[index],
        "settings": json.loads(
            decode_bytes(frame["store_files"]["sync/settings.json"][index])
        )
        if frame["store_files"]["sync/settings.json"][index] is not None
        else {
            "schema_version": 1,
            "revision": 0,
            "connections": [],
            "policies": [],
            "errors": {},
        },
    }
    touched = {(change.before or change.after)["uid"] for change in changes}
    versions = frame.get("agreement_versions", ({}, {}))
    touched.update(
        uid
        for uid in versions[0].keys() | versions[1].keys()
        if versions[0].get(uid) != versions[1].get(uid)
    )
    current_agreements = runtime.baselines.references()
    target_agreements = restoration["agreements"]
    restoration["agreements"] = {
        **current_agreements,
        **{uid: target_agreements.get(uid) for uid in touched},
    }
    target_connections = restoration["settings"]["connections"]
    restoration["settings"] = {
        **settings,
        "connections": [
            record
            for record in settings["connections"]
            if record["context_uid"] not in touched
        ]
        + [record for record in target_connections if record["context_uid"] in touched],
    }
    # Scope policy belongs to the current Profile, even when restoring an
    # older document state. Undo must not silently toggle automatic Sync.
    restoration["settings"]["policies"] = settings["policies"]
    result = publish_profile_changes(
        runtime,
        plan,
        SyncRequest(all_contexts=True),
        settings,
        restoration=restoration,
    )
    checkpoints = []
    for change, (_name, checkpoint_uid) in zip(
        changes, result.checkpoint_uids, strict=True
    ):
        if change.after is not None:
            entries = store.list_checkpoints(change.after["name"])
        else:
            _archive, _manifest, _context, entries = (
                store._load_command_context_archive(checkpoint_uid)
            )
        record = next(entry for entry in entries if entry["uid"] == checkpoint_uid)
        checkpoints.append(
            Checkpoint(
                **{
                    key: value
                    for key, value in record.items()
                    if key != "command_before" and key != "timestamp"
                },
                timestamp=datetime.fromisoformat(record["timestamp"]),
            )
        )
    return CommandRestoreResult(unit, direction, result.run_uid, tuple(checkpoints))
