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
        use_when="Choosing the operation-specific or directional Impact form.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Impact remains read-only in either form; Apply belongs to a separate "
            "execution operation."
        ),
        options=(
            OperationComparisonOption(
                label="OPERATION-SPECIFIC",
                guidance=(
                    "Use mem impact OPERATION to prepare Atomize, Forget, Distill, "
                    "Resolve, or directional Update effects, or inspect a saved "
                    "Meld, Sever, or Update Impact."
                ),
            ),
            OperationComparisonOption(
                label="DIRECTIONAL UPDATE",
                guidance=(
                    "Use mem impact update SOURCE TARGET, or retain the root "
                    "--from or --to compatibility form; a missing option endpoint "
                    "is the current Context."
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
