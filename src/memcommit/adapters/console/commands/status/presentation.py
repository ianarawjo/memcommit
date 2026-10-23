"""Plain terminal presentation for typed Status results."""

from __future__ import annotations

import typer

from memcommit.adapters.console.terminal.core.text import (
    display_escape_text,
    safe_terminal_text,
)
from memcommit.application.operations.status.application import (
    StatusContextResult,
    StatusResult,
)


_COUNT_LABELS = (
    "Memories",
    "Checkpoints",
)


def _lineage(name: str) -> str:
    return " > ".join(name.split("/"))


def _count_values(context: StatusContextResult) -> tuple[int, ...]:
    return (
        context.memory_count,
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
            f"{display_escape_text(prefix)} [{'OWNED'}] · " + _inline_counts(context)
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
            f"[{'OWNED'}]{current} · "
            + _visible_counts(
                _count_values(context),
                separator="  |  ",
                empty="Direct inventory empty",
            )
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
    recursive = result.include_descendants
    if recursive:
        _render_recursive_overview(result)
    else:
        typer.secho("\nInventory", bold=True, nl=False)
        typer.echo(" · " + _inline_counts(current))
        _render_memory_preview(current)
        _render_recent_changes(current)


__all__ = ["render_status"]
