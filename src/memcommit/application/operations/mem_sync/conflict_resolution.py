"""Apply one Profile-wide version choice to a completely frozen Sync plan."""

from dataclasses import replace

from memcommit.application.capabilities.import_export.export_documents import (
    plan_export_documents,
)
from memcommit.application.capabilities.import_export.model import MemContent
from memcommit.models.context import Context
from .documents.connections.document_paths import prepare_sync_document_units
from .documents.change_planning.prepare_inbound_changes import member_digest
from .model import SyncBaseline, SyncCancelled, SyncConflictChoiceRequired


def select_conflict_version(plan, chooser):
    if chooser is None:
        raise SyncConflictChoiceRequired(
            "Sync conflict: both mem and external files changed. Run 'mem sync' in a terminal to choose a version for all conflicts in this profile."
        )
    choice = chooser(plan.conflicts)
    if choice is None:
        raise SyncCancelled()
    if choice not in {"external", "mem"}:
        raise ValueError("Unknown Sync conflict version choice.")
    if choice == "external":
        return replace(plan, conflict_choice=choice)
    conflicted = {uid for conflict in plan.conflicts for uid in conflict.context_uids}
    before = {record["uid"]: record for record in plan.profile_changes.before_records}
    agreements = []
    replacement_files = {}
    for owner_uid, agreement in plan.baselines:
        if not any(member["uid"] in conflicted for member in agreement.members):
            agreements.append((owner_uid, agreement))
            continue
        members = tuple(
            Context.from_dict(before[member["uid"]]) for member in agreement.members
        )
        # Concurrent-version selection currently applies to text document units;
        # attached/composite edits are refused while preparing the frozen plan.
        unit = next(
            unit
            for unit in prepare_sync_document_units(MemContent(members, {}))
            if unit[0].uid == owner_uid
        )
        files = unit[2]
        replacement_files.update((file.path, file) for file in files)
        agreements.append(
            (
                owner_uid,
                SyncBaseline(
                    member_digest(members),
                    tuple((file.path, file.data) for file in files),
                    tuple(member.to_dict() for member in members),
                    tuple((file.path, file.source_ranges) for file in files),
                ),
            )
        )
    exports = tuple(
        plan_export_documents(
            export.destination,
            tuple(replacement_files.get(file.path, file) for file in export.files),
            {
                path: dict(plan.profile_changes.snapshot.files).get(path)
                for path, _digest in export.previous_hashes
            },
            removals=export.removals,
            directories=export.directories,
            removed_directories=export.removed_directories,
        )
        for export in plan.exports
    )
    return replace(
        plan, exports=exports, baselines=tuple(agreements), conflict_choice=choice
    )
