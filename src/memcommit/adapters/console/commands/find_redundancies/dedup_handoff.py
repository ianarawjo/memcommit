"""Internal bridge from confirmed semantic evidence into Dedun resolution."""

from __future__ import annotations

from memcommit.adapters.console.clipboard import write_system_clipboard
from memcommit.application.operations.dedun.application import (
    DedunRequest,
    apply_dedun,
    prepare_dedun,
)
from memcommit.application.operations.dedun.runtime import MemoryStoreDedunPort
from memcommit.adapters.console.commands.dedun.workbench import run_dedun_workbench
from memcommit.application.capabilities.memory_issue_analysis.handoff import (
    QualityFindingHandoff,
)
from memcommit.persistence.store import MemoryStore


def run_dedun_resolution(
    store: MemoryStore,
    *,
    current_name: str | None,
    handoffs: tuple[QualityFindingHandoff, ...],
) -> None:
    """Open Dedun review after fresh Source and authority validation."""

    request = DedunRequest(
        handoffs,
        exact_source=handoffs[0].sources[0],
        exact_source_frame_digest=handoffs[0].source_frame_digest,
    )
    port = MemoryStoreDedunPort(store, current_name=current_name)
    plan = prepare_dedun(request, port=port)
    run_dedun_workbench(
        plan,
        apply_selections=lambda selections: apply_dedun(
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
