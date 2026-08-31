"""Resolve console operands for one directional Update invocation."""

from __future__ import annotations

from dataclasses import dataclass

from memcommit.application.capabilities.operand_resolution import ContextOperandCandidate
from memcommit.application.capabilities.authority.context_access import ContextAccess
from memcommit.application.context_access.operand_resolution import (
    ResolvedContextAccess,
    freeze_profile_context_access_candidates,
    resolve_existing_context_access,
)
from memcommit.persistence.store import MemoryStore


@dataclass(frozen=True)
class UpdateEndpointAccesses:
    """Exact source and target identities from one frozen readable catalog."""

    source: ResolvedContextAccess
    target: ResolvedContextAccess


def choose_update_endpoint_operands(
    operands: list[str] | tuple[str, ...] | None,
    *,
    source_option: str | None,
    target_option: str | None,
    allow_single_source: bool = False,
) -> tuple[str | None, str | None]:
    """Normalize positional operands and legacy directional options."""

    positional = tuple(operands or ())
    allowed_lengths = {0, 1, 2} if allow_single_source else {0, 2}
    if len(positional) not in allowed_lengths:
        raise ValueError(
            (
                "expected zero, SOURCE, or SOURCE TARGET operands."
                if allow_single_source
                else "expected either no positional Contexts or exactly SOURCE TARGET."
            )
        )
    if len(positional) == 2 and (
        source_option is not None or target_option is not None
    ):
        raise ValueError("positional Contexts cannot be combined with --from or --to.")
    if len(positional) == 2:
        return positional[0], positional[1]
    if len(positional) == 1:
        if source_option is not None:
            raise ValueError("Source was supplied both positionally and with --from.")
        return positional[0], target_option
    return source_option, target_option


def resolve_update_endpoint_accesses(
    store: MemoryStore,
    *,
    source_locator: str | None,
    target_locator: str | None,
    current: str | None,
    candidates: tuple[ContextOperandCandidate[ContextAccess], ...] | None = None,
) -> UpdateEndpointAccesses:
    """Resolve both existing endpoints by name or UID against one snapshot."""

    if source_locator is None and target_locator is None:
        raise ValueError("At least one directional endpoint locator is required.")
    if source_locator is None:
        if not current:
            raise ValueError("No current source Context. Supply '--from SOURCE'.")
        source_locator = current
    if target_locator is None:
        if not current:
            raise ValueError("No current target Context. Supply '--to TARGET'.")
        target_locator = current
    frozen = (
        candidates
        if candidates is not None
        else freeze_profile_context_access_candidates(
            store,
            current_name=current,
        )
    )
    source = resolve_existing_context_access(
        store,
        source_locator,
        current_name=current,
        required_permission="READ",
        candidates=frozen,
    )
    target = resolve_existing_context_access(
        store,
        target_locator,
        current_name=current,
        required_permission="READ",
        candidates=frozen,
    )
    # Names can expose the same durable Context through different authorized
    # public routes. Update still requires two identities, not two spellings.
    if source.uid == target.uid:
        raise ValueError("Source and target Contexts must be distinct.")
    return UpdateEndpointAccesses(source=source, target=target)


__all__ = [
    "UpdateEndpointAccesses",
    "choose_update_endpoint_operands",
    "resolve_update_endpoint_accesses",
]
