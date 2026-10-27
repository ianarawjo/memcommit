"""Immutable completed Update evidence, independent of work-in-progress state."""

from __future__ import annotations
from dataclasses import dataclass
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
    checkpoints: tuple[UpdateCheckpointReceipt, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "applied_at": self.applied_at,
            "operation_digest": self.operation_digest,
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints],
        }

    @classmethod
    def from_dict(cls, value: object) -> UpdateApplicationReceipt:
        # Older receipts retain state snapshots; new evidence needs only the effects.
        if isinstance(value, dict):
            value = {
                key: item
                for key, item in value.items()
                if key not in {"target_digest", "target_contexts"}
            }
        data = _require_exact_keys(
            value,
            {
                "applied_at",
                "operation_digest",
                "checkpoints",
            },
            "update application receipt",
        )
        operation_hash = data["operation_digest"]
        if not _is_sha256(operation_hash):
            raise ValueError("Invalid update operation digest.")
        if not isinstance(data["checkpoints"], list):
            raise ValueError("Invalid update checkpoint receipts.")
        checkpoints = tuple(
            UpdateCheckpointReceipt.from_dict(item) for item in data["checkpoints"]
        )
        checkpoint_owners = [
            (checkpoint.context_uid, checkpoint.context_name)
            for checkpoint in checkpoints
        ]
        if len(checkpoint_owners) != len(set(checkpoint_owners)):
            raise ValueError("Duplicate update checkpoint owner.")
        return cls(
            applied_at=_require_string(
                data["applied_at"],
                "update application time",
            ),
            operation_digest=operation_hash,
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
        if not owners <= set(self.inputs.target_contexts):
            raise ValueError("Update receipt has an owner outside its Target scope.")
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
