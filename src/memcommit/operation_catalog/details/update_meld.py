"""Shared Help boundary between Update and Meld."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


_BODY = (
    "Update is revision-oriented: it treats a Source as verified change evidence "
    "and semantically patches an existing Target. Meld is merge-oriented: it "
    "semantically combines two inputs while reconciling their relationships and "
    "conflicts, either into an existing Baseline or a new Result."
)


UPDATE_MELD_DETAILS = tuple(
    OperationTextDetail(
        id="update-vs-meld",
        operation=operation,
        title="UPDATE VS. MELD",
        use_when="Choosing between Update and Meld for an input-to-Target operation.",
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.SEMANTIC_BOUNDARY,
        body=_BODY,
    )
    for operation in ("meld", "update")
)


__all__ = ["UPDATE_MELD_DETAILS"]
