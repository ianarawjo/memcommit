"""Render actual Sync file effects and committed automatic settings."""

import typer

from memcommit.adapters.console.terminal.core.text import display_escape_text as escape
from memcommit.adapters.console.terminal.core.theme import (
    semantic_action_role,
    semantic_color_rgb,
)


def render_sync_receipt(result):
    if result.conflict_choice:
        typer.echo(
            "Used "
            + ("mem" if result.conflict_choice == "mem" else "workspace files")
            + " for all conflicts."
        )
    if result.context_effects:
        typer.echo(f"Synced project documents. [sync {result.run_uid[:8]}]")
        for action, name, target in result.context_effects:
            role = semantic_action_role(action)
            label = (
                typer.style(action, fg=semantic_color_rgb(role), bold=True)
                if role
                else action
            )
            typer.echo(
                f"  {label} CONTEXT · {escape(name)}"
                + (f" → {escape(target)}" if target else "")
            )
    if result.run_uid and not result.context_effects:
        if all(effect.action == "UNCHANGED" for effect in result.effects):
            typer.echo(
                f"Sync checked {len(result.context_names)} Context(s); files already match. [sync {result.run_uid[:8]}]"
            )
        else:
            typer.echo(
                f"Synced {len(result.context_names)} Context(s). [sync {result.run_uid[:8]}]"
            )
    elif not result.run_uid:
        typer.echo(
            f"Sync checked {len(result.context_names)} Context(s); files already match."
        )
    for effect in result.effects:
        if result.checkpoint_uids and effect.action == "UNCHANGED":
            continue
        role = semantic_action_role(effect.action)
        label = (
            typer.style(effect.action, fg=semantic_color_rgb(role), bold=True)
            if role
            else effect.action
        )
        typer.echo("  " + label + " · " + escape(effect.path))


def render_sync_error(error):
    typer.echo("Sync failed: " + escape(str(error)), err=True)
