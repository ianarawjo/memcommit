"""Detailed Help topics owned by Add."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


ADD_DETAILS = (
    OperationTextDetail(
        id="literal-input",
        operation="add",
        title="LITERAL INPUT",
        use_when="Checking how Add interprets supplied text.",
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Add stores each positional text value as one new Memory in the current Context."
        ),
        detail_kind=HelpDetailKind.LIMITATION,
        body=(
            "Each positional text value becomes one new Memory in the current Context. "
            "Memory UIDs, Context names, and file paths are stored as text; "
            "Add does not load their contents."
        ),
    ),
)


__all__ = ["ADD_DETAILS"]
