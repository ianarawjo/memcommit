"""Map literal Context names to shared Export document layouts."""

from copy import deepcopy
from dataclasses import replace
from pathlib import PurePosixPath

from memcommit.application.capabilities.import_export.export_documents import (
    prepare_export_documents,
)
from memcommit.application.capabilities.import_export.model import MemContent
from memcommit.application.capabilities.import_export.formats.skill import (
    parse_skill,
    validate_skill,
)
from memcommit.application.capabilities.import_export.model import InputFile
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)
from memcommit.core.document_path import relative_document_path
from memcommit.models.context import Context


def context_document_is_excluded(context, rules):
    """Decide primary placement before rendering possibly non-exportable content."""
    state = context.corresponding_document_metadata
    if state and state.role == "package":
        return rules.excludes(context.name, directory=True)
    if state and state.role == "skill_metadata":
        path = context.name.removesuffix("/metadata")
    elif state and state.path_scope == "PROFILE":
        path = state.path
    elif state and state.role == "skill_body":
        path = context.name
    elif state:
        original = PurePosixPath(state.path)
        path = (
            context.name
            if context.name.rsplit("/", 1)[-1] == original.name
            else context.name + original.suffix
        )
    else:
        path = (
            context.name
            if context.name.lower().endswith(".md")
            else context.name + ".md"
        )
    return rules.excludes(context.name) or rules.excludes(path)


def prepare_sync_document_units(content: MemContent):
    """Return each identity-owned document unit and its global relative files."""
    by_name = {context.name: context for context in content.contexts}
    consumed = set()
    units = []
    for context in content.contexts:
        if context.name in consumed:
            continue
        state = context.corresponding_document_metadata
        if state and state.role == "skill_metadata":
            continue
        directories = ()
        members = (context.name,)
        if state and state.role == "package":
            # A package is a directory, never a fabricated text Memory.
            if any(not isinstance(item, Context) for item in context.iter_memories()):
                raise ValueError(
                    f"Package Context contains unplaced text: {context.name}"
                )
            cloned = deepcopy(context)
            cloned.asset_metadata = [
                replace(file, path=context.name + "/" + file.path)
                for file in context.asset_metadata
            ]
            files, _ = prepare_export_documents(
                MemContent((cloned,), content.attached_data), allow_empty_package=True
            )
            directories = (
                state.path if state.path_scope == "PROFILE" else context.name,
            )
        elif state and state.role == "skill_body":
            metadata_name = context.name + "/metadata"
            metadata = by_name.get(metadata_name)
            if metadata is None:
                raise ValueError(f"Skill metadata is not selected: {context.name}")
            rendered, _ = prepare_export_documents(
                MemContent((context, metadata), content.attached_data)
            )
            skill_name = validate_skill(
                parse_skill(tuple(InputFile(f.path, f.data) for f in rendered))
            )["name"]
            prefix = context.name.rsplit("/", 1)[0] if "/" in context.name else ""
            if prefix and prefix.rsplit("/", 1)[-1] != skill_name:
                raise ValueError(
                    f"Skill Context directory must match its metadata name: {skill_name!r}."
                )
            files = tuple(
                replace(file, path=(prefix + "/" if prefix else "") + file.path)
                for file in rendered
            )
            members = (context.name, metadata_name)
            consumed.add(metadata_name)
        else:
            cloned = deepcopy(context)
            if state and state.path_scope == "PROFILE":
                cloned.corresponding_document_metadata = state
            elif state:
                original_path = PurePosixPath(state.path)
                final_name = context.name.rsplit("/", 1)[-1]
                if final_name not in {original_path.name, original_path.stem}:
                    raise ValueError(
                        f"Imported document and Context names must agree: {context.name!r}, {state.path!r}."
                    )
                path = (
                    context.name
                    if final_name == original_path.name
                    else context.name + original_path.suffix
                )
                cloned.corresponding_document_metadata = replace(state, path=path)
            else:
                path = (
                    context.name
                    if context.name.lower().endswith(".md")
                    else context.name + ".md"
                )
                cloned.corresponding_document_metadata = CorrespondingDocumentMetadata(
                    path, "md"
                )
            cloned.asset_metadata = [
                replace(file, path=context.name + "/" + file.path)
                for file in context.asset_metadata
            ]
            files, _ = prepare_export_documents(
                MemContent((cloned,), content.attached_data)
            )
        for file in files:
            relative_document_path(file.path)
        units.append((context, members, files, directories))
        consumed.add(context.name)
    return tuple(units)
