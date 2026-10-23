"""Plan Profile document membership and content changes without publishing them."""

from dataclasses import replace
from pathlib import PurePosixPath

from memcommit.application.capabilities.import_export.conversion import (
    convert_for_import,
)
from memcommit.application.capabilities.import_export.export_documents import (
    plan_export_documents,
)
from memcommit.application.capabilities.import_export.model import InputFile, MemContent
from memcommit.application.capabilities.import_export.project_documents import (
    ProjectDocumentRules,
)
from memcommit.application.operations.mem_sync.model import (
    ProfileDocumentChanges,
    SyncBaseline,
    SyncConnection,
    SyncContextChange,
    SyncMemoryEffect,
    SyncPlan,
)
from memcommit.configuration.config import external_document_locator
from memcommit.models.context import Context

from ..connections.document_paths import (
    context_document_is_excluded,
    prepare_sync_document_units,
)
from ..content_changes.import_document_changes import import_document_changes
from ..content_changes.import_skill_changes import import_skill_changes
from ..content_changes.import_yaml_changes import import_yaml_changes
from .detect_file_renames import detect_file_renames
from .prepare_inbound_changes import member_digest, prepare_inbound_changes


def plan_context_changes(*, content, selection, settings, baselines, snapshot):
    """Freeze one coherent create/update/rename/remove set for selected owned files."""
    from memcommit.persistence.operations.mem_sync.settings_repository import (
        decode_sync_connection,
    )

    rules = ProjectDocumentRules(snapshot.ignore_bytes)
    before = {context.name: context.to_dict() for context in content.contexts}
    by_name = {name: Context.from_dict(record) for name, record in before.items()}
    connections = {
        record["context_uid"]: decode_sync_connection(record)
        for record in settings["connections"]
    }
    allowed_names = set(selection.names)
    excluded_names = {
        context.name
        for context in content.contexts
        if context.name not in allowed_names
        or context_document_is_excluded(context, rules)
    }
    units = prepare_sync_document_units(
        MemContent(
            tuple(
                context
                for context in content.contexts
                if context.name not in excluded_names
            ),
            content.attached_data,
        )
    )

    def excluded_path(path):
        return rules.excludes(path)

    active_units = []
    known_paths = set()
    known_paths.update(
        path for connection in connections.values() for path in connection.paths
    )
    for unit in units:
        owner, members, files, _directories = unit
        known_paths.update(file.path for file in files)
        previous_connection = connections.get(owner.uid)
        ignored_connection = previous_connection and any(
            excluded_path(path) for path in previous_connection.paths
        )
        if (
            not set(members).intersection(allowed_names)
            or ignored_connection
            or rules.excludes(
                owner.name,
                directory=bool(
                    owner.corresponding_document_metadata
                    and owner.corresponding_document_metadata.role == "package"
                ),
            )
            or any(excluded_path(file.path) for file in files)
        ):
            excluded_names.update(members)
        else:
            active_units.append(unit)
    external = {path: data for path, data in snapshot.files if not excluded_path(path)}
    deleted = {}
    missing_units = {}
    inbound_connections = dict(connections)
    inbound_baselines = dict(baselines)
    inbound_external = dict(external)
    for unit in active_units:
        owner, members, files, _directories = unit
        if any(
            connection.context_name == owner.name
            and connection.context_uid != owner.uid
            for connection in connections.values()
        ):
            raise ValueError(f"Sync Context identity changed: {owner.name}")
        baseline = baselines.get(owner.uid)
        connection = connections.get(owner.uid)
        if connection and (
            connection.context_name != owner.name
            or connection.paths != tuple(file.path for file in files)
        ):
            if baseline is None or len(files) != len(connection.paths):
                raise ValueError(f"Sync connection placement changed: {owner.name}")
            prior = dict(baseline.files)
            for old_path, file in zip(connection.paths, files, strict=True):
                if external.get(old_path) != prior.get(old_path):
                    raise ValueError(
                        f"Context rename conflicts with an independent external change: {old_path}"
                    )
                if file.path != old_path and external.get(file.path) not in (
                    None,
                    file.data,
                ):
                    raise ValueError(
                        f"Context rename destination conflicts with an external file: {file.path}"
                    )
                inbound_external[file.path] = external.get(
                    file.path, external.get(old_path)
                )
            inbound_connections[owner.uid] = replace(
                connection,
                context_name=owner.name,
                paths=tuple(file.path for file in files),
                member_names=members,
            )
            inbound_baselines[owner.uid] = replace(
                baseline,
                files=tuple(
                    (file.path, prior[old_path])
                    for old_path, file in zip(connection.paths, files, strict=True)
                ),
            )
            continue
        missing = [file.path for file in files if file.path not in external]
        if missing and baseline:
            if len(files) != 1 or files[0].attached:
                raise ValueError(
                    f"Missing composite document requires explicit resolution: {owner.name}"
                )
            if (
                member_digest(tuple(by_name[name] for name in members))
                != baseline.source_digest
            ):
                raise ValueError(
                    f"External deletion conflicts with newer mem changes: {files[0].path}"
                )
            path = files[0].path
            deleted[path] = dict(baseline.files)[path]
            missing_units[path] = unit
    additions = {
        path: data
        for path, data in external.items()
        if path not in known_paths and rules.supports(path)
    }
    renames = detect_file_renames(deleted, additions)
    effects = []
    replacements = {}
    removed_names = set()
    claimed_additions = set()
    rename_names = {}
    change_paths = {}
    for match in renames:
        owner, members, files, _directories = missing_units[match.old_path]
        parsed, _issues = convert_for_import(
            (InputFile(match.new_path, additions[match.new_path]),), "documents", None
        )
        parsed_by_name = {context.name: context for context in parsed.contexts}
        body = parsed_by_name[match.new_path]
        new_members = (
            (body.name, body.name + "/metadata")
            if body.corresponding_document_metadata.role == "skill_body"
            else (body.name,)
        )
        if (
            len(members) != len(new_members)
            or owner.corresponding_document_metadata
            and owner.corresponding_document_metadata.format
            != body.corresponding_document_metadata.format
        ):
            raise ValueError(f"Rename changes the document format: {match.old_path}")
        baseline = baselines[owner.uid]
        if deleted[match.old_path] != additions[match.new_path]:
            ranges = dict(baseline.source_ranges).get(match.old_path, ())
            if body.corresponding_document_metadata.role == "skill_body":
                changes = import_skill_changes(
                    by_name[members[0]],
                    by_name[members[1]],
                    deleted[match.old_path],
                    additions[match.new_path],
                    ranges,
                    path=match.old_path,
                    renamed_skill_name=PurePosixPath(match.new_path).parent.name,
                )
            else:
                importer = (
                    import_yaml_changes
                    if body.corresponding_document_metadata.format == "yaml"
                    else import_document_changes
                )
                changes = (
                    importer(
                        owner,
                        deleted[match.old_path],
                        additions[match.new_path],
                        ranges,
                        path=match.old_path,
                    ),
                )
            for change in changes:
                replacements[change.after["name"]] = Context.from_dict(change.after)
                effects.extend(change.effects)
        for old_name, new_name in zip(members, new_members, strict=True):
            if new_name in before and new_name != old_name:
                raise ValueError(
                    f"Rename Context destination already exists: {new_name}"
                )
            context = replacements.pop(old_name, by_name[old_name])
            context.name = new_name
            context.corresponding_document_metadata = parsed_by_name[
                new_name
            ].corresponding_document_metadata
            replacements[new_name] = context
            rename_names[old_name] = new_name
            change_paths[context.uid] = (match.old_path, match.new_path)
        # Directory Contexts are real lexical parents, not document Memories.
        for context in parsed.contexts:
            if (
                context.corresponding_document_metadata.role == "package"
                and context.name not in before
            ):
                context.memories.clear()
                context.order.clear()
                replacements.setdefault(context.name, context)
        claimed_additions.add(match.new_path)
    renamed_old_paths = {match.old_path for match in renames}
    for path, unit in missing_units.items():
        if path not in renamed_old_paths:
            for name in unit[1]:
                removed_names.add(name)
                change_paths[by_name[name].uid] = (path,)

    existing_units = tuple(
        unit
        for unit in active_units
        if not any(file.path in missing_units for file in unit[2])
    )
    existing_names = {name for unit in existing_units for name in unit[1]}
    existing_content = MemContent(
        tuple(by_name[name] for name in sorted(existing_names)), content.attached_data
    )
    _updated_content, inbound, conflicts = prepare_inbound_changes(
        existing_content,
        existing_units,
        inbound_connections,
        inbound_baselines,
        external_files=inbound_external,
    )
    for change in inbound:
        replacements[change.after["name"]] = Context.from_dict(change.after)
        effects.extend(change.effects)
        change_paths[change.after["uid"]] = change.paths
    remaining = tuple(
        InputFile(path, data)
        for path, data in sorted(additions.items())
        if path not in claimed_additions
    )
    if remaining:
        parsed, _issues = convert_for_import(remaining, "documents", None)
        for context in parsed.contexts:
            if context.name in before:
                if (
                    not context.corresponding_document_metadata
                    or context.corresponding_document_metadata.role != "package"
                    or not by_name[context.name].corresponding_document_metadata
                    or by_name[context.name].corresponding_document_metadata.role
                    != "package"
                ):
                    raise ValueError(
                        f"New document collides with an existing Context: {context.name}"
                    )
                continue
            if context.corresponding_document_metadata.role == "package":
                context.memories.clear()
                context.order.clear()
            replacements[context.name] = context
            change_paths[context.uid] = (context.corresponding_document_metadata.path,)

    after = {
        name: context
        for name, context in by_name.items()
        if name not in removed_names and name not in rename_names
    }
    after.update(replacements)
    _refresh_directory_membership(after, excluded_names, baselines, snapshot)
    export, new_connections, new_baselines = _prepare_profile_exports(
        after,
        content.attached_data,
        excluded_names,
        excluded_path,
        additions,
        inbound,
        external,
        baselines,
        connections,
        active_units,
        snapshot,
    )
    changes = _context_record_changes(before, after, change_paths, effects)
    changes.sort(key=lambda change: (change.after or change.before)["name"])
    effects = [
        replace(
            effect,
            context_name=rename_names.get(effect.context_name, effect.context_name),
        )
        for effect in effects
    ]
    return SyncPlan(
        selection,
        (export,),
        tuple(new_connections),
        tuple(new_baselines),
        (),
        ProfileDocumentChanges(
            snapshot,
            tuple(before.values()),
            tuple(changes),
            tuple(effects),
            tuple(
                (match.old_path, match.new_path, match.similarity) for match in renames
            ),
            tuple(sorted(excluded_names)),
        ),
        conflicts,
    )


def _refresh_directory_membership(after, excluded_names, baselines, snapshot):
    # Directory membership follows public names; it is never stored as Context items.
    while True:
        empty_missing = {
            name
            for name, context in after.items()
            if context.corresponding_document_metadata
            and context.corresponding_document_metadata.role == "package"
            and context.uid in baselines
            and name not in snapshot.directories
            and name not in excluded_names
            and not tuple(context.iter_memories())
            and not any(
                child.startswith(name + "/") for child in after if child != name
            )
        }
        if not empty_missing:
            break
        for name in empty_missing:
            del after[name]
        for context in after.values():
            if (
                context.corresponding_document_metadata
                and context.corresponding_document_metadata.role == "package"
            ):
                for item in list(context.iter_memories()):
                    if type(item) is Context and item.name in empty_missing:
                        context.remove(item.uid)


def _prepare_profile_exports(
    after,
    attached_data,
    excluded_names,
    excluded_path,
    additions,
    inbound,
    external,
    baselines,
    connections,
    active_units,
    snapshot,
):
    new_content = MemContent(
        tuple(after[name] for name in sorted(after) if name not in excluded_names),
        attached_data,
    )
    next_units = [
        unit
        for unit in prepare_sync_document_units(new_content)
        if not set(unit[1]).intersection(excluded_names)
    ]
    new_connections = []
    new_baselines = []
    output = []
    directories = set()
    for owner, members, files, unit_directories in next_units:
        if any(excluded_path(file.path) for file in files):
            continue
        output.extend(files)
        directories.update(unit_directories)
        for file in files:
            directories.update(
                str(parent)
                for parent in PurePosixPath(file.path).parents
                if str(parent) != "."
            )
            # Newly accepted bytes must round-trip exactly before any write.
            if (
                file.path in additions
                or file.path in {path for change in inbound for path in change.paths}
            ) and external.get(file.path) != file.data:
                raise ValueError(
                    f"Document conversion cannot reproduce exact external bytes: {file.path}"
                )
            if (
                owner.uid not in baselines
                and external.get(file.path) is not None
                and external[file.path] != file.data
            ):
                raise ValueError(
                    f"External Sync changes conflict with an unconnected Context: {file.path}"
                )
        new_connections.append(
            SyncConnection(
                owner.uid,
                owner.name,
                external_document_locator(snapshot.root),
                tuple(file.path for file in files),
                tuple(sorted(set(unit_directories))),
                members,
                True,
            )
        )
        new_baselines.append(
            (
                owner.uid,
                SyncBaseline(
                    member_digest(tuple(after[name] for name in members)),
                    tuple((file.path, file.data) for file in files),
                    tuple(after[name].to_dict() for name in members),
                    tuple((file.path, file.source_ranges) for file in files),
                ),
            )
        )
    output_paths = {file.path for file in output}
    old_paths = {
        path
        for unit in active_units
        for path in connections.get(
            unit[0].uid, SyncConnection(unit[0].uid, unit[0].name, {}, ())
        ).paths
    }
    previous_files = {path: external.get(path) for path in output_paths | old_paths}
    for path in old_paths - output_paths:
        if previous_files[path] is not None:
            baseline_bytes = next(
                (
                    dict(baseline.files)[path]
                    for baseline in baselines.values()
                    if path in dict(baseline.files)
                ),
                None,
            )
            if previous_files[path] != baseline_bytes:
                raise ValueError(
                    f"External removal conflicts with newer file changes: {path}"
                )
    export = plan_export_documents(
        snapshot.root,
        tuple(output),
        previous_files,
        removals=tuple(sorted(old_paths - output_paths)),
        directories=tuple(sorted(directories)),
    )
    return export, new_connections, new_baselines


def _context_record_changes(before, after, change_paths, effects):
    by_uid_before = {record["uid"]: record for record in before.values()}
    by_uid_after = {context.uid: context.to_dict() for context in after.values()}
    changes = []
    for uid in sorted(by_uid_before.keys() | by_uid_after.keys()):
        prior, following = by_uid_before.get(uid), by_uid_after.get(uid)
        if prior == following:
            continue
        action = (
            "ADD"
            if prior is None
            else "REMOVE"
            if following is None
            else "RENAME"
            if prior["name"] != following["name"]
            else "EDIT"
        )
        changes.append(
            SyncContextChange(prior, following, action, change_paths.get(uid, ()))
        )
        if action in {"ADD", "REMOVE"}:
            subject = following or prior
            effects.extend(
                SyncMemoryEffect(subject["name"], memory_uid, action)
                for memory_uid, item in subject["memories"].items()
                if item["type"] == "memory"
            )
    return changes
