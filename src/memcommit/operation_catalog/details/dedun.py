"""Detailed Help boundary for Dedup's retained semantic Dedun implementation."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


DEDUN_DETAILS = (
    OperationTextDetail(
        id="partial-overlap",
        operation="dedup",
        title="PARTIAL OVERLAP",
        use_when="Only wording or one claim inside a Memory overlaps another Memory.",
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Semantic Dedup judges complete stored Memories; partial-claim overlap requires "
            "Atomize first."
        ),
        detail_kind=HelpDetailKind.SEMANTIC_BOUNDARY,
        body=(
            "Default Dedup treats each complete stored direct Memory as one indivisible "
            "judgment unit. Shared wording or a shared proper part—including abc "
            "and bcd sharing bc—is OVERLAP, not semantic redundancy, so Dedup does "
            "not split or remove it. If only one claim inside a multi-claim Memory "
            "is redundant, run Atomize first, then run Dedup on the separately "
            "reviewable Memories. Use --literal to remove only same-role exact "
            "copies without semantic inference."
        ),
    ),
)


__all__ = ["DEDUN_DETAILS"]
