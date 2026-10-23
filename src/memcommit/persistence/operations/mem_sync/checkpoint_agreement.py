"""Reconstruct the last successful Sync agreement from retained checkpoints."""

from uuid import UUID

from memcommit.application.capabilities.import_export.model import MemContent
from memcommit.application.operations.mem_sync.documents.connections.document_paths import (
    prepare_sync_document_units,
)
from memcommit.application.operations.mem_sync.documents.change_planning.prepare_inbound_changes import (
    member_digest,
)
from memcommit.application.operations.mem_sync.model import SyncBaseline
from memcommit.models.context import Context
from memcommit.persistence.store.attached_files import read_attached_file
from .legacy_baselines import LegacySyncBaselineReader
from .run_repository import SyncRunRepository


class SyncCheckpointAgreementRepository:
    def __init__(self, store):
        self.store = store

    def references(self):
        references = {}
        for receipt in sorted(
            SyncRunRepository(self.store).history(),
            key=lambda record: (record["created_at"], record["uid"]),
        ):
            versions = receipt.get("profile", {}).get("agreement_versions")
            if versions is not None:
                references = versions[1]
        return references

    def load(self):
        # Historical files stay readable but are never updated. A tombstone
        # prevents a removed agreement from reappearing through that fallback.
        agreements = LegacySyncBaselineReader(self.store).load()
        references = self.references()
        if not references:
            return agreements
        checkpoints = {}
        for context in self.store.load_direct_context_graph_strict():
            for record in self.store.list_checkpoints(context.name):
                checkpoints[record["uid"]] = record
        for _context, entries in self.store.list_command_context_archives():
            for record in entries:
                checkpoints[record["uid"]] = record
        for owner_uid, members in references.items():
            UUID(owner_uid)
            if members is None:
                agreements.pop(owner_uid, None)
                continue
            contexts = []
            attached = {}
            for member in members:
                record = checkpoints.get(member["checkpoint_uid"])
                if record is None or record["snapshot"]["uid"] != member["context_uid"]:
                    raise ValueError(
                        "The last successful Sync checkpoint is unavailable; files were preserved."
                    )
                context = Context.from_dict(record["snapshot"])
                contexts.append(context)
                for file in context.asset_metadata:
                    attached[file.sha256] = read_attached_file(
                        self.store.store_dir, file.sha256
                    )
            units = prepare_sync_document_units(MemContent(tuple(contexts), attached))
            unit = next((unit for unit in units if unit[0].uid == owner_uid), None)
            if unit is None or set(unit[1]) != {context.name for context in contexts}:
                raise ValueError("Sync checkpoint document membership is incomplete.")
            _owner, names, files, _directories = unit
            by_name = {context.name: context for context in contexts}
            ordered = tuple(by_name[name] for name in names)
            agreements[owner_uid] = SyncBaseline(
                member_digest(ordered),
                tuple((file.path, file.data) for file in files),
                tuple(context.to_dict() for context in ordered),
                tuple((file.path, file.source_ranges) for file in files),
            )
        return agreements
