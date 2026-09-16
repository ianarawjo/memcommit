"""Immediate document Import; input/validation completes before publication."""

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol

from memcommit.application.capabilities.import_export.conversion import (
    convert_for_import,
    detect_format,
)
from memcommit.application.capabilities.import_export.model import (
    ConversionIssue,
    InputFile,
    MemContent,
)


@dataclass(frozen=True)
class ImportRequest:
    source: Path
    target: str | None = None
    name: str | None = None
    format: str | None = None
    recursive: bool = False


@dataclass(frozen=True)
class ImportResult:
    source: Path
    target_contexts: tuple[str, ...]
    files: tuple[tuple[str, str, str], ...]
    memory_count: int
    checkpoints: tuple[str, ...]
    issues: tuple[ConversionIssue, ...] = ()


class ImportPort(Protocol):
    def resolve_target(self, request: ImportRequest) -> str: ...
    def read_source(
        self, request: ImportRequest
    ) -> tuple[tuple[InputFile, ...], tuple[ConversionIssue, ...], bool]: ...
    def save_content(self, target: str, content: MemContent) -> ImportResult: ...


def run_import(request: ImportRequest, port: ImportPort) -> ImportResult:
    if not isinstance(request, ImportRequest):
        raise TypeError("Expected ImportRequest.")
    if request.name is not None and request.target is not None:
        raise ValueError("Use --as NEW_ROOT or --into PARENT, not both.")
    files, read_issues, single_file = port.read_source(request)
    format = detect_format(files, request.format)
    request = replace(request, format=format)
    target = port.resolve_target(request)
    content, issues = convert_for_import(files, format, target, single_file=single_file)
    result = port.save_content(target, content)
    return replace(result, issues=read_issues + issues)
