"""Small publication manifests and immutable outbound Sync execution receipts."""

from datetime import datetime, timezone
from uuid import UUID
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic
from .settings_repository import read_sync_record, sync_record_path


class SyncRunRepository:
    def __init__(self, store):
        self.store = store

    def pending(self):
        return read_sync_record(sync_record_path(self.store, "pending.json"), None)

    def start(self, manifest):
        self.store._assert_profile_write_allowed()
        _write_json_atomic(
            sync_record_path(self.store, "pending.json"),
            {"schema_version": 1, **manifest},
        )

    def complete(self, result, causing_command):
        self.store._assert_profile_write_allowed()
        uid = str(UUID(result.run_uid))
        path = sync_record_path(self.store, "runs", uid + ".json")
        _write_json_atomic(
            path,
            {
                "schema_version": 1,
                "uid": uid,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "command": "sync",
                "direction": "outbound",
                "context_names": result.context_names,
                "automatic": result.automatic,
                "causing_command": causing_command,
                "effects": [
                    {
                        "path": effect.path,
                        "action": effect.action,
                        "attached": effect.attached,
                    }
                    for effect in result.effects
                ],
            },
        )
        sync_record_path(self.store, "pending.json").unlink(missing_ok=True)
