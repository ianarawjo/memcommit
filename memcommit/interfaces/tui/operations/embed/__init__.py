"""Interactive adapter for the Embed application use case."""

from memcommit.interfaces.tui.operations.embed.adapter import choose_embed_setup
from memcommit.interfaces.tui.operations.embed.model import EmbedTuiSetup
from memcommit.interfaces.tui.operations.embed.screen import (
    embed_exact_command_review,
    run_embed_tui,
)

__all__ = [
    "EmbedTuiSetup",
    "choose_embed_setup",
    "embed_exact_command_review",
    "run_embed_tui",
]
