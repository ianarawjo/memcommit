"""Detailed Help topics owned by Impact."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


IMPACT_DETAILS = (
    OperationComparisonDetail(
        id="invocation",
        operation="impact",
        title="INVOCATION",
        use_when="Choosing an operation-specific Impact or saved analysis.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Impact remains read-only; Apply belongs to a separate "
            "execution operation."
        ),
        options=(
            OperationComparisonOption(
                label="OPERATION-SPECIFIC",
                guidance=(
                    "Use mem impact OPERATION to prepare Atomize, Distill, "
                    "Elaborate, or Makemore effects, inspect a saved Sever result, "
                    "or see the planned Merge scope."
                ),
            ),
            OperationComparisonOption(
                label="SAVED ANALYSES",
                guidance=(
                    "Use mem impact --sessions to browse every durable artifact "
                    "that Impact can inspect, or mem impact atomize --sessions "
                    "for the filtered Atomize catalog."
                ),
            ),
        ),
    ),
)


__all__ = ["IMPACT_DETAILS"]
