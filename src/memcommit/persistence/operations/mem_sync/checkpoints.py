"""Read Sync comparison states from successful commands' Context checkpoints."""

from memcommit.application.capabilities.history.reconstruction.checkpoint_state_projection import (
    flatten_checkpoint_entries,
)
from memcommit.application.operations.import_export_sync.common.model import MemContent
from memcommit.application.operations.import_export_sync.mem_sync.documents.connections.document_paths import (
    prepare_sync_document_units,
)
from memcommit.application.operations.import_export_sync.mem_sync.documents.change_planning.prepare_inbound_changes import (
    member_digest,
)
from memcommit.application.operations.import_export_sync.mem_sync.model import (
    SyncBaseline,
)
from memcommit.models.context import Context
from memcommit.persistence.store.attached_files import read_attached_file
from .run_repository import SyncRunRepository


def load_sync_checkpoint_records(store, contexts=None):
    if contexts is None:
        contexts = store.load_all_contexts()
    histories = [store.list_checkpoints(context.name) for context in contexts]
    histories.extend(
        entries for _context, entries in store.list_command_context_archives()
    )
    records = {}
    for history in histories:
        entries, _warnings = flatten_checkpoint_entries(history)
        records.update((entry["uid"], entry) for entry in entries)
    return records


def load_last_sync_baselines(store, contexts=None):
    receipts = sorted(
        SyncRunRepository(store).history(),
        key=lambda record: (record["created_at"], record["uid"]),
    )
    if not receipts:
        return {}
    records = load_sync_checkpoint_records(store, contexts)
    deleted_checkpoint_uids = {
        uid
        for event in store.list_context_lifecycle_events()
        for uid in event.deleted_checkpoint_uids
    }
    latest = {}
    for receipt in receipts:
        # Undo changes mem only; it must not move the common workspace baseline.
        if receipt.get("profile", {}).get("restoration"):
            continue
        excluded_names = set(receipt["profile"].get("excluded_names", ()))
        latest = {
            uid: snapshot
            for uid, snapshot in latest.items()
            if snapshot["name"] in excluded_names
        }
        for _name, checkpoint_uid in receipt["checkpoint_uids"]:
            if checkpoint_uid in deleted_checkpoint_uids:
                continue
            record = records.get(checkpoint_uid)
            if record is None:
                raise ValueError(
                    "The last successful Sync checkpoint is unavailable; files were preserved."
                )
            uid = record["snapshot"]["uid"]
            if record["command_details"]["sync_operation"]["action"] == "REMOVE":
                latest.pop(uid, None)
            else:
                latest[uid] = record["snapshot"]
    baselines = {}
    for uid, snapshot in latest.items():
        context = Context.from_dict(snapshot)
        attached = {
            file.sha256: read_attached_file(store.store_dir, file.sha256)
            for file in context.asset_metadata
        }
        _owner, _names, files, _directories = prepare_sync_document_units(
            MemContent((context,), attached)
        )[0]
        baselines[uid] = SyncBaseline(
            member_digest((context,)),
            tuple((file.path, file.data) for file in files),
            (snapshot,),
            tuple((file.path, file.source_ranges) for file in files),
        )
    return baselines
