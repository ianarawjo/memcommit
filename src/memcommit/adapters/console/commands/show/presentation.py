"""Plain console projection for typed read-only Show results."""

from __future__ import annotations


import typer

from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.adapters.console.terminal.core.theme import memory_object_color_rgb
from memcommit.application.operations.show.application import (
    ShowContextSnapshot,
    ShowMemory,
    ShowResult,
)
from memcommit.source_projection.model import SourceForm, SourceReach
from memcommit.source_projection.presentation import (
    source_object_label,
)


def _render_memory_content(content: str, *, prefix: str = "") -> None:
    """Keep every visible Memory body on the shared semantic foreground."""

    typer.secho(
        f"{prefix}{safe_terminal_text(content)}",
        fg=memory_object_color_rgb(),
    )


def _render_memory(memory: ShowMemory, context_name: str) -> None:
    label = source_object_label(SourceForm.MEMORY, title=True)
    # A direct lookup already identifies one complete object, so keep its owner
    # and durable identity adjacent to the body instead of spending a header
    # block on metadata that does not need independent scanning.
    typer.echo(
        f"[{label} {display_escape_text(context_name)}:"
        f"{display_escape_text(memory.uid)}] ",
        nl=False,
    )
    _render_memory_content(memory.content)


def _render_context(context: ShowContextSnapshot) -> None:
    typer.secho(f"Context: {display_escape_text(context.name)}", bold=True)
    if context.source.reach is not SourceReach.DIRECT:
        typer.echo("Reach: " + context.source.reach.value)
    typer.echo(f"  Memories {len(context.items)}")
    if not context.items:
        typer.echo("\n  (no items)")
        return
    typer.secho("\nItems (in context order):", bold=True)
    for memory in context.items:
        typer.echo(f"  [memory {display_escape_text(memory.uid[:8])}] ", nl=False)
        _render_memory_content(memory.content)


def render_show(result: ShowResult) -> None:
    """Preserve ordinary Show presentation over the complete typed scope."""
    if isinstance(result.value, ShowMemory):
        _render_memory(result.value, result.resolved_context_name)
    elif result.include_descendants:
        typer.secho(
            "Recursive scope: " + display_escape_text(result.resolved_context_name),
            bold=True,
        )
        typer.echo(
            f"  Contexts {len(result.contexts)}  |  Memories {sum(len(context.items) for context in result.contexts)}"
        )
        for context in result.contexts:
            typer.echo()
            _render_context(context)
    else:
        _render_context(result.value)
