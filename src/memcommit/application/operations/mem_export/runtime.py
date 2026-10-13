"""Ordinary Export placement over shared readable-source and publication ports."""

from pathlib import Path
from memcommit.application.capabilities.import_export.export_runtime import (
    DocumentExportRuntime,
)
from memcommit.application.capabilities.import_export.model import InputFile
from memcommit.application.capabilities.import_export.formats.skill import (
    parse_skill,
    validate_skill,
)


class ExportRuntime(DocumentExportRuntime):
    def resolve_destination(self, request, files):
        skill_file = next((f for f in files if f.path == "SKILL.md"), None)
        skill_name = None
        if skill_file:
            skill_name = validate_skill(
                parse_skill((InputFile("SKILL.md", skill_file.data),))
            )["name"]
        destination = (
            Path(request.destination)
            if request.destination
            else Path.cwd() / (skill_name or self.source_name.rsplit("/", 1)[-1])
        )
        if skill_name and destination.name != skill_name:
            raise ValueError(
                f"Skill output directory must match its name: {skill_name!r}; choose --to .../{skill_name}."
            )
        if destination.is_symlink():
            raise ValueError("Export destination cannot be a symbolic link.")
        return destination.expanduser().resolve()
