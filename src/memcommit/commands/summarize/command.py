"""Render the shared understanding-summary unit for one Context."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated, Iterator, Optional

import typer

from memcommit.bootstrap import build_summarize_console_runner
from memcommit.infrastructure.clipboard import ClipboardError, write_system_clipboard
from memcommit.infrastructure.command_ledger.attempts import annotate_read_report_attempt
from memcommit.commands.shared.command_progress import CommandProgress
from memcommit.commands.shared.context_operand import ContextOperandSnapshot
from memcommit.interfaces.tui.components.operation_launcher.location import (
    operation_launcher_orientation,
)
from memcommit.application.authority.access import (
    context_access_display_facts,
    resolve_context_access,
)
from memcommit.commands.shared.readable_context_catalog import (
    freeze_profile_readable_context_catalog,
)
from memcommit.context_targeting.presets import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.context_targeting.tui.picker import context_memory_rows
from memcommit.context_targeting.tui.reach import ContextReachViewMode
from memcommit.interfaces.console import (
    ConsoleMode,
    ConsoleModeError,
    SystemTerminalCapabilities,
    resolve_console_mode,
)
from memcommit.interfaces.tui.workbenches.read_report import (
    ReadReportSelectTarget,
    choose_read_report_recent,
)
from memcommit.interfaces.console.text import display_escape_text
from memcommit.interfaces.tui.operations.summarize import (
    SummarizeTuiOutcome,
    SummarizeTuiSetup,
    project_summarize_clipboard,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.infrastructure.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.reviewing.read_report import ReadReportError, ReadReportTarget
from memcommit.application.reviewing.read_report_recents import (
    read_report_recents,
    revalidate_read_report_recent,
)
from memcommit.application.operations.summarize.model import SummarizeError, SummarizeProvider
from memcommit.application.operations.summarize.application import SummarizeRequest, SummarizeResult
from memcommit.application.operations.summarize.runtime import run_summarize_with_store


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
                "Copy the verified Summary document as plain "
                "text without creating a structured mutation stage"
            ),
        ),
    ] = False,
    plain: Annotated[
        bool,
        typer.Option(
            "--plain",
            help="Print the result (the default without --tui)",
        ),
    ] = False,
    tui: Annotated[
        bool,
        typer.Option(
            "--tui",
            help="Open the interactive Recent, Context, range, and result flow",
        ),
    ] = False,
) -> None:
    """Summarize what Mem understands; never change or checkpoint a Context."""
    try:
        mode = resolve_console_mode(plain=plain, tui=tui)
        terminal = SystemTerminalCapabilities()
        # A missing Context operand is still a complete request because
        # Summarize owns the current-Context/direct defaults. Keep executable
        # argv in the primary terminal flow; the broader Recent/target/range
        # workbench is an explicit --tui action, as with supplied-pattern Find.
        if mode is ConsoleMode.AUTO:
            mode = ConsoleMode.PLAIN
        resources: tuple[MemoryStore, ContextOperandSnapshot] | None = None

        def command_resources() -> tuple[MemoryStore, ContextOperandSnapshot]:
            nonlocal resources
            if resources is None:
                store = MemoryStore(create=False)
                resources = (store, ContextOperandSnapshot.capture(store))
            return resources

        if (
            context_name is None
            and not direct
            and not recursive
            and mode is not ConsoleMode.PLAIN
            and terminal.is_interactive()
        ):
            store, _snapshot = command_resources()
            recents = read_report_recents(store, operation="summarize")
            launch = choose_read_report_recent(
                recents,
                operation="summarize",
                orientation=operation_launcher_orientation(store),
            )
            if launch is None:
                typer.echo("Summarize cancelled.")
                return
            if isinstance(launch, ReadReportTarget):
                matching = next(
                    (recent for recent in recents if recent.target == launch),
                    None,
                )
                if matching is None:
                    raise ReadReportError(
                        "Summarize launcher returned an unknown recent target."
                    )
                launch = revalidate_read_report_recent(store, matching)
                if len(launch.target_names) != 1:
                    raise ReadReportError(
                        "Summarize recent target must contain one Context."
                    )
                context_name = launch.target_names[0]
                direct = launch.ranges == ("DIRECT",)
                recursive = launch.ranges == ("RECURSIVE",)
            elif not isinstance(launch, ReadReportSelectTarget):
                raise ReadReportError("Summarize launcher returned an invalid action.")

        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)

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
                memory_loader=lambda name: context_memory_rows(
                    catalog.load_direct(name)
                ),
            )

        runner = build_summarize_console_runner(
            execute=execute,
            prepare_tui=prepare_tui,
            clipboard_writer=write_system_clipboard,
            terminal=terminal,
        )
        result = runner.run(
            SummarizeRequest(
                context_locator=context_name,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            ),
            mode=mode,
        )
        if isinstance(result, SummarizeTuiOutcome):
            annotate_read_report_attempt(
                ReadReportTarget(
                    operation="summarize",
                    context_names=(result.results[0].context_name,),
                    target_names=(result.results[0].context_name,),
                    selection_mode="SINGLE",
                    ranges=tuple(
                        "RECURSIVE" if item.include_descendants else "DIRECT"
                        for item in result.results
                    ),
                )
            )
        elif isinstance(result, SummarizeResult):
            annotate_read_report_attempt(
                ReadReportTarget(
                    operation="summarize",
                    context_names=(result.context_name,),
                    target_names=(result.context_name,),
                    selection_mode="SINGLE",
                    ranges=(
                        "RECURSIVE" if result.include_descendants else "DIRECT",
                    ),
                )
            )
    except (
        FileNotFoundError,
        OSError,
        ProfileConfigError,
        ProfileError,
        QueryProviderError,
        RuntimeError,
        SummarizeError,
        ReadReportError,
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
            "Copied Summary as plain text; no structured "
            "clipboard stage was created.",
            fg=typer.colors.GREEN,
            err=True,
        )
