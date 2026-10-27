"""Plan Profile document membership and content changes without publishing them."""

from dataclasses import replace
from pathlib import PurePosixPath

from memcommit.application.operations.import_export_sync.common.conversion import (
    parse_project_documents,
    normalize_document_bytes,
    validate_project_document_context_name,
)
from memcommit.application.operations.import_export_sync.common.export_documents import (
    plan_export_documents,
)
from memcommit.application.operations.import_export_sync.common.model import (
    InputFile,
    MemContent,
)
from memcommit.application.operations.import_export_sync.common.project_documents import (
    ProjectDocumentRules,
)
from memcommit.application.operations.import_export_sync.mem_sync.model import (
    ProfileDocumentChanges,
    SyncBaseline,
    SyncContextChange,
    SyncMemoryEffect,
    SyncPlan,
)
from memcommit.models.context import Context
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)

from ..connections.document_paths import (
    context_document_is_excluded,
    prepare_sync_document_units,
)
from ..content_changes.import_document_changes import import_document_changes
from .detect_file_renames import detect_file_renames
from .prepare_inbound_changes import member_digest, prepare_inbound_changes


def plan_context_changes(*, content, baselines, snapshot):
    """Freeze one coherent create/update/rename/remove set for Profile documents."""
    rules = ProjectDocumentRules(snapshot.ignore_bytes)
    for path, _data in snapshot.files:
        if rules.supports(path) and not rules.excludes(path):
            validate_project_document_context_name(path)
    before = {context.name: context.to_dict() for context in content.contexts}
    by_name = {name: Context.from_dict(record) for name, record in before.items()}
    previous_contexts_by_uid = {
        member["uid"]: member
        for baseline in baselines.values()
        for member in baseline.members
    }
    excluded_names = {
        context.name
        for context in content.contexts
        if context_document_is_excluded(context, rules)
    }
    directory_document_uids = set()
    for context in by_name.values():
        state = context.corresponding_document_metadata
        if (
            context.name not in excluded_names
            and state is not None
            and state.role == "directory"
            and context.memories
        ):
            document_path = state.path + ".md"
            if rules.excludes(document_path):
                excluded_names.add(context.name)
                continue
            # Keep the lexical parent and its children; only its own content
            # gains a sibling document in this Sync's atomic publication.
            context.corresponding_document_metadata = CorrespondingDocumentMetadata(
                document_path, "md"
            )
            directory_document_uids.add(context.uid)
    units = prepare_sync_document_units(
        MemContent(
            tuple(
                context
                for context in by_name.values()
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
        path for baseline in baselines.values() for path, _data in baseline.files
    )
    for unit in units:
        owner, members, files, _directories = unit
        known_paths.update(file.path for file in files)
        baseline = baselines.get(owner.uid)
        ignored_agreement = baseline and any(
            excluded_path(path) for path, _data in baseline.files
        )
        if (
            ignored_agreement
            or rules.excludes(
                owner.name,
                directory=bool(
                    owner.corresponding_document_metadata
                    and owner.corresponding_document_metadata.role == "directory"
                ),
            )
            or any(excluded_path(file.path) for file in files)
        ):
            excluded_names.update(members)
        else:
            for file in files:
                if not file.attached:
                    validate_project_document_context_name(file.path)
            active_units.append(unit)
    external = {path: data for path, data in snapshot.files if not excluded_path(path)}
    deleted = {}
    missing_units = {}
    inbound_baselines = dict(baselines)
    inbound_external = dict(external)
    for unit in active_units:
        owner, members, files, _directories = unit
        if any(
            member["name"] == owner.name and uid != owner.uid
            for uid, member in previous_contexts_by_uid.items()
        ):
            raise ValueError(f"Sync Context identity changed: {owner.name}")
        baseline = baselines.get(owner.uid)
        previous_context = previous_contexts_by_uid.get(owner.uid)
        previous_paths = tuple(path for path, _data in baseline.files) if baseline else ()
        if owner.uid in directory_document_uids:
            continue
        if previous_context and (
            previous_context["name"] != owner.name
            or previous_paths != tuple(file.path for file in files)
        ):
            if len(files) != len(previous_paths):
                raise ValueError(f"Sync document placement changed: {owner.name}")
            prior = dict(baseline.files)
            for old_path, file in zip(previous_paths, files, strict=True):
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
            inbound_baselines[owner.uid] = replace(
                baseline,
                files=tuple(
                    (file.path, prior[old_path])
                    for old_path, file in zip(previous_paths, files, strict=True)
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
    change_paths = {
        context.uid: (context.corresponding_document_metadata.path,)
        for context in by_name.values()
        if context.uid in directory_document_uids
    }
    for match in renames:
        owner, members, files, _directories = missing_units[match.old_path]
        parsed = parse_project_documents(
            (InputFile(match.new_path, additions[match.new_path]),)
        )
        body = next(
            context
            for context in parsed.contexts
            if context.corresponding_document_metadata.role == "document"
        )
        new_members = (body.name,)
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
            changes = (
                import_document_changes(
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
            context.corresponding_document_metadata = (
                body.corresponding_document_metadata
            )
            replacements[new_name] = context
            rename_names[old_name] = new_name
            change_paths[context.uid] = (match.old_path, match.new_path)
        # Directory Contexts are real lexical parents, not document Memories.
        for context in parsed.contexts:
            if (
                context.corresponding_document_metadata.role == "directory"
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
        parsed = parse_project_documents(remaining)
        for context in parsed.contexts:
            if context.name in before:
                if context.corresponding_document_metadata.role == "directory":
                    # A document Context can also be a lexical parent.
                    continue
                existing = by_name[context.name]
                if (
                    not existing.corresponding_document_metadata
                    or existing.corresponding_document_metadata.role != "directory"
                    or existing.memories
                ):
                    raise ValueError(
                        f"New document collides with an existing Context: {context.name}"
                    )
                # Adding the parent document retains the directory Context history.
                context.uid = existing.uid
            if context.corresponding_document_metadata.role == "directory":
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
    export, new_baselines = _prepare_profile_exports(
        after,
        content.attached_data,
        excluded_names,
        excluded_path,
        additions,
        inbound,
        external,
        baselines,
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
        (export,),
        tuple(new_baselines),
        ProfileDocumentChanges(
            snapshot,
            tuple(before.values()),
            tuple(changes),
            tuple(effects),
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
            and context.corresponding_document_metadata.role == "directory"
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
                and context.corresponding_document_metadata.role == "directory"
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
            # Only inter-block separators may change while accepting external content.
            if (
                file.path in additions
                or file.path in {path for change in inbound for path in change.paths}
            ) and normalize_document_bytes(
                external.get(file.path), path=file.path
            ) != file.data:
                raise ValueError(
                    f"Document conversion changed content beyond block separators: {file.path}"
                )
            if (
                (owner.uid not in baselines or not baselines[owner.uid].files)
                and external.get(file.path) is not None
                and normalize_document_bytes(external[file.path], path=file.path)
                != file.data
            ):
                raise ValueError(
                    f"External Sync changes conflict with an unconnected Context: {file.path}"
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
        if unit[0].uid in baselines
        for path, _data in baselines[unit[0].uid].files
    }
    # Undo may remove a discovered Context while leaving its workspace file.
    # Only this subsequent explicit Sync may publish that native deletion.
    old_paths.update(
        path
        for baseline in baselines.values()
        if all(member["name"] not in after and member["name"] not in excluded_names for member in baseline.members)
        for path, _data in baseline.files
        if not excluded_path(path)
    )
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
    return export, new_baselines


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
