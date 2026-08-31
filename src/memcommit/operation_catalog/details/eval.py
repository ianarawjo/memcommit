"""Detailed Help topic for the reserved Eval shell."""

from memcommit.operation_catalog.model import (
    DetailDiscovery,
    HelpDetailKind,
    OperationTextDetail,
)


EVAL_DETAILS = (
    OperationTextDetail(
        id="evaluation-scope",
        operation="eval",
        title="RESERVED SHELL",
        use_when="Checking the current boundary of the unfinished Eval operation.",
        discovery=DetailDiscovery.ON_DEMAND,
        detail_kind=HelpDetailKind.LIMITATION,
        body=(
            "Eval currently preserves only its public command and application "
            "package names. It has no executable subcommands, campaign engine, "
            "provider calls, Context effects, or evaluation ledger behavior."
        ),
    ),
)


__all__ = ["EVAL_DETAILS"]
