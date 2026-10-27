"""Detailed Help topics owned by Init."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


INIT_DETAILS = (
    OperationTextDetail(
        id="parent-contexts",
        operation="init",
        title="PARENT CONTEXTS",
        use_when="Understanding which Contexts Init creates or reuses.",
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.LIMITATION,
        body=(
            "mem init CONTEXT_NAME creates missing parent Contexts and the "
            "requested Context, reuses existing Contexts without changing their "
            "Memories or history, and switches to the requested Context. "
            "This does not embed children."
        ),
    ),
)


__all__ = ["INIT_DETAILS"]
