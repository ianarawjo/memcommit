"""Small publication manifests and immutable Sync execution receipts."""

from datetime import datetime, timezone
from uuid import UUID

from .settings_repository import read_sync_record, sync_record_path


class SyncRunRepository:
    def __init__(self, store):
        self.store = store

    def receipt_record(self, result, causing_command=None):
        uid = str(UUID(result.run_uid))
        return {
            "schema_version": 1,
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
            record = read_sync_record(path, None)
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
            or record.get("profile", {}).get("lifecycle")
            or record.get("profile", {}).get("restoration")
        )
