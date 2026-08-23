"""Resolve auto-typed Compare endpoints without changing Compare semantics."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.authority.access import (
    ContextAccess,
    GrantedReadStore,
    resolve_context_access,
)
from memcommit.context import Memory
from memcommit.context_locator import resolve_context_locator
from memcommit.context_targeting.loading import (
    resolve_local_direct_memory_locator,
)
from memcommit.context_targeting.resolution import parse_direct_memory_locator
from memcommit.profile_config import ProfileRegistry
from memcommit.store import MemoryStore


class CompareTargetingError(ValueError):
    """A Compare endpoint could not be frozen as one Context/Memory role."""


@dataclass(frozen=True, slots=True)
class CompareCliTargets:
    """Two authorized Context frames and their optional exact Memory focus."""

    reference_access: ContextAccess
    compared_access: ContextAccess
    reference_memory_uid: str | None
    compared_memory_uid: str | None


def _resolve_context_endpoint(
    store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
    registry: ProfileRegistry,
    role: str,
) -> ContextAccess:
    requested = operand if operand is not None else current_name
    if requested is None:
        raise CompareTargetingError(
            "No current reference Context. Run 'mem switch NAME' first."
        )
    canonical = resolve_context_locator(requested, current=current_name)
    try:
        return resolve_context_access(
            store,
            canonical,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
        )
    except FileNotFoundError as error:
        resolution = "" if canonical == requested else f" (resolved to {canonical!r})"
        raise CompareTargetingError(
            f"{role} Context {requested!r}{resolution} does not exist."
        ) from error


def _direct_context(access: ContextAccess, registry: ProfileRegistry):
    """Load only the authorized direct owner used by the shared UID grammar."""

    if access.is_granted:
        return GrantedReadStore(access, registry=registry).load_direct(
            access.display_name
        )
    return access.store.load_direct(access.context_name)


def _resolve_qualified_memory(
    access: ContextAccess,
    selector: str,
    *,
    registry: ProfileRegistry,
    role: str,
) -> str:
    context = _direct_context(access, registry)
    matches = tuple(
        item
        for item in context.iter_items()
        if isinstance(item, Memory) and item.uid.startswith(selector)
    )
    if not matches:
        raise CompareTargetingError(
            f"No directly owned {role} Memory with uid starting with "
            f"{selector!r} exists in Context {access.display_name!r}."
        )
    if len(matches) > 1:
        raise CompareTargetingError(
            f"{role} Memory prefix {selector!r} is ambiguous in Context "
            f"{access.display_name!r}: "
            + ", ".join(memory.uid[:8] for memory in matches)
            + "."
        )
    return matches[0].uid


def _resolve_auto_memory_endpoint(
    store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    registry: ProfileRegistry,
    role: str,
) -> tuple[ContextAccess, str]:
    locator = parse_direct_memory_locator(operand)
    if locator.context_locator is None:
        # Bare selectors deliberately scan ordinary local direct owners only.
        # Grant contents are not an enumerable namespace, and current Context
        # must not silently win when branch copies retain the same Memory UID.
        try:
            target = resolve_local_direct_memory_locator(
                store,
                locator.memory_selector,
                current=current_name,
            )
        except ValueError as error:
            if "was found in any local Context" not in str(error):
                raise
            raise CompareTargetingError(
                f"{error} Bare Memory operands do not enumerate Grants; use "
                "CONTEXT:UID to name a readable public owner."
            ) from error
        access = _resolve_context_endpoint(
            store,
            target.context_name,
            current_name=current_name,
            registry=registry,
            role=role,
        )
        return access, target.memory_uid

    access = _resolve_context_endpoint(
        store,
        locator.context_locator,
        current_name=current_name,
        registry=registry,
        role=f"{role} Memory owner",
    )
    memory_uid = _resolve_qualified_memory(
        access,
        locator.memory_selector,
        registry=registry,
        role=role,
    )
    return access, memory_uid


def resolve_compare_cli_targets(
    store: MemoryStore,
    *,
    reference_operand: str | None,
    compared_operand: str,
    reference_is_auto_memory: bool,
    compared_is_auto_memory: bool,
    reference_memory_selector: str | None,
    compared_memory_selector: str | None,
    current_name: str | None,
    registry: ProfileRegistry,
) -> CompareCliTargets:
    """Freeze auto-typed operands into Compare's existing focused-frame inputs."""

    if reference_is_auto_memory:
        if reference_operand is None:  # pragma: no cover - caller invariant
            raise CompareTargetingError("REFERENCE Memory operand is missing.")
        reference_access, reference_memory_uid = _resolve_auto_memory_endpoint(
            store,
            reference_operand,
            current_name=current_name,
            registry=registry,
            role="Reference",
        )
    else:
        reference_access = _resolve_context_endpoint(
            store,
            reference_operand,
            current_name=current_name,
            registry=registry,
            role="Reference",
        )
        reference_memory_uid = reference_memory_selector

    if compared_is_auto_memory:
        compared_access, compared_memory_uid = _resolve_auto_memory_endpoint(
            store,
            compared_operand,
            current_name=current_name,
            registry=registry,
            role="Compared",
        )
    else:
        compared_access = _resolve_context_endpoint(
            store,
            compared_operand,
            current_name=current_name,
            registry=registry,
            role="Compared",
        )
        compared_memory_uid = compared_memory_selector

    return CompareCliTargets(
        reference_access=reference_access,
        compared_access=compared_access,
        reference_memory_uid=reference_memory_uid,
        compared_memory_uid=compared_memory_uid,
    )


__all__ = [
    "CompareCliTargets",
    "CompareTargetingError",
    "resolve_compare_cli_targets",
]
