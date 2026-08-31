"""Four-responsibility runtime package for the blank-Ground shell."""

from prompt_toolkit.widgets import Frame

from memcommit.adapters.console.terminal.components.in_frame_input import (
    build_inline_direct_edit_input,
)
from memcommit.adapters.console.terminal.components.multiline_input import (
    build_framed_multiline_input,
)
from memcommit.adapters.console.terminal.components.scrollable_pane import (
    build_scrollable_text_pane,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.presentation import (
    _render_proposal_effects_block,
    render_ground_contexts_pane,
)
from memcommit.adapters.console.commands.ground_workbench.ground.shell.proposal import (
    _freeze_memory_drafts,
    _freeze_rule_drafts,
)

from .entry import (
    GROUND_CONTEXTS_FRAME_HEIGHT,
    GROUND_GOAL_FRAME_HEIGHT,
    GROUND_LOCATION_FRAME_HEIGHT,
    INITIAL_QUESTION,
    _THINKING_INTERVAL_SECONDS,
    run_ground_shell,
)

__all__ = [
    # Compatibility seams retained for focused prompt-toolkit tests.
    "Frame",
    "GROUND_CONTEXTS_FRAME_HEIGHT",
    "GROUND_GOAL_FRAME_HEIGHT",
    "GROUND_LOCATION_FRAME_HEIGHT",
    "INITIAL_QUESTION",
    "_THINKING_INTERVAL_SECONDS",
    "_freeze_memory_drafts",
    "_freeze_rule_drafts",
    "_render_proposal_effects_block",
    "build_framed_multiline_input",
    "build_inline_direct_edit_input",
    "build_scrollable_text_pane",
    "render_ground_contexts_pane",
    "run_ground_shell",
]
