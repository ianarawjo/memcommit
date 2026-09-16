"""Read-only operation Context browser and its noninteractive projection."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.components.context_picker.projection import (
    context_memory_rows,
)
from memcommit.adapters.console.terminal.components.context_picker.rendering import (
    render_memory_rows,
)
from memcommit.adapters.console.terminal.components.context_viewer.shell import (
    run_context_viewer,
)
from memcommit.adapters.console.terminal.core.capabilities import (
    is_interactive_terminal,
)
from memcommit.adapters.console.terminal.core.text import safe_terminal_text
from memcommit.application.operations.config.operation_contexts import (
    OperationContextEntry,
    list_operation_contexts,
)
from memcommit.persistence.operation_contexts.repository import (
    OperationContextRepository,
)


def operation_context_fragments(
    entry: OperationContextEntry, *, wrap_width: int | None = None
) -> list[tuple[str, str]]:
    if entry.error is not None:
        return [
            (
                "class:report-neutral",
                "Could not read Context: " + safe_terminal_text(entry.error),
            )
        ]
    assert entry.context is not None
    rows = context_memory_rows(entry.context)
    if not rows:
        return [("class:report-neutral", "(empty Context)")]
    # Keep the Switch renderer's exact UID/body grammar in the standalone pane.
    fragments = render_memory_rows(
        rows, context_name=entry.name, show_item_marker=False, wrap_width=wrap_width
    )
    return fragments[1:] if fragments and fragments[0] == ("", "\n") else fragments


def operation_contexts() -> None:
    """Browse Contexts packaged with operations."""
    entries = list_operation_contexts(OperationContextRepository())
    if not entries:
        typer.echo("(no operation Contexts found)")
        return
    by_name = {entry.name: entry for entry in entries}
    if is_interactive_terminal():
        run_context_viewer(
            tuple(by_name),
            lambda name, width: operation_context_fragments(
                by_name[name], wrap_width=width
            ),
            title="OPERATION CONTEXTS",
            folder_parents=True,
            compact_names=True,
        )
    else:
        for index, entry in enumerate(entries):
            if index:
                typer.echo()
            typer.echo(safe_terminal_text(entry.name))
            typer.echo(
                "".join(text for _style, text in operation_context_fragments(entry))
            )
    if any(entry.error is not None for entry in entries):
        raise typer.Exit(1)
