"""Store/file implementation of immediate document Import."""

from dataclasses import replace
from pathlib import Path

from memcommit.application.capabilities.import_export.conversion import _segment
from memcommit.application.capabilities.import_export.model import (
    ConversionIssue,
    InputFile,
)
from memcommit.application.capabilities.operand_resolution import (
    resolve_existing_local_context_operand,
)
from memcommit.application.operations.profile.model._storage import (
    authority_grant_snapshot_lock,
)
from memcommit.core.context import AutoCheckpoint, Memory
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.import_export.source import read_source
from memcommit.persistence.store import MemoryStore
from memcommit.persistence.store.attached_files import save_attached_file

from .application import ImportResult
from ._shared import require_active_profile_snapshot
from .context_data import _closed_import_contexts, _context_name_mapping
from .documents.publication import import_context_records


class ImportRuntime:
    def __init__(self, store=None):
        self.store = store or MemoryStore()
        self.current = self.store.current_context_name()
        self.parent_binding = None

    def read_source(self, request):
        self.request = request
        result = read_source(Path(request.source), request.recursive)
        issues = tuple(
            ConversionIssue(
                "excluded-input",
                path,
                "Not included (nonrecursive scope, symbolic link, or nonregular file).",
                False,
            )
            for path in result.skipped
        )
        return (
            tuple(InputFile(path, data) for path, data in result.files),
            issues,
            result.single_file,
        )

    def resolve_target(self, request):
        self.request = request
        if request.format == "mem":
            if request.target:
                raise ValueError(
                    "mem-format import preserves Context names; use --as to rename its root."
                )
            return request.name or "imported"
        if request.name:
            return validate_portable_context_name(request.name)
        parent = request.target or self.current
        if parent:
            resolved = resolve_existing_local_context_operand(
                self.store, parent, current=self.current
            )
            parent_context = self.store.load_direct(resolved.name)
            if parent_context.uid != resolved.uid:
                raise ValueError("Import parent changed identity.")
            self.parent_binding = (resolved.name, parent_context.uid)
            parent = resolved.name
        label = _segment(Path(request.source).stem or "document")
        return validate_portable_context_name(parent + "/" + label if parent else label)

    def save_content(self, target, content):
        if self.request.format == "mem" and self.request.name:
            names = tuple(c.name for c in content.contexts)
            roots = [
                name
                for name in names
                if not any(
                    name.startswith(other + "/") for other in names if other != name
                )
            ]
            if len(roots) != 1:
                raise ValueError("--as requires one mem package root.")
            mapping = _context_name_mapping(
                names, source_root=roots[0], target_root=self.request.name
            )
            content = replace(
                content, contexts=_closed_import_contexts(content.contexts, mapping)
            )
        with authority_grant_snapshot_lock() as registry:
            require_active_profile_snapshot(registry, self.store)
            if self.parent_binding:
                name, uid = self.parent_binding
                if self.store.load_direct(name).uid != uid:
                    raise ValueError("Import parent changed identity.")
            # Immutable bytes are retained before any Context can point at them.
            # An interrupted command may leave unreferenced bytes, never a live
            # Context referring to content that was not successfully retained.
            for digest, data in content.attached_data.items():
                if save_attached_file(self.store.store_dir, data) != digest:
                    raise ValueError("Attached-file identity mismatch.")
            entries = tuple(
                (
                    context,
                    AutoCheckpoint(
                        command="import",
                        args={
                            "resource_kind": "document",
                            "target_context": context.name,
                        },
                        description="Imported document syntax and current file composition.",
                    ),
                )
                for context in content.contexts
            )
            created = import_context_records(self.store, entries)
            checkpoints = tuple(
                str(item["uid"])
                for context in created
                for item in self.store.list_checkpoints(context.name)
            )
        files = []
        for context in created:
            if context.document and context.document.role != "package":
                files.append((context.document.path, "DOCUMENT", context.name))
            files.extend(
                (f.path, "ATTACHED", context.name) for f in context.attached_files
            )
        return ImportResult(
            Path(self.request.source),
            tuple(c.name for c in created),
            tuple(files),
            sum(isinstance(i, Memory) for c in created for i in c.iter_items()),
            checkpoints,
        )
