"""Detailed Help topics owned by Query."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


QUERY_DETAILS = (
    OperationTextDetail(
        id="query-only-access",
        operation="query",
        title="QUERY-ONLY ACCESS",
        use_when=(
            "Using shared memory that permits questions without revealing its "
            "complete Source Memories."
        ),
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Query can answer through QUERY-only access without exposing the "
            "complete underlying Source Memories or policy."
        ),
        detail_kind=HelpDetailKind.ACCESS_BOUNDARY,
        body=(
            "Shared agent memory may allow QUERY without READ: it can answer a "
            "specific question within the granted boundary while keeping its "
            "complete Source Memories and full underlying policy concealed."
        ),
    ),
)


__all__ = ["QUERY_DETAILS"]
