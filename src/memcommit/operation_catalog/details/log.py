"""Detailed Help topics owned by Log."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


LOG_DETAILS = (
    OperationComparisonDetail(
        id="history-routes",
        operation="log",
        title="LOG ROUTES",
        use_when="Choosing which recorded history surface to inspect.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Log groups several retained-history views under one entry point. "
            "Only a natural-language history search requires semantic interpretation."
        ),
        options=(
            OperationComparisonOption(
                label="CONTEXT CHECKPOINTS",
                guidance="Browse the recorded checkpoints for one Context.",
            ),
            OperationComparisonOption(
                label="MEMORY LINEAGE",
                guidance=(
                    "Inspect one retained Memory lineage; mem trace is the "
                    "shorter equivalent entry point."
                ),
            ),
            OperationComparisonOption(
                label="SEMANTIC SEARCH",
                guidance="Search retained history with a natural-language query.",
            ),
            OperationComparisonOption(
                label="PROFILE ATTEMPTS",
                guidance=(
                    "Inspect Profile-scoped attempts and their complete "
                    "entered commands."
                ),
            ),
            OperationComparisonOption(
                label="STUDY ACTIONS",
                guidance=(
                    "Inspect detailed actions for the active Study Profile, "
                    "including Participant command text."
                ),
            ),
        ),
    ),
)


__all__ = ["LOG_DETAILS"]
