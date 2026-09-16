"""Current document layout and attached-file identities, retained by checkpoints.

These values describe the current artifact, not an original-file snapshot or
source-offset map. Text and syntax live in ordinary Memory.content values.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
import re


def relative_document_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("Document path must be a nonempty relative POSIX path.")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in value.split("/")):
        raise ValueError(f"Document path escapes its package: {value!r}.")
    if any(":" in part for part in path.parts):
        raise ValueError(f"Document path contains an invalid segment: {value!r}.")
    return value


@dataclass(frozen=True)
class DocumentState:
    path: str
    format: str
    role: str = "document"
    package: str = "documents"
    opening: str = ""
    closing: str = ""

    def __post_init__(self):
        relative_document_path(self.path)
        if self.format not in {"md", "txt", "yaml"}:
            raise ValueError("Unsupported document format.")
        if self.role not in {"document", "package", "skill_body", "skill_metadata"}:
            raise ValueError("Unsupported document role.")
        if self.package not in {"documents", "skill", "mem"}:
            raise ValueError("Unsupported document package.")
        if not isinstance(self.opening, str) or not isinstance(self.closing, str):
            raise ValueError("Document delimiters must be text.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, record):
        if not isinstance(record, dict) or set(record) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid document state fields.")
        return cls(**record)


@dataclass(frozen=True)
class AttachedFile:
    path: str
    sha256: str

    def __post_init__(self):
        relative_document_path(self.path)
        if (
            not isinstance(self.sha256, str)
            or re.fullmatch(r"[0-9a-f]{64}", self.sha256) is None
        ):
            raise ValueError("Invalid attached-file digest.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, record):
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise ValueError("Invalid attached-file fields.")
        return cls(**record)
