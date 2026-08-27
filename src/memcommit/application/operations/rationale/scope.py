"""Resolve a Memory and its readable descendant frame for ``mem rationale``."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.authority.access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.core.context_targeting.readable_catalog import (
    ReadableContextCatalog,
    freeze_readable_context_catalog,
    freeze_profile_readable_context_catalog,
)
from memcommit.context import Context, Memory
from memcommit.application.authority.derived_policy import authorize_combination
from memcommit.application.retained_history.memory_history_reconstruction.retained_record_verification import (
    MemoryState,
)
from memcommit.application.retained_history.memory_history_reconstruction.memory_history_construction import (
    MemoryHistoryCandidate,
    MemoryHistory,
    reconstruct_memory_history,
    collect_memory_history_candidates,
)
from memcommit.application.operations.rationale.model import RationaleError
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class RationaleScope:
    """One frozen readable Context subtree and its access boundary."""

    access: ContextAccess
    read_store: ReadableContextCatalog
    root_name: str
    contexts: tuple[Context, ...]
    context_accesses: tuple[tuple[str, ContextAccess], ...]

    @property
    def granted(self) -> bool:
        return self.access.is_granted

    def access_for(self, context_name: str) -> ContextAccess:
        for name, access in self.context_accesses:
            if name == context_name:
                return access
        raise RationaleError(
            f"Context {context_name!r} is outside the frozen Rationale scope."
        )

    @property
    def contributor_accesses(self) -> tuple[ContextAccess, ...]:
        return tuple(access for _name, access in self.context_accesses)


@dataclass(frozen=True)
class RationaleTarget:
    """One selected Memory plus the direct Context that owns it."""

    selector: str
    owner: Context
    candidate: MemoryHistoryCandidate
    access: ContextAccess


def load_rationale_scope(
    active_store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
    include_descendants: bool = True,
) -> RationaleScope:
    """Load one selected Context range from the readable public namespace."""

    if type(include_descendants) is not bool:
        raise TypeError("Rationale descendant scope must be a boolean.")

    access = resolve_context_access(
        active_store,
        operand,
        current_name=current_name,
        required_permission="READ",
    )
    read_store = freeze_readable_context_catalog(
        active_store,
        access,
        include_query_routes=False,
    )
    return rationale_scope_from_catalog(
        read_store,
        access.display_name,
        include_descendants=include_descendants,
    )


def freeze_rationale_profile_catalog(
    active_store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
) -> ReadableContextCatalog:
    """Freeze the full readable Profile namespace for bare target selection."""

    access = resolve_context_access(
        active_store,
        operand,
        current_name=current_name,
        required_permission="READ",
    )
    return freeze_profile_readable_context_catalog(
        active_store,
        access,
        include_query_routes=False,
    )


def rationale_scope_from_catalog(
    read_store: ReadableContextCatalog,
    root_name: str,
    *,
    include_descendants: bool,
) -> RationaleScope:
    """Project one exact/subtree scope from a command-frozen readable catalog."""

    if type(include_descendants) is not bool:
        raise TypeError("Rationale descendant scope must be a boolean.")
    access = read_store.access_for(root_name)
    names = [
        name
        for name in read_store.list_context_names()
        if name == root_name
        or (include_descendants and name.startswith(root_name + "/"))
    ]
    if root_name not in names:
        raise FileNotFoundError(f"Context {root_name!r} not found.")
    # Direct loads keep the inference corpus restricted to ordinary Memory
    # ownership. Embedded pointers and query-only routes never broaden it.
    contexts = tuple(read_store.load_direct(name) for name in names)
    return RationaleScope(
        access=access,
        read_store=read_store,
        root_name=root_name,
        contexts=contexts,
        context_accesses=tuple((name, read_store.access_for(name)) for name in names),
    )


def authorize_rationale_inference(scope: RationaleScope) -> None:
    """Authorize contextual inference only when it crosses ownership domains."""

    accesses = scope.contributor_accesses
    if not any(access.is_granted for access in accesses):
        return
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
    if len(domains) > 1:
        authorize_combination(accesses)


def rationale_candidates(
    scope: RationaleScope,
) -> tuple[tuple[MemoryHistoryCandidate, ...], dict[str, tuple[Context, MemoryHistoryCandidate]]]:
    """Collect one unambiguous selector catalog across the readable subtree."""

    ordered: list[MemoryHistoryCandidate] = []
    owners: dict[str, tuple[Context, MemoryHistoryCandidate]] = {}
    for context in scope.contexts:
        access = scope.access_for(context.name)
        if access.is_granted:
            candidates = tuple(
                MemoryHistoryCandidate(
                    uid=memory.uid,
                    content=memory.content,
                    position=position,
                    status="CURRENT",
                )
                for position, memory in enumerate(
                    item for item in context.iter_items() if isinstance(item, Memory)
                )
            )
        else:
            candidates = collect_memory_history_candidates(access.store, context)
        for candidate in candidates:
            if candidate.uid in owners:
                raise RationaleError(
                    "The rationale subtree contains a duplicate Memory UID; "
                    "select a narrower Context."
                )
            owners[candidate.uid] = (context, candidate)
            ordered.append(candidate)
    return tuple(ordered), owners


def resolve_rationale_target(
    scope: RationaleScope,
    selector: str,
) -> RationaleTarget:
    """Resolve an exact UID or unambiguous prefix within the frozen subtree."""

    _candidates, owners = rationale_candidates(scope)
    matches = [
        (uid, owner, candidate)
        for uid, (owner, candidate) in owners.items()
        if uid == selector or uid.startswith(selector)
    ]
    exact = [match for match in matches if match[0] == selector]
    if exact:
        matches = exact
    if not matches:
        raise RationaleError(
            f"Memory {selector!r} does not exist in Context subtree "
            f"{scope.root_name!r}."
        )
    if len(matches) != 1:
        raise RationaleError(f"Memory selector {selector!r} is ambiguous.")
    uid, owner, candidate = matches[0]
    return RationaleTarget(
        selector=uid,
        owner=owner,
        candidate=candidate,
        access=scope.access_for(owner.name),
    )


def rationale_memory_history(scope: RationaleScope, target: RationaleTarget) -> MemoryHistory:
    """Build local provenance or a history-free granted READ projection."""

    if not target.access.is_granted:
        return reconstruct_memory_history(target.access.store, target.owner, target.selector)
    state = MemoryState(
        uid=target.candidate.uid,
        content=target.candidate.content,
        position=target.candidate.position,
    )
    # A granted Rationale needs the selected content identity but must not
    # inspect authority checkpoints, analysis attachments, or command logs.
    return MemoryHistory(
        context_uid=target.owner.uid,
        context_name=target.owner.name,
        selected_uid=state.uid,
        component_uids=(state.uid,),
        originals=(),
        current=(state,),
        events=(),
        analyses=(),
        warnings=(
            "Authority history is outside this granted READ view; Rationale "
            "uses only the current readable Memory subtree.",
        ),
    )
