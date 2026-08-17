"""Detailed Help topics owned by Provider."""

from memcommit.help_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


PROVIDER_DETAILS = (
    OperationComparisonDetail(
        id="actions",
        operation="provider",
        title="PROVIDER ACTIONS",
        use_when="Choosing whether to inspect, select, or contact a provider.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "Provider configuration and readiness checking are separate actions. "
            "Neither action changes Context content."
        ),
        options=(
            OperationComparisonOption(
                label="STATUS",
                guidance=(
                    "Show the selected provider and bounded settings without "
                    "connecting or exposing credentials."
                ),
            ),
            OperationComparisonOption(
                label="USE",
                guidance="Store the provider and model selection for later commands.",
            ),
            OperationComparisonOption(
                label="PROBE",
                guidance=(
                    "Contact the selected provider with one synthetic strict-schema "
                    "completion before durable work."
                ),
            ),
        ),
    ),
)


__all__ = ["PROVIDER_DETAILS"]
