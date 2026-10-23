"""Freeze readable selection, then write only the generated external files."""

from memcommit.application.capabilities.import_export.model import MemContent
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_readable_context_catalog,
)

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
            self.store, source, current_name=self.current
        ).value
        self.catalog = freeze_readable_context_catalog(self.store, self.access)
        names = expand_lexical_context_names(
            (self.access.access_name,),
            self.catalog.list_context_names(),
            include_descendants=request.recursive,
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
            for file in context.asset_metadata:
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
                self.store, name, current_name=self.current
            ).value
            context = access.store.load_direct(access.context_name)
            self.accesses[name] = access
            self.bindings.append((name, context.to_dict()))
            contexts.append(context)
            for file in context.asset_metadata:
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
        # Hold the captured local Sources stable until all external files publish.
        names = sorted(self.accesses[name].context_name for name, _ in self.bindings)
        with self.store._context_graph_lock(
            exclusive=hasattr(self, "revalidate_selection")
        ):
            with self.store._context_write_locks(names):
                root = self.store.store_dir.absolute()
                for relative in (
                    *tuple(file.path for file in plan.files),
                    *plan.removals,
                    *plan.directories,
                    *plan.removed_directories,
                ):
                    target = plan.destination / relative
                    if target == root or target.is_relative_to(root):
                        raise ValueError(
                            "External document output cannot overwrite internal Profile state."
                        )
                for name, record in self.bindings:
                    access = self.accesses[name]
                    current = self.store.load_direct(access.context_name)
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
