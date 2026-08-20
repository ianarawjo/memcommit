"""Detailed Help topics owned by Impact."""

from memcommit.help_catalog.model import (
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
                    "or Resolve effects, or inspect a saved Meld, Sever, or Update "
                    "Impact."
                ),
            ),
            OperationComparisonOption(
                label="DIRECTIONAL UPDATE",
                guidance=(
                    "Omit OPERATION and provide --from or --to; the omitted endpoint "
                    "is the current Context."
                ),
            ),
        ),
    ),
)


__all__ = ["IMPACT_DETAILS"]
