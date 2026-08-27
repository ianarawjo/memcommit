"""Detailed Help topics owned by Init."""

from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


INIT_DETAILS = (
    OperationComparisonDetail(
        id="parent-contexts",
        operation="init",
        title="PARENT CONTEXTS",
        use_when="Choosing whether Init should also create missing parent Contexts.",
        discovery=DetailDiscovery.ON_DEMAND,
        explanation=(
            "mem init NAME creates only that exact Context. Add -p when "
            "missing parent Contexts should also exist."
        ),
        options=(
            OperationComparisonOption(
                label="DEFAULT",
                guidance="Create only the exact requested Context.",
            ),
            OperationComparisonOption(
                label="WITH -P",
                guidance=(
                    "Create missing parent Contexts and reuse parents that "
                    "already exist; this does not embed children."
                ),
            ),
        ),
    ),
)


__all__ = ["INIT_DETAILS"]
