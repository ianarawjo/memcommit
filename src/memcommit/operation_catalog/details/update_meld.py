"""Shared Help boundary between Update and Merge."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


_BODY = (
    "Update applies one instruction to revise Memories in the current Context; "
    "-r includes its lexical descendants. Merge combines two exact Contexts "
    "and reconciles their relationships and conflicts in an existing Target."
)


UPDATE_MELD_DETAILS = tuple(
    OperationTextDetail(
        id="update-vs-merge",
        operation=operation,
        title="UPDATE VS. MERGE",
        use_when="Choosing between revising Memories with an instruction and combining two Contexts.",
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.SEMANTIC_BOUNDARY,
        body=_BODY,
    )
    for operation in ("merge", "update")
)


__all__ = ["UPDATE_MELD_DETAILS"]
