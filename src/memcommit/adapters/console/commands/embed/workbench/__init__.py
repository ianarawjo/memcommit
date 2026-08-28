"""Interactive workbench for the Embed application use case."""

from memcommit.adapters.console.commands.embed.workbench.setup import (
    build_embed_tui_setup,
    choose_embed_setup,
)
from memcommit.adapters.console.commands.embed.workbench.model import EmbedTuiSetup
from memcommit.adapters.console.commands.embed.workbench.screen import (
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
