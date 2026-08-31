"""Validate and freeze one blank-Ground runtime start."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from memcommit.core.context_targeting.naming import validate_portable_context_name

from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellProposal,
    _freeze_proposal,
)


@dataclass(frozen=True)
class GroundShellStart:
    """Validated inputs from which one process-local session can start."""

    fixed_ground_name: str | None
    frozen_initial_proposal: GroundShellProposal | None
    frozen_initial_turns: tuple[str, ...]
    working_goal: str


def prepare_ground_shell_start(
    *,
    ground_name: str | None,
    initial_request: str,
    initial_proposal: GroundShellProposal | None,
    initial_submitted_turns: Sequence[str],
    context_catalog_count: int,
    context_catalog_names: Sequence[str],
) -> GroundShellStart:
    """Reject contradictory entry states before prompt-toolkit is built."""

    fixed_ground_name = (
        validate_portable_context_name(ground_name) if ground_name is not None else None
    )
    if initial_proposal is not None and initial_request.strip():
        raise ValueError(
            "A resumed Ground proposal cannot start another initial request."
        )
    if initial_proposal is not None and fixed_ground_name is None:
        raise ValueError("A resumed Ground proposal requires its Save Location.")
    frozen_initial_proposal = (
        _freeze_proposal(
            initial_proposal,
            expected_ground_name=fixed_ground_name,
        )
        if initial_proposal is not None
        else None
    )
    frozen_initial_turns = tuple(initial_submitted_turns)
    if any(
        not isinstance(turn, str) or not turn.strip() for turn in frozen_initial_turns
    ):
        raise ValueError("Resumed Ground turns must be nonblank text.")
    if frozen_initial_proposal is None and frozen_initial_turns:
        raise ValueError("Resumed Ground turns require a saved proposal.")
    if fixed_ground_name is not None and (
        context_catalog_count or tuple(context_catalog_names)
    ):
        raise ValueError(
            "A fixed Ground Save Location cannot use Context recommendations."
        )

    working_goal = (
        frozen_initial_proposal.goal
        if frozen_initial_proposal is not None
        else initial_request.strip()
    )
    return GroundShellStart(
        fixed_ground_name=fixed_ground_name,
        frozen_initial_proposal=frozen_initial_proposal,
        frozen_initial_turns=frozen_initial_turns,
        working_goal=working_goal,
    )
