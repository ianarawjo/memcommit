"""Immutable completed Update evidence, independent of work-in-progress state."""

from __future__ import annotations
from dataclasses import dataclass
from .fingerprints import ContextFingerprint
from .inputs import UpdateContextInputs
from .plan import UpdatePlan
from .changes import (
    _is_sha256,
    _require_exact_keys,
    _require_string,
    _require_uuid,
    _operation_from_dict,
    AddOperation,
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


@dataclass(frozen=True, slots=True)
class UpdateReceipt:
    inputs: UpdateContextInputs
    plan: UpdatePlan
    application: UpdateApplicationReceipt

    @property
    def uid(self) -> str:
        return self.plan.uid

    def __post_init__(self) -> None:
        if (self.plan.target_uid, self.plan.target_name) != (
            self.inputs.target_uid,
            self.inputs.target_name,
        ):
            raise ValueError("Update receipt names a different Target.")
        if self.application.operation_digest != self.plan.digest:
            raise ValueError("Update receipt does not match its operations.")
        identities = [
            (op.owner_context_uid, op.memory_uid) for op in self.plan.operations
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate Update effect.")
        owners = {
            (op.owner_context_uid, op.owner_context_name) for op in self.plan.operations
        }
        checkpoints = {
            (cp.context_uid, cp.context_name) for cp in self.application.checkpoints
        }
        if owners != checkpoints:
            raise ValueError("Update checkpoints do not cover its changed Contexts.")
        before = [(c.uid, c.name) for c in self.inputs.target_contexts]
        after = [(c.uid, c.name) for c in self.application.target_contexts]
        if before != after or not owners <= set(before):
            raise ValueError("Update receipt changed its Target identities.")
        for op in self.plan.operations:
            if self.inputs.target_memory_uid is not None and (
                isinstance(op, AddOperation)
                or op.memory_uid != self.inputs.target_memory_uid
            ):
                raise ValueError("Update effect exceeds its Target Memory scope.")
            if self.inputs.source_memory_uid is not None and any(
                ref.memory_uid != self.inputs.source_memory_uid
                for ref in op.source_refs
            ):
                raise ValueError("Update effect exceeds its Source Memory scope.")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "uid": self.uid,
            "inputs": self.inputs.to_dict(),
            "operations": [op.to_dict() for op in self.plan.operations],
            "application": self.application.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> UpdateReceipt:
        data = _require_exact_keys(
            value,
            {"schema_version", "uid", "inputs", "operations", "application"},
            "Update receipt",
        )
        if (
            type(data["schema_version"]) is not int
            or data["schema_version"] != 1
            or not isinstance(data["operations"], list)
        ):
            raise ValueError("Invalid Update receipt schema.")
        inputs = UpdateContextInputs.from_dict(data["inputs"])
        plan = UpdatePlan(
            _require_uuid(data["uid"], "Update operation uid"),
            inputs.target_uid,
            inputs.target_name,
            tuple(_operation_from_dict(op) for op in data["operations"]),
        )
        return cls(
            inputs, plan, UpdateApplicationReceipt.from_dict(data["application"])
        )
