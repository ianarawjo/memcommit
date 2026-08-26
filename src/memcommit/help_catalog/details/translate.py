"""Detailed Help topics owned by Translate."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


TRANSLATE_DETAILS = (
    OperationComparisonDetail(
        id="materialization-routes",
        operation="translate",
        title="MATERIALIZATION ROUTES",
        use_when="Choosing whether a translated view should become local content.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Every route preserves the original Memory content; only explicit "
            "materialization creates or adds ordinary Memories."
        ),
        options=(
            OperationComparisonOption(
                label="VIEW",
                guidance=(
                    "Generate and save a reusable translated view without "
                    "materializing ordinary Memories."
                ),
            ),
            OperationComparisonOption(
                label="--SAVE-AS",
                guidance="Create a separate translated Context.",
            ),
            OperationComparisonOption(
                label="--IN-PLACE",
                guidance=(
                    "Add translated sibling Memories without rewriting the "
                    "original Memories."
                ),
            ),
        ),
    ),
)


__all__ = ["TRANSLATE_DETAILS"]
