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
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.import_export.source import read_source
from memcommit.persistence.store import MemoryStore

from ._shared import require_active_profile_snapshot
from .context_data import _closed_import_contexts, _context_name_mapping
from .documents.publication import publish_document_import


class ImportRuntime:
    def __init__(self, store=None):
        self.store = store or MemoryStore()
        self.current = self.store.current_context_name()
        self.parent_binding = None
        from memcommit.application.operations.profile.config import load_profile_registry, profile_store_dir, profile_root_dir
        registry = load_profile_registry()
        self.profile = next((p for p in registry.visible_profiles if profile_store_dir(p).resolve() == self.store.store_dir.resolve()), None)
        self.project_root = profile_root_dir(self.profile) if self.profile else None

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
        source = Path(request.source).expanduser().resolve()
        self.profile_placement = bool(self.project_root and source.is_relative_to(self.project_root) and not request.name and not request.target and request.format not in {"mem", "skill"})
        prefix = source.relative_to(self.project_root).as_posix() if self.profile_placement else "."
        if result.single_file and self.profile_placement:
            files = tuple(InputFile(prefix, data) for _, data in result.files)
        else:
            files = tuple(InputFile((prefix + "/" if prefix != "." else "") + path, data) for path, data in result.files)
        return (
            files,
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
        if self.profile_placement:
            return None
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
                content, contexts=_closed_import_contexts(
                    source_contexts=content.contexts,
                    mapping=mapping,
                )
            )
        with authority_grant_snapshot_lock() as registry:
            require_active_profile_snapshot(registry=registry, destination=self.store)
            if self.parent_binding:
                name, uid = self.parent_binding
                if self.store.load_direct(name).uid != uid:
                    raise ValueError("Import parent changed identity.")
            return publish_document_import(
                destination=self.store,
                request=self.request,
                content=content,
            )
