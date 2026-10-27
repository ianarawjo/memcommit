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
            from memcommit.application.operations.update.model import UpdateReceipt

            receipt = UpdateReceipt.from_dict(
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
