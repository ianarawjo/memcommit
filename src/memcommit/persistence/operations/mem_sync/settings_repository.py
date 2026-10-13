"""One atomic settings frame for document bindings and selected-set toggles."""

import json
from pathlib import Path
from uuid import UUID

from memcommit.application.operations.mem_sync.model import SyncConnection
from memcommit.configuration.config import resolve_external_document_locator
from memcommit.core.document import relative_document_path
from memcommit.persistence.store.infrastructure.atomic_io import (
    _write_json_atomic,
    _reject_duplicate_json_keys,
)


def sync_record_path(store, *segments):
    path = store.store_dir / "sync"
    for segment in segments:
        path = path / segment
    for parent in (store.store_dir / "sync", *path.parents):
        if parent == store.store_dir:
            break
        if parent.is_symlink():
            raise ValueError(f"Invalid Sync record directory: {parent}")
    if path.is_symlink():
        raise ValueError(f"Invalid Sync record: {path}")
    return path


def read_sync_record(path: Path, default):
    if not path.exists():
        return default
    with path.open(encoding="utf-8") as stream:
        record = json.load(stream, object_pairs_hook=_reject_duplicate_json_keys)
    if not isinstance(record, dict) or record.get("schema_version") != 1:
        raise ValueError("Invalid Sync record schema.")
    return record


def decode_sync_connection(record):
    if not isinstance(record, dict) or set(record) != set(
        SyncConnection.__dataclass_fields__
    ):
        raise ValueError("Invalid Sync connection fields.")
    if str(UUID(record["context_uid"])) != record["context_uid"]:
        raise ValueError("Invalid Sync Context UID.")
    relative_document_path(record["context_name"])
    resolve_external_document_locator(record["base"])
    if type(record["recursive"]) is not bool:
        raise ValueError("Invalid Sync connection reach.")
    for field in ("paths", "directories", "member_names"):
        if not isinstance(record[field], (list, tuple)):
            raise ValueError("Invalid Sync connection members.")
        for path in record[field]:
            relative_document_path(path)
    return SyncConnection(
        record["context_uid"],
        record["context_name"],
        record["base"],
        tuple(record["paths"]),
        tuple(record["directories"]),
        tuple(record["member_names"]),
        record["recursive"],
    )


class SyncSettingsRepository:
    def __init__(self, store):
        self.store = store

    def load(self):
        record = read_sync_record(
            sync_record_path(self.store, "settings.json"),
            {
                "schema_version": 1,
                "revision": 0,
                "connections": [],
                "policies": [],
                "errors": {},
            },
        )
        if set(record) != {
            "schema_version",
            "revision",
            "connections",
            "policies",
            "errors",
        }:
            raise ValueError("Invalid Sync settings fields.")
        if type(record["revision"]) is not int or record["revision"] < 0:
            raise ValueError("Invalid Sync settings revision.")
        for connection in record["connections"]:
            decode_sync_connection(connection)
        for rule in record["policies"]:
            if (
                set(rule) != {"scope", "name", "uid", "enabled"}
                or type(rule["enabled"]) is not bool
            ):
                raise ValueError("Invalid automatic Sync policy.")
            if rule["scope"] not in {"all", "recursive", "exact"}:
                raise ValueError("Invalid automatic Sync scope.")
            if rule["scope"] != "all":
                relative_document_path(rule["name"])
                if str(UUID(rule["uid"])) != rule["uid"]:
                    raise ValueError("Invalid automatic Sync identity.")
        if not isinstance(record["errors"], dict):
            raise ValueError("Invalid Sync error state.")
        return record

    def save(self, record, *, expected_revision):
        self.store._assert_profile_write_allowed()
        if self.load()["revision"] != expected_revision:
            raise ValueError("Sync settings changed; retry Sync alone.")
        record = {**record, "revision": expected_revision + 1}
        _write_json_atomic(sync_record_path(self.store, "settings.json"), record)
        return record
