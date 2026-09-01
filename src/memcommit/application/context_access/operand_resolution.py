"""Resolve Context operands into exact local or Grant-aware access."""

from __future__ import annotations

import json

from memcommit.application.capabilities.context_locator import (
    is_relative_context_locator,
    resolve_context_locator,
)
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
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.application.context_access.readable_contexts import (
    freeze_profile_readable_context_catalog,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.core.context_targeting.model import InlineTextOperand
from memcommit.core.context_targeting.model import DirectMemoryTarget
from memcommit.core.context_targeting.uid_locator import is_memory_uid_prefix
from memcommit.core.context import Memory
from memcommit.core.context_targeting.naming import validate_portable_context_name
from memcommit.persistence.store import MemoryStore


ResolvedContextAccess = ResolvedExistingContextOperand[ContextAccess]
ContextAccessOrLocalMemory = ResolvedContextAccess | DirectMemoryTarget


def _access_uid(
    access: ContextAccess,
    *,
    registry: ProfileRegistry | None = None,
) -> str:
    context = (
        GrantedReadStore(access, registry=registry).load_direct(access.access_name)
        if access.is_granted
        else access.store.load_direct(access.context_name)
    )
    return context.uid


def freeze_profile_context_access_candidates(
    active_store: MemoryStore,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
) -> tuple[ContextOperandCandidate[ContextAccess], ...]:
    """Freeze every ordinary-local and READ-granted access identity."""

    local_names = tuple(active_store.list_context_names())
    if current_name is not None:
        selected_access = resolve_context_access(
            active_store,
            current_name,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
    elif local_names:
        selected_name = local_names[0]
        selected_access = ContextAccess(
            store=active_store,
            context_name=selected_name,
            access_name=selected_name,
            permission="READ",
        )
    else:
        return ()
    catalog = freeze_profile_readable_context_catalog(
        active_store,
        selected_access,
        include_query_routes=False,
        registry=registry,
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
    required_permission: str = "READ",
    registry: ProfileRegistry | None = None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> ResolvedContextAccess | None:
    """Resolve an exact access name first, then an authorized Context UID.

    Exact name lookup retains ``resolve_context_access`` diagnostics and Grant
    semantics.  UID lookup is intentionally limited to readable Contexts; a
    concealed QUERY-only route must not disclose its authority Context UID.
    """

    canonical_name = resolve_context_locator(operand, current=current_name)
    try:
        access = resolve_context_access(
            active_store,
            canonical_name,
            current_name=current_name,
            required_permission=required_permission,
            registry=registry,
        )
    except FileNotFoundError:
        pass
    else:
        return ResolvedExistingContextOperand(
            selector=operand,
            uid=_access_uid(access, registry=registry),
            name=access.access_name,
            value=access,
        )

    frozen = (
        candidates
        if candidates is not None
        else freeze_profile_context_access_candidates(
            active_store,
            current_name=current_name,
            registry=registry,
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
        required_permission=required_permission,
        registry=registry,
    )
    if _access_uid(access, registry=registry) != resolved.uid:
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
    required_permission: str = "READ",
    registry: ProfileRegistry | None = None,
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
        required_permission=required_permission,
        registry=registry,
        candidates=candidates,
    )
    if resolved is not None:
        return resolved
    canonical_name = resolve_context_locator(operand, current=current_name)
    if is_unresolved_uid_selector(operand):
        raise ContextOperandNotFoundError(
            f"Context UID {operand!r} is unavailable in this authorized view."
        )
    raise ContextOperandNotFoundError(
        f"Context {canonical_name!r} does not exist in this authorized view."
    )


def resolve_context_access_or_inline_text(
    active_store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> ResolvedContextAccess | InlineTextOperand:
    """Resolve readable Context identity before an explicitly supported text route."""

    resolved = try_resolve_existing_context_access(
        active_store,
        operand,
        current_name=current_name,
        required_permission="READ",
        registry=registry,
        candidates=candidates,
    )
    if resolved is not None:
        return resolved
    if is_unresolved_uid_selector(operand):
        return resolve_existing_context_access(
            active_store,
            operand,
            current_name=current_name,
            registry=registry,
            candidates=candidates,
        )
    if is_relative_context_locator(operand):
        return resolve_existing_context_access(
            active_store,
            operand,
            current_name=current_name,
            registry=registry,
            candidates=candidates,
        )
    try:
        validate_portable_context_name(operand)
    except ValueError:
        return InlineTextOperand(operand)
    return resolve_existing_context_access(
        active_store,
        operand,
        current_name=current_name,
        registry=registry,
        candidates=candidates,
    )


def try_resolve_context_access_or_local_memory(
    active_store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    registry: ProfileRegistry | None = None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> ContextAccessOrLocalMemory | None:
    """Resolve a readable Context or ordinary-local Memory in one UID frame.

    Exact public Context names win. Bare UID-shaped values then compare every
    readable Context identity with every ordinary-local directly owned Memory
    identity. Grant contents are intentionally absent from the enumerable
    Memory side; callers may still support them through explicit CONTEXT:UID.
    """

    if not isinstance(operand, str) or not operand:
        raise ValueError("A Context or Memory operand must be nonempty text.")
    frozen = (
        candidates
        if candidates is not None
        else freeze_profile_context_access_candidates(
            active_store,
            current_name=current_name,
            registry=registry,
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
        DurableUidCandidate[ContextOperandCandidate[ContextAccess] | DirectMemoryTarget],
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
            value=DirectMemoryTarget(context.name, item.uid),
        )
        for context in local_graph
        for item in context.iter_items()
        if isinstance(item, Memory)
    )
    try:
        identity = try_resolve_durable_uid(durable_candidates, operand)
    except DurableUidAmbiguityError as error:
        raise ContextOperandAmbiguityError(str(error)) from error
    if identity is None:
        return None
    coordinates: list[
        ContextOperandCandidate[ContextAccess] | DirectMemoryTarget
    ] = []
    keys: set[tuple[str, ...]] = set()
    for value in identity.values:
        key = (
            ("memory", value.context_name, value.memory_uid)
            if isinstance(value, DirectMemoryTarget)
            else ("context", value.name, value.uid)
        )
        if key not in keys:
            keys.add(key)
            coordinates.append(value)
    if len(coordinates) != 1:
        memory_by_coordinate = {
            (context.name, item.uid): item
            for context in local_graph
            for item in context.iter_items()
            if isinstance(item, Memory)
        }
        rendered = "\n".join(
            (
                f"  {value.context_name}:{value.memory_uid} "
                + json.dumps(
                    memory_by_coordinate[
                        (value.context_name, value.memory_uid)
                    ].content,
                    ensure_ascii=False,
                )
                if isinstance(value, DirectMemoryTarget)
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
    if isinstance(selected, DirectMemoryTarget):
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
    "resolve_context_access_or_inline_text",
    "resolve_existing_context_access",
    "try_resolve_context_access_or_local_memory",
    "try_resolve_existing_context_access",
]
