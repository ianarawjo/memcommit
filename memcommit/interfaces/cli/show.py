"""Plain console projection for typed read-only Show results."""

from __future__ import annotations

import shlex

import typer

from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.show_application import (
    ShowContextSnapshot,
    ShowEmbeddedContext,
    ShowMemory,
    ShowMemoryReference,
    ShowQueryView,
    ShowResult,
)
from memcommit.source_projection.model import SourceForm
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_display_text,
    source_object_label,
)


def _render_memory(memory: ShowMemory, context_name: str) -> None:
    label = source_object_label(SourceForm.MEMORY, title=True)
    typer.secho(f"{label}: {display_escape_text(memory.uid)}", bold=True)
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo()
    typer.echo(safe_terminal_text(memory.content))


def _render_memory_ref(
    memory_ref: ShowMemoryReference,
    context_name: str,
) -> None:
    typer.secho(
        f"{source_object_label(memory_ref.source, title=True)}: "
        f"{display_escape_text(memory_ref.uid)}",
        bold=True,
    )
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo(f"State: {source_annotation_text(memory_ref.source)}")
    typer.echo(
        f"Source: {display_escape_text(memory_ref.target_context_name)} "
        f"[{display_escape_text(memory_ref.target_context_uid[:8])}]"
    )
    typer.echo(
        "Target Memory: " + display_escape_text(memory_ref.target_memory_uid)
    )
    typer.echo()
    if memory_ref.content is None:
        typer.secho("(memory ref target is unavailable)", fg=typer.colors.YELLOW)
    else:
        typer.echo(safe_terminal_text(memory_ref.content))


def _render_query_view(query_view: ShowQueryView, context_name: str) -> None:
    label = source_object_label(SourceForm.QUERY_VIEW, title=True)
    typer.secho(f"{label}: {display_escape_text(query_view.name)}", bold=True)
    typer.echo(f"Route: {display_escape_text(query_view.uid)}")
    typer.echo(f"Parent Context: {display_escape_text(context_name)}")
    typer.echo("Mode: QUERY ONLY")
    typer.echo("Content: concealed from mem ls and mem show")
    typer.echo()
    command = shlex.join(["mem", "query", query_view.name, "<question>"])
    typer.echo(f"Ask with: {display_escape_text(command)}")


def _render_context(context: ShowContextSnapshot) -> None:
    memories = [item for item in context.items if isinstance(item, ShowMemory)]
    references = [
        item for item in context.items if isinstance(item, ShowMemoryReference)
    ]
    query_views = [
        item for item in context.items if isinstance(item, ShowQueryView)
    ]
    embedded = [
        item for item in context.items if isinstance(item, ShowEmbeddedContext)
    ]

    typer.secho(f"Context: {display_escape_text(context.name)}", bold=True)
    annotation = source_display_text(context.source)
    if annotation:
        typer.echo(f"Access: {annotation}")
    typer.echo(
        f"  Memories {len(memories)}"
        f"  |  Memory Refs {len(references)}"
        f"  |  Query Views {len(query_views)}"
        f"  |  Embedded Contexts {len(embedded)}"
    )

    if not context.items:
        typer.echo("\n  (no items)")
        return

    typer.secho("\nItems (in context order):", bold=True)
    for item in context.items:
        annotation = source_annotation_text(item.source)
        if isinstance(item, ShowEmbeddedContext):
            typer.echo(
                f"  [{source_object_label(SourceForm.CONTEXT)} "
                f"{display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.name)}"
                + (f"  {annotation}" if annotation else "")
            )
        elif isinstance(item, ShowQueryView):
            typer.echo(
                f"  [{source_object_label(item.source)} "
                f"{display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.name)}"
                + (f"  {annotation}" if annotation else "")
            )
        elif isinstance(item, ShowMemoryReference):
            typer.echo(
                f"  [{source_object_label(item.source)} "
                f"{display_escape_text(item.uid[:8])}] "
                f"{display_escape_text(item.target_context_name)}#"
                f"{display_escape_text(item.target_memory_uid[:8])}"
                + (f"  {annotation}" if annotation else "")
            )
            if item.content is not None:
                typer.secho(
                    f"           {safe_terminal_text(item.content)}",
                    dim=True,
                )
        else:
            typer.echo(
                f"  [{source_object_label(item.source)} "
                f"{display_escape_text(item.uid[:8])}] ",
                nl=False,
            )
            typer.secho(safe_terminal_text(item.content), dim=True)
            if annotation:
                typer.echo(f"    {annotation}")


def render_show(result: ShowResult) -> None:
    """Preserve established ``mem show`` output over one typed result."""

    value = result.value
    if isinstance(value, ShowContextSnapshot):
        _render_context(value)
    elif isinstance(value, ShowMemory):
        _render_memory(value, result.resolved_context_name)
    elif isinstance(value, ShowMemoryReference):
        _render_memory_ref(value, result.resolved_context_name)
    else:
        _render_query_view(value, result.resolved_context_name)


__all__ = ["render_show"]
