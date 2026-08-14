"""Render the shared understanding-summary unit for one Context."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated, Iterator, Optional

import typer

from memcommit.bootstrap import build_summarize_console_runner
from memcommit.clipboard import ClipboardError, write_system_clipboard
from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.context_targeting.tui.reach import ContextReachViewMode
from memcommit.interfaces.console import (
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.summarize import (
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
    project_summarize_clipboard,
)
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.summarize import SummarizeError, SummarizeProvider
from memcommit.summarize_application import SummarizeRequest, SummarizeResult
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


def _summarize_clipboard_text(
    result: SummarizeResult | SummarizeTuiOutcome,
) -> str:
    """Keep both explicitly requested TUI views distinct on the clipboard."""

    return project_summarize_clipboard(result).text


def _initial_tui_range_mode(
    *,
    direct: bool,
    recursive: bool,
) -> ContextReachViewMode:
    """Keep explicit CLI scope while making a flagless TUI dual-view."""

    if direct and recursive:
        raise ValueError("Summarize TUI scope flags are mutually exclusive.")
    if direct:
        return "EXACT"
    if recursive:
        return "SUBTREE"
    return "BOTH"


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
        resources: tuple[MemoryStore, ContextOperandSnapshot] | None = None

        def command_resources() -> tuple[MemoryStore, ContextOperandSnapshot]:
            nonlocal resources
            if resources is None:
                store = MemoryStore(create=False)
                resources = (store, ContextOperandSnapshot.capture(store))
            return resources

        def execute(request: SummarizeRequest):
            # Route validation happens before opening durable or semantic
            # infrastructure, so a forced TUI cannot partially execute when
            # no terminal is available.
            store, snapshot = command_resources()
            return run_summarize_with_store(
                request,
                store=store,
                current_context_name=snapshot.current_name,
                provider_session_factory=_provider_session,
            )

        def prepare_tui(request: SummarizeRequest) -> SummarizeTuiSetup:
            store, snapshot = command_resources()
            selected_access = resolve_context_access(
                store,
                request.context_locator,
                current_name=snapshot.current_name,
                required_permission="READ",
            )
            catalog = freeze_profile_readable_context_catalog(
                store,
                selected_access,
                include_query_routes=False,
            )
            names = tuple(catalog.list_context_names())
            annotations = tuple(
                (name, context_access_display_facts(access))
                for name in names
                if (access := catalog.access_for(name)).is_granted
            )
            current = snapshot.current_name
            return SummarizeTuiSetup(
                names=names,
                selected_context=selected_access.display_name,
                initial_range_mode=_initial_tui_range_mode(
                    direct=direct,
                    recursive=recursive,
                ),
                current_context=current if current in names else None,
                annotations=annotations,
            )

        runner = build_summarize_console_runner(
            execute=execute,
            prepare_tui=prepare_tui,
            clipboard_writer=write_system_clipboard,
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

    if result is None:
        typer.echo("Summarize cancelled.")
        return

    if copy_result:
        clipboard_text = _summarize_clipboard_text(result)
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
