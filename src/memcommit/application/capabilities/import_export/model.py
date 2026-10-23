"""Transient values for document conversion; persisted layout belongs to core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from memcommit.models.context import Context
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)


class DocumentFormat(str, Enum):
    MARKDOWN = "md"
    TEXT = "txt"
    YAML = "yaml"


class PackageFormat(str, Enum):
    DOCUMENTS = "documents"
    SKILL = "skill"
    MEM = "mem"


@dataclass(frozen=True)
class InputFile:
    path: str
    data: bytes


@dataclass(frozen=True)
class ProjectDocumentSnapshot:
    root: Path
    files: tuple[tuple[str, bytes], ...]
    ignore_bytes: bytes | None
    directories: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemorySourceRange:
    context_uid: str
    context_name: str
    memory_uid: str
    start: int
    end: int


@dataclass(frozen=True)
class DocumentSourceRange:
    start: int
    end: int
    source: MemorySourceRange


@dataclass(frozen=True)
class DocumentBlock:
    kind: str
    text: str
    children: tuple[DocumentBlock, ...] = ()
    start_byte: int = field(default=0, compare=False)
    end_byte: int = field(default=0, compare=False)
    source: MemorySourceRange | None = field(default=None, compare=False)


@dataclass(frozen=True)
class Document:
    state: CorrespondingDocumentMetadata
    blocks: tuple[DocumentBlock, ...]


@dataclass(frozen=True)
class DocumentPackage:
    documents: tuple[Document, ...]
    attached_files: tuple[InputFile, ...] = ()
    format: PackageFormat = PackageFormat.DOCUMENTS


@dataclass(frozen=True)
class MemContent:
    contexts: tuple[Context, ...]
    attached_data: dict[str, bytes] = field(default_factory=dict)


@dataclass(frozen=True)
class OutputFile:
    path: str
    data: bytes
    attached: bool = False
    source_ranges: tuple[DocumentSourceRange, ...] = field(default=(), compare=False)


@dataclass(frozen=True)
class ExportFileEffect:
    path: str
    action: str
    attached: bool = False


@dataclass(frozen=True)
class ExportPlan:
    destination: Path
    files: tuple[OutputFile, ...]
    removals: tuple[str, ...]
    directories: tuple[str, ...]
    previous_hashes: tuple[tuple[str, str | None], ...]
    effects: tuple[ExportFileEffect, ...]
    removed_directories: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConversionIssue:
    code: str
    path: str
    message: str
    blocking: bool = True


class ConversionError(ValueError):
    def __init__(self, issues: tuple[ConversionIssue, ...]):
        self.issues = issues
        super().__init__("; ".join(f"{i.path}: {i.message}" for i in issues))


def fail(code: str, path: str, message: str):
    raise ConversionError((ConversionIssue(code, path, message),))
