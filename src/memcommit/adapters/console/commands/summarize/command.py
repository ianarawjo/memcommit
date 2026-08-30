"""Render the shared understanding-summary unit for one Context."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Annotated, Iterator, Optional

import typer

from memcommit.adapters.console.clipboard import ClipboardError, write_system_clipboard
from memcommit.persistence.command_ledger.attempts import annotate_read_report_attempt
from memcommit.adapters.console.terminal.components.progress import CommandProgress
from memcommit.adapters.console.coordination.context_operand import (
    ContextOperandSnapshot,
)
from memcommit.adapters.console.coordination.context_scope_options import (
    ContextScopePreset,
    resolve_context_traversal,
    resolve_scope_preset,
)
from memcommit.adapters.console.terminal.core.text import display_escape_text
from memcommit.adapters.console.commands.summarize.presentation import (
    render_summarize_plain,
)
from memcommit.application.operations.profile.config import ProfileConfigError
from memcommit.application.operations.profile.model import ProfileError
from memcommit.providers.subscription import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.persistence.store import MemoryStore
from memcommit.application.capabilities.reviewing.read_report import ReadReportTarget
from memcommit.application.operations.summarize.model import (
    SummarizeError,
    SummarizeProvider,
)
from memcommit.application.operations.summarize.application import (
    SummarizeRequest,
    SummarizeResult,
)
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
    result: SummarizeResult,
) -> str:
    """Copy the complete understanding body from the single Summary result."""

    return display_escape_text(result.understanding.text)


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
) -> None:
    """Summarize what Mem understands; never change or checkpoint a Context."""
    try:
        preset = resolve_scope_preset(
            direct=direct,
            recursive=recursive,
            default=ContextScopePreset.DIRECT,
        )
        traversal = resolve_context_traversal(preset=preset)

        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        result = run_summarize_with_store(
            SummarizeRequest(
                context_locator=context_name,
                include_descendants=traversal.include_descendants,
                follow_embeds=traversal.follow_embeds,
            ),
            store=store,
            current_context_name=snapshot.current_name,
            provider_session_factory=_provider_session,
        )
        render_summarize_plain(result)
        annotate_read_report_attempt(
            ReadReportTarget(
                operation="summarize",
                context_names=(result.context_name,),
                target_names=(result.context_name,),
                selection_mode="SINGLE",
                ranges=("RECURSIVE" if result.include_descendants else "DIRECT",),
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
        ValueError,
    ) as error:
        typer.secho(
            "Summarize error: " + display_escape_text(str(error)),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

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
            "Copied Summary as plain text; no structured clipboard stage was created.",
            fg=typer.colors.GREEN,
            err=True,
        )
