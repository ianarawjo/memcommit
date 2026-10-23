"""Resolve Context operands into exact local access."""

from __future__ import annotations

import json

from memcommit.application.capabilities.context_locator import resolve_context_locator
from memcommit.application.capabilities.durable_uid_resolution import (
    DurableUidAmbiguityError,
    DurableUidCandidate,
    is_unresolved_uid_selector,
    try_resolve_durable_uid,
)
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandAmbiguityError,
    ContextOperandCandidate,
    ContextOperandNotFoundError,
    ResolvedExistingContextOperand,
    try_resolve_existing_context_operand,
)
from memcommit.application.capabilities.local_target_lookup import (
    DirectMemoryNotFoundError,
    resolve_local_direct_memory_locator,
)
from memcommit.application.context_access.access import (
    ContextAccess,
    resolve_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.models.context import Context
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.models.memory import Memory
from memcommit.persistence.store import MemoryStore


ResolvedContextAccess = ResolvedExistingContextOperand[ContextAccess]
ContextAccessOrLocalMemory = ResolvedContextAccess | tuple[Context, Memory]


def _access_uid(
    access: ContextAccess,
) -> str:
    context = access.store.load_direct(access.context_name)
    return context.uid


def freeze_profile_context_access_candidates(
    active_store: MemoryStore,
    *,
    current_name: str | None,
) -> tuple[ContextOperandCandidate[ContextAccess], ...]:
    """Freeze every local Context access identity."""

    local_names = tuple(active_store.list_context_names())
    if current_name is not None:
        selected_access = resolve_context_access(
            active_store,
            current_name,
            current_name=current_name,
        )
    elif local_names:
        selected_name = local_names[0]
        selected_access = ContextAccess(
            store=active_store,
            context_name=selected_name,
            access_name=selected_name,
        )
    else:
        return ()
    catalog = freeze_profile_readable_context_catalog(
        active_store,
        selected_access,
    )
    return tuple(
        ContextOperandCandidate(
            uid=catalog.load_direct(name).uid,
            name=name,
            value=catalog.access_for(name),
        )
        for name in catalog.list_context_names()
    )


def try_resolve_existing_context_access(
    active_store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> ResolvedContextAccess | None:
    """Resolve an exact local Context name first, then its durable UID within the frozen catalog."""

    canonical_name = resolve_context_locator(operand, current=current_name)
    try:
        access = resolve_context_access(
            active_store,
            canonical_name,
            current_name=current_name,
        )
    except FileNotFoundError:
        pass
    else:
        return ResolvedExistingContextOperand(
            selector=operand,
            uid=_access_uid(access),
            name=access.access_name,
            value=access,
        )

    frozen = (
        candidates
        if candidates is not None
        else freeze_profile_context_access_candidates(
            active_store,
            current_name=current_name,
        )
    )
    resolved = try_resolve_existing_context_operand(
        frozen,
        operand,
        current=current_name,
    )
    if resolved is None:
        return None
    # The frozen UID catalog proves only that the identity is readable enough
    # to disclose. A mutation or stronger query route must still resolve the
    # chosen access name under its exact operation permission before use.
    access = resolve_context_access(
        active_store,
        resolved.name,
        current_name=current_name,
    )
    if _access_uid(access) != resolved.uid:
        raise ContextOperandNotFoundError(
            f"Context {resolved.name!r} changed identity during operand resolution."
        )
    return ResolvedExistingContextOperand(
        selector=operand,
        uid=resolved.uid,
        name=resolved.name,
        value=access,
    )


def resolve_existing_context_access(
    active_store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> ResolvedContextAccess:
    """Require one existing accessible Context selected by name or durable UID."""

    if operand is None:
        if current_name is None:
            raise RuntimeError("No current context. Run 'mem init <name>' first.")
        operand = current_name
    resolved = try_resolve_existing_context_access(
        active_store,
        operand,
        current_name=current_name,
        candidates=candidates,
    )
    if resolved is not None:
        return resolved
    canonical_name = resolve_context_locator(operand, current=current_name)
    if is_unresolved_uid_selector(operand):
        raise ContextOperandNotFoundError(
            f"Context UID {operand!r} is unavailable in this Profile."
        )
    raise ContextOperandNotFoundError(
        f"Context {canonical_name!r} does not exist in this Profile."
    )


def try_resolve_context_access_or_local_memory(
    active_store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> ContextAccessOrLocalMemory | None:
    """Resolve a local Context or directly owned Memory in one UID frame. Exact Context names take precedence; ambiguous identities require qualification."""

    if not isinstance(operand, str) or not operand:
        raise ValueError("A Context or Memory operand must be nonempty text.")
    frozen = (
        candidates
        if candidates is not None
        else freeze_profile_context_access_candidates(
            active_store,
            current_name=current_name,
        )
    )
    canonical_name = resolve_context_locator(operand, current=current_name)
    named = tuple(candidate for candidate in frozen if candidate.name == canonical_name)
    if len(named) == 1:
        candidate = named[0]
        return ResolvedExistingContextOperand(
            selector=operand,
            uid=candidate.uid,
            name=candidate.name,
            value=candidate.value,
        )
    if len(named) > 1:
        raise ContextOperandAmbiguityError(
            f"Context name {canonical_name!r} has multiple authorized identities."
        )

    if not is_unresolved_uid_selector(operand):
        if is_memory_uid_prefix(operand):
            try:
                return resolve_local_direct_memory_locator(
                    active_store,
                    operand,
                    current=current_name,
                )
            except DirectMemoryNotFoundError:
                return None
        return None

    local_graph = active_store.load_direct_context_graph_strict()
    durable_candidates: tuple[
        DurableUidCandidate[
            ContextOperandCandidate[ContextAccess] | tuple[Context, Memory]
        ],
        ...,
    ] = tuple(
        DurableUidCandidate(
            uid=candidate.uid,
            kind="context",
            value=candidate,
        )
        for candidate in frozen
    ) + tuple(
        DurableUidCandidate(
            uid=item.uid,
            kind="memory",
            value=(context, item),
        )
        for context in local_graph
        for item in context.iter_memories()
        if isinstance(item, Memory)
    )
    try:
        identity = try_resolve_durable_uid(durable_candidates, operand)
    except DurableUidAmbiguityError as error:
        raise ContextOperandAmbiguityError(str(error)) from error
    if identity is None:
        return None
    coordinates: list[ContextOperandCandidate[ContextAccess] | tuple[Context, Memory]] = []
    keys: set[tuple[str, ...]] = set()
    for value in identity.values:
        key = (
            ("memory", value[0].name, value[1].uid)
            if isinstance(value, tuple)
            else ("context", value.name, value.uid)
        )
        if key not in keys:
            keys.add(key)
            coordinates.append(value)
    if len(coordinates) != 1:
        rendered = "\n".join(
            (
                f"  {value[0].name}:{value[1].uid} "
                + json.dumps(
                    value[1].content,
                    ensure_ascii=False,
                )
                if isinstance(value, tuple)
                else f"  Context {value.name} [{value.uid}]"
            )
            for value in coordinates
        )
        raise ContextOperandAmbiguityError(
            f"UID {operand!r} identifies multiple readable target coordinates:\n"
            f"{rendered}\nTo select one, rerun with its CONTEXT:UID value "
            "shown above. An exact Context name also selects a Context row."
        )
    selected = coordinates[0]
    if isinstance(selected, tuple):
        return selected
    return ResolvedExistingContextOperand(
        selector=operand,
        uid=selected.uid,
        name=selected.name,
        value=selected.value,
    )


__all__ = [
    "ContextAccessOrLocalMemory",
    "ResolvedContextAccess",
    "freeze_profile_context_access_candidates",
    "resolve_existing_context_access",
    "try_resolve_context_access_or_local_memory",
    "try_resolve_existing_context_access",
]
