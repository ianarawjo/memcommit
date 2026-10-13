"""Freeze readable selection, then write only the generated external files."""

from pathlib import Path
from contextlib import ExitStack

from memcommit.application.capabilities.import_export.model import MemContent
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.context_access.access import (
    GrantedReadStore,
    resolve_granted_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_readable_context_catalog,
)
from memcommit.application.operations.profile.model._storage import (
    authority_grant_snapshot_lock,
)
from memcommit.application.operations.profile.config import profile_store_dir
from memcommit.core.context_targeting.model import ContextScope
from memcommit.core.context_targeting.resolution import expand_lexical_context_names
from memcommit.persistence.import_export.output import write_output_files
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.attached_files import read_attached_file


class DocumentExportRuntime:
    def __init__(self, store=None):
        self.store = store or MemoryStore()
        self.current = self.store.current_context_name()

    def load_content(self, request):
        source = request.source or self.current
        if not source:
            raise ValueError("No current Context; supply an Export source.")
        self.access = resolve_existing_context_access(
            self.store, source, current_name=self.current, required_permission="READ"
        ).value
        self.catalog = freeze_readable_context_catalog(
            self.store, self.access, include_query_routes=False
        )
        names = expand_lexical_context_names(
            ContextScope.create(
                (self.access.access_name,), include_descendants=request.recursive
            ),
            self.catalog.list_context_names(),
        )
        contexts = []
        attached = {}
        self.bindings = []
        self.accesses = {}
        for name in names:
            context = self.catalog.load_direct(name)
            access = self.catalog.access_for(name)
            self.accesses[name] = access
            self.bindings.append((name, context.to_dict()))
            contexts.append(context)
            for file in context.attached_files:
                attached[file.sha256] = read_attached_file(
                    access.store.store_dir, file.sha256
                )
        self.source_name = self.access.access_name
        return MemContent(tuple(contexts), attached)

    def load_named_contexts(self, names):
        self.bindings = []
        self.accesses = {}
        contexts = []
        attached = {}
        for name in names:
            access = resolve_existing_context_access(
                self.store, name, current_name=self.current, required_permission="READ"
            ).value
            context = (
                GrantedReadStore(access).load_direct(name)
                if access.is_granted
                else access.store.load_direct(access.context_name)
            )
            self.accesses[name] = access
            self.bindings.append((name, context.to_dict()))
            contexts.append(context)
            for file in context.attached_files:
                attached[file.sha256] = read_attached_file(
                    access.store.store_dir, file.sha256
                )
        return MemContent(tuple(contexts), attached)

    def write_files(self, destination, files):
        from .export_documents import plan_export_documents, publish_export_documents
        from memcommit.persistence.import_export.source import read_output_files

        self.last_plan = plan_export_documents(
            destination, files, read_output_files(destination, (f.path for f in files))
        )
        publish_export_documents(self.last_plan, self)
        return tuple(str(destination / file.path) for file in files)

    def publish(self, plan):
        # Reauthorize every exact source before disclosure. No reference or
        # global current-Context change can silently broaden this selection.
        with authority_grant_snapshot_lock() as registry:
            if (
                self.store.store_dir.absolute()
                != profile_store_dir(registry.active).absolute()
            ):
                raise ValueError(
                    "Active Profile changed during export; rerun the command."
                )
            owners = {}
            if hasattr(self, "revalidate_selection"):
                owners[str(self.store.store_dir.absolute())] = (self.store, set())
            current_accesses = {}
            for name, _ in self.bindings:
                access = self.accesses[name]
                if access.is_granted:
                    fresh = resolve_granted_context_access(
                        self.store,
                        name,
                        grant_uid=access.view.grant.uid,
                        required_permission="READ",
                        registry=registry,
                    )
                    if (
                        fresh.store.store_dir.absolute()
                        != access.store.store_dir.absolute()
                        or fresh.context_name != access.context_name
                    ):
                        raise ValueError(f"Export authority binding changed: {name}")
                    access = fresh
                current_accesses[name] = access
                key = str(access.store.store_dir.absolute())
                store, names = owners.setdefault(key, (access.store, set()))
                names.add(access.context_name)
            with ExitStack() as locks:
                # Revalidation sees one stable frame, including cross-Profile
                # READ-granted sources; a later source cannot change an earlier
                # checked member while the external result is being published.
                for key in sorted(owners):
                    store, names = owners[key]
                    locks.enter_context(
                        store._context_graph_lock(
                            exclusive=hasattr(self, "revalidate_selection")
                        )
                    )
                    locks.enter_context(store._context_write_locks(sorted(names)))
                for root in owners:
                    for relative in (
                        *tuple(file.path for file in plan.files),
                        *plan.removals,
                        *plan.directories,
                        *plan.removed_directories,
                    ):
                        target = plan.destination / relative
                        if target == Path(root) or target.is_relative_to(Path(root)):
                            raise ValueError(
                                "External document output cannot overwrite internal Profile state."
                            )
                for name, record in self.bindings:
                    access = current_accesses[name]
                    current = (
                        GrantedReadStore(access, registry=registry).load_direct(name)
                        if access.is_granted
                        else access.store.load_direct(access.context_name)
                    )
                    if current.to_dict() != record:
                        raise ValueError(
                            f"Export source changed during conversion: {name}"
                        )
                if hasattr(self, "revalidate_selection"):
                    self.revalidate_selection()
                write_output_files(
                    plan.destination,
                    tuple((f.path, f.data) for f in plan.files),
                    removals=plan.removals,
                    directories=plan.directories,
                    removed_directories=plan.removed_directories,
                    expected_hashes=dict(plan.previous_hashes),
                )
