"""MemoryStore composition for the read-only Trace application."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.application.capabilities.authority.study_operation_policy import (
    require_trace_access,
)
from memcommit.application.capabilities.memory_report_targeting import (
    ReadableMemoryTargetNotFoundError,
    ResolvedMemoryReportTarget,
    freeze_memory_report_readable_catalog,
    parse_memory_report_locator,
    resolve_local_memory_report_target,
    resolve_readable_memory_target,
)
from memcommit.application.capabilities.history.query.context_history_slicing import (
    build_context_history_slice,
)
from memcommit.application.operations.trace.granted_view import (
    GrantedMemoryTraceReport,
    build_granted_memory_trace,
)
from memcommit.application.capabilities.history.query.memory_history_slicing import (
    collect_memory_history_candidates,
    reconstruct_memory_history,
)
from memcommit.application.operations.trace.reference_lineage import (
    build_reference_trace,
)
from memcommit.application.operations.trace.application import (
    FrozenTraceSubject,
    TraceContextTarget,
    TraceError,
    TraceMemoryTarget,
    TraceReport,
    TraceRequest,
    TraceResult,
    TraceTargetCandidate,
    TraceTargetCatalog,
    TraceTargetCatalogRequest,
    list_trace_targets,
    run_trace,
)
from memcommit.core.context import Context
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True, slots=True)
class _OwnedContextBinding:
    store: MemoryStore
    context: Context


@dataclass(frozen=True, slots=True)
class _OwnedMemoryBinding:
    store: MemoryStore
    context: Context
    target: ResolvedMemoryReportTarget


@dataclass(frozen=True, slots=True)
class _GrantedMemoryBinding:
    access: ContextAccess
    report: GrantedMemoryTraceReport


class MemoryStoreTraceSource:
    """Resolve Trace subjects while keeping Store details outside application.py."""

    def __init__(self, store: MemoryStore) -> None:
        self._store = store

    def _owned_context(
        self,
        context_locator: str | None,
        *,
        current_context_name: str | None,
    ) -> tuple[ContextAccess, Context]:
        access = resolve_context_access(
            self._store,
            context_locator,
            current_name=current_context_name,
            required_permission="READ",
        )
        # READ exposes current content. Retained owner checkpoints remain a
        # separate authority boundary and must be checked before opening them.
        require_trace_access(
            access.display_name,
            granted=access.is_granted,
            store_root=self._store.store_dir,
        )
        return access, access.store.load_direct(access.context_name)

    def target_catalog(
        self,
        request: TraceTargetCatalogRequest,
    ) -> TraceTargetCatalog:
        access, root = self._owned_context(
            request.context_locator,
            current_context_name=request.current_context_name,
        )
        names = tuple(
            name
            for name in self._store.list_context_names()
            if name == access.context_name
            or (
                request.include_descendants
                and name.startswith(access.context_name + "/")
            )
        )
        if access.context_name not in names:
            raise TraceError("Trace target catalog omitted its selected root.")
        contexts = tuple(
            root if name == access.context_name else self._store.load_direct(name)
            for name in names
        )
        candidates = tuple(
            TraceTargetCandidate(
                context_name=context.name,
                uid=candidate.uid,
                content=candidate.content,
                position=candidate.position,
                status=candidate.status,
                change_count=candidate.change_count,
            )
            for context in contexts
            for candidate in collect_memory_history_candidates(self._store, context)
        )
        return TraceTargetCatalog(
            root_context_name=access.display_name,
            context_names=names,
            candidates=candidates,
        )

    def _granted_subject(
        self,
        access: ContextAccess,
        selector: str,
    ) -> FrozenTraceSubject:
        report = build_granted_memory_trace(access, selector)
        return FrozenTraceSubject(
            kind="GRANTED_MEMORY",
            context_uid=report.context_uid,
            context_name=report.context_name,
            selected_uid=report.selected_uid,
            token=_GrantedMemoryBinding(access=access, report=report),
        )

    def _memory_subject(
        self,
        target: TraceMemoryTarget,
        *,
        current_context_name: str | None,
    ) -> FrozenTraceSubject:
        owner_locator, selector = parse_memory_report_locator(
            target.selector,
            explicit_context=target.context_locator,
        )
        if owner_locator is not None:
            access = resolve_context_access(
                self._store,
                owner_locator,
                current_name=current_context_name,
                required_permission="READ",
            )
            if access.is_granted:
                return self._granted_subject(access, selector)
            resolved = resolve_local_memory_report_target(
                self._store,
                selector,
                current=current_context_name,
                context_locator=access.context_name,
            )
        else:
            catalog = freeze_memory_report_readable_catalog(
                self._store,
                current=current_context_name,
            )
            try:
                readable = (
                    resolve_readable_memory_target(catalog, selector)
                    if catalog is not None
                    else None
                )
            except ReadableMemoryTargetNotFoundError:
                readable = None
            if readable is not None:
                if readable.access.is_granted:
                    return self._granted_subject(readable.access, readable.uid)
                resolved = resolve_local_memory_report_target(
                    self._store,
                    readable.uid,
                    current=current_context_name,
                    context_locator=readable.context_name,
                )
            else:
                resolved = resolve_local_memory_report_target(
                    self._store,
                    selector,
                    current=current_context_name,
                    context_locator=None,
                )

        context = self._store.load_direct(resolved.context_name)
        return FrozenTraceSubject(
            kind=(
                "MEMORY_REFERENCE"
                if resolved.kind == "MEMORY_REFERENCE"
                else "MEMORY"
            ),
            context_uid=context.uid,
            context_name=context.name,
            selected_uid=resolved.uid,
            token=_OwnedMemoryBinding(
                store=self._store,
                context=context,
                target=resolved,
            ),
        )

    def freeze(self, request: TraceRequest) -> FrozenTraceSubject:
        if isinstance(request.target, TraceContextTarget):
            access, context = self._owned_context(
                request.target.context_locator,
                current_context_name=request.current_context_name,
            )
            return FrozenTraceSubject(
                kind="CONTEXT",
                context_uid=context.uid,
                context_name=access.display_name,
                selected_uid=None,
                token=_OwnedContextBinding(store=self._store, context=context),
            )
        if isinstance(request.target, TraceMemoryTarget):
            return self._memory_subject(
                request.target,
                current_context_name=request.current_context_name,
            )
        raise TraceError("Trace runtime received an unsupported target.")

    def reconstruct(self, subject: FrozenTraceSubject) -> TraceReport:
        token = subject.token
        if isinstance(token, _OwnedContextBinding):
            return build_context_history_slice(token.store, token.context.name)
        if isinstance(token, _OwnedMemoryBinding):
            if subject.kind == "MEMORY_REFERENCE":
                return build_reference_trace(
                    token.store,
                    token.context,
                    token.target.uid,
                )
            return reconstruct_memory_history(
                token.store,
                token.context,
                token.target.uid,
            )
        if isinstance(token, _GrantedMemoryBinding):
            return token.report
        raise TraceError("Frozen Trace subject has an invalid runtime binding.")


def load_trace_target_catalog(
    request: TraceTargetCatalogRequest,
    *,
    store: MemoryStore,
) -> TraceTargetCatalog:
    """List one Trace picker catalog through the application boundary."""

    return list_trace_targets(request, source=MemoryStoreTraceSource(store))


def execute_trace(
    request: TraceRequest,
    *,
    store: MemoryStore,
) -> TraceResult:
    """Execute one Store-backed Trace without CLI or TUI effects."""

    return run_trace(request, source=MemoryStoreTraceSource(store))


__all__ = [
    "MemoryStoreTraceSource",
    "execute_trace",
    "load_trace_target_catalog",
]
