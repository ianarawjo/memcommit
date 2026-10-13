"""Store and shared Export composition for Profile-owned document synchronization."""

from dataclasses import asdict
from hashlib import sha256
from pathlib import PurePosixPath
import json

from memcommit.application.capabilities.import_export.export_documents import (
    plan_export_documents,
)
from memcommit.application.capabilities.import_export.export_runtime import (
    DocumentExportRuntime,
)
from memcommit.application.capabilities.import_export.conversion import (
    validate_output_files,
)
from memcommit.application.operations.mem_sync.documents.context_selection import (
    select_sync_contexts,
)
from memcommit.application.operations.mem_sync.documents.document_paths import (
    prepare_sync_document_units,
)
from memcommit.application.operations.mem_sync.documents.compare_files import (
    compare_sync_files,
)
from memcommit.application.operations.mem_sync.model import (
    SyncBaseline,
    SyncConnection,
    SyncPlan,
)
from memcommit.configuration.config import (
    external_document_locator,
    resolve_external_document_locator,
)
from memcommit.persistence.import_export.source import (
    read_output_files,
)
from memcommit.persistence.operations.mem_sync.settings_repository import (
    SyncSettingsRepository,
    decode_sync_connection,
)
from memcommit.persistence.operations.mem_sync.baseline_repository import (
    SyncBaselineRepository,
)
from memcommit.persistence.operations.mem_sync.run_repository import SyncRunRepository
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory.records import context_record_digest


class SyncRuntime:
    def __init__(self, store=None):
        self.store = store or MemoryStore()
        self.current = self.store.current_context_name()
        from memcommit.application.operations.profile.config import load_profile_registry, profile_store_dir, profile_root_dir
        registry = load_profile_registry()
        self.profile = next((p for p in registry.visible_profiles if profile_store_dir(p).resolve() == self.store.store_dir.resolve()), None)
        self.project_root = profile_root_dir(self.profile) if self.profile else self.store.store_dir.parent
        self.settings = SyncSettingsRepository(self.store)
        self.baselines = SyncBaselineRepository(self.store)
        self.runs = SyncRunRepository(self.store)
        self.exporter = DocumentExportRuntime(self.store)

    def execution_boundary(self):
        # Reuse the existing command-order lock for baseline/settings CAS;
        # automatic execution enters only after the primary holder released it.
        return self.store._command_write_lock()

    def freeze_selection(self, request):
        self.contexts = tuple(self.store.load_direct_context_graph_strict())
        self.by_name = {context.name: context for context in self.contexts}
        self.selection = select_sync_contexts(
            request, current_name=self.current, contexts=self.contexts
        )
        return self.selection

    def prepare_plan(self, request, selection, settings):
        self.store._assert_profile_write_allowed()
        content = self.exporter.load_named_contexts(selection.names)
        self.by_name.update({context.name: context for context in content.contexts})
        units = prepare_sync_document_units(content)
        validate_output_files(tuple(file for _, _, files, _ in units for file in files))
        existing = {
            connection.context_uid: connection
            for connection in map(decode_sync_connection, settings["connections"])
        }
        self.previous_baselines = self.baselines.load()
        bases, connections, new_baselines = {}, [], {}
        selected = set(selection.names)
        default_base = external_document_locator(self.project_root)
        if request.destination is not None and external_document_locator(request.destination) != default_base:
            raise ValueError("Sync destination is fixed to the Profile project root; use export for another destination.")
        retired_connections = set()
        claim_roots = (
            (selection.root_name,)
            if selection.scope == "recursive"
            else tuple(
                name
                for name in selection.names
                if not any(name.startswith(parent + "/") for parent in selection.names)
            )
            if selection.scope == "all"
            else ()
        )
        for context, members, files, directories in units:
            connection = existing.get(context.uid)
            if (
                connection
                and connection.context_name != context.name
                and request.destination is None
            ):
                raise ValueError(
                    f"Sync Context was renamed; explicitly reconnect it: {connection.context_name}"
                )
            stale = tuple(
                old
                for old in existing.values()
                if old.context_name == context.name and old.context_uid != context.uid
            )
            if stale and request.destination is None:
                raise ValueError(f"Sync Context identity changed: {context.name}")
            retired_connections.update(old.context_uid for old in stale)
            base = (
                connection.base
                if connection and request.destination is None
                else default_base
            )
            destination = resolve_external_document_locator(base)
            if base != default_base:
                raise ValueError("Sync connection belongs to a different project root.")
            # Project documents never own any Profile's internal Store state.
            if destination == self.store.store_dir or destination.is_relative_to(
                self.store.store_dir
            ):
                raise ValueError("Sync output cannot be inside the Profile Store.")
            digest = sha256(
                json.dumps(
                    [context_record_digest(self.by_name[name]) for name in members]
                ).encode()
            ).hexdigest()
            new_baselines[context.uid] = SyncBaseline(
                digest, tuple((file.path, file.data) for file in files)
            )
            implied_dirs = {
                str(parent)
                for file in files
                for parent in PurePosixPath(file.path).parents
                if str(parent) != "."
            }
            directories = tuple(sorted(set(directories) | implied_dirs))
            new_connection = SyncConnection(
                context.uid,
                context.name,
                base,
                tuple(file.path for file in files),
                directories,
                members,
                context.name in claim_roots
                or bool(connection and connection.recursive and connection.base == base)
                or bool(
                    request.automatic
                    and any(
                        rule["enabled"]
                        and (
                            rule["scope"] == "recursive"
                            and rule["name"] == context.name
                            and rule["uid"] == context.uid
                            or rule["scope"] == "all"
                            and not any(
                                context.name.startswith(name + "/")
                                for name in self.by_name
                            )
                        )
                        for rule in settings["policies"]
                    )
                ),
            )
            connections.append(new_connection)
            group = bases.setdefault(
                destination,
                {"files": [], "directories": set(), "uids": set(), "extra": {}},
            )
            group["files"].extend(files)
            group["directories"].update(directories)
            group["uids"].add(context.uid)
        # Missing former descendants are a checked removal, never an empty
        # source fallback. A same-named replacement is a stale binding instead.
        removed_connections = []
        for uid, connection in existing.items():
            if uid in retired_connections:
                continue
            if uid in new_baselines:
                continue
            in_scope = selection.scope == "all" or (
                selection.scope == "recursive"
                and (
                    connection.context_name == selection.root_name
                    or connection.context_name.startswith(selection.root_name + "/")
                )
            )
            if request.automatic:
                from .automatic.settings import automatic_sync_enabled

                in_scope = automatic_sync_enabled(
                    connection.context_name,
                    uid,
                    settings["policies"],
                    dict(selection.inventory),
                )
            if in_scope and connection.context_name not in self.by_name:
                if any(context.uid == uid for context in self.contexts):
                    raise ValueError(
                        f"Sync Context was renamed: {connection.context_name}"
                    )
                removed_connections.append(uid)
                destination = resolve_external_document_locator(connection.base)
                group = bases.setdefault(
                    destination,
                    {"files": [], "directories": set(), "uids": set(), "extra": {}},
                )
                group["uids"].add(uid)
            elif (
                in_scope
                and connection.context_name in self.by_name
                and self.by_name[connection.context_name].uid != uid
            ):
                raise ValueError(
                    f"Sync Context identity changed: {connection.context_name}"
                )
        self.removed_connection_uids = tuple(
            set(removed_connections) | retired_connections
        )
        # A recursive selection owns explicit baselined documents only. Walking
        # the project to claim extra files could delete another tool's content.
        pending = self.runs.pending()
        self.had_errors = any(name in settings["errors"] for name in selection.names)
        if pending:
            if not set(pending.get("source_digests", {})).issubset(
                set(new_baselines) | set(self.removed_connection_uids)
            ):
                raise ValueError(
                    "Retry interrupted Sync with its original Context scope."
                )
            if (
                request.destination is not None
                and str(resolve_external_document_locator(default_base))
                not in pending["files"]
            ):
                raise ValueError(
                    "Retry pending Sync at its pinned destination before reconnecting."
                )
            old_inventory = dict(pending["source_inventory"])
            if any(
                self.by_name[name].uid != uid
                for name, uid in old_inventory.items()
                if name in self.by_name
            ):
                raise ValueError(
                    "Interrupted Sync Context identities changed; resolve the pending run first."
                )
            if request.automatic and pending.get("source_digests") != {
                uid: baseline.source_digest for uid, baseline in new_baselines.items()
            }:
                raise ValueError(
                    "Interrupted Sync source content changed; retry 'mem sync' explicitly."
                )
        exports = []
        for destination, group in bases.items():
            files = tuple(group["files"])
            validate_output_files(files)
            prior_files = {}
            protected_paths = set()
            for uid in group["uids"]:
                baseline = self.previous_baselines.get(uid)
                old_connection = existing.get(uid)
                reconnected = request.destination is not None and (
                    old_connection is None
                    or old_connection.base != default_base
                    or old_connection.context_name not in selected
                )
                if baseline and not reconnected:
                    prior_files.update(baseline.files)
                    new_connection = next(
                        (item for item in connections if item.context_uid == uid), None
                    )
                    if new_connection:
                        protected_paths.update(new_connection.paths)
                    for directory in old_connection.directories:
                        if (
                            directory in group["directories"]
                            and not (destination / directory).is_dir()
                            and not pending
                        ):
                            raise ValueError(
                                f"External Sync directory was removed: {destination / directory}"
                            )
            paths = (
                set(prior_files) | {file.path for file in files} | set(group["extra"])
            )
            external = read_output_files(destination, sorted(paths))
            projected = {file.path: file.data for file in files}
            interrupted = None
            if pending:
                if request.automatic and pending.get("source_inventory") != [
                    list(pair) for pair in selection.inventory
                ]:
                    raise ValueError(
                        "Interrupted Sync source identities changed; resolve the pending run first."
                    )
                interrupted = {
                    path: tuple(hashes)
                    for path, hashes in pending.get("files", {})
                    .get(str(destination), {})
                    .items()
                }
            previous = SyncBaseline("0" * 64, tuple(prior_files.items()))
            removals = compare_sync_files(projected, external, previous, interrupted)
            required_directories = set(group["directories"])
            for file in files:
                required_directories.update(
                    str(parent)
                    for parent in PurePosixPath(file.path).parents
                    if str(parent) != "."
                )
            old_directories = group.get("old_directories", set())
            for uid in group["uids"]:
                if uid in existing:
                    old_directories.update(existing[uid].directories)
            exports.append(
                plan_export_documents(
                    destination,
                    files,
                    external,
                    removals=removals,
                    directories=tuple(sorted(required_directories)),
                    removed_directories=tuple(
                        sorted(old_directories - required_directories)
                    ),
                )
            )
        self.exporter.revalidate_selection = self.revalidate_selection
        self.validate_connection_claims(connections, existing)
        return SyncPlan(
            selection, tuple(exports), tuple(connections), tuple(new_baselines.items())
        )

    def validate_connection_claims(self, connections, existing):
        replaced = {connection.context_uid for connection in connections} | set(
            self.removed_connection_uids
        )
        claims = {}
        for connection in (
            *connections,
            *(old for uid, old in existing.items() if uid not in replaced),
        ):
            base = resolve_external_document_locator(connection.base)
            for relative in connection.paths:
                path = str(base / relative).casefold()
                if path in claims and claims[path] != connection.context_uid:
                    raise ValueError(
                        f"Sync document path is already connected to another Context: {base / relative}"
                    )
                if any(
                    path.startswith(other + "/") or other.startswith(path + "/")
                    for other in claims
                ):
                    raise ValueError(
                        f"Sync document path is also a directory: {base / relative}"
                    )
                claims[path] = connection.context_uid

    def revalidate_selection(self):
        current = tuple(
            sorted(
                (context.name, context.uid)
                for context in self.store.load_direct_context_graph_strict()
            )
        )
        if current != self.selection.inventory:
            raise ValueError("Sync Context inventory changed before publication.")

    def agreement_changed(self, plan):
        old = {
            connection.context_uid: connection
            for connection in map(
                decode_sync_connection, self.settings.load()["connections"]
            )
        }
        changed_bindings = any(
            connection != old.get(connection.context_uid)
            for connection in plan.connections
        )
        return (
            changed_bindings
            or self.had_errors
            or bool(self.runs.pending())
            or bool(self.removed_connection_uids)
            or any(
                self.previous_baselines.get(uid) != baseline
                for uid, baseline in plan.baselines
            )
        )

    def publisher_for(self, export):
        return self.exporter

    def begin_publication(self, plan, run_uid):
        files = {}
        for export in plan.exports:
            after = {file.path: sha256(file.data).hexdigest() for file in export.files}
            files[str(export.destination)] = {
                path: [before, after.get(path)]
                for path, before in export.previous_hashes
            }
        self.runs.start(
            {
                "uid": run_uid,
                "source_inventory": plan.selection.inventory,
                "files": files,
                "source_digests": {
                    uid: baseline.source_digest for uid, baseline in plan.baselines
                },
            }
        )

    def finish_publication(self, plan, settings, policies, result, causing_command):
        if result.run_uid is None:
            return
        removed = set(self.removed_connection_uids)
        baselines = {
            uid: baseline
            for uid, baseline in self.previous_baselines.items()
            if uid not in removed
        }
        baselines.update(plan.baselines)
        self.baselines.save(baselines)
        connections = {
            record["context_uid"]: record
            for record in settings["connections"]
            if record["context_uid"] not in removed
        }
        connections.update(
            {
                connection.context_uid: asdict(connection)
                for connection in plan.connections
            }
        )
        errors = {
            name: error
            for name, error in settings["errors"].items()
            if name not in plan.selection.names
        }
        self.settings.save(
            {
                **settings,
                "connections": list(connections.values()),
                "policies": policies,
                "errors": errors,
            },
            expected_revision=settings["revision"],
        )
        self.runs.complete(result, causing_command)

    def record_failure(self, selection, settings, error):
        current = self.settings.load()
        self.settings.save(
            {
                **current,
                "errors": {
                    **current["errors"],
                    **dict.fromkeys(selection.names, error),
                },
            },
            expected_revision=current["revision"],
        )
