"""Transient values for document conversion; persisted layout belongs to core."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from memcommit.core.context import Context
from memcommit.core.document import DocumentState


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
class DocumentBlock:
    kind: str
    text: str
    children: tuple[DocumentBlock, ...] = ()


@dataclass(frozen=True)
class Document:
    state: DocumentState
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
