"""Plain command-line projection for typed Status results."""

from __future__ import annotations

import typer

from memcommit.adapters.interfaces.console.text import display_escape_text, safe_terminal_text
from memcommit.source_projection.model import SourceAccess
from memcommit.source_projection.presentation import source_display_text
from memcommit.application.operations.status.application import StatusContextResult, StatusResult


_COUNT_LABELS = (
    "Memories",
    "Memory Refs",
    "Query Views",
    "Embedded Contexts",
    "Grants",
    "Checkpoints",
)


def _lineage(name: str) -> str:
    return " > ".join(name.split("/"))


def _access_label(context: StatusContextResult) -> str:
    if context.source.access is SourceAccess.OWNED:
        return "OWNED"
    label = source_display_text(context.source, include_permissions=True)
    if context.access_grant_uid is not None:
        label += f" · {context.access_grant_uid[:8]} r{context.access_grant_revision}"
    return label


def _count_values(context: StatusContextResult) -> tuple[int, ...]:
    return (
        context.memory_count,
        len(context.memory_references),
        len(context.query_views),
        len(context.embedded_contexts),
        len(context.grants),
        context.checkpoint_count,
    )


def _visible_counts(
    values: tuple[int, ...],
    *,
    separator: str,
    empty: str,
) -> str:
    labelled = tuple(zip(_COUNT_LABELS, values, strict=True))
    visible = tuple(f"{label} {value}" for label, value in labelled if value)
    return separator.join(visible) if visible else empty


def _inline_counts(context: StatusContextResult) -> str:
    return _visible_counts(
        _count_values(context),
        separator=" · ",
        empty="Direct inventory empty",
    )


def _recursive_count_values(result: StatusResult) -> tuple[int, ...]:
    return tuple(
        sum(values)
        for values in zip(
            *(_count_values(context) for context in result.contexts),
            strict=True,
        )
    )


def _render_short(result: StatusResult, *, branch: bool) -> None:
    for context in result.contexts:
        prefix = (
            f"## {result.profile_name} :: {_lineage(context.name)}"
            if branch
            else context.name
        )
        typer.echo(
            f"{display_escape_text(prefix)} [{_access_label(context)}] · "
            + _inline_counts(context)
        )


def _render_recursive_overview(result: StatusResult) -> None:
    typer.secho("\nRecursive scope", bold=True, nl=False)
    typer.echo(
        f" · Contexts {len(result.contexts)}  |  "
        + _visible_counts(
            _recursive_count_values(result),
            separator="  |  ",
            empty="Inventory empty",
        )
    )
    for index, context in enumerate(result.contexts):
        current = " · CURRENT" if index == 0 else ""
        typer.echo(
            f"  {display_escape_text(context.name)} "
            f"[{_access_label(context)}]{current} · "
            + _visible_counts(
                _count_values(context),
                separator="  |  ",
                empty="Direct inventory empty",
            )
        )


def _render_relationships(context: StatusContextResult) -> None:
    if not (
        context.memory_references
        or context.query_views
        or context.embedded_contexts
        or context.grants
    ):
        return
    typer.secho("\nRelationships:", bold=True)
    for item in context.memory_references:
        typer.echo(
            f"  MEMORY REF [{display_escape_text(item.uid[:8])}] "
            f"{display_escape_text(item.target_context_name)}#"
            f"{display_escape_text(item.target_memory_uid[:8])}"
        )
    for item in context.query_views:
        typer.echo(
            f"  QUERY VIEW [{display_escape_text(item.uid[:8])}] "
            f"{display_escape_text(item.name)}"
        )
    for item in context.embedded_contexts:
        typer.echo(
            f"  {'CONTEXT REFERENCE' if item.snapshot else 'EMBEDDED CONTEXT'} "
            f"[{display_escape_text(item.uid[:8])}] "
            f"{display_escape_text(item.name)}"
        )
    for grant in context.grants:
        permissions = " + ".join(grant.permissions) or "NONE"
        typer.echo(
            f"  GRANT [{display_escape_text(grant.uid[:8])} r{grant.revision}] "
            f"{display_escape_text(grant.public_name)} · PERMISSIONS "
            f"{display_escape_text(permissions)}"
        )


def _render_memory_preview(context: StatusContextResult) -> None:
    if not context.memory_preview:
        return
    typer.secho(
        "\nMemory preview · "
        f"first {len(context.memory_preview)} of {context.memory_count}:",
        bold=True,
    )
    for memory in context.memory_preview:
        typer.echo(f"  [{display_escape_text(memory.uid[:8])}] ", nl=False)
        lines = safe_terminal_text(memory.content).splitlines()
        preview = "\n         ".join(lines[:5])
        suffix = "\n         …" if len(lines) > 5 else ""
        typer.echo(f"{preview}{suffix}")


def _render_recent_changes(context: StatusContextResult) -> None:
    if not context.recent_checkpoints:
        return
    typer.secho(
        "\nRecent changes · latest "
        f"{len(context.recent_checkpoints)} of {context.checkpoint_count} checkpoints:",
        bold=True,
    )
    for checkpoint in context.recent_checkpoints:
        timestamp = checkpoint.timestamp[:16].replace("T", " ")
        command = checkpoint.command if checkpoint.automatic else "checkpoint"
        description = " ".join(checkpoint.description.split())
        typer.echo(
            f"  {display_escape_text(checkpoint.uid[:8])}  "
            f"{display_escape_text(timestamp)}  "
            f"{display_escape_text(command):<12}  "
            f"{display_escape_text(description)}"
        )


def render_status(
    result: StatusResult,
    *,
    short: bool,
    branch: bool,
) -> None:
    """Render one typed Status result without owning read or scope policy."""

    if short:
        _render_short(result, branch=branch)
        return
    if branch:
        typer.secho(f"Profile: {display_escape_text(result.profile_name)}", bold=True)
        typer.echo(
            "Context lineage: "
            + display_escape_text(_lineage(result.current_context_name))
        )
    current = result.current
    typer.secho(
        f"On context: {display_escape_text(result.current_context_name)}",
        bold=True,
    )
    if current.source.access is not SourceAccess.OWNED:
        typer.secho(
            "  Access: "
            + source_display_text(current.source, include_permissions=True),
            dim=True,
        )
    recursive = result.include_descendants or result.follow_embeds
    if recursive:
        _render_recursive_overview(result)
    else:
        typer.secho("\nInventory", bold=True, nl=False)
        typer.echo(" · " + _inline_counts(current))
        _render_relationships(current)
        _render_memory_preview(current)
        _render_recent_changes(current)


__all__ = ["render_status"]
