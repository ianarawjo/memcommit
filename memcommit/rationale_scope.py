"""Resolve a Memory and its readable descendant frame for ``mem rationale``."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.commands.granted_context import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.context import Context, Memory
from memcommit.provenance import (
    MemoryState,
    TraceCandidate,
    TraceReport,
    build_trace,
    collect_trace_candidates,
)
from memcommit.rationale import RationaleError
from memcommit.store import MemoryStore


@dataclass(frozen=True)
class RationaleScope:
    """One frozen readable Context subtree and its access boundary."""

    access: ContextAccess
    read_store: MemoryStore | GrantedReadStore
    root_name: str
    contexts: tuple[Context, ...]

    @property
    def granted(self) -> bool:
        return self.access.is_granted


@dataclass(frozen=True)
class RationaleTarget:
    """One selected Memory plus the direct Context that owns it."""

    selector: str
    owner: Context
    candidate: TraceCandidate


def load_rationale_scope(
    active_store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
) -> RationaleScope:
    """Load the selected Context and every readable lexical descendant."""

    access = resolve_context_access(
        active_store,
        operand,
        current_name=current_name,
        required_permission="READ",
    )
    read_store: MemoryStore | GrantedReadStore = (
        GrantedReadStore(access) if access.is_granted else access.store
    )
    root_name = access.display_name
    names = [
        name
        for name in read_store.list_context_names()
        if name == root_name or name.startswith(root_name + "/")
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
    )


def rationale_candidates(
    scope: RationaleScope,
) -> tuple[tuple[TraceCandidate, ...], dict[str, tuple[Context, TraceCandidate]]]:
    """Collect one unambiguous selector catalog across the readable subtree."""

    ordered: list[TraceCandidate] = []
    owners: dict[str, tuple[Context, TraceCandidate]] = {}
    for context in scope.contexts:
        if scope.granted:
            candidates = tuple(
                TraceCandidate(
                    uid=memory.uid,
                    content=memory.content,
                    position=position,
                    status="CURRENT",
                )
                for position, memory in enumerate(
                    item
                    for item in context.iter_items()
                    if isinstance(item, Memory)
                )
            )
        else:
            candidates = collect_trace_candidates(scope.read_store, context)
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
    return RationaleTarget(selector=uid, owner=owner, candidate=candidate)


def rationale_trace(scope: RationaleScope, target: RationaleTarget) -> TraceReport:
    """Build local provenance or a history-free granted READ projection."""

    if not scope.granted:
        assert isinstance(scope.read_store, MemoryStore)
        return build_trace(scope.read_store, target.owner, target.selector)
    state = MemoryState(
        uid=target.candidate.uid,
        content=target.candidate.content,
        position=target.candidate.position,
    )
    # A granted Rationale needs the selected content identity but must not
    # inspect authority checkpoints, analysis attachments, or command logs.
    return TraceReport(
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
