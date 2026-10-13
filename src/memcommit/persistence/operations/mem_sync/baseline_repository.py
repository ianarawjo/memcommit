"""Retain last successful document bytes independently of Memory attachment GC."""

import base64
from memcommit.application.operations.mem_sync.model import SyncBaseline
from memcommit.core.document import relative_document_path
from memcommit.persistence.store.infrastructure.atomic_io import _write_json_atomic
from .settings_repository import read_sync_record, sync_record_path


class SyncBaselineRepository:
    def __init__(self, store):
        self.store = store

    def load(self):
        record = read_sync_record(
            sync_record_path(self.store, "baselines.json"),
            {"schema_version": 1, "baselines": {}},
        )
        if set(record) != {"schema_version", "baselines"}:
            raise ValueError("Invalid Sync baseline fields.")
        baselines = {}
        for uid, value in record["baselines"].items():
            if (
                set(value) != {"source_digest", "files"}
                or len(value["source_digest"]) != 64
            ):
                raise ValueError("Invalid Sync baseline.")
            for path in value["files"]:
                relative_document_path(path)
            baselines[uid] = SyncBaseline(
                value["source_digest"],
                tuple(
                    (path, base64.b64decode(data, validate=True))
                    for path, data in value["files"].items()
                ),
            )
        return baselines

    def save(self, baselines):
        self.store._assert_profile_write_allowed()
        _write_json_atomic(
            sync_record_path(self.store, "baselines.json"),
            {
                "schema_version": 1,
                "baselines": {
                    uid: {
                        "source_digest": baseline.source_digest,
                        "files": {
                            path: base64.b64encode(data).decode("ascii")
                            for path, data in baseline.files
                        },
                    }
                    for uid, baseline in baselines.items()
                },
            },
        )
