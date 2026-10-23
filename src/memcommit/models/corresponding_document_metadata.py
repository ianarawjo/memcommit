"""Metadata for the document corresponding to a Context's Memory content."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from memcommit.core.document_path import relative_document_path


@dataclass(frozen=True)
class CorrespondingDocumentMetadata:
    """Describe the corresponding document or package, including its layout."""

    path: str
    format: str
    role: str = "document"
    package: str = "documents"
    opening: str = ""
    closing: str = ""
    path_scope: str = "PACKAGE"

    def __post_init__(self):
        relative_document_path(self.path)
        if self.path_scope not in {"PACKAGE", "PROFILE"}:
            raise ValueError("Unsupported document path scope.")
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
