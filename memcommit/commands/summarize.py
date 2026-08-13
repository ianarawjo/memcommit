"""Render the shared understanding-summary unit for one Context."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated, Iterator, Optional

import typer

from memcommit.bootstrap import build_summarize_console_runner
from memcommit.clipboard import ClipboardError, write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.interfaces.console import (
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.understanding import understanding_lines
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.summarize import SummarizeError, SummarizeProvider
from memcommit.summarize_application import SummarizeRequest
from memcommit.summarize_runtime import run_summarize_with_store


@contextmanager
def _provider_session() -> Iterator[SummarizeProvider]:
    """Keep terminal progress outside the application/provider contracts."""

    with CommandProgress(
        "SUMMARIZE",
        "connecting provider",
        total=2,
    ) as progress:
        provider = connect_codex_chatgpt_provider()
        progress.update("summarizing memories", step=2)
        yield provider


def cmd(
    context_name: Annotated[
        Optional[str],
        typer.Argument(
            help=(
                "Existing Context to summarize by canonical name or explicit "
                "relative locator (defaults to current)"
            )
        ),
    ] = None,
    direct: Annotated[
        bool,
        typer.Option(
            "-d",
            "--direct",
            help="Summarize only directly owned Memories in the selected Context",
        ),
    ] = False,
    recursive: Annotated[
        bool,
        typer.Option(
            "-r",
            "--recursive",
            help=("Include readable lexical descendants and follow embedded Contexts"),
        ),
    ] = False,
    copy_result: Annotated[
        bool,
        typer.Option(
            "--copy",
            help=(
                "Copy the verified WHAT MEM UNDERSTOOD document as plain "
                "text without creating a structured mutation stage"
            ),
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print the result instead of opening the interactive Viewer",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Require the interactive result Viewer",
        ),
    ] = False,
) -> None:
    """Summarize what Mem understands; never change or checkpoint a Context."""
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)
        mode = resolve_console_mode(plain=plain, tui=tui)

        def execute(request: SummarizeRequest):
            # Route validation happens before opening durable or semantic
            # infrastructure, so a forced TUI cannot partially execute when
            # no terminal is available.
            store = MemoryStore(create=False)
            snapshot = ContextOperandSnapshot.capture(store)
            return run_summarize_with_store(
                request,
                store=store,
                current_context_name=snapshot.current_name,
                provider_session_factory=_provider_session,
            )

        runner = build_summarize_console_runner(
            execute=execute,
            terminal=SystemTerminalCapabilities(),
        )
        result = runner.run(
            SummarizeRequest(
                context_locator=context_name,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            ),
            mode=mode,
        )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        SummarizeError,
        ConsoleModeError,
        ValueError,
    ) as error:
        typer.secho(
            "Summarize error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if copy_result:
        rendered_understanding = understanding_lines(result.understanding)
        clipboard_text = "\n".join(rendered_understanding)
        try:
            write_system_clipboard(clipboard_text)
        except ClipboardError as error:
            typer.secho(
                f"Copy error: {display_escape_text(str(error))}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1)
        typer.secho(
            "Copied WHAT MEM UNDERSTOOD as plain text; no structured "
            "clipboard stage was created.",
            fg=typer.colors.GREEN,
            err=True,
        )
