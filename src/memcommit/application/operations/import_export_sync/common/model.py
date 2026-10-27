"""Transient values for document conversion; persisted layout belongs to models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from memcommit.models.context import Context
from memcommit.models.corresponding_document_metadata import (
    CorrespondingDocumentMetadata,
)


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
