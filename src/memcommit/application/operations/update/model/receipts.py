"""Frozen Context fingerprints and durable Update application receipts."""

from __future__ import annotations

from dataclasses import dataclass

from .changes import (
    _is_sha256,
    _require_exact_keys,
    _require_string,
    _require_uuid,
)


@dataclass(frozen=True)
class ContextFingerprint:
    uid: str
    name: str
    digest: str

    def to_dict(self) -> dict[str, str]:
        return {
            "uid": self.uid,
            "name": self.name,
            "digest": self.digest,
        }

    @classmethod
    def from_dict(cls, value: object) -> ContextFingerprint:
        data = _require_exact_keys(
            value,
            {"uid", "name", "digest"},
            "Context fingerprint",
        )
        digest = data["digest"]
        if not _is_sha256(digest):
            raise ValueError("Invalid Context fingerprint digest.")
        return cls(
            uid=_require_string(data["uid"], "Context fingerprint uid"),
            name=_require_string(data["name"], "Context fingerprint name"),
            digest=digest,
        )
@dataclass(frozen=True)
class UpdateCheckpointReceipt:
    context_uid: str
    context_name: str
    checkpoint_uid: str

    def to_dict(self) -> dict[str, str]:
        return {
            "context_uid": self.context_uid,
            "context_name": self.context_name,
            "checkpoint_uid": self.checkpoint_uid,
        }

    @classmethod
    def from_dict(cls, value: object) -> UpdateCheckpointReceipt:
        data = _require_exact_keys(
            value,
            {"context_uid", "context_name", "checkpoint_uid"},
            "update checkpoint receipt",
        )
        return cls(
            context_uid=_require_string(
                data["context_uid"],
                "checkpoint owner Context uid",
            ),
            context_name=_require_string(
                data["context_name"],
                "checkpoint owner Context name",
            ),
            checkpoint_uid=_require_uuid(
                data["checkpoint_uid"],
                "update checkpoint uid",
            ),
        )


@dataclass(frozen=True)
class UpdateApplicationReceipt:
    applied_at: str
    operation_digest: str
    target_digest: str
    target_contexts: tuple[ContextFingerprint, ...]
    checkpoints: tuple[UpdateCheckpointReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "applied_at": self.applied_at,
            "operation_digest": self.operation_digest,
            "target_digest": self.target_digest,
            "target_contexts": [context.to_dict() for context in self.target_contexts],
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints],
        }

    @classmethod
    def from_dict(cls, value: object) -> UpdateApplicationReceipt:
        data = _require_exact_keys(
            value,
            {
                "applied_at",
                "operation_digest",
                "target_digest",
                "target_contexts",
                "checkpoints",
            },
            "update application receipt",
        )
        operation_hash = data["operation_digest"]
        target_digest = data["target_digest"]
        if not _is_sha256(operation_hash):
            raise ValueError("Invalid update operation digest.")
        if not _is_sha256(target_digest):
            raise ValueError("Invalid applied target digest.")
        if not isinstance(data["target_contexts"], list):
            raise ValueError("Invalid applied target Context fingerprints.")
        if not isinstance(data["checkpoints"], list):
            raise ValueError("Invalid update checkpoint receipts.")
        target_contexts = tuple(
            ContextFingerprint.from_dict(item) for item in data["target_contexts"]
        )
        checkpoints = tuple(
            UpdateCheckpointReceipt.from_dict(item) for item in data["checkpoints"]
        )
        context_identities = [
            (context.uid, context.name) for context in target_contexts
        ]
        if len(context_identities) != len(set(context_identities)):
            raise ValueError("Duplicate applied target Context fingerprint.")
        checkpoint_owners = [
            (checkpoint.context_uid, checkpoint.context_name)
            for checkpoint in checkpoints
        ]
        if len(checkpoint_owners) != len(set(checkpoint_owners)):
            raise ValueError("Duplicate update checkpoint owner.")
        if not set(checkpoint_owners) <= set(context_identities):
            raise ValueError("Update checkpoint owner is outside the target.")
        return cls(
            applied_at=_require_string(
                data["applied_at"],
                "update application time",
            ),
            operation_digest=operation_hash,
            target_digest=target_digest,
            target_contexts=target_contexts,
            checkpoints=checkpoints,
        )
