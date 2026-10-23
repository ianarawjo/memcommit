"""Reconcile Skill sections together while retaining their separate Contexts."""

from dataclasses import replace

from memcommit.application.capabilities.import_export.formats.skill import (
    parse_skill,
    split_skill_text,
    validate_skill,
)
from memcommit.application.capabilities.import_export.model import InputFile
from memcommit.application.operations.mem_sync.model import SyncConflictError, SyncIssue

from .import_document_changes import import_document_changes
from .import_yaml_changes import import_yaml_changes


def import_skill_changes(
    body,
    metadata,
    baseline_file,
    external_bytes,
    ranges,
    *,
    path,
    renamed_skill_name=None,
):
    def conflict(code, message):
        raise SyncConflictError(SyncIssue(code, path, message))

    if max(len(baseline_file), len(external_bytes)) > 2_000_000:
        conflict(
            "match-limit", "Document exceeds the bounded automatic matching limit."
        )
    old_package = parse_skill((InputFile("SKILL.md", baseline_file),))
    new_package = parse_skill((InputFile("SKILL.md", external_bytes),))
    new_name = validate_skill(new_package)["name"]
    if (
        validate_skill(old_package)["name"] != new_name
        and new_name != renamed_skill_name
    ):
        conflict(
            "skill-name",
            "Changing a Skill name requires explicit placement and import.",
        )
    old_sections = split_skill_text(baseline_file.decode("utf-8"))
    new_sections = split_skill_text(external_bytes.decode("utf-8"))
    if (old_sections[0], old_sections[2]) != (new_sections[0], new_sections[2]):
        conflict(
            "layout-conflict", "Skill frontmatter delimiters must remain unchanged."
        )
    changes = []
    for context, index, importer in (
        (metadata, 1, import_yaml_changes),
        (body, 3, import_document_changes),
    ):
        old_section = old_sections[index].encode("utf-8")
        new_section = new_sections[index].encode("utf-8")
        if old_section == new_section:
            continue
        offset = len("".join(old_sections[:index]).encode("utf-8"))
        owned = tuple(span for span in ranges if span.source.context_uid == context.uid)
        if any(
            not offset <= span.start < span.end <= offset + len(old_section)
            for span in owned
        ):
            conflict(
                "invalid-attribution", "Skill section ownership crosses its delimiters."
            )
        section_ranges = tuple(
            replace(span, start=span.start - offset, end=span.end - offset)
            for span in owned
        )
        changes.append(
            importer(context, old_section, new_section, section_ranges, path=path)
        )
    return tuple(changes)
