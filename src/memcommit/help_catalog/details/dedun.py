"""Detailed Help boundary for complete exact-plus-semantic Dedun."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


DEDUN_DETAILS = (
    OperationTextDetail(
        id="partial-overlap",
        operation="dedun",
        title="PARTIAL OVERLAP",
        use_when="Only wording or one claim inside a Memory overlaps another Memory.",
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Dedun judges complete stored Memories; partial-claim overlap requires "
            "Atomize first."
        ),
        detail_kind=HelpDetailKind.SEMANTIC_BOUNDARY,
        body=(
            "Dedun treats each complete stored direct Memory as one indivisible "
            "judgment unit. Shared wording or a shared proper part—including abc "
            "and bcd sharing bc—is OVERLAP, not semantic redundancy, so Dedun does "
            "not split or remove it. If only one claim inside a multi-claim Memory "
            "is redundant, run Atomize first, then run Dedun on the separately "
            "reviewable Memories."
        ),
    ),
)


__all__ = ["DEDUN_DETAILS"]
