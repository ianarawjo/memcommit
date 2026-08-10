"""Materialize an exact checked set of interactive Find results."""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Literal

import memcommit.ops as ops
from memcommit.commands.find_search_workbench import FindSearchResponse
from memcommit.commands.granted_context import (
    ContextAccess,
    authorized_context_operation,
)
from memcommit.commands.readable_context_catalog import ReadableContextCatalog
from memcommit.context import AutoCheckpoint, Context, Memory
from memcommit.derived_policy import (
    authorize_analysis_save,
    authorize_combination,
    authorize_derived_transfer,
)
from memcommit.store import MemoryStore, context_record_digest, validate_context_name


FindMaterializationMode = Literal["COPY", "REFERENCE"]


class FindMaterializationError(RuntimeError):
    """A checked Find set cannot safely become a new Context."""


@dataclass(frozen=True)
class FindMaterializationResult:
    """Durable receipt for one newly created Find result Context."""

    mode: FindMaterializationMode
    context_name: str
    context_uid: str
    checkpoint_uid: str
    item_uids: tuple[str, ...]


@dataclass(frozen=True)
class _ResolvedSource:
    public_name: str
    access: ContextAccess
    context: Context
    memory: Memory
    result_index: int
    result_kind: str
    relevance: str


def _local_output_access(store: MemoryStore, name: str) -> ContextAccess:
    return ContextAccess(
        store=store,
        context_name=name,
        display_name=name,
        attachment_name=None,
        permission="CREATE",
    )


def _source_public_name(
    catalog: ReadableContextCatalog,
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
        raise FindMaterializationError(
            f"Source Context '{result.source_context_name}' left the readable view."
        )
    containing = catalog.access_for(result.context_name)
    if not containing.is_granted or containing.view is None:
        raise FindMaterializationError(
            f"Referenced source Context '{result.source_context_name}' is not readable."
        )
    grant = containing.view.grant
    authority_name = result.source_context_name
    if authority_name == grant.resource_name:
        public_name = grant.public_name
    elif authority_name.startswith(grant.resource_name + "/"):
        public_name = grant.public_name + authority_name[len(grant.resource_name) :]
    else:
        raise FindMaterializationError(
            "The referenced Memory target is outside its readable Grant resource."
        )
    catalog.access_for(public_name)
    return public_name


def _resolve_sources(
    catalog: ReadableContextCatalog,
    response: FindSearchResponse,
    selected_result_indices: tuple[int, ...],
) -> tuple[_ResolvedSource, ...]:
    if response.mode != "CURRENT":
        raise FindMaterializationError(
            "History results are evidence views and cannot be materialized."
        )
    if not selected_result_indices:
        raise FindMaterializationError("Check at least one Find result.")
    if len(set(selected_result_indices)) != len(selected_result_indices) or any(
        isinstance(index, bool)
        or not isinstance(index, int)
        or not 0 <= index < len(response.results)
        for index in selected_result_indices
    ):
        raise FindMaterializationError("Find selected an invalid result row.")

    resolved: list[_ResolvedSource] = []
    identities: set[tuple[str, str]] = set()
    for index in selected_result_indices:
        result = response.results[index]
        if result.kind not in {"memory", "ref"}:
            raise FindMaterializationError(
                f"{result.kind} results cannot become Memory copies or references."
            )
        if not all(
            (
                result.source_context_name,
                result.source_context_uid,
                result.source_memory_uid,
            )
        ):
            raise FindMaterializationError(
                "This Find result has no frozen source-Memory identity."
            )
        public_name = _source_public_name(catalog, result)
        access = catalog.access_for(public_name)
        context = access.store.load_direct(access.context_name)
        if context.uid != result.source_context_uid:
            raise FindMaterializationError(
                f"Source Context '{public_name}' changed identity after search."
            )
        item = context.memories.get(result.source_memory_uid)
        if not isinstance(item, Memory) or item.content != result.content:
            raise FindMaterializationError(
                f"Source Memory [{result.source_memory_uid[:8]}] changed after search."
            )
        identity = (context.uid, item.uid)
        if identity in identities:
            raise FindMaterializationError(
                f"Source Memory [{item.uid[:8]}] was selected more than once."
            )
        identities.add(identity)
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
            (
                "grant",
                access.view.grant.uid,
                access.view.grant.resource_uid,
            )
            if access.is_granted and access.view is not None
            else ("local", str(access.store.store_dir), access.context_name)
        )
        for access in accesses
    }
    return len(domains) > 1


def materialize_find_results(
    store: MemoryStore,
    catalog: ReadableContextCatalog,
    response: FindSearchResponse,
    *,
    selected_result_indices: tuple[int, ...],
    mode: FindMaterializationMode,
    destination_name: str,
) -> FindMaterializationResult:
    """Create one new local Context from the exact reviewed result rows.

    COPY creates new Memory identities containing the reviewed values.
    REFERENCE delegates to the ordinary live-reference primitive and therefore
    accepts only directly owned local source Memories.  Source snapshots are
    rechecked at the require-new publication boundary; Source is never changed.
    """

    if mode not in {"COPY", "REFERENCE"}:
        raise FindMaterializationError("Choose COPY or REFERENCE.")
    validate_context_name(destination_name)
    store.assert_context_creatable(destination_name)
    sources = _resolve_sources(catalog, response, selected_result_indices)
    accesses = _unique_accesses(sources)
    output_access = _local_output_access(store, destination_name)

    if mode == "REFERENCE" and any(access.is_granted for access in accesses):
        raise FindMaterializationError(
            "REFERENCE requires locally owned source Memories; use COPY for "
            "an export-authorized Grant result."
        )
    if mode == "COPY":
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

    output = Context(uid=str(uuid.uuid4()), name=destination_name)
    output_uids: list[str] = []
    source_rows: list[dict[str, object]] = []
    for source in sources:
        if mode == "COPY":
            output_item = Memory(uid=str(uuid.uuid4()), content=source.memory.content)
            output.add(output_item)
        else:
            output_item = ops.reference_memory(
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
        command="find",
        args={
            "context_creation": {
                "version": 1,
                "context_uid": output.uid,
                "context_name": output.name,
            },
            "find_materialization": {
                "query": response.request.query,
                "mode": mode,
                "output": output.name,
                "results": source_rows,
            },
        },
        description=(
            f"Materialized {len(sources)} checked Find result(s) as {mode} "
            f"in new Context '{destination_name}'; sources unchanged"
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
    access_by_store_and_name = {
        (str(source.access.store.store_dir), source.access.context_name): source.access
        for source in sources
        if source.access.is_granted
    }

    with authorized_context_operation(tuple(checks)):
        with ExitStack() as stack:
            # Granted stores cannot participate in the active Profile's one
            # lock set, so retain their exact read snapshots until the local
            # require-new write has committed.
            for store_dir, name, uid, digest in external_sources:
                access = access_by_store_and_name[(store_dir, name)]
                stack.enter_context(
                    access.store.locked_context_snapshot(
                        name,
                        expected_uid=uid,
                        expected_digest=digest,
                    )
                )
            if local_bindings:
                created_checkpoint = store.create_context_with_sources(
                    output,
                    checkpoint,
                    source_bindings=local_bindings,
                )
            else:
                created_checkpoint = store.create_context(output, checkpoint)

    if created_checkpoint is None:
        raise FindMaterializationError(
            "Find result Context creation produced no checkpoint."
        )
    return FindMaterializationResult(
        mode=mode,
        context_name=output.name,
        context_uid=output.uid,
        checkpoint_uid=created_checkpoint.uid,
        item_uids=tuple(output_uids),
    )


__all__ = [
    "FindMaterializationError",
    "FindMaterializationMode",
    "FindMaterializationResult",
    "materialize_find_results",
]
