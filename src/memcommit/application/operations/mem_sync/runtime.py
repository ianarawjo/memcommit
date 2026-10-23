"""Store and shared Export composition for Profile-owned document synchronization."""

import json
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import PurePosixPath

from memcommit.application.capabilities.import_export.conversion import (
    validate_output_files,
)
from memcommit.application.capabilities.import_export.export_documents import (
    plan_export_documents,
)
from memcommit.application.capabilities.import_export.export_runtime import (
    DocumentExportRuntime,
)
from memcommit.application.operations.mem_sync.documents.change_planning.compare_files import (
    compare_sync_files,
)
from memcommit.application.operations.mem_sync.documents.connections.context_selection import (
    select_sync_contexts,
)
from memcommit.application.operations.mem_sync.documents.connections.document_paths import (
    context_document_is_excluded,
    prepare_sync_document_units,
)
from memcommit.application.operations.mem_sync.documents.change_planning.prepare_inbound_changes import (
    prepare_inbound_changes,
)
from memcommit.application.operations.mem_sync.model import (
    SyncBaseline,
    ProfileDocumentChanges,
    SyncContextChange,
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
from memcommit.persistence.operations.mem_sync.checkpoint_agreement import (
    SyncCheckpointAgreementRepository,
)
from memcommit.persistence.operations.mem_sync.run_repository import SyncRunRepository
from memcommit.persistence.operations.mem_sync.settings_repository import (
    SyncSettingsRepository,
    decode_sync_connection,
)
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.context_memory.records import (
    context_record_digest,
    checkpoint_history_digest,
)
from memcommit.application.capabilities.import_export.model import (
    ProjectDocumentSnapshot,
)


class SyncRuntime:
    def __init__(self, store=None):
        self.store = store or MemoryStore()
        self.current = self.store.current_context_name()
        from memcommit.application.operations.profile.config import (
            load_profile_registry,
            profile_root_dir,
            profile_store_dir,
        )

        registry = load_profile_registry()
        self.profile = next(
            (
                p
                for p in registry.visible_profiles
                if profile_store_dir(p).resolve() == self.store.store_dir.resolve()
            ),
            None,
        )
        self.project_root = (
            profile_root_dir(self.profile)
            if self.profile
            else self.store.store_dir.parent
        )
        self.settings = SyncSettingsRepository(self.store)
        self.baselines = SyncCheckpointAgreementRepository(self.store)
        self.runs = SyncRunRepository(self.store)
        self.exporter = DocumentExportRuntime(self.store)

    def execution_boundary(self):
        # Planning and publication share the existing command-order lock.
        return self.store._command_write_lock()

    def freeze_selection(self, request):
        self.contexts = tuple(self.store.load_direct_context_graph_strict())
        self.by_name = {context.name: context for context in self.contexts}
        self.checkpoint_history_snapshot = {
            context.name: checkpoint_history_digest(
                self.store.list_checkpoints(context.name)
            )
            for context in self.contexts
        }
        self.selection = select_sync_contexts(
            request, current_name=self.current, contexts=self.contexts
        )
        return self.selection

    def prepare_plan(self, request, selection, settings):
        if request.discover_documents:
            from memcommit.persistence.import_export.source import (
                read_project_documents,
            )
            from .documents.change_planning.plan_context_changes import (
                plan_context_changes,
            )

            if request.destination is not None and external_document_locator(
                request.destination
            ) != external_document_locator(self.project_root):
                raise ValueError(
                    "Sync destination is fixed to the Profile project root; use export for another destination."
                )
            self.previous_baselines = self.baselines.load()
            self.had_errors = any(
                name in settings["errors"] for name in selection.names
            )
            snapshot = read_project_documents(self.project_root)
            from memcommit.application.capabilities.import_export.project_documents import (
                ProjectDocumentRules,
            )
            from memcommit.persistence.import_export.source import (
                require_regular_output_path,
            )

            rules = ProjectDocumentRules(snapshot.ignore_bytes)
            for record in settings["connections"]:
                if not set(record["member_names"]).intersection(selection.names):
                    continue
                for path in record["paths"]:
                    if not rules.excludes(path):
                        require_regular_output_path(self.project_root, path)
            content = self.exporter.load_named_contexts(tuple(sorted(self.by_name)))
            plan = plan_context_changes(
                content=content,
                selection=selection,
                settings=settings,
                baselines=self.previous_baselines,
                snapshot=snapshot,
            )
            self.removed_connection_uids = tuple(
                change.before["uid"]
                for change in plan.profile_changes.changes
                if change.before is not None and change.after is None
            )
            return plan
        content = self.exporter.load_named_contexts(selection.names)
        from memcommit.persistence.import_export.source import (
            read_project_document_rules,
        )
        from memcommit.application.capabilities.import_export.model import MemContent

        rules = read_project_document_rules(self.project_root)
        self.ignore_rules_snapshot = rules
        ignored_primary_names = {
            context.name
            for context in content.contexts
            if context_document_is_excluded(context, rules)
        }
        excluded = {
            name
            for owner, members, files, _directories in prepare_sync_document_units(
                MemContent(
                    tuple(
                        context
                        for context in content.contexts
                        if context.name not in ignored_primary_names
                    ),
                    content.attached_data,
                )
            )
            if rules.excludes(
                owner.name,
                directory=bool(
                    owner.corresponding_document_metadata
                    and owner.corresponding_document_metadata.role == "package"
                ),
            )
            or any(rules.excludes(file.path) for file in files)
            for name in members
        }
        excluded.update(ignored_primary_names)
        if excluded:
            selection = replace(
                selection,
                names=tuple(name for name in selection.names if name not in excluded),
            )
            self.selection = selection
            content = MemContent(
                tuple(
                    context
                    for context in content.contexts
                    if context.name not in excluded
                ),
                content.attached_data,
            )
            self.exporter.bindings = [
                (name, record)
                for name, record in self.exporter.bindings
                if name not in excluded
            ]
        self.by_name.update({context.name: context for context in content.contexts})
        units = prepare_sync_document_units(content)
        validate_output_files(tuple(file for _, _, files, _ in units for file in files))
        existing = {
            connection.context_uid: connection
            for connection in map(decode_sync_connection, settings["connections"])
        }
        self.previous_baselines = self.baselines.load()
        content, inbound_changes, conflicts = prepare_inbound_changes(
            content, units, existing, self.previous_baselines
        )
        self.by_name.update({context.name: context for context in content.contexts})
        units = prepare_sync_document_units(content)
        bases, connections, new_baselines = {}, [], {}
        selected = set(selection.names)
        default_base = external_document_locator(self.project_root)
        if (
            request.destination is not None
            and external_document_locator(request.destination) != default_base
        ):
            raise ValueError(
                "Sync destination is fixed to the Profile project root; use export for another destination."
            )
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
                digest,
                tuple((file.path, file.data) for file in files),
                tuple(self.by_name[name].to_dict() for name in members),
                tuple((file.path, file.source_ranges) for file in files),
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
                or bool(
                    connection and connection.recursive and connection.base == base
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
        self.had_errors = any(name in settings["errors"] for name in selection.names)
        exports = []
        selected_files = {}
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
                        ):
                            raise ValueError(
                                f"External Sync directory was removed: {destination / directory}"
                            )
            paths = (
                set(prior_files) | {file.path for file in files} | set(group["extra"])
            )
            external = read_output_files(destination, sorted(paths))
            selected_files.update(external)
            projected = {file.path: file.data for file in files}
            previous = SyncBaseline("0" * 64, tuple(prior_files.items()))
            removals = compare_sync_files(projected, external, previous)
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
        self.selected_file_snapshot = selected_files
        self.exporter.revalidate_selection = self.revalidate_selection
        self.validate_connection_claims(connections, existing)
        return SyncPlan(
            selection,
            tuple(exports),
            tuple(connections),
            tuple(new_baselines.items()),
            inbound_changes,
            ProfileDocumentChanges(
                ProjectDocumentSnapshot(
                    self.project_root,
                    tuple(
                        (path, data)
                        for path, data in sorted(selected_files.items())
                        if data is not None
                    ),
                    rules.ignore_bytes,
                ),
                tuple(context.to_dict() for context in self.contexts),
                tuple(
                    SyncContextChange(change.before, change.after, "EDIT", change.paths)
                    for change in inbound_changes
                ),
                tuple(
                    effect for change in inbound_changes for effect in change.effects
                ),
                (),
                tuple(sorted(set(self.by_name) - set(selection.names))),
            ),
            conflicts,
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
        if hasattr(self, "checkpoint_history_snapshot") and any(
            checkpoint_history_digest(self.store.list_checkpoints(name)) != digest
            for name, digest in self.checkpoint_history_snapshot.items()
        ):
            raise ValueError("Checkpoint history changed before Sync publication.")
        from memcommit.persistence.import_export.source import (
            read_project_document_rules,
        )

        if (
            hasattr(self, "ignore_rules_snapshot")
            and read_project_document_rules(self.project_root)
            != self.ignore_rules_snapshot
        ):
            raise ValueError(".memignore changed before Sync publication.")
        current = tuple(
            sorted(
                (context.name, context.uid)
                for context in self.store.load_direct_context_graph_strict()
            )
        )
        if current != self.selection.inventory:
            raise ValueError("Sync Context inventory changed before publication.")

    def agreement_changed(self, plan):
        # Legacy attribution is upgraded on a real agreement write, so an
        # unchanged read need not modify a write-protected Profile's metadata.
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

        def baseline_changed(uid, baseline):
            previous = self.previous_baselines.get(uid)
            if previous is None:
                return True
            if not previous.members:
                return (previous.source_digest, previous.files) != (
                    baseline.source_digest,
                    baseline.files,
                )
            if not any(spans for _path, spans in previous.source_ranges):
                # YAML/Skill acquired emission traces after schema 2. Missing
                # attribution alone must not turn an unchanged read into a write.
                return (previous.source_digest, previous.files, previous.members) != (
                    baseline.source_digest,
                    baseline.files,
                    baseline.members,
                )
            return previous != baseline

        return (
            changed_bindings
            or self.had_errors
            or bool(self.removed_connection_uids)
            or any(baseline_changed(uid, baseline) for uid, baseline in plan.baselines)
        )

    def agreement_records(self, plan, settings, policies):
        removed = set(self.removed_connection_uids)
        baselines = {
            uid: baseline
            for uid, baseline in self.previous_baselines.items()
            if uid not in removed
        }
        baselines.update(plan.baselines)
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
        return baselines, {
            **settings,
            "connections": list(connections.values()),
            "policies": policies,
            "errors": errors,
        }

    def publish_profile_changes(self, plan, request, settings):
        from .publication import publish_profile_changes

        return publish_profile_changes(self, plan, request, settings)
