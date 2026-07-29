"""Render a concise implementation inventory for the top-level CLI."""
from __future__ import annotations

import click
import typer


IMPLEMENTATION_LEVELS = {
    "add": "implemented",
    "atomize": "implemented",
    "branch": "implemented",
    "checkout": "alias",
    "checkpoint": "implemented",
    "chunk": "implemented",
    "clear": "implemented",
    "config": "legacy",
    "contexts": "implemented",
    "delete": "implemented",
    "diff": "partial",
    "edit": "implemented",
    "embed": "implemented",
    "find": "implemented",
    "find-ambiguities": "implemented",
    "find-conflicts": "implemented",
    "find-duplicates": "implemented",
    "forget": "legacy",
    "help": "implemented",
    "impact": "partial",
    "init": "implemented",
    "integrate": "legacy",
    "list": "implemented",
    "log": "implemented",
    "ls": "alias",
    "merge": "partial",
    "query": "implemented",
    "rationale": "implemented",
    "reference": "implemented",
    "remove": "implemented",
    "revert": "implemented",
    "review": "partial",
    "show": "implemented",
    "status": "implemented",
    "switch": "implemented",
    "trace": "implemented",
    "update": "partial",
}

LEVEL_DESCRIPTIONS = (
    "implemented = advertised behavior is available",
    "partial = only a bounded subset is available",
    "legacy = older path outside the current workflow",
    "alias = alternate name for another command",
)


def _visible_commands(ctx: click.Context) -> list[tuple[str, click.Command]]:
    """Return visible root commands in the same canonical order as Click."""
    if not isinstance(ctx.command, click.Group):
        raise RuntimeError("The root CLI is not a command group.")

    commands: list[tuple[str, click.Command]] = []
    for name in ctx.command.list_commands(ctx):
        command = ctx.command.get_command(ctx, name)
        if command is None or command.hidden:
            continue
        commands.append((name, command))
    return commands


def cmd(ctx: typer.Context) -> None:
    """List command names, implementation levels, and short descriptions."""
    root = ctx.parent
    if root is None:
        typer.secho(
            "Help error: no root command context.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    commands = _visible_commands(root)
    visible_names = {name for name, _ in commands}
    missing = sorted(visible_names - IMPLEMENTATION_LEVELS.keys())
    stale = sorted(IMPLEMENTATION_LEVELS.keys() - visible_names)
    if missing or stale:
        details = []
        if missing:
            details.append("unclassified: " + ", ".join(missing))
        if stale:
            details.append("not registered: " + ", ".join(stale))
        typer.secho(
            "Help inventory error: " + "; ".join(details),
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.secho("mem command inventory", bold=True)
    typer.echo("Levels: " + "; ".join(LEVEL_DESCRIPTIONS))
    typer.echo()

    name_width = max(len(name) for name, _ in commands)
    level_width = max(len(level) for level in IMPLEMENTATION_LEVELS.values())
    for name, command in commands:
        description = " ".join((command.help or "No description.").split())
        typer.echo(
            f"{name:<{name_width}} - "
            f"{IMPLEMENTATION_LEVELS[name]:<{level_width}} - "
            f"{description}"
        )
