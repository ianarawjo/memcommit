"""Durable completed Update evidence; no pending work or mutable status."""

from __future__ import annotations
import json
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from memcommit.application.operations.update.model import UpdateReceipt
from memcommit.persistence.store.infrastructure.atomic_io import (
    _write_json_atomic,
    _reject_duplicate_json_keys,
)


def _decode_completed_receipt(data):
    from memcommit.application.operations.update.model import UpdateReceipt

    if not isinstance(data, dict) or "status" not in data:
        return UpdateReceipt.from_dict(data)
    # Retained historical receipts remain evidence. This decoder never opens
    # a pending-work file and cannot restore the removed resume lifecycle.
    version = data.get("schema_version")
    if version not in {6, 7, 8, 9, 10} or data.get("status") not in {
        "applied",
        "undone",
    }:
        raise ValueError("Expected completed Update evidence.")
    keys = {
        "schema_version",
        "uid",
        "status",
        "created_at",
        "source",
        "target",
        "operations",
        "application",
    }
    if version in {9, 10}:
        keys.add("goal_focus")
    if set(data) != keys:
        raise ValueError("Invalid historical Update receipt.")
    inputs = {"goal_focus": data.get("goal_focus"), "inline_source_content": None}
    for role in ("source", "target"):
        endpoint = data[role]
        fields = {"uid", "name", "digest", "contexts", "access", "include_descendants"}
        if version >= 7:
            fields.add("memory_uid")
        if role == "source" and version in {8, 10}:
            fields.add("inline_memory")
        if not isinstance(endpoint, dict) or set(endpoint) != fields:
            raise ValueError("Invalid historical Update input.")
        for field in ("uid", "name", "digest", "contexts", "include_descendants"):
            inputs[f"{role}_{field}"] = endpoint[field]
        inputs[f"{role}_memory_uid"] = endpoint.get("memory_uid")
        inputs[f"granted_{role}"] = endpoint["access"]
        if "inline_memory" in endpoint:
            inline = endpoint["inline_memory"]
            from memcommit.application.operations.update.model import (
                inline_update_context,
            )

            if not isinstance(inline, dict) or set(inline) != {"uid", "content"}:
                raise ValueError("Invalid historical inline Source.")
            source = inline_update_context(inline["content"])
            if inline["uid"] != next(iter(source.memories)):
                raise ValueError("Invalid historical inline Memory identity.")
            inputs["inline_source_content"] = inline["content"]
    return UpdateReceipt.from_dict(
        {
            "schema_version": 1,
            "uid": data["uid"],
            "inputs": inputs,
            "operations": data["operations"],
            "application": data["application"],
        }
    )


class UpdateReceiptRepository:
    def __init__(self, store):
        self.store = store
        self.directory = store.store_dir / "update-receipts"

    def path(self, operation_uid):
        if str(uuid.UUID(operation_uid)) != operation_uid:
            raise ValueError("Invalid Update receipt UID.")
        return self.directory / f"{operation_uid}.json"

    def save(self, receipt: UpdateReceipt):
        from memcommit.application.operations.update.model import UpdateReceipt

        self.store._assert_profile_write_allowed()
        if not isinstance(receipt, UpdateReceipt):
            raise TypeError("Expected a completed UpdateReceipt.")
        data = receipt.to_dict()
        if UpdateReceipt.from_dict(data) != receipt:
            raise ValueError("Update receipt changed during validation.")
        path = self.path(receipt.uid)
        if path.exists() or path.is_symlink():
            if self.load(receipt.uid) != receipt:
                raise ValueError("Update receipt already contains different evidence.")
            return
        if self.directory.is_symlink():
            raise ValueError("Invalid Update receipt directory.")
        _write_json_atomic(path, data)

    def load(self, operation_uid) -> UpdateReceipt:
        path = self.path(operation_uid)
        if path.is_symlink() or self.directory.is_symlink():
            raise ValueError("Invalid Update receipt storage.")
        with path.open(encoding="utf-8") as stream:
            receipt = _decode_completed_receipt(
                json.load(stream, object_pairs_hook=_reject_duplicate_json_keys)
            )
        if receipt.uid != operation_uid:
            raise ValueError("Update receipt identity does not match its path.")
        return receipt

    def list(self):
        if not self.directory.exists():
            return ()
        if self.directory.is_symlink() or not self.directory.is_dir():
            raise ValueError("Invalid Update receipt storage.")
        receipts = [self.load(path.stem) for path in self.directory.glob("*.json")]
        return tuple(
            sorted(
                receipts, key=lambda r: (r.application.applied_at, r.uid), reverse=True
            )
        )


class _UpdateReceiptStoreMixin:
    def load_update_receipt(self, operation_uid):
        return UpdateReceiptRepository(self).load(operation_uid)
