"""Public compatibility surface for the named Ground shell runtime.

The UI factories and renderers remain available here as test seams retained
from the former single-module runtime. The workbench resolves them when it is
constructed so existing monkeypatch-based terminal captures keep working.
"""

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
from memcommit.adapters.console.commands.ground.named_shell.presentation import (
    render_named_ground_memories_pane,
    render_named_ground_memory_detail,
    render_named_ground_rules_pane,
)

from memcommit.adapters.console.commands.ground.named_shell.runtime.entrypoint import (
    run_named_ground_shell,
)

__all__ = [
    "Frame",
    "build_framed_multiline_input",
    "build_inline_direct_edit_input",
    "build_scrollable_text_pane",
    "render_named_ground_memories_pane",
    "render_named_ground_memory_detail",
    "render_named_ground_rules_pane",
    "run_named_ground_shell",
]
