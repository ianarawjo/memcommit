"""Prepare every inbound document before any selected Context is written."""

import json
from dataclasses import replace
from hashlib import sha256

from memcommit.application.operations.mem_sync.model import (
    SyncConflictError,
    SyncIssue,
    SyncVersionConflict,
)
from memcommit.configuration.config import resolve_external_document_locator
from memcommit.models.context import Context
from memcommit.persistence.import_export.source import read_output_files
from memcommit.persistence.store.context_memory.records import context_record_digest

from .compare_files import classify_sync_changes
from ..connections.document_paths import prepare_sync_document_units
from ..content_changes.import_document_changes import import_document_changes
from ..content_changes.import_skill_changes import import_skill_changes
from ..content_changes.import_yaml_changes import import_yaml_changes


def member_digest(contexts):
    return sha256(
        json.dumps([context_record_digest(context) for context in contexts]).encode()
    ).hexdigest()


def prepare_inbound_changes(
    content, units, connections, baselines, *, external_files=None
):
    by_name = {context.name: context for context in content.contexts}
    changes = []
    conflicts = []
    for context, members, files, _directories in units:
        connection = connections.get(context.uid)
        baseline = baselines.get(context.uid)
        if connection is None or baseline is None:
            continue
        # Identity/placement changes belong to the normal connection checks;
        # never import through a formerly occupied path into a different owner.
        if (
            connection.context_name != context.name
            or tuple(file.path for file in files) != connection.paths
        ):
            continue
        current_members = tuple(by_name[name] for name in members)
        projected = {file.path: file.data for file in files}
        external = (
            {path: external_files.get(path) for path in connection.paths}
            if external_files is not None
            else read_output_files(
                resolve_external_document_locator(connection.base), connection.paths
            )
        )
        direction = classify_sync_changes(
            projected,
            external,
            baseline,
            source_changed=member_digest(current_members) != baseline.source_digest,
        )
        if direction in {"UNCHANGED", "OUTBOUND", "CONVERGED"}:
            continue
        concurrent_change = direction == "CONFLICT"
        original_members = current_members
        if concurrent_change:
            if not baseline.members:
                raise ValueError(
                    "A Sync conflict needs retained checkpoint attribution before choosing a version."
                )
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
                    tuple(member.uid for member in original_members), connection.paths
                )
            )
        is_skill = (
            context.corresponding_document_metadata is not None
            and context.corresponding_document_metadata.role == "skill_body"
        )
        if len(files) != 1 or (len(members) != 1 and not is_skill) or files[0].attached:
            raise SyncConflictError(
                SyncIssue(
                    "unsupported-format",
                    ", ".join(connection.paths),
                    "This document unit does not yet support inbound Sync.",
                )
            )
        file = files[0]
        if external[file.path] is None:
            raise SyncConflictError(
                SyncIssue(
                    "missing-file",
                    file.path,
                    "An external file is missing; file deletion does not delete its Context.",
                )
            )
        if baseline.members:
            if list(baseline.members) != [
                member.to_dict() for member in current_members
            ]:
                raise ValueError(
                    "Sync baseline snapshots do not match their retained source digest."
                )
            ranges = dict(baseline.source_ranges).get(file.path, ())
            # Earlier YAML/Skill baselines had snapshots but no emission trace.
            # Reconstruct only from the unchanged source and retained file bytes.
            if (
                not ranges
                and context.corresponding_document_metadata is not None
                and (
                    context.corresponding_document_metadata.format == "yaml" or is_skill
                )
            ):
                ranges = file.source_ranges
            if projected != dict(baseline.files) or ranges != file.source_ranges:
                raise SyncConflictError(
                    SyncIssue(
                        "invalid-attribution",
                        file.path,
                        "The retained baseline attribution cannot be reproduced by the shared renderer.",
                    )
                )
        else:
            # Legacy attribution is reconstructible only from the unchanged
            # retained source. Never bless the already edited external bytes.
            if projected != dict(baseline.files):
                raise ValueError(
                    "Legacy Sync baseline cannot reproduce its original file bytes."
                )
            ranges = file.source_ranges
        arguments = (dict(baseline.files)[file.path], external[file.path], ranges)
        try:
            if is_skill:
                unit_changes = import_skill_changes(
                    context, current_members[1], *arguments, path=file.path
                )
            else:
                importer = (
                    import_yaml_changes
                    if context.corresponding_document_metadata is not None
                    and context.corresponding_document_metadata.format == "yaml"
                    else import_document_changes
                )
                unit_changes = (importer(context, *arguments, path=file.path),)
        except SyncConflictError:
            if not concurrent_change:
                raise
            unit_changes = _import_complete_external_version(
                original_members, external[file.path], file.path
            )
        if concurrent_change:
            from memcommit.application.operations.mem_sync.model import (
                InboundContextChange,
            )

            external_members = {
                member.uid: member.to_dict() for member in current_members
            }
            external_members.update(
                (change.after["uid"], change.after) for change in unit_changes
            )
            # A Skill is one physical version. Unchanged sections of B come
            # from the agreed checkpoint S, never from concurrent local A.
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
        if rendered != external:
            raise SyncConflictError(
                SyncIssue(
                    "unrepresentable-format",
                    file.path,
                    "Accepted Memories cannot reproduce these exact external bytes; nothing was changed.",
                )
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
    from memcommit.application.capabilities.import_export.conversion import (
        convert_for_import,
    )
    from memcommit.application.capabilities.import_export.model import InputFile
    from memcommit.application.operations.mem_sync.model import (
        InboundContextChange,
        SyncMemoryEffect,
    )

    parsed, _issues = convert_for_import((InputFile(path, data),), "documents", None)
    documents = [
        context
        for context in parsed.contexts
        if context.corresponding_document_metadata.role != "package"
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
    from memcommit.application.operations.mem_sync.model import SyncMemoryEffect

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
