"""Validated Update change operations and their source evidence."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Literal, TypeAlias


class UpdateError(RuntimeError):
    """Safe, user-facing semantic update error."""
def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_json(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return _sha256_text(encoded)


def _strict_json_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    """Build one JSON object while rejecting duplicate keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _is_sha256(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _require_exact_keys(
    value: object,
    keys: set[str],
    label: str,
) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError(f"Invalid {label}.")
    return value


def _require_string(value: object, label: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise ValueError(f"Invalid {label}.")
    return value


def _require_uuid(value: object, label: str) -> str:
    text = _require_string(value, label)
    try:
        parsed = uuid.UUID(text)
    except ValueError as error:
        raise ValueError(f"Invalid {label}.") from error
    if str(parsed) != text:
        raise ValueError(f"Invalid {label}.")
    return text
@dataclass(frozen=True)
class SourceReference:
    context_uid: str
    context_name: str
    memory_uid: str
    content_digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "memory_uid": self.memory_uid,
            "content_digest": self.content_digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> SourceReference:
        data = _require_exact_keys(
            value,
            {
                "context_uid",
                "context_name",
                "memory_uid",
                "content_digest",
            },
            "source reference",
        )
        digest = data["content_digest"]
        if not _is_sha256(digest):
            raise ValueError("Invalid source reference digest.")
        return cls(
            context_uid=_require_string(
                data["context_uid"],
                "source Context uid",
            ),
            context_name=_require_string(
                data["context_name"],
                "source Context name",
            ),
            memory_uid=_require_string(
                data["memory_uid"],
                "source Memory uid",
            ),
            content_digest=digest,
        )


@dataclass(frozen=True)
class EditOperation:
    owner_context_uid: str
    owner_context_name: str
    memory_uid: str
    old_content: str
    new_content: str
    source_refs: tuple[SourceReference, ...]
    reason: str

    @property
    def operation(self) -> Literal["edit"]:
        return "edit"

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "owner_context": {
                "uid": self.owner_context_uid,
                "name": self.owner_context_name,
            },
            "memory_uid": self.memory_uid,
            "old_content": self.old_content,
            "new_content": self.new_content,
            "source_refs": [source.to_dict() for source in self.source_refs],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AddOperation:
    owner_context_uid: str
    owner_context_name: str
    memory_uid: str
    new_content: str
    source_refs: tuple[SourceReference, ...]
    reason: str

    @property
    def operation(self) -> Literal["add"]:
        return "add"

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "owner_context": {
                "uid": self.owner_context_uid,
                "name": self.owner_context_name,
            },
            "memory_uid": self.memory_uid,
            "new_content": self.new_content,
            "source_refs": [source.to_dict() for source in self.source_refs],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RemoveOperation:
    owner_context_uid: str
    owner_context_name: str
    memory_uid: str
    old_content: str
    source_refs: tuple[SourceReference, ...]
    reason: str

    @property
    def operation(self) -> Literal["remove"]:
        return "remove"

    def to_dict(self) -> dict[str, object]:
        return {
            "operation": self.operation,
            "owner_context": {
                "uid": self.owner_context_uid,
                "name": self.owner_context_name,
            },
            "memory_uid": self.memory_uid,
            "old_content": self.old_content,
            "source_refs": [source.to_dict() for source in self.source_refs],
            "reason": self.reason,
        }


UpdateOperation: TypeAlias = EditOperation | AddOperation | RemoveOperation


def operation_digest(operations: tuple[UpdateOperation, ...]) -> str:
    """Hash the exact ordered operation set approved for one update."""
    return _sha256_json([operation.to_dict() for operation in operations])
def _parse_owner(value: object) -> tuple[str, str]:
    owner = _require_exact_keys(value, {"uid", "name"}, "operation owner")
    return (
        _require_string(owner["uid"], "operation owner uid"),
        _require_string(owner["name"], "operation owner name"),
    )


def _parse_source_refs(value: object) -> tuple[SourceReference, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("Invalid operation source references.")
    refs = tuple(SourceReference.from_dict(item) for item in value)
    identities = {(ref.context_uid, ref.memory_uid) for ref in refs}
    if len(identities) != len(refs):
        raise ValueError("Duplicate operation source reference.")
    return refs


def _operation_from_dict(value: object) -> UpdateOperation:
    if not isinstance(value, dict):
        raise ValueError("Invalid update operation.")
    operation = value.get("operation")
    if operation == "edit":
        data = _require_exact_keys(
            value,
            {
                "operation",
                "owner_context",
                "memory_uid",
                "old_content",
                "new_content",
                "source_refs",
                "reason",
            },
            "edit operation",
        )
        owner_uid, owner_name = _parse_owner(data["owner_context"])
        old_content = _require_string(
            data["old_content"],
            "edit old content",
            empty=True,
        )
        new_content = _require_string(
            data["new_content"],
            "edit new content",
        )
        if old_content == new_content:
            raise ValueError("Invalid no-op edit operation.")
        return EditOperation(
            owner_context_uid=owner_uid,
            owner_context_name=owner_name,
            memory_uid=_require_string(
                data["memory_uid"],
                "edit Memory uid",
            ),
            old_content=old_content,
            new_content=new_content,
            source_refs=_parse_source_refs(data["source_refs"]),
            reason=_require_string(data["reason"], "edit reason"),
        )
    if operation == "add":
        data = _require_exact_keys(
            value,
            {
                "operation",
                "owner_context",
                "memory_uid",
                "new_content",
                "source_refs",
                "reason",
            },
            "add operation",
        )
        owner_uid, owner_name = _parse_owner(data["owner_context"])
        return AddOperation(
            owner_context_uid=owner_uid,
            owner_context_name=owner_name,
            memory_uid=_require_uuid(
                data["memory_uid"],
                "added Memory uid",
            ),
            new_content=_require_string(
                data["new_content"],
                "added Memory content",
            ),
            source_refs=_parse_source_refs(data["source_refs"]),
            reason=_require_string(data["reason"], "addition reason"),
        )
    if operation == "remove":
        data = _require_exact_keys(
            value,
            {
                "operation",
                "owner_context",
                "memory_uid",
                "old_content",
                "source_refs",
                "reason",
            },
            "remove operation",
        )
        owner_uid, owner_name = _parse_owner(data["owner_context"])
        return RemoveOperation(
            owner_context_uid=owner_uid,
            owner_context_name=owner_name,
            memory_uid=_require_string(
                data["memory_uid"],
                "removed Memory uid",
            ),
            old_content=_require_string(
                data["old_content"],
                "removed Memory content",
                empty=True,
            ),
            source_refs=_parse_source_refs(data["source_refs"]),
            reason=_require_string(data["reason"], "removal reason"),
        )
    raise ValueError("Invalid update operation type.")
def required_grant_permissions(
    operations: tuple[UpdateOperation, ...],
) -> tuple[str, ...]:
    """Return the exact granted permissions needed to apply a plan."""

    required = {"READ"}
    if any(isinstance(operation, EditOperation) for operation in operations):
        required.add("UPDATE")
    if any(isinstance(operation, AddOperation) for operation in operations):
        required.add("CREATE")
    if any(isinstance(operation, RemoveOperation) for operation in operations):
        required.add("DELETE")
    order = ("READ", "CREATE", "UPDATE", "DELETE")
    return tuple(permission for permission in order if permission in required)
