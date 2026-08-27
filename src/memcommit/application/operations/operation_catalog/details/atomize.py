"""Detailed Help topics owned by Atomize."""

from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


ATOMIZE_DETAILS = (
    OperationComparisonDetail(
        id="operation-routes",
        operation="atomize",
        title="ATOMIZE ROUTES",
        use_when=(
            "Distinguishing ordinary proposition separation from issue-scoped "
            "evaluation."
        ),
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Ordinary Atomize and --evaluate share one command entry point but "
            "perform different semantic operations."
        ),
        options=(
            OperationComparisonOption(
                label="ATOMIZE",
                guidance=(
                    "Separate distinct propositions already present in composite "
                    "Memories into independently reviewable Memories."
                ),
            ),
            OperationComparisonOption(
                label="--EVALUATE",
                guidance=(
                    "Perform an issue-scoped directional Meld rather than the "
                    "ordinary Atomize split route."
                ),
            ),
        ),
    ),
)


__all__ = ["ATOMIZE_DETAILS"]
