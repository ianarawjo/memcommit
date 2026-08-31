"""Operation-owned MemoryStore adapter for Search materialization."""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Protocol

import memcommit.application.capabilities.ops as ops
from memcommit.application.capabilities.authority.context_access import (
    ContextAccess,
    authorized_context_operation,
)
from memcommit.core.context import AutoCheckpoint, Context, Memory
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.application.authorization.source_use import (
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.application.operations.search.application import SearchResponse
from memcommit.application.operations.search.materialization_application import (
    SearchMaterializationError,
    SearchMaterializationPort,
    SearchMaterializationRequest,
    SearchMaterializationResult,
    FrozenSearchMaterialization,
    run_search_materialization,
)
from memcommit.persistence.store import MemoryStore, context_record_digest


class SearchMaterializationCatalog(Protocol):
    """Exact readable bindings frozen by the preceding search adapter."""

    def access_for(self, name: str) -> ContextAccess: ...


@dataclass(frozen=True)
class _ResolvedSource:
    public_name: str
    access: ContextAccess
    context: Context
    memory: Memory
    result_index: int
    result_kind: str
    relevance: str


@dataclass(frozen=True)
class _StoreSearchMaterializationToken:
    output: Context
    output_uids: tuple[str, ...]
    checkpoint: AutoCheckpoint
    sources: tuple[_ResolvedSource, ...]
    checks: tuple[tuple[ContextAccess, tuple[str, ...]], ...]
    local_bindings: tuple[tuple[str, str, str], ...]
    external_sources: tuple[tuple[str, str, str, str], ...]
    external_accesses: dict[tuple[str, str], ContextAccess]


def _local_output_access(store: MemoryStore, name: str) -> ContextAccess:
    return ContextAccess(
        store=store,
        context_name=name,
        display_name=name,
        attachment_name=None,
        permission="CREATE",
    )


def _source_public_name(
    catalog: SearchMaterializationCatalog,
    result,
) -> str:
    """Map a ref's authority-side target back into the frozen public tree."""

    assert result.source_context_name is not None
    try:
        catalog.access_for(result.source_context_name)
        return result.source_context_name
    except FileNotFoundError:
        pass
    if result.kind != "ref":
        raise SearchMaterializationError(
            f"Source Context '{result.source_context_name}' left the readable view."
        )
    containing = catalog.access_for(result.context_name)
    if not containing.is_granted or containing.view is None:
        raise SearchMaterializationError(
            f"Referenced source Context '{result.source_context_name}' is not readable."
        )
    grant = containing.view.grant
    authority_name = result.source_context_name
    if authority_name == grant.resource_name:
        public_name = grant.public_name
    elif authority_name.startswith(grant.resource_name + "/"):
        public_name = grant.public_name + authority_name[len(grant.resource_name) :]
    else:
        raise SearchMaterializationError(
            "The referenced Memory target is outside its readable Grant resource."
        )
    catalog.access_for(public_name)
    return public_name


def _resolve_sources(
    catalog: SearchMaterializationCatalog,
    response: SearchResponse,
    selected_result_indices: tuple[int, ...],
) -> tuple[_ResolvedSource, ...]:
    resolved: list[_ResolvedSource] = []
    for index in selected_result_indices:
        result = response.results[index]
        assert result.source_context_name is not None
        assert result.source_context_uid is not None
        assert result.source_memory_uid is not None
        public_name = _source_public_name(catalog, result)
        access = catalog.access_for(public_name)
        context = access.store.load_direct(access.context_name)
        if context.uid != result.source_context_uid:
            raise SearchMaterializationError(
                f"Source Context '{public_name}' changed identity after search."
            )
        item = context.memories.get(result.source_memory_uid)
        if not isinstance(item, Memory) or item.content != result.content:
            raise SearchMaterializationError(
                f"Source Memory [{result.source_memory_uid[:8]}] changed after search."
            )
        resolved.append(
            _ResolvedSource(
                public_name=public_name,
                access=access,
                context=context,
                memory=item,
                result_index=index,
                result_kind=result.kind,
                relevance=result.relevance,
            )
        )
    return tuple(resolved)


def _unique_accesses(sources: tuple[_ResolvedSource, ...]) -> tuple[ContextAccess, ...]:
    values: list[ContextAccess] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        access = source.access
        key = (
            str(access.store.store_dir),
            access.context_name,
            access.view.grant.uid if access.view is not None else "",
        )
        if key not in seen:
            seen.add(key)
            values.append(access)
    return tuple(values)


def _combination_has_multiple_domains(accesses: tuple[ContextAccess, ...]) -> bool:
    domains = {
        (
            ("grant", access.view.grant.uid, access.view.grant.resource_uid)
            if access.is_granted and access.view is not None
            else ("local", str(access.store.store_dir), access.context_name)
        )
        for access in accesses
    }
    return len(domains) > 1


class MemoryStoreSearchMaterializationPort(SearchMaterializationPort):
    """Prepare and publish one Search result under Store and Grant locks."""

    def __init__(
        self,
        store: MemoryStore,
        catalog: SearchMaterializationCatalog,
    ) -> None:
        self._store = store
        self._catalog = catalog

    def prepare(
        self,
        request: SearchMaterializationRequest,
    ) -> FrozenSearchMaterialization:
        validate_portable_context_name(request.destination_name)
        self._store.assert_context_creatable(request.destination_name)
        sources = _resolve_sources(
            self._catalog,
            request.response,
            request.selected_result_indices,
        )
        accesses = _unique_accesses(sources)
        output_access = _local_output_access(self._store, request.destination_name)

        if request.mode == "REFERENCE" and any(
            access.is_granted for access in accesses
        ):
            raise SearchMaterializationError(
                "REFERENCE requires locally owned source Memories; use COPY for "
                "an export-authorized Grant result."
            )
        if request.mode == "COPY":
            authorize_combination(accesses)
            authorize_analysis_save(accesses, retention="RETAINED")
            for access in accesses:
                authorize_derived_transfer(access, output_access)

        multiple_domains = _combination_has_multiple_domains(accesses)
        checks: list[tuple[ContextAccess, tuple[str, ...]]] = []
        for access in accesses:
            if not access.is_granted:
                continue
            permissions = ["READ", "DERIVE", "EXPORT", "SAVE_ANALYSIS"]
            if multiple_domains:
                permissions.append("COMBINE")
            checks.append((access, tuple(permissions)))

        output = Context(uid=str(uuid.uuid4()), name=request.destination_name)
        output_uids: list[str] = []
        source_rows: list[dict[str, object]] = []
        for source in sources:
            if request.mode == "COPY":
                output_item = Memory(
                    uid=str(uuid.uuid4()),
                    content=source.memory.content,
                )
                output.add(output_item)
            else:
                output_item = ops.embed_memory(
                    source.memory,
                    source.context,
                    output,
                )
            output_uids.append(output_item.uid)
            source_rows.append(
                {
                    "result_index": source.result_index + 1,
                    "result_kind": source.result_kind,
                    "relevance": source.relevance,
                    "source_context": source.public_name,
                    "source_context_uid": source.context.uid,
                    "source_memory_uid": source.memory.uid,
                    "output_uid": output_item.uid,
                }
            )

        checkpoint = AutoCheckpoint(
            command="search",
            args={
                "context_creation": {
                    "version": 1,
                    "context_uid": output.uid,
                    "context_name": output.name,
                },
                "search_materialization": {
                    "query": request.response.request.query,
                    "mode": request.mode,
                    "output": output.name,
                    "results": source_rows,
                },
            },
            description=(
                f"Saved {len(sources)} checked Search result(s) as {request.mode} "
                f"in new Context '{request.destination_name}'; sources unchanged"
            ),
        )

        local_bindings = tuple(
            dict.fromkeys(
                (
                    source.access.context_name,
                    source.context.uid,
                    context_record_digest(source.context),
                )
                for source in sources
                if not source.access.is_granted
            )
        )
        external_sources = tuple(
            dict.fromkeys(
                (
                    str(source.access.store.store_dir),
                    source.access.context_name,
                    source.context.uid,
                    context_record_digest(source.context),
                )
                for source in sources
                if source.access.is_granted
            )
        )
        external_accesses = {
            (str(source.access.store.store_dir), source.access.context_name): (
                source.access
            )
            for source in sources
            if source.access.is_granted
        }
        return FrozenSearchMaterialization(
            mode=request.mode,
            destination_name=request.destination_name,
            source_count=len(sources),
            token=_StoreSearchMaterializationToken(
                output=output,
                output_uids=tuple(output_uids),
                checkpoint=checkpoint,
                sources=sources,
                checks=tuple(checks),
                local_bindings=local_bindings,
                external_sources=external_sources,
                external_accesses=external_accesses,
            ),
        )

    def materialize(
        self,
        prepared: FrozenSearchMaterialization,
    ) -> SearchMaterializationResult:
        token = prepared.token
        if not isinstance(token, _StoreSearchMaterializationToken):
            raise SearchMaterializationError(
                "The prepared Search materialization token is invalid."
            )
        if (
            token.output.name != prepared.destination_name
            or len(token.sources) != prepared.source_count
            or len(token.output_uids) != prepared.source_count
        ):
            raise SearchMaterializationError(
                "The prepared Search materialization changed before publication."
            )

        # This early check improves the ordinary collision error. The Store's
        # require-new write remains authoritative against concurrent creators.
        self._store.assert_context_creatable(prepared.destination_name)
        with authorized_context_operation(token.checks):
            with ExitStack() as stack:
                # Granted stores cannot join the active Profile's lock set.
                # Retain each authority snapshot until local publication ends.
                for store_dir, name, uid, digest in token.external_sources:
                    access = token.external_accesses[(store_dir, name)]
                    stack.enter_context(
                        access.store.locked_context_snapshot(
                            name,
                            expected_uid=uid,
                            expected_digest=digest,
                        )
                    )
                if token.local_bindings:
                    created_checkpoint = self._store.create_context_with_sources(
                        token.output,
                        token.checkpoint,
                        source_bindings=token.local_bindings,
                    )
                else:
                    created_checkpoint = self._store.create_context(
                        token.output,
                        token.checkpoint,
                    )

        if created_checkpoint is None:
            raise SearchMaterializationError(
                "Search result Context creation produced no checkpoint."
            )
        return SearchMaterializationResult(
            mode=prepared.mode,
            context_name=token.output.name,
            context_uid=token.output.uid,
            checkpoint_uid=created_checkpoint.uid,
            item_uids=token.output_uids,
        )


def execute_search_materialization(
    request: SearchMaterializationRequest,
    *,
    store: MemoryStore,
    catalog: SearchMaterializationCatalog,
) -> SearchMaterializationResult:
    """Execute the reviewed write without CLI, TUI, or provider bootstrap."""

    return run_search_materialization(
        request,
        port=MemoryStoreSearchMaterializationPort(store, catalog),
    )


__all__ = [
    "SearchMaterializationCatalog",
    "MemoryStoreSearchMaterializationPort",
    "execute_search_materialization",
]
