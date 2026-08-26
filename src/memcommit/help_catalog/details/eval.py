"""Detailed Help topics owned by legacy Eval."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


EVAL_DETAILS = (
    OperationComparisonDetail(
        id="evaluation-scope",
        operation="eval",
        title="EVALUATION SCOPE",
        use_when="Understanding the boundary of the existing research harness.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "This legacy surface operates on fixed research fixtures and a "
            "Profile-independent evaluation ledger. It does not evaluate or "
            "change the current Context; a general evaluation interface remains "
            "future work."
        ),
        options=(
            OperationComparisonOption(
                label="STATUS",
                guidance="Inspect retained campaign results without a provider call.",
            ),
            OperationComparisonOption(
                label="RUN",
                guidance=(
                    "Run a fixed semantic campaign, which may contact a provider "
                    "and writes only the evaluation ledger."
                ),
            ),
        ),
    ),
)


__all__ = ["EVAL_DETAILS"]
