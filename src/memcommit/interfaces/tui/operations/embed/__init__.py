"""Interactive adapter for the Embed application use case."""

from memcommit.interfaces.tui.operations.embed.adapter import (
    build_embed_tui_setup,
    choose_embed_setup,
)
from memcommit.interfaces.tui.operations.embed.model import EmbedTuiSetup
from memcommit.interfaces.tui.operations.embed.screen import (
    EMBED_COMMAND_FORM,
    embed_exact_command_review,
    memory_embed_exact_command_review,
    parse_embed_command_argv,
    run_embed_tui,
)

__all__ = [
    "EmbedTuiSetup",
    "EMBED_COMMAND_FORM",
    "build_embed_tui_setup",
    "choose_embed_setup",
    "embed_exact_command_review",
    "memory_embed_exact_command_review",
    "parse_embed_command_argv",
    "run_embed_tui",
]
