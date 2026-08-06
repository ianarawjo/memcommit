"""Render the shared understanding-summary unit for one Context."""
from __future__ import annotations

from typing import Annotated, Optional

import typer

from memcommit.commands.command_progress import CommandProgress
from memcommit.commands.context_operand import ContextOperandSnapshot
from memcommit.commands.granted_context import (
    GrantedReadStore,
    freeze_granted_context_binding,
    resolve_context_access,
    revalidate_granted_context_binding,
)
from memcommit.commands.tui_primitives import display_escape_text
from memcommit.commands.understanding_render import understanding_lines
from memcommit.profile_config import ProfileConfigError
from memcommit.profiles import ProfileError, authority_grant_snapshot_lock
from memcommit.query_provider import (
    QueryProviderError,
    connect_codex_chatgpt_provider,
)
from memcommit.store import MemoryStore
from memcommit.summarize import (
    SummarizeError,
    SummaryFrame,
    collect_summary_frame,
    summarize_frame,
)


def _load_frame(access, *, recursive: bool, registry=None) -> SummaryFrame:
    if access.is_granted:
        store = GrantedReadStore(access, registry=registry)
        context = (
            store.load(access.display_name)
            if recursive
            else store.load_direct(access.display_name)
        )
    else:
        context = (
            access.store.load(access.context_name)
            if recursive
            else access.store.load_direct(access.context_name)
        )
    return collect_summary_frame(context, recursive=recursive)


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
            "--direct",
            help="Summarize only directly owned ordinary Memories",
        ),
    ] = False,
) -> None:
    """Summarize what Mem understands; never change or checkpoint a Context."""
    recursive = not direct
    try:
        store = MemoryStore(create=False)
        snapshot = ContextOperandSnapshot.capture(store)
        with authority_grant_snapshot_lock() as registry:
            access = resolve_context_access(
                store,
                context_name,
                current_name=snapshot.current_name,
                required_permission="READ",
                registry=registry,
            )
            binding = (
                freeze_granted_context_binding(access)
                if access.is_granted
                else None
            )
            frame = _load_frame(
                access,
                recursive=recursive,
                registry=registry,
            )
        if frame.sources:
            with CommandProgress(
                "SUMMARIZE",
                "connecting provider",
                total=2,
            ) as progress:
                provider = connect_codex_chatgpt_provider()
                progress.update("summarizing memories", step=2)
                summary = summarize_frame(frame, provider)
        else:
            summary = summarize_frame(frame, _UnavailableProvider())

        if binding is not None:
            with authority_grant_snapshot_lock() as registry:
                current_access = revalidate_granted_context_binding(
                    binding,
                    registry=registry,
                )
                current_frame = _load_frame(
                    current_access,
                    recursive=recursive,
                    registry=registry,
                )
        else:
            current_access = resolve_context_access(
                store,
                frame.context_name,
                current_name=snapshot.current_name,
                required_permission="READ",
            )
            current_frame = _load_frame(
                current_access,
                recursive=recursive,
            )
        if current_frame.digest != frame.digest:
            raise SummarizeError(
                "The selected Context changed while summarization was running; "
                "no summary was published."
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

    typer.secho(
        "SUMMARY · " + display_escape_text(frame.context_name),
        bold=True,
    )
    typer.echo("STATUS · READ-ONLY · " + ("RECURSIVE" if recursive else "DIRECT"))
    typer.echo()
    for line in understanding_lines(summary):
        typer.echo(line)


class _UnavailableProvider:
    """Prove that an empty frame never connects to a semantic provider."""

    def complete(self, *args, **kwargs):
        raise AssertionError("An empty summary frame must not call a provider.")
