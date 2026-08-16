"""Interactive adapter from confirmed duplicate findings into Dedup."""

from __future__ import annotations

from memcommit.clipboard import write_system_clipboard
from memcommit.dedup_application import (
    DedupRequest,
    apply_dedup,
    prepare_dedup,
)
from memcommit.dedup_runtime import MemoryStoreDedupPort
from memcommit.interfaces.tui.operations.dedup import run_dedup_tui
from memcommit.quality_finding_handoff import QualityFindingHandoff
from memcommit.store import MemoryStore


def run_duplicate_dedup_handoff(
    store: MemoryStore,
    *,
    current_name: str | None,
    handoffs: tuple[QualityFindingHandoff, ...],
) -> None:
    """Open normal Dedup review after fresh Source and authority validation."""

    request = DedupRequest(handoffs)
    port = MemoryStoreDedupPort(store, current_name=current_name)
    plan = prepare_dedup(request, port=port)
    run_dedup_tui(
        plan,
        apply_selections=lambda selections: apply_dedup(
            plan,
            selections,
            port=port,
        ),
        clipboard_writer=write_system_clipboard,
    )


__all__ = ["run_duplicate_dedup_handoff"]
