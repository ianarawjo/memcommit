"""Live status for effectively enabled Contexts, outside navigation snapshots."""

from hashlib import sha256
import json

from .settings import automatic_sync_enabled, automatic_document_exclusions
from memcommit.configuration.config import resolve_external_document_locator
from memcommit.persistence.import_export.source import (
    read_output_files,
    read_output_tree,
)
from memcommit.persistence.operations.mem_sync.settings_repository import (
    SyncSettingsRepository,
    decode_sync_connection,
)
from memcommit.persistence.operations.mem_sync.baseline_repository import (
    SyncBaselineRepository,
)
from memcommit.persistence.store.context_memory.records import context_record_digest


def context_sync_statuses(store):
    settings = SyncSettingsRepository(store).load()
    if not any(rule["enabled"] for rule in settings["policies"]):
        return {}
    contexts = store.load_direct_context_graph_strict()
    by_name = {context.name: context for context in contexts}
    inventory = {context.name: context.uid for context in contexts}
    baselines = SyncBaselineRepository(store).load()
    connections = tuple(map(decode_sync_connection, settings["connections"]))
    tree_errors = set()
    statuses = {}
    for context in contexts:
        if not automatic_sync_enabled(
            context.name, context.uid, settings["policies"], inventory
        ):
            continue
        connection = next(
            (item for item in connections if context.name in item.member_names), None
        )
        status = "SYNC PENDING" if connection is None else "SYNC"
        if context.name in settings["errors"] or any(
            context.name == root or context.name.startswith(root + "/")
            for root in tree_errors
        ):
            status = "SYNC ERROR"
        elif connection:
            baseline = baselines.get(connection.context_uid)
            try:
                if (
                    connection.context_name not in by_name
                    or by_name[connection.context_name].uid != connection.context_uid
                ):
                    status = "SYNC ERROR"
                elif baseline is None:
                    status = "SYNC PENDING"
                elif any(
                    (
                        resolve_external_document_locator(connection.base) / directory
                    ).is_symlink()
                    or not (
                        resolve_external_document_locator(connection.base) / directory
                    ).is_dir()
                    for directory in connection.directories
                ):
                    status = "SYNC ERROR"
                elif read_output_files(
                    resolve_external_document_locator(connection.base), connection.paths
                ) != dict(baseline.files):
                    status = "SYNC ERROR"
                else:
                    members = connection.member_names or (connection.context_name,)
                    digest = sha256(
                        json.dumps(
                            [context_record_digest(by_name[name]) for name in members]
                        ).encode()
                    ).hexdigest()
                    if digest != baseline.source_digest:
                        status = "SYNC PENDING"
            except (OSError, ValueError, KeyError):
                status = "SYNC ERROR"
        statuses[context.name] = status
    return statuses
