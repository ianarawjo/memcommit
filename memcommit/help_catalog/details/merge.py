"""Detailed Help topics owned by Merge."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


MERGE_DETAILS = (
    OperationComparisonDetail(
        id="structural-boundary",
        operation="merge",
        title="MERGE BOUNDARY",
        use_when="Checking how each structural Source/Target case is handled.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Merge is a deterministic structural union, not a three-way or "
            "semantic reconciliation."
        ),
        options=(
            OperationComparisonOption(
                label="SOURCE ONLY",
                guidance="Add the Source item to the selected Target.",
            ),
            OperationComparisonOption(
                label="EXACT MATCH",
                guidance="Leave the stored item unchanged.",
            ),
            OperationComparisonOption(
                label="CONFLICT",
                guidance=(
                    "Choose KEEP TARGET or TAKE SOURCE; Merge never synthesizes "
                    "custom content."
                ),
            ),
            OperationComparisonOption(
                label="TARGET ONLY",
                guidance=(
                    "Keep the Target item; absence from Source never deletes it."
                ),
            ),
            OperationComparisonOption(
                label="RECURSIVE",
                guidance="Align descendants by the same relative path.",
            ),
        ),
    ),
)


__all__ = ["MERGE_DETAILS"]
