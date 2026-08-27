"""Detailed Help topics owned by Check Conformance."""

from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    OperationComparisonDetail,
    OperationComparisonOption,
)


CHECK_CONFORMANCE_DETAILS = (
    OperationComparisonDetail(
        id="fit-or-conformance",
        operation="check-conformance",
        title="FIT OR CONFORMANCE",
        use_when=(
            "Choosing between mutual compatibility and satisfaction of stated "
            "conditions."
        ),
        discovery=DetailDiscovery.TOOL_SELECTION,
        discovery_summary=(
            "Fit asks whether propositions can coexist; Conformance asks whether "
            "selected subjects satisfy stated Rules or condition propositions."
        ),
        explanation=(
            "The two checks use related semantic judgment but answer different "
            "questions."
        ),
        options=(
            OperationComparisonOption(
                label="FIT",
                guidance=(
                    "Judge whether all propositions in one defined set can jointly "
                    "hold under ordinary interpretation."
                ),
            ),
            OperationComparisonOption(
                label="CONFORMANCE",
                guidance=(
                    "Judge whether selected Memories or Examples satisfy stated "
                    "Rules or condition propositions."
                ),
            ),
        ),
    ),
)


__all__ = ["CHECK_CONFORMANCE_DETAILS"]
