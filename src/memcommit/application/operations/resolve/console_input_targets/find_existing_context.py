"""Find the existing readable Context or local Memory owner named by an input."""

from __future__ import annotations

from typing import TYPE_CHECKING

from memcommit.application.capabilities.local_target_lookup import (
    LocalDirectMemoryLocatorStore,
    resolve_local_direct_memory_locator,
)
from memcommit.application.context_access.operand_resolution import (
    resolve_existing_context_access,
)
from memcommit.core.context_targeting.model import DirectMemoryTarget

if TYPE_CHECKING:
    from memcommit.application.capabilities.operand_resolution import ContextOperandCandidate
    from memcommit.application.context_access.access import ContextAccess


def locate_context_from_operand(
    store: LocalDirectMemoryLocatorStore,
    operand: str,
    *,
    current_context_name: str | None,
    context_candidates: tuple[ContextOperandCandidate[ContextAccess], ...],
) -> str:
    """Find a readable Context using the command-start namespace snapshot."""
    target = resolve_existing_context_access(
        store,
        operand,
        current_name=current_context_name,
        required_permission="READ",
        candidates=context_candidates,
    )
    return target.name


def find_memory_owner_context(
    store: LocalDirectMemoryLocatorStore,
    memory_selector: str,
    *,
    current_context_name: str | None,
) -> DirectMemoryTarget:
    """Find a local owner and exact Memory UID for an unqualified selector."""
    # Global Memory lookup must not enumerate granted contents or give the
    # current Context hidden priority. Granted owners must be named explicitly.
    return resolve_local_direct_memory_locator(
        store,
        memory_selector,
        current=current_context_name,
    )
