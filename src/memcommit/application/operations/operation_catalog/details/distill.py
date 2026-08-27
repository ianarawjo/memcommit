"""Detailed Help topics owned by Distill."""

from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


DISTILL_DETAILS = (
    OperationComparisonDetail(
        id="distill-or-atomize",
        operation="distill",
        title="DISTILL OR ATOMIZE",
        use_when=(
            "Choosing whether to derive a higher-level proposition or separate "
            "propositions already present."
        ),
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Use Distill to infer higher-level Rules or condition propositions "
            "across cases; use Atomize to separate propositions already present."
        ),
        explanation=(
            "The bounded Source Context supplies supporting propositions. An "
            "optional Goal focuses the direction of Distill's derivation."
        ),
        options=(
            OperationComparisonOption(
                label="DISTILL",
                guidance=(
                    "Derive a higher-level Rule or condition proposition across "
                    "Case or Example propositions."
                ),
            ),
            OperationComparisonOption(
                label="ATOMIZE",
                guidance=(
                    "Separate distinct propositions already present in composite "
                    "Memories without deriving a higher-level Rule."
                ),
            ),
        ),
    ),
)


__all__ = ["DISTILL_DETAILS"]
