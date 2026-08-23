"""Internal bridge from confirmed semantic evidence into Dedun resolution."""

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


def run_dedun_resolution(
    store: MemoryStore,
    *,
    current_name: str | None,
    handoffs: tuple[QualityFindingHandoff, ...],
) -> None:
    """Open Dedun review after fresh Source and authority validation."""

    request = DedupRequest(
        handoffs,
        exact_source=handoffs[0].sources[0],
        exact_source_frame_digest=handoffs[0].source_frame_digest,
    )
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


# Compatibility names for internal callers and plugins compiled against v1.
run_redundancy_consolidation = run_dedun_resolution
run_duplicate_dedup_handoff = run_dedun_resolution


__all__ = [
    "run_dedun_resolution",
    "run_duplicate_dedup_handoff",
    "run_redundancy_consolidation",
]
