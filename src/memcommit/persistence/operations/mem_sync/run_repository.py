"""Small publication manifests and immutable Sync execution receipts."""

import json
from datetime import datetime, timezone
from uuid import UUID

from memcommit.persistence.store.infrastructure.atomic_io import (
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


class SyncRunRepository:
    def __init__(self, store):
        self.store = store

    def receipt_record(self, result, causing_command=None):
        uid = str(UUID(result.run_uid))
        return {
            "uid": uid,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "command": "sync",
            "direction": result.direction,
            "trigger": "MANUAL",
            "checkpoint_uids": list(result.checkpoint_uids),
            "memory_effects": [
                {
                    "context_name": effect.context_name,
                    "memory_uid": effect.memory_uid,
                    "action": effect.action,
                }
                for effect in result.memory_effects
            ],
            "context_names": result.context_names,
            "causing_command": causing_command,
            "effects": [
                {
                    "path": effect.path,
                    "action": effect.action,
                    "attached": effect.attached,
                }
                for effect in result.effects
            ],
        }

    def history(self):
        root = sync_record_path(self.store, "runs")
        if not root.exists():
            return ()
        records = []
        for path in sorted(root.glob("*.json")):
            if path.is_symlink() or str(UUID(path.stem)) != path.stem:
                raise ValueError("Invalid Sync execution receipt path.")
            with path.open(encoding="utf-8") as stream:
                record = json.load(stream, object_pairs_hook=_reject_duplicate_json_keys)
            if not isinstance(record, dict):
                raise ValueError("Invalid Sync execution receipt.")
            if record.get("uid") != path.stem:
                raise ValueError(
                    "Sync execution receipt identity differs from its path."
                )
            records.append(record)
        return tuple(records)

    def profile_history(self):
        return tuple(
            record
            for record in self.history()
            if record.get("profile", {}).get("undoable")
            or record.get("profile", {}).get("restoration")
        )
