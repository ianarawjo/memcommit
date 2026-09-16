"""Resolve auto-typed Compare endpoints without changing Compare semantics."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.context_access.access import (
    ContextAccess,
    GrantedReadStore,
)
from memcommit.application.context_access.operand_resolution import (
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
    try_resolve_context_access_or_local_memory,
)
from memcommit.core.context import Memory
from memcommit.application.capabilities.operand_resolution import (
    ContextOperandCandidate,
    ContextOperandResolutionError,
    ResolvedExistingContextOperand,
)
from memcommit.application.capabilities.local_target_lookup import (
    resolve_local_direct_memory_locator,
)
from memcommit.core.context_targeting.model import (
    DirectMemoryLocator,
    DirectMemoryTarget,
)
from memcommit.core.context_targeting.resolution import (
    parse_auto_typed_context_memory_operand,
    parse_direct_memory_locator,
)
from memcommit.application.operations.profile.config import ProfileRegistry
from memcommit.persistence.store import MemoryStore


class CompareTargetingError(ValueError):
    """A Compare endpoint could not be frozen as one Context/Memory role."""


@dataclass(frozen=True, slots=True)
class CompareCliTargets:
    """Two authorized Context frames and their optional exact Memory focus."""

    reference_access: ContextAccess
    compared_access: ContextAccess
    reference_memory_uid: str | None
    compared_memory_uid: str | None
    reference_operand_is_memory: bool = False
    compared_operand_is_memory: bool = False


def _resolve_context_endpoint(
    store: MemoryStore,
    operand: str | None,
    *,
    current_name: str | None,
    registry: ProfileRegistry,
    role: str,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...],
) -> ContextAccess:
    requested = operand if operand is not None else current_name
    if requested is None:
        raise CompareTargetingError(
            "No current reference Context. Run 'mem switch NAME' first."
        )
    try:
        return resolve_existing_context_access(
            store,
            requested,
            current_name=current_name,
            required_permission="READ",
            registry=registry,
            candidates=candidates,
        ).value
    except (FileNotFoundError, ContextOperandResolutionError) as error:
        raise CompareTargetingError(
            f"{role} Context {requested!r} does not exist or is unavailable."
        ) from error


def _direct_context(access: ContextAccess, registry: ProfileRegistry):
    """Load only the authorized direct owner used by the shared UID grammar."""

    if access.is_granted:
        return GrantedReadStore(access, registry=registry).load_direct(
            access.access_name
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
            f"{selector!r} exists in Context {access.access_name!r}."
        )
    if len(matches) > 1:
        raise CompareTargetingError(
            f"{role} Memory prefix {selector!r} is ambiguous in Context "
            f"{access.access_name!r}: "
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
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...],
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
            candidates=candidates,
        )
        return access, target.memory_uid

    access = _resolve_context_endpoint(
        store,
        locator.context_locator,
        current_name=current_name,
        registry=registry,
        role=f"{role} Memory owner",
        candidates=candidates,
    )
    memory_uid = _resolve_qualified_memory(
        access,
        locator.memory_selector,
        registry=registry,
        role=role,
    )
    return access, memory_uid


def _resolve_auto_typed_endpoint(
    store: MemoryStore,
    operand: str,
    *,
    current_name: str | None,
    registry: ProfileRegistry,
    role: str,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...],
) -> tuple[ContextAccess, str | None]:
    """Preserve an exact readable Context, then try one short local Memory."""

    parsed = parse_auto_typed_context_memory_operand(operand)
    if isinstance(parsed, DirectMemoryLocator) and parsed.context_locator is not None:
        return _resolve_auto_memory_endpoint(
            store,
            operand,
            current_name=current_name,
            registry=registry,
            role=role,
            candidates=candidates,
        )
    resolved = try_resolve_context_access_or_local_memory(
        store,
        operand,
        current_name=current_name,
        registry=registry,
        candidates=candidates,
    )
    if isinstance(resolved, ResolvedExistingContextOperand):
        return resolved.value, None
    if isinstance(resolved, DirectMemoryTarget):
        access = _resolve_context_endpoint(
            store,
            resolved.context_name,
            current_name=current_name,
            registry=registry,
            role=role,
            candidates=candidates,
        )
        return access, resolved.memory_uid
    return (
        _resolve_context_endpoint(
            store,
            operand,
            current_name=current_name,
            registry=registry,
            role=role,
            candidates=candidates,
        ),
        None,
    )


def resolve_compare_cli_targets(
    store: MemoryStore,
    *,
    reference_operand: str | None,
    compared_operand: str,
    reference_is_auto_memory: bool,
    compared_is_auto_memory: bool,
    reference_is_auto_typed: bool = False,
    compared_is_auto_typed: bool = False,
    reference_memory_selector: str | None,
    compared_memory_selector: str | None,
    current_name: str | None,
    registry: ProfileRegistry,
) -> CompareCliTargets:
    """Freeze auto-typed operands into Compare's existing focused-frame inputs."""

    candidates = freeze_profile_context_access_candidates(
        store,
        current_name=current_name,
        registry=registry,
    )
    reference_operand_is_memory = False
    compared_operand_is_memory = False
    if reference_is_auto_memory:
        if reference_operand is None:  # pragma: no cover - caller invariant
            raise CompareTargetingError("REFERENCE Memory operand is missing.")
        reference_access, reference_memory_uid = _resolve_auto_memory_endpoint(
            store,
            reference_operand,
            current_name=current_name,
            registry=registry,
            role="Reference",
            candidates=candidates,
        )
        reference_operand_is_memory = True
    elif reference_is_auto_typed and reference_operand is not None:
        reference_access, reference_memory_uid = _resolve_auto_typed_endpoint(
            store,
            reference_operand,
            current_name=current_name,
            registry=registry,
            role="Reference",
            candidates=candidates,
        )
        reference_operand_is_memory = reference_memory_uid is not None
        if reference_operand_is_memory and reference_memory_selector is not None:
            raise CompareTargetingError(
                "REFERENCE Memory was supplied both positionally and with "
                "--reference-memory."
            )
        if not reference_operand_is_memory:
            reference_memory_uid = reference_memory_selector
    else:
        reference_access = _resolve_context_endpoint(
            store,
            reference_operand,
            current_name=current_name,
            registry=registry,
            role="Reference",
            candidates=candidates,
        )
        reference_memory_uid = reference_memory_selector

    if compared_is_auto_memory:
        compared_access, compared_memory_uid = _resolve_auto_memory_endpoint(
            store,
            compared_operand,
            current_name=current_name,
            registry=registry,
            role="Compared",
            candidates=candidates,
        )
        compared_operand_is_memory = True
    elif compared_is_auto_typed:
        compared_access, compared_memory_uid = _resolve_auto_typed_endpoint(
            store,
            compared_operand,
            current_name=current_name,
            registry=registry,
            role="Compared",
            candidates=candidates,
        )
        compared_operand_is_memory = compared_memory_uid is not None
        if compared_operand_is_memory and compared_memory_selector is not None:
            raise CompareTargetingError(
                "PEER Memory was supplied both positionally and with --compared-memory."
            )
        if not compared_operand_is_memory:
            compared_memory_uid = compared_memory_selector
    else:
        compared_access = _resolve_context_endpoint(
            store,
            compared_operand,
            current_name=current_name,
            registry=registry,
            role="Compared",
            candidates=candidates,
        )
        compared_memory_uid = compared_memory_selector

    return CompareCliTargets(
        reference_access=reference_access,
        compared_access=compared_access,
        reference_memory_uid=reference_memory_uid,
        compared_memory_uid=compared_memory_uid,
        reference_operand_is_memory=reference_operand_is_memory,
        compared_operand_is_memory=compared_operand_is_memory,
    )


__all__ = [
    "CompareCliTargets",
    "CompareTargetingError",
    "resolve_compare_cli_targets",
]
