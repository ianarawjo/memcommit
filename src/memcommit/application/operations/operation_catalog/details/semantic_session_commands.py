"""Command-boundary Help for semantic execution sessions."""

from memcommit.application.operations.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


def _detail(operation: str, start_effect: str, turn_effect: str) -> OperationTextDetail:
    return OperationTextDetail(
        id="interactive-commands",
        operation=operation,
        title="INTERACTIVE COMMANDS",
        use_when="Reviewing what the interactive setup and response actions execute.",
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.LIMITATION,
        body=(
            f"The setup screen rebuilds one portable START command; {start_effect}. "
            "Each later execution decision rebuilds a TURN command containing "
            f"--expect-session for the exact saved revision; {turn_effect}. "
            "Once required decisions are complete, the operation atomically Applies "
            "the frozen state and publishes a compact receipt."
        ),
    )


SEMANTIC_SESSION_COMMAND_DETAILS = (
    _detail(
        "meld",
        "running it starts or resumes Meld analysis and its decision session",
        "running it replaces the saved decisions; completion Applies the target",
    ),
    _detail(
        "update",
        "running it starts or resumes the staged Update decisions",
        "running it replaces those decisions; completion Applies target changes",
    ),
    _detail(
        "sever",
        "running it starts or resumes Sever analysis and its decision session",
        "running it records a candidate decision; completion creates the Result",
    ),
)


__all__ = ["SEMANTIC_SESSION_COMMAND_DETAILS"]
