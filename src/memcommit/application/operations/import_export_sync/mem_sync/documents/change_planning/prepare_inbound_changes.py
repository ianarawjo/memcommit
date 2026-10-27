"""Prepare every inbound document before any selected Context is written."""

import json
from dataclasses import replace
from hashlib import sha256

from memcommit.application.operations.import_export_sync.mem_sync.model import (
    SyncConflictError,
    SyncVersionConflict,
)
from memcommit.models.context import Context
from memcommit.persistence.store.context_memory.records import context_record_digest

from memcommit.application.operations.import_export_sync.common.conversion import (
    normalize_document_bytes,
)

from .compare_files import classify_sync_changes
from ..connections.document_paths import prepare_sync_document_units
from ..content_changes.import_document_changes import import_document_changes


def member_digest(contexts):
    return sha256(
        json.dumps([context_record_digest(context) for context in contexts]).encode()
    ).hexdigest()


def prepare_inbound_changes(content, units, baselines, *, external_files):
    by_name = {context.name: context for context in content.contexts}
    changes = []
    conflicts = []
    for context, members, files, _directories in units:
        baseline = baselines.get(context.uid)
        if baseline is None:
            continue
        # Placement changes are checked by the Profile planner before importing.
        paths = tuple(path for path, _data in baseline.files)
        if tuple(file.path for file in files) != paths:
            continue
        current_members = tuple(by_name[name] for name in members)
        projected = {file.path: file.data for file in files}
        external = {path: external_files.get(path) for path in paths}
        direction = classify_sync_changes(
            projected,
            {
                path: normalize_document_bytes(data, path=path)
                for path, data in external.items()
            },
            baseline,
            source_changed=member_digest(current_members) != baseline.source_digest,
        )
        if direction in {"UNCHANGED", "OUTBOUND", "CONVERGED"}:
            continue
        concurrent_change = direction == "CONFLICT"
        original_members = current_members
        if concurrent_change:
            current_members = tuple(
                Context.from_dict(record) for record in baseline.members
            )
            context = current_members[0]
            baseline_unit = next(
                unit
                for unit in prepare_sync_document_units(
                    replace(content, contexts=current_members)
                )
                if unit[0].uid == context.uid
            )
            projected = {file.path: file.data for file in baseline_unit[2]}
            files = baseline_unit[2]
            conflicts.append(
                SyncVersionConflict(
                    tuple(member.uid for member in original_members)
                )
            )
        if len(files) != 1 or len(members) != 1 or files[0].attached:
            raise SyncConflictError(
                ", ".join(paths),
                "This document unit does not yet support inbound Sync.",
            )
        file = files[0]
        if external[file.path] is None:
            raise SyncConflictError(
                file.path,
                "An external file is missing; file deletion does not delete its Context.",
            )
        if list(baseline.members) != [member.to_dict() for member in current_members]:
            raise ValueError(
                "Sync baseline snapshots do not match their retained source digest."
            )
        ranges = dict(baseline.source_ranges).get(file.path, ())
        if projected != dict(baseline.files) or ranges != file.source_ranges:
            raise SyncConflictError(
                file.path,
                "The retained baseline attribution cannot be reproduced by the shared renderer.",
            )
        arguments = (dict(baseline.files)[file.path], external[file.path], ranges)
        try:
            unit_changes = (
                import_document_changes(context, *arguments, path=file.path),
            )
        except SyncConflictError:
            if not concurrent_change:
                raise
            unit_changes = _import_complete_external_version(
                original_members, external[file.path], file.path
            )
        if concurrent_change:
            from memcommit.application.operations.import_export_sync.mem_sync.model import (
                InboundContextChange,
            )

            external_members = {
                member.uid: member.to_dict() for member in current_members
            }
            external_members.update(
                (change.after["uid"], change.after) for change in unit_changes
            )
            # Whole-version selection preserves unchanged external content from
            # the last agreement, not the concurrently edited local version.
            unit_changes = tuple(
                InboundContextChange(
                    original.to_dict(),
                    external_members[original.uid],
                    (file.path,),
                    _changed_memory_effects(
                        original.to_dict(), external_members[original.uid]
                    ),
                )
                for original in original_members
            )
        proposed_members = dict(by_name)
        for change in unit_changes:
            proposed_members[change.after["name"]] = Context.from_dict(change.after)
        proposed_content = replace(
            content,
            contexts=tuple(
                proposed_members[member.name] for member in content.contexts
            ),
        )
        rendered = {
            output.path: output.data
            for owner, _, outputs, _ in prepare_sync_document_units(proposed_content)
            if owner.uid == context.uid
            for output in outputs
        }
        if rendered != {
            path: normalize_document_bytes(data, path=path)
            for path, data in external.items()
        }:
            raise SyncConflictError(
                file.path,
                "Document conversion changed content beyond block separators; nothing was changed.",
            )
        for change in unit_changes:
            if change.before != change.after:
                changes.append(change)
                by_name[change.after["name"]] = proposed_members[change.after["name"]]
    return (
        replace(
            content,
            contexts=tuple(by_name[context.name] for context in content.contexts),
        ),
        tuple(changes),
        tuple(conflicts),
    )


def _import_complete_external_version(original_members, data, path):
    """Whole-version selection may replace ambiguous Memory ownership explicitly."""
    from memcommit.application.operations.import_export_sync.common.conversion import (
        parse_project_documents,
    )
    from memcommit.application.operations.import_export_sync.common.model import (
        InputFile,
    )
    from memcommit.application.operations.import_export_sync.mem_sync.model import (
        InboundContextChange,
        SyncMemoryEffect,
    )

    parsed = parse_project_documents((InputFile(path, data),))
    documents = [
        context
        for context in parsed.contexts
        if context.corresponding_document_metadata.role != "directory"
    ]
    if len(documents) != len(original_members):
        raise ValueError(
            "External version changes the document's Context membership; nothing was changed."
        )
    changes = []
    for original, imported in zip(original_members, documents, strict=True):
        # Replacing a whole version is different from claiming an ambiguous
        # old Memory retained its identity. Context identity remains stable.
        following = Context.from_dict(
            {**imported.to_dict(), "uid": original.uid, "name": original.name}
        )
        changes.append(
            InboundContextChange(
                original.to_dict(),
                following.to_dict(),
                (path,),
                tuple(
                    SyncMemoryEffect(original.name, uid, "REMOVE")
                    for uid in original.get_ordered_memory_uids()
                )
                + tuple(
                    SyncMemoryEffect(original.name, uid, "ADD")
                    for uid in following.get_ordered_memory_uids()
                ),
            )
        )
    return tuple(changes)


def _changed_memory_effects(before, after):
    from memcommit.application.operations.import_export_sync.mem_sync.model import (
        SyncMemoryEffect,
    )

    effects = []
    for uid in dict.fromkeys((*before["order"], *after["order"])):
        prior, following = before["memories"].get(uid), after["memories"].get(uid)
        if prior != following:
            effects.append(
                SyncMemoryEffect(
                    before["name"],
                    uid,
                    "ADD"
                    if prior is None
                    else "REMOVE"
                    if following is None
                    else "EDIT",
                )
            )
    retained = set(before["order"]) & set(after["order"])
    if [uid for uid in before["order"] if uid in retained] != [
        uid for uid in after["order"] if uid in retained
    ]:
        effects.append(SyncMemoryEffect(before["name"], None, "REORDER"))
    return tuple(effects)
