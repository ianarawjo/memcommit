"""Detailed Help topics owned by Fit."""

from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


FIT_DETAILS = (
    OperationComparisonDetail(
        id="verdicts",
        operation="fit",
        title="YES, MAY, OR NO",
        use_when="Interpreting Fit's closed judgment labels.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Fit judges ordinary-language compatibility, not whether the "
            "propositions are true or sufficiently supported."
        ),
        options=(
            OperationComparisonOption(
                label="YES",
                guidance=(
                    "Compatible across materially ordinary readings. Context: "
                    "the building has a main and side entrance. 'The main entrance "
                    "closes at 5.' and 'The side entrance stays open until 8.'"
                ),
            ),
            OperationComparisonOption(
                label="MAY",
                guidance=(
                    "One ordinary reading is compatible and another is not. "
                    "Context: the building has multiple entrances, including a "
                    "main and side entrance. 'The main entrance closes at 5.' and "
                    "'The entrance stays open until 8.' depend on which entrance "
                    "the second proposition denotes."
                ),
            ),
            OperationComparisonOption(
                label="NO",
                guidance=(
                    "Incompatible across materially ordinary readings. Context: "
                    "the building has only one entrance. 'The entrance closes at "
                    "5.' and 'The entrance stays open until 8.' denote that same "
                    "entrance."
                ),
            ),
        ),
    ),
)


__all__ = ["FIT_DETAILS"]
