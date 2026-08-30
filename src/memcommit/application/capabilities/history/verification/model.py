"""Shared evidence values for retained-record verification."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal


MemoryHistoryEvidence = Literal["RECORDED", "RECONSTRUCTED", "INFERRED", "UNRECORDED"]

TRACE_METADATA_SCHEMA_VERSION = 3
TRACE_METADATA_NORMAL_FORM_SCHEMA_VERSION = 4
TRACE_METADATA_REVIEWED_LEGACY_SCHEMA_VERSION = 2
TRACE_METADATA_LEGACY_SCHEMA_VERSION = 1


class MemoryHistoryReconstructionError(RuntimeError):
    """Safe, user-facing failure while reading provenance."""


@dataclass(frozen=True)
class MemoryState:
    uid: str
    content: str
    position: int

    @property
    def content_digest(self) -> str:
        return hashlib.sha256(self.content.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "content": self.content,
            "position": self.position,
            "content_digest": self.content_digest,
        }


@dataclass(frozen=True)
class SourceOccurrence:
    mode: str
    ordinal: int
    total: int
    line_number: int | None = None
    raw_line: str | None = None
    exact_raw_source: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "ordinal": self.ordinal,
            "total": self.total,
            "line_number": self.line_number,
            "raw_line": self.raw_line,
            "exact_raw_source": self.exact_raw_source,
        }


@dataclass(frozen=True)
class MemoryHistoryChildEvidence:
    """Recorded source/frame citations for one applied result Memory."""

    result_uid: str
    source_spans: tuple[str, ...]
    frame_spans: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "result_uid": self.result_uid,
            "source_spans": list(self.source_spans),
            "frame_spans": list(self.frame_spans),
        }


@dataclass(frozen=True)
class MemoryHistoryCommandContext:
    """One Context named by a retained command-unit receipt."""

    uid: str
    name: str

    def to_dict(self) -> dict[str, str]:
        return {"uid": self.uid, "name": self.name}


@dataclass(frozen=True)
class MemoryHistoryCommandOperation:
    """The command boundary shared by one or more Context checkpoints."""

    uid: str
    command: str
    contexts: tuple[MemoryHistoryCommandContext, ...]
    source_uid: str | None = None
    source_command: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "uid": self.uid,
            "command": self.command,
            "contexts": [context.to_dict() for context in self.contexts],
            "source_uid": self.source_uid,
            "source_command": self.source_command,
        }


@dataclass(frozen=True)
class MemoryHistoryContextTransition:
    """One recorded ancestry transition between Context-bound occurrences."""

    source: MemoryHistoryCommandContext
    target: MemoryHistoryCommandContext

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
        }
