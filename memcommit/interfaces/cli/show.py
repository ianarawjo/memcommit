"""Plain console projection for typed read-only Show results."""

from __future__ import annotations

import shlex
from dataclasses import replace

import typer

from memcommit.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.interfaces.console.theme import memory_object_color_rgb
from memcommit.show_application import (
    ShowContextSnapshot,
    ShowEmbeddedContext,
    ShowMemory,
    ShowMemoryReference,
    ShowQueryView,
    ShowResult,
)
from memcommit.source_projection.console import (
    styled_source_object_label,
    styled_source_relationship_label,
)
from memcommit.source_projection.model import SourceForm, SourceReach
from memcommit.source_projection.presentation import (
    source_annotation_text,
    source_display_text,
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
    typer.secho(f"{label}: {display_escape_text(memory.uid)}", bold=True)
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo()
    _render_memory_content(memory.content)


def _render_memory_ref(
    memory_ref: ShowMemoryReference,
    context_name: str,
) -> None:
    relationship_label = styled_source_object_label(
        memory_ref.source,
        title=True,
    )
    typer.secho(
        f"{relationship_label}: " f"{display_escape_text(memory_ref.uid)}",
        bold=True,
    )
    typer.echo(f"Context: {display_escape_text(context_name)}")
    typer.echo(f"State: {source_annotation_text(memory_ref.source)}")
    typer.echo(
        f"Source: {display_escape_text(memory_ref.target_context_name)} "
        f"[{display_escape_text(memory_ref.target_context_uid[:8])}]"
    )
    typer.echo("Target Memory: " + display_escape_text(memory_ref.target_memory_uid))
    typer.echo()
    if memory_ref.content is None:
        typer.secho(
            "(embedded Memory Source is unavailable)",
            fg=typer.colors.YELLOW,
        )
    else:
        _render_memory_content(memory_ref.content)


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
    query_views = [item for item in context.items if isinstance(item, ShowQueryView)]
    embedded = [item for item in context.items if isinstance(item, ShowEmbeddedContext)]

    typer.secho(f"Context: {display_escape_text(context.name)}", bold=True)
    direct_source = replace(context.source, reach=SourceReach.DIRECT)
    annotation = source_display_text(direct_source)
    if annotation:
        typer.echo(f"Access: {annotation}")
    if context.source.reach is not SourceReach.DIRECT:
        typer.echo(
            "Reach: "
            + display_escape_text(context.source.reach.value.replace("_", " "))
        )
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
            label = styled_source_relationship_label(item.source)
            typer.echo(
                f"  [{label} "
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
            label = styled_source_relationship_label(item.source)
            typer.echo(
                f"  [{label} "
                f"{display_escape_text(item.uid[:8])}] "
                f"[{display_escape_text(item.target_context_name)}]"
                f"[memory {display_escape_text(item.target_memory_uid[:8])}]"
                + (f"  {annotation}" if annotation else "")
            )
            if item.content is not None:
                _render_memory_content(item.content, prefix="           ")
        else:
            typer.echo(
                f"  [{source_object_label(item.source)} "
                f"{display_escape_text(item.uid[:8])}] ",
                nl=False,
            )
            _render_memory_content(item.content)
            if annotation:
                typer.echo(f"    {annotation}")


def _context_counts(context: ShowContextSnapshot) -> tuple[int, int, int, int]:
    return (
        sum(isinstance(item, ShowMemory) for item in context.items),
        sum(isinstance(item, ShowMemoryReference) for item in context.items),
        sum(isinstance(item, ShowQueryView) for item in context.items),
        sum(isinstance(item, ShowEmbeddedContext) for item in context.items),
    )


def _render_recursive_scope(result: ShowResult) -> None:
    totals = tuple(
        sum(values)
        for values in zip(
            *(_context_counts(context) for context in result.contexts),
            strict=True,
        )
    )
    typer.secho(
        "Recursive scope: " + display_escape_text(result.resolved_context_name),
        bold=True,
    )
    typer.echo(
        f"  Contexts {len(result.contexts)}"
        f"  |  Memories {totals[0]}"
        f"  |  Memory Refs {totals[1]}"
        f"  |  Query Views {totals[2]}"
        f"  |  Embedded Contexts {totals[3]}"
    )
    for context in result.contexts:
        typer.echo()
        _render_context(context)


def render_show(result: ShowResult) -> None:
    """Preserve established ``mem show`` output over one typed result."""

    if result.include_descendants or result.follow_embeds:
        _render_recursive_scope(result)
        return
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
