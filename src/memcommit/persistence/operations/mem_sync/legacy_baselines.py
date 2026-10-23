"""Read-only decoder for pre-checkpoint Sync agreement files."""

import base64

from memcommit.application.capabilities.import_export.model import (
    DocumentSourceRange,
    MemorySourceRange,
)
from memcommit.application.operations.mem_sync.model import SyncBaseline
from memcommit.core.document_path import relative_document_path

from .settings_repository import read_sync_record, sync_record_path


class LegacySyncBaselineReader:
    def __init__(self, store):
        self.store = store

    def load(self):
        record = read_sync_record(
            sync_record_path(self.store, "baselines.json"),
            {"schema_version": 1, "baselines": {}},
            schema_versions=(1, 2),
        )
        if set(record) != {"schema_version", "baselines"}:
            raise ValueError("Invalid Sync baseline fields.")
        baselines = {}
        for uid, value in record["baselines"].items():
            if (
                set(value)
                != (
                    {"source_digest", "files"}
                    if record["schema_version"] == 1
                    else {"source_digest", "files", "members", "source_ranges"}
                )
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
                tuple(value.get("members", ())),
                tuple(
                    (
                        path,
                        tuple(
                            DocumentSourceRange(
                                span["start"],
                                span["end"],
                                MemorySourceRange(**span["source"]),
                            )
                            for span in spans
                        ),
                    )
                    for path, spans in value.get("source_ranges", {}).items()
                ),
            )
        return baselines
