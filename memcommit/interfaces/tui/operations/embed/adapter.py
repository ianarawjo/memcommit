"""Compose the Embed TUI with one Store-backed application port."""

from __future__ import annotations

from prompt_toolkit.input import Input
from prompt_toolkit.output import Output

from memcommit.embed_application import FrozenEmbedPlan
from memcommit.embed_runtime import MemoryStoreEmbedPort
from memcommit.interfaces.tui.operations.embed.model import EmbedTuiSetup
from memcommit.interfaces.tui.operations.embed.screen import run_embed_tui


def choose_embed_setup(
    port: MemoryStoreEmbedPort,
    *,
    app_input: Input | None = None,
    app_output: Output | None = None,
    require_tty: bool = True,
) -> FrozenEmbedPlan | None:
    """Review one local relationship without letting the TUI own storage."""

    setup = EmbedTuiSetup(
        names=port.local_context_names,
        current_context=(
            port.current_context_name
            if port.current_context_name in port.local_context_names
            else None
        ),
    )
    return run_embed_tui(
        setup,
        inspect_context=port.inspect_local_context,
        freeze_exact_gap=port.freeze_exact_gap,
        app_input=app_input,
        app_output=app_output,
        require_tty=require_tty,
    )
