"""Export request, execution, and result independent of terminal presentation."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from memcommit.application.capabilities.import_export.conversion import (
    convert_for_export,
)
from memcommit.application.capabilities.import_export.model import (
    ConversionIssue,
    MemContent,
    OutputFile,
)


@dataclass(frozen=True)
class ExportRequest:
    source: str | None = None
    destination: Path | None = None
    format: str | None = None
    recursive: bool = False
    skill_name: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class ExportResult:
    source_contexts: tuple[str, ...]
    destination: Path
    files: tuple[tuple[str, bool], ...]
    issues: tuple[ConversionIssue, ...] = ()


class ExportPort(Protocol):
    def load_content(self, request: ExportRequest) -> MemContent: ...
    def resolve_destination(
        self, request: ExportRequest, files: tuple[OutputFile, ...]
    ) -> Path: ...
    def write_files(
        self, destination: Path, files: tuple[OutputFile, ...]
    ) -> tuple[str, ...]: ...


def run_export(request: ExportRequest, port: ExportPort) -> ExportResult:
    if not isinstance(request, ExportRequest):
        raise TypeError("Expected ExportRequest.")
    if (request.skill_name is None) != (request.description is None):
        raise ValueError("Supply --skill-name and --description together.")
    if request.skill_name is not None and request.format != "skill":
        raise ValueError("New skill metadata requires --format skill.")
    content = port.load_content(request)
    files, issues = convert_for_export(
        content,
        request.format,
        skill_name=request.skill_name,
        description=request.description,
    )
    destination = port.resolve_destination(request, files)
    written = port.write_files(destination, files)
    return ExportResult(
        tuple(c.name for c in content.contexts),
        destination,
        tuple((path, file.attached) for path, file in zip(written, files, strict=True)),
        issues,
    )
