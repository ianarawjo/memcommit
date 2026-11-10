"""Blank-Ground shell contracts, presentation, and runtime."""

from memcommit.adapters.console.commands.ground.shell.presentation import (
    render_ground_cases_pane,
    render_ground_contexts_pane,
    render_ground_goal_pane,
    render_ground_rules_pane,
    render_ground_top_panel,
    render_proposal_review,
    _anchored_conversation_fragments as _anchored_conversation_fragments,
)
from memcommit.adapters.console.commands.ground.shell.proposal import (
    GroundShellContextSuggestion,
    GroundShellMemoryDraft,
    GroundShellNewContextSuggestion,
    GroundShellProposal,
    GroundShellResult,
    GroundShellRuleDraft,
    format_proposal_command,
    proposal_argv,
)
from memcommit.adapters.console.commands.ground.shell.runtime import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
    run_ground_shell,
)

__all__ = [
    "GROUND_CONTEXTS_FRAME_HEIGHT",
    "GROUND_GOAL_FRAME_HEIGHT",
    "GroundShellContextSuggestion",
    "GroundShellMemoryDraft",
    "GroundShellNewContextSuggestion",
    "GroundShellProposal",
    "GroundShellResult",
    "GroundShellRuleDraft",
    "format_proposal_command",
    "proposal_argv",
    "render_ground_cases_pane",
    "render_ground_contexts_pane",
    "render_ground_goal_pane",
    "render_ground_rules_pane",
    "render_ground_top_panel",
    "render_proposal_review",
    "run_ground_shell",
]
