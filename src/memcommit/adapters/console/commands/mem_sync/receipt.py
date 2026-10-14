"""Render actual Sync file effects and committed automatic settings."""

import typer
from memcommit.adapters.console.terminal.core.text import display_escape_text as escape
from memcommit.adapters.console.terminal.core.theme import (
    semantic_action_role,
    semantic_color_rgb,
)


def render_sync_receipt(result):
    if result.error:
        typer.echo(
            "Automatic Sync failed after the command committed: "
            + escape(result.error)
            + " Retry 'mem sync' alone.",
            err=True,
        )
        return
    if result.run_uid:
        prefix = "Automatically synced" if result.automatic else "Synced"
        typer.echo(
            f"{prefix} {len(result.context_names)} Context(s). [sync {result.run_uid[:8]}]"
        )
    elif not result.automatic_change:
        typer.echo(
            f"Sync checked {len(result.context_names)} Context(s); files already match."
        )
    for effect in result.effects:
        role = semantic_action_role(effect.action)
        label = (
            typer.style(effect.action, fg=semantic_color_rgb(role), bold=True)
            if role
            else effect.action
        )
        typer.echo("  " + label + " · " + escape(effect.path))
    change = result.automatic_change
    if change:
        action = "enabled" if change.enabled else "disabled"
        if not change.context_names:
            typer.echo(f"Automatic Sync {action} for this Profile, including future Contexts.")
            return
        suffix = (
            f" ({change.newly_enabled} newly enabled, {change.already_enabled} already enabled)"
            if change.enabled and change.already_enabled
            else ""
        )
        names = (
            "'" + escape(change.context_names[0]) + "'"
            if len(change.context_names) == 1
            else f"{len(change.context_names)} Contexts"
        )
        typer.echo(f"Automatic Sync {action} for {names}{suffix}.")


def render_sync_error(error):
    typer.echo("Sync failed: " + escape(str(error)), err=True)
