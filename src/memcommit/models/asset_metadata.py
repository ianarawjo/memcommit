"""Metadata locating retained asset bytes within a document package."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re

from memcommit.core.document_path import relative_document_path


@dataclass(frozen=True)
class AssetMetadata:
    """Identify an asset by its relative path and immutable content hash."""

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
