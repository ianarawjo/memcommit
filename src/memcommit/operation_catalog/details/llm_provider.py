"""Detailed Help topics owned by LLM Provider."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


LLM_PROVIDER_DETAILS = (
    OperationComparisonDetail(
        id="actions",
        operation="llm-provider",
        title="LLM PROVIDER ACTIONS",
        use_when="Choosing whether to inspect, select, or contact an LLM provider.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "LLM provider inspection, configuration, reset, and readiness checking "
            "are separate actions. None changes Context content."
        ),
        options=(
            OperationComparisonOption(
                label="OVERVIEW",
                guidance=(
                    "Use bare mem llm-provider in a terminal to open USE and CONFIGURE together; piped output prints a summary without "
                    "an interactive screen."
                ),
            ),
            OperationComparisonOption(
                label="STATUS",
                guidance=(
                    "Show the selected LLM provider and bounded settings without "
                    "connecting or exposing credentials."
                ),
            ),
            OperationComparisonOption(
                label="USE",
                guidance="Select saved Codex settings without changing its model or reasoning.",
            ),
            OperationComparisonOption(
                label="CONFIGURE",
                guidance="Edit Codex model and supported reasoning choices; preserve the active provider and other settings.",
            ),
            OperationComparisonOption(
                label="RESET",
                guidance=(
                    "Restore the saved Codex model and low reasoning "
                    "defaults while preserving provider selection and hidden settings."
                ),
            ),
            OperationComparisonOption(
                label="PROBE",
                guidance=(
                    "Contact the selected LLM provider with one synthetic strict-schema "
                    "completion before durable work."
                ),
            ),
        ),
    ),
)


__all__ = ["LLM_PROVIDER_DETAILS"]
