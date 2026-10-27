"""Project-relative metadata for a Context's corresponding document or directory."""

from dataclasses import asdict, dataclass
from memcommit.core.document_path import relative_document_path


@dataclass(frozen=True)
class CorrespondingDocumentMetadata:
    path: str
    format: str
    role: str = "document"

    def __post_init__(self):
        relative_document_path(self.path)
        if self.format != "md":
            raise ValueError("Unsupported project document format.")
        if self.role not in {"document", "directory"}:
            raise ValueError("Unsupported project document role.")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, record):
        if not isinstance(record, dict) or set(record) != set(cls.__dataclass_fields__):
            raise ValueError("Invalid document state fields.")
        return cls(**record)
